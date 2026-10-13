#!/usr/bin/env bash
# Ultimate AI - Kaggle one-cell setup (Linux, NVIDIA GPU, e.g. T4 x2).
# Idempotent: safe to re-run any time. Requires Internet enabled on the notebook.
set -u
ROOT="$(cd "$(dirname "$0")" && pwd)"
HOST="http://127.0.0.1:11434"

echo "=============================================================="
echo "  U L T I M A T E   A I   -   KAGGLE SETUP"
echo "=============================================================="

echo "[1/6] Python dependencies"
python -m pip install -q -r "$ROOT/requirements.txt" 2>&1 | tail -1 || {
    echo "  pip install failed - check Internet is enabled on the notebook"; exit 1; }

echo "[2/6] Ollama"
if ! command -v ollama >/dev/null 2>&1; then
    curl -fsSL https://ollama.com/install.sh | sh || { echo "  ollama install failed"; exit 1; }
else
    echo "  ollama already installed: $(ollama --version 2>/dev/null || echo '?')"
fi

echo "[3/6] Daemon with max-context env (flash attention + q8_0 KV cache)"
export OLLAMA_FLASH_ATTENTION=1
export OLLAMA_KV_CACHE_TYPE=q8_0
if curl -s --max-time 3 "$HOST/api/ps" >/dev/null 2>&1; then
    echo "  daemon already running - if it was started WITHOUT the env vars above,"
    echo "  the 65536 context proof will simply keep the safe floor (auto-healing)."
else
    nohup ollama serve > /tmp/ultimate-ai-ollama.log 2>&1 &
    for i in $(seq 1 60); do
        curl -s --max-time 2 "$HOST/api/ps" >/dev/null 2>&1 && break
        sleep 2
    done
    curl -s --max-time 3 "$HOST/api/ps" >/dev/null 2>&1 || { echo "  daemon did not come up - see /tmp/ultimate-ai-ollama.log"; exit 1; }
    echo "  daemon up (GPU: $(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | tr '\n' ' '))"
fi

echo "[4/6] Model pull (skips if already present)"
ollama pull gpt-oss:20b || { echo "  pull failed"; exit 1; }

echo "[5/6] Warm the model (stays resident 24h)"
curl -s --max-time 600 "$HOST/api/generate" \
    -d '{"model":"gpt-oss:20b","prompt":"ping","keep_alive":"24h","options":{"num_predict":1}}' > /dev/null
echo "  warm ok"

echo "[6/6] Real-prompt context proof (ADOPT writes .ctx-proof.json -> 65536 window)"
python "$ROOT/tools/ctx_proof.py" || echo "  (proof inconclusive - the harness keeps the proven floor; everything still works)"

echo ""
echo "SETUP COMPLETE - now in the next notebook cell:"
echo "    import sys; sys.path.insert(0, '$ROOT')"
echo "    from kaggle_bridge import UltimateAI"
echo "    ai = UltimateAI()"
echo "    ai.run('your goal here')"
