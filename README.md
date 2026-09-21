# KAT-Coder Gateway

KAT-Coder Gateway runs KAT-Coder V2.5 Dev on CPU through Colibri and exposes
an OpenAI-compatible API with tool calling. It is designed for coding clients
such as OpenCode that need the model to read files, edit code, run commands,
and continue after receiving tool results.

The model and project data stay on your own server. Model weights are not
included in this repository.

## What this project adds

- Native tool declarations for Colibri's Qwen3.6 engine
- Structured OpenAI `tool_calls` responses
- Support for `auto`, `none`, `required`, and named tool choices
- Multiple tool calls and consecutive tool results
- Typed string, number, boolean, object, and array arguments
- Stable call IDs
- Strict rejection of undeclared tools and invalid typed arguments
- Streaming tool-call responses
- OpenCode v2 configuration with accurate context limits
- A private, persistent systemd service for a CPU server

## Tested configuration

- Model: KAT-Coder V2.5 Dev, Colibri int4 gs64
- Runtime: Colibri v1.12.0 Qwen3.6 engine
- Context window: 65,536 tokens
- Maximum output: 8,192 tokens
- Inference: CPU only, eight physical threads
- Concurrency: one request and one KV slot
- API bind: `127.0.0.1:18080`

The model supports a larger theoretical context. This project uses 64K as a
practical ceiling for longer coding sessions while retaining RAM for the other
applications on the CPU server. Very large uncached prompts remain slower than
short incremental turns.

## Install on the server

Create a dedicated service account, then clone the repository to a conventional
private runtime path. Replace `YOUR_ACCOUNT` with the GitHub account or
organization that hosts your fork.

```sh
sudo useradd --system --home /opt/kat-coder-gateway \
  --shell /usr/sbin/nologin kat-coder
sudo git clone https://github.com/YOUR_ACCOUNT/kat-coder-gateway.git \
  /opt/kat-coder-gateway
sudo chown -R kat-coder:kat-coder /opt/kat-coder-gateway
```

Place the converted model at:

```text
/opt/kat-coder-models/KAT-Coder-V2.5-Dev-colibri-i4-gs64
```

Create the private production configuration from the committed example. Never
commit `.env.production`.

```sh
cd /opt/kat-coder-gateway
sudo -u kat-coder cp .env.example .env.production
sudo chmod 600 .env.production
sudoedit .env.production
```

Set `KAT_GATEWAY_API_KEY` to a strong random value. Keep the same value in the
workstation's private `.env.production` so OpenCode can authenticate.

Build the Qwen3.6 engine:

```sh
cd /opt/kat-coder-gateway
sudo -u kat-coder make -C c qwen36 ARCH=native
```

Install [deploy/kat-coder-gateway.service](deploy/kat-coder-gateway.service)
as `/etc/systemd/system/kat-coder-gateway.service`, then enable it:

```sh
sudo cp deploy/kat-coder-gateway.service \
  /etc/systemd/system/kat-coder-gateway.service
sudo systemctl daemon-reload
sudo systemctl enable --now kat-coder-gateway.service
```

Check the private endpoint on the server:

```sh
set -a
. ./.env.production
set +a
curl http://127.0.0.1:18080/health
curl -H "Authorization: Bearer $KAT_GATEWAY_API_KEY" \
  http://127.0.0.1:18080/v1/models
```

## Connect from a workstation

Copy `.env.example` to `.env.production` in your local gateway checkout and set
the SSH values. Never commit `.env.production`.

```sh
cp .env.example .env.production
chmod 600 .env.production
editor .env.production
```

The launcher opens the SSH tunnel automatically. You do not need to keep a
second terminal open.

Install one local command by linking the launcher into a directory on `PATH`:

```sh
mkdir -p "$HOME/.local/bin"
ln -s /path/to/kat-coder-gateway/scripts/start_opencode.sh \
  "$HOME/.local/bin/opencode"
```

Add this line to `~/.zshrc` if `~/.local/bin` is not already on `PATH`:

```sh
export PATH="$HOME/.local/bin:$PATH"
```

The private OpenAI-compatible endpoint is available through the temporary
tunnel at:

```text
http://127.0.0.1:18080/v1
```

You can still open the tunnel manually for API testing:

```sh
./scripts/open_tunnel.sh
set -a
. /path/to/kat-coder-gateway/.env.production
set +a
curl -H "Authorization: Bearer $KAT_GATEWAY_API_KEY" \
  http://127.0.0.1:18080/v1/models
```

## Use with OpenCode v2

