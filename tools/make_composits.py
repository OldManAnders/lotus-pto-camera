
from __future__ import annotations

import re
import numpy as np
import cv2
import logging
import sys
from tqdm import tqdm
from functools import partial
from multiprocessing import Pool
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta, time
from pathlib import Path
from typing import Dict, List, Optional, Type
from utils import parsing

#### Logging and filename structure ####
logger = logging.getLogger(__name__)
FILENAME_PATTERN = re.compile(r"^(?P<date>\d{8})-(?P<time>\d{6})_(?P<rig>[^_]+)_(?P<camera_config>[^_]+)_(?P<lighting_config>.+)$")

@dataclass
class TimeBin:
    records: List[ImageRecord]
    start: datetime
    end: datetime
    img: np.ndarray = None

    @property
    def label(self) -> str:
        return self.start.strftime("%Y%m%d-%H%M%S")

#### COMPOSITE SCAFFOLDING ####
# Base composite class which all composite methods should extend
class CompositeMethod(ABC):
    _registry: Dict[str, Type["CompositeMethod"]] = {}

    @classmethod
    def register(cls, name: str):
        def _wrap(subclass: Type["CompositeMethod"]):
            cls._registry[name] = subclass
            return subclass
        return _wrap

    @classmethod
    def create(cls, name: str, **kwargs) -> "CompositeMethod":
        if name not in cls._registry:
            available = ", ".join(sorted(cls._registry)) or "<none registered>"
            raise ValueError(f"Unknown composite method '{name}'. Available: {available}")
        return cls._registry[name](**kwargs)

    @classmethod
    def available_methods(cls) -> List[str]:
        return sorted(cls._registry)
    
    @abstractmethod
    def composite(self, images: List[np.ndarray]) -> np.ndarray:
        raise NotImplementedError("The scaffolding class does not contain the combine functionality please subclass and implement")
        return np.ndarray([])
    
    def __call__(self, images: List[np.ndarray]) -> np.ndarray:
        return self.composite(images)

#### COMPOSITE METHODS ####
# Per-pixel average across the stack.
@CompositeMethod.register("mean")
class MeanComposite(CompositeMethod):
    def composite(self, images: List[np.ndarray]):
        acc = np.zeros(images[0].shape, dtype=np.float32)
        for image in images:
            acc += image.astype(np.float32, copy=False)

        result = acc / len(images)
        return np.clip(result, 0, 255).astype(np.uint8)
    
# Per-pixel median across the stack
@CompositeMethod.register("median")
class MedianComposite(CompositeMethod): 
    def composite(self, images: List[np.ndarray]):
        stack = np.stack(images)
        return np.clip(np.median(stack, axis=0), 0, 255).astype(np.uint8)

# Percentile based sampling
@CompositeMethod.register("percentile")
class PercentileComposite(CompositeMethod):
    def __init__(self, percentile: float = 25.0):
        self.percentile = float(percentile)

    def composite(self, images: List[np.ndarray]) -> np.ndarray:
        stack = np.stack(images)
        return np.clip(np.percentile(stack, self.percentile, axis=0), 0, 255).astype(np.uint8)

#### BIN HANDLING ####
def assign_to_bins(records: List[ImageRecord], bins: List[TimeBin], discard_empty=True) -> List[TimeBin]:
    """Finds a matching bin for each record and returns the bin (with the records)"""
    for record in records:
        for b in bins:
            if b.start <= record.timestamp <= b.end:
                b.records.append(record)
    if discard_empty:
        return [b for b in bins if len(b.records) >=1]

    else:
        return bins

def build_bins(records: List[ImageRecord], interval: int, width:int) -> List[TimeBin]:
    """Create bins from a list of records with set intervals and bin widths"""
    # Verify valid interval and bin width
    if interval <= 1 and width <=1:
        raise ValueError("bin_freq and bin_width must be <= 1 minutes")

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
    """Load image from disk"""
    image = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if image is None:
        logger.warning("Could not read image %s", path)
    return image

def process_bin(bin: TimeBin, method: CompositeMethod, logger=None) -> Optional[np.ndarray]:
    """Function for parralel processing and bin verification"""
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
