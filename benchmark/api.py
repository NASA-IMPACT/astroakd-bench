"""Supported Python API for AstroAKD-Bench workflows (v0.6.1).

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
from .generator import generate, parse_modules, write_jsonl
from .seeds import SkyTarget
from .validator import validate, load_jsonl, EXPECTED_ACCEPTED_020_SHA256, atomic_json
from .agent_runner import run_agents
from .evaluator import evaluate
from .replay import build_reference_fixtures, FixtureStore, ReplayClient


class AstroAKDBench:
    """Reusable local benchmark workflows and defaults rooted in *root*.

    Methods never overwrite generated artifacts unless ``replace=True``.
    ``generate_queries`` only uses MCP discovery, not archive queries or an LLM.
    ``evaluate_agent`` and ``build_fixtures`` require no external service.
    """

    def __init__(self, root: str | Path = '.', *, mcp_url: str = DEFAULT_MCP_URL,
                 timeout: float = 180.0):
        self.root = Path(root).expanduser().resolve()
        self.mcp_url = mcp_url
        if timeout <= 0:
            raise ValueError('timeout must be positive')
        self.timeout = timeout

    def path(self, relative: str | Path) -> Path:
        """Resolve default artifact paths under the chosen benchmark root."""
        value = Path(relative).expanduser()
        return value if value.is_absolute() else self.root / value

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
                               backend: str = "openai", model: str = "gpt-4.1-mini",
                               use_instructions: bool = True, use_mcp: bool = True,
                               instructions_file: str | Path | None = None,
                               batch_size: int = 5,
                               openai_client_factory: Callable | None = None,
                               progress: Callable[[str], None] | None = None,
                               ) -> dict[str, Any]:
        """Discover read-only signatures and save reproducible candidate JSONL."""
        destination = self.path(output) if output is not None else self.tasks_path
        report_path = self.path(report) if report is not None else None
        if report_path is not None and report_path.resolve() == destination.resolve():
            raise ValueError('Dataset and report destinations must differ')
        from .exports import check_destinations, save_views
        csv_path = self.path(csv_output) if csv_output is not None else None
        pretty_path = self.path(pretty_output) if pretty_output is not None else None
        check_destinations(None, destination, report_path,
                           pretty_path, csv_path, replace=replace)
        if destination.exists() and not replace:
            raise ValueError(f'Dataset already exists: {destination}; use replace=True')
        if report_path is not None and report_path.exists() and not replace:
            raise ValueError(f'Report already exists: {report_path}; use replace=True')
        if backend == 'template':
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
        summary['dataset_sha256'] = write_jsonl(destination, candidates, replace=replace)
        summary['output'] = str(destination)
        save_views(candidates, pretty=pretty_path, csv_path=csv_path,
                   kind='candidate', replace=replace)
        if csv_path is not None:
            summary['csv_output'] = str(csv_path)
        if pretty_path is not None:
            summary['pretty_output'] = str(pretty_path)
        if report_path is not None:
            atomic_json(report_path, summary, replace=replace)
        return summary

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

    async def run_agent(self, *, agent: str = 'openai', model: str = 'gpt-4.1-mini',
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
