"""Safe output path planning for opt-in generation followed by live MCP references."""
from __future__ import annotations
from pathlib import Path
from .validator import ValidationError


def reference_paths(dataset: Path, output: Path | None, report: Path | None,
                    csv: Path | None, pretty: Path | None):
    base = dataset.stem
    if dataset.parent.name == 'generated':
        folder = dataset.parent.parent / 'validated'
    else:
        folder = dataset.parent / 'validated'
    return (output or folder / f'{base}_references.jsonl',
            report or folder / f'{base}_references_report.json',
            csv or folder / f'{base}_references.csv',
            pretty)


def check_reference_paths(dataset: Path, gen_report: Path | None,
                          gen_pretty: Path | None, gen_csv: Path | None,
                          selected: tuple, *, replace: bool):
    from .exports import check_destinations
    refs, report, csv, pretty = selected
    journal = refs.with_name(refs.name + '.progress.jsonl')
    manifest = refs.with_name(refs.name + '.manifest.json')
    existing = [dataset, gen_report, gen_pretty, gen_csv, refs, report, csv,
                pretty, journal, manifest]
    paths = [p for p in existing if p is not None]
    if len(set(p.resolve() for p in paths)) != len(paths):
        raise ValidationError('Generation/reference destination collision; use distinct paths')
    check_destinations(dataset, refs, report, pretty, csv, replace=replace,
                       extras=(journal, manifest))
    if not replace:
        for p in (refs, report, csv, pretty, journal, manifest):
            if p is not None and p.exists():
                raise ValidationError(f'Reference output already exists: {p}; use distinct filenames or --replace')
