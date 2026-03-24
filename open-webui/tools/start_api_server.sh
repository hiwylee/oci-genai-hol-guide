#!/usr/bin/env bash
# 오라 여행 SSE API 서버 시작 스크립트
# 사용법: ./start_api_server.sh [start|stop|restart|status]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVER_SCRIPT="${SCRIPT_DIR}/call_api_server.py"
LOG_FILE="/tmp/call_api_server.log"
PID_FILE="/tmp/call_api_server.pid"
PORT=8000

# ── 색상 출력 ──────────────────────────────────────────────────
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
ok()   { echo -e "${GREEN}[OK]${NC}  $*"; }
info() { echo -e "${YELLOW}[--]${NC}  $*"; }
err()  { echo -e "${RED}[ERR]${NC} $*" >&2; }

# ── 의존 확인 ──────────────────────────────────────────────────
check_uv() {
  if ! command -v uv &>/dev/null; then
    err "uv 가 설치되어 있지 않습니다. https://docs.astral.sh/uv/getting-started/installation/"
    exit 1
  fi
}

# ── 포트 기반 프로세스 확인 (uv run이 자식 uvicorn을 spawn 후 종료하므로 포트로 판단)
is_running() {
  curl -sf "http://localhost:${PORT}/health" &>/dev/null
}

# 서버 프로세스 PID (uvicorn 또는 python3 call_api_server)
server_pid() {
  pgrep -f "call_api_server.py" 2>/dev/null | head -1
}

do_start() {
  check_uv
  if is_running; then
    ok "이미 실행 중 (PID=$(cat "${PID_FILE}"), port=${PORT})"
    return 0
  fi

  info "서버 시작 중 (port=${PORT}) ..."
  nohup uv run \
    --with fastapi \
    --with "uvicorn[standard]" \
    python3 "${SERVER_SCRIPT}" \
    >> "${LOG_FILE}" 2>&1 &
  local pid=$!
  echo "${pid}" > "${PID_FILE}"

  # 최대 10초 대기
  for i in $(seq 1 10); do
    sleep 1
    if curl -sf "http://localhost:${PORT}/health" &>/dev/null; then
      ok "서버 기동 완료 (PID=${pid}, port=${PORT})"
      ok "로그: ${LOG_FILE}"
      return 0
    fi
  done

  err "서버 기동 실패. 로그 확인: ${LOG_FILE}"
  tail -20 "${LOG_FILE}" >&2
  exit 1
}

do_stop() {
  if ! is_running; then
    info "실행 중인 서버가 없습니다."
    rm -f "${PID_FILE}"
    return 0
  fi
  local pid
  pid=$(server_pid)
  info "서버 종료 중 (PID=${pid}) ..."
  pkill -f "call_api_server.py" 2>/dev/null || true
  sleep 1
  rm -f "${PID_FILE}"
  ok "서버 종료 완료"
}

do_status() {
  if is_running; then
    local pid
    pid=$(server_pid || echo "?")
    ok "실행 중 (PID=${pid}, port=${PORT})"
    curl -s "http://localhost:${PORT}/health" | python3 -m json.tool 2>/dev/null || true
  else
    info "중지 상태"
    rm -f "${PID_FILE}"
  fi
}

# ── 메인 ───────────────────────────────────────────────────────
CMD="${1:-start}"
case "${CMD}" in
  start)   do_start ;;
  stop)    do_stop ;;
  restart) do_stop; sleep 1; do_start ;;
  status)  do_status ;;
  *)
    echo "사용법: $0 {start|stop|restart|status}"
    exit 1
    ;;
esac
