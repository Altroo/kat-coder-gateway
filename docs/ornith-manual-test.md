# Ornith manual test — 2026-10-08

At the user's request, Ornith 1.5 35B-A3B replaces KAT on the private OpenCode endpoint for hands-on testing. KAT's weights and service configuration remain installed; its service is stopped and disabled. No PR or production Git push was made.

## Active configuration

- Service: `ornith-gateway.service`, enabled at boot; Docker container `ornith-gateway`.
- Runtime: pinned llama.cpp CPU image in [the service unit](../deploy/ornith-gateway.service). This does not run Ornith through Colibri.
- Weights: the already verified official `Ornith-1.5-35B-Q4_K_M.gguf`; no second copy or new download.
- Model ID: `ornith-1.5-35b-a3b`.
- Endpoint: `http://127.0.0.1:18080/v1`, reached remotely through the existing SSH launcher.
- Authentication: existing private gateway identity, mounted from `/etc/ornith-gateway/api-key` with root-only permissions. No credential is stored in this repository.
- Context: **65,536 tokens**. OpenCode response allowance: **32,768 tokens**, including reasoning and final output.
- Thinking: on, preserved across tool turns; no unsupported reasoning-effort level.
- Temperature 0.6, top-p 0.95, top-k 20, min-p 0.0; author's pinned chat template.
- CPU: eight threads, one request slot; 44 GiB container limit with no swap.
- OpenCode: default model and `deep` agent both use Ornith; one-hour request timeout, fifteen-minute header timeout, two-minute streamed-chunk timeout.

Launch `opencode` normally in the project directory. Start a new session, or select `local-ai/ornith-1.5-35b-a3b` if an existing session remembers KAT. The displayed name is **Ornith 1.5 35B (thinking)**.

## Verification

The endpoint passed health and authentication checks: `/health` returned OK, authenticated `/v1/models` listed Ornith, and unauthenticated model access returned 401. A real OpenCode session through the normal SSH launcher called the `read` tool on an isolated fixture and returned `ORNITH_GATEWAY_OK`, exiting successfully without an error event. The server's actual request parameters showed `max_tokens: 32768`, `n_predict: 32768`, reasoning format `deepseek`, and an open `<think>` marker. KAT was inactive and Ornith active. A direct streaming check also emitted nonempty reasoning, returned the correct answer, and ended with `finish_reason: stop` plus `[DONE]`. See the [activation record](../benchmark/runs/2026-10-07-ornith/manual-activation.json).

## Restore KAT when requested

On the server:

```sh
sudo systemctl disable --now ornith-gateway
sudo systemctl enable --now kat-coder-gateway
```

Restore or merge the workstation model entries from the private backup `~/.config/opencode/opencode.jsonc.before-ornith-20261008T103128`, preserving any newer user changes. Then verify KAT health and an authenticated completion. The services conflict so they do not intentionally run together on the same endpoint.

Ornith's active weight file remains under `/var/www/colibri-benchmarks/ornith-2026-10-07`. Do not delete that file as benchmark cleanup while the service uses it. The earlier benchmark results remain unchanged; activating Ornith for this trial is a user choice, not a change to the recorded scores.
