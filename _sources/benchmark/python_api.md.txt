# Python API

Use the same named datasets and output root from Python:

```python
import asyncio
from benchmark.api import AstroAKDBench

bench = AstroAKDBench('.')

async def main():
    await bench.create_synthetic_queries(
        name='astroakd_100_v2', count=100, output_dir='datasets',
        require_ads=True, with_reference_answers=True,
    )

asyncio.run(main())

# Reports use saved evidence; they make no model or MCP calls.
reference_report = bench.create_reference_report(
    name='astroakd_100_v2', output_dir='datasets'
)
agent_report = bench.create_agent_report(
    name='astroakd_100_v2', output_dir='datasets'
)
```

For question generation alone use `with_reference_answers=False` (default), and then call `await bench.collect_named_references(name='astroakd_100_v2', output_dir='datasets')`. After a partial collection pass `resume=True` to the same named dataset.

`name` is a safe filename prefix, `count` supports the built-in 1–100 mix, and `output_dir` points to the study root; changing any does not alter a previously frozen dataset. An explicit seed can be supplied; the default is `20261018`.

The lower-level package API is retained for specialized research workflows. For CLI parameters, run `uv run python -m benchmark --help` and `uv run python -m benchmark <command> --help`.

For durable generation, the Python API uses the same filesystem checkpoints as the CLI. After a failure, call `await bench.create_synthetic_queries(name='astroakd_100_v2', count=100, output_dir='datasets', require_ads=True, with_reference_answers=True, resume=True)` with unchanged generation inputs.
