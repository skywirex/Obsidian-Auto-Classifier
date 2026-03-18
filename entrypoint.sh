#!/bin/sh
set -eu

# --- 1. STARTING ---
echo "[INFO] Entrypoint starting..."
LOOP_HOUR=${LOOP_HOUR:-24}
echo "[INFO] LOOP_HOUR=${LOOP_HOUR}"

# --- 2. CHECK REQUIRED ENV ---
if [ -z "${GEMINI_API_KEY:-}" ]; then
    echo "[ERROR] GEMINI_API_KEY is not set. Please set this secret before running." >&2
    exit 1
fi

if [ -z "${VAULT_PATH:-}" ]; then
    echo "[WARN] VAULT_PATH is not set, defaulting to /app/vault"
    export VAULT_PATH="/app/vault"
else
    echo "[INFO] VAULT_PATH=${VAULT_PATH}"
fi

echo "[INFO] GEMINI_MODEL=${GEMINI_MODEL:-gemini-2.5-flash}"

# --- 3. Start loop script ---
exec /app/scripts/oac.sh