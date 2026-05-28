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
LOGFILE="$LOGDIR/$(date +%Y-%m-%d).log"

# Setup Logging function (to collate with python)
log_system() {
    echo "$(date +%Y-%m-%d%H:%M:%S),[SYSTEM],$*"
}

# Apply logging to all stdouts (Bash and Python)
exec >> "$LOGFILE" 2>&1 #Buffered logging to file
#exec > >(awk '{ print $0; fflush(); }' >> "$LOGFILE") 2>&1 # unbuffered logging (for real-time logging and monitoring)

# Start logging service
log_system "Routine capture service started"

# Set cwd and python env path
cd /home/aau/LOTUS-PTO_studentwork/
PYTHON_BIN="./venv/bin/python3"

# Keep retrying until
until [ $count -ge $MAX_RETRIES ]; do
    # Image acquisition begins
    $PYTHON_BIN main.py any --output_path $OUTPUTDIR -c prototypeLongExp bright -c prototypeLongExp dim
    break

    count=$((count+1))
    log_system "Attempt $count/$MAX_RETRIES failed, retrying in 60 seconds..."
    sleep $retry_timer
done

if [ $count -eq $MAX_RETRIES ]; then
    log_system "All $MAX_RETRIES retries failed, exiting with error"
    exit 1
fi
