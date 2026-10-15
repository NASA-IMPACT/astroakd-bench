"""0.6.7.10 regression: archive budgets, consolidated review and gold safety."""
import asyncio
import csv
import copy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from benchmark.exports import observed_reference_values
from benchmark.gold import gold_finalize
from benchmark.reference_review import reference_review_draft, review_detail
from benchmark.three_arm import _score_one
from benchmark.validator import (ValidationError, atomic_jsonl, execute_task,
                                 parse_archive_overrides, load_jsonl, validate)
from benchmark.tests.test_generator import run_fixture
from benchmark.tests.test_reference_validation import fake_factory, no_wait


class ArchivePolicyTests(unittest.TestCase):
    def test_archive_policy_validations(self):
        self.assertEqual(parse_archive_overrides('mast=60,simbad=30',kind='timeouts'),
                         {'mast':60.0,'simbad':30.0})
        self.assertEqual(parse_archive_overrides('mast=1,gaia=2',kind='attempts'),
                         {'mast':1,'gaia':2})
        self.assertEqual(parse_archive_overrides(None,kind='timeouts'), {})
        for val,kind in [('foo=2','timeouts'),('mast=nan','timeouts'),
                         ('mast=-1','timeouts'),('mast=2,mast=3','timeouts'),
                         ('mast=0','attempts'),('mast=1.5','attempts'),
                         ('mast=9','attempts'),('mast:12','timeouts')]:
            with self.subTest(val=val),self.assertRaises(ValidationError):
                parse_archive_overrides(val,kind=kind)

    def test_total_deadline_avoids_further_attempt(self):
        task=run_fixture(count=5)[0][0][1]  # MAST
        async def slow_call(self, *args, **kwargs):
            await asyncio.sleep(.05)
        from benchmark.tests.test_reference_validation import ValidatingSession
        original=ValidatingSession.call_tool
        try:
            ValidatingSession.call_tool=slow_call
            result=asyncio.run(execute_task(task,url='http://127.0.0.1:8000/mcp',
                       timeout=.1,attempts=3,delay=0,max_rows=20,
                       max_response_bytes=1024*1024,total_deadline=.013,
                       session_factory=fake_factory(),sleep=no_wait))
            self.assertEqual(result['disposition'],'transport_error')
            self.assertEqual(len(result['attempts']),1)
            self.assertIn('timed out',result['attempts'][0]['error']['message'])
        finally:
            ValidatingSession.call_tool=original

    def test_validation_routing_consolidation_and_resume(self):
        tasks,_=run_fixture(count=5)[0]
        with TemporaryDirectory() as root:
            root=Path(root)
            dataset=root/'tasks.jsonl'; refs=root/'references.jsonl'
            report=root/'report.json'; csv_path=root/'reference.csv'
            atomic_jsonl(dataset,tasks)
            async def run(**kwargs):
                return await validate(dataset,refs,report,timeout=2,attempts=2,delay=0,
                    archive_timeouts='mast=0.5,simbad=1',archive_attempts='mast=1',
                    reference_deadline=1.2,csv_output=csv_path,
                    session_factory=fake_factory(),sleep=no_wait,**kwargs)
            pilot=asyncio.run(run(limit=2))
            self.assertEqual(pilot['processed'],2)
            self.assertTrue((root/'reference_review.csv').exists())
            journal=load_jsonl(root/'references.jsonl.progress.jsonl')[0]
            self.assertEqual(journal[0]['effective_timeout_seconds'],1)
            self.assertEqual(journal[1]['effective_timeout_seconds'],.5)
            self.assertEqual(journal[1]['effective_attempt_limit'],1)
            result=asyncio.run(run(resume=True))
            self.assertEqual(result['processed'],5)
            self.assertEqual(len(load_jsonl(refs)[0]),5)
            with (root/'reference_review.csv').open(newline='') as fh:
                rows=list(csv.DictReader(fh))
            self.assertEqual(len(rows),5)
            for col in ('question','archive','target','answer_shape','observed_answer_preview',
                        'reference_answer_status','review_flags','gold_status'):
                self.assertIn(col,rows[0])
            self.assertTrue(all(r['gold_status']=='pending' for r in rows))


