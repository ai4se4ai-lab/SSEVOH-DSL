#!/usr/bin/env bash
# Only inference/setup stages need the local server. It is isolated per allocation.
if [[ "$STAGE" == "setup" || "$STAGE" == "llm" ]]; then
  if [[ ! -x "$OLLAMA_BIN" ]]; then
    log_error "Ollama binary missing: stage a verified runtime before submitting"
    return 1
  fi
  # Libraries on shared scratch can exceed Ollama's fixed GPU discovery watchdog on a cold node.
  # Stage the same binary/libraries on node-local disk; no runtime version or model is substituted.
  runtime_source=$(cd "$(dirname "$OLLAMA_BIN")/.." && pwd)
  runtime_local="${SLURM_TMPDIR:?Slurm node-local storage required}/ssevoh-ollama"
  mkdir -p "$runtime_local"
  rsync -a --exclude=vulkan "$runtime_source/" "$runtime_local/" || return 1
  export OLLAMA_BIN="$runtime_local/bin/ollama"
  export OLLAMA_VULKAN=0 OLLAMA_LOAD_TIMEOUT=10m
  python "$REPO_DIR/experiments/scripts/gpu_bootstrap.py" --runtime-root "$runtime_local" \
    --output "$LOG_ROOT/env/cuda_preflight_${JOB_TAG}.json" || return 1
  python "$REPO_DIR/experiments/scripts/runtime.py" seed || return 1
  export OLLAMA_HOST="127.0.0.1:$((20000 + SLURM_JOB_ID % 30000))"
  export OLLAMA_NUM_PARALLEL=1 OLLAMA_MAX_LOADED_MODELS=1 OLLAMA_NO_CLOUD=1
  export OLLAMA_KEEP_ALIVE=2m
  "$OLLAMA_BIN" serve > "$LOG_ROOT/env/ollama_${JOB_TAG}.log" 2>&1 &
  SERVICE_PIDS+=("$!")
  curl --fail --silent --retry 12 --retry-connrefused --retry-delay 2 \
       --retry-max-time 30 "http://$OLLAMA_HOST/api/version" > /dev/null || return 1
fi
