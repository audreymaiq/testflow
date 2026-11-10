#!/bin/sh
# Read-only smoke checks against the real HTTPS origin.
set -eu

origin=${1:?Usage: smoke.sh https://your-domain}
case "$origin" in https://*) ;; *) echo 'A verified HTTPS origin is required' >&2; exit 2 ;; esac
origin=${origin%/}

expect_status() {
    expected=$1
    path=$2
    actual=$(curl --silent --show-error --max-time 20 --output /dev/null --write-out '%{http_code}' "$origin$path")
    test "$actual" = "$expected" || {
        printf '%s returned %s; expected %s\n' "$path" "$actual" "$expected" >&2
        exit 1
    }
}

expect_status 200 /
expect_status 200 /library
expect_status 200 /healthz
expect_status 200 /api/v1/exams/
expect_status 401 /api/v1/imports/mine/
expect_status 401 /api/v1/practice/sessions/history/
printf 'Anonymous and private-route smoke checks passed: %s\n' "$origin"
