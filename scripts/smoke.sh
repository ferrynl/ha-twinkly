#!/usr/bin/env bash
set -euo pipefail

dir="$1"
http_port="$2"
name="twinkly-smoke-$http_port"
data="$name-data"
cleanup() {
  docker rm -f "$name" >/dev/null 2>&1 || true
  docker volume rm "$data" >/dev/null 2>&1 || true
}
trap cleanup EXIT

if [[ "${3:-}" != "" ]]; then
  image="$3"
else
  image="$name"
  docker build --tag "$image" "$dir"
fi
docker volume create "$data" >/dev/null
# Seed root-owned Supervisor settings and state as on an existing installation.
docker run --rm -i -v "$data:/data" --entrypoint /bin/sh "$image" -ec '
  umask 077
  cp /dev/stdin /data/options.json
  mkdir /data/gif-library
  printf "[]" > /data/devices.json
' <<'JSON'
{"ddp_source":"127.0.0.1","discovery_broadcast":"255.255.255.255","fps":20,"media_player":""}
JSON

docker run --detach --name "$name" --network host -v "$data:/data" "$image"
for _ in $(seq 1 30); do
  if [[ "$(curl --silent --max-time 2 --output /dev/null --write-out '%{http_code}' "http://127.0.0.1:$http_port/")" == 403 ]]; then
    test "$(curl --fail --silent --max-time 2 "http://127.0.0.1:$http_port/healthz")" = OK
    # Direct requests are rejected by HA ingress middleware after the app starts.
    test "$(docker inspect --format '{{.State.Running}}' "$name")" = true
    docker exec --user 10001:10001 "$name" /bin/sh -ec '
      grep -Eq "^Uid:[[:space:]]+10001[[:space:]]+10001" /proc/1/status
      grep -Eq "^NoNewPrivs:[[:space:]]+1$" /proc/1/status
      test -r /data/options.json
      test -w /data/devices.json
      test -w /data/gif-library
      temp=$(mktemp /data/smoke.XXXXXX)
      rm "$temp"
    '
    exit 0
  fi
  sleep 1
done
docker logs "$name"
exit 1
