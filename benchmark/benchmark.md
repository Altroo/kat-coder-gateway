# Coding model benchmark

Original screening protocol: **2026-10-07.v1**. Larger-output screening: **2026-10-07.v2-fast**. Framework repair protocol: **2026-10-07.repo-v1**. This is a small, repeatable screening test for our self-hosted programming assistant. It does not replace a real repository benchmark.

**Default for future evaluations: thinking enabled.** Use the full thinking comparison command at the end of this document. The original thinking-off instructions are retained only to reproduce historical measurements; do not use them for the current recommendation.

## Files

- `benchmark.py`: exact prompts, test cases, streaming client, and isolated code execution.
- `selftest.py`: reference implementations used to check that the test harness works.
- `recheck.py`: reruns tests on saved output without generating or repairing code.
- `summarize.py`: prints a results table from raw JSON without overwriting past results.
- `campaign.py`: sequential runner for our server; restores the KAT service in `finally`.
- `repository_benchmark.py` and `repo_fixtures/`: bounded file-editing tool loop and isolated Django/React projects.
- `compare_candidate.py`: fresh KAT/candidate comparison; `restore_kat.py` is its systemd restoration fallback.
- `candidate_budget_probe.py`: one separate larger-budget attempt for truncated candidate functions.
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

## Historical v1 generation settings

- Temperature `0`, top-p `1`, thinking disabled.
- Initial coding output ceiling: **1,024 tokens**. If and only if `finish_reason` is `length`, regenerate the unchanged prompt with **2,048 tokens**. Preserve the initial truncated attempt; do not call it a logic failure. If the larger attempt is also truncated, record an incomplete answer, give no passing credit for unexecuted tests, and keep it separate from observed assertion failures.
- Tool call: at most 256 tokens; final tool-result answer: at most 128 tokens.
- Eight CPU threads and one active model request at a time.
- Warm up each model with the identical short prompt `Reply only OK.` before scoring.
- Use each model's own chat template and inspect a rendered prompt before scoring. If a packaged template is malformed, use the author's canonical template, pin its revision and SHA-256, save before/after prompt evidence, and invalidate the affected scores. Do not substitute an unrelated template simply to improve a score.
- A stream missing its terminal `finish_reason` is a serving failure, not a successful answer.

Our first comparison uses KAT's production Colibri configuration with a 65,536-token capacity and llama.cpp with an 8,192-token capacity for GGUF candidates. Actual test prompts fit both. Runtimes and quantizations differ: the results compare usable deployment configurations, not model weights in isolation.

## Historical v1 reproduction

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

## Historical v1 reporting

Report test cases passed out of 30, complete tasks out of three, tool-loop success, median generation throughput, median time to first generated output, and observed peak process RSS. Keep startup/model loading separate. Keep any larger-budget retries visible.

For streamed responses, generation throughput is completion tokens divided by time after the first generated output; it is an approximate client measurement. Observed peak RSS is the process-tree sample during the initial campaign; a separate larger-budget retry is not included in that memory sample. Report one-pass results as a screening result. A small score difference is insufficient to claim one model is universally better.

Prefer a candidate only when its correctness, reliable tool use, latency, and RAM fit our actual coding workflow. A strong candidate should next be evaluated on real Django/React changes before replacing the default.

## Larger-output comparison and framework repairs

The Ornith comparison adds two protocols without replacing or rescoring the original results:

- `2026-10-07.v2-fast`: the same three function contracts and tests, with **4,096 output tokens from the first attempt**. Both KAT and the candidate are rerun at that ceiling; no automatic repair feedback is given on these function tasks. Do not mix these scores with the original 1,024/2,048-token screening table.
- `2026-10-07.repo-v1`: two small, purpose-built framework projects with ten integration checks each. These use actual Django/DRF and React/React DOM, but are synthetic fixtures rather than edits to production repositories or a SWE-bench evaluation.

The Django task repairs tenant isolation across list/retrieve/update/delete, assigns the authenticated user's company on creation, blocks ownership transfer, and fails closed when company context is missing. The React task fixes stale request results/errors/loading states, query clearing, loader changes, and abort handling while preserving the component UI.

