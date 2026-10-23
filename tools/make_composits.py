"""Offline compositing tool: bin timestamped images by time and composite each bin.

Reads timestamped images, groups them into time bins, applies a configurable
composite method (mean, median, percentile) to each bin, and writes the
resulting composites as JPEG files. Intended to be run as a script.
"""

from __future__ import annotations

import logging
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, time
from functools import partial
from multiprocessing import Pool
from pathlib import Path
from typing import List, Optional

import cv2
import numpy as np
from tqdm import tqdm

from utils import parsing
from utils.composits import CompositeMethod

#### Logging and filename structure ####
logger = logging.getLogger(__name__)
FILENAME_PATTERN = re.compile(r"^(?P<date>\d{8})-(?P<time>\d{6})_(?P<rig>[^_]+)_(?P<camera_config>[^_]+)_(?P<lighting_config>.+)$")

@dataclass
class TimeBin:
    """A time interval holding the image records that fall within it.

    Attributes:
        records: Image records whose timestamps fall within ``[start, end]``.
        start: Inclusive start of the bin.
        end: Inclusive end of the bin.
        img: Composited image for the bin, or ``None`` until processing runs.
    """

    records: List[parsing.ImageRecord]
    start: datetime
    end: datetime
    img: Optional[np.ndarray] = None

    @property
    def label(self) -> str:
        """Return the bin start as a ``YYYYMMDD-HHMMSS`` label.

        Returns:
            The formatted start timestamp, used as an output filename prefix.
        """
        return self.start.strftime("%Y%m%d-%H%M%S")

#### BIN HANDLING ####
def assign_to_bins(records: List[parsing.ImageRecord], bins: List[TimeBin], discard_empty: bool = True) -> List[TimeBin]:
    """Assign each record to the first bin whose interval contains it.

    Args:
        records: Image records to distribute across ``bins``.
        bins: Time bins to populate in place.
        discard_empty: If ``True``, drop bins that received no records.

    Returns:
        The populated bins, optionally excluding empty ones.
    """
    for record in records:
        for b in bins:
            if b.start <= record.timestamp <= b.end:
                b.records.append(record)
    if discard_empty:
        return [b for b in bins if len(b.records) >=1]

    else:
        return bins

def build_bins(records: List[parsing.ImageRecord], interval: int, width: int) -> List[TimeBin]:
    """Create fixed-interval time bins spanning the records' date range.

    Args:
        records: Image records whose timestamps define the overall span.
        interval: Minutes between the start of consecutive bins.
        width: Length of each bin in minutes.

    Returns:
        Time bins covering from midnight of the earliest record's date to
        midnight after the latest record's date.

    Raises:
        ValueError: If ``interval`` and ``width`` are both ``<= 1``.
    """
    # Verify valid interval and bin width
    if interval <= 1 and width <=1:
        raise ValueError("bin_freq and bin_width must be greater than 1")

    # Fetch all timestamps
    timestamps = [record.timestamp for record in records]
    start = datetime.combine(min(timestamps).date(), time.min)
    end = datetime.combine(max(timestamps).date() + timedelta(days=1), time.min)

    # Build bins at intervals of 'interval' minutes, each bin is 'width' minutes long
    bins = []
    bin_start = start
    while bin_start < end:
        bin_end = min(bin_start + timedelta(minutes=width), end)
        bins.append(TimeBin(records=[], start=bin_start, end=bin_end))
        bin_start += timedelta(minutes=interval)
    return bins

def load_image(path: Path) -> Optional[np.ndarray]:
    """Load an image from disk as a BGR array.

    Args:
        path: Path to the image file.

    Returns:
        The decoded BGR image, or ``None`` if it could not be read.
    """
    image = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if image is None:
        logger.warning("Could not read image %s", path)
    return image

