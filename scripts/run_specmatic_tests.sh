#!/usr/bin/env bash
# Run ALL Specmatic tests locally, exactly as CI does — self-contained.
# Starts the LLM stub + the app (LLM virtualized, real API-bearer auth), then runs the
# 2 spec test jobs (specmatic.yaml's schemaResiliencyTests: all means each single run
# already covers conformance + resiliency) and the LLM smoke test. Copies each job's
# HTML report into reports/ as it finishes, so reports/ always reflects the latest run.
# Uses Docker if available, else a Specmatic jar (needs Java 17+).
#
#   bash scripts/run_specmatic_tests.sh
#
# Configurable env vars (all optional):
#   STUB_PORT        LLM stub port                          default: 9090 (auto-bumped if busy)
#   APP_PORT          Flask app port                         default: 5001 (auto-bumped if busy)
#   TEST_APP_PORT     port specmatic.yaml points tests at     default: same as APP_PORT
#   API_BEARER_TOKEN  bearer token app + Specmatic both use   default: specmatic-ci-token
#   SPECMATIC_JAR     path to the Specmatic jar (jar mode)    default: ./specmatic.jar
#   GROQ_API_URL / GROQ_API_KEY  where the app sends LLM calls in test mode
#   ENABLE_ACTUATOR   exposes /actuator/mappings for actual-coverage reporting  default: 1
set -u
cd "$(dirname "$0")/.."
ROOT="$PWD"
TOKEN="${API_BEARER_TOKEN:-specmatic-ci-token}"
JAR="${SPECMATIC_JAR:-$ROOT/specmatic.jar}"
PY="${PYTHON:-python3}"; [ -x "./venv/bin/python" ] && PY="./venv/bin/python"

# Pick a free port at/after a preferred one, so a busy 9090/5001 never blocks the run.
free_port(){ local p="$1"; while lsof -nP -iTCP:"$p" -sTCP:LISTEN -t >/dev/null 2>&1; do p=$((p+1)); done; echo "$p"; }
STUB_PORT="${STUB_PORT:-$(free_port 9090)}"
APP_PORT="${APP_PORT:-$(free_port 5001)}"
# The config reads TEST_APP_PORT to keep baseUrl + actuatorUrl aligned with the app port.
export TEST_APP_PORT="${TEST_APP_PORT:-$APP_PORT}"
echo "==> ports: stub=$STUB_PORT app=$APP_PORT (override with STUB_PORT=.. APP_PORT=..)"
IMG="specmatic/specmatic:2.48.0"

if docker info >/dev/null 2>&1; then
  MODE=docker; echo "==> using Docker ($IMG)"
elif command -v java >/dev/null 2>&1 && [ -f "$JAR" ]; then
  MODE=jar;    echo "==> using $JAR (Java $(java -version 2>&1|head -1))"
else
  echo "ERROR: need either Docker, or Java 17+ with a Specmatic jar at \$SPECMATIC_JAR (default: $ROOT/specmatic.jar)"; exit 1
fi

stub()  { if [ "$MODE" = docker ]; then
            docker run -d --rm --name spec-stub --network host -v "$ROOT:/specs" -w /specs \
              "$IMG" stub llm_contract.yaml --port "$STUB_PORT" >/dev/null
          else nohup java -jar "$JAR" stub llm_contract.yaml --port "$STUB_PORT" >/tmp/spec_stub.log 2>&1 & fi; }
runtest(){ # $1 spec  $2 extra args  $3 report name (used to copy the HTML report into reports/)
          local spec="$1" extra="$2" name="$3" rc
          rm -rf build/reports/specmatic
          if [ "$MODE" = docker ]; then
            docker run --rm --network host -e TEST_APP_PORT="$APP_PORT" -e API_BEARER_TOKEN="$TOKEN" \
              -v "$ROOT:/specs" -w /specs \
              "$IMG" test "$spec" $extra --host localhost --port "$APP_PORT"
          else eval "TEST_APP_PORT=$APP_PORT java -jar \"$JAR\" test $spec $extra --host localhost --port $APP_PORT"; fi
          rc=$?
          mkdir -p reports
          if [ -f build/reports/specmatic/test/html/index.html ]; then
            cp build/reports/specmatic/test/html/index.html "reports/$name.html"
            echo "  -> reports/$name.html"
          fi
          return $rc; }

cleanup(){ docker rm -f spec-stub >/dev/null 2>&1 || true
           for p in "$STUB_PORT" "$APP_PORT"; do pid=$(lsof -nP -iTCP:$p -sTCP:LISTEN -t 2>/dev/null); [ -n "$pid" ] && kill $pid 2>/dev/null; done; }
trap cleanup EXIT

echo "==> starting LLM stub on :$STUB_PORT"; stub
for i in $(seq 1 40); do curl -s -o /dev/null "http://localhost:$STUB_PORT/" && break; sleep 1; done

echo "==> starting app on :$APP_PORT (API bearer-token auth + actuator, LLM -> stub)"
API_BEARER_TOKEN="$TOKEN" ENABLE_ACTUATOR="${ENABLE_ACTUATOR:-1}" \
  GROQ_API_URL="${GROQ_API_URL:-http://localhost:$STUB_PORT/openai/v1/chat/completions}" GROQ_API_KEY="${GROQ_API_KEY:-ci-stub-key}" \
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
echo "==> [1/3] contract_public.yaml (conformance + resiliency)"; runtest contract_public.yaml "--examples examples"     contract_public || fail=1
echo "==> [2/3] api_contract.yaml (conformance + resiliency, LLM mocked)"; runtest api_contract.yaml "--examples examples_api" api_contract || fail=1
echo "==> [3/3] LLM virtualization smoke test"
GROQ_API_URL="http://localhost:$STUB_PORT/openai/v1/chat/completions" GROQ_API_KEY=ci-stub-key "$PY" scripts/llm_mock_test.py || fail=1

echo; [ $fail = 0 ] && echo "ALL SPECMATIC TESTS PASSED. HTML reports in reports/ (and build/reports/specmatic/test/html/ for the last job)." || echo "SOME TESTS FAILED (see output above)."
exit $fail
