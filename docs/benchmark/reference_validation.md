# AstroAKD-Bench 0.3.0 — Reference validation

This milestone executes the **accepted, unmodified 0.2.0 candidate dataset** through the
same locally hosted Astroquery MCP HTTP server. It does **not** call the OpenAI API.
The production server (`server.py`, `executor.py`, dependencies, and lockfiles) is unchanged.

## Start the MCP server

```bash
uv run fastmcp run server.py --transport http --host 127.0.0.1 --port 8000
```

In a second terminal (from the repository root), first run a **five-task pilot**:

```bash
uv run python -m benchmark validate \
  --input datasets/generated/synthetic_queries.jsonl \
  --strict-accepted-020 \
  --limit 5 \
  --attempts 2 --delay 2 --timeout 180 \
  --output datasets/validated/reference_answers.jsonl \
  --report datasets/validated/validation_report.json
```

`--strict-accepted-020` verifies the SHA-256 of the accepted 50-task input dataset:
`e6de68eedf2b38ea08dd684cac678edc80ee23abe51b7189f0adfb5e369c1fe9`.
The five-task pilot reports `PARTIAL` and saves an fsynced progress journal; it does
not publish an incomplete reference dataset. Continue with:

```bash
uv run python -m benchmark validate \
  --input datasets/generated/synthetic_queries.jsonl \
  --strict-accepted-020 --resume \
  --attempts 2 --delay 2 --timeout 180 \
  --output datasets/validated/reference_answers.jsonl \
  --report datasets/validated/validation_report.json
```

Alternatively, omit `--limit` to run all 50 tasks in one pass. Use `--replace`
only to explicitly **discard previous benchmark validation work and start over**.
Do not use it for normal resumptions. `--resume` and `--replace` cannot be used
together. No output or report paths may overlap the input.

## Outputs and interpretation

- `reference_answers.jsonl`: one outcome **for every input task**, in input order,
  once the run completes. Includes the exact generated MCP call, response payload
  when within the byte limit, disposition, evidence, and per-attempt trace.
- `reference_answers.jsonl.progress.jsonl`: per-task append-only fsynced journal.
  It persists even if the process or archive stops unexpectedly.
- `reference_answers.jsonl.manifest.json`: input SHA-256, server URL,
  discovery SHA-256 and execution limits for safe `--resume`.
- `validation_report.json`: totals by module and disposition and a quality gate;
  includes the output SHA-256 when all tasks have been processed.

Possible dispositions:

| Disposition | Meaning |
|---|---|
| `accepted_nonempty` | Consistent structured table, at least one returned row |
| `accepted_empty` | Valid empty table/table list; expected science answer is still unverified |
| `rejected_arguments` | Server rejected the reference arguments |
| `rejected_auth` | Authorization rejected |
| `archive_error` | Upstream/service failure, after eligible retries |
| `transport_error` | HTTP/MCP failure after retries |
| `rejected_malformed` | Unexpected or inconsistent success envelope/table metadata |
| `rejected_oversize` | Response too large to preserve within safety limit |
| `review_required` | Success response, but unknown result shape |

The report `status=COMPLETE` means **every candidate has a disposition**. It does
not imply every query succeeded. `quality_gate=PASS` means all completed queries
were structurally accepted; `REVIEW` means one or more need investigation.
Neither establishes independently verified astrophysical accuracy.

### Scientific validation boundary

The validator checks the response's `module/function`, serialized table shape,
`row_count`, `total_rows`, and truncation consistency. Where it can identify
coordinate columns that are reliably in degrees, it calculates separation
from the requested center and stores it as **advisory evidence only**. It does
not reject otherwise valid observation searches by separation: instrument
footprints can intersect the region while observation-center coordinates lie
outside the search radius. Catalog identity remains `not_independently_verified`
when only the requested catalog argument is available. Additional independent
astronomical spot checks/manual gold-answer auditing are recommended before
using these references for scientific correctness scoring.

### Safety and upstream limitations

- Only fixed, read-only 0.2.0 MCP methods and curated catalogs are allowed.
- Introspection schema drift **fails closed** before executing reference calls.
- One query at a time with a default 2-second pause, max 2 attempts per task,
  exponential retry delay, and a 180-second MCP timeout per operation.
- `--max-rows` is supported by the **MAST** `query_region` server path only;
  other archives may return larger result tables. Set `--max-response-bytes`
  (default 8 MiB) to limit stored responses; oversized responses are not
  silently truncated, but explicitly rejected.
- The journal saves unsuccessful attempts and reason codes; candidates are
  never silently deleted.
- The client uses the same local server URL, but live archive access requires
  internet access. Requests are made to public astronomy archives, not OpenAI.

## Offline tests

```bash
uv run python -m unittest discover -s benchmark/tests -v
```

Live acceptance requires running the real `validate` command on the laptop.
