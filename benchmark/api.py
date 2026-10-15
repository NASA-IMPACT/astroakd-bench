"""Supported Python API for AstroAKD-Bench workflows (v0.6.7.11).

AstroAKD-Bench is an independent project. The NASA IMPACT Astroquery MCP
server is a separate service accessed through its HTTP MCP endpoint.

The facade delegates to the same guarded implementation used by the CLI:
there is no separate generator, validator, execution engine or score logic.
All output paths are under the caller-selected project root by default.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from . import DEFAULT_MCP_URL
from .mcp_config import resolve_mcp_url
from .generator import generate, parse_modules, write_jsonl
from .seeds import SkyTarget
from .validator import validate, load_jsonl, EXPECTED_ACCEPTED_020_SHA256, atomic_json
from .agent_runner import run_agents
from .evaluator import evaluate
from .replay import build_reference_fixtures, FixtureStore, ReplayClient


class AstroAKDBench:
    """Reusable local benchmark workflows and defaults rooted in *root*.

    Methods never overwrite generated artifacts unless ``replace=True``.
    ``generate_queries`` supports OpenAI, template, and native Gold mixed generation.
    ``evaluate_agent`` and ``build_fixtures`` require no external service.
    """

    def __init__(self, root: str | Path = '.', *, mcp_url: str | None = None,
                 timeout: float = 180.0):
        self.root = Path(root).expanduser().resolve()
        self.mcp_url = resolve_mcp_url(mcp_url)
        if timeout <= 0:
            raise ValueError('timeout must be positive')
        self.timeout = timeout

    def path(self, relative: str | Path) -> Path:
        """Resolve default artifact paths under the chosen benchmark root."""
        value = Path(relative).expanduser()
        return value if value.is_absolute() else self.root / value

    def export_answer_csv(self, *, tasks: str | Path, questions_csv: str | Path,
                          arms_csv: str | Path, summary_csv: str | Path,
                          report: str | Path, runs: str | Path | None = None,
                          references: str | Path | None = None,
                          reference_tasks: str | Path | None = None,
                          gold: str | Path | None = None,
                          reference_values_csv: str | Path | None = None,
                          per_arm_dir: str | Path | None = None,
                          replace: bool = False) -> dict[str, Any]:
        """Generate inspection CSVs; execution success is never claimed as science truth."""
        from .answer_reports import export_answer_csv
        def resolve(p): return self.path(p) if p is not None else None
        return export_answer_csv(resolve(tasks),resolve(questions_csv),resolve(arms_csv),
             resolve(summary_csv),resolve(report),runs=resolve(runs),references=resolve(references),
             reference_tasks=resolve(reference_tasks),gold=resolve(gold),
             reference_values_csv=resolve(reference_values_csv),per_arm_dir=resolve(per_arm_dir),replace=replace)

    # One-line named dataset APIs introduced in 0.6.7.11. Complex workflows
    # remain available through the detailed methods below.
    async def create_synthetic_queries(self, *, name=None, count=100,
                                       output_dir=None,
                                       seed=20261018, mix='balanced100',
                                       model='gpt-5.2', require_ads=False,
                                       replace=False, **kwargs):
        from .simple_workflows import create_queries
        return await create_queries(name=name, root=self.root, output_dir=output_dir, count=count,seed=seed,
            mix=mix,model=model,require_ads=require_ads,replace=replace,
            url=self.mcp_url,timeout=self.timeout,**kwargs)

    async def collect_named_references(self, *, name='synthetic_100', output_dir=None,
                                       resume=False,limit=None,**kwargs):
        from .simple_workflows import collect_references
        return await collect_references(name=name,root=self.root,output_dir=output_dir,url=self.mcp_url,
            resume=resume,limit=limit,**kwargs)

    def create_reference_report(self, *, name='synthetic_100', output_dir=None, plots=True,
                                replace=False):
        from .simple_workflows import reference_report
        return reference_report(name=name,root=self.root,output_dir=output_dir,plots=plots,replace=replace)

    def create_agent_report(self, *, name='synthetic_100', output_dir=None, plots=True,
                            replace=False):
        from .simple_workflows import dataset_paths
        from .operational_report import create_operational_report
        paths=dataset_paths(self.root,name,output_dir=output_dir)
        return create_operational_report(paths['tasks'],paths['runs'],paths['plots']/'agents',
            plots=plots,replace=replace)

    @property
    def tasks_path(self) -> Path:
        return self.path('datasets/generated/synthetic_queries.jsonl')

    @property
    def references_path(self) -> Path:
        return self.path('datasets/validated/reference_answers.jsonl')

    async def generate_queries(self, *, count: int = 50, seed: int = 42,
                               modules: str | tuple[str, ...] = ('simbad','mast','heasarc','gaia','vizier'),
                               output: str | Path | None = None, report: str | Path | None = None,
                               replace: bool = False, session_factory: Callable | None = None,
                               csv_output: str | Path | None = None,
                               pretty_output: str | Path | None = None,
                               targets: tuple[SkyTarget, ...] | None = None,
                               uniqueness: str = "archive-target",
                               question_style: str = "answer-oriented",
                               backend: str = "openai", model: str = "gpt-5.2",
                               use_instructions: bool = True, use_mcp: bool = True,
                               instructions_file: str | Path | None = None,
                               batch_size: int = 5,
                               task_mix: str | None = None,
                               single_call_output: str | Path | None = None,
                               literature_output: str | Path | None = None,
                               openai_client_factory: Callable | None = None,
                               progress: Callable[[str], None] | None = None,
                               with_reference_answers: bool = False,
                               reference_output: str | Path | None = None,
                               reference_report: str | Path | None = None,
                               reference_csv: str | Path | None = None,
                               reference_pretty: str | Path | None = None,
                               reference_limit: int | None = None,
                               reference_attempts: int = 2,
                               reference_delay: float = 2.0,
                               ) -> dict[str, Any]:
        """Save candidates; optionally execute real, resumable MCP references.

        Observed values are unreviewed archive evidence, never model-written gold.
        """
        destination = self.path(output) if output is not None else self.tasks_path
        report_path = self.path(report) if report is not None else None
        if report_path is not None and report_path.resolve() == destination.resolve():
            raise ValueError('Dataset and report destinations must differ')
        from .exports import check_destinations, save_views
        csv_path = self.path(csv_output) if csv_output is not None else None
        pretty_path = self.path(pretty_output) if pretty_output is not None else None
        if with_reference_answers:
            if not use_mcp or task_mix is not None:
                raise ValueError('Reference collection requires ordinary MCP single-call tasks')
            from .reference_generation import reference_paths, check_reference_paths
            ref_destinations = reference_paths(destination,
                self.path(reference_output) if reference_output is not None else None,
                self.path(reference_report) if reference_report is not None else None,
                self.path(reference_csv) if reference_csv is not None else None,
                self.path(reference_pretty) if reference_pretty is not None else None)
            check_reference_paths(destination, report_path, pretty_path, csv_path,
                                  ref_destinations, replace=replace)
        elif any(value is not None for value in (reference_output,reference_report,
                                                  reference_csv,reference_pretty,reference_limit)):
            raise ValueError('Reference destinations/limit require with_reference_answers=True')
        from .mixed_generation import parse_task_mix
        mix = parse_task_mix(task_mix, count=count)
        ordinary_path = self.path(single_call_output) if single_call_output is not None else None
        literature_path = self.path(literature_output) if literature_output is not None else None
        split_paths = tuple(p for p in (ordinary_path,literature_path) if p is not None)
        if split_paths and mix is None:
            raise ValueError('Split outputs require task_mix')
        check_destinations(None, destination, report_path,
                           pretty_path, csv_path, replace=replace, extras=split_paths)
        for p in split_paths:
            if p.exists() and not replace:
                raise ValueError(f'Split output exists: {p}')
        if destination.exists() and not replace:
            raise ValueError(f'Dataset already exists: {destination}; use replace=True')
        if report_path is not None and report_path.exists() and not replace:
            raise ValueError(f'Report already exists: {report_path}; use replace=True')
        if mix is not None:
            from .mixed_generation import generate_mixed
            candidates, summary = await generate_mixed(self.mcp_url, count=count, seed=seed,
                modules=parse_modules(modules), mix=mix, timeout=self.timeout,
                uniqueness=uniqueness, backend=backend, model=model,
                use_instructions=use_instructions, use_mcp=use_mcp,
                instructions_file=self.path(instructions_file) if instructions_file is not None else None,
                batch_size=batch_size, session_factory=session_factory,
                progress=progress, openai_client_factory=openai_client_factory)
        elif backend == 'template':
            if instructions_file is not None:
                raise ValueError('Template backend does not use custom instructions')
            if not use_mcp:
                raise ValueError('Template backend requires MCP; use openai/hybrid with use_mcp=False')
            candidates, summary = await generate(self.mcp_url, count=count, seed=seed,
                                                 modules=parse_modules(modules),
                                                 timeout=self.timeout, session_factory=session_factory,
                                                 targets=targets, uniqueness=uniqueness,
                                                 question_style=question_style)
            summary.update({'generation_backend': 'template', 'use_instructions': False,
                            'use_mcp': True, 'openai_requests': 0, 'web_search_calls': 0})
        else:
            from .llm_generation import generate_llm
            candidates, summary = await generate_llm(self.mcp_url, count=count, seed=seed,
                modules=parse_modules(modules), timeout=self.timeout,
                session_factory=session_factory, targets=targets,
                uniqueness=uniqueness, question_style=question_style,
                backend=backend, model=model, use_instructions=use_instructions,
                use_mcp=use_mcp,
                instructions_file=self.path(instructions_file) if instructions_file is not None else None,
                batch_size=batch_size, openai_client_factory=openai_client_factory,
                progress=progress)
        if mix is not None:
            if ordinary_path is not None:
                summary['single_call_sha256'] = write_jsonl(ordinary_path,
                    [t for t in candidates if t['task_type'] != 'literature_driven'], replace=replace)
                summary['single_call_output'] = str(ordinary_path)
            if literature_path is not None:
                summary['literature_sha256'] = write_jsonl(literature_path,
                    [t for t in candidates if t['task_type'] == 'literature_driven'], replace=replace)
                summary['literature_output'] = str(literature_path)
        summary['dataset_sha256'] = write_jsonl(destination, candidates, replace=replace)
        summary['output'] = str(destination)
        save_views(candidates, pretty=pretty_path, csv_path=csv_path,
                   kind='candidate', replace=replace)
        if csv_path is not None:
            summary['csv_output'] = str(csv_path)
        if pretty_path is not None:
            summary['pretty_output'] = str(pretty_path)
        if with_reference_answers:
            refs, rreport, rcsv, rpretty = ref_destinations
            result = await validate(destination, refs, rreport, url=self.mcp_url,
                timeout=self.timeout, attempts=reference_attempts, delay=reference_delay,
                limit=reference_limit, csv_output=rcsv, pretty_output=rpretty,
                replace=replace, session_factory=session_factory, progress=progress)
            summary['reference_collection'] = {
                'status': result['status'], 'quality_gate': result['quality_gate'],
                'reference_output': result.get('output', ''),
                'reference_journal': result['journal'],
                'reference_report': str(rreport), 'reference_csv': str(rcsv),
                'processed': result['processed'], 'remaining': result['remaining'],
                'accepted_reference_count': result['accepted_reference_count'],
                'dispositions': result['dispositions'],
                'answer_key_status': 'reference_anchored_unreviewed',
            }
            summary['status'] = ('PARTIAL' if result['status']=='PARTIAL' else
                'REVIEW' if result['quality_gate']!='PASS' else 'PASS')
        if report_path is not None:
            atomic_json(report_path, summary, replace=replace)
        return summary

    async def research_literature(self, query: str, *, max_results: int = 5,
                                  model: str = 'gpt-5.2', use_mcp: bool = True,
                                  session_factory: Callable | None = None,
                                  openai_client_factory: Callable | None = None) -> dict[str, Any]:
        """MCP ADS search with automatic OpenAI web-search fallback; not gold validation."""
        from .literature import research_literature
        return await research_literature(query, url=self.mcp_url, timeout=self.timeout,
                  max_results=max_results, model=model, use_mcp=use_mcp,
                  session_factory=session_factory, openai_client_factory=openai_client_factory)

    async def validate_queries(self, *, input: str | Path | None = None,
                               output: str | Path = 'datasets/validated/reference_answers.jsonl',
                               report: str | Path = 'datasets/validated/validation_report.json',
                               strict_accepted_020: bool = False, attempts: int = 2,
                               delay: float = 2.0, limit: int | None = None,
                               resume: bool = False, replace: bool = False,
                               max_rows: int = 20, json_format: str = 'compact',
                               session_factory: Callable | None = None,
                               pretty_output: str | Path | None = None,
                               csv_output: str | Path | None = None,
                               progress: Callable[[str], None] | None = None) -> dict[str, Any]:
        """Query real archives through MCP and journal every reference disposition."""
        return await validate(self.path(input) if input is not None else self.tasks_path,
                              self.path(output), self.path(report), url=self.mcp_url,
                              timeout=self.timeout, attempts=attempts, delay=delay,
                              limit=limit, resume=resume, replace=replace, max_rows=max_rows,
                              strict_sha256=(EXPECTED_ACCEPTED_020_SHA256
                                             if strict_accepted_020 else None),
                              json_format=json_format, session_factory=session_factory,
                              pretty_output=self.path(pretty_output) if pretty_output is not None else None,
                              csv_output=self.path(csv_output) if csv_output is not None else None,
                              progress=progress)

    async def run_agent(self, *, agent: str = 'openai', model: str = 'gpt-5.2',
                        adapter: str | None = None, mcp_mode: str = 'live',
                        fixtures: str | Path | None = None,
                        tasks: str | Path | None = None, references: str | Path | None = None,
                        output: str | Path = 'datasets/agent/agent_runs.jsonl',
                        report: str | Path = 'datasets/agent/run_report.json',
                        limit: int | None = None, max_turns: int = 8,
                        max_calls: int = 12, max_tool_bytes: int = 65536,
                        task_timeout: float = 600.0, strict_accepted_020: bool = False,
                        resume: bool = False, replace: bool = False,
                        json_format: str = 'compact',
                        agent_factory: Callable | None = None,
                        session_factory: Callable | None = None) -> dict[str, Any]:
        """Run an LLM, a user-supplied adapter or an echo harness with audited tools.

        In replay mode the MCP layer is fully offline. OpenAI agents still need
        their own model API; external local agents need not use one.
        """
        return await run_agents(self.path(tasks) if tasks is not None else self.tasks_path,
                                self.path(references) if references is not None else self.references_path,
                                self.path(output), self.path(report), url=self.mcp_url,
                                timeout=self.timeout, agent_name=agent, model=model,
                                adapter=adapter, mcp_mode=mcp_mode,
                                fixtures=self.path(fixtures) if fixtures is not None else None,
                                limit=limit, max_turns=max_turns, max_calls=max_calls,
                                max_tool_bytes=max_tool_bytes, task_timeout=task_timeout,
                                strict_accepted_020=strict_accepted_020,
                                resume=resume, replace=replace, json_format=json_format,
                                agent_factory=agent_factory, session_factory=session_factory)

    def evaluate_agent(self, *, runs: str | Path,
                       tasks: str | Path | None = None, references: str | Path | None = None,
                       output: str | Path = 'datasets/evaluation/task_scores.jsonl',
                       report: str | Path = 'datasets/evaluation/evaluation_report.json',
                       csv: str | Path | None = 'datasets/evaluation/task_scores.csv',
                       pretty_output: str | Path | None = None,
                       strict_accepted_020: bool = False, replace: bool = False,
                       json_format: str = 'compact') -> dict[str, Any]:
        """Score saved traces offline; never call an archive or a model."""
        return evaluate(self.path(tasks) if tasks is not None else self.tasks_path,
                        self.path(references) if references is not None else self.references_path,
                        self.path(runs), self.path(output), self.path(report),
                        csv_path=self.path(csv) if csv is not None else None,
                        pretty_output=self.path(pretty_output) if pretty_output is not None else None,
                        strict_accepted_020=strict_accepted_020, replace=replace,
                        json_format=json_format)

    def gold_draft(self, *, tasks: str | Path, output: str | Path,
                   report: str | Path, references: str | Path | None = None,
                   reference_tasks: str | Path | None = None,
                   replace: bool = False) -> dict[str, Any]:
        """Produce an unapproved human-review gold sheet; no invented answers."""
        from .gold import gold_draft
        return gold_draft(self.path(tasks),self.path(output),self.path(report),
             references=self.path(references) if references is not None else None,
             reference_tasks=self.path(reference_tasks) if reference_tasks is not None else None,
             replace=replace)

    def gold_finalize(self, *, tasks: str | Path, reviewed: str | Path,
                      output: str | Path, report: str | Path,
                      allow_partial: bool = False, replace: bool = False) -> dict[str, Any]:
        """Freeze human-reviewed scientific answers with cited evidence."""
        from .gold import gold_finalize
        return gold_finalize(self.path(tasks),self.path(reviewed),self.path(output),
                             self.path(report),allow_partial=allow_partial,replace=replace)

    async def run_three_arm(self, *, tasks: str | Path, agent_instruction: str | Path,
                            output: str | Path, report: str | Path,
                            model: str = 'gpt-5.2', limit: int | None = None,
                            max_turns: int = 8,max_calls: int = 12,
                            max_tool_bytes: int = 65536,task_timeout: float = 600,
                            resume: bool = False,replace: bool = False,
                            mcp_factory: Callable | None = None,sdk: Any = None,
                            progress: Callable[[str], None] | None = None) -> dict[str, Any]:
        """Run matched AstroAKD A/B/C with no gold or reference access."""
        from .three_arm import run_three_arm
        return await run_three_arm(self.path(tasks),self.path(agent_instruction),
            self.path(output),self.path(report),url=self.mcp_url,model=model,limit=limit,
            max_turns=max_turns,max_calls=max_calls,max_tool_bytes=max_tool_bytes,
            task_timeout=task_timeout,timeout=self.timeout,resume=resume,replace=replace,
            mcp_factory=mcp_factory,sdk=sdk,progress=progress)

    def score_three_arm(self, *, tasks: str | Path,gold: str | Path,runs: str | Path,
                         output: str | Path,report: str | Path,
                         replace: bool = False) -> dict[str, Any]:
        """Strict scientific scores only on reviewed and frozen gold answers."""
        from .three_arm import score_three_arm
        return score_three_arm(self.path(tasks),self.path(gold),self.path(runs),
                               self.path(output),self.path(report),replace=replace)

    def build_scorable(self, *, source_tasks: str | Path, references: str | Path,
                       tasks_output: str | Path, oracle_output: str | Path,
                       answers_csv: str | Path, report: str | Path,
                       count: int = 50, replace: bool = False) -> dict[str, Any]:
        """Construct fixed-field snapshot-reference tasks; does not certify scientific truth."""
        from .scorable import build_scorable
        return build_scorable(self.path(source_tasks),self.path(references),
                              self.path(tasks_output),self.path(oracle_output),
                              self.path(answers_csv),self.path(report),count=count,replace=replace)

    def score_scorable(self, *, tasks: str | Path, oracle: str | Path, runs: str | Path,
                       comparison_csv: str | Path, summary_csv: str | Path,
                       report: str | Path, detail_csv: str | Path | None = None,
                       performance_csv: str | Path | None = None,
                       task_performance_csv: str | Path | None = None,
                       plots_dir: str | Path | None = None,
                       mcp_calls_csv: str | Path | None = None,
                       mcp_tool_frequency_csv: str | Path | None = None,
                       overall_csv: str | Path | None = None,
                       mcp_ab_summary_csv: str | Path | None = None,
                       paired_questions_csv: str | Path | None = None,
                       paired_summary_csv: str | Path | None = None,
                       mismatch_audit_csv: str | Path | None = None,
                       paired_plots_dir: str | Path | None = None,
                       replace: bool = False) -> dict[str, Any]:
        """Export A/B/C full answers with frozen snapshot-reference exact match percentages."""
        from .scorable import score_scorable
        return score_scorable(self.path(tasks),self.path(oracle),self.path(runs),
                              self.path(comparison_csv),self.path(summary_csv),
                              self.path(report),
                              detail_csv=self.path(detail_csv) if detail_csv else None,
                              performance_csv=self.path(performance_csv) if performance_csv else None,
                              task_performance_csv=self.path(task_performance_csv) if task_performance_csv else None,
                              plots_dir=self.path(plots_dir) if plots_dir else None,
                              mcp_calls_csv=self.path(mcp_calls_csv) if mcp_calls_csv else None,
                              mcp_tool_frequency_csv=self.path(mcp_tool_frequency_csv) if mcp_tool_frequency_csv else None,
                              overall_csv=self.path(overall_csv) if overall_csv else None,
                              mcp_ab_summary_csv=self.path(mcp_ab_summary_csv) if mcp_ab_summary_csv else None,
                              paired_questions_csv=self.path(paired_questions_csv) if paired_questions_csv else None,
                              paired_summary_csv=self.path(paired_summary_csv) if paired_summary_csv else None,
                              mismatch_audit_csv=self.path(mismatch_audit_csv) if mismatch_audit_csv else None,
                              paired_plots_dir=self.path(paired_plots_dir) if paired_plots_dir else None,
                              replace=replace)

    def audit_diversity(self, *, tasks: str | Path | None = None,
                        references: str | Path | None = None) -> dict[str, Any]:
        """Audit repeated questions, archive-target combinations and returned tables offline."""
        from .diversity import audit
        cases = self.load_records(tasks if tasks is not None else self.tasks_path)
        refs = self.load_records(references) if references is not None else None
        return audit(cases, refs)

    def build_fixtures(self, *, tasks: str | Path | None = None,
                       references: str | Path | None = None,
                       output: str | Path = 'datasets/replay/reference_fixtures.json',
                       strict_accepted_020: bool = False,
                       replace: bool = False) -> dict[str, Any]:
        """Build verified MCP reference fixtures offline from prior references."""
        return build_reference_fixtures(
            self.path(tasks) if tasks is not None else self.tasks_path,
            self.path(references) if references is not None else self.references_path,
            self.path(output), strict_accepted_020=strict_accepted_020,
            replace=replace)

    def load_fixtures(self, path: str | Path = 'datasets/replay/reference_fixtures.json') -> FixtureStore:
        """Verify fixture contents, call keys and published SHA-256 integrity."""
        return FixtureStore.load(self.path(path))

    def load_records(self, path: str | Path) -> list[dict[str, Any]]:
        """Read compact JSONL dataset/trace/score records without modifying them."""
        return load_jsonl(self.path(path), max_bytes=512 * 1024 * 1024)[0]


__all__ = ['AstroAKDBench', 'SkyTarget', 'FixtureStore', 'ReplayClient']
