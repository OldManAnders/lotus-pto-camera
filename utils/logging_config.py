import csv
import io
import json
import logging
import os
import sys
from datetime import datetime

EVENT_NAMES = frozenset({
    "routine_start", "attempt_failed", "routine_done", "all_retries_failed",
    "unifi_initialization", "unifi_initialization_failure", "unifi_interface", "unifi_hardware",
    "poe_control", "poe_control_success", "poe_control_failure", "poe_camera_warmup",
    "wiper", "wiper_failed", "capture", "capture_failed",
    "lights_set", "lights", "set_leds_error",
    "image_saved", "image_save_failed", "grab_failed", "capture_error",
    "camera_reconnected", "reconnect_failed", "camera_settings_updated", "settings_update_error",
    "metadata_saved", "metadata_save_failed",
    "config_loading", "config_parsing", "interrupted", "exception", "abort",
    "ping", "get_request", "http_get_failed", "http_post_failed",
    "wipe_error", "reset_error", "microcontroller_initialized", "camera_handler_initialized",
    "logger_initialization", "camera_sleep", "camera_wake", "camera_stopped", "bad_config_type",
})

_DETAILS_TRUNCATE = 4096
_HUMAN_DETAILS_TRUNCATE = 300


def _normalize_details(details):
    if details is None:
        return {}
    if isinstance(details, dict):
        return details
    if isinstance(details, str):
        return {"note": details} if details else {}
    return {"note": str(details)}


def _details_json(details):
    d = _normalize_details(details)
    try:
        s = json.dumps(d, separators=(",", ":"), ensure_ascii=False, default=str)
    except Exception:
        s = json.dumps({"note": str(details)[:_DETAILS_TRUNCATE]}, separators=(",", ":"))
    if len(s) > _DETAILS_TRUNCATE:
        s = s[:_DETAILS_TRUNCATE]
    return s.replace("\r", " | ").replace("\n", " | ")


def _iso_now():
    return datetime.now().astimezone().isoformat(timespec="milliseconds")


class CSVFormatter(logging.Formatter):
    """Strict CSV: timestamp,level,run_id,rig,component,event,message,details_json."""

    COLUMNS = ["timestamp", "level", "run_id", "rig", "component", "event", "message", "details_json"]

    def format(self, record: logging.LogRecord) -> str:
        timestamp = _iso_now()
        level = record.levelname
        run_id = str(getattr(record, "run_id", "") or "")
        rig = str(getattr(record, "rig", "") or "")
        component = str(getattr(record, "component", "") or "")
        event = str(getattr(record, "event", "") or "")
        try:
            message = record.getMessage()
        except Exception:
            message = ""
        message = (message or "").replace("\r", " | ").replace("\n", " | ")
        details_json = _details_json(getattr(record, "details", None))
        buf = io.StringIO()
        writer = csv.writer(buf, quoting=csv.QUOTE_MINIMAL)
        writer.writerow([timestamp, level, run_id, rig, component, event, message, details_json])
        return buf.getvalue().strip("\r\n")


class HumanFormatter(logging.Formatter):
    """Single-line human output for stdout / journal."""

    def format(self, record: logging.LogRecord) -> str:
        timestamp = _iso_now()
        level = record.levelname
        rig = str(getattr(record, "rig", "") or "")
        component = str(getattr(record, "component", "") or "")
        event = str(getattr(record, "event", "") or "")
        run_id = str(getattr(record, "run_id", "") or "")
        try:
            message = record.getMessage()
        except Exception:
            message = ""
        message = (message or "").replace("\r", " | ").replace("\n", " | ")
        details = _details_json(getattr(record, "details", None))
        if len(details) > _HUMAN_DETAILS_TRUNCATE:
            details = details[:_HUMAN_DETAILS_TRUNCATE] + "..."
        where = f"{rig}/{component}" if rig and component else (rig or component or record.name)
        return f'{timestamp} {level} [{where}] event={event} run={run_id} msg="{message}" details={details}'


class _ContextFilter(logging.Filter):
    def __init__(self, run_id="", rig=""):
        super().__init__()
        self.run_id = run_id
        self.rig = rig

    def filter(self, record):
        if not getattr(record, "run_id", None):
            record.run_id = self.run_id or os.environ.get("LOTUS_RUN_ID", "")
        if not getattr(record, "rig", None):
            record.rig = self.rig
        if not hasattr(record, "component"):
            record.component = ""
        if not hasattr(record, "event"):
            record.event = ""
        if not hasattr(record, "details"):
            record.details = {}
        return True


def configure_logging(level=logging.INFO, logfile: str = None, run_id: str = "", rig: str = ""):
    root = logging.getLogger()
    for h in list(root.handlers):
        root.removeHandler(h)
    root.setLevel(level)

    if not run_id:
        run_id = os.environ.get("LOTUS_RUN_ID", "")

    filt = _ContextFilter(run_id=run_id, rig=rig)

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(HumanFormatter())
    stream_handler.addFilter(filt)
    root.addHandler(stream_handler)

    if logfile:
        new_file = (not os.path.exists(logfile)) or os.path.getsize(logfile) == 0
        fh = logging.FileHandler(logfile)
        fh.setFormatter(CSVFormatter())
        fh.addFilter(filt)
        root.addHandler(fh)
        if new_file:
            try:
                with open(logfile, "a", newline="") as f:
                    writer = csv.writer(f)
                    writer.writerow(CSVFormatter.COLUMNS)
            except OSError:
                pass

    for noisy in ("urllib3", "requests", "PIL"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str, component: str = None, rig: str = None) -> logging.LoggerAdapter:
    logger = logging.getLogger(name)

    class _Adapter(logging.LoggerAdapter):
        def process(self, msg, kwargs):
            extra = kwargs.get("extra") or {}
            merged = dict(self.extra) if self.extra else {}
            merged.update(extra)
            if "component" not in merged or not merged["component"]:
                merged["component"] = component or ""
            if rig is not None and not merged.get("rig"):
                merged["rig"] = rig
            kwargs["extra"] = merged
            return msg, kwargs

    return _Adapter(logger, {"component": component or "", "rig": rig or ""})
