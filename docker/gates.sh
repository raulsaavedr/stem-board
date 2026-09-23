#!/usr/bin/env bash
# Run the same small check set as CI inside the isolated Docker environment.
set -euo pipefail
cd /repo

export CARGO_NET_OFFLINE=true

gate() { # gate <name> <cmd...>
  local name="$1"; shift
  echo
  echo "==================================================================="
  echo "sandbox gates: [$name]"
  echo "==================================================================="
  if "$@"; then
    echo "sandbox gates: [$name] PASS"
  else
    local rc=$?
    echo "sandbox gates: [$name] FAIL (exit $rc)" >&2
    echo "sandbox gates: stopping at the first failing gate: $name" >&2
    exit "$rc"
  fi
}

# Gate 0: prove the isolation profile before anything else runs.
export HB_SELFCHECK_NETWORK=off
gate "selfcheck (isolation proof)" bash /repo/docker/selfcheck.sh

gate "cargo fmt --all --check" cargo fmt --all --check
gate "cargo clippy --workspace --all-targets --all-features -- -D warnings" \
  cargo clippy --workspace --all-targets --all-features -- -D warnings
gate "cargo test --workspace --all-features" cargo test --workspace --all-features
echo
echo "sandbox gates: ALL GATES PASSED"
