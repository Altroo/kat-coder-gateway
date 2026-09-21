#!/bin/sh
# Deploy main from a bare Git remote, build the native engine, then restart.
set -eu

hook_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
deploy_env=${KAT_GATEWAY_DEPLOY_ENV:-$hook_dir/deploy.env}

if [ ! -r "$deploy_env" ]; then
    echo "Missing private deployment configuration: $deploy_env" >&2
    exit 1
fi

set -a
. "$deploy_env"
set +a

: "${KAT_DEPLOY_GIT_DIR:?missing KAT_DEPLOY_GIT_DIR}"
: "${KAT_DEPLOY_TARGET:?missing KAT_DEPLOY_TARGET}"
: "${KAT_DEPLOY_ACTIVE_LINK:?missing KAT_DEPLOY_ACTIVE_LINK}"
: "${KAT_DEPLOY_SERVICE:?missing KAT_DEPLOY_SERVICE}"
: "${KAT_DEPLOY_HEALTH_URL:?missing KAT_DEPLOY_HEALTH_URL}"

branch=${KAT_DEPLOY_BRANCH:-main}
old_target=

rollback() {
    if [ -n "$old_target" ]; then
        echo "Deployment failed. Restoring the previous service target." >&2
        sudo ln -sfnT "$old_target" "$KAT_DEPLOY_ACTIVE_LINK"
        sudo systemctl restart "$KAT_DEPLOY_SERVICE" || true
    fi
}

while read -r _old_revision _new_revision ref_name; do
    [ "$ref_name" = "refs/heads/$branch" ] || continue

    echo "Deploying $branch to $KAT_DEPLOY_TARGET"
    mkdir -p "$KAT_DEPLOY_TARGET"
    git --work-tree="$KAT_DEPLOY_TARGET" --git-dir="$KAT_DEPLOY_GIT_DIR" \
        checkout -f "$branch"

    if [ ! -e "$KAT_DEPLOY_TARGET/.env.production" ]; then
        echo "Missing private runtime configuration in the deployment target." >&2
        exit 1
    fi

    make -C "$KAT_DEPLOY_TARGET/c" qwen36 ARCH=native

    if [ -L "$KAT_DEPLOY_ACTIVE_LINK" ]; then
        old_target=$(readlink "$KAT_DEPLOY_ACTIVE_LINK")
    fi

    trap rollback EXIT HUP INT TERM
    sudo ln -sfnT "$KAT_DEPLOY_TARGET" "$KAT_DEPLOY_ACTIVE_LINK"
    sudo systemctl restart "$KAT_DEPLOY_SERVICE"

    ready=false
    attempt=1
    while [ "$attempt" -le 30 ]; do
        if curl -fsS "$KAT_DEPLOY_HEALTH_URL" >/dev/null; then
            ready=true
            break
        fi
        sleep 2
        attempt=$((attempt + 1))
    done

    if [ "$ready" != true ]; then
        echo "Gateway health check failed after deployment." >&2
        exit 1
    fi

    trap - EXIT HUP INT TERM
    echo "Gateway deployment complete."
done
