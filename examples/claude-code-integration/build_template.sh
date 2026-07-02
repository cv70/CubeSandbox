#!/usr/bin/env bash
set -euo pipefail

IMAGE="${IMAGE:-cubesandbox-claude-code:latest}"
REGISTRY_IMAGE="${REGISTRY_IMAGE:-}"
WRITABLE_LAYER_SIZE="${WRITABLE_LAYER_SIZE:-4G}"

docker build -t "${IMAGE}" "$(dirname "$0")"

if [[ -n "${REGISTRY_IMAGE}" ]]; then
  docker tag "${IMAGE}" "${REGISTRY_IMAGE}"
  docker push "${REGISTRY_IMAGE}"
  IMAGE="${REGISTRY_IMAGE}"
fi

cubemastercli tpl create-from-image \
  --image "${IMAGE}" \
  --writable-layer-size "${WRITABLE_LAYER_SIZE}" \
  --expose-port 49983 \
  --probe 49983 \
  --probe-path /health
