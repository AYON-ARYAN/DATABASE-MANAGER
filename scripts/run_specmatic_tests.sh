#!/usr/bin/env bash
# Run ALL Specmatic tests locally, exactly as CI does — self-contained.
# Starts the LLM stub + the app (LLM virtualized, gated test-auth), then runs the
# 4 test jobs (contract + resiliency for each app spec) and the LLM smoke test.
# Uses Docker if available, else the bundled specmatic.jar (needs Java 17+).
#
#   bash scripts/run_specmatic_tests.sh
#
# Ports are overridable: STUB_PORT (default 9090), APP_PORT (default 5001).
set -u
cd "$(dirname "$0")/.."
ROOT="$PWD"
STUB_PORT="${STUB_PORT:-9090}"
APP_PORT="${APP_PORT:-5001}"
TOKEN="specmatic-ci-token"
PY="${PYTHON:-python3}"; [ -x "./venv/bin/python" ] && PY="./venv/bin/python"

if docker info >/dev/null 2>&1; then
  MODE=docker; echo "==> using Docker (specmatic/specmatic:latest)"
elif command -v java >/dev/null 2>&1 && [ -f specmatic.jar ]; then
  MODE=jar;    echo "==> using bundled specmatic.jar (Java $(java -version 2>&1|head -1))"
else
  echo "ERROR: need either Docker or Java 17+ with specmatic.jar"; exit 1
fi

stub()  { if [ "$MODE" = docker ]; then
            docker run -d --rm --name spec-stub --network host -v "$ROOT:/specs" -w /specs \
              specmatic/specmatic:latest stub llm_contract.yaml --port "$STUB_PORT" >/dev/null
          else nohup java -jar specmatic.jar stub llm_contract.yaml --port "$STUB_PORT" >/tmp/spec_stub.log 2>&1 & fi; }
runtest(){ # $1 spec  $2 generative(true|"")  $3 extra
          local gen=""; [ "$2" = true ] && gen="SPECMATIC_GENERATIVE_TESTS=true"
          if [ "$MODE" = docker ]; then
            docker run --rm --network host -e SPECMATIC_GENERATIVE_TESTS="${2:-false}" -v "$ROOT:/specs" -w /specs \
              specmatic/specmatic:latest test "$1" $3 --host localhost --port "$APP_PORT"
          else eval "$gen java -jar specmatic.jar test $1 $3 --host localhost --port $APP_PORT"; fi; }

cleanup(){ docker rm -f spec-stub >/dev/null 2>&1 || true
           for p in "$STUB_PORT" "$APP_PORT"; do pid=$(lsof -nP -iTCP:$p -sTCP:LISTEN -t 2>/dev/null); [ -n "$pid" ] && kill $pid 2>/dev/null; done; }
trap cleanup EXIT

echo "==> starting LLM stub on :$STUB_PORT"; stub
for i in $(seq 1 40); do curl -s -o /dev/null "http://localhost:$STUB_PORT/" && break; sleep 1; done

echo "==> starting app on :$APP_PORT (LLM -> stub, gated test-auth)"
SPECMATIC_TEST="$TOKEN" GROQ_API_URL="http://localhost:$STUB_PORT/openai/v1/chat/completions" GROQ_API_KEY=ci-stub-key \
  nohup "$PY" -m flask --app app run --port "$APP_PORT" >/tmp/spec_app.log 2>&1 &
for i in $(seq 1 40); do curl -s -o /dev/null "http://localhost:$APP_PORT/api/auth/session" && break; sleep 1; done

fail=0
echo "==> [1/5] contract_public · contract";   runtest contract_public.yaml ""   "--examples examples"     || fail=1
echo "==> [2/5] contract_public · resiliency"; runtest contract_public.yaml true "--examples examples"     || fail=1
echo "==> [3/5] api_contract · contract";      runtest api_contract.yaml    ""   "--examples examples_api" || fail=1
echo "==> [4/5] api_contract · resiliency";    runtest api_contract.yaml    true "--examples examples_api" || fail=1
echo "==> [5/5] LLM virtualization smoke test"
GROQ_API_URL="http://localhost:$STUB_PORT/openai/v1/chat/completions" GROQ_API_KEY=ci-stub-key "$PY" scripts/llm_mock_test.py || fail=1

echo; [ $fail = 0 ] && echo "ALL SPECMATIC TESTS PASSED. HTML reports in build/reports/specmatic/test/html/" || echo "SOME TESTS FAILED (see output above)."
exit $fail
