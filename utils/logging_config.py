import logging
import csv
import io
import sys

# Custom telemetry level1
TELEMETRY = 15
logging.addLevelName(TELEMETRY, "TELEMETRY")

class CSVFormatter(logging.Formatter):
    """Formats records as CSV rows: timestamp,level,logger,component,event,details

    `details` is written as-is and quoted by the CSV writer.
    """

    def __init__(self, datefmt="%Y-%m-%d %H:%M:%S"):
        super().__init__(datefmt=datefmt)
        self.datefmt = datefmt

    def format(self, record: logging.LogRecord) -> str:
        timestamp = self.formatTime(record, self.datefmt)
        level = record.levelname
        logger_name = record.name
        component = getattr(record, "component", "") or ""
        event = getattr(record, "event", "") or ""
        details = getattr(record, "details", None)

        details_value = "" if details is None else str(details)

        # Use csv writer to handle quoting
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow([timestamp, level, logger_name, component, event, details_value])
        return buf.getvalue().strip()

def configure_logging(level=logging.INFO, logfile: str = None):
    root = logging.getLogger()
    # Clear existing handlers
    for h in list(root.handlers):
        root.removeHandler(h)

    root.setLevel(level)

    formatter = CSVFormatter()

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    root.addHandler(stream_handler)

    if logfile:
        fh = logging.FileHandler(logfile)
        fh.setFormatter(formatter)
        root.addHandler(fh)

def get_logger(name: str, component: str = None) -> logging.LoggerAdapter:
    logger = logging.getLogger(name)
    class LoggerWithTelemetry(logging.LoggerAdapter):
        def __init__(self, logger, extra, merge_extra: bool = True):
            super().__init__(logger, extra)
            self.merge_extra = merge_extra

        def process(self, msg, kwargs):
            extra = kwargs.get("extra")
            if self.merge_extra:
                merged = dict(self.extra) if self.extra else {}
                if extra:
                    merged.update(extra)
                kwargs["extra"] = merged
            else:
                if extra is not None:
                    kwargs["extra"] = extra
                else:
                    kwargs["extra"] = dict(self.extra) if self.extra else {}
            return msg, kwargs

        def telemetry(self, event: str, details=None):
            # Use the adapter's log method so `extra` is merged with adapter extra
            self.log(TELEMETRY, "", extra={"event": event, "details": details})

    return LoggerWithTelemetry(logger, {"component": component}, merge_extra=True)

def _telemetry(self, event: str, details=None):
    """Log a TELEMETRY-level record with `event` and `details` in the extra dict."""
    if self.isEnabledFor(TELEMETRY):
        self.log(TELEMETRY, "", extra={"event": event, "details": details})

# Attach telemetry helper to Logger class for convenience
logging.Logger.telemetry = _telemetry
