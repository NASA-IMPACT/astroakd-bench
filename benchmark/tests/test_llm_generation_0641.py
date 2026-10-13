"""0.6.4.1 host-failure regression: missing archive in first OpenAI batch."""
import asyncio
import json
import unittest
from types import SimpleNamespace as Obj
from benchmark.llm_generation import generate_llm, _ensure_named_archive
from benchmark.generator import GenerationError, generate
from benchmark.tests.test_generator import FixtureSession
from benchmark.tests.test_llm_generation_064 import StubResponses


class OmittingArchiveResponses(StubResponses):
    def create(self, **kwargs):
        reply = super().create(**kwargs)
        payload = json.loads(reply.output_text)
        for row in payload['questions']:
            if row['id'] == 'ASTROAKD-020-00005':
                # Simulates actual failure: omits archive while preserving target.
                slots = json.loads(kwargs['input'][1]['content'].split('SLOTS JSON:\n',1)[1])
                target = next(s['target'] for s in slots if s['id'] == row['id'])
                row['question'] = f'For {target}, what catalog source IDs are present?'
        reply.output_text = json.dumps(payload)
        return reply


class WrongArchiveResponses(StubResponses):
    def create(self, **kwargs):
        reply = super().create(**kwargs)
        payload = json.loads(reply.output_text)
        data = json.loads(kwargs['input'][1]['content'].split('SLOTS JSON:\n',1)[1])
        payload['questions'][0]['question'] = (
            f"Which SIMBAD observation IDs are available for {data[0]['target']}?"
        )
        reply.output_text = json.dumps(payload)
        return reply


class MissingArchiveClosureTests(unittest.TestCase):
    def test_first_batch_omitted_vizier_is_normalized_without_changing_reference_call(self):
        tasks, report = asyncio.run(generate_llm(
            count=50, seed=123, use_mcp=True, use_instructions=True,
            session_factory=lambda url: FixtureSession(url),
            openai_client_factory=lambda: Obj(responses=OmittingArchiveResponses()),
        ))
        self.assertEqual(len(tasks), 50)
        self.assertEqual(report['openai_requests'], 10)
        self.assertEqual(report['archive_name_repairs'], 1)
        repaired = next(t for t in tasks if t['id'] == 'ASTROAKD-020-00005')
        self.assertEqual(repaired['module'], 'vizier')
        self.assertTrue(repaired['question'].startswith('Using VizieR, '))
        self.assertEqual(repaired['provenance']['original_llm_question'],
                         f'For {repaired["target"]}, what catalog source IDs are present?')
        self.assertTrue(repaired['provenance']['archive_name_repaired'])
        base, _ = asyncio.run(generate(
            count=50, seed=123, session_factory=lambda url: FixtureSession(url)))
        self.assertEqual([t['reference_call'] for t in tasks],
                         [t['reference_call'] for t in base])

    def test_absent_archive_only_is_repairable(self):
        t = {'id':'t','module':'vizier'}
        q, edited = _ensure_named_archive('Which sources are near M31?', t)
        self.assertTrue(edited)
        self.assertEqual(q, 'Using VizieR, which sources are near M31?')
        q, edited = _ensure_named_archive('Which VizieR sources are near M31?', t)
        self.assertFalse(edited)
        self.assertEqual(q, 'Which VizieR sources are near M31?')

    def test_conflicting_archive_fails_closed(self):
        with self.assertRaisesRegex(GenerationError, 'conflicting archive'):
            _ensure_named_archive('Which MAST sources are near M31?',
                                  {'id':'t', 'module':'vizier'})
        with self.assertRaisesRegex(GenerationError, 'conflicting archive'):
            _ensure_named_archive('Using VizieR and Gaia, which sources are near M31?',
                                  {'id':'t', 'module':'vizier'})

    def test_malformed_question_still_fails(self):
        class BadResponse(StubResponses):
            def create(self, **kw):
                out = super().create(**kw)
                data = json.loads(out.output_text)
                data['questions'][0]['question'] = 'M31?'
                out.output_text = json.dumps(data)
                return out
        with self.assertRaisesRegex(GenerationError, 'must be 20..450'):
            asyncio.run(generate_llm(count=2,
                session_factory=lambda url: FixtureSession(url),
                openai_client_factory=lambda: Obj(responses=BadResponse())))

if __name__ == '__main__':
    unittest.main()
