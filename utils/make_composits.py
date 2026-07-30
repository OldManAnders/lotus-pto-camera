
from __future__ import annotations

import re
import numpy as np
import cv2
import logging
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta, time
from pathlib import Path
from typing import Dict, List, Optional, Type
from utils.parsing import ImageRecord, parse_filename, parse_images, filter_records

#### Logging and filename structure ####
logger = logging.getLogger(__name__)
FILENAME_PATTERN = re.compile(r"^(?P<date>\d{8})-(?P<time>\d{6})_(?P<rig>[^_]+)_(?P<camera_config>[^_]+)_(?P<lighting_config>.+)$")

@dataclass
class TimeBin:
    records: List[ImageRecord]
    start: datetime
    end: datetime

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
#Per-pixel average across the stack.
@CompositeMethod.register("mean")
class MeanComposite(CompositeMethod):
    def composite(self, images: List[np.ndarray]):
        stack = np.stack(images).astype(np.float32)
        return np.clip(stack.mean(axis=0), 0, 255).astype(np.uint8)

#Per-pixel median across the stack
@CompositeMethod.register("median")
class MedianComposite(CompositeMethod): 
    def composite(self, images: List[np.ndarray]):
        stack = np.stack(images).astype(np.float32)
        return np.clip(np.median(stack, axis=0), 0, 255).astype(np.uint8)

def assign_to_bins(records: List[ImageRecord], bins: List[TimeBin]) -> List[TimeBin]:
    for record in records:
        for b in bins:
            if b.start <= record.timestamp < b.end:
                b.records.append(record)
                break
    return bins

def build_bins(records: List[ImageRecord], interval: int, width:int) -> List[TimeBin]:
    if interval <= 1:
        raise ValueError("capture_interval must be > 0 minutes")

    #Fetch all timestamps
    timestamps = [record.timestamp for record in records]
    start = datetime.combine(min(timestamps).date(), time.min)
    end = datetime.combine(max(timestamps).date() + timedelta(days=1), time.min)

    #Build consecutive non-overlapping bins for the day
    bins = []
    n_bins = int((end - start) / timedelta(minutes=interval))
    for i in range(n_bins):
        bin_start = start + timedelta(minutes=i*interval)
        bin_end = bin_start + timedelta(minutes=width)
        bins.append(TimeBin(records=[], start=bin_start, end=bin_end))
    return bins

def load_image(path: Path) -> Optional[np.ndarray]:
    image = cv2.imread(str(path))
    if image is None:
        logger.warning("Could not read image %s", path)
    return image

def process_bin(bin: TimeBin, method: CompositeMethod) -> Optional[np.ndarray]:
    #Check if there is images
    if len(bin.records) <=0:
        logger.warning(f"Bin {bin.label}: is empty, skipping")
    images = [load_image(r.path) for r in bin.records]
    # Try to read the images
    if len(images)<=0:
        logger.warning(f"Bin {bin.label}: no readable images, skipping")
        return None
    # Process images
    return method(images)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("input_dir", type=Path, help="Folder containing source images (assumes final folder name has a timestamp)")
    parser.add_argument("output_dir", type=Path, help="Folder to write composites to")
    parser.add_argument("camera_rig", type=str, help="Camera rig identifier to filter for")
    parser.add_argument("--bin_freq", type=int, default=15, help="How frequent to establish each bin (in minutes)")
    parser.add_argument("--bin_width", type=int, default=15, help="Width of each bin (in minutes)")
    parser.add_argument("--camera_configs", type=str, nargs="+", default=None, help="Restrict to one or more camera configs, omit to include all camera configs.")
    parser.add_argument("--lighting_configs", type=str, nargs="+", default=None, help="Restrict to one or more lighting configs, omit to include all lighting configs.")
    parser.add_argument("--filter_options", action='store_true', help="Display all available filter options")
    parser.add_argument("--method", type=str, default="mean", choices=CompositeMethod.available_methods(), help="Composite method to use")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable debug logging")
    args = parser.parse_args()

    #Prepare logging and output folder
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,format="[%(levelname)s] %(message)s")
    args.output_dir.mkdir(parents=True, exist_ok=True)

    #Initialize composite method
    method = CompositeMethod.create(args.method)

    #Gather all images
    all_records = parse_images(args.input_dir)

    #Show all available filter options
    if args.filter_options:
        ccs = sorted({record.camera_config for record in all_records if record.camera_config is not None})
        lcs = sorted({record.lighting_config for record in all_records if record.lighting_config is not None})
        print(f"\n##### Camera configs present in records #####")
        print(", ".join(ccs))
        print(f"\n##### Lighting configs present in records #####")
        print(", ".join(lcs))
        sys.exit()

    #Filer images based on criteria
    filtered_records = filter_records(all_records, camera_rig=args.camera_rig,camera_configs=args.camera_configs, lighting_configs=args.lighting_configs)
    logger.info(f"Found {len(all_records)} images total, {len(filtered_records)} matching rig '{args.camera_rig}' and filter criterias '{','.join(args.camera_configs) if args.camera_configs else 'any'}' and '{','.join(args.lighting_configs) if args.lighting_configs else 'any'}'")

    #Create interval bins and assign images
    print("Building bins")
    bins = build_bins(filtered_records, args.bin_freq, args.bin_width)
    
    print("Assigning records to bins")
    assignment = assign_to_bins(filtered_records, bins)

    #Create a filesystem-safe tag describing the applied filtering
    config_tag_parts = []
    if args.camera_configs:
        config_tag_parts.append("+".join(args.camera_configs))
    if args.lighting_configs:
        config_tag_parts.append("+".join(args.lighting_configs))
    config_tag = f"_{'_'.join(config_tag_parts)}" if config_tag_parts else ""

    # Process each bin
    for i,b in enumerate(bins):
        composite = process_bin(b, method)
        if composite is not None:
            out_path = args.output_dir / f"{args.camera_rig}_{b.label}{config_tag}_{args.method}.jpg"
            cv2.imwrite(str(out_path), composite)
            logger.info(f"({i}/{len(bins)}) Wrote {out_path}")