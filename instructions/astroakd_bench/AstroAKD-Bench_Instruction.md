# AstroAKD-Bench question-writing instructions — V1-derived; reference-aware (0.6.7.11.9)

**Source and scope:** Synthesized from the user-provided `Astro Benchmark V1(1).xlsx`, with three worksheets (`benchmark_results`, `with_system_prompt`, `mcp`) containing about 100 evaluation questions each. The two latter sheets share the same 100 question texts. These are *design examples*, not a verified astronomical truth set. Do **not** copy any expected_answer or use historical model responses as gold.

## Instruction policy (default ON for OpenAI and hybrid backends)

Write concise, natural, **answer-oriented astronomical data-discovery questions** that ask for a specific retrievable field rather than simply saying “query this archive.” The V1 examples emphasize observational metadata: observation identifier / ObsID, proposal or program ID, instrument and detector/channel, filter and grating, exposure/duration in seconds, start date in UTC, and object-specific observational constraints. For catalogs, ask for source identifiers, astrometric coordinates, parallax/proper motion, and photometric magnitudes when those fields exist.

Requirements:
1. Vary the *scientific intent* as well as the astronomical target; make tasks observationally concrete but do not hallucinate a specific date, ObsID, telescope, instrument, program, filter, measured answer, or archive predicate absent from the supplied constraints or verified search evidence.
2. Keep the astronomical target and archive explicitly identifiable. Preserve given coordinates, angular search radius and catalog exactly. Do not add observational filters that cannot be expressed by the reference MCP call.
3. Ask a question answerable from the **specified result columns**. Prefer one primary measurable field per task (an ID, quantity with units, instrument, observing configuration), and specify how to select a result only when selection criteria are in the verified call.
4. Maintain diversity across module, target, intent, and question phrasing; never repeat a question or present superficial punctuation/synonym variants as independent science.
5. Prefer a specific question over an open-ended dump of metadata. Include units for exposures and angular quantities; use ICRS for coordinates and UTC for times when grounded.
6. Treat generated questions as **unverified candidates**. Leave expected answers empty until separately checked against actual archive results. Never claim a web page or an LLM response is a scientific reference answer.
7. If no MCP server is used, employ the OpenAI Responses API `web_search` tool for research context, keep trustworthy source URLs when available, and mark MCP executability/answer verification as *not established*.

## Reference-aware core-question policy (0.6.7.11.9)

**Primary goal:** Produce questions for which an independent live Astroquery MCP call can return a **complete, bounded, machine-comparable answer**. Do not make questions easy by removing legitimate astronomy, but avoid tasks whose answers are thousands of catalog rows or 20-row excerpts from a larger result.

- Use the supplied *prechecked MCP call*, center, radius, archive and expected answer field exactly. The precheck is made **before** question authoring. It must have a nonempty, structurally complete result, no truncation, the requested field, and size within configured limits; a model response never establishes this.
- **Gaia:** Never ask for all parallaxes, proper motions, magnitudes or source IDs over a broad multi-arcminute cone. Prefer a prechecked compact result with a small angular radius and clearly defined field and source association. Do not claim that an unsupported rank, limit or quality filter was applied by the MCP call.
- **MAST:** Do not present its first 20 rows as an exhaustive observation census when the service reports more records. Use only prechecked, untruncated, bounded results. Keep observation IDs paired with their properties when the question requires per-observation answers.
- **HEASARC:** Distinguish *distinct statuses/instruments* from per-observation status or exposure lists. Preserve row multiplicity when the question asks for each observation; do not silently compress duplicate values. Do not invent a catalog filter.
- **VizieR:** State the actual catalog. Avoid unrestricted multi-table dumps and fields not present in the prechecked result. Do not invent source-selection criteria absent from the MCP query.
- If multiple records are returned, do not imply there is exactly one matching source or measurement. Specify whether the answer is a set of distinct values or a per-record list, consistently with the frozen task template.
- Never ask for a response that requires complete records beyond the prechecked MCP result. Null, absent, oversized and truncated result columns must be rejected by the program before authoring, not patched with model guesses.
- Candidate acceptance must be independent of how arms A, B, and C performed on any previous benchmark. Benchmark difficulties must be driven by answer feasibility, not tuned to make particular agents succeed.
- These constraints apply to **core single-call** questions. ADS literature and multi-archive tracks are explicitly multistep and still require separate answer evidence; do not mislabel ADS paper metadata as a complete science reference.

The boundedness policy is **enforced in source code** (`benchmark/reference_aware.py`) when `create-queries --with-reference-answers` is used. Instructions alone cannot alter an MCP search call. A prechecked response is a feasibility observation, not a gold answer; independently recollect references after publishing the dataset.

## Question families inspired by workbook

- Observation identification: “Which observation ID corresponds to …?”
- Program attribution: “What observing proposal or program identifier is associated with …?”
- Instrument configuration: “Which instrument/channel or filter was used for …?”
- Timing: “What is the start time (UTC) or exposure duration (s) of …?”
- Catalog property: “What source identifier, parallax, proper motion, or magnitude is reported for …?”

For the MCP-backed track, only emit families actually supported by the discovered function and returned column schema. A result listing alone does not establish observation-specific truth.

**Limitations:** Original workbook questions often specify exact dates/instruments/filters; these constraints cannot be faithfully generated from a broad cone-search MCP call alone. Do not invent them. Deeper scientific grounding requires separately retrieving and checking archive row-level records.

---

## Gold Benchmark Dataset taxonomy (expanded in 0.6.4.3)

