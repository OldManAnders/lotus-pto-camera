import os
import subprocess
import tempfile
import logging
from utils import parsing
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional
from tqdm import tqdm


class TimelapseGenerator:      
    def _build_timestamp_ass(self, records, fps, overlay_text=None):
        """Build ASS subtitle file for frame timestamps."""

        def format_ass_time(seconds):
            """Convert to ASS subtitle timestamps for temporal positioning"""
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            secs = seconds % 60
            return f"{hours:d}:{minutes:02d}:{secs:05.2f}"

        # Define text formating and style
        lines = [
            "[Script Info]",
            "ScriptType: v4.00+",
            "PlayResX: 1920",
            "PlayResY: 1080",
            "ScaledBorderAndShadow: yes",
            "",
            "[V4+ Styles]",
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
            "Style: Default,Arial,24,&H00FFFFFF,&H000000FF,&H00000000,&H64000000,0,0,0,0,100,100,0,0,1,1,0,1,10,10,10,1",
            "",
            "[Events]",
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
        ]

        # Generate a single overlay string in the top left
        if overlay_text:
            overlay_text = overlay_text.strip()
            if overlay_text:
                total_duration = len(records) / fps
                lines.append(f"Dialogue: 1,0:00:00.00,{format_ass_time(total_duration)},Default,,0,0,0,,{{\\an7}}{overlay_text}")

        # Add a timestamp for each frame in the bottom left
        for index, record in enumerate(records):
            #Write the timestamp in the bottom left corner for each frame
            timestamp = record.timestamp.strftime("%Y-%m-%d %H:%M:%S")
            start_time = index / fps
            end_time = (index + 1) / fps
            lines.append(f"Dialogue: 0,{format_ass_time(start_time)},{format_ass_time(end_time)},Default,,0,0,0,,{timestamp}")
        
        # Write the subtitle file to temp folder
        temp_ass = tempfile.NamedTemporaryFile(delete=False, mode="w", encoding="utf-8", suffix=".ass")
        temp_ass.write("\n".join(lines))
        temp_ass.close()
        return temp_ass.name

    def _build_video_filter(self, scale, subtitle_path_escaped, crop=None):
        """Build the ffmpeg video filter chain for export."""
        filters = []
        
        # Crop the video if crop values are provided
        if crop is not None:
            x, y, width, height = [int(value) for value in crop]
            # Sanity check the crop values
            if width <= 0 or height <= 0:
                raise ValueError("Crop width and height must be greater than zero.")
            filters.append(f"crop={width}:{height}:{x}:{y}")
            
        #Scale the video if value is not 1.0 (no scaling)
        if scale != 1.0:
            filters.append(f"scale=trunc(iw*{scale}/2)*2:trunc(ih*{scale}/2)*2")
            
        # Add subtitles filter
        filters.append(f"subtitles='{subtitle_path_escaped}'")
        return ",".join(filters)

    def export(self, records, output, fps=15, scale=1.0, codec="libx264", preset="medium", crf=23, crop=None, overlay_text=None, progress_callback=None):
        """Export matched images to video file."""

        # Check if there even is images in the export
        if len(records) <= 0:
            raise ValueError("No images to export.")
        total_frames = len(records)
        pbar = None
        if progress_callback is None:
            pbar = tqdm(total=total_frames, unit="frame")
        
        # Create file list for ffmpeg concat
        with tempfile.NamedTemporaryFile(delete=False, mode="w", encoding="utf-8", suffix=".txt") as list_file:
            list_path = list_file.name

            # Write list of images to include in the video
            for record in records:
                path_for_list = os.path.abspath(os.fspath(record.path)).replace("\\", "/")
                safe_path = path_for_list.replace("'", "'\\''")
                list_file.write(f"file '{safe_path}'\n")
        
        # Build subtitle file with timestamps
        subtitle_path = self._build_timestamp_ass(records, fps, overlay_text)
        subtitle_path_quoted = os.path.abspath(subtitle_path).replace("\\", "/")
        subtitle_path_escaped = (subtitle_path_quoted.replace(":", "\\:").replace(",", "\\,").replace("'", "\\'"))

        # Create a video filter to apply scaling, cropping and add subtitles/overlays
        video_filter = self._build_video_filter(
            scale=scale,
            subtitle_path_escaped=subtitle_path_escaped,
            crop=crop,
        )

        # Define FFMPEG command
        command = [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel", "error",
            "-f", "concat",
            "-safe", "0",
            "-r", str(fps),
            "-i", list_path,
            "-vf", video_filter,
            "-c:v", codec,
            "-preset", preset,
            "-crf", str(crf),
            "-pix_fmt", "yuv420p",
            "-progress", "pipe:1",
            os.path.abspath(output),
        ]
        
        # Start ffmpeg process and handle progress reporting
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        
        try:
            # Report progress
            last_frame = 0
            for line in process.stdout:
                if line.startswith("frame="):
                    frame = int(line.strip().split("=")[1])
                    if pbar is not None:
                        pbar.update(frame - last_frame)
                    if progress_callback is not None:
                        progress_callback(frame, total_frames)
                    last_frame = frame
                elif line.strip() == "progress=end":
                    break      
        finally:
            if pbar is not None:
                pbar.close()
            print("Finalizing export")
            # Check if process is finished
            retcode = process.poll()
            if retcode is None:
                process.wait()
                retcode = process.returncode
            
            # Clean up temporary files
            print("Removing temporary files")
            for temp_file in [list_path, subtitle_path]:
                try:
                    os.remove(temp_file)
                except OSError:
                    pass

            # Check if FFmpeg failed
            if retcode != 0:
                stderr = process.stderr.read() if process.stderr else ""
                raise RuntimeError(f"FFmpeg failed with return code {retcode}.\n\n{stderr}")      
            else:
                print("Export complete!")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Generate timelapse videos from timestamped images.", formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    positional = parser.add_argument_group("Positional arguments")
    positional.add_argument("input", type=str, help="Root directory containing the images folder.")
    positional.add_argument("output", type=str, help="Output video filename.")
    positional.add_argument("start", type=str, help="Start date (YYYY-MM-DD)")
    positional.add_argument("end", type=str, help="End date (YYYY-MM-DD)")
    # FILTER ARGUMENTS
    filter_group = parser.add_argument_group("Filter options")
    filter_group.add_argument("--rig", type=str, default=None, help="Filter by setup name")
    filter_group.add_argument("--camera", nargs="+", type=str, default=None, help="Filter by camera configuration")
    filter_group.add_argument("--lighting", nargs="+", type=str, default=None, help="Filter by lighting configuration")
    filter_group.add_argument("--time_period", nargs=2, action="append", metavar=("START_HOUR", "END_HOUR"), default=None, help="Limit each day's images to a time window, for example: --time_period 00:00 12:00")
    # VIDEO ARGUMENTS
    video_group = parser.add_argument_group("Video options")
    video_group.add_argument("--fps", type=int, default=15, help="Frames per second")
    video_group.add_argument("--scale", type=float, default=1.0, help="Scale the image resolution by a floating point scaler")
    video_group.add_argument("--codec", default="libx264", choices=["libx264", "libx265", "mpeg4"], help="Video codec to use")
    video_group.add_argument("--preset", default="medium", choices=["ultrafast", "superfast", "veryfast", "faster", "fast", "medium", "slow", "slower", "veryslow"], help="Encoding preset for the selected codec")
    video_group.add_argument("--crf", type=int, default=23, help="Constant Rate Factor for quality/compression")
    video_group.add_argument("--crop", type=int, nargs=4, default=None, metavar=("x", "y", "width", "height"), help="Crop area of the timelapse")
    #OVERLAY ARGUMENTS
    overlay_group = parser.add_argument_group("Overlay options")
    overlay_group.add_argument("--overlay", type=str, default=None, help="Optional text overlay to display on the video (top left)")
    #MISC ARGUMENTS
    misc_group = parser.add_argument_group("Miscellaneous")
    misc_group.add_argument("-v", "--verbose", action="store_true", help="Enable verbosity")
    #PARSE
    args = parser.parse_args()

    #Setup logger
    logging.basicConfig()
    logger = logging.getLogger(__name__)
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    else: logger.setLevel(logging.INFO)
    
    # Find records
    records = parsing.parse_images(args.input, logger=logger)
    records.sort(key=lambda r: r.timestamp)

    if len(records) <= 0:
        raise ValueError(f"No timestamped images were found in the provided directory. {args.input}")

    # Filter records
    records = parsing.filter_records(
        records,
        camera_rig=args.rig,
        camera_configs=args.camera,
        lighting_configs=args.lighting,
        date_range=(datetime.strptime(args.start, "%Y-%m-%d").date(), datetime.strptime(args.end, "%Y-%m-%d").date()),
        time_ranges=[(datetime.strptime(lim[0], "%H:%M").time(), datetime.strptime(lim[1], "%H:%M").time()) for lim in args.time_period] if args.time_period else None,
        logger=logger)

    #Sort chronologically
    records.sort(key=lambda r: r.timestamp)

    try:
        # Initialize Generator
        generator = TimelapseGenerator()
        # Export
        generator.export(
            records=records,
            output=args.output,
            fps=args.fps,
            scale=args.scale,
            codec=args.codec,
            preset=args.preset,
            crf=args.crf,
            crop=args.crop,
            overlay_text=args.overlay,
        )
    except Exception as e:
        raise SystemExit(f"Export error: {e}")