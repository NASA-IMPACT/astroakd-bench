"""Gold-blind, three-arm AstroAKD agent experiment and gold-only offline scoring."""
from __future__ import annotations
import asyncio
from collections import Counter
from pathlib import Path
import hashlib
import json
import os
import time
from typing import Any, Callable
from . import __version__, DEFAULT_MCP_URL
from .agent_runner import OpenAIAgent, TracedMCPGateway, AgentRunError
from .client import AstroqueryMCPClient
from .validator import load_jsonl, atomic_json, atomic_jsonl, append_journal, now_utc, json_bytes, ValidationError
from .gold import _read_tasks, _path_safety, MILESTONE

ARMS = ('mcp_only','mcp_instruction','web_only')
MINIMAL = ("You are an astronomy research assistant. Use only the provided tools and the user's question. "
           "Use archive results as evidence, cite source identifiers, never fabricate an observation or bibliographic ID. "
           "Do not invent missing parameters. State uncertainty and say when the available evidence is insufficient. "
           "Return the final answer as JSON with keys answer (string), answer_values (array of exact strings or numbers), "
           "unit (string or null), sources (array of URLs/identifiers), abstained (boolean). "
           "Do not include numerical or bibliographic values absent from results.")
WEB = ("You are an astronomy research assistant. Use ONLY OpenAI's hosted web_search tool; "
       "no Astroquery MCP tools are available. Cite source URLs and do not fabricate observation identifiers. "
       "Return a JSON object with answer, answer_values (array), unit, sources (array), abstained. "
       "Search is necessary; do not rely on recalled facts alone.")


def _parse_answer(text: str) -> dict[str,Any]:
    text=text.strip()
    if text.startswith('```json') and text.endswith('```'):
        text=text[7:-3].strip()
    try:
        obj=json.loads(text)
    except (json.JSONDecodeError,TypeError):
        return {'answer':text,'answer_values':None,'unit':None,'sources':[],'abstained':False,'parse_status':'unstructured'}
    if not isinstance(obj,dict) or not isinstance(obj.get('answer'),str) or not isinstance(obj.get('answer_values'),list):
        return {'answer':text,'answer_values':None,'unit':None,'sources':[],'abstained':False,'parse_status':'unstructured'}
    return {'answer':obj['answer'], 'answer_values':obj['answer_values'], 'unit':obj.get('unit'),
            'sources':obj.get('sources') if isinstance(obj.get('sources'),list) else [],
            'abstained':obj.get('abstained') is True,'parse_status':'structured'}


async def _web_answer(question: str, *, model: str, sdk: Any):
    response = await sdk.responses.create(model=model, tools=[{'type':'web_search'}],
        tool_choice='required',include=['web_search_call.action.sources'],
        input=[{'role':'system','content':WEB},{'role':'user','content':question}])
    uses=sum(getattr(x,'type',None)=='web_search_call' for x in getattr(response,'output',[]) or [])
    if uses<1:
        raise AgentRunError('Web-only arm produced no actual web_search call')
    from .literature import _observed_urls, _message_citation_urls
    urls=sorted(_observed_urls(response)|_message_citation_urls(response))
    value=_parse_answer(getattr(response,'output_text','') or '')
    value['sources']=sorted({str(x) for x in value['sources'] if isinstance(x,str)}|set(urls))
    usage=getattr(response,'usage',None)
    counts={k:int(getattr(usage,k,0) or 0) for k in ('input_tokens','output_tokens','total_tokens')}
    return value, counts, [{'tool':'openai_web_search','status':'ok','source_urls':urls,'web_search_calls':uses}]


