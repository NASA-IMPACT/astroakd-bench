"""Version 0.2.0: deterministic, signature-aware candidate generation.

Discovery uses only list_modules, list_functions, and get_function_info.
The generator NEVER calls astroquery_execute or any archive data service.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import random
import tempfile
from typing import Any, Callable

from . import __version__, DEFAULT_MCP_URL
from .client import AstroqueryMCPClient
from .seeds import (TARGETS, RADII_ARCMIN, HEASARC_CATALOGS,
                    VIZIER_CATALOGS, SEED_CATALOG_VERSION, SkyTarget)


SUPPORTED_MODULES = ("simbad", "mast", "heasarc", "gaia", "vizier")
# A strict whitelist of read-only operations. No dynamically discovered method
# can extend this list, even if it begins with query_/get_/list_.
SAFE_METHODS: dict[str, tuple[str, ...]] = {
    "simbad": ("query_object",),
    "mast": ("query_region",),
    "heasarc": ("query_region",),
    "gaia": ("query_object", "query_object_async"),
    "vizier": ("query_region",),
}

# Each template requires the named semantic arguments. Alternative parameter
# spellings are admitted only if the MCP introspection advertises them.
ALIASES: dict[str, dict[str, tuple[str, ...]]] = {
    "simbad": {"object": ("object_name",)},
    "mast": {"coordinate": ("coordinates",), "radius": ("radius",)},
    "heasarc": {"coordinate": ("position",), "radius": ("radius",), "catalog": ("catalog",)},
    "gaia": {"coordinate": ("coordinate",), "radius": ("radius",)},
    "vizier": {"coordinate": ("coordinates",), "radius": ("radius",), "catalog": ("catalog",)},
}


class GenerationError(ValueError):
    """Refused to create unsafe, invalid, or non-reproducible candidates."""


def _canonical_json(data: Any) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def _sha256(data: Any) -> str:
    return hashlib.sha256(_canonical_json(data).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class BoundMethod:
    module: str
    method: str
    semantic_parameters: dict[str, str]
    advertised_parameters: tuple[dict[str, Any], ...]
    signature_source: str = "introspection"


def parse_modules(value: str | list[str] | tuple[str, ...]) -> tuple[str, ...]:
    if isinstance(value, str):
        raw = value.split(",")
    else:
        raw = list(value)
    requested = [part.strip().lower() for part in raw]
    if not requested or any(not item for item in requested):
        raise GenerationError("--modules requires a nonempty comma-separated list")
    if len(set(requested)) != len(requested):
        raise GenerationError("Duplicate module names are not permitted")
    unknown = sorted(set(requested) - set(SUPPORTED_MODULES))
    if unknown:
        raise GenerationError("Unsupported/unsafe module(s): " + ", ".join(unknown))
    # Canonical ordering makes --modules argument ordering irrelevant.
    return tuple(name for name in SUPPORTED_MODULES if name in requested)


def _function_names(payload: dict[str, Any], module: str) -> set[str]:
    functions = payload.get("functions", [])
    names: set[str] = set()
    for entry in functions:
        if not isinstance(entry, dict):
            continue
        method = entry.get("method")
        if not isinstance(method, str):
            continue
        # Never accept a method erroneously advertised under another module.
        if entry.get("module", module) == module:
            names.add(method)
    return names


def bind_signature(module: str, method: str, info: dict[str, Any]) -> BoundMethod:
    """Reject unapproved methods, unsupported args, and unknown required args.

    Signature checking is structural. It does not establish live archive
    compatibility; that is an explicit 0.3.0 task.
    """
    if method not in SAFE_METHODS.get(module, ()):
        raise GenerationError(f"Disallowed operation: {module}.{method}")
    if info.get("module", module) != module or info.get("method", method) != method:
        raise GenerationError(f"Mismatched introspection response for {module}.{method}")
    entries = info.get("parameters")
    if not isinstance(entries, list) or not entries:
        raise GenerationError(f"Missing parameter signature for {module}.{method}")
    # The synchronous query_region methods of VizieR and MAST are documented
    # class/instance wrappers, which can introspect as (*args, **kwargs).
    # The proxy signature is not a valid API schema. In these two explicitly
    # documented cases use the conservative public keyword contract and label
    # the provenance. Unknown modules/methods NEVER get this bypass.
    if module in ("vizier", "mast") and method == "query_region" and \
            {p.get("name") for p in entries} == {"args", "kwargs"}:
        names = ("coordinates", "radius", "catalog") if module == "vizier" else ("coordinates", "radius")
        mapped = {key: {"name": key, "required": key == "coordinates", "type": "Any"}
                  for key in names}
        semantic = {"coordinate": "coordinates", "radius": "radius"}
        if module == "vizier":
            semantic["catalog"] = "catalog"
        return BoundMethod(module, method, semantic,
                           tuple(mapped.values()), f"documented_{module}_wrapper")

    mapped: dict[str, dict[str, Any]] = {}
    for entry in entries:
        if not isinstance(entry, dict) or not isinstance(entry.get("name"), str):
            raise GenerationError(f"Malformed signature for {module}.{method}")
        name = entry["name"]
        if name in mapped:
            raise GenerationError(f"Duplicate signature argument {name} for {module}.{method}")
        mapped[name] = entry

    bound: dict[str, str] = {}
    for semantic, aliases in ALIASES[module].items():
        found = next((alias for alias in aliases if alias in mapped), None)
        if found is None:
            raise GenerationError(f"{module}.{method} missing required template argument {semantic}: {aliases}")
        bound[semantic] = found
    selected = set(bound.values())
    unsupported_required = [name for name, spec in mapped.items()
                            if spec.get("required") is True and name not in selected]
    if unsupported_required:
        raise GenerationError(f"{module}.{method} has unsupported required argument(s): "
                              + ", ".join(sorted(unsupported_required)))
    # Unknown 'required' value is rejected rather than assumed optional.
    unspecified = [name for name, spec in mapped.items()
                   if name not in selected and not isinstance(spec.get("required"), bool)]
    if unspecified:
        raise GenerationError(f"{module}.{method} cannot establish optionality of: "
                              + ", ".join(sorted(unspecified)))
    return BoundMethod(module, method, bound, tuple(mapped.values()))


async def discover_bindings(client: AstroqueryMCPClient,
                            modules: tuple[str, ...]) -> dict[str, BoundMethod]:
    advertised = await client.list_modules()
    available = {entry.get("name"): entry.get("available")
                 for entry in advertised["modules"] if isinstance(entry, dict)}
    bindings: dict[str, BoundMethod] = {}
    for module in modules:
        if available.get(module) is not True:
            raise GenerationError(f"Required server module '{module}' is not available")
        functions = await client.list_functions(module)
        methods = _function_names(functions, module)
        candidates = [method for method in SAFE_METHODS[module] if method in methods]
        if not candidates:
            raise GenerationError(f"No approved read-only query function advertised by '{module}' "
                                  f"(expected one of {SAFE_METHODS[module]})")
        problems = []
        for method in candidates:
            info = await client.function_info(module, method)
            try:
                bindings[module] = bind_signature(module, method, info)
                break
            except GenerationError as exc:
                problems.append(str(exc))
        if module not in bindings:
            raise GenerationError("; ".join(problems))
    return bindings


def _description(module: str, target: SkyTarget, radius: int, catalog: str | None) -> str:
    if module == "simbad":
        return f"Using SIMBAD, retrieve the basic object information for {target.name}."
    center = f"ICRS RA {target.ra_deg:.4f} deg, Dec {target.dec_deg:+.4f} deg"
    if module == "mast":
        return f"Search MAST observations within {radius} arcmin of {center} (near {target.name})."
    if module == "heasarc":
        return (f"Search the HEASARC {catalog} catalog within {radius} arcmin of "
                f"{center} (near {target.name}).")
    if module == "gaia":
        return f"Query Gaia sources within {radius} arcmin of {center} (near {target.name})."
    if module == "vizier":
        return (f"Query VizieR catalog {catalog} within {radius} arcmin of "
                f"{center} (near {target.name}).")
    raise GenerationError(f"Unknown module: {module}")


def _candidate(module: str, bound: BoundMethod, target: SkyTarget,
               radius: int, catalog: str | None) -> dict[str, Any]:
    semantic = bound.semantic_parameters
    if module == "simbad":
        params: dict[str, Any] = {semantic["object"]: target.name}
        constraints = {"object_name": target.name}
        kind = "object_lookup"
    else:
        params = {
            semantic["coordinate"]: {"ra": target.ra_deg, "dec": target.dec_deg,
                                      "frame": "icrs"},
            semantic["radius"]: {"value": radius, "unit": "arcmin"},
        }
        constraints = {"near_object": target.name, "center_icrs": {
            "ra_deg": target.ra_deg, "dec_deg": target.dec_deg},
            "radius": {"value": radius, "unit": "arcmin"}}
        kind = "region_search"
        if catalog is not None:
            params[semantic["catalog"]] = catalog
            constraints["catalog"] = catalog
    return {
        "question": _description(module, target, radius, catalog),
        "category": kind,
        "module": module,
        "target": target.name,
        "constraints": constraints,
        "reference_call": {
            "tool": "astroquery_execute",
            "arguments": {"module_name": module, "function_name": bound.method,
                          "params": params},
        },
    }


def _module_candidates(module: str, bound: BoundMethod, rng: random.Random) -> list[dict[str, Any]]:
    candidates = []
    targets = list(TARGETS)
    rng.shuffle(targets)
    # Rotate the radius order for each center, providing distinct constraints.
    radii = list((1, 2, 3) if module in ("gaia", "vizier") else RADII_ARCMIN)
    rng.shuffle(radii)
    for i, target in enumerate(targets):
        if module == "simbad":
            candidates.append(_candidate(module, bound, target, radii[0], None))
            continue
        per_target_radii = radii[i % len(radii):] + radii[:i % len(radii)]
        for j, radius in enumerate(per_target_radii):
            catalog = None
            if module == "heasarc":
                catalog = HEASARC_CATALOGS[(i + j) % len(HEASARC_CATALOGS)]
            elif module == "vizier":
                catalog = VIZIER_CATALOGS[(i + j) % len(VIZIER_CATALOGS)]
            candidates.append(_candidate(module, bound, target, radius, catalog))
    return candidates


def generate_candidates(bindings: dict[str, BoundMethod], *,
                        count: int, seed: int, modules: tuple[str, ...]) -> list[dict[str, Any]]:
    if isinstance(count, bool) or count < 1 or count > 500:
        raise GenerationError("--count must be between 1 and 500")
    if not modules:
        raise GenerationError("At least one module is required")
    rng = random.Random(seed)
    queues = {mod: _module_candidates(mod, bindings[mod], rng) for mod in modules}
    selected: list[dict[str, Any]] = []
    # Round robin across modules, guaranteeing near-equal coverage.
    for i in range(count):
        mod = modules[i % len(modules)]
        if not queues[mod]:
            raise GenerationError(f"Not enough unique seed combinations for {mod}; "
                                  "reduce --count or restrict --modules")
        selected.append(queues[mod].pop(0))
    # Fingerprint the *observed* method contracts, not local assumptions.
    # Hash the behavioral signature only. Avoid unstable repr(default) values
    # or long docstrings from introspection changing between identical runs.
    snapshot = {module: {"method": bindings[module].method,
                         "parameters": sorted(({
                             "name": p["name"], "type": str(p.get("type", "Any")),
                             "required": p.get("required"),
                         } for p in bindings[module].advertised_parameters),
                             key=lambda p: p["name"]),
                         "signature_source": bindings[module].signature_source}
                for module in modules}
    schema_sha256 = _sha256(snapshot)
    for i, candidate in enumerate(selected, start=1):
        candidate["id"] = f"ASTROAKD-020-{i:05d}"
        candidate["benchmark_version"] = __version__
        candidate["validation_status"] = "candidate_unvalidated"
        candidate["provenance"] = {
            "random_seed": seed,
            "seed_catalog_version": SEED_CATALOG_VERSION,
            "discovered_schema_sha256": schema_sha256,
            "generation_index": i,
            "signature_source": bindings[candidate["module"]].signature_source,
        }
    return selected


def write_jsonl(path: Path, candidates: list[dict[str, Any]], *, replace: bool = False) -> str:
    """Atomic UTF-8 JSONL publication; refuse overwrite absent --replace."""
    if path.exists() and not replace:
        raise GenerationError(f"Output exists: {path}; pass --replace to overwrite")
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = ("\n".join(_canonical_json(task) for task in candidates) + "\n").encode("utf-8")
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="wb", dir=path.parent, prefix=".astroakd-",
                                         suffix=".tmp", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(payload)
        if path.exists() and not replace:
            raise GenerationError(f"Output exists: {path}; pass --replace to overwrite")
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return hashlib.sha256(payload).hexdigest()


async def generate(url: str = DEFAULT_MCP_URL, *, count: int = 50, seed: int = 42,
                   modules: tuple[str, ...] = SUPPORTED_MODULES, timeout: float = 180,
                   session_factory: Callable[[str], Any] | None = None,
                   ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    modules = parse_modules(modules)
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise GenerationError("--seed must be an integer")
    if count < 1 or count > 500:
        raise GenerationError("--count must be between 1 and 500")
    async with AstroqueryMCPClient(url, timeout=timeout, session_factory=session_factory) as client:
        names = {tool["name"] for tool in await client.list_tools()}
        required = {"astroquery_list_modules", "astroquery_list_functions",
                    "astroquery_get_function_info"}
        missing = required - names
        if missing:
            raise GenerationError("Missing MCP discovery tool(s): " + ", ".join(sorted(missing)))
        bindings = await discover_bindings(client, modules)
    candidates = generate_candidates(bindings, count=count, seed=seed, modules=modules)
    summary = {
        "milestone": "0.2.0 — SYNTHETIC_QUERY_GENERATION",
        "benchmark_version": __version__,
        "endpoint": url,
        "seed": seed,
        "count": len(candidates),
        "modules": list(modules),
        "by_module": dict(sorted(Counter(t["module"] for t in candidates).items())),
        "discovered_methods": {mod: bindings[mod].method for mod in modules},
        "signature_sources": {mod: bindings[mod].signature_source for mod in modules},
        "discovered_schema_sha256": candidates[0]["provenance"]["discovered_schema_sha256"],
        "validation_status": "candidate_unvalidated",
        "archive_queries_executed": 0,
        "status": "PASS",
    }
    return candidates, summary
