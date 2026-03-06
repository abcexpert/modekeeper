#!/usr/bin/env bash
set -Eeuo pipefail

if [[ $# -ne 1 ]]; then
  echo "usage: $0 <oversized_requests|replica_overprovisioning|burst_traffic>" >&2
  exit 2
fi

case "$1" in
  oversized_requests)
    echo "manifests/oversized-requests-productcatalogservice.yaml"
    ;;
  replica_overprovisioning)
    echo "manifests/replica-overprovisioning-emailservice.yaml"
    ;;
  burst_traffic)
    echo "manifests/burst-traffic-loadgenerator-job.yaml"
    ;;
  *)
    echo "unknown scenario: $1" >&2
    exit 2
    ;;
esac
