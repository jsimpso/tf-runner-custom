#!/usr/bin/env sh

exec /sbin/tini -- tf-runner "$@"
