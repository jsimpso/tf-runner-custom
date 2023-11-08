#!/usr/bin/env sh

set -e
echo '
provider_installation {
  filesystem_mirror {
    path = "/opt/providers"
  }
}' > ~/.terraformrc

exec /sbin/tini -- tf-runner "$@"