The separate user-provided **Gold Benchmark Dataset.xlsx**, sheet `benchmark_queries`,
contains **31 populated numbered questions**, classified as **20 `archive_driven`,
7 `coordinate_driven`, and 4 `literature_driven`**. The workbook's expected-answer
cells are evaluation examples, *not* automatically trusted new gold answers.

**`archive_driven` task family (20 examples):** Begin with an explicitly named object
or observation. Ask for Chandra/HEASARC ObsIDs, proposal IDs, total exposure in
kiloseconds, data product URLs, or records associated with a specified bibcode or DOI.
Preserve telescope, grating (e.g., HETGS), cut-off year, and the given identifier.
A question requiring filtering by instrument/year or accumulating multiple exposures
must not be represented as verified by a broad 20-row cone search alone.

**`coordinate_driven` (7 examples):** Begin with an explicit ICRS J2000 sky position,
expressed as sexagesimal RA/Dec, and an angular radius in arcsec/arcmin. Examples
search Chandra HETGS, XMM-Newton, and NICER observations. Convert coordinates
and units carefully; distinguish sky radius from exposure or epoch, and do not
silently invent source-name matches. Cross-archive questions may need several MCP
calls and cannot be reduced to a single assumed-successful observation.

**`literature_driven` (4 examples):** Start from a physical description in a paper
rather than a known source name or sky coordinate. The examples include a quasar
at `z=0.0809` with a `-17,300 km/s` ultra-fast outflow; the nearest tidal disruption
event; and a nearby Lyman-break-galaxy analog. Discover the relevant paper and
object with traceable literature evidence **before** constructing an observation
request for Chandra HETGS, HST COS, NICER, or XMM-Newton. Do not assume that an
abstract directly proves the availability of a requested archive dataset.

### Literature tool routing — required

1. Use the **independent NASA IMPACT Astroquery MCP server** for all Astroquery
   calls. Its authentication variable for ADS is **`API_DEV_KEY`** in the MCP
   server's launch environment. Never make direct `astroquery.nasa_ads`, `ads`,
   `requests` or independent ADS REST calls from the benchmark.
2. Query `astroquery_check_auth` **on the MCP server** (do not print or persist the
   token). If ADS is configured, use MCP `ads_query_compact` (standard or minimal
   fields, bounded results), then optionally `ads_get_paper` for a verified bibcode.
3. If ADS authentication is missing, the ADS tool is unavailable, or ADS search
   fails, **continue** with OpenAI Responses API `web_search`. This fallback may
   still use MCP for non-literature astronomical archive steps.
4. Preserve the research provider (`astroquery_mcp_ads` versus `openai_web_search`),
   bibliographic references and observed public source URLs in provenance.
   Do not mistake an LLM result or paper metadata for an independently validated
   telescope observation or a verified expected answer.
5. For a literature-driven benchmark, separate: (a) *literature identification*,
   (b) *object/position determination*, (c) *actual archive observation lookup*,
   (d) *answer verification*. Record which of these stages have actually completed.

### Diversity / safety

Balance the three question families and vary observatory, science class, evidence
source, task intent, coordinate form, and units. Reject duplicate scientific
intent/target/archive combinations. Do not simply replace one ObsID or quasar
name with a fictional value. Distinguish requests for a complete list from
results truncated by a server's `max_rows` limit. Keep expected answers *unverified*
until independent reference validation.

## Native Gold mixed generation (0.6.5)

Generate the three distinct **task types** within the same benchmark workflow:

- **`archive_driven`:** Start from a named object, and request a specific archive field supported by its discovered MCP call (IDs, exposure, proposal, instrument, catalog measurement). Do not claim a broad table search enforces publication dates, HETGS, or other filters it does not express.
- **`coordinate_driven`:** Start with explicit J2000 ICRS RA/Dec (prefer sexagesimal accompanied by decimal degrees), search radius in arcsec or arcmin, and an archive-compatible task. Coordinates and radius must come from the immutable MCP reference-call constraints, not be hallucinated by the model. The benchmark itself injects precise coordinates when necessary.
- **`literature_driven`:** Start with paper/object discovery and **then** ask the agent to identify/verify observation data or objects using the appropriate archive. Search via Astroquery MCP's `astroquery_check_auth` and `ads_query_compact` when the MCP server is authenticated with `API_DEV_KEY`; otherwise use OpenAI `web_search`. Cite identified publications and separately cross-check archive metadata, preferably using `ads_get_paper` when a bibcode is available. Do not equate bibliographic discovery with archive validation.

Gold Benchmark Dataset.xlsx has 31 populated example questions: 20 archive-driven, 7 coordinate-driven, 4 literature-driven. Its examples motivate the task distribution and scientific content, but **no gold answer is copied** and literature-specific paper statements remain unverified until checked. The `--task-mix gold50` option requests 32 / 10 / 8 as a configurable test composition, not the workbook's exact original proportions. The eight literature **research anchors** are deliberately seeds rather than canned complete benchmark questions, so OpenAI authors the output after new research; every authored question and research provenance is recorded. If the model authoring fails, the question is marked as a template fallback, not misrepresented as model-authored.

**Evaluation requirement:** keep literature-driven tasks on a separate multistep track; the existing single-call reference validator is for MCP-bound archive/coordinate candidates only. All three types are `unverified_candidate` until actual evidence and answers are checked. Ensure separate source provenance for MCP ADS vs. OpenAI fallback; ADS authentication is not proof of successful ADS query execution.