async def run_three_arm(tasks_path:Path, instruction_file:Path, output:Path, report:Path, *,
                        url:str=DEFAULT_MCP_URL, model:str='gpt-4.1-mini', limit:int|None=None,
                        max_turns:int=8,max_calls:int=12,max_tool_bytes:int=65536,timeout:float=180,
                        task_timeout:float=600,resume:bool=False,replace:bool=False,
                        mcp_factory:Callable|None=None,sdk:Any=None,
                        progress:Callable[[str],None]|None=None):
    """Blind execution: no gold or reference-answer path is accepted by the runner."""
    if resume and replace: raise AgentRunError('--resume and --replace are mutually exclusive')
    if limit is not None and limit<1: raise AgentRunError('--limit must be >=1')
    if not 1<=max_turns<=32 or not 1<=max_calls<=100 or not 1024<=max_tool_bytes<=1024*1024 or timeout<=0 or task_timeout<=0:
        raise AgentRunError('Invalid tool/time budget')
    _path_safety([tasks_path,instruction_file],[output,report],replace or resume)
    tasks,dataset_hash=_read_tasks(tasks_path)
    instructions=instruction_file.read_text(encoding='utf-8')
    if not 200<=len(instructions)<=30000: raise AgentRunError('AstroAKD agent instruction must be 200..30000 characters')
    instr_hash=hashlib.sha256(instructions.encode()).hexdigest()
    context={'tasks_sha256':dataset_hash,'agent_instruction_sha256':instr_hash,'model':model,
             'mcp_url':url,'max_turns':max_turns,'max_calls':max_calls,'max_tool_bytes':max_tool_bytes,
             'task_timeout':task_timeout,'mcp_timeout':timeout,'arms':ARMS}
    journal=output.with_name(output.name+'.progress.jsonl')
    manifest=output.with_name(output.name+'.manifest.json')
    if resume:
        if not manifest.exists() or output.exists(): raise AgentRunError('No resumable journal or output already final')
        if json.loads(manifest.read_text())!=context: raise AgentRunError('Resume context differs; refuse data mixing')
        prior,_=load_jsonl(journal,max_bytes=512*1024*1024)
        completed={}
        taskids={t['id'] for t in tasks}
        for r in prior:
            key=(r.get('task_id'),r.get('arm'))
            if key[0] not in taskids or key[1] not in ARMS or key in completed or r.get('candidate_sha256')!=dataset_hash:
                raise AgentRunError('Corrupted or mismatched three-arm journal')
            completed[key]=r
    else:
        if any(p.exists() for p in (output,report,journal,manifest)) and not replace:
            raise AgentRunError('Output already exists; --resume or --replace required')
        if replace:
            for p in (output,report,journal,manifest): p.unlink(missing_ok=True)
        atomic_json(manifest,context)
        completed={}
    todo=[(t,arm) for t in tasks for arm in ARMS if (t['id'],arm) not in completed]
    if limit is not None:
        selected={t['id'] for t,a in todo[:limit*len(ARMS)]}
        todo=[(t,a) for t,a in todo if t['id'] in selected]
    if todo and sdk is None:
        if not os.getenv('OPENAI_API_KEY'): raise AgentRunError('OPENAI_API_KEY missing for three-arm experiment')
        from openai import AsyncOpenAI
        sdk=AsyncOpenAI(timeout=min(task_timeout,120),max_retries=0)
    for t,arm in todo:
        ident=t['id']
        if progress: progress(f'START {ident} {arm}')
        started=time.monotonic()
        answer={'answer':'','answer_values':None,'unit':None,'sources':[], 'abstained':True,'parse_status':'unstructured'}
        trace=[]; usage={}; status='error'; error=None
        try:
            if arm=='web_only':
                async with asyncio.timeout(task_timeout):
                    answer,usage,trace=await _web_answer(t['question'],model=model,sdk=sdk)
            else:
                async with asyncio.timeout(task_timeout):
                    client=mcp_factory(url) if mcp_factory else AstroqueryMCPClient(url,timeout=timeout)
                    async with client as conn:
                        advertised=await conn.list_tools()
                        gate=TracedMCPGateway(conn,max_calls=max_calls,max_tool_bytes=max_tool_bytes,
                             available=advertised,question=t['question'],extended_tools=True)
                        prompt=MINIMAL if arm=='mcp_only' else (MINIMAL+'\n\n'+instructions)
                        agent=OpenAIAgent(model=model,sdk_client=sdk,system_prompt=prompt)
                        result=await agent.run(t['question'],gate,max_turns)
                        answer=_parse_answer(result['answer'])
                        usage=result.get('token_usage',{})
                        trace=gate.events
            status='completed'
        except Exception as exc:
            error={'type':type(exc).__name__,'message':str(exc)[:500]}
        record={'task_id':ident,'task_type':t.get('task_type'),'arm':arm,'model':model,
                'status':status,'answer':answer,'trace':trace,'token_usage':usage,
                'duration_seconds':round(time.monotonic()-started,4),'error':error,
                'successful_mcp_queries':sum(1 for e in trace if e.get('tool') in ('astroquery_execute','ads_query_compact','ads_get_paper','simbad_query_bibobj') and e.get('status')=='ok' and (e.get('response_success') is True if e.get('tool')=='astroquery_execute' else True)),
                'candidate_sha256':dataset_hash,'agent_instruction_sha256':instr_hash if arm=='mcp_instruction' else None,
                'timestamp_utc':now_utc()}
        append_journal(journal,record)
        completed[(ident,arm)]=record
        if progress: progress(f'DONE {ident} {arm}: {status}')
    ordered=[completed[(t['id'],arm)] for t in tasks for arm in ARMS if (t['id'],arm) in completed]
    complete=len(ordered)==len(tasks)*len(ARMS)
    if complete: atomic_jsonl(output,ordered,replace=replace)
    report_data={'milestone':MILESTONE,'benchmark_version':__version__,
                 'status':'COMPLETE' if complete else 'PARTIAL',
                 'tasks':len(tasks),'arm_runs_completed':len(ordered),'expected_arm_runs':len(tasks)*3,
                 'by_arm':{a:dict(Counter(r['status'] for r in ordered if r['arm']==a)) for a in ARMS},
                 'tasks_sha256':dataset_hash,'instruction_sha256':instr_hash,
                 'gold_answers_seen_by_runner':False,'model':model,
                 'note':'No gold data supplied to agent. Different MCP/web capabilities are intentional experimental conditions.',
                 'journal':str(journal),'output':str(output) if complete else None}
    atomic_json(report,report_data,replace=True,style='pretty')
    return report_data


