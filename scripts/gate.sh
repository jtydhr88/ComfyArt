#!/usr/bin/env bash
# ComfyArt merge gate. Usage: scripts/gate.sh <slug>   (worktree = $GATE_ROOT/wt_<slug without '-'>)
# Env: GATE_ROOT (/workspace), GATE_MAIN (/workspace/ComfyArt, node_modules source),
#      GATE_PY (/workspace/ca-venv/bin/python), GATE_PORTS ("9392", e2e mock ports)
set -u -o pipefail
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
. "$HERE/gate_lib.sh"
S=${1:?usage: gate.sh <slug>}
ROOT=${GATE_ROOT:-/workspace}; MAIN=${GATE_MAIN:-$ROOT/ComfyArt}; PY=${GATE_PY:-$ROOT/ca-venv/bin/python}
W=${GATE_WT:-$ROOT/wt_${S//-/}}
LOGDIR=$(mktemp -d "/tmp/gate_${S//-/}_XXXX"); RC=0
fail() { RC=1; echo "$S GATE_FAIL: $*"; }
archive() {
  [ "$RC" = 0 ] && return
  local a="$LOGDIR.failure.tar.gz"; tar -czf "$a" -C "$LOGDIR" . 2>/dev/null
  echo "$S FAILURE_LOGS: $a (tracebacks in $LOGDIR)"
}
cleanup() {
  # Only touch the worktree if this run owns it (marker written after pre-checks passed).
  if [ -f "$W/.gate_owned" ] && [ "$(cat "$W/.gate_owned" 2>/dev/null)" = "$$" ]; then
    cd "$W" && { git checkout -q -- dist 2>/dev/null; git clean -fdq dist; rm -rf node_modules; rm -f .gate_owned; git status --porcelain | head -2; }
  fi
  archive; echo "$S GATE_EXIT=$RC"; exit $RC; }
trap cleanup EXIT
trap 'RC=130; exit 130' INT TERM

gate_check_wt_name "$W" || { RC=2; exit 2; }
gate_check_no_node_modules "$W" || { RC=2; exit 2; }
[ -e "$W/.gate_owned" ] && { echo "GATE_FAIL: $W/.gate_owned exists (another gate run, or stale marker: remove it)" >&2; RC=2; exit 2; }
# concurrency pre-checks before ANY pytest stage (repeated before E2E)
gate_check_no_pytest || { RC=2; exit 2; }
# shellcheck disable=SC2086
gate_check_ports_free ${GATE_PORTS:-9392} || { RC=2; exit 2; }
cd "$W"; echo "$$" > .gate_owned; cp -al "$MAIN/node_modules" node_modules

npx tsc --noEmit -p . >"$LOGDIR/tsc.log" 2>&1 && echo "$S TSC_OK" || fail "tsc (see $LOGDIR/tsc.log)"

stage() { # name, -k expr
  local n=$1 k=$2 co
  "$PY" -m pytest -q -p no:cacheprovider --co tests -k "$k" >"$LOGDIR/$n.collect.log" 2>&1; co=$?
  if [ "$co" != 0 ]; then   # no count on a broken collection (pytest's partial N would mislead)
    echo "$S $n: collected=COLLECTION_ERROR collect_exit=$co"; gate_collect_err_tail "$LOGDIR/$n.collect.log"
    fail "$n collection exit $co"; return
  fi
  local cnt; cnt=$(grep -oE '^[0-9]+(/[0-9]+)? tests? (collected|selected)' "$LOGDIR/$n.collect.log" | grep -oE '^[0-9]+' | head -1)
  echo "$S $n: collected=${cnt:-?} collect_exit=$co"
  "$PY" -m pytest -q -p no:cacheprovider tests -k "$k" >"$LOGDIR/$n.log" 2>&1; local ec=$?
  grep -E "^FAILED|^ERROR|passed|failed" "$LOGDIR/$n.log" | sed "s/^/$S $n: /"
  echo "$S $n: exit=$ec"
  [ "$ec" = 0 ] || fail "$n pytest exit $ec"
  gate_check_log_errors "$LOGDIR/$n.log" || fail "$n has error lines"
}
stage UNIT "skill and not e2e"
npx vite build >"$LOGDIR/build.log" 2>&1 && echo "$S BUILD_OK(local, not committed)" || fail "vite build"
gate_check_no_pytest || { fail "pytest already running"; exit; }
# shellcheck disable=SC2086
gate_check_ports_free ${GATE_PORTS:-9392} || { fail "ports busy"; exit; }
stage E2E "(skill and e2e) or 650 or creator"
