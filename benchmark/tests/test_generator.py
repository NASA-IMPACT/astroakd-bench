"""Offline tests for 0.2.0. No network calls, archive execution, or live server."""

import asyncio
from collections import Counter
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest

from benchmark.generator import (
    GenerationError, SAFE_METHODS, SUPPORTED_MODULES, bind_signature,
    generate, generate_candidates, parse_modules, write_jsonl,
)


PARAMETERS = {
    "simbad": {"query_object": ("object_name",)},
    "mast": {"query_region": ("coordinates", "radius")},
    "heasarc": {"query_region": ("position", "radius", "catalog")},
    "gaia": {"query_object": ("coordinate", "radius")},
    "vizier": {"query_region": ("coordinates", "radius", "catalog")},
}


def param(name, required=True):
    return {"name": name, "type": "Any", "required": required}


class FixtureSession:
    def __init__(self, url, *, change=None):
        self.url = url
        self.change = change or {}
        self.calls = []
        self.closed = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        self.closed = True

    async def ping(self):
        return True

    async def list_tools(self):
        return [SimpleNamespace(name=name, description="fixture", inputSchema={})
                for name in ("astroquery_list_modules", "astroquery_list_functions",
                             "astroquery_get_function_info", "astroquery_execute")]

    async def call_tool(self, name, args, *, timeout=None):
        self.calls.append((name, args))
        if name == "astroquery_execute":
            raise AssertionError("0.2.0 must never call astroquery_execute")
        module = args.get("module_name")
        if name == "astroquery_list_modules":
            data = {"module_count": len(SUPPORTED_MODULES), "modules": [
                {"name": item, "available": self.change.get("unavailable") != item}
                for item in SUPPORTED_MODULES]}
        elif name == "astroquery_list_functions":
            funcs = [{"name": f"{module}_{method}", "module": module,
                      "method": method} for method in PARAMETERS.get(module, {})]
            if self.change.get("no_method") == module:
                funcs = [{"name": f"{module}_delete_jobs", "module": module,
                          "method": "delete_jobs"}]
            data = {"function_count": len(funcs), "functions": funcs}
        elif name == "astroquery_get_function_info":
            method = args["function_name"]
            pars = [param(n) for n in PARAMETERS[module][method]]
            pars += [param("verbose", required=False)]
            if self.change.get("heasarc_kwargs") and module == "heasarc":
                pars.append(param("kwargs", required=True))
            if self.change.get("unexpected_required") == module:
                pars.append(param("password"))
            if self.change.get("missing_radius") == module:
                pars = [p for p in pars if p["name"] != "radius"]
            data = {"module": module, "method": method, "parameters": pars}
        else:
            raise AssertionError(f"Unexpected discovery call {name}")
        return SimpleNamespace(data=data, structured_content=None,
                               content=[], is_error=False)


def run_fixture(*, count=50, seed=42, modules=SUPPORTED_MODULES, change=None):
    sessions = []
    def factory(url):
        s = FixtureSession(url, change=change)
        sessions.append(s)
        return s
    result = asyncio.run(generate(count=count, seed=seed, modules=modules,
                                  session_factory=factory))
    return result, sessions[0]


