#!/bin/bash

#Retry counter
MAX_RETRIES=3
count=0
retry_timer=30

# Setup log dir
OUTPUTDIR="/home/aau/lotus-data/"
mkdir -p "$OUTPUTDIR"
LOGDIR="$OUTPUTDIR/logs/"
mkdir -p "$LOGDIR"
LOGFILE="$LOGDIR/$(date +%F).csv"
RUN_ID="$(date +%Y%m%d-%H%M%S)-rig1"
export LOTUS_RUN_ID="$RUN_ID"
# Set to 1 to skip UniFi PoE control (assume camera pre-powered)
DISABLE_UNIFI="${DISABLE_UNIFI:-0}"

# Setup Logging function: human line to stdout only (journal).
# CSV rows are owned by main.py via its FileHandler (timelines/uptime);
# inspect the journal for shell retry/attempt lines.
log_system() {
    event="$1"
    shift || true
    details="$*"
    ts=$(date +%Y-%m-%dT%H:%M:%S.%3N%z)
    echo "$ts INFO [rig1/system] event=$event run=$RUN_ID msg=\"$details\" details={}"
}

# Start logging service (no exec redirect: Python FileHandler owns the CSV, journal owns stdout)
log_system "routine_start" "Routine capture service started"

# Set cwd and python env path
cd /home/aau/lotus-pto-camera/
PYTHON_BIN="./venv/bin/python3"

# Keep retrying until
until [ $count -ge $MAX_RETRIES ]; do
    # Image acquisition begins
    # shellcheck disable=SC2086
    $PYTHON_BIN main.py rig1 --output_path $OUTPUTDIR --log_level debug --log-file $LOGFILE --run-id $RUN_ID \
    -c default demoLed1Full \
    -c default demoLed2Full \
    -c default demoLed3Full \
    -c default demoAll \
    -c 20pAutoExp demoLed1Full \
    -c 20pAutoExp demoLed2Full \
    -c 20pAutoExp demoLed3Full \
    -c 20pAutoExp demoAll \
    -c default lightsOff \
    -c 20pAutoExp lightsOff
    rc=$?
    if [ $rc -eq 0 ]; then
        log_system "routine_done" "Capture routine completed"
        break
    fi

    count=$((count+1))
    log_system "attempt_failed" "Attempt $count/$MAX_RETRIES failed (rc=$rc), retrying in 60 seconds..."
    sleep $retry_timer
done

if [ $count -eq $MAX_RETRIES ]; then
    log_system "all_retries_failed" "All $MAX_RETRIES retries failed, exiting with error"
    exit 1
fi
