#!/bin/sh
# Start the gateway from private production environment values.
set -eu

install_dir=${KAT_GATEWAY_INSTALL_DIR:-/opt/kat-coder-gateway}
env_file=${KAT_GATEWAY_ENV_FILE:-$install_dir/.env.production}
if [ -r "$env_file" ]; then
    set -a
    . "$env_file"
    set +a
fi

: "${KAT_GATEWAY_INSTALL_DIR:?missing KAT_GATEWAY_INSTALL_DIR}"
: "${KAT_GATEWAY_MODEL_DIR:?missing KAT_GATEWAY_MODEL_DIR}"
: "${KAT_GATEWAY_HOST:?missing KAT_GATEWAY_HOST}"
: "${KAT_GATEWAY_PORT:?missing KAT_GATEWAY_PORT}"
: "${KAT_GATEWAY_MODEL_ID:?missing KAT_GATEWAY_MODEL_ID}"
: "${KAT_GATEWAY_CONTEXT:?missing KAT_GATEWAY_CONTEXT}"
: "${KAT_GATEWAY_MAX_OUTPUT:?missing KAT_GATEWAY_MAX_OUTPUT}"
: "${KAT_GATEWAY_RAM_GB:?missing KAT_GATEWAY_RAM_GB}"
: "${KAT_GATEWAY_THREADS:?missing KAT_GATEWAY_THREADS}"
: "${KAT_GATEWAY_MAX_QUEUE:?missing KAT_GATEWAY_MAX_QUEUE}"
: "${KAT_GATEWAY_KV_SLOTS:?missing KAT_GATEWAY_KV_SLOTS}"

export OMP_NUM_THREADS="$KAT_GATEWAY_THREADS"
export OMP_PROC_BIND=close
export OMP_PLACES=cores
export COLI_THINK=0
if [ -n "${KAT_GATEWAY_API_KEY:-}" ]; then
    export COLI_API_KEY="$KAT_GATEWAY_API_KEY"
fi

cd "$KAT_GATEWAY_INSTALL_DIR"
set -- serve \
    --model "$KAT_GATEWAY_MODEL_DIR" \
    --host "$KAT_GATEWAY_HOST" \
    --port "$KAT_GATEWAY_PORT" \
    --model-id "$KAT_GATEWAY_MODEL_ID" \
    --ctx "$KAT_GATEWAY_CONTEXT" \
    --ngen "$KAT_GATEWAY_MAX_OUTPUT" \
    --ram "$KAT_GATEWAY_RAM_GB" \
    --auto-tier \
    --gpu none \
    --no-think \
    --temp 0 \
    --max-queue "$KAT_GATEWAY_MAX_QUEUE" \
    --kv-slots "$KAT_GATEWAY_KV_SLOTS"

exec "$KAT_GATEWAY_INSTALL_DIR/c/coli" "$@"
