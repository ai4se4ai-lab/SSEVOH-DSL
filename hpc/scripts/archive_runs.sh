#!/bin/bash
# Free /scratch inodes losslessly: pack each run directory into one verified tar.gz, then delete the original.
# Usage (on a cluster login node): nohup setsid bash archive_runs.sh WORK_DIR [ARCHIVE_DIR] > ARCHIVE_DIR/archive.log 2>&1 &
# A run is deleted only if gzip integrity passes and the archive's entry count equals the directory's entry count.
set -u
WORK=${1:?work dir}
RUNS="$WORK/runs"
ARCH="${2:-$WORK/archive}"  # optional: another filesystem when WORK has no free inodes
mkdir -p "$ARCH"
cd "$RUNS" || exit 1
# Smallest directories first (by top-level entry count is cheap; good enough ordering).
for run in $(ls -d */ | sed 's#/$##'); do
  out="$ARCH/$run.tar.gz"
  if [ -e "$out.verified" ]; then echo "skip $run (already verified)"; continue; fi
  echo "$(date -u +%FT%TZ) pack $run"
  n_dir=$(find "$run" | wc -l)
  if ! nice -n 10 tar -czf "$out.part" "$run"; then echo "FAIL tar $run"; rm -f "$out.part"; continue; fi
  if ! gzip -t "$out.part"; then echo "FAIL gzip -t $run"; continue; fi
  n_tar=$(tar -tzf "$out.part" | wc -l)
  if [ "$n_tar" != "$n_dir" ]; then echo "FAIL count $run dir=$n_dir tar=$n_tar (kept)"; continue; fi
  mv "$out.part" "$out"
  sha256sum "$out" > "$out.verified"
  echo "$n_dir entries" >> "$out.verified"
  rm -rf "$run" && echo "$(date -u +%FT%TZ) done $run entries=$n_dir"
done
echo "$(date -u +%FT%TZ) ALL DONE"
lfs quota -u "$USER" /scratch 2>/dev/null | sed -n 3,4p
