#!/bin/sh
# Open the private workstation-to-server tunnel.
set -eu

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
env_file=${KAT_GATEWAY_ENV_FILE:-$script_dir/../.env.production}

if [ ! -r "$env_file" ]; then
    echo "Missing $env_file. Copy .env.example to .env.production and edit it." >&2
    exit 1
fi

set -a
. "$env_file"
set +a

: "${KAT_GATEWAY_LOCAL_PORT:?missing KAT_GATEWAY_LOCAL_PORT}"
: "${KAT_GATEWAY_REMOTE_PORT:?missing KAT_GATEWAY_REMOTE_PORT}"
: "${KAT_GATEWAY_SSH_HOST:?missing KAT_GATEWAY_SSH_HOST}"
: "${KAT_GATEWAY_SSH_USER:?missing KAT_GATEWAY_SSH_USER}"
: "${KAT_GATEWAY_SSH_KEY:?missing KAT_GATEWAY_SSH_KEY}"

exec ssh -N \
    -o ExitOnForwardFailure=yes \
    -o ServerAliveInterval=30 \
    -o ServerAliveCountMax=3 \
    -L "$KAT_GATEWAY_LOCAL_PORT:127.0.0.1:$KAT_GATEWAY_REMOTE_PORT" \
    -i "$KAT_GATEWAY_SSH_KEY" \
    "$KAT_GATEWAY_SSH_USER@$KAT_GATEWAY_SSH_HOST"
