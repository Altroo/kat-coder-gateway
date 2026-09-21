#!/bin/sh
# Load private client values before starting OpenCode.
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

exec opencode "$@"
