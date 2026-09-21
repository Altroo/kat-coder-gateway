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
- Context window: 32,768 tokens
- Maximum output: 8,192 tokens
- Inference: CPU only, eight physical threads
- Concurrency: one request and one KV slot
- API bind: `127.0.0.1:18080`

The model supports a larger theoretical context. This project starts at 32K
because it provides useful coding context without consuming unnecessary RAM or
making CPU prompt processing excessively slow.

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

The example configuration keeps the core file, search, shell, edit, write, and
question tools. It disables optional browser, web, skill, subagent, and code
mode tools to reduce cold prompt processing on CPU. Remove a `false` entry from
the `tools` object if you need that capability. Shell commands run with your
macOS user account, but OpenCode asks before crossing the active project
boundary and the supplied policy denies that access.

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
