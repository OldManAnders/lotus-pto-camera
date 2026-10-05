"""Parse image filenames and load sidecar metadata into records.

Filenames follow ``YYYYMMDD-HHMMSS_<rig>_<camera_config>_<lighting_config>``;
``parse_filename`` turns one into an ``ImageRecord``, optionally loading
the matching ``.json`` sidecar. ``parse_images`` walks a directory tree and
``filter_records`` narrows the resulting records by rig, config, date, or time.
"""

import json
import logging
import re
from datetime import date, datetime, time
from pathlib import Path
from typing import List, Optional, Callable, Tuple
from dataclasses import dataclass

IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".bmp", ".gif", ".tif", ".tiff")
FILENAME_PATTERN = re.compile(r"^(?P<date>\d{8})-(?P<time>\d{6})_(?P<rig>.+)_(?P<camera_config>[^_]+)_(?P<lighting_config>.+)$")

@dataclass
class ImageRecord:
    """A parsed image file and its associated capture context.

    Attributes:
        path: Filesystem path to the image file.
        camera_rig: Rig identifier parsed from the filename.
        timestamp: Capture timestamp parsed from the filename.
        camera_config: Camera configuration label, when present.
        lighting_config: Lighting configuration label, when present.
        metadata: Sidecar JSON metadata, when loaded.
    """

    path: Path
    camera_rig: str
    timestamp: datetime
    camera_config: Optional[str] = None
    lighting_config: Optional[str] = None
    metadata: Optional[dict] = None

    @property
    def timestamp_as_string(self) -> str:
        """Return the timestamp formatted as ``YYYY-MM-DD HH:MM:SS``."""
        return self.timestamp.strftime("%Y-%m-%d %H:%M:%S")

def parse_metadata_file(json_path: Path) -> Optional[dict]:
    """Load a sidecar JSON metadata file.

    Args:
        json_path: Path to the ``.json`` metadata file.

    Returns:
        The parsed metadata mapping, or ``None`` when the file is missing,
        unreadable, or contains invalid JSON.
    """
    try:
        with open(json_path, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError, PermissionError, OSError):
        return None

def parse_filename(path: Path, logger: Optional[logging.Logger] = None, load_metadata: bool = False) -> Optional[ImageRecord]:
    """Parse a single image path into an ``ImageRecord``.

    The filename must match
    ``YYYYMMDD-HHMMSS_<rig>_<camera_config>_<lighting_config>``.

    Args:
        path: Path to the image file.
        logger: Optional logger used to report skipped files.
        load_metadata: When ``True``, load the matching ``.json`` sidecar into
            the record's ``metadata`` field.

    Returns:
        The parsed record, or ``None`` when the filename does not match the
        expected pattern or its timestamp cannot be parsed.
    """
    match = FILENAME_PATTERN.search(path.stem)
    if not match:
        if logger:
            logger.warning(f"Skipping {path.name}: filename doesn't match expected pattern")
        return None
    else:
        try: #to parse filename into Image Record
            timestamp = datetime.strptime(f"{match['date']}-{match['time']}", "%Y%m%d-%H%M%S")
            record = ImageRecord(
                path=path, 
                camera_rig=match["rig"],
                timestamp=timestamp,
                camera_config=match["camera_config"],
                lighting_config=match["lighting_config"])
            if load_metadata:
                json_path = path.with_suffix(".json")
                record.metadata = parse_metadata_file(json_path)
            return record
        #Handlee when filenames dont align with known format
        except ValueError:
            if logger:
                logger.warning(f"Skipping {path.name}: could not parse timestamp")
            return None

def parse_images(input_dir: str, extensions: Tuple[str, ...] = IMAGE_EXTENSIONS, logger: Optional[logging.Logger] = None, load_metadata: bool = False) -> List[ImageRecord]:
    """Recursively parse image files under a directory.

    Args:
        input_dir: Directory to search recursively.
        extensions: Accepted filename extensions, compared case-insensitively.
        logger: Optional logger used to report progress and skipped files.
        load_metadata: When ``True``, load each image's ``.json`` sidecar.

    Returns:
        The list of successfully parsed records, in filesystem traversal order.
    """
    input_dir = Path(input_dir)
    records = []
    #Iterate over folder recursively
    matches = input_dir.rglob("*")

    # Process every file
    for i, path in enumerate(matches):
        if path.suffix.lower() in extensions:
            record = parse_filename(path, logger=logger, load_metadata=load_metadata)
            if record:
                records.append(record)
    #Sort and return
    if logger:
        logger.info(f"Parsed a total of {len(records)} files")
    
    return records

def filter_records(records: List[ImageRecord],
                    camera_rig: Optional[str] = None,
                    camera_configs: Optional[List[str]] = None,
                    lighting_configs: Optional[List[str]] = None,
                    date_range: Optional[Tuple[date, date]] = None,
                    time_ranges: Optional[List[Tuple[time, time]]] = None,
                    logger: Optional[logging.Logger] = None,) -> List[ImageRecord]:
    """Filter records by rig, config, date, and time criteria.

    Each argument narrows the result set; arguments left as ``None`` are
    ignored. Filters are applied in the order rig, date, time, camera configs,
    then lighting configs.

    Args:
        records: Records to filter.
        camera_rig: Keep only records for this rig.
        camera_configs: Keep only records whose camera config is in this list.
        lighting_configs: Keep only records whose lighting config is in this
            list.
        date_range: Inclusive ``(start_date, end_date)`` bounds on the capture
            date.
        time_ranges: Keep records whose capture time falls within any inclusive
            ``(start_time, end_time)`` range.
        logger: Optional logger used to report filtering progress.

    Returns:
        The filtered list of records.
    """
    
    filtered = list(records)
    if logger:
        logger.info(f"Total records: {len(filtered)}")

    # Filter by camera rig
    if camera_rig is not None:
        filtered = [r for r in filtered if r.camera_rig == camera_rig]
        if logger:
            logger.debug(f"{len(filtered)} fits rig.")

    # Filter by date range
    if date_range is not None:
        start_date, end_date = date_range
        filtered = [r for r in filtered if start_date <= r.timestamp.date() <= end_date]
        if logger:
            logger.debug(f"{len(filtered)} fits the date range. [{start_date} - {end_date}]")
        
    # Filter by time range
    if time_ranges is not None:
        filtered = [r for r in filtered if any(start_time <= r.timestamp.time() <= end_time for start_time, end_time in time_ranges)]
        if logger:
            logger.debug(f"{len(filtered)} fits the time range. [{' | '.join([f'{x} - {y}' for x,y in time_ranges])}]")
        
    # Filter by list of camera configs
    if camera_configs is not None:
        allowed = set(camera_configs)
        filtered = [r for r in filtered if r.camera_config in allowed]
        if logger:
            logger.debug(f"{len(filtered)} fits camera configs. [{allowed}]")
        
    # Filter by list of lighting configs
    if lighting_configs is not None:
        allowed = set(lighting_configs)
        filtered = [r for r in filtered if r.lighting_config in allowed]
        if logger:
            logger.debug(f"{len(filtered)} fits lighting configs. [{allowed}]")

    if logger:
        logger.info(f"Filtered images: {len(filtered)}")

    return filtered