#!/bin/sh
# Executed by Pebble after it prepares its state on writable /tmp.
set -eu
umask 077
export HOME="${HOME:-/home/runner}"
export TF_PLUGIN_CACHE_DIR="${TF_PLUGIN_CACHE_DIR:-$HOME/.terraform.d/plugin-cache}"
mkdir -p "$TF_PLUGIN_CACHE_DIR" "$HOME/.local/share/juju"
# Kubernetes Args replace OCI CMD, so forward each argument without shell parsing.
exec /usr/local/bin/tf-runner "$@"
