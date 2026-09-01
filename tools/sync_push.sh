# Note: this script is designed for a specific use_case and predominantly generated with AI assistannce. It is not suitable for general-purpose use without modification. Use at your own risk.

GATEWAY="user@gateway.com"
MACHINE_B="user@machine_ip"

FULL_SCAN=0
DRY_RUN=0
CONTROL_PATH=""
TMPDIR_SYNC=""
MASTER_STARTED=0
MAX_RETRIES=5

usage() {
    cat <<EOF
Usage: $0 <local_path> <destination_path> [--full-scan] [--dry-run]

  <local_path>         Local source directory (must exist, e.g. /home/user/lotus-data)
  <destination_path>   Absolute destination path on destination machine (e.g. /home/user/lotus-data)

Options:
  --full-scan          Fallback: plain rsync -W full scan (slow for 120k, no inventory diff)
  --dry-run            Show what would be transferred without copying
  -h, --help           Show this help

Default (no flag): inventory-diff mode
  1. Single MFA auth via ControlMaster (ProxyJump through $GATEWAY)
  2. Remote inventory: ssh find | sort
  3. Local inventory:  find | sort
  4. Diff: comm -23 -> rsync --files-from (only missing files)

Copies ALL files in the directory (no filetype filter).

Examples:
  $0 /home/user/lotus-data /home/user/lotus-data
  $0 /home/user/lotus-data /home/user/lotus-data --dry-run
  $0 /home/user/lotus-data /home/user/lotus-data --full-scan
EOF
}

cleanup() {
    local rc=$?
    if [[ -n "${TMPDIR_SYNC:-}" && -d "$TMPDIR_SYNC" ]]; then
        rm -rf "$TMPDIR_SYNC"
    fi
    if [[ "$MASTER_STARTED" -eq 1 && -n "$CONTROL_PATH" && -S "$CONTROL_PATH" ]]; then
        ssh -S "$CONTROL_PATH" -O exit "$MACHINE_B" 2>/dev/null || true
        echo "ControlMaster closed ($CONTROL_PATH)" >&2
    fi
    exit $rc
}
trap cleanup EXIT INT TERM

# --- argument parsing ---
if [[ $# -lt 2 ]]; then
    echo "Error: missing required arguments" >&2
    usage >&2
    exit 1
fi

LOCAL_PATH="$1"
DEST_PATH="$2"
shift 2

while [[ $# -gt 0 ]]; do
    case "$1" in
        --full-scan) FULL_SCAN=1; shift ;;
        --dry-run) DRY_RUN=1; shift ;;
        -h|--help) usage; exit 0 ;;
        *) echo "Error: unknown option '$1'" >&2; usage >&2; exit 1 ;;
    esac
done

if [[ ! -e "$LOCAL_PATH" ]]; then
    echo "Error: '$LOCAL_PATH' does not exist" >&2
    exit 1
fi

# Ensure LOCAL_PATH is a directory (inventory mode uses find -printf '%P')
if [[ ! -d "$LOCAL_PATH" ]]; then
    echo "Error: '$LOCAL_PATH' is not a directory (expected top-level folder with ~3000 files/dir)" >&2
    exit 1
fi

# DEST must be absolute
if [[ "$DEST_PATH" != /* ]]; then
    echo "Error: <destination_path> must be absolute (got '$DEST_PATH')" >&2
    exit 1
fi

# Strip trailing slashes (preserve root "/")
while [[ "$DEST_PATH" != "/" && "$DEST_PATH" == */ ]]; do DEST_PATH="${DEST_PATH%/}"; done

# Dependency preflight
for cmd in ssh rsync find sort comm; do
    command -v "$cmd" >/dev/null 2>&1 || { echo "Error: required '$cmd' not found in PATH" >&2; exit 1; }
done

# Normalize without trailing slash for find, keep original for rsync with trailing slash
LOCAL_PATH="$(realpath "$LOCAL_PATH")"

# Shell-quote DEST_PATH for safe embedding in remote sh -c commands
printf -v DEST_Q '%q' "$DEST_PATH"

# Count local files for confirmation prompt
LOCAL_FILE_COUNT=$(find "$LOCAL_PATH" -type f | wc -l | tr -d ' ')

echo "Source: $LOCAL_PATH/ ($LOCAL_FILE_COUNT files)" >&2
echo "Dest:   $MACHINE_B:$DEST_PATH/" >&2
read -r -p "Proceed with sync? [y/N] " _confirm
if [[ ! "$_confirm" =~ ^[Yy]$ ]]; then
    echo "Aborted." >&2
    exit 0
