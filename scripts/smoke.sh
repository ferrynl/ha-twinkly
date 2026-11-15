#!/usr/bin/env bash
set -euo pipefail

dir="$1"
http_port="$2"
name="twinkly-smoke-$http_port"
data="$(mktemp -d)"
cleanup() {
  docker rm -f "$name" >/dev/null 2>&1 || true
  rm -rf "$data"
}
trap cleanup EXIT

cat > "$data/options.json" <<'JSON'
{"ddp_source":"127.0.0.1","discovery_broadcast":"255.255.255.255","fps":20,"media_player":""}
JSON

docker build --tag "$name" "$dir"
docker run --detach --name "$name" --network host -v "$data:/data" "$name"
for _ in $(seq 1 30); do
  if [[ "$(curl --silent --max-time 2 --output /dev/null --write-out '%{http_code}' "http://127.0.0.1:$http_port/")" == 403 ]]; then
    # Direct requests are rejected by HA ingress middleware after the app starts.
    test "$(docker inspect --format '{{.State.Running}}' "$name")" = true
    exit 0
  fi
  sleep 1
done
docker logs "$name"
exit 1
