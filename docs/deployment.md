# Deployment

This fork adds native OpenAI-compatible tool calling for KAT-Coder V2.5 Dev
on Colibri's Qwen3.6 engine. The service stays bound to server loopback and is
reached from a workstation through an SSH tunnel.

## Runtime limits

- Context window: 32,768 tokens
- Maximum generated output: 8,192 tokens
- One request and one KV slot at a time
- CPU only, eight physical inference threads
- Deterministic, non-thinking generation by default

The model supports a larger theoretical context, but 32K is the practical
starting point for this CPU server. It leaves RAM for the hosted applications
and avoids turning long prompt prefill into an unusable wait.

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

Set the SSH values in the workstation's private `.env.production`, then keep
this running in a terminal:

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

Copy `deploy/opencode.jsonc.example` to either the repository being edited or
the global OpenCode configuration at `~/.config/opencode/opencode.jsonc`. Use
`scripts/start_opencode.sh` so the private API key and base URL are loaded from
`.env.production` before OpenCode starts.

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

Keep `deploy.env` on the server. Do not commit it. The hook checks out the new
revision and builds the native engine before changing the active service link.
If the restart or health check fails, it restores the previous link.