Models receive the same issue descriptions and readable-file list. Tools can read listed files, replace only allowed source files, and run the fixed integration checks. Each task allows eight model turns, up to 4,096 output tokens per turn, 12,000 completion tokens total, and at most three requested test runs; the evaluator then grades the final files. Temperature is zero and thinking is disabled for both models. A valid tool call and test feedback are part of the assessment. Generated code is executed only in disposable, unprivileged containers without network access or host secrets, with a 512 MiB memory limit, one CPU and a 45-second deadline. Only the test file is mounted; reference fixes are not exposed.

Before model evaluation, `repository_benchmark.py --selftest` must show that the original buggy fixtures fail and the reference patches pass all 20 checks. Exact test image identities are retained in `repo-images.json`; the React dependency lockfile is committed.

Run a comparison in a **new server working directory**, containing copies of the runner files and `repo_fixtures/`, a verified candidate GGUF, its `.verified.json` manifest, and `repo-images.json`. Run the reference self-check, then launch:

```sh
sudo python3 compare_candidate.py --candidate ornith --verified ornith.verified.json --legacy-fast
```

The verified manifest must contain `file`, `size_bytes`, `sha256`, `revision`, `repo`, and `verified: true`. The comparison uses the pinned llama.cpp image, 16K candidate context, eight CPU threads, one slot, a 36 GiB memory ceiling and no swap. KAT uses its existing production runtime configuration. Models run sequentially and KAT is restored in `finally`; the server's systemd job also uses a 45-minute runtime limit and `restore_kat.py` as `ExecStopPost`.

Preserve both `report.json` (30 function checks and the basic tool probe) and `repo-report.json` (20 framework checks, all model/tool turns, final source files, and timings). Report the two scores separately. These historical thinking-off scores do not assess reasoning-enabled performance. The current recommendation uses the thinking-enabled comparison below.

## Reasoning-mode supplement

`2026-10-07.v2-thinking` reruns the three unchanged function tasks on both models with thinking enabled, temperature zero, and a 4,096-token total output ceiling including reasoning. It is recorded separately from the fast-mode results. The small tool probe is skipped because its 256/128-token budgets were designed for non-thinking output; a skipped probe is displayed as untested, not failed. The Django/React repair results above remain fast-mode measurements.

After the fast comparison has completed and restored KAT, launch the separate phase from the same working directory:

```sh
sudo python3 compare_candidate.py --candidate ornith --verified ornith.verified.json --reasoning-only
```

It uses new `kat-reasoning` and `ornith-reasoning` result labels, writes `reasoning-campaign.json`, and refuses to overwrite prior results. The server phase has a 30-minute systemd runtime limit and the same restoration fallback. Check that reasoning was actually emitted before interpreting the results; token-limited outputs remain classified as incomplete.

## Corrected full thinking comparison

Use **`2026-10-07.v3-thinking`** and **`2026-10-07.repo-v2-thinking`** for the current recommendation. Both models receive `enable_thinking: true`; KAT also receives `reasoning_effort: high`, while Ornith omits the unsupported effort parameter. Both use temperature **1.0**, top-p **0.95**, and an **8,192-token** response ceiling including reasoning and final output. Temperature/top-p match the shared coding-benchmark settings published by both authors; this is still our small one-pass deployment comparison, not a reproduction of their leaderboards. Samplers and quantizations differ between runtimes.

The function contracts and test cases are unchanged. The tiny 256/128-token tool probe is skipped; the two framework tasks provide the tool-use assessment. Each repair allows eight model turns, 8,192 tokens per turn, 24,576 completion tokens across the task, and three model-requested test runs plus the evaluator's final grade. Reasoning content is returned to the model between tool turns. Report token-limit and turn-limit outcomes separately from observed code failures.

`high` matches the KAT OpenCode deep-profile request. The benchmark checks runtime capabilities and omits the effort parameter for Ornith, whose runtime explicitly declares it unsupported. It is **not a distinct model-native effort level for these templates**: the deployed KAT Qwen renderer accepts the parameter but uses only thinking on/off; Ornith's canonical template likewise branches on `enable_thinking` and does not read `reasoning_effort`. Ornith's runtime reports `supports_reasoning_effort: false`. There is no additional reasoning-token sub-budget; the overall response ceiling still applies. Verify nonempty reasoning in saved responses rather than assuming the requested flag took effect.

