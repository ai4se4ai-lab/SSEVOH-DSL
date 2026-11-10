#!/usr/bin/env bash
# Interactive login is the only step requiring the user's MFA. No credential caching.
set -euo pipefail
root=$(cd "$(dirname "$0")/../.." && pwd)
if [[ $# -eq 0 ]]; then
  echo "Usage: bash hpc/scripts/ssh-session.sh connect all   # complete MFA"
  echo "       bash hpc/scripts/ssh-session.sh status all    # inspect existing sessions"
  exit 0
fi
cluster=${2:-all}
user=${ALLIANCE_USER:-mbabaei}
mkdir -p "$root/hpc/.ssh"
chmod 700 "$root/hpc/.ssh"
case "$cluster" in fir|narval|rorqual) clusters=("$cluster");; all) clusters=(fir narval rorqual);; *) echo 'cluster must be fir, narval, rorqual, all' >&2; exit 2;; esac
failed=0
for site in "${clusters[@]}"; do
  socket="$root/hpc/.ssh/$site"
  host="$user@$site.alliancecan.ca"
  opts=(-o StrictHostKeyChecking=yes -o ConnectTimeout=15 -o ServerAliveInterval=60 -o ServerAliveCountMax=3 -o ControlPath="$socket")
  case "${1:-status}" in
    connect) ssh "${opts[@]}" -o ControlMaster=auto -o ControlPersist=12h -MNf "$host" || failed=1 ;;
    status) echo "$site:"; ssh "${opts[@]}" -O check "$host" || failed=1 ;;
    close) ssh "${opts[@]}" -O exit "$host" || failed=1 ;;
    *) echo 'usage: ssh-session.sh connect|status|close [fir|narval|rorqual|all]' >&2; exit 2;;
  esac
done

exit "$failed"