def _normalize(v:Any) -> str:
    return ' '.join(str(v).casefold().split())


def _score_one(gold:dict,answer:dict):
    if answer.get('abstained'):
        return 'ABSTAIN',0.0
    vals=answer.get('answer_values')
    if not isinstance(vals,list): return 'REVIEW_UNSTRUCTURED',None
    ref=gold['values']; kind=gold['kind']
    if kind=='numeric':
        if len(vals)!=1 or _normalize(answer.get('unit'))!=_normalize(gold['unit']):
            return 'INCORRECT',0.0
        try:
            import math
            observed=float(vals[0]); expected=float(ref[0]); tolerance=float(gold.get('absolute_tolerance',0))
            good=math.isfinite(observed) and abs(observed-expected)<=tolerance
        except (ValueError,TypeError,OverflowError): good=False
        return ('CORRECT',1.0) if good else ('INCORRECT',0.0)
    true={_normalize(x) for x in ref}; pred={_normalize(x) for x in vals}
    if len(pred)!=len(vals): return 'REVIEW_DUPLICATE_VALUES',None
    if kind=='text':
        return ('CORRECT',1.0) if true==pred else ('INCORRECT',0.0)
    precision=len(true&pred)/len(pred) if pred else 0
    recall=len(true&pred)/len(true) if true else 0
    f1=2*precision*recall/(precision+recall) if precision+recall else 0
    return ('CORRECT' if f1==1 else 'PARTIAL' if f1 else 'INCORRECT',round(f1,5))