Install OpenCode v2 on macOS:

```sh
brew install anomalyco/tap/opencode-v2
```

Install [deploy/opencode.jsonc.example](deploy/opencode.jsonc.example) as the
global OpenCode configuration:

```sh
mkdir -p "$HOME/.config/opencode"
cp /path/to/kat-coder-gateway/deploy/opencode.jsonc.example \
  "$HOME/.config/opencode/opencode.jsonc"
```

Start OpenCode inside the Git repository it should edit:

```sh
cd /path/to/your-project
opencode
```

That is the complete daily workflow. The command loads the private credentials,
opens the SSH tunnel, starts an isolated OpenCode session, and closes its tunnel
when OpenCode exits. File tools are confined to the directory where the command
was started and its Git worktree. External directories and private environment
files are denied. `git push` requires confirmation.

The configured model appears as
`local-ai/kat-coder-v2.5-dev-colibri`. Use `/models` in OpenCode if you need to
select it manually.

The default `build` and `research` agents use a fast profile with thinking off
and a 1,024-token response ceiling. They answer broad explanation and teaching
requests in chat with a compact overview of at most 300 words, and do not create
files unless the user explicitly asks for file changes. This avoids turning a
broad question into a long generated document.

Switch to the primary `deep` agent for difficult debugging, architecture, or
multi-step implementation work that benefits from thinking mode. The deep
profile keeps the 8,192-token ceiling. In the terminal, use:

```sh
opencode run --agent deep "diagnose this difficult issue"
```

KAT-Coder supports thinking on or off, but its Qwen3.6 template does not have a
reliable graded high, medium, or low thinking budget. Deep mode can therefore
take several minutes on CPU if the model reasons at length.

The OpenCode provider allows ten minutes for a complete request, five minutes
for response headers, and two minutes between streamed chunks. These explicit
timeouts prevent a healthy CPU inference from being cancelled near one minute
and retried without its final `finish_reason` event. The gateway sends keepalive
chunks during prompt processing, so a stalled connection still fails instead of
waiting silently for the full request timeout.

Automatic AI-generated session titles are disabled because they otherwise launch
a second model request beside the first coding turn. Sessions keep OpenCode's
default timestamp title, leaving the single inference slot available for work.

The build agent uses a compact system prompt suited to the local CPU model. It
keeps the normal inspect, edit, verify, safety, and task-completion rules without
making every new session prefill OpenCode's much larger generic coding prompt.
For broad learning requests it starts with a concise overview and offers to
expand one topic instead of generating a complete course.

The default `build` agent omits web tool schemas for lower latency. Switch to
the primary `research` agent in OpenCode when you need web search or page
fetching, then switch back to `build` for the leanest coding loop. From the
terminal, `opencode run --agent research "your question"` selects it directly.

The example configuration keeps read, edit, and shell as the minimal coding
tool set. Search, listing, testing, and Git remain available through shell
commands without sending separate tool schemas on every request. Optional
browser, language-server, todo, question, skill, and subagent tools stay off to
reduce cold prompt processing on CPU. Web access is isolated in the `research`
agent so it is available without slowing the default coding agent. Shell
commands run with your macOS user account, but OpenCode asks before crossing the
active project boundary and the supplied policy denies that access.

## Call the API directly

```sh
curl http://127.0.0.1:18080/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -H "Authorization: Bearer $KAT_GATEWAY_API_KEY" \
  -d '{
    "model": "kat-coder-v2.5-dev-colibri",
    "messages": [{"role": "user", "content": "Explain JavaScript void clearly."}],
    "temperature": 0,
    "max_tokens": 2048
  }'
```

## Verify tool calling

Run the unit tests:

```sh
cd c
python3 -m unittest tests.test_openai_server tests.test_family_registry
```

Run the real two-turn tool loop against a running gateway:

```sh
cd c
set -a
. ../.env.production
set +a
python3 tools/try_tool_calling.py \
  --url http://127.0.0.1:18080 \
  --tool-choice required \
  --raw
```

The live probe passes only when KAT emits a valid structured call, receives the
tool result, and uses that result in its final response.

See [docs/deployment.md](docs/deployment.md) for deployment details.
It also documents the optional bare Git remote and rollback-capable deployment
hook used for repeatable production updates.

## Upstream and license

KAT-Coder Gateway is based on
[JustVugg/colibri](https://github.com/JustVugg/colibri). The original project
documentation is preserved in
[UPSTREAM_COLIBRI_README.md](UPSTREAM_COLIBRI_README.md).

This repository retains the upstream Apache-2.0 license.
