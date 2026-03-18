#!/bin/sh
# /app/scripts/oac.sh

# Configurable interval: LOOP_HOUR defaults to 24 (hours)
LOOP_HOUR="${LOOP_HOUR:-24}"
if ! echo "$LOOP_HOUR" | grep -Eq '^[0-9]+$'; then
    echo "ERROR: LOOP_HOUR must be a positive integer. Got: '$LOOP_HOUR'" >&2
    exit 1
fi
LOOP_SECONDS=$((LOOP_HOUR * 3600))

echo "Using LOOP_HOUR: ${LOOP_HOUR}h -> ${LOOP_SECONDS}s"

echo "oac started — running every ${LOOP_SECONDS} seconds"

while true; do
    echo "=== $(date '+%Y-%m-%d %H:%M:%S %Z') === Running main.py (loop=${LOOP_SECONDS}s)"

    /app/venv/bin/python /app/main.py
    EXIT_CODE=$?

    if [ $EXIT_CODE -eq 0 ]; then
        echo "main.py completed successfully"
    else
        echo "main.py failed with exit code $EXIT_CODE"
    fi

    echo "Sleeping ${LOOP_SECONDS} seconds..."
    sleep "$LOOP_SECONDS"
done