The official Ornith Q4_K_M GGUF includes a modified embedded template. An initial reading of escaped `/props` output incorrectly suggested malformed newlines; byte inspection of `embedded-template-probe.json` shows six actual newlines and zero literal backslash-n sequences. No template defect was established. The preliminary reasoning phase was interrupted during that investigation and is not a completed comparison. This full thinking phase pins the author's canonical `chat_template.jinja` in `template-manifest.json`; the weights remain unchanged. The runner saves `/props` and asserts correct rendered ChatML separators and the open thinking marker before scoring Ornith. `assessment.json` records this correction and the status of earlier measurements.

```sh
sudo python3 compare_candidate.py --candidate ornith --verified ornith.verified.json --thinking-full
```

This phase uses `kat-thinking` and `ornith-thinking`, with separate `thinking-campaign.json`. It requires `template-manifest.json` and the hash-matching template file in the working directory. Ornith receives 32K context and a 40 GiB cgroup memory ceiling with no swap, eight CPU threads and one slot. KAT uses the existing 64K Colibri service. Both run sequentially. The systemd job restores KAT on exit; always verify its health afterward. Preserve all raw outputs, runtime metadata and the final files produced by each model.

Official sources: [Ornith model card](https://huggingface.co/ornith-ai/Ornith-1.5-35B-A3B), [Ornith canonical template](https://huggingface.co/ornith-ai/Ornith-1.5-35B-A3B/blob/10fbf86fed7ecee4a061f8b499a618f46001cac1/chat_template.jinja), [KAT model card](https://huggingface.co/Kwaipilot/KAT-Coder-V2.5-Dev). Do not label the original thinking-off measurements as normal thinking-enabled OpenCode use.

### Resuming an interrupted function phase

Use the same directory and append `--resume` to the full thinking command. The runner verifies the original model/template identities and all campaign settings, archives the paused campaign metadata, preserves every completed function answer (including failures), and generates only missing tasks. A missing task interrupted by a user pause restarts from its unchanged prompt; the discarded partial generation is not a scored attempt. Completed framework reports are retained. An unfinished framework conversation requires restoring its saved tool history; the runner refuses to silently replace it.

On 2026-10-08, KAT's invoice and dependency answers were retained byte-for-byte at task-object level; only the interrupted cache generation was restarted. The checkpoint stores their hashes. Peak RSS spans both active segments. Aggregate campaign seconds include interrupted generation time, so compare model latency using completed per-task timings and report the pause separately.

### Larger-budget diagnostic for truncated functions

`candidate_budget_probe.py --candidate ornith --verified ornith.verified.json` runs only after the full comparison is complete. It gives each candidate function response that ended with `finish_reason: length` one fresh attempt at **16,384 output tokens**, using the same prompt, thinking mode, temperature 1.0 and top-p 0.95, without test feedback. Completed logical failures are not retried. Original answers and the 8K comparison remain unchanged; the probe uses a separate label and `budget-probe.json`. Report its scores and extra time separately. KAT's three function answers all finished below 8K, so they are retained rather than regenerated. This is an output-budget diagnostic, not a second equal-budget leaderboard. It does not change framework-task budgets.

The probe uses the same pinned candidate runtime, weights, template, 32K context, CPU limits and restoration safeguards. A response still truncated at 16K remains incomplete; do not keep increasing budgets without a new evaluation decision. The summarizer displays the actual number of selected checks so a one-task diagnostic appears as `/10`, not `/30`.

### Thinking-mode timing

For the full thinking comparison, report **end-to-end completion throughput**: completion tokens, including reasoning, divided by total request seconds. The deployed Colibri Qwen reasoning splitter defers reasoning chunks until it can separate thinking from the final answer. Therefore, subtracting first-visible-output latency and dividing *all* completion tokens by the remaining interval produces an inflated apparent generation rate for KAT. The summarizer now displays the end-to-end measure, retains the older post-first-output calculation as a separate JSON field for historical inspection, and labels first-output latency as client-observed. Earlier published thinking-off tables retain their original throughput definition. Total task times and scores are unaffected by this reporting correction.


### Comparing tuned models later

Keep this evaluation set separate from training data. Fine-tuning examples should contain independently verified solutions and, for agent tasks, valid file edits and tool interactions. Evaluate the exported/quantized model as actually served, not only its training checkpoint. Before promoting a model, repeat a broader set of held-out tasks across several samples and compare correctness, completion rate, total tokens, wall time, and memory. A fresh retry at temperature 1.0 can be shorter or better even when it never uses the extra token allowance; a successful larger-budget retry alone does not prove the increased ceiling caused the improvement.
