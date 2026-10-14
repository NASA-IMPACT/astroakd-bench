"""0.6.4.2 live-host regression: batch 6 returned rewritten/omitted task IDs."""
import asyncio
import json
import unittest
from types import SimpleNamespace as Obj

from benchmark.generator import GenerationError, generate
from benchmark.llm_generation import (
    _resolve_batch_slots, _target_in_question, generate_llm,
)
from benchmark.tests.test_generator import FixtureSession
from benchmark.tests.test_llm_generation_064 import StubResponses


class RewrittenSixthBatch(StubResponses):
    def create(self, **kwargs):
        reply = super().create(**kwargs)
        if len(self.calls) == 6:
            payload = json.loads(reply.output_text)
            # The actual run failed here; simulate a changed-ID, missing-ID,
            # and reordered reply without altering question semantics.
            payload['questions'].reverse()
            payload['questions'][0]['id'] = '5'
            payload['questions'][1]['id'] = None
            payload['questions'][2]['id'] = 'ASTROAKD-020-99999'
            reply.output_text = json.dumps(payload)
        return reply


class UnresolvableThenFixed(StubResponses):
    def create(self, **kwargs):
        reply = super().create(**kwargs)
        if len(self.calls) == 1:
            payload = json.loads(reply.output_text)
            payload['questions'][0]['id'] = 'wrong'
            payload['questions'][0]['question'] = 'How many galaxies are there in a different sky region?'
            reply.output_text = json.dumps(payload)
        return reply


class AlwaysUnresolvable(StubResponses):
    def create(self, **kwargs):
        reply = super().create(**kwargs)
        payload = json.loads(reply.output_text)
        payload['questions'][0]['id'] = None
        payload['questions'][0]['question'] = 'How many galaxies are there in a different sky region?'
        reply.output_text = json.dumps(payload)
        return reply


class TaskIDReconciliationTests(unittest.TestCase):
    def test_sixth_batch_labeled_wrong_and_reordered_but_reference_calls_frozen(self):
        tasks, report = asyncio.run(generate_llm(
            count=50, seed=123, use_mcp=True,
            session_factory=lambda url: FixtureSession(url),
            openai_client_factory=lambda: Obj(responses=RewrittenSixthBatch()),
        ))
        self.assertEqual(len(tasks), 50)
        self.assertEqual(report['openai_requests'], 10)
        self.assertEqual(report['task_id_repairs'], 3)
        self.assertEqual(report['openai_batch_retries'], 0)
        self.assertEqual(report['distinct_archive_target_pairs'], 50)
        corrected = [task for task in tasks if task['provenance']['task_id_repaired']]
        self.assertEqual(len(corrected), 3)
        self.assertTrue(any(task['provenance']['original_llm_task_id'] is None for task in corrected))
        self.assertTrue(all(task['id'].startswith('ASTROAKD-020-') for task in corrected))
        original, _ = asyncio.run(generate(count=50, seed=123,
                         session_factory=lambda url: FixtureSession(url)))
        self.assertEqual([task['reference_call'] for task in tasks],
                         [task['reference_call'] for task in original])

    def test_no_mcp_task_id_repair_keeps_research_only(self):
        tasks, report = asyncio.run(generate_llm(count=50, seed=123, use_mcp=False,
            openai_client_factory=lambda: Obj(responses=RewrittenSixthBatch())))
        self.assertEqual(report['task_id_repairs'], 3)
        self.assertTrue(all(task['reference_call'] is None for task in tasks))
        self.assertEqual(report['web_search_calls'], 10)

    def test_retry_once_only_when_scientific_slot_assignment_unresolvable(self):
        stub = UnresolvableThenFixed()
        tasks, report = asyncio.run(generate_llm(count=5,
            session_factory=lambda url: FixtureSession(url),
            openai_client_factory=lambda: Obj(responses=stub)))
        self.assertEqual(report['openai_requests'], 2)
        self.assertEqual(report['openai_batch_retries'], 1)
        self.assertEqual(report['task_id_repairs'], 0)
        self.assertEqual(len(tasks), 5)
        self.assertIn('Regenerate this entire batch',stub.calls[1]['input'][-1]['content'])

    def test_fails_closed_after_single_retry(self):
        with self.assertRaisesRegex(GenerationError, 'could not be safely aligned after retry'):
            asyncio.run(generate_llm(count=2,
                session_factory=lambda url: FixtureSession(url),
                openai_client_factory=lambda: Obj(responses=AlwaysUnresolvable())))

    def test_ambiguous_sky_target_matches_are_not_guessed(self):
        base = dict(answer_spec={'expected_columns':['obs_id']},
                    question='Which observation IDs?', target='M31')
        batch = [dict(base, id='id-a', module='mast'), dict(base,id='id-b',module='heasarc')]
        rows = [{'id':None,'question':'For M31, what observation IDs exist?'},
                {'id':None,'question':'For M31, what observation IDs exist?'}]
        with self.assertRaisesRegex(GenerationError,'ambiguous'):
            _resolve_batch_slots(rows,batch,use_mcp=True)

    def test_rejects_conflicting_archive_even_with_wrong_id(self):
        batch = [dict(id='id-a', target='M31', module='mast', question='M31',
                      answer_spec={'expected_columns':['obs_id']})]
        with self.assertRaisesRegex(GenerationError,'cannot be safely assigned'):
            _resolve_batch_slots([{'id':'incorrect','question':
                'Using HEASARC, what observation IDs exist near M31?'}], batch, use_mcp=True)

    def test_target_name_boundaries(self):
        self.assertFalse(_target_in_question('M1','What observations cover M101?'))
        self.assertTrue(_target_in_question('M1','What observations cover M1?'))
        self.assertTrue(_target_in_question('NGC 4151','What is the Gaia ID for NGC  4151?'))

if __name__ == '__main__':
    unittest.main()
