import os
import sys
import argparse
import shutil
import subprocess
import tempfile
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from datetime import datetime

IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".bmp", ".gif", ".tif", ".tiff", ".webp", ".heic")


class TimelapseGenerator:
    """Core timelapse generation logic - independent from GUI."""
    
    def __init__(self):
        self.image_index = {}
        self.unique_dates = []
        self.rig_options = ["All"]
        self.camera_options = ["All"]
        self.lighting_options = ["All"]
    
    def scan(self, root_directory):
        """Scan root directory for timestamped images and build indices."""
        self.image_index = {}
        self.unique_dates = []
        self.rig_options = ["All"]
        self.camera_options = ["All"]
        self.lighting_options = ["All"]
        
        images_root = os.path.join(root_directory, "images")
        if not os.path.isdir(images_root):
            raise ValueError("Selected directory must contain an 'images' folder.")
        
        rigs = set()
        cameras = set()
        lightings = set()
        found_dates = set()
        total_images = 0
        
        for root_dir, _, files in os.walk(images_root):
            for file_name in files:
                lower_name = file_name.lower()
                if not lower_name.endswith(IMAGE_EXTENSIONS):
                    continue
                
                base_name, _ = os.path.splitext(file_name)
                if len(base_name) < 17 or base_name[8] != "-":
                    continue
                
                date_prefix = base_name[:8]
                try:
                    valid_date = datetime.strptime(date_prefix, "%Y%m%d").date()
                except ValueError:
                    continue
                
                parts = base_name.split("_")
                if len(parts) < 3:
                    continue
                
                lighting = parts[-1]
                camera = parts[-2]
                rig = "_".join(parts[1:-2]) if len(parts) > 3 else parts[1]
                date_key = valid_date.strftime("%Y-%m-%d")
                
                entry = {
                    "path": os.path.normpath(os.path.join(root_dir, file_name)),
                    "date": date_key,
                    "rig": rig,
                    "camera": camera,
                    "lighting": lighting,
                }
                
                self.image_index.setdefault(date_key, []).append(entry)
                rigs.add(rig)
                cameras.add(camera)
                lightings.add(lighting)
                found_dates.add(valid_date)
                total_images += 1
        
        if not found_dates:
            raise ValueError("No timestamped images were found under the 'images' folder.")
        
        self.unique_dates = [d.strftime("%Y-%m-%d") for d in sorted(found_dates)]
        self.rig_options += sorted(rigs)
        self.camera_options += sorted(cameras)
        self.lighting_options += sorted(lightings)
        
        return {
            "total_images": total_images,
            "dates": len(self.unique_dates),
            "rigs": len(rigs),
            "cameras": len(cameras),
            "lightings": len(lightings),
        }
    
    def get_matching_images(self, start=None, end=None, rig="All", camera="All", lighting="All"):
        """Get images matching the given filters."""
        if start is None or end is None:
            return []
        
        try:
            start_date = start if isinstance(start, str) else start.strftime("%Y-%m-%d")
            end_date = end if isinstance(end, str) else end.strftime("%Y-%m-%d")
        except (ValueError, AttributeError):
            return []
        
        if start_date > end_date:
            return []
        
        matches = []
        for date_key in self.unique_dates:
            if not (start_date <= date_key <= end_date):
                continue
            for entry in self.image_index.get(date_key, []):
                if rig != "All" and entry["rig"] != rig:
                    continue
                if camera != "All" and entry["camera"] != camera:
                    continue
                if lighting != "All" and entry["lighting"] != lighting:
                    continue
                matches.append(entry)
        
        return sorted(matches, key=lambda x: x["path"])
    
    def _extract_image_timestamp(self, image_path):
        """Extract timestamp from image filename."""
        base_name = os.path.splitext(os.path.basename(image_path))[0]
        if len(base_name) >= 15 and base_name[8] == "-":
            try:
                dt = datetime.strptime(base_name[:15], "%Y%m%d-%H%M%S")
                return dt.strftime("%Y-%m-%d %H:%M:%S")
            except ValueError:
                pass
        return base_name
    
    def _build_timestamp_ass(self, matches, fps, overlay_text=None):
        """Build ASS subtitle file for frame timestamps."""
        def format_ass_time(seconds):
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            secs = seconds % 60
            return f"{hours:d}:{minutes:02d}:{secs:05.2f}"

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


        if overlay_text:
            overlay_text = overlay_text.strip()
            if overlay_text:
                total_duration = len(matches) / fps
                lines.append(
                    f"Dialogue: 1,0:00:00.00,{format_ass_time(total_duration)},Default,,0,0,0,,{{\\an7}}{overlay_text}"
                )
        
        for index, entry in enumerate(matches):
            timestamp = self._extract_image_timestamp(entry["path"])
            start_time = index / fps
            end_time = (index + 1) / fps
            lines.append(
                f"Dialogue: 0,{format_ass_time(start_time)},{format_ass_time(end_time)},Default,,0,0,0,,{timestamp}"
            )
        
        temp_ass = tempfile.NamedTemporaryFile(delete=False, mode="w", encoding="utf-8", suffix=".ass")
        temp_ass.write("\n".join(lines))
        temp_ass.close()
        return temp_ass.name
    
    def _normalize_crop(self, crop):
        """Normalize the crop values into a tuple of (x, y, width, height)."""
        if crop is None:
            return None

        if isinstance(crop, str):
            crop = tuple(part.strip() for part in crop.split(",") if part.strip())

        if len(crop) != 4:
            raise ValueError("Crop must contain four values: x, y, width, height.")

        try:
            x, y, width, height = [int(value) for value in crop]
        except (TypeError, ValueError) as exc:
            raise ValueError("Crop values must be integers.") from exc

        if width <= 0 or height <= 0:
            raise ValueError("Crop width and height must be greater than zero.")

        return (x, y, width, height)

    def _build_video_filter(self, scale, subtitle_path_escaped, crop=None):
        """Build the ffmpeg video filter chain for export."""
        crop_values = self._normalize_crop(crop)
        filters = []

        if crop_values is not None:
            x, y, width, height = crop_values
            filters.append(f"crop={width}:{height}:{x}:{y}")

        if scale != 1.0:
            filters.append(f"scale=trunc(iw*{scale}/2)*2:trunc(ih*{scale}/2)*2")

        filters.append(f"subtitles='{subtitle_path_escaped}'")
        return ",".join(filters)

    def export(self, matches, output, fps=15, scale=1.0, codec="libx264", preset="medium", crf=23, crop=None, progress_callback=None, overlay_text=None):
        """Export matched images to video file."""
        save_path = os.path.abspath(output)
        if not matches:
            raise ValueError("No images to export.")
        
        if shutil.which("ffmpeg") is None:
            raise RuntimeError("FFmpeg was not found on your system PATH.")
        
        # Create file list for ffmpeg concat
        with tempfile.NamedTemporaryFile(delete=False, mode="w", encoding="utf-8", suffix=".txt") as list_file:
            list_path = list_file.name
            for entry in matches:
                path_for_list = os.path.abspath(entry["path"]).replace("\\", "/")
                safe_path = path_for_list.replace("'", "'\\''")
                list_file.write(f"file '{safe_path}'\n")
        
        # Build subtitle file with timestamps
        subtitle_path = self._build_timestamp_ass(matches, fps, overlay_text)
        subtitle_path_quoted = os.path.abspath(subtitle_path).replace("\\", "/")
        subtitle_path_escaped = (subtitle_path_quoted.replace(":", "\\:").replace(",", "\\,").replace("'", "\\'"))

        video_filter = self._build_video_filter(
            scale=scale,
            subtitle_path_escaped=subtitle_path_escaped,
            crop=crop,
        )

        #Execute FFMPEG command
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
            save_path,
        ]
        
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        
        try:
            percent = 5
            total_frames = len(matches)
            if progress_callback:
                progress_callback(percent, f"Exporting frame 0/{total_frames}...")
            
            while True:
                line = process.stdout.readline()
                if not line and process.poll() is not None:
                    break
                if not line:
                    continue
                
                line = line.strip()
                if line.startswith("frame="):
                    try:
                        current_frame = int(line.split("=", 1)[1].strip())
                        progress_value = 5 + 85 * (current_frame / total_frames)
                        progress_value = min(90, max(5, progress_value))
                        if progress_value > percent:
                            percent = progress_value
                            if progress_callback:
                                progress_callback(percent, f"Exporting frame {current_frame}/{total_frames}...")
                    except ValueError:
                        pass
                
                elif line.startswith("progress="):
                    progress_state = line.split("=", 1)[1]
                    if progress_state == "end":
                        percent = 95
                        if progress_callback:
                            progress_callback(percent, "Finalizing render...")
        
        finally:
            retcode = process.poll()
            if retcode is None:
                process.wait()
                retcode = process.returncode
            
            # Clean up temporary files
            try:
                os.remove(list_path)
            except OSError:
                pass
            
            try:
                os.remove(subtitle_path)
            except OSError:
                pass
            
            if retcode != 0:
                stderr = process.stderr.read() if process.stderr else ""
                raise RuntimeError(f"FFmpeg failed with return code {retcode}.\n\n{stderr}")
            
            if progress_callback:
                progress_callback(100, "Export complete")