class ReviewTests(unittest.TestCase):
    def _references(self, tasks, rows, *, truncated=False):
        # Shape-compatible stored MCP records without archive/network calls.
        import hashlib
        import benchmark.validator as v
        with TemporaryDirectory() as root:
            root=Path(root)
            dataset=root/'dataset.jsonl'; reference=root/'refs.jsonl'
            atomic_jsonl(dataset,tasks)
            task_sha=hashlib.sha256(dataset.read_bytes()).hexdigest()
            recs=[]
            for task, tab_rows in zip(tasks,rows):
                args=task['reference_call']['arguments']
                recs.append({'task_id':task['id'],'module':task['module'],
                    'input_dataset_sha256':task_sha,'reference_call':task['reference_call'],
                    'disposition':'accepted_nonempty' if tab_rows else 'accepted_empty',
                    'response':{'success':True,'module':task['module'],
                        'function':args['function_name'], 'result':{
                            'data':tab_rows, 'row_count':len(tab_rows),
                            'total_rows':len(tab_rows)+8 if truncated else len(tab_rows),
                            'truncated':truncated}},
                    'evaluation':{'checks':{'returned_rows':len(tab_rows),
                        'reported_total_rows':len(tab_rows)+8 if truncated else len(tab_rows),
                        'truncated':truncated}}})
            atomic_jsonl(reference,recs)
            draft=root/'review.jsonl'; report=root/'review.json'; csvout=root/'review.csv'
            summary=reference_review_draft(dataset,reference,draft,report,csv_output=csvout)
            yield tasks, dataset, draft, report, csvout, summary

    def test_shapes_and_ambiguous_values(self):
        tasks,_=run_fixture(count=5)[0]
        sample=copy.deepcopy(tasks[0]);sample['answer_spec']['expected_columns']=['ra','dec']
        record={'disposition':'accepted_nonempty','response':{'result':{'data':[{'ra':1.2,'dec':-3.1}]}}}
        self.assertEqual(review_detail(sample,record)['answer_shape'],'coordinate_pair')
        record['response']['result']['data'].append({'ra':1.3,'dec':-3.2})
        self.assertEqual(review_detail(sample,record)['answer_shape'],'coordinate_pair_list')
        sample['answer_spec']['expected_columns']=['parallax']
        record['response']['result']['data']=[{'parallax':None},{'parallax':5.0}]
        info=review_detail(sample,record)
        self.assertEqual(info['answer_shape'],'single_value')
        self.assertEqual(info['null_value_count'],1)
        self.assertIn('null_measurements',info['review_flags'])

    def test_review_cli_preserves_editable_jsonl(self):
        from contextlib import redirect_stdout
        from io import StringIO
        from benchmark.cli import main
        tasks,_=run_fixture(count=5)[0]
        rows=[]
        for task in tasks:
            fields=task['answer_spec']['expected_columns'] or ['ra']
            rows.append([{name:'observed' for name in fields}])
        for _tasks,dataset,draft,report,csvout,summary in self._references(tasks,rows):
            reference_path=draft.with_name('refs.jsonl')
            with redirect_stdout(StringIO()):
                code=main(['reference-review-draft','--tasks',str(dataset),
                    '--references',str(reference_path),'--output',str(draft),
                    '--csv-output',str(csvout),'--report',str(report),'--replace'])
            self.assertEqual(code,0)
            records,_=load_jsonl(draft)
            self.assertEqual(len(records),5)
            self.assertTrue(all(r['gold_status']=='pending' for r in records))
            self.assertEqual(json.loads(report.read_text())['questions'],5)

    def test_gold_draft_compatible_and_fail_closed(self):
        tasks,_=run_fixture(count=5)[0]
        rows=[]
        for task in tasks:
            names=task.get('answer_spec',{}).get('expected_columns',[]) or ['ra']
            rows.append([{name:'source_obs_1' for name in names}])
        for _tasks, dataset, draft, report, csvout, summary in self._references(tasks,rows):
            self.assertEqual(summary['questions'],5)
            self.assertEqual(summary['gold_verified'],0)
            lines,_=load_jsonl(draft)
            self.assertTrue(all(r['gold_status']=='pending' and r['gold'] is None for r in lines))
            with self.assertRaisesRegex(ValidationError,'Only 0/5 gold'):
                gold_finalize(dataset,draft,report.with_name('gold.jsonl'),report.with_name('gold_report.json'))
            result=gold_finalize(dataset,draft,report.with_name('gold.jsonl'),report.with_name('gold_report.json'),allow_partial=True)
            self.assertEqual(result['verified_gold_answers'],0)
            self.assertFalse(result['scientific_accuracy_ready'])
            # Wrong fingerprint fails without publishing any artifact.
            bad=copy.deepcopy(lines);bad[0]['input_dataset_sha256']='x'*64
            atomic_jsonl(report.with_name('bad_review.jsonl'),bad)
            with self.assertRaises(ValidationError):
                gold_finalize(dataset,report.with_name('bad_review.jsonl'),report.with_name('badgold.jsonl'),report.with_name('badreport.json'),allow_partial=True)
            self.assertFalse(report.with_name('badgold.jsonl').exists())

    def test_science_review_blocks_truncated_set(self):
        tasks,_=run_fixture(count=5)[0]
        rows=[]
        for task in tasks:
            names=task['answer_spec']['expected_columns'] or ['ra']
            rows.append([{name:'sample' for name in names}])
        for tasks,dataset,draft,report,csvout,summary in self._references(tasks,rows,truncated=True):
            draft_data,_=load_jsonl(draft)
            row=draft_data[0]
            row.update(question_review='approved',gold_status='verified',reviewer='human',
                       gold={'kind':'set','values':['sample']},
                       sources=[{'uri':'https://archive.example/a','description':'archive'},
                                {'uri':'https://independent.example/b','description':'independent'}])
            rewritten=report.with_name('edited.jsonl');atomic_jsonl(rewritten,draft_data)
            with self.assertRaisesRegex(ValidationError, 'Truncated reference'):
                gold_finalize(dataset,rewritten,report.with_name('out.jsonl'),
                              report.with_name('out_report.json'),allow_partial=True)

    def test_finalize_approved_coordinate_pair(self):
        import hashlib
        with TemporaryDirectory() as root:
            root=Path(root)
            task=copy.deepcopy(run_fixture(count=5)[0][0][0])
            task['answer_spec']['expected_columns']=['ra','dec']
            taskfile=root/'source.jsonl'
            atomic_jsonl(taskfile,[task])
            sha=hashlib.sha256(taskfile.read_bytes()).hexdigest()
            rec={'task_id':task['id'],'module':task['module'],
                 'input_dataset_sha256':sha,'disposition':'accepted_nonempty',
                 'response':{'result':{'data':[{'ra':359.99,'dec':-20.0}],
                                       'row_count':1}},
                 'evaluation':{'checks':{'returned_rows':1,'reported_total_rows':1,
                                         'truncated':False}}}
            refs=root/'refs.jsonl';atomic_jsonl(refs,[rec])
            review=root/'review.jsonl'
            reference_review_draft(taskfile,refs,review,root/'review_report.json')
            rows,_=load_jsonl(review)
            self.assertEqual(rows[0]['answer_shape'],'coordinate_pair')
            rows[0].update(question_review='approved',gold_status='verified',
                gold={'kind':'coordinate_pair','values':[359.99,-20],
                      'unit':'deg','frame':'icrs','absolute_tolerance':.01},
                sources=[{'uri':'https://one.example/obj','description':'source1'},
                         {'uri':'https://two.example/obj','description':'source2'}],
                reviewer='scientist')
            edited=root/'edited.jsonl';atomic_jsonl(edited,rows)
            finalized=gold_finalize(taskfile,edited,root/'frozen.jsonl',
                                    root/'frozen_report.json')
            self.assertEqual(finalized['verified_gold_answers'],1)
            self.assertTrue(finalized['scientific_accuracy_ready'])

    def test_coordinate_gold_comparison(self):
        gold={'kind':'coordinate_pair','values':[359.999,-10.0],'unit':'deg','frame':'icrs',
              'absolute_tolerance':0.01}
        self.assertEqual(_score_one(gold,{'answer_values':[0.001,-10.001],'unit':'deg','abstained':False}),('CORRECT',1.0))
        self.assertEqual(_score_one(gold,{'answer_values':[100,50],'unit':'deg','abstained':False}),('INCORRECT',0.0))
        self.assertEqual(_score_one(gold,{'answer_values':[0.001,-10],'unit':'rad','abstained':False}),('INCORRECT',0.0))


if __name__=='__main__':
    unittest.main()
