#!/usr/bin/env bash
# Run ALL Specmatic tests locally, exactly as CI does — self-contained.
# Starts the LLM stub + the app (LLM virtualized, gated test-auth), then runs the
# 4 test jobs (contract + resiliency for each app spec) and the LLM smoke test.
# Uses Docker if available, else a configurable Specmatic jar (needs Java 17+).
#
#   bash scripts/run_specmatic_tests.sh
#
# Ports are overridable: STUB_PORT (default 9090), APP_PORT (default 5001).
set -u
cd "$(dirname "$0")/.."
ROOT="$PWD"
TOKEN="specmatic-ci-token"
PY="${PYTHON:-python3}"; [ -x "./venv/bin/python" ] && PY="./venv/bin/python"
SPECMATIC_JAR="${SPECMATIC_JAR:-$HOME/.specmatic/specmatic.jar}"

# Pick a free port at/after a preferred one, so a busy 9090/5001 never blocks the run.
free_port(){ local p="$1"; while lsof -nP -iTCP:"$p" -sTCP:LISTEN -t >/dev/null 2>&1; do p=$((p+1)); done; echo "$p"; }
STUB_PORT="${STUB_PORT:-$(free_port 9090)}"
APP_PORT="${APP_PORT:-$(free_port 5001)}"
# The config reads TEST_APP_PORT to keep baseUrl + actuatorUrl aligned with the app port.
export TEST_APP_PORT="$APP_PORT"
echo "==> ports: stub=$STUB_PORT app=$APP_PORT (override with STUB_PORT=.. APP_PORT=..)"
IMG="specmatic/specmatic:2.48.0"

if docker info >/dev/null 2>&1; then
  MODE=docker; echo "==> using Docker (specmatic/specmatic:latest)"
elif command -v java >/dev/null 2>&1 && [ -f "$SPECMATIC_JAR" ]; then
  MODE=jar;    echo "==> using Specmatic jar at $SPECMATIC_JAR (Java $(java -version 2>&1|head -1))"
else
  echo "ERROR: need either Docker or Java 17+ with SPECMATIC_JAR set to a valid path"; exit 1
fi

stub()  { if [ "$MODE" = docker ]; then
            docker run -d --rm --name spec-stub --network host -v "$ROOT:/specs" -w /specs \
              "$IMG" stub llm_contract.yaml --port "$STUB_PORT" >/dev/null
          else nohup java -jar "$SPECMATIC_JAR" stub llm_contract.yaml --port "$STUB_PORT" >/tmp/spec_stub.log 2>&1 & fi; }
runtest(){ # $1 spec  $2 generative(true|"")  $3 extra
          local gen=""; [ "$2" = true ] && gen="SPECMATIC_GENERATIVE_TESTS=true"
          if [ "$MODE" = docker ]; then
            docker run --rm --network host -e SPECMATIC_GENERATIVE_TESTS="${2:-false}" -e TEST_APP_PORT="$APP_PORT" \
              -e API_BEARER_TOKEN="$TOKEN" -v "$ROOT:/specs" -w /specs \
              "$IMG" test "$1" $3 --host localhost --port "$APP_PORT"
          else eval "$gen TEST_APP_PORT=$APP_PORT java -jar \"$SPECMATIC_JAR\" test $1 $3 --host localhost --port $APP_PORT"; fi; }

cleanup(){ docker rm -f spec-stub >/dev/null 2>&1 || true
           for p in "$STUB_PORT" "$APP_PORT"; do pid=$(lsof -nP -iTCP:$p -sTCP:LISTEN -t 2>/dev/null); [ -n "$pid" ] && kill $pid 2>/dev/null; done; }
trap cleanup EXIT

echo "==> starting LLM stub on :$STUB_PORT"; stub
for i in $(seq 1 40); do curl -s -o /dev/null "http://localhost:$STUB_PORT/" && break; sleep 1; done

echo "==> starting app on :$APP_PORT (API bearer-token auth + actuator, LLM -> stub)"
API_BEARER_TOKEN="$TOKEN" ENABLE_ACTUATOR=1 GROQ_API_URL="http://localhost:$STUB_PORT/openai/v1/chat/completions" GROQ_API_KEY=ci-stub-key \
  nohup "$PY" -m flask --app app run --port "$APP_PORT" >/tmp/spec_app.log 2>&1 &
for i in $(seq 1 40); do curl -s -o /dev/null "http://localhost:$APP_PORT/api/auth/session" && break; sleep 1; done
# Warm the LLM-calling path (app -> stub round-trip) before the suite, so the first
# /api/command scenarios don't race a cold stub. Retry until it answers cleanly.
echo "==> warming up the LLM-mock path"
for i in $(seq 1 15); do
  curl -s -o /dev/null -X POST "http://localhost:$APP_PORT/api/command" \
    -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
    -d '{"command":"warmup"}' && break
  sleep 1
done

fail=0
echo "==> [1/5] contract_public · contract";   runtest contract_public.yaml ""   "--examples examples"     || fail=1
echo "==> [2/5] contract_public · resiliency"; runtest contract_public.yaml true "--examples examples"     || fail=1
echo "==> [3/5] api_contract · contract";      runtest api_contract.yaml    ""   "--examples examples_api" || fail=1
echo "==> [4/5] api_contract · resiliency";    runtest api_contract.yaml    true "--examples examples_api" || fail=1
echo "==> [5/5] LLM virtualization smoke test"
GROQ_API_URL="http://localhost:$STUB_PORT/openai/v1/chat/completions" GROQ_API_KEY=ci-stub-key "$PY" scripts/llm_mock_test.py || fail=1

echo; [ $fail = 0 ] && echo "ALL SPECMATIC TESTS PASSED. HTML reports in build/reports/specmatic/test/html/" || echo "SOME TESTS FAILED (see output above)."
exit $fail
