"""Offline MCP fixture construction, capture and deterministic replay (v0.6.0).

Only read-only, explicitly allowlisted Astroquery tool calls are stored. A
replay miss never contacts a network server and never invents a response.
Fixtures capture tool responses, not LLM answers; the agent remains independent.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from . import __version__
from .errors import MCPTransportError
from .validator import (ValidationError, atomic_json, json_bytes, load_jsonl,
                        SUCCESS_DISPOSITIONS, EXPECTED_ACCEPTED_020_SHA256)
from .agent_runner import load_run_inputs, redact, validate_tool_args, ALLOWED_TOOLS

FIXTURE_FORMAT = 'astroakd-bench-mcp-fixtures-v1'
MAX_FIXTURE_BYTES = 512 * 1024 * 1024
MAX_SINGLE_RESPONSE = 8 * 1024 * 1024


class ReplayError(ValidationError):
    """Invalid, mismatched, unsafe or missing offline fixture."""


def key_for(tool: str, arguments: dict[str, Any]) -> str:
    if tool not in ALLOWED_TOOLS:
        raise ReplayError(f'Unapproved MCP fixture operation: {tool}')
    validate_tool_args(tool, arguments)
    return hashlib.sha256(json_bytes({'tool':tool,'arguments':arguments})).hexdigest()


def static_catalog() -> list[dict[str, Any]]:
    """Minimal, explicit tool schemas used only to bootstrap from frozen references.

    The schema is not claimed to be identical to current server introspection.
    For server-faithful discovery, use --mcp-mode record against the real server.
    """
    def arg(name: str, text: str, properties: dict, required: list[str]) -> dict:
        return {'name':name, 'description':text,
                'input_schema':{'type':'object','properties':properties,'required':required}}
    st={'type':'string'}
    return [
        arg('astroquery_list_modules','List available Astroquery modules (read only)',{},[]),
        arg('astroquery_list_functions','List module functions',{'module_name':st},['module_name']),
        arg('astroquery_get_function_info','Describe an Astroquery method',
            {'module_name':st,'function_name':st},['module_name','function_name']),
        arg('astroquery_execute','Execute allowlisted read-only Astroquery queries. '
            'Use module-specific params; max_rows only for MAST.',
            {'module_name':st,'function_name':st,
             'params':{'type':'object','additionalProperties':True},
             'max_rows':{'type':'integer','minimum':1,'maximum':100}},
            ['module_name','function_name','params']),
    ]


class FixtureStore:
    def __init__(self, catalog: list[dict[str, Any]], entries: list[dict[str, Any]] | None = None,
                 *, source: str = 'recorded', dataset_sha256: str | None = None):
        if not isinstance(catalog,list) or not all(isinstance(x,dict) and x.get('name') in ALLOWED_TOOLS
                                                    and isinstance(x.get('input_schema'),dict) for x in catalog):
            raise ReplayError('Fixture catalog has invalid or unapproved tools')
        if len({x['name'] for x in catalog}) != len(catalog):
            raise ReplayError('Duplicate MCP catalog tool')
        self.catalog = catalog
        self.source = source
        self.dataset_sha256 = dataset_sha256
        self.entries: dict[str,dict[str,Any]] = {}
        for item in (entries or []):
            self.add_entry(item, validate=True)

    @property
    def fingerprint(self) -> str:
        return hashlib.sha256(json_bytes(self.body())).hexdigest()

    def body(self) -> dict[str,Any]:
        return {'format':FIXTURE_FORMAT,'source':self.source,'dataset_sha256':self.dataset_sha256,
                'catalog':self.catalog, 'entries':[self.entries[k] for k in sorted(self.entries)]}

    def publish(self,path:Path, *, replace:bool=False) -> str:
        content=self.body()
        content['integrity_sha256']=self.fingerprint
        atomic_json(path,content,replace=replace)
        return self.fingerprint

    @classmethod
    def load(cls,path:Path) -> 'FixtureStore':
        if not path.is_file() or path.stat().st_size > MAX_FIXTURE_BYTES:
            raise ReplayError(f'Fixture missing or exceeds {MAX_FIXTURE_BYTES} bytes: {path}')
        try:
            payload=json.loads(path.read_text(encoding='utf-8'))
        except (ValueError,UnicodeError) as exc:
            raise ReplayError('Fixture is not valid JSON') from exc
        if not isinstance(payload,dict) or payload.get('format')!=FIXTURE_FORMAT:
            raise ReplayError('Unsupported fixture format')
        entries=payload.get('entries')
        if not isinstance(entries,list):
            raise ReplayError('Fixture entries must be a list')
        store=cls(payload.get('catalog'),entries,source=payload.get('source'),
                  dataset_sha256=payload.get('dataset_sha256'))
        if store.fingerprint!=payload.get('integrity_sha256'):
            raise ReplayError('Fixture integrity SHA-256 mismatch; possible alteration')
        if len(store.entries)!=len(entries):
            raise ReplayError('Duplicate fixture calls are not allowed')
        return store

    def add_entry(self,item:dict[str,Any],*,validate:bool=True) -> None:
        if not isinstance(item,dict) or set(item)!={'key','tool','arguments','outcome','payload_sha256','payload'}:
            raise ReplayError('Malformed fixture entry')
        tool,args=item['tool'],item['arguments']
        key=key_for(tool,args)
        if item['key']!=key:
            raise ReplayError('Fixture call key does not match arguments')
        if item['outcome'] not in ('ok','error') or not isinstance(item['payload'],(dict,list,str,int,float,bool,type(None))):
            raise ReplayError('Invalid fixture outcome/payload')
        if hashlib.sha256(json_bytes(item['payload'])).hexdigest()!=item['payload_sha256']:
            raise ReplayError('Fixture response SHA-256 mismatch')
        if len(json_bytes(item['payload']))>MAX_SINGLE_RESPONSE:
            raise ReplayError('Fixture response exceeds per-call size limit')
        previous=self.entries.get(key)
        if previous is not None and previous!=item:
            raise ReplayError('Conflicting fixture responses for same call')
        self.entries[key]=item

    def record(self, tool:str, arguments:dict, payload:Any, *,outcome:str='ok') -> bool:
        clean=redact(payload)
        if len(json_bytes(clean))>MAX_SINGLE_RESPONSE:
            raise ReplayError('Tool response too large for record/replay fixture')
        key=key_for(tool,arguments)
        entry={'key':key,'tool':tool,'arguments':redact(arguments),
               'outcome':outcome,'payload_sha256':hashlib.sha256(json_bytes(clean)).hexdigest(),
               'payload':clean}
        if key in self.entries:
            # Preserve original response to keep one deterministic value per call.
            return False
        self.add_entry(entry)
        return True

    def lookup(self,tool:str,arguments:dict)->Any:
        key=key_for(tool,arguments)
        entry=self.entries.get(key)
        if entry is None:
            raise ReplayError(f'OFFLINE_REPLAY_MISS: no recorded fixture for {tool} '
                              f'and argument fingerprint {key[:16]}; no network fallback')
        if entry['outcome']=='error':
            detail=entry['payload']
            raise MCPTransportError('Recorded MCP failure: '+str(detail.get('message','error'))[:400])
        return json.loads(json.dumps(entry['payload'],ensure_ascii=False))


def build_reference_fixtures(tasks_path:Path, refs_path:Path, output:Path, *,
                             strict_accepted_020:bool=False,replace:bool=False)->dict[str,Any]:
    if output.resolve() in {tasks_path.resolve(),refs_path.resolve()}:
        raise ReplayError('Fixture destination must differ from input files')
    if output.exists() and not replace:
        raise ReplayError('Fixture already exists; use --replace')
    tasks, dataset_hash, refs_hash=load_run_inputs(tasks_path,refs_path,strict_sha=strict_accepted_020)
    refs,_=load_jsonl(refs_path,max_bytes=512*1024*1024)
    store=FixtureStore(static_catalog(),source='accepted_reference_0.3.0',dataset_sha256=dataset_hash)
    for record in refs:
        if record.get('disposition') not in SUCCESS_DISPOSITIONS:
            raise ReplayError('Unaccepted reference')
        call=record['reference_call']
        if not isinstance(record.get('response'),dict) or record['response'].get('success') is not True:
            raise ReplayError('Reference lacks successful serialized MCP response')
        store.record(call['tool'],call['arguments'],record['response'])
    digest=store.publish(output,replace=replace)
    return {'milestone':'0.6.0 — REPLAY_AND_BENCHMARK_RELEASE','benchmark_version':__version__,
            'mode':'build-fixtures','status':'PASS','network_calls':0,
            'candidate_dataset_sha256':dataset_hash,'reference_answers_sha256':refs_hash,
            'fixture_fingerprint':digest,'records':len(store.entries),
            'tools':len(store.catalog),'output':str(output),
            'note':'Frozen archive responses are structural references, not independently verified gold. '
                   'Only exact recorded calls can be replayed; no network fallback.'}


class ReplayClient:
    """Drop-in MCP client without sockets, DNS, imports or live archive calls."""
    def __init__(self,store:FixtureStore):
        self.store=store
    async def __aenter__(self):
        return self
    async def __aexit__(self,*args):
        return None
    async def list_tools(self):
        return json.loads(json.dumps(self.store.catalog))
    async def call(self,name,arguments=None):
        return self.store.lookup(name,arguments or {})


class RecordClient:
    """Transparent live-client wrapper that publishes fsynced fixtures per call."""
    def __init__(self, live, path:Path, *,resume:bool=False,replace:bool=False,
                 dataset_hash:str|None=None):
        self.live=live;self.path=path;self.resume=resume;self.replace=replace
        self.dataset_hash=dataset_hash;self.store=None
    async def __aenter__(self):
        await self.live.__aenter__()
        try:
            catalog=[x for x in await self.live.list_tools() if x['name'] in ALLOWED_TOOLS]
            if self.resume:
                self.store=FixtureStore.load(self.path)
                if self.store.dataset_sha256 != self.dataset_hash or self.store.catalog != catalog:
                    raise ReplayError('Recording resume fixture context/schema mismatch')
            else:
                self.store=FixtureStore(catalog,source='live_mcp_recording',
                                        dataset_sha256=self.dataset_hash)
                self.store.publish(self.path,replace=self.replace)
        except BaseException:
            await self.live.__aexit__(None,None,None)
            raise
        return self
    async def __aexit__(self,*args):
        return await self.live.__aexit__(*args)
    async def list_tools(self):
        return json.loads(json.dumps(self.store.catalog))
    async def call(self,name,arguments=None):
        arguments=arguments or {}
        try:
            response=await self.live.call(name,arguments)
        except Exception as exc:
            self.store.record(name,arguments,{'type':type(exc).__name__,
                                             'message':str(exc)[:400]},outcome='error')
            self.store.publish(self.path,replace=True)
            raise
        else:
            if self.store.record(name,arguments,response):
                self.store.publish(self.path,replace=True)
            return response
