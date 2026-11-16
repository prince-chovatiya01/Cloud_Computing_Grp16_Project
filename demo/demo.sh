#!/usr/bin/env bash
# Viva live demo (~5 min, no AWS): the same failure with and without the circuit breaker.
#   bash demo/demo.sh          press Enter to move to each step
# Do not run while loadtest/run_local_suite.sh is using port 8081.
set -euo pipefail
cd "$(dirname "$0")/.."
S2="docker compose -f app/docker-compose.services.yml"
URL=http://localhost:8081

step() { echo; echo "=== $1"; read -rp "    [Enter] " _; }
wait_up() { for i in $(seq 1 60); do curl -sf "$URL/health" >/dev/null && return; sleep 2; done; echo "not up"; exit 1; }
# Ten home-page requests: status code, latency and where the recommendations came from.
probe() {
  for i in $(seq 1 10); do
    curl -s -o /dev/null -D - -w '%{http_code} %{time_total}s' "$URL/?user=user$i" \
      | awk 'tolower($1)=="x-recs-source:"{src=$2} /^[0-9]{3} /{code=$0} END{printf "  %s  recs=%s\n", code, src}' | tr -d '\r'
  done
}
up() { BREAKER=$1 $S2 up -d --build --force-recreate >/dev/null 2>&1; wait_up; }

step "1. Start the service split (catalogue, recommendations, auth, Postgres) WITH the circuit breaker"
up on
probe

step "2. Chaos: stop the recommendations service"
$S2 stop recommendations >/dev/null 2>&1
probe
echo "  -> still HTTP 200: the breaker opened and the home page used the generic popular list (graceful degradation)"

step "3. Recover: start recommendations again (breaker half-opens after 10 s)"
$S2 start recommendations >/dev/null 2>&1
sleep 12
probe

step "4. Same app WITHOUT the circuit breaker"
up off
probe

step "5. Chaos: stop the recommendations service again"
$S2 stop recommendations >/dev/null 2>&1
probe
echo "  -> HTTP 502: one failed dependency now breaks the whole home page (cascading failure)"

step "6. Clean up"
$S2 down >/dev/null 2>&1
echo "  done"
