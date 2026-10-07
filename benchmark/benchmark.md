# Coding model benchmark

Protocol version: **2026-10-07.v1**. This is a small, repeatable screening test for our self-hosted programming assistant. It does not replace a real repository benchmark.

## Files

- `benchmark.py`: exact prompts, test cases, streaming client, and isolated code execution.
- `selftest.py`: reference implementations used to check that the test harness works.
- `recheck.py`: reruns tests on saved output without generating or repairing code.
- `summarize.py`: prints a results table from raw JSON without overwriting past results.
- `campaign.py`: sequential runner for our server; restores the KAT service in `finally`.
- `results.md`: dated comparisons and recommendations.
- `runs/YYYY-MM-DD/`: raw results, model revisions, runtime identity, and supporting evidence.

Keep the prompts and tests fixed when adding a model. If their meaning changes, assign a new protocol version and rerun the baseline.

## What we test

| Task | Contract | Scoring |
| --- | --- | --- |
| Invoice arithmetic | Python `Decimal`, per-line half-up rounding, discounts, validation, unchanged inputs | 10 test cases |
| Dependency ordering | Stable topological order, duplicates, invalid references, cycles, a 2,000-task chain | 10 test cases |
| Asynchronous cache | JavaScript Promise deduplication, TTL, rejected loads, invalidation during an in-flight load | 10 test cases |
| Tool loop | Call `read_file` for exactly `src/settings.py`, then use the returned `RETRY_LIMIT = 17` | Report separately as pass/fail |

The invoice input is explicitly a **list of dictionaries**. Test cases are withheld from the model. Each coding task uses a fresh conversation and receives no feedback or repair attempt after test failures.

Generated code runs in disposable Docker containers with no network, a read-only filesystem, an unprivileged user, no Linux capabilities, 256 MiB RAM, one CPU, and a 20-second limit. Each asynchronous JavaScript test also has a one-second timeout; a zero process exit code alone is insufficient, and all 10 test cases must finish. The model has no shell access to the host.

## Generation settings

- Temperature `0`, top-p `1`, thinking disabled.
- Initial coding output ceiling: **1,024 tokens**. If and only if `finish_reason` is `length`, regenerate the unchanged prompt with **2,048 tokens**. Preserve the initial truncated attempt; do not call it a logic failure. If the larger attempt is also truncated, record an incomplete answer, give no passing credit for unexecuted tests, and keep it separate from observed assertion failures.
- Tool call: at most 256 tokens; final tool-result answer: at most 128 tokens.
- Eight CPU threads and one active model request at a time.
- Warm up each model with the identical short prompt `Reply only OK.` before scoring.
- Use each model's own chat template. Do not substitute a template simply to improve a score.
- A stream missing its terminal `finish_reason` is a serving failure, not a successful answer.

Our first comparison uses KAT's production Colibri configuration with a 65,536-token capacity and llama.cpp with an 8,192-token capacity for GGUF candidates. Actual test prompts fit both. Runtimes and quantizations differ: the results compare usable deployment configurations, not model weights in isolation.

## How to run a new model

1. Read `results.md` and the previous model decisions first. Do not present a previously rejected model as new; rerun it only when a changed revision, runtime, or configuration provides a concrete reason, and label the run as a retest. Record the model's source, immutable revision, exact quantization, file size, and SHA-256. Verify the downloaded checksum.
2. Confirm the article translation/correction batch is stopped. Leave its services and data alone. Check available RAM and avoid concurrent model inference.
3. Use an isolated local endpoint for the candidate. Match eight CPU threads, one slot, thinking disabled, and the candidate runtime settings in the dated run manifest. Bind the endpoint to loopback only.
4. Validate the harness on the test server:

   ```sh
   python3 selftest.py
   ```

5. Run the candidate, using a unique dated label:

   ```sh
   python3 benchmark.py \
     --label new-model-YYYY-MM-DD \
     --url http://127.0.0.1:18180 \
     --model new-model
   ```

   Run the KAT baseline against the same unchanged protocol:

   ```sh
   sudo python3 benchmark.py \
     --label kat-YYYY-MM-DD \
     --url http://127.0.0.1:18080 \
     --model kat-coder-v2.5-dev-colibri \
     --env-file /opt/kat-coder-gateway/.env.production
   ```

   Keys are read inside the process and must never be included in reports or command arguments. The runner requires permission to use Docker; the current server uses `sudo -n docker`.

6. Check failures. Infrastructure failures must be resolved or reported separately. Never change a failing test to accommodate a model. If the runner was interrupted, `--only invoice_decimal`, `--only dependency_order`, or `--only async_cache` reruns just that task. Preserve discarded results and explain reruns.
7. Print the comparison (the directory should contain one subfolder per model and optionally `campaign.json`):

   ```sh
   python3 summarize.py runs/YYYY-MM-DD
   ```

8. Restore KAT and verify `/health`. Record results below the previous dated comparison in `results.md`, and retain the raw JSON, which includes every generated response. The runner also saves extracted source files under `results/` for inspection.

`campaign.py` is specific to our current server: it stops `kat-coder-gateway`, serves the configured candidates one at a time with a 32 GiB memory ceiling and no swap, then restores KAT. Review its model list and paths before a future campaign. Archive `campaign.json` and `results/` into a new dated run directory first; the runner refuses to overwrite them. The verified GGUF files and their `.verified.json` records stay in the working directory. Do not run two campaigns together. Forced termination or a host crash can bypass Python cleanup; always confirm KAT is active afterward.

## Reporting

Report test cases passed out of 30, complete tasks out of three, tool-loop success, median generation throughput, median time to first generated output, and observed peak process RSS. Keep startup/model loading separate. Keep any larger-budget retries visible.

For streamed responses, generation throughput is completion tokens divided by time after the first generated output; it is an approximate client measurement. Observed peak RSS is the process-tree sample during the initial campaign; a separate larger-budget retry is not included in that memory sample. Report one-pass results as a screening result. A small score difference is insufficient to claim one model is universally better.

Prefer a candidate only when its correctness, reliable tool use, latency, and RAM fit our actual coding workflow. A strong candidate should next be evaluated on real Django/React changes before replacing the default.
