# Benchmark results

## 2026-10-07 — completed

**Keep KAT-Coder V2.5 Dev as the default. None of these results justifies replacing it.** Tiel's one-check advantage over KAT is too small to justify a switch, especially with its higher memory use. MiMo used the least RAM but performed poorly in this configuration.

**Qwen3.8 was already tested and rejected in an earlier evaluation.** The user reaffirmed that decision on 2026-10-07 because it was both slow and poor at practical programming. Its inclusion here was a retest, not discovery of a new candidate. It passed 29 of these 30 narrow checks, but that does not overturn the earlier real-work assessment; it also generated about six times slower than KAT. Qwen3.8 remains rejected as a replacement. The older evaluation is recorded here as user-provided history; the measurements below are from this run only.

This is a small screening test: three coding tasks, ten test cases each, and one two-turn tool interaction. It is not a general coding leaderboard or a full OpenCode repository-editing benchmark. All models ran with thinking disabled; these results do not measure their best reasoning-enabled quality.

Protocol: [2026-10-07.v1](benchmark.md). Server: AMD Ryzen 7 7700, eight physical cores, 62 GiB RAM; CPU only, eight inference threads, one active model request at a time. The article translation/correction batch remained stopped and its services were left alone.

### Measured comparison

| Model and quantization | Checks passed /30 | Complete tasks /3 | Tool loop | Median generation tok/s | Median first output (s) | Observed peak RSS (GiB) |
| --- | ---: | ---: | --- | ---: | ---: | ---: |
| KAT-Coder V2.5 Dev, Colibri int4 gs64 | 19* | 1 | Pass | 18.4 | 2.4 | 21.3 |
| Tiel-Coder-35B-A3B, UD-Q4_K_XL | 20 | 0 | Pass | 15.6 | 1.8 | 31.9 |
| MiMo-V2.6-Distill-Qwen-9B, Q8_0 | 10 | 0 | Pass | 6.0 | 2.7 | 10.2 |
| Qwen3.8-27B, UD-Q4_K_XL | 29 | 2 | Pass | 3.0 | 5.4 | 22.4 |

* KAT's asynchronous-cache response remained incomplete at both the 1,024-token initial ceiling and the 2,048-token retry ceiling. Its ten cache checks could not execute and received no passing credit. This is an output-budget failure, not ten observed logic failures. The larger attempt took 128.86 seconds; both attempts together took 186.69 seconds. All other coding responses finished within the initial ceiling.

Throughput is a client-side approximation: completion tokens divided by elapsed time after the first generated output, summarized as the median of the three tasks. First-output latency uses each task's initial attempt. RSS was sampled from the model process tree during the initial campaign, so KAT's separate 2,048-token retry is not included in its memory figure. Measurements are one pass and should not be treated as precise sustained-performance estimates.

| Model | Invoice arithmetic /10 | Dependency ordering /10 | Async cache /10 | Main observed issue |
| --- | ---: | ---: | ---: | --- |
| KAT | 9 | 10 | 0, incomplete | Empty-input invoice path skipped discount validation; cache response repeatedly revised its approach inside comments and hit the output ceiling. |
| Tiel | 9 | 4 | 7 | Non-finite discount exception type; mixed task indices with IDs; detached cache loads could hang. |
| MiMo | 1 | 4 | 5 | Multiple arithmetic/validation and ordering failures; cache mishandled synchronous loads and invalidation races. |
| Qwen3.8 | 10 | 10 | 9 | Concurrent calls did not deduplicate a loader that throws synchronously. |

All four completed the tool probe: request exactly `src/settings.py` with `read_file`, then report `RETRY_LIMIT = 17` from the supplied result. This proves a basic tool round trip only.

### Runtime and method notes

