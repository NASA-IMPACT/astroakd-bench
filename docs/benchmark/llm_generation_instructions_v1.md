# AstroAKD-Bench question-writing instructions — V1-derived (0.6.4)

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

## Question families inspired by workbook

- Observation identification: “Which observation ID corresponds to …?”
- Program attribution: “What observing proposal or program identifier is associated with …?”
- Instrument configuration: “Which instrument/channel or filter was used for …?”
- Timing: “What is the start time (UTC) or exposure duration (s) of …?”
- Catalog property: “What source identifier, parallax, proper motion, or magnitude is reported for …?”

For the MCP-backed track, only emit families actually supported by the discovered function and returned column schema. A result listing alone does not establish observation-specific truth.

**Limitations:** Original workbook questions often specify exact dates/instruments/filters; these constraints cannot be faithfully generated from a broad cone-search MCP call alone. Do not invent them. Deeper scientific grounding requires separately retrieving and checking archive row-level records.