class GeneratorTests(unittest.TestCase):
    def test_balanced_50_candidates_and_safe_methods(self):
        (items, report), session = run_fixture()
        self.assertEqual(len(items), 50)
        self.assertEqual(Counter(t["module"] for t in items),
                         Counter({mod: 10 for mod in SUPPORTED_MODULES}))
        self.assertEqual(report["archive_queries_executed"], 0)
        self.assertEqual(report["validation_status"], "candidate_unvalidated")
        self.assertTrue(session.closed)
        self.assertNotIn("astroquery_execute", [name for name, _ in session.calls])
        for case in items:
            self.assertEqual(case["validation_status"], "candidate_unvalidated")
            ref = case["reference_call"]
            self.assertEqual(ref["tool"], "astroquery_execute")
            module = ref["arguments"]["module_name"]
            self.assertIn(ref["arguments"]["function_name"], SAFE_METHODS[module])
            self.assertEqual(case["constraints"]["object_name"] if module == "simbad" else
                             case["constraints"]["radius"]["unit"],
                             case["target"] if module == "simbad" else "arcmin")
            self.assertFalse(any(key in ref["arguments"]["params"]
                                 for key in ("download", "upload", "login", "delete")))

    def test_reproducible_same_seed_and_schema(self):
        (first, report1), _ = run_fixture()
        (second, report2), _ = run_fixture()
        self.assertEqual(first, second)
        self.assertEqual(report1["discovered_schema_sha256"], report2["discovered_schema_sha256"])
        (different, _), _ = run_fixture(seed=99)
        self.assertNotEqual(first, different)
        self.assertEqual([c["id"] for c in first], [f"ASTROAKD-020-{i:05d}" for i in range(1, 51)])
        self.assertEqual(len({case["question"] for case in first}), 50)

    def test_ref_arguments_correspond_to_signature(self):
        (items, _), session = run_fixture()
        signature_map = {}
        for module, methods in PARAMETERS.items():
            method = next(iter(methods))
            signature_map[module] = set(methods[method])
        for case in items:
            ref = case["reference_call"]["arguments"]
            self.assertEqual(set(ref["params"]), signature_map[case["module"]])
            self.assertEqual(ref["module_name"], case["module"])

    def test_available_methods_are_only_allowlisted(self):
        with self.assertRaises(GenerationError):
            bind_signature("gaia", "delete_user_table",
                           {"parameters": [param("name")]})
        with self.assertRaises(GenerationError):
            run_fixture(change={"no_method": "heasarc"})

    def test_reject_unavailable_service(self):
        with self.assertRaisesRegex(GenerationError, "not available"):
            run_fixture(change={"unavailable": "gaia"})

    def test_reject_unsupported_required_parameter(self):
        with self.assertRaisesRegex(GenerationError, "unsupported required"):
            run_fixture(change={"unexpected_required": "vizier"})

    def test_generate_full_dataset_with_realistic_heasarc_kwargs(self):
        (items, report), session = run_fixture(change={"heasarc_kwargs": True})
        self.assertEqual(len(items), 50)
        self.assertEqual(report["by_module"]["heasarc"], 10)
        self.assertEqual(report["archive_queries_executed"], 0)
        self.assertNotIn("astroquery_execute", [name for name, _ in session.calls])

    def test_heasarc_documented_variadic_kwargs_is_not_required(self):
        # On the real laptop astroquery-mcp reports HEASARC.query_region's
        # **kwargs as required=True because introspection loses parameter kind.
        info = {"module": "heasarc", "method": "query_region", "parameters": [
            param("position", required=False),
            param("catalog", required=False),
            param("radius", required=False),
            param("spatial", required=False),
            param("maxrec", required=False),
            param("kwargs", required=True),
        ]}
        bound = bind_signature("heasarc", "query_region", info)
        self.assertEqual(bound.semantic_parameters, {
            "coordinate": "position", "radius": "radius", "catalog": "catalog",
        })
        self.assertEqual(bound.signature_source, "introspection")
        self.assertIn("kwargs", {p["name"] for p in bound.advertised_parameters})

    def test_heasarc_other_unknown_required_still_rejected(self):
        info = {"module": "heasarc", "method": "query_region", "parameters": [
            param("position", required=False), param("catalog", required=False),
            param("radius", required=False), param("kwargs", required=True),
            param("token", required=True),
        ]}
        with self.assertRaisesRegex(GenerationError, "unsupported required.*token"):
            bind_signature("heasarc", "query_region", info)

    def test_other_module_kwargs_is_not_whitelisted(self):
        info = {"module": "gaia", "method": "query_object", "parameters": [
            param("coordinate"), param("radius", required=False),
            param("kwargs", required=True),
        ]}
        with self.assertRaisesRegex(GenerationError, "unsupported required.*kwargs"):
            bind_signature("gaia", "query_object", info)

    def test_reject_absent_radius(self):
        with self.assertRaisesRegex(GenerationError, "missing required template"):
            run_fixture(change={"missing_radius": "mast"})

    def test_schema_rejects_unknown_required_flag(self):
        with self.assertRaisesRegex(GenerationError, "optionality"):
            bind_signature("simbad", "query_object", {
                "parameters": [param("object_name"), {"name": "wildcard"}],
            })

    def test_reject_bad_module_selection(self):
        for value in ("", "simbad,simbad", "gaia,ads", "simbad,"):
            with self.subTest(value=value), self.assertRaises(GenerationError):
                parse_modules(value)
        self.assertEqual(parse_modules("vizier,simbad"), ("simbad", "vizier"))

    def test_restrict_modules_and_small_counts(self):
        (items, report), _ = run_fixture(count=5, modules=("gaia",))
        self.assertEqual(len(items), 5)
        self.assertEqual({i["module"] for i in items}, {"gaia"})
        self.assertEqual(report["by_module"], {"gaia": 5})

    def test_bounded_count_and_unique_seed_pool(self):
        for count in (0, 501):
            with self.assertRaises(GenerationError):
                run_fixture(count=count)
        with self.assertRaisesRegex(GenerationError, "Not enough unique"):
            run_fixture(count=23, modules=("simbad",))

    def test_atomic_jsonl_and_no_overwrite(self):
        (items, _), _ = run_fixture(count=11)
        with TemporaryDirectory() as d:
            path = Path(d) / "nested" / "dataset.jsonl"
            digest = write_jsonl(path, items)
            blob = path.read_bytes()
            self.assertEqual(hashlib.sha256(blob).hexdigest(), digest)
            decoded = [json.loads(line) for line in blob.decode().splitlines()]
            self.assertEqual(decoded, items)
            with self.assertRaisesRegex(GenerationError, "Output exists"):
                write_jsonl(path, items)
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), digest)
            self.assertEqual(write_jsonl(path, items, replace=True), digest)
            self.assertFalse(any(p.name.startswith(".astroakd-") for p in path.parent.iterdir()))


if __name__ == "__main__":
    unittest.main()


class WrappedSignatureTests(unittest.TestCase):
    def test_vizier_documented_decorator_adapter_is_tagged(self):
        info = {"module": "vizier", "method": "query_region", "parameters": [
            {"name": "args", "required": True}, {"name": "kwargs", "required": True},
        ]}
        bound = bind_signature("vizier", "query_region", info)
        self.assertEqual(bound.signature_source, "documented_vizier_wrapper")
        self.assertEqual(bound.semantic_parameters,
                         {"coordinate": "coordinates", "radius": "radius", "catalog": "catalog"})

    def test_no_generic_dynamic_wrapper_bypass(self):
        info = {"module": "gaia", "method": "query_object", "parameters": [
            {"name": "args", "required": True}, {"name": "kwargs", "required": True},
        ]}
        with self.assertRaises(GenerationError):
            bind_signature("gaia", "query_object", info)
