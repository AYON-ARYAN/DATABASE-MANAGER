#!/usr/bin/env bash
# Boot a clean LLM stub + app for local Specmatic report generation (non-destructive ports).
set -u
REPO=/Volumes/BLACK_SHARK/MINOR_PROJECT
cd "$REPO"
STUB_PORT=9091
APP_PORT=5002

# clean up any prior instances WE started on these ports
for p in $STUB_PORT $APP_PORT; do
  pid=$(lsof -nP -iTCP:$p -sTCP:LISTEN -t 2>/dev/null)
  [ -n "$pid" ] && { echo "killing pid $pid on $p"; kill "$pid" 2>/dev/null; }
done
sleep 1

echo "starting LLM stub on $STUB_PORT..."
nohup java -jar specmatic.jar stub llm_contract.yaml --port $STUB_PORT > /tmp/spec_stub9091.log 2>&1 &
for i in $(seq 1 40); do curl -s -o /dev/null http://localhost:$STUB_PORT/ && break; sleep 1; done
echo "stub status: $(curl -s -o /dev/null -w '%{http_code}' http://localhost:$STUB_PORT/ || echo down)"

echo "starting Flask app on $APP_PORT (SPECMATIC_TEST, LLM->stub)..."
SPECMATIC_TEST=specmatic-ci-token \
GROQ_API_URL=http://localhost:$STUB_PORT/openai/v1/chat/completions \
GROQ_API_KEY=ci-stub-key \
nohup ./venv/bin/python -m flask --app app run --port $APP_PORT > /tmp/app5002.log 2>&1 &
for i in $(seq 1 40); do curl -s -o /dev/null http://localhost:$APP_PORT/api/auth/session && break; sleep 1; done
echo "app session status: $(curl -s -o /dev/null -w '%{http_code}' http://localhost:$APP_PORT/api/auth/session || echo down)"
echo "BOOT DONE"