def score_three_arm(tasks_path:Path,gold_path:Path,runs_path:Path,output:Path,report:Path,*,replace:bool=False):
    _path_safety([tasks_path,gold_path,runs_path],[output,report],replace)
    tasks,sha=_read_tasks(tasks_path)
    gold, goldhash=load_jsonl(gold_path,max_bytes=12*1024*1024)
    runs,runhash=load_jsonl(runs_path,max_bytes=512*1024*1024)
    if [g.get('task_id') for g in gold]!=[t['id'] for t in tasks] or any(g.get('input_dataset_sha256')!=sha for g in gold):
        raise ValidationError('Gold does not match candidate ID/order/hash')
    ids={t['id'] for t in tasks}
    observed={}; scores=[]
    for r in runs:
        key=(r.get('task_id'),r.get('arm'))
        if key in observed or key[0] not in ids or key[1] not in ARMS or r.get('candidate_sha256')!=sha:
            raise ValidationError('Run ID/arm/dataset invalid or duplicate')
        trace=r.get('trace',[])
        if not isinstance(trace,list): raise ValidationError('Malformed arm trace')
        if key[1]=='web_only' and any(e.get('tool')!='openai_web_search' for e in trace):
            raise ValidationError('Web-only arm illegally contains MCP tool usage')
        if key[1]!='web_only' and any(e.get('tool')=='openai_web_search' for e in trace):
            raise ValidationError('MCP arm illegally contains web_search tool usage')
        observed[key]=r
    for g in gold:
        tid=g['task_id']
        for arm in ARMS:
            r=observed.get((tid,arm))
            if g.get('gold_status')!='verified':
                status='UNSCORABLE_NO_GOLD'; fraction=None
            elif r is None:
                status='NOT_RUN'; fraction=None
            elif r.get('status')!='completed':
                status='RUN_ERROR'; fraction=None
            else:
                status,fraction=_score_one(g['gold'],r.get('answer') or {})
            scores.append({'task_id':tid,'task_type':g.get('task_type'),'arm':arm,
                           'score_status':status,'scientific_fraction':fraction,
                           'gold_approved':g.get('gold_status')=='verified',
                           'duration_seconds':r.get('duration_seconds') if r else None,
                           'token_usage':r.get('token_usage') if r else None,
                           'mcp_tool_calls':sum(x.get('tool')!='openai_web_search' for x in r.get('trace',[])) if r else None,
                           'web_search_calls':sum(x.get('web_search_calls',0) for x in r.get('trace',[])) if r else None})
    atomic_jsonl(output,scores,replace=replace)
    arm_reports={}
    for arm in ARMS:
        s=[v for v in scores if v['arm']==arm]; graded=[v for v in s if v['scientific_fraction'] is not None]
        arm_reports[arm]={'gold_eligible':sum(v['gold_approved'] for v in s),
                          'scored':len(graded),'mean_scientific_fraction':round(sum(v['scientific_fraction'] for v in graded)/len(graded),5) if graded else None,
                          'statuses':dict(Counter(v['score_status'] for v in s))}
    paired=[g['task_id'] for g in gold if all(
       next((v['scientific_fraction'] for v in scores if v['task_id']==g['task_id'] and v['arm']==arm),None) is not None
       for arm in ARMS)]
    for arm in ARMS:
        values=[v['scientific_fraction'] for v in scores if v['arm']==arm and v['task_id'] in paired]
        arm_reports[arm]['paired_mean_scientific_fraction']=(round(sum(values)/len(values),5) if values else None)
    result={'milestone':MILESTONE,'benchmark_version':__version__,
            'status':'REVIEW' if any(v['score_status'].startswith('UNSCORABLE') for v in scores) else 'COMPLETE',
            'dataset_sha256':sha,'gold_sha256':goldhash,'runs_sha256':runhash,
            'total_tasks':len(tasks),'verified_gold':sum(g.get('gold_status')=='verified' for g in gold),
            'paired_scored_tasks':len(paired),
            'arms':arm_reports,'interpretation': 'Strict structured exact/set/numeric scoring only. Unstructured replies require review; reference evidence is not gold; comparison of scores requires matched graded questions.',
            'output':str(output)}
    atomic_json(report,result,replace=replace,style='pretty')
    return result