class TimelapseGeneratorApp:
    """GUI application for timelapse generation."""
    
    def __init__(self, root):
        self.root = root
        self.root.title("Timelapse Generator")
        self.root.resizable(True, True)
        self.root.geometry("900x700")
        
        self.generator = TimelapseGenerator()
        self.selected_dir = ""
        self.dir_change_after_id = None
        self.suppress_dir_trace = False
        
        self._build_ui()
    
    def _build_ui(self):
        """Build the GUI layout."""
        self.frame_main = ttk.LabelFrame(self.root, text=" Select Root Directory", padding=10)
        self.frame_main.pack(pady=10, fill="x", padx=10)
        
        self.btn_browse = ttk.Button(self.frame_main, text="📁 Browse", command=self.browse_directory)
        self.btn_browse.grid(row=0, column=0, padx=5, pady=2, sticky="w")
        
        self.dir_var = tk.StringVar()
        self.dir_var.trace_add("write", self.on_dir_var_changed)
        self.entry_dir = ttk.Entry(self.frame_main, textvariable=self.dir_var, width=50)
        self.entry_dir.grid(row=0, column=1, columnspan=3, sticky="we", padx=5, pady=2)
        
        self.lbl_summary = ttk.Label(self.frame_main, text="", foreground="green")
        self.lbl_summary.grid(row=1, column=0, columnspan=4, sticky="w", padx=5, pady=(5, 0))
        
        self.frame_filters = ttk.LabelFrame(self.root, text=" Filters ", padding=10)
        self.frame_filters.pack(pady=10, fill="x", padx=10)
        
        ttk.Label(self.frame_filters, text="Start Date:").grid(row=0, column=0, padx=5, sticky="w")
        self.combo_start = ttk.Combobox(self.frame_filters, state="disabled", width=15)
        self.combo_start.grid(row=0, column=1, padx=5)
        
        ttk.Label(self.frame_filters, text="End Date:").grid(row=0, column=2, padx=5, sticky="w")
        self.combo_end = ttk.Combobox(self.frame_filters, state="disabled", width=15)
        self.combo_end.grid(row=0, column=3, padx=5)
        
        ttk.Label(self.frame_filters, text="Rig:").grid(row=1, column=0, padx=5, sticky="w")
        self.combo_rig = ttk.Combobox(self.frame_filters, state="disabled", width=18)
        self.combo_rig.grid(row=1, column=1, padx=5, pady=(5, 0))
        
        ttk.Label(self.frame_filters, text="Camera:").grid(row=1, column=2, padx=5, sticky="w")
        self.combo_camera = ttk.Combobox(self.frame_filters, state="disabled", width=18)
        self.combo_camera.grid(row=1, column=3, padx=5, pady=(5, 0))
        
        ttk.Label(self.frame_filters, text="Lighting:").grid(row=2, column=0, padx=5, sticky="w")
        self.combo_lighting = ttk.Combobox(self.frame_filters, state="disabled", width=18)
        self.combo_lighting.grid(row=2, column=1, padx=5, pady=(5, 0))
        
        self.lbl_match_status = ttk.Label(self.frame_filters, text="", foreground="blue")
        self.lbl_match_status.grid(row=3, column=0, columnspan=4, sticky="w", padx=5, pady=(10, 0))
        
        self.frame_results = ttk.LabelFrame(self.root, text=" Matched Images ", padding=10)
        self.frame_results.pack(pady=10, fill="both", expand=True, padx=10)
        
        self.match_listbox = tk.Listbox(self.frame_results, height=12)
        self.match_listbox.pack(side="left", fill="both", expand=True, padx=(0, 5))
        
        self.scrollbar = ttk.Scrollbar(self.frame_results, orient="vertical", command=self.match_listbox.yview)
        self.match_listbox.configure(yscrollcommand=self.scrollbar.set)
        self.scrollbar.pack(side="right", fill="y")
        
        self.frame_encoding = ttk.LabelFrame(self.root, text=" Encoding Options ", padding=10)
        self.frame_encoding.pack(pady=10, fill="x", padx=10)
        
        ttk.Label(self.frame_encoding, text="Scale:").grid(row=0, column=0, padx=5, sticky="w")
        self.scale_var = tk.DoubleVar(value=1.0)
        self.entry_scale = ttk.Entry(self.frame_encoding, textvariable=self.scale_var, width=10)
        self.entry_scale.grid(row=0, column=1, padx=5, pady=2, sticky="w")
        
        ttk.Label(self.frame_encoding, text="FPS:").grid(row=0, column=2, padx=5, sticky="w")
        self.fps_var = tk.IntVar(value=30)
        self.entry_fps = ttk.Entry(self.frame_encoding, textvariable=self.fps_var, width=10)
        self.entry_fps.grid(row=0, column=3, padx=5, pady=2, sticky="w")
        
        ttk.Label(self.frame_encoding, text="Codec:").grid(row=1, column=0, padx=5, sticky="w")
        self.codec_var = tk.StringVar(value="libx264")
        self.combo_codec = ttk.Combobox(self.frame_encoding, textvariable=self.codec_var, values=("libx264", "libx265", "mpeg4"), state="readonly", width=12)
        self.combo_codec.grid(row=1, column=1, padx=5, pady=2, sticky="w")
        
        ttk.Label(self.frame_encoding, text="Preset:").grid(row=1, column=2, padx=5, sticky="w")
        self.preset_var = tk.StringVar(value="medium")
        self.combo_preset = ttk.Combobox(self.frame_encoding, textvariable=self.preset_var, values=("ultrafast", "superfast", "veryfast", "faster", "fast", "medium", "slow", "slower", "veryslow"), state="readonly", width=12)
        self.combo_preset.grid(row=1, column=3, padx=5, pady=2, sticky="w")
        
        ttk.Label(self.frame_encoding, text="CRF:").grid(row=2, column=0, padx=5, sticky="w")
        self.crf_var = tk.IntVar(value=23)
        self.entry_crf = ttk.Entry(self.frame_encoding, textvariable=self.crf_var, width=10)
        self.entry_crf.grid(row=2, column=1, padx=5, pady=2, sticky="w")

        ttk.Label(self.frame_encoding, text="Crop X:").grid(row=3, column=0, padx=5, sticky="w")
        self.crop_x_var = tk.IntVar(value=0)
        self.entry_crop_x = ttk.Entry(self.frame_encoding, textvariable=self.crop_x_var, width=10)
        self.entry_crop_x.grid(row=3, column=1, padx=5, pady=2, sticky="w")

        ttk.Label(self.frame_encoding, text="Crop Y:").grid(row=3, column=2, padx=5, sticky="w")
        self.crop_y_var = tk.IntVar(value=0)
        self.entry_crop_y = ttk.Entry(self.frame_encoding, textvariable=self.crop_y_var, width=10)
        self.entry_crop_y.grid(row=3, column=3, padx=5, pady=2, sticky="w")

        ttk.Label(self.frame_encoding, text="Crop W:").grid(row=4, column=0, padx=5, sticky="w")
        self.crop_w_var = tk.IntVar(value=0)
        self.entry_crop_w = ttk.Entry(self.frame_encoding, textvariable=self.crop_w_var, width=10)
        self.entry_crop_w.grid(row=4, column=1, padx=5, pady=2, sticky="w")

        ttk.Label(self.frame_encoding, text="Crop H:").grid(row=4, column=2, padx=5, sticky="w")
        self.crop_h_var = tk.IntVar(value=0)
        self.entry_crop_h = ttk.Entry(self.frame_encoding, textvariable=self.crop_h_var, width=10)
        self.entry_crop_h.grid(row=4, column=3, padx=5, pady=2, sticky="w")
        
        self.frame_actions = ttk.Frame(self.root, padding=10)
        self.frame_actions.pack(pady=10, fill="x", padx=10)
        
        self.btn_generate = ttk.Button(self.frame_actions, text="Export Timelapse Video", command=self.generate_timelapse, state="disabled")
        self.btn_generate.grid(row=0, column=0, padx=5, pady=2, sticky="w")
        
        self.frame_progress = ttk.Frame(self.root, padding=10)
        self.frame_progress.pack(pady=(0, 10), fill="x", padx=10)
        
        self.progress_var = tk.DoubleVar(value=0.0)
        self.progress_bar = ttk.Progressbar(self.frame_progress, variable=self.progress_var, maximum=100, mode="determinate")
        self.progress_bar.pack(fill="x", expand=True, side="left", padx=(0, 5))
        
        self.progress_label = ttk.Label(self.frame_progress, text="Idle")
        self.progress_label.pack(side="left")
    
    def browse_directory(self):
        """Open directory browser dialog."""
        directory = filedialog.askdirectory(title="Select Timelapse Directory")
        if not directory:
            return
        
        self.set_directory_text(directory)
        self.scan_images(preserve_selection=True)
    
    def set_directory_text(self, directory):
        """Set directory path and update UI."""
        self.selected_dir = os.path.normpath(directory)
        self.suppress_dir_trace = True
        self.dir_var.set(self.selected_dir)
        self.suppress_dir_trace = False
    
    def on_dir_var_changed(self, *args):
        """Handle directory input changes with debouncing."""
        if self.suppress_dir_trace:
            return
        
        if self.dir_change_after_id:
            self.root.after_cancel(self.dir_change_after_id)
        
        self.dir_change_after_id = self.root.after(300, self.handle_dir_change)
    
    def handle_dir_change(self):
        """Process directory change after debounce."""
        self.dir_change_after_id = None
        new_dir = self.dir_var.get().strip()
        
        if not new_dir:
            self.selected_dir = ""
            self.lbl_summary.config(text="")
            self.disable_filters()
            return
        
        if new_dir == self.selected_dir:
            return
        
        self.selected_dir = new_dir
        if os.path.isdir(self.selected_dir):
            self.scan_images(preserve_selection=True)
        else:
            self.lbl_summary.config(text="Invalid directory")
            self.disable_filters()
    
    def scan_images(self, preserve_selection=False):
        """Scan directory for images and update filter options."""
        previous_start = self.combo_start.get() if preserve_selection else None
        previous_end = self.combo_end.get() if preserve_selection else None
        previous_rig = self.combo_rig.get() if preserve_selection else None
        previous_camera = self.combo_camera.get() if preserve_selection else None
        previous_lighting = self.combo_lighting.get() if preserve_selection else None
        
        try:
            stats = self.generator.scan(self.selected_dir)
            self.lbl_summary.config(
                text=f"Found {stats['total_images']} images across {stats['dates']} dates with {stats['rigs']} rigs, {stats['cameras']} cameras, {stats['lightings']} lighting settings"
            )
            
            self.enable_filters(
                previous_start=previous_start,
                previous_end=previous_end,
                previous_rig=previous_rig,
                previous_camera=previous_camera,
                previous_lighting=previous_lighting,
            )
        except ValueError as e:
            messagebox.showwarning("Scan Error", str(e))
            self.disable_filters()
    
    def enable_filters(self, previous_start=None, previous_end=None, previous_rig=None, previous_camera=None, previous_lighting=None):
        """Enable filter dropdowns with scanned data."""
        self.combo_start.config(values=self.generator.unique_dates, state="readonly")
        self.combo_end.config(values=self.generator.unique_dates, state="readonly")
        self.combo_rig.config(values=self.generator.rig_options, state="readonly")
        self.combo_camera.config(values=self.generator.camera_options, state="readonly")
        self.combo_lighting.config(values=self.generator.lighting_options, state="readonly")
        
        if previous_start in self.generator.unique_dates:
            self.combo_start.set(previous_start)
        else:
            self.combo_start.current(0)
        
        if previous_end in self.generator.unique_dates:
            self.combo_end.set(previous_end)
        else:
            self.combo_end.current(len(self.generator.unique_dates) - 1)
        
        self.combo_rig.set(previous_rig if previous_rig in self.generator.rig_options else "All")
        self.combo_camera.set(previous_camera if previous_camera in self.generator.camera_options else "All")
        self.combo_lighting.set(previous_lighting if previous_lighting in self.generator.lighting_options else "All")
        
        self.combo_start.bind("<<ComboboxSelected>>", self.on_filter_change)
        self.combo_end.bind("<<ComboboxSelected>>", self.on_filter_change)
        self.combo_rig.bind("<<ComboboxSelected>>", self.on_filter_change)
        self.combo_camera.bind("<<ComboboxSelected>>", self.on_filter_change)
        self.combo_lighting.bind("<<ComboboxSelected>>", self.on_filter_change)
        
        self.btn_generate.config(state="normal")
        self.update_match_status()
    
    def disable_filters(self):
        """Disable all filter controls."""
        self.combo_start.config(values=[], state="disabled")
        self.combo_end.config(values=[], state="disabled")
        self.combo_rig.config(values=[], state="disabled")
        self.combo_camera.config(values=[], state="disabled")
        self.combo_lighting.config(values=[], state="disabled")
        self.combo_start.set("")
        self.combo_end.set("")
        self.combo_rig.set("")
        self.combo_camera.set("")
        self.combo_lighting.set("")
        self.match_listbox.delete(0, tk.END)
        self.lbl_match_status.config(text="")
        self.btn_generate.config(state="disabled")
        self._set_progress(0, "Idle")
    
    def on_filter_change(self, event=None):
        """Handle filter changes."""
        self.update_match_status()
    
    def get_matching_images(self):
        """Get images matching current filter selections."""
        return self.generator.get_matching_images(
            start=self.combo_start.get() or None,
            end=self.combo_end.get() or None,
            rig=self.combo_rig.get() or "All",
            camera=self.combo_camera.get() or "All",
            lighting=self.combo_lighting.get() or "All",
        )
    
    def update_match_status(self):
        """Update match count and preview list."""
        matches = self.get_matching_images()
        self.lbl_match_status.config(
            text=f"Matched {len(matches)} images across {len({m['date'] for m in matches})} dates"
        )
        
        self.match_listbox.delete(0, tk.END)
        for entry in matches[:200]:
            self.match_listbox.insert(tk.END, f"{entry['date']} | {entry['rig']} | {entry['camera']} | {entry['lighting']}")
        
        if len(matches) > 200:
            self.match_listbox.insert(tk.END, f"... and {len(matches) - 200} more images")
    
    def _set_progress(self, value, message):
        """Update progress bar."""
        self.progress_var.set(value)
        self.progress_bar.config(mode="determinate")
        self.progress_label.config(text=message)
        self.root.update_idletasks()
    
    def _progress_callback(self, value, message):
        """Callback for progress updates from generator."""
        self.root.after(0, self._set_progress, value, message)
    
    def generate_timelapse(self):
        """Start timelapse export process."""
        matches = self.get_matching_images()
        if not matches:
            messagebox.showwarning("No images selected", "No images match the current filters.")
            return
        
        if shutil.which("ffmpeg") is None:
            messagebox.showerror("FFmpeg Missing", "FFmpeg was not found on your system PATH.")
            return
        
        save_path = filedialog.asksaveasfilename(
            title="Save timelapse video",
            defaultextension=".mp4",
            filetypes=[("MP4 video", "*.mp4"), ("MOV video", "*.mov"), ("MKV video", "*.mkv")],
        )
        if not save_path:
            return
        
        # Validate inputs
        try:
            scale = float(self.scale_var.get())
            if scale <= 0:
                raise ValueError
        except (ValueError, tk.TclError):
            messagebox.showerror("Invalid Scale", "Scale must be a positive number.")
            return
        
        try:
            fps = int(self.fps_var.get())
            if fps <= 0:
                raise ValueError
        except (ValueError, tk.TclError):
            messagebox.showerror("Invalid FPS", "FPS must be a positive integer.")
            return
        
        codec = self.codec_var.get() or "libx264"
        preset = self.preset_var.get() or "medium"
        
        try:
            crf = int(self.crf_var.get())
            if crf < 0 or crf > 51:
                raise ValueError
        except (ValueError, tk.TclError):
            messagebox.showerror("Invalid CRF", "CRF must be an integer between 0 and 51.")
            return

        try:
            crop = (
                int(self.crop_x_var.get()),
                int(self.crop_y_var.get()),
                int(self.crop_w_var.get()),
                int(self.crop_h_var.get()),
            )
            if all(value == 0 for value in crop):
                crop = None
            else:
                crop = self.generator._normalize_crop(crop)
        except (ValueError, tk.TclError):
            messagebox.showerror("Invalid Crop", "Crop values must be integers. Use 0 for no offset and provide width/height greater than zero when cropping.")
            return
        
        self._set_progress(5, "Preparing export...")
        self.btn_generate.config(state="disabled")
        
        # Run export in separate thread
        export_thread = threading.Thread(
            target=self._run_export,
            args=(matches, save_path, fps, scale, codec, preset, crf, crop),
            daemon=True,
        )
        export_thread.start()
    
    def _run_export(self, matches, save_path, fps, scale, codec, preset, crf, crop):
        """Run export in background thread."""
        try:
            self.generator.export(
                matches=matches,
                output=save_path,
                fps=fps,
                scale=scale,
                codec=codec,
                preset=preset,
                crf=crf,
                progress_callback=self._progress_callback,
                crop=crop,
            )
            self.root.after(0, lambda: messagebox.showinfo("Success", f"Exported {len(matches)} images to {save_path}."))
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Export Error", str(e)))
        finally:
            self.root.after(0, lambda: self.btn_generate.config(state="normal"))