- KAT used the deployed Colibri service with a 65,536-token context capacity. GGUF candidates used the pinned llama.cpp CPU image, an 8,192-token context, one slot, and a 32 GiB RAM ceiling with no swap. The actual prompts fit both capacities. Quantizations and inference runtimes differ; this compares practical deployment configurations.
- Candidate GGUF files were SHA-256 verified against pinned model revisions. KAT's existing container metadata was hashed; its full weight shards were not rehashed during timed inference. Exact identities are in [model-manifest.json](runs/2026-10-07/model-manifest.json).
- The invoice prompt initially omitted its input container type. It was clarified to explicitly say a list of dictionaries before any candidate was scored, and KAT's invoice response was regenerated using that same final prompt. The [discarded baseline attempt](runs/2026-10-07/kat/original-ambiguous-invoice.json) is retained. The initial campaign's total KAT wall time includes this pause; use the per-task timings instead.
- Inspection caught a harness issue: Node can exit successfully while a Promise remains unresolved. The final harness enforces a timeout per asynchronous test and requires all ten test results. Every saved response was regraded without model feedback or regeneration. Earlier test outputs remain in `initial_test_result`; they are not the reported scores. All 30 reference tests passed against the corrected harness.
- The identical-prompt 2,048-token retry policy applies to any response truncated at 1,024 tokens. Only KAT needed it. Both of its attempts are retained.

Print the saved scores and timing summary with the current reporting definitions:

```sh
python3 benchmark/summarize.py benchmark/runs/2026-10-07
```

Raw results: [KAT](runs/2026-10-07/kat/report.json), [Tiel](runs/2026-10-07/tiel/report.json), [MiMo](runs/2026-10-07/mimo/report.json), [Qwen3.8](runs/2026-10-07/qwen/report.json), and [runtime observations](runs/2026-10-07/campaign.json). The protocol and scripts are also saved on the server in `/var/www/colibri-benchmarks` for the next comparison.

### Upgrade and streaming validation

OpenCode was upgraded from **2.0.12 to 2.0.24** and the Colibri fork from **1.12.0 to 2.0.0**. The deployed Colibri/gateway commit is `f2e1fc04`; the previous installation remains available for rollback.

The `OpenAI Chat stream ended without finish_reason` retry was reproduced and fixed in Colibri's engine control handling. The gateway sends an internal `STOP` when it sees a configured stopping sequence or end-of-turn marker. Colibri had treated this normal completion as `CANCEL` and returned an error, leaving the stream without its terminal event. This did not require the user to press Stop. `STOP` now completes normally, while explicit `CANCEL` remains a cancellation.

The repaired deployment passed the explicit-stop reproduction, a Redux `providesTags`/`invalidatesTags` explanation, and an upgraded OpenCode CLI smoke test with no error events. Both direct stream checks emitted `finish_reason: stop` and `[DONE]`.

Validation: portable suite 2,360 tests with 296 skipped; Linux gateway suite 436 tests with one skipped; nine real-engine control tests; tiny-model oracle matched all 16 reference tokens. See [validation.json](runs/2026-10-07/validation.json).

Final state: KAT restored, gateway healthy, temporary candidate container removed. Qwen remains a previously rejected model; its retest artifacts are retained for transparency. None of the candidate weights was promoted into the permanent production model directory. PR work remains deferred.

### Storage cleanup — 2026-10-07

At the user's request, the Tiel, MiMo, and Qwen3.8 GGUF downloads were deleted after testing, reclaiming 49.45 GB (46.05 GiB). KAT remains in `/var/www/colibri-models/KAT-Coder-V2.5-Dev-colibri-i4-gs64` and the gateway passed its health check. Benchmark scripts, manifests, generated answers, and results were retained. Candidate weights would need to be downloaded and verified again before a rerun. See [cleanup.json](runs/2026-10-07/cleanup.json).


## 2026-10-07–08 — Ornith comparison with thinking enabled

**The main thinking-enabled comparison is complete: keep KAT as the default.** The separate 16K-token diagnostic is also complete; it does not change that recommendation. The user requested thinking-enabled programming evaluation: KAT receives thinking on plus `reasoning_effort: high`; Ornith receives native thinking on and no unsupported effort field.

