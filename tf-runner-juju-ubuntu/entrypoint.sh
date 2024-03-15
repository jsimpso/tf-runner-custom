#!/usr/bin/env sh

set -e
#echo '
#provider_installation {
#  filesystem_mirror {
#    path = "/opt/providers"
#  }
#}' > ~/.terraformrc

mkdir -p ~/.local/share/juju

exec /bin/tini -- tf-runner "$@"
