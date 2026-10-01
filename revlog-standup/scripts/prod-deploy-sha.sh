#!/usr/bin/env bash
# Prints the git sha currently deployed to prod for txt-server and txt-client,
# then (optionally) reports whether each given commit is included in it.
# Usage: prod-deploy-sha.sh [commit ...]
# Requires: aws CLI with prod read access, a git checkout with origin fetched.
set -euo pipefail
CLUSTER=ecs-cluster-ue1-p-main
# macOS /bin/bash is 3.2: no associative arrays, so one var per service.
sha_for() {
  td=$(aws ecs describe-services --cluster "$CLUSTER" --services "ecs-service-ue1-p-$1" \
        --query 'services[0].taskDefinition' --output text)
  img=$(aws ecs describe-task-definition --task-definition "$td" \
        --query 'taskDefinition.containerDefinitions[0].image' --output text)
  echo "${img##*:}"
}
SHA_SERVER=$(sha_for txt-server); echo "txt-server $SHA_SERVER"
SHA_CLIENT=$(sha_for txt-client); echo "txt-client $SHA_CLIENT"
[ $# -eq 0 ] && exit 0
git fetch -q origin main
for c in "$@"; do
  for pair in "txt-server=$SHA_SERVER" "txt-client=$SHA_CLIENT"; do
    svc=${pair%%=*}; sha=${pair#*=}
    if git merge-base --is-ancestor "$c" "$sha" 2>/dev/null; then
      echo "$c $svc deployed"
    else
      echo "$c $svc NOT deployed"
    fi
  done
done
