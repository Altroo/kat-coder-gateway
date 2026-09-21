#!/bin/sh
# Start OpenCode with the private KAT gateway and manage its SSH tunnel.
set -eu

resolve_script() {
    target=$1
    while [ -L "$target" ]; do
        target_dir=$(CDPATH= cd -- "$(dirname -- "$target")" && pwd)
        target=$(readlink "$target")
        case "$target" in
            /*) ;;
            *) target=$target_dir/$target ;;
        esac
    done
    CDPATH= cd -- "$(dirname -- "$target")" && pwd
}

script_dir=$(resolve_script "$0")
gateway_home=${KAT_GATEWAY_HOME:-$script_dir/..}
env_file=${KAT_GATEWAY_ENV_FILE:-$gateway_home/.env.production}

if [ ! -r "$env_file" ]; then
    echo "Missing private gateway configuration: $env_file" >&2
    echo "Copy .env.example to .env.production and edit it locally." >&2
    exit 1
fi

set -a
. "$env_file"
set +a

: "${KAT_GATEWAY_API_KEY:?missing KAT_GATEWAY_API_KEY}"
: "${KAT_GATEWAY_BASE_URL:?missing KAT_GATEWAY_BASE_URL}"
: "${KAT_GATEWAY_LOCAL_PORT:?missing KAT_GATEWAY_LOCAL_PORT}"
: "${KAT_GATEWAY_REMOTE_PORT:?missing KAT_GATEWAY_REMOTE_PORT}"
: "${KAT_GATEWAY_SSH_HOST:?missing KAT_GATEWAY_SSH_HOST}"
: "${KAT_GATEWAY_SSH_USER:?missing KAT_GATEWAY_SSH_USER}"
: "${KAT_GATEWAY_SSH_KEY:?missing KAT_GATEWAY_SSH_KEY}"

find_opencode() {
    if [ -n "${KAT_OPENCODE_BIN:-}" ] && [ -x "$KAT_OPENCODE_BIN" ]; then
        printf '%s\n' "$KAT_OPENCODE_BIN"
        return
    fi
    for candidate in \
        /opt/homebrew/bin/opencode \
        /usr/local/bin/opencode \
        /opt/local/bin/opencode
    do
        if [ -x "$candidate" ] && [ "$candidate" != "$0" ]; then
            printf '%s\n' "$candidate"
            return
        fi
    done
    echo "OpenCode is not installed. See README.md for installation instructions." >&2
    exit 1
}

gateway_ready() {
    curl -fsS --max-time 2 \
        -H "Authorization: Bearer $KAT_GATEWAY_API_KEY" \
        "$KAT_GATEWAY_BASE_URL/models" >/dev/null 2>&1
}

tunnel_pid=
cleanup() {
    if [ -n "$tunnel_pid" ] && kill -0 "$tunnel_pid" 2>/dev/null; then
        kill "$tunnel_pid" 2>/dev/null || true
        wait "$tunnel_pid" 2>/dev/null || true
    fi
}
trap cleanup EXIT HUP INT TERM

if ! gateway_ready; then
    echo "Connecting to the private KAT gateway..." >&2
    ssh -N \
        -o BatchMode=yes \
        -o ExitOnForwardFailure=yes \
        -o ServerAliveInterval=30 \
        -o ServerAliveCountMax=3 \
        -L "$KAT_GATEWAY_LOCAL_PORT:127.0.0.1:$KAT_GATEWAY_REMOTE_PORT" \
        -i "$KAT_GATEWAY_SSH_KEY" \
        "$KAT_GATEWAY_SSH_USER@$KAT_GATEWAY_SSH_HOST" &
    tunnel_pid=$!

    attempts=0
    while ! gateway_ready; do
        attempts=$((attempts + 1))
        if ! kill -0 "$tunnel_pid" 2>/dev/null; then
            wait "$tunnel_pid" 2>/dev/null || true
            echo "Could not open the private KAT gateway tunnel." >&2
            exit 1
        fi
        if [ "$attempts" -ge 20 ]; then
            echo "The KAT gateway did not become ready in time." >&2
            exit 1
        fi
        sleep 0.5
    done
fi

opencode_bin=$(find_opencode)

# Interactive sessions use a private OpenCode server so the gateway environment
# always belongs to this invocation. Other administrative subcommands do not
# need a private server.
case "${1:-}" in
    run|mini)
        subcommand=$1
        shift
        "$opencode_bin" "$subcommand" --standalone "$@"
        ;;
    ""|-*)
        "$opencode_bin" --standalone "$@"
        ;;
    *)
        "$opencode_bin" "$@"
        ;;
esac