The downloaded weights are the official `ornith-ai/Ornith-1.5-35B-A3B-GGUF` **Q4_K_M** file (21,713,463,040 bytes), revision `12393612fd4f730ff5aadc23e9b8f9648aa49ceb`. Its full SHA-256 matches the published LFS checksum: `42739874cc2ccfdb8523b23fbe52e29b2a7555c8176737ca9ca0b5d59859d41f`.

**Diagnostic correction:** an initial interpretation of escaped runtime metadata suggested malformed template newlines. Inspecting the actual saved rendered prompt shows six real newlines and zero literal backslash-n sequences. No template defect was established; the earlier claim was incorrect. The preliminary reasoning phase was interrupted during that investigation. See [prompt evidence](runs/2026-10-07-ornith/embedded-template-probe.json) and [assessment.json](runs/2026-10-07-ornith/assessment.json).

The full thinking run pins the author's canonical template from revision `10fbf86fed7ecee4a061f8b499a618f46001cac1`, SHA-256 `182e77dd83bd8e9ca818b240b82e28f243762cd5dda32e6eef327df7b1cd107e`. It validates rendered role separators and the thinking marker before scoring. No weights were changed or redownloaded.

Protocols: `2026-10-07.v3-thinking` (three functions, 30 checks) and `2026-10-07.repo-v2-thinking` (Django/React tool-driven repairs, 20 checks). Both use temperature 1.0, top-p 0.95, an 8,192-token response ceiling including reasoning, and eight CPU threads. Repair tasks allow eight turns, 24,576 completion tokens and three test-tool calls. Thinking history is preserved between tool turns. This is a small, one-pass test of usable CPU deployments, not a leaderboard reproduction.

Ornith exposes thinking on/off, with no low/medium/high levels in its official template. In the deployed Colibri Qwen renderer, KAT's `high` field enables thinking but does not implement a separate effort scale either. There is no additional reasoning-only budget; both remain subject to their total output ceiling.

Historical thinking-off results in this phase: KAT 26/30 function checks and 18/20 framework checks; Ornith 19/30 and 17/20. Those remain valid observations of that mode, but do not answer the user's thinking-enabled comparison. The preliminary 4,096-token KAT reasoning run hit its output ceiling on the cache task; the larger-budget comparison supersedes it. Raw outputs remain in [the dated directory](runs/2026-10-07-ornith/).


### Shared 8K response budget — completed

| Task | KAT checks passed | Ornith checks passed | KAT time | Ornith time |
| --- | ---: | ---: | ---: | ---: |
| Invoice arithmetic | 10/10 | 0/10, incomplete | 404.6 s | 436.4 s |
| Dependency ordering | 6/10 | 10/10 | 53.6 s | 257.1 s |
| Async cache | 10/10 | 0/10, incomplete | 494.7 s | 435.5 s |
| Django tenant repair | 10/10 | 10/10 | 469.5 s | 267.5 s |
| React search repair | 10/10 | 1/10, repair incomplete | 194.5 s | 495.9 s |
| **Total** | **46/50; 4/5 tasks fully pass** | **21/50; 2/5 tasks fully pass** | **26m 56.9s** | **31m 32.4s** |

KAT's four failures are actual dependency-ordering test failures: it validates references against an ID map that is still being populated, so valid references to later input tasks are rejected. Ornith solves that task correctly. Both solve the Django task; Ornith is faster there.

Ornith reaches the 8,192-token ceiling on invoice arithmetic and asynchronous caching. The invoice answer contains an incomplete code block; the cache answer contains reasoning only. Their 20 checks cannot execute and receive no passing credit, rather than representing 20 observed logic errors. During React repair, Ornith spends four turns reading files and running the original tests, then exhausts its fifth response while reasoning. It makes no file edits; grading the unchanged fixture yields one pass and nine failed checks. This is an unfinished repair, not nine defects introduced by a completed patch.