fi

# --- ControlMaster setup (single MFA) ---
# Use /tmp path to avoid 108-char socket limit; include PID for concurrency safety
CONTROL_PATH="${TMPDIR:-/tmp}/cm_sync_push_$$_${USER:-vap}.sock"
# Ensure no stale socket
rm -f "$CONTROL_PATH"

echo "Establishing ControlMaster via $GATEWAY -> $MACHINE_B (MFA prompt once)..." >&2
# Check if master already exists (unlikely with unique path, but handle)
if ssh -S "$CONTROL_PATH" -O check "$MACHINE_B" 2>/dev/null; then
    echo "Reusing existing ControlMaster $CONTROL_PATH" >&2
else
    # -fN backgrounds after auth; ControlPersist keeps it for the run only
    if ! ssh -o ControlMaster=auto -o ControlPath="$CONTROL_PATH" -o ControlPersist=600 \
           -o ServerAliveInterval=30 -o ServerAliveCountMax=5 -o IPQoS=throughput \
           -J "$GATEWAY" -M -fN "$MACHINE_B"; then
        echo "Error: failed to establish ControlMaster (MFA/auth failed)" >&2
        exit 1
    fi
    MASTER_STARTED=1
    echo "ControlMaster established: $CONTROL_PATH" >&2
    # Verify
    if ! ssh -S "$CONTROL_PATH" -O check "$MACHINE_B" 2>/dev/null; then
        echo "Error: ControlMaster not responding after establishment" >&2
        exit 1
    fi
fi

SSH_S=(ssh -S "$CONTROL_PATH" -o ServerAliveInterval=30 -o ServerAliveCountMax=5)
RSYNC_SSH="ssh -S '$CONTROL_PATH' -o ServerAliveInterval=30 -o ServerAliveCountMax=5 -o IPQoS=throughput"

# Shared rsync base flags
# --whole-file: skip delta checksums (critical over slow links)
# --no-compress: skip for already-compressed media; --partial --delay-updates for resume/robustness
RSYNC_BASE=(-avh --whole-file --no-compress --partial --partial-dir=.rsync-partial --delay-updates --timeout=60 --info=progress2 --human-readable)

if [[ "$DRY_RUN" -eq 1 ]]; then
    RSYNC_BASE+=(-n)
    echo "*** DRY-RUN mode: no data will be transferred ***" >&2
fi

if [[ "$FULL_SCAN" -eq 1 ]]; then
    echo "Mode: --full-scan (plain rsync -W, enumerates all 120k files over jump host)" >&2
    echo "Source: $LOCAL_PATH/" >&2
    echo "Dest:   $MACHINE_B:$DEST_PATH/" >&2
    # Ensure dest exists
    "${SSH_S[@]}" "$MACHINE_B" "mkdir -p $DEST_Q"
    # Retry with capped attempts reusing ControlMaster (no re-MFA)
    set +e
    tries=0
    until rsync "${RSYNC_BASE[@]}" -e "$RSYNC_SSH" "$LOCAL_PATH/" "$MACHINE_B:$DEST_PATH/"; do
        rc=$?
        if [[ "$rc" -eq 1 ]]; then
            echo "rsync syntax/usage error (rc=$rc), aborting." >&2
            exit "$rc"
        fi
        ((tries++))
        if (( tries >= MAX_RETRIES )); then
            echo "rsync failed after $tries retries (rc=$rc), aborting." >&2
            exit "$rc"
        fi
        echo "rsync exited $rc, retrying in 5s (attempt $tries/$MAX_RETRIES)..." >&2
        sleep 5
    done
    set -e
    echo "Full-scan sync complete." >&2
    exit 0
fi

# --- Default: inventory-diff mode ---
echo "Mode: inventory-diff (default, efficient for 120k append-only)" >&2
echo "Source: $LOCAL_PATH/" >&2
echo "Dest:   $MACHINE_B:$DEST_PATH/" >&2

TMPDIR_SYNC="$(mktemp -d "${TMPDIR:-/tmp}/sync_push.XXXXXX")"
LOCAL_LIST="$TMPDIR_SYNC/local.txt"
REMOTE_LIST="$TMPDIR_SYNC/remote.txt"
NEW_LIST="$TMPDIR_SYNC/new_files.txt"

