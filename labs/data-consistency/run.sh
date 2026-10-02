#!/usr/bin/env bash
set -Eeuo pipefail
python3 -c 'import sys; sys.exit("Optimized Python is forbidden" if sys.flags.optimize else 0)' 
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
case "${1:-all}" in all|d1|d2|d3|d4|d5) chapter="${1:-all}";; *) echo 'Use: bash run.sh [all|d1|d2|d3|d4|d5]' >&2; exit 64;; esac
# Random names are never supplied by callers. No existing DB/Redis target accepted.
owner="$(python3 -c 'import uuid; print(uuid.uuid4().hex)')"
export LAB_OWNER="$owner"
project="ks-data-${owner}"
out="$PWD/results/$owner"
mkdir -p "$out"
printf '{"status":"NOT_RUN","reason":"starting isolated containers"}\n' > "$out/result.json"
compose=(docker compose --env-file infra/versions.env --project-name "$project" -f compose.yaml)
cleanup() {
  rc=$?
  trap - EXIT INT TERM
  set +e
  timeout --kill-after=5s 30s "${compose[@]}" logs --no-color > "$out/containers.log" 2>&1
  logs_rc=$?
  timeout --kill-after=5s 15s "${compose[@]}" ps -a > "$out/containers.txt" 2>&1
  ps_rc=$?
  # Exact project only. Never prune, list/delete unrelated resources or volumes.
  timeout --kill-after=5s 45s "${compose[@]}" down --volumes --timeout 10 > "$out/cleanup.log" 2>&1
  cleanup_rc=$?
  printf 'run_exit_code=%s\ncleanup_exit_code=%s\nlogs_exit_code=%s\nps_exit_code=%s\n' "$rc" "$cleanup_rc" "$logs_rc" "$ps_rc" > "$out/exit-codes.txt"
  python3 - "$out/result.json" "$rc" "$cleanup_rc" "$logs_rc" "$ps_rc" <<'PYRESULT'
import json,sys
from pathlib import Path
p=Path(sys.argv[1]); report=json.loads(p.read_text())
run_rc,cleanup_rc,logs_rc,ps_rc=map(int,sys.argv[2:])
report["run_exit_code"]=run_rc
report["cleanup_exit_code"]=cleanup_rc
report["logs_exit_code"]=logs_rc
report["ps_exit_code"]=ps_rc
if run_rc or cleanup_rc or logs_rc or ps_rc:
    report["status"]="FAIL"
    report.setdefault("error", "Run, evidence capture or scoped cleanup failed; inspect logs")
p.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
PYRESULT
  summary_rc=$?
  echo "Evidence: $out"
  if [ "$rc" -eq 0 ] && [ "$cleanup_rc" -ne 0 ]; then exit "$cleanup_rc"; fi
  if [ "$rc" -eq 0 ] && [ "$summary_rc" -ne 0 ]; then exit "$summary_rc"; fi
  if [ "$rc" -eq 0 ] && [ "$logs_rc" -ne 0 ]; then exit "$logs_rc"; fi
  if [ "$rc" -eq 0 ] && [ "$ps_rc" -ne 0 ]; then exit "$ps_rc"; fi
  exit "$rc"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
python3 --version > "$out/python-version.txt" 2>&1
timeout --kill-after=5s 15s docker version > "$out/docker-version.txt" 2>&1
timeout --kill-after=5s 15s docker compose version > "$out/compose-version.txt" 2>&1
timeout --kill-after=5s 240s "${compose[@]}" up -d --wait --wait-timeout 180 > "$out/start.log" 2>&1
mysql_id="$(timeout --kill-after=5s 15s "${compose[@]}" ps -q mysql)"
redis_id="$(timeout --kill-after=5s 15s "${compose[@]}" ps -q redis)"
for id in "$mysql_id" "$redis_id"; do
  timeout --kill-after=5s 15s docker inspect --format '{{.Image}}' "$id" >> "$out/image-ids.txt"
  image_id="$(timeout --kill-after=5s 15s docker inspect --format '{{.Image}}' "$id")"
  timeout --kill-after=5s 15s docker image inspect --format '{{json .RepoDigests}}' "$image_id" >> "$out/image-digests.txt"
done
# Pass only container IDs belonging to the exact owned project.
python3 lab.py --mysql "$mysql_id" --redis "$redis_id" --owner "$owner" --out "$out" --chapter "$chapter"
