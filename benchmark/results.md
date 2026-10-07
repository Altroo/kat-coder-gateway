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

Reproduce the table with:

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