echo "Step 1/4: Remote inventory (find + sort on MachineB)..." >&2
# mkdir -p before find so empty dest yields empty list, not error
# printf '%P' gives path relative to DEST; no filetype filter - copies all files
if ! "${SSH_S[@]}" "$MACHINE_B" "mkdir -p $DEST_Q && find $DEST_Q -type f -printf '%P\n' 2>/dev/null | LC_ALL=C sort" > "$REMOTE_LIST"; then
    ssh_rc=$?
    if ssh -S "$CONTROL_PATH" -O check "$MACHINE_B" 2>/dev/null; then
        echo "Warning: remote find failed (rc=$ssh_rc), treating as empty (new dest?)" >&2
        : > "$REMOTE_LIST"
    else
        echo "Error: SSH connection lost during remote inventory (rc=$ssh_rc), aborting." >&2
        exit "$ssh_rc"
    fi
fi
REMOTE_COUNT=$(wc -l < "$REMOTE_LIST" | tr -d ' ')
echo "  Remote files: $REMOTE_COUNT" >&2

echo "Step 2/4: Local inventory (find + sort)..." >&2
find "$LOCAL_PATH" -type f -printf '%P\n' 2>/dev/null | LC_ALL=C sort > "$LOCAL_LIST"
LOCAL_COUNT=$(wc -l < "$LOCAL_LIST" | tr -d ' ')
echo "  Local files: $LOCAL_COUNT" >&2

echo "Step 3/4: Diff (comm -23)..." >&2
comm -23 "$LOCAL_LIST" "$REMOTE_LIST" > "$NEW_LIST" || true
NEW_COUNT=$(wc -l < "$NEW_LIST" | tr -d ' ')
echo "  Missing on remote: $NEW_COUNT / $LOCAL_COUNT" >&2

if [[ "$NEW_COUNT" -eq 0 ]]; then
    echo "All files already present on MachineB. Nothing to do." >&2
    exit 0
fi

# Show sample of what will be synced (first 10)
echo "  Sample missing files (first 10):" >&2
head -n 10 "$NEW_LIST" | sed 's/^/    /' >&2
if [[ "$NEW_COUNT" -gt 10 ]]; then
    echo "    ... and $((NEW_COUNT - 10)) more" >&2
fi

# Ensure dest exists (redundant but safe)
"${SSH_S[@]}" "$MACHINE_B" "mkdir -p $DEST_Q"

echo "Step 4/4: Pushing $NEW_COUNT files via rsync --files-from (single stream, resume within MFA session)..." >&2
# Use trailing slash on source so %P paths resolve
RSYNC_FROM_ARGS=(-e "$RSYNC_SSH" --files-from="$NEW_LIST")

# Retry loop reusing ControlMaster with capped attempts
set +e
tries=0
until rsync "${RSYNC_BASE[@]}" "${RSYNC_FROM_ARGS[@]}" "$LOCAL_PATH/" "$MACHINE_B:$DEST_PATH/"; do
    rc=$?
    if [[ "$rc" -eq 1 ]]; then
        echo "rsync syntax/usage error (rc=$rc), aborting." >&2
        exit "$rc"
    fi
    ((tries++))
    if (( tries >= MAX_RETRIES )); then
        echo "rsync failed after $tries retries (rc=$rc), aborting." >&2
        exit "$rc"
    fi
    # Re-check control master
    if ! ssh -S "$CONTROL_PATH" -O check "$MACHINE_B" 2>/dev/null; then
        echo "Error: ControlMaster died, need re-auth. Aborting." >&2
        exit "$rc"
    fi
    echo "rsync exited $rc (likely slow-link timeout), retrying in 5s (attempt $tries/$MAX_RETRIES)..." >&2
    sleep 5
done
set -e

echo "Inventory-diff sync complete: $NEW_COUNT files pushed." >&2

# Optional verification: re-count remote (quick)
if [[ "$DRY_RUN" -eq 0 ]]; then
    echo "Verifying..." >&2
    REMOTE_AFTER=$("${SSH_S[@]}" "$MACHINE_B" "find $DEST_Q -type f -printf '%P\n' 2>/dev/null | wc -l" | tr -d ' \r\n')
    echo "  Remote now: $REMOTE_AFTER / Local: $LOCAL_COUNT" >&2
    if [[ "$REMOTE_AFTER" -eq "$LOCAL_COUNT" ]]; then
        echo "Verification OK: counts match." >&2
    else
        echo "Verification: counts differ (remote $REMOTE_AFTER != local $LOCAL_COUNT) - possible partial transfer." >&2
    fi
fi
