"""Regression: JSON round-trip of resume manifest must preserve semantic equality."""
import asyncio
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from benchmark.agent_runner import AgentRunError
from benchmark.three_arm import ARMS, run_three_arm
from benchmark.validator import atomic_jsonl, load_jsonl
from benchmark.tests.test_gold_three_arm_066 import FakeSDK, FakeMCP


class TestThreeArmResume0672(unittest.TestCase):
    def test_partial_resume_roundtrips_manifest_without_duplicate_runs(self):
        async def go():
            with TemporaryDirectory() as name:
                base=Path(name)
                tasks=base/'tasks.jsonl'
                atomic_jsonl(tasks,[
                    {'id':'T1','task_type':'archive_driven','question':'What identifier does SIMBAD return for M31?',
                     'module':'simbad','target':'M31','answer_spec':{'expected_columns':['main_id']}},
                    {'id':'T2','task_type':'archive_driven','question':'What is SIMBAD primary identifier for M31?',
                     'module':'simbad','target':'M31','answer_spec':{'expected_columns':['main_id']}},
                ])
                instr=base/'AstroAKD_Instruction.md'
                instr.write_text('# AstroAKD agent instruction\n'+'Resolve object names from SIMBAD. '*18)
                output=base/'runs.jsonl';report=base/'report.json'
                sdk=FakeSDK()
                kwargs=dict(model='gpt-5.2',max_turns=8,max_calls=12,
                            max_tool_bytes=262144,timeout=180,task_timeout=900,
                            sdk=sdk,mcp_factory=FakeMCP)
                partial=await run_three_arm(tasks,instr,output,report,limit=1,**kwargs)
                self.assertEqual(partial['status'],'PARTIAL')
                self.assertEqual(partial['arm_runs_completed'],3)
                manifest=json.loads((base/'runs.jsonl.manifest.json').read_text())
                self.assertEqual(manifest['arms'],list(ARMS))
                self.assertFalse(output.exists())
                with self.assertRaisesRegex(AgentRunError,'Resume context differs'):
                    await run_three_arm(tasks,instr,output,report,resume=True,
                                       model='gpt-5.2-other',max_turns=8,max_calls=12,
                                       max_tool_bytes=262144,timeout=180,task_timeout=900,
                                       sdk=sdk,mcp_factory=FakeMCP)
                completed=await run_three_arm(tasks,instr,output,report,resume=True,**kwargs)
                self.assertEqual(completed['status'],'COMPLETE')
                self.assertEqual(completed['arm_runs_completed'],6)
                records=load_jsonl(output)[0]
                self.assertEqual(len(records),6)
                self.assertEqual(len({(r['task_id'],r['arm']) for r in records}),6)
                self.assertEqual(len(load_jsonl(base/'runs.jsonl.progress.jsonl')[0]),6)
                self.assertTrue(all(r['status']=='completed' for r in records))
        asyncio.run(go())
