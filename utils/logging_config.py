"""Configure structured CSV and human-readable logging.

The root logger receives a single-line ``HumanFormatter`` on stdout and, when a
log file is supplied, a strict columnar ``CSVFormatter`` appended to that file.
Each record carries the structured context fields ``run_id``, ``rig``,
``component``, ``event``, and ``details``; ``_ContextFilter`` injects defaults
for any that are missing, and event names are drawn from ``EVENT_NAMES``.
"""

import csv
import io
import json
import logging
import os
import sys
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

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

_LEVEL_NAMES = {
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "warning": logging.WARNING,
    "warn": logging.WARNING,
    "error": logging.ERROR,
    "critical": logging.CRITICAL,
    "fatal": logging.CRITICAL,
}


def _normalize_level(level: Any) -> int:
    """Normalize/Convert int or name to a logging level to an integer."""
    if isinstance(level, str):
        return _LEVEL_NAMES.get(level.strip().lower(), logging.INFO)
    return level


def _normalize_details(details: Any) -> Dict[str, Any]:
    """Coerce an arbitrary detail payload into a dictionary. """
    if details is None:
        return {}
    if isinstance(details, dict):
        return details
    if isinstance(details, str):
        return {"note": details} if details else {}
    return {"note": str(details)}


def _details_json(details: Any) -> str:
    """Serialize details to a single-line JSON string.

    The result is truncated to ``_DETAILS_TRUNCATE`` characters and has embedded
    carriage returns and newlines replaced with ``" | "`` so it stays on one CSV
    row.

    Args:
        details: Arbitrary detail payload accepted by ``_normalize_details``.

    Returns:
        A compact JSON string safe for a single CSV field.
    """
    d = _normalize_details(details)
    try:
        s = json.dumps(d, separators=(",", ":"), ensure_ascii=False, default=str)
    except Exception:
        s = json.dumps({"note": str(details)[:_DETAILS_TRUNCATE]}, separators=(",", ":"))
    if len(s) > _DETAILS_TRUNCATE:
        s = s[:_DETAILS_TRUNCATE]
    return s.replace("\r", " | ").replace("\n", " | ")


def _iso_now() -> str:
    """Return the current local time as an ISO 8601 string."""
    return datetime.now().astimezone().isoformat(timespec="milliseconds")


class CSVFormatter(logging.Formatter):
    """Format log records as strict CSV rows.

    Columns are fixed, in order: ``timestamp``, ``level``, ``run_id``, ``rig``, ``component``, ``event``, ``message``, and ``details_json``.
    """

    COLUMNS = ["timestamp", "level", "run_id", "rig", "component", "event", "message", "details_json"]

    def format(self, record: logging.LogRecord) -> str:
        """Render a record as one CSV line.

        Args:
            record: The log record to format.

        Returns:
            A single CSV row without a trailing newline, using the strict column
            order defined by ``COLUMNS``.
        """
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
    """Format log records as a single line for stdout or journald."""

    def format(self, record: logging.LogRecord) -> str:
        """Render a record as one human-readable line.

        Args:
            record: The log record to format.

        Returns:
            A single line with timestamp, level, location, event, run id,
            message, and truncated details.
        """
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
    """Inject default structured context fields into every log record.

    Ensures each record exposes ``run_id``, ``rig``, ``component``, ``event``,
    and ``details`` so the formatters can rely on them.
    """

    def __init__(self, run_id: str = "", rig: str = "") -> None:
        """Initialize the filter with fallback context values.

        Args:
            run_id: Run identifier applied when a record does not define one.
            rig: Camera rig applied when a record does not define one.
        """
        super().__init__()
        self.run_id = run_id
        self.rig = rig

    def filter(self, record: logging.LogRecord) -> bool:
        """Populate missing context fields on a record.

        Args:
            record: The log record being processed.

        Returns:
            Always ``True`` so the record is emitted.
        """
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


def configure_logging(level: Any = logging.INFO, logfile: Optional[str] = None, run_id: str = "", rig: str = "") -> None:
    """Configure root logging for console and optional CSV file output.

    Existing root handlers are removed before installing a human-readable
    stdout handler and, when ``logfile`` is provided, a CSV file handler. A
    header row is written when the log file is new or empty.

    Args:
        level: Logging level as an ``int`` or a case-insensitive name.
        logfile: Path to the CSV log file; no file handler is added when
            ``None``.
        run_id: Run identifier stored on every record; falls back to the
            ``LOTUS_RUN_ID`` environment variable when empty.
        rig: Camera rig stored on every record.

    Returns:
        None.
    """
    root = logging.getLogger()
    for h in list(root.handlers):
        root.removeHandler(h)
    root.setLevel(_normalize_level(level))

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


def get_logger(name: str, component: Optional[str] = None, rig: Optional[str] = None) -> logging.LoggerAdapter:
    """Create a logger adapter that injects component and rig context.

    Args:
        name: Logger name, typically ``__name__``.
        component: Default component applied to records that lack one.
        rig: Default rig applied to records that lack one.

    Returns:
        A ``logging.LoggerAdapter`` that merges ``component`` and ``rig`` into
        each record's ``extra`` context.
    """
    logger = logging.getLogger(name)

    class _Adapter(logging.LoggerAdapter):
        """Merge component and rig defaults into record context."""

        def process(self, msg: str, kwargs: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
            """Merge default context into the record's ``extra`` mapping.

            Args:
                msg: The log message.
                kwargs: Keyword arguments passed to the logging call.

            Returns:
                The unchanged message and the updated keyword arguments.
            """
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
