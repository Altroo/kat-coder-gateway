# Deployment

KAT-Coder on Colibri was restored on 2026-10-13. The Ornith trial ended and its weights, service and unused runtime image were removed. The [retired Ornith trial record](ornith-manual-test.md) preserves the historical context.

This fork adds native OpenAI-compatible tool calling for KAT-Coder V2.5 Dev
on Colibri's Qwen3.6 engine. The service stays bound to server loopback and is
reached from a workstation through an SSH tunnel.

## Runtime limits

- Context window: 65,536 tokens
- Maximum generated output: 8,192 tokens
- One request and one KV slot at a time
- CPU only, eight physical inference threads
- OpenCode requests thinking mode; direct API requests without an override retain the deterministic, non-thinking fallback

The model supports a larger theoretical context, but 64K is the practical
ceiling for this CPU server. It leaves RAM for the hosted applications while
giving longer coding sessions room before compaction. Large uncached prompts
remain expensive on CPU.

## Server service

Create `.env.production` from `.env.example`, replace every placeholder, and
restrict it to the service account. Install `deploy/kat-coder-gateway.service`
as:

```text
/etc/systemd/system/kat-coder-gateway.service
```

The endpoint is intentionally private:

```text
http://127.0.0.1:18080/v1
```

## Workstation tunnel

Set the SSH values in the workstation's private `.env.production`. The normal
`opencode` launcher creates and removes the tunnel automatically. Use the
manual helper only when testing the API without OpenCode:

```sh
./scripts/open_tunnel.sh
```

Then verify the endpoint:

```sh
set -a
. ./.env.production
set +a
curl -H "Authorization: Bearer $KAT_GATEWAY_API_KEY" \
  http://127.0.0.1:18080/v1/models
```

## OpenCode v2

Install the current OpenCode v2 CLI on macOS:

```sh
brew install anomalyco/tap/opencode-v2
```

Copy `deploy/opencode.jsonc.example` to the global OpenCode configuration at
`~/.config/opencode/opencode.jsonc`. Link `scripts/start_opencode.sh` to
`~/.local/bin/opencode`, then put `~/.local/bin` before the Homebrew path.
Running `opencode` from a project directory loads the private API key, opens the
SSH tunnel, and closes the tunnel when OpenCode exits.

The example uses a lean tool profile for CPU inference. The default `build` and
`research` agents enable thinking and cap each response at 8,192 tokens,
including reasoning. They answer broad teaching and explanation requests in
chat with at most 300 words, and create files only when the user explicitly
requests file changes. The `deep` agent uses the same model profile with a
prompt focused on difficult work. External directories and private environment
files are denied, and `git push` requires confirmation.

The provider settings use a ten-minute request timeout, a five-minute header
timeout, and a two-minute streamed-chunk timeout. This accommodates CPU prompt
processing while still detecting a stalled stream. Keep these values explicit
because a client-side cancellation closes the gateway stream before its final
`finish_reason` event and causes OpenCode to retry the completed text.

## Verification

Run the existing real two-turn tool loop against the server:

```sh
cd /opt/kat-coder-gateway/c
set -a
. ../.env.production
set +a
python3 tools/try_tool_calling.py \
  --url http://127.0.0.1:18080 \
  --tool-choice required \
  --raw
```

The probe passes only when KAT declares a valid call, receives the tool result,
and uses that result in its final answer.

## Production Git remote

The optional `deploy/post-receive.sh` hook supports deployment from a bare Git
repository. Install it as `hooks/post-receive` in that repository and create a
private sibling file named `hooks/deploy.env`:

```sh
KAT_DEPLOY_GIT_DIR=/path/to/kat-coder-gateway.git
KAT_DEPLOY_TARGET=/path/to/checked-out/kat-coder-gateway
KAT_DEPLOY_ACTIVE_LINK=/opt/kat-coder-gateway
KAT_DEPLOY_SERVICE=kat-coder-gateway.service
KAT_DEPLOY_HEALTH_URL=http://127.0.0.1:18080/health
KAT_DEPLOY_BRANCH=main
```

Keep `deploy.env` on the server. Do not commit it. The hook archives the exact
pushed commit into a unique directory under `${KAT_DEPLOY_TARGET}-releases`.
It builds there without modifying the previous checkout, then atomically
replaces the active symlink. The service path must be a symlink, not a real
directory. Linux `flock -n` rejects overlapping deployments; it does not queue
them. Git has already accepted the push when a post-receive hook fails, so a
rejected deployment must be retried after the active deployment finishes.
An ordinary repeat push of the same commit is a no-op and will not rerun the
hook. An operator must rerun the hook with the intended revision or push a new
commit. Health probes have explicit connection and total timeouts.

Before installing the updated hook, verify Linux `flock`, GNU `readlink`, and
GNU `mv` are available. The deploy account must be able to create release
directories and use noninteractive sudo for the hook's scoped `ln`, `mv`, and
`rm` operations and service `restart`/`stop`. An older policy that permits only
`ln` and `restart` is not sufficient. Review the exact server paths and sudo
policy before deployment; the local tests do not verify real permissions.

The private configuration remains outside the release. By default it is read
from `$KAT_DEPLOY_TARGET/.env.production`; optionally set
`KAT_DEPLOY_RUNTIME_ENV` to another private configuration file. Its real path
is resolved before switching releases, and each release links to that same
file without copying or changing its permissions. The service's systemd
`EnvironmentFile` follows this link. Keep the config path and parent
directories accessible as required by systemd and the service account. The
deploy account only needs to resolve and stat the config path, not read the
secrets: systemd reads its `EnvironmentFile` before dropping privileges.

If restart or health validation fails, the hook restores the untouched previous
release and restarts it. A failed first deployment removes its new active link
and stops the service. Failed release directories remain for diagnosis; no
automatic pruning deletes older releases. A build failure leaves the active
release and service unchanged. Updating this hook and deploying it to the
server are separate operational steps. Coordinate deployment with other
long-running workloads: the build and service restart share server resources.

Test the hook locally without sudo, systemd, network access, or a real build:

```sh
cd c
python3 -m unittest -v tests.test_gateway_deploy
```