| Resource measure | KAT | Ornith |
| --- | ---: | ---: |
| Completion tokens across all five tasks, including thinking | 17,805 | 34,265 |
| Median function completion tokens / total response seconds | 12.8 tok/s | 18.8 tok/s |
| Observed peak process RSS during main campaign | 21.8 GiB | 38.5 GiB |

Ornith generates tokens faster in this CPU configuration, but uses about 1.9 times as many completion tokens and finishes fewer tasks. KAT is more efficient for this sample of our coding workflow; that is different from having the higher raw token rate. Neither outcome proves general model superiority from five synthetic tasks and one sample per prompt.

Times sum completed task attempts, including framework tool/test time; they exclude loading, warmups, the user-requested pause, and the interrupted KAT cache generation that was restarted on resume. KAT's two completed pre-pause responses were preserved. RSS is sampled process-tree memory, not a universal model minimum. Runtime, quantization, context capacities, and some sampler defaults differ.

First-visible-output timing is affected by Colibri's reasoning buffering. The current end-to-end rate includes all reasoning tokens and the full request duration; the earlier calculation that divided all tokens by only the time after the first visible chunk inflated KAT's apparent generation rate. Scores and total task times are unchanged.

Raw main results: [KAT functions](runs/2026-10-07-ornith/kat-thinking/report.json), [KAT framework repairs](runs/2026-10-07-ornith/kat-thinking/repo-report.json), [Ornith functions](runs/2026-10-07-ornith/ornith-thinking/report.json), [Ornith framework repairs](runs/2026-10-07-ornith/ornith-thinking/repo-report.json), and [runtime campaign](runs/2026-10-07-ornith/thinking-campaign.json).


### Recommended KAT output budget

Keep **8,192 completion tokens with thinking enabled** for the deep profile. In this run, KAT's successful invoice and cache answers used 5,216 and 6,347 tokens respectively, including reasoning; 4K would be too small for those answers. The ceiling is a maximum, not a target. KAT needed no 16K retry. Its end-to-end median across the three function responses was 12.8 tokens/s, versus Ornith's 18.8 tokens/s; useful task completion favoured KAT despite that lower token rate. This recommendation concerns generated output, not the input context capacity. The existing OpenCode deep profile already has the 8K ceiling; the profile configuration was not changed.


### Separate 16K diagnostic — completed

Only Ornith's two truncated function responses were retried, once each, with unchanged prompts and no test feedback. Thinking stayed on, temperature stayed 1.0, and top-p stayed 0.95. This is separate from the shared 8K comparison above; KAT's completed answers and the framework repairs were not regenerated.

| Retried task | Result | Completion tokens | Time |
| --- | --- | ---: | ---: |
| Invoice arithmetic | 10/10 passed; normal completion | 4,241 | 216.2 s |
| Async cache | Incomplete; reasoning only, no code | 16,384 | 969.0 s |

The probe earns **10/20 checks** and adds **19m 45.1s** of task time. The cache test harness reports a missing function because the answer contains no code; this is not evidence of ten separate logic defects. The invoice retry finishes below even the original 8K ceiling, so its improvement cannot be attributed to the larger ceiling alone: this is a fresh stochastic sample. We have preserved both attempts and have not substituted the better retry into the main comparison.

Raw evidence: [diagnostic report](runs/2026-10-07-ornith/ornith-thinking-16k/report.json), [probe metadata](runs/2026-10-07-ornith/budget-probe.json), and [final service verification](runs/2026-10-07-ornith/final-verification.json).

**Final state:** KAT is active on the existing upgraded deployment, `/health` returns HTTP 200, and an authenticated streamed request finishes with `finish_reason: stop`. The temporary Ornith serving container is removed. Ornith's verified download remains in `/var/www/colibri-benchmarks/ornith-2026-10-07`; it has not been promoted into `/var/www/colibri-models`. The article-processing services and production project files were not changed. PR work remains deferred.
