#!/usr/bin/env bash
set -euo pipefail

umask 077

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd -- "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_DIR"

if [[ -z "${ENV_FILE:-}" ]]; then
  if [[ -f "$HOME/.config/webnovel-radar/env" ]]; then
    ENV_FILE="$HOME/.config/webnovel-radar/env"
  else
    ENV_FILE="$REPO_DIR/.env"
  fi
fi
if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source <(sed -e 's/\r$//' "$ENV_FILE")
  set +a
fi

export TZ="${REPORT_TZ:-Asia/Shanghai}"
export LANG="${LANG:-C.UTF-8}"
export PYTHONIOENCODING=utf-8

DATE="${REPORT_DATE:-$(date +%F)}"
REPORT_DIR="$REPO_DIR/reports"
LOG_DIR="$REPO_DIR/logs"
REPORT_PATH="${REPORT_PATH:-$REPORT_DIR/webnovel-radar-$DATE.md}"
LOG_FILE="$LOG_DIR/run-$DATE.log"
PROMPT_FILE="$REPO_DIR/prompts/daily.md"
PUSH_SCRIPT="$REPO_DIR/scripts/push_serverchan.py"
OPENCODE_BIN="${OPENCODE_BIN:-$HOME/.opencode/bin/opencode}"
MODEL="${OPENCODE_MODEL:-deepseek/deepseek-flash}"
REPORT_KEEP_DAYS="${REPORT_KEEP_DAYS:-7}"
LOG_KEEP_DAYS="${LOG_KEEP_DAYS:-14}"

mkdir -p "$REPORT_DIR" "$LOG_DIR"

log() {
  printf '[%s] %s\n' "$(date -Is)" "$*" | tee -a "$LOG_FILE"
}

if [[ ! -f "$PROMPT_FILE" ]]; then
  log "prompt file not found: $PROMPT_FILE"
  exit 1
fi

if [[ ! -x "$OPENCODE_BIN" ]] && command -v opencode >/dev/null 2>&1; then
  OPENCODE_BIN="$(command -v opencode)"
fi
if [[ ! -x "$OPENCODE_BIN" ]]; then
  log "opencode not found (OPENCODE_BIN=$OPENCODE_BIN)"
  exit 1
fi

command -v python3 >/dev/null 2>&1 || {
  log "python3 not found"
  exit 1
}

exec 9>"$LOG_DIR/.run.lock"
if ! flock -n 9; then
  log "another run is already in progress, exiting"
  exit 1
fi

PROMPT="$(python3 - "$PROMPT_FILE" "$DATE" "$REPORT_PATH" <<'PY'
import pathlib
import sys

text = pathlib.Path(sys.argv[1]).read_text(encoding="utf-8")
print(text.replace("{{DATE}}", sys.argv[2]).replace("{{REPORT_PATH}}", sys.argv[3]))
PY
)"

run_agent() {
  local rc=0
  log "starting opencode run (model=$MODEL, date=$DATE)"
  set +e
  "$OPENCODE_BIN" run --auto --model "$MODEL" --title "网文雷达 $DATE" "$PROMPT" 2>&1 | tee -a "$LOG_FILE"
  rc="${PIPESTATUS[0]}"
  set -e
  log "opencode exited with code $rc"
  return 0
}

report_ready() {
  local started_at="$1"
  [[ -s "$REPORT_PATH" ]] || return 1
  local report_mtime
  report_mtime="$(stat -c %Y "$REPORT_PATH" 2>/dev/null || echo 0)"
  (( report_mtime >= started_at ))
}

REPORT_OK=0
for attempt in 1 2; do
  started_at="$(date +%s)"
  run_agent
  if report_ready "$started_at"; then
    REPORT_OK=1
    break
  fi
  if (( attempt == 1 )); then
    log "report not produced, retrying once in 60s"
    sleep 60
  fi
done

PUSH_OK=0
if (( REPORT_OK == 1 )); then
  log "report ready: $REPORT_PATH"
  if python3 "$PUSH_SCRIPT" "$REPORT_PATH" >>"$LOG_FILE" 2>&1; then
    PUSH_OK=1
    log "ServerChan push succeeded"
  else
    log "ServerChan push failed"
  fi
else
  log "report missing after retry: $REPORT_PATH"
fi

if (( PUSH_OK == 0 )); then
  FAIL_BODY="$(mktemp)"
  {
    echo "任务日期：$DATE"
    echo
    if (( REPORT_OK == 1 )); then
      echo "状态：报告已生成，但 ServerChan 推送失败。"
    else
      echo "状态：报告生成失败（opencode 未产出报告文件）。"
    fi
    echo
    echo "最近日志："
    echo '```text'
    tail -n 40 "$LOG_FILE" | sed -E 's/\x1B\[[0-9;]*[mK]//g'
    echo '```'
    if (( REPORT_OK == 1 )); then
      echo
      echo "报告仍在服务器：$REPORT_PATH"
    fi
  } >"$FAIL_BODY"
  python3 "$PUSH_SCRIPT" --title "网文雷达失败 $DATE" --body-file "$FAIL_BODY" >>"$LOG_FILE" 2>&1 || true
  rm -f "$FAIL_BODY"
fi

find "$REPORT_DIR" -maxdepth 1 -type f -name 'webnovel-radar-*.md' -mtime +"$REPORT_KEEP_DAYS" -delete
find "$LOG_DIR" -maxdepth 1 -type f -name 'run-*.log' -mtime +"$LOG_KEEP_DAYS" -delete
log "cleanup done (reports older than ${REPORT_KEEP_DAYS}d, logs older than ${LOG_KEEP_DAYS}d)"

if (( PUSH_OK == 0 )); then
  exit 1
fi
exit 0
