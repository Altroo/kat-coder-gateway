#!/bin/sh
# Build an isolated release before switching the live service symlink.
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
release_dir=
staged_link=
switch_number=0

switch_target() {
    switch_number=$((switch_number + 1))
    candidate_link="$KAT_DEPLOY_ACTIVE_LINK.next-$$-$switch_number"
    sudo ln -s -- "$1" "$candidate_link" || return $?
    staged_link=$candidate_link
    sudo mv -Tf -- "$staged_link" "$KAT_DEPLOY_ACTIVE_LINK" || return $?
    staged_link=
}

finish() {
    result=$?
    trap - EXIT HUP INT TERM
    if [ -n "$staged_link" ]; then
        sudo rm -f -- "$staged_link" || true
        staged_link=
    fi
    # Only undo our own switch. A build failure never touched the live target.
    if [ "$result" -ne 0 ] && [ -n "$release_dir" ] &&
       [ -L "$KAT_DEPLOY_ACTIVE_LINK" ] &&
       [ "$(readlink "$KAT_DEPLOY_ACTIVE_LINK")" = "$release_dir" ]; then
        if [ -n "$old_target" ]; then
            echo "Deployment failed. Restoring the previous release." >&2
            if switch_target "$old_target"; then
                sudo systemctl restart "$KAT_DEPLOY_SERVICE" || true
            else
                echo "Rollback link update failed; manual recovery is required." >&2
            fi
        else
            sudo rm -f -- "$KAT_DEPLOY_ACTIVE_LINK" || true
            sudo systemctl stop "$KAT_DEPLOY_SERVICE" || true
        fi
    fi
    if [ -n "$staged_link" ]; then
        sudo rm -f -- "$staged_link" || true
    fi
    exit "$result"
}

while read -r _old_revision _new_revision ref_name; do
    [ "$ref_name" = "refs/heads/$branch" ] || continue
    case "$_new_revision" in *[!0]*) ;; *) continue ;; esac

    for deployment_path in "$KAT_DEPLOY_TARGET" "$KAT_DEPLOY_ACTIVE_LINK"; do
        case "$deployment_path" in
            /|*/../*|*/..|*/./*|*/.) echo "Unsafe deployment path." >&2; exit 1 ;;
            /*) ;;
            *) echo "Deployment paths must be absolute." >&2; exit 1 ;;
        esac
    done
    if [ -e "$KAT_DEPLOY_ACTIVE_LINK" ] && [ ! -L "$KAT_DEPLOY_ACTIVE_LINK" ]; then
        echo "The active service path must be a symlink, not a directory." >&2
        exit 1
    fi

    umask 022
    releases_dir="${KAT_DEPLOY_TARGET%/}-releases"
    mkdir -p "$releases_dir"
    exec 9>"$releases_dir/.deploy.lock"
    if ! flock -n 9; then
        echo "Another gateway deployment is running." >&2
        exit 1
    fi
    revision=$(git --git-dir="$KAT_DEPLOY_GIT_DIR" rev-parse --verify --end-of-options "$_new_revision^{commit}")
    # Resolve before changing the live symlink; never link a release back to itself.
    runtime_env=$(readlink -f -- "${KAT_DEPLOY_RUNTIME_ENV:-$KAT_DEPLOY_TARGET/.env.production}")
    if [ ! -f "$runtime_env" ]; then
        echo "Missing private runtime configuration." >&2
        exit 1
    fi
    old_target=
    if [ -L "$KAT_DEPLOY_ACTIVE_LINK" ]; then
        old_target=$(readlink "$KAT_DEPLOY_ACTIVE_LINK")
    fi
    trap finish EXIT
    trap 'exit 129' HUP
    trap 'exit 130' INT
    trap 'exit 143' TERM

    release_dir=$(mktemp -d "$releases_dir/release-$revision.XXXXXX")
    chmod 755 "$release_dir"
    echo "Building revision $revision in $release_dir"
    git --git-dir="$KAT_DEPLOY_GIT_DIR" archive --format=tar \
        --output="$release_dir.tar" "$revision"
    tar -xf "$release_dir.tar" -C "$release_dir"
    rm -f -- "$release_dir.tar"
    ln -s -- "$runtime_env" "$release_dir/.env.production"

    make -C "$release_dir/c" qwen36 ARCH=native
    switch_target "$release_dir"
    sudo systemctl restart "$KAT_DEPLOY_SERVICE"

    ready=false
    attempt=1
    while [ "$attempt" -le 30 ]; do
        if curl -fsS --connect-timeout 2 --max-time 5 "$KAT_DEPLOY_HEALTH_URL" >/dev/null; then
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
    release_dir=
    echo "Gateway deployment complete."
done