def main():
    """Main entry point."""
    gui_parser = argparse.ArgumentParser(add_help=False)
    gui_parser.add_argument("--gui", action="store_true", help="Launch the GUI application.")
    gui_args, cli_args = gui_parser.parse_known_args()

    #Launch GUI or proceed to CLI
    if gui_args.gui:
        root = tk.Tk()
        app = TimelapseGeneratorApp(root)
        root.mainloop()
        return

    else:
        parser = argparse.ArgumentParser(description="Generate timelapse videos from timestamped images.")
        parser.add_argument("input", type=str,help="Root directory containing the images folder.")
        parser.add_argument("output", type=str, help="Output video filename.")
        parser.add_argument("start", type=str, help="Start date (YYYY-MM-DD)")
        parser.add_argument("end", type=str, help="End date (YYYY-MM-DD)")
        parser.add_argument("--rig", type=str, default="All", help="Filter by setup name")
        parser.add_argument("--camera", type=str, default="All", help="Filter by camera configuration")
        parser.add_argument("--lighting", type=str, default="All", help="Filter by lighting configuration")
        parser.add_argument("--fps", type=int, default=15, help="Frames per second")
        parser.add_argument("--scale", type=float, default=1.0, help="Scale the image resolution by a floating point scaler")
        parser.add_argument("--codec", default="libx264", choices=["libx264", "libx265", "mpeg4"])
        parser.add_argument("--preset", default="medium", choices=["ultrafast", "superfast", "veryfast", "faster", "fast", "medium", "slow", "slower", "veryslow"], help="Encoding preset for the selected codec. Slower = better compression.")
        parser.add_argument("--crf", type=int, default=23)
        parser.add_argument("--overlay", type=str, default=None, help="Optional text overlay to display on the video. (top left)")
        parser.add_argument("--crop", type=int, nargs=4,default=None, metavar=("x", "y", "width", "height"), help="Crop an area of the timelapse")
        args = parser.parse_args(cli_args)

        # Scan for files
        generator = TimelapseGenerator()
        try:
            generator.scan(args.input)
        except ValueError as e:
            raise SystemExit(f"Scan error: {e}")
        
        matches = generator.get_matching_images(
            start=args.start,
            end=args.end,
            rig=args.rig,
            camera=args.camera,
            lighting=args.lighting,
        )
        
        if not matches:
            raise SystemExit("No matching images found.")
        else:
            print(f"Found {len(matches)} matching images")


        if args.crop:
            crop = generator._normalize_crop(args.crop)
        else:
            crop = None
        
        try:
            def cli_progress(value, message):
                print(f"[{value:3.0f}%] {message}")

            generator.export(
                matches=matches,
                output=args.output,
                fps=args.fps,
                scale=args.scale,
                codec=args.codec,
                preset=args.preset,
                crf=args.crf,
                progress_callback=cli_progress,
                crop=crop,
                overlay_text=args.overlay,
            )
            print("Export complete!")
        except Exception as e:
            raise SystemExit(f"Export error: {e}")


if __name__ == "__main__":
    main()
