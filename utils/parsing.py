import logging
import re
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Callable
from dataclasses import dataclass

IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".bmp", ".gif", ".tif", ".tiff")
FILENAME_PATTERN = re.compile(r"^(?P<date>\d{8})-(?P<time>\d{6})_(?P<rig>.+)_(?P<camera_config>[^_]+)_(?P<lighting_config>.+)$")

@dataclass
class ImageRecord:
    path: Path
    camera_rig: str
    timestamp: datetime
    camera_config: str = None
    lighting_config: str = None

    @property
    def timestamp_as_string(self) -> str:
        return self.timestamp.strftime("%Y-%m-%d %H:%M:%S")

def parse_filename(path:Path, logger=None):
    match = FILENAME_PATTERN.search(path.stem)
    if not match:
        if logger:
            logger.warning(f"Skipping {path.name}: filename doesn't match expected pattern")
        return None
    else:
        try: #to parse filename into Image Record
            timestamp = datetime.strptime(f"{match['date']}-{match['time']}", "%Y%m%d-%H%M%S")
            return ImageRecord(
                path=path, 
                camera_rig=match["rig"],
                timestamp=timestamp,
                camera_config=match["camera_config"],
                lighting_config=match["lighting_config"])
        #Handlee when filenames dont align with known format
        except ValueError:
            if logger:
                logger.warning(f"Skipping {path.name}: could not parse timestamp")
            return None

def parse_images(input_dir:str, extensions:tuple = IMAGE_EXTENSIONS, logger=None) -> List[ImageRecord]:
    input_dir = Path(input_dir)
    records = []
    #Iterate over folder recursively
    matches = input_dir.rglob("*")

    # Process every file
    for i, path in enumerate(matches):
        if path.suffix.lower() in extensions:
            record = parse_filename(path)
            if record:
                records.append(record)
    #Sort and return
    if logger:
        logger.info(f"Parsed a total of {len(records)} files")
    
    return records

def filter_records(records:List[ImageRecord],
                    camera_rig:str = None,
                    camera_configs:List[str] = None,
                    lighting_configs:List[str] = None,
                    date_range: tuple = None,
                    time_range: tuple = None,
                    logger = None,) -> List[ImageRecord]:
    
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
    if time_range is not None:
        start_time, end_time = time_range
        filtered = [r for r in filtered if start_time <= r.timestamp <= end_time]
        if logger:
            logger.debug(f"{len(filtered)} fits the time range. [{start_time} - {end_time}]")
        
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