def process_bin(bin: TimeBin, method: CompositeMethod, logger: Optional[logging.Logger] = None) -> Optional[TimeBin]:
    """Read and composite the images belonging to a single bin.

    Args:
        bin: The time bin to process; its ``records`` are read and its ``img``
            is populated when compositing succeeds.
        method: Composite method applied to the successfully loaded images.
        logger: Optional logger for progress and failure messages.

    Returns:
        The processed bin, with ``img`` set when compositing succeeded, or the
        unchanged bin when it is empty or no images could be read.
    """
    logger.debug(f"Processing bin {bin.label}")
    # Check if there is images
    if len(bin.records) <=0:
        if logger:
            logger.warning(f"Bin {bin.label}: is empty, skipping")
        return bin

    # Try to read the images
    logger.debug(f"Bin {bin.label}: reading {len(bin.records)} images")
    images = [img for img in (load_image(r.path) for r in bin.records) if img is not None]
    if len(images)>=1:
        # Process image
        logger.debug(f"Bin {bin.label}: processing {len(images)} images with method {method.__class__.__name__}")
        bin.img = method(images)
        return bin
    else:
        logger.warning(f"Bin {bin.label}: failed to read images, skipping")
        return bin

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Create composite images from a set of input images.", formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    positional = parser.add_argument_group("Positional arguments")
    positional.add_argument("input", type=Path, help="The '*/images/' directory containing all of the images")
    positional.add_argument("output", type=Path, help="Output directory for composite images")
    positional.add_argument("start", type=str, help="Start date (YYYY-MM-DD)")
    positional.add_argument("end", type=str, help="End date (YYYY-MM-DD)")
    # FILTER ARGUMENTS
    filter_group = parser.add_argument_group("Filter options")
    filter_group.add_argument("--rig", type=str, default=None, help="Filter by setup name")
    filter_group.add_argument("--camera", nargs="+", type=str, default=None, help="Filter by camera configuration")
    filter_group.add_argument("--lighting", nargs="+", type=str, default=None, help="Filter by lighting configuration")
    filter_group.add_argument("--time_period", nargs=2, action="append", metavar=("START_HOUR", "END_HOUR"), default=None, help="Limit each day's images to a time window, for example: --time_period 00:00 12:00")
    # BINNING ARGUMENTS
    bin_group = parser.add_argument_group("Bin options")
    bin_group.add_argument("--bin_freq", type=int, default=15, help="How frequent to establish each bin (minutes)")
    bin_group.add_argument("--bin_width", type=int, default=15, help="Width of each bin (minutes)")
    # COMPOSITING ARGUMENTS
    composite_group = parser.add_argument_group("Composite options")
    composite_group.add_argument("--method", type=str, default="mean", choices=CompositeMethod.available_methods(), help="Composite method to use")
    composite_group.add_argument("-a", "--method_args", action="append", default=[], help="Override arguments for composite methods")
    # MISC ARGUMENTS
    misc_group = parser.add_argument_group("Miscellaneous")
    misc_group.add_argument("--filter_options", action="store_true", help="Display all available filter options")
    misc_group.add_argument("-v", "--verbose", action="store_true", help="Enable debug logging")
    # PARSE
    args = parser.parse_args()

    # Setup logger
    logging.basicConfig()
    logger = logging.getLogger(__name__)
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.INFO)

    # Prepare output folder
    args.output.mkdir(parents=True, exist_ok=True)

    # Initialize composite method
    method = CompositeMethod.create(args.method, **{item.split("=", 1)[0]: item.split("=", 1)[1] for item in args.method_args})

    # Gather all images
    logger.debug(f"Parsing images from {args.input}")
    records = parsing.parse_images(args.input, logger=logger)

    # Filer images based on criteria
    logger.debug(f"Filtering {len(records)} records with criteria: rig={args.rig}, camera={args.camera}, lighting={args.lighting}, date_range=({args.start}, {args.end}), time_ranges={args.time_period}")
    records = parsing.filter_records(
        records,
        camera_rig=args.rig,
        camera_configs=args.camera,
        lighting_configs=args.lighting,
        date_range=(datetime.strptime(args.start, "%Y-%m-%d").date(), datetime.strptime(args.end, "%Y-%m-%d").date()),
        time_ranges=[(datetime.strptime(lim[0], "%H:%M").time(), datetime.strptime(lim[1], "%H:%M").time()) for lim in args.time_period] if args.time_period else None,
        logger=logger)

    # Show all available filter options (Subject to current filter)
    if args.filter_options:
        ccs = sorted({record.camera_config for record in records if record.camera_config is not None})
        lcs = sorted({record.lighting_config for record in records if record.lighting_config is not None})
        print(f"\n##### Camera configs present in records #####")
        print(", ".join(ccs))
        print(f"\n##### Lighting configs present in records #####")
        print(", ".join(lcs))
        sys.exit()

    # Create interval bins and assign images
    logger.info(f"Building bins - [{args.bin_width} minute bins every {args.bin_freq} minutes]")
    bins = build_bins(records, args.bin_freq, args.bin_width)
    
    # Create bins with relevanct image records
    logger.info("Assigning records to bins")
    assigned_bins = assign_to_bins(records, bins)

    # Multiprocessing paralel processing
    logger.info("Processing bins")
    pool = Pool()

    # post-process each returned composite
    for i, bin in enumerate(tqdm(pool.imap_unordered(partial(process_bin, method=method, logger=logger), assigned_bins), total=len(assigned_bins)), start=1):
        # If the composite succeeded, save the file
        if bin.img is not None: #
            out_path = args.output / f"{bin.label}_{args.rig}_{'Composite'}_{args.method}.jpg"
            cv2.imwrite(str(out_path), bin.img)
    
    # Close out
    pool.close()
    pool.join()
