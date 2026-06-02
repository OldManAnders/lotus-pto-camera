import os
import shutil
import subprocess
import tempfile
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from datetime import datetime

IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".bmp", ".gif", ".tif", ".tiff", ".webp", ".heic")


class TimelapseGeneratorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Timelapse Generator")
        self.root.resizable(True, True)
        self.root.padx = 20
        self.root.pady = 20

        self.selected_dir = ""
        self.unique_dates = []
        self.image_index = {}
        self.rig_options = ["All"]
        self.camera_options = ["All"]
        self.lighting_options = ["All"]

        self.dir_change_after_id = None
        self.suppress_dir_trace = False

        self._build_ui()

    def _build_ui(self):
        self.frame_main = ttk.LabelFrame(self.root, text=" Select Root Directory", padding=10)
        self.frame_main.pack(pady=10, fill="x")

        self.btn_browse = ttk.Button(self.frame_main, text="📁 Browse", command=self.browse_directory)
        self.btn_browse.grid(row=0, column=0, padx=5, pady=2, sticky="w")

        self.dir_var = tk.StringVar()
        self.dir_var.trace_add("write", self.on_dir_var_changed)
        self.entry_dir = ttk.Entry(self.frame_main, textvariable=self.dir_var, width=50)
        self.entry_dir.grid(row=0, column=1, columnspan=3, sticky="we", padx=5, pady=2)

        self.lbl_summary = ttk.Label(self.frame_main, text="", foreground="green")
        self.lbl_summary.grid(row=1, column=0, columnspan=4, sticky="w", padx=5, pady=(5, 0))

        self.frame_filters = ttk.LabelFrame(self.root, text=" Filters ", padding=10)
        self.frame_filters.pack(pady=10, fill="x")

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
        self.frame_results.pack(pady=10, fill="both", expand=True)

        self.match_listbox = tk.Listbox(self.frame_results, height=12)
        self.match_listbox.pack(side="left", fill="both", expand=True, padx=(0, 5))

        self.scrollbar = ttk.Scrollbar(self.frame_results, orient="vertical", command=self.match_listbox.yview)
        self.match_listbox.configure(yscrollcommand=self.scrollbar.set)
        self.scrollbar.pack(side="right", fill="y")

        self.frame_encoding = ttk.LabelFrame(self.root, text=" Encoding Options ", padding=10)
        self.frame_encoding.pack(pady=10, fill="x")

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

        self.frame_actions = ttk.Frame(self.root, padding=10)
        self.frame_actions.pack(pady=10, fill="x")

        self.btn_generate = ttk.Button(self.frame_actions, text="Export Timelapse Video", command=self.generate_timelapse, state="disabled")
        self.btn_generate.grid(row=0, column=0, padx=5, pady=2, sticky="w")

        self.frame_progress = ttk.Frame(self.root, padding=10)
        self.frame_progress.pack(pady=(0, 10), fill="x")

        self.progress_var = tk.DoubleVar(value=0.0)
        self.progress_bar = ttk.Progressbar(self.frame_progress, variable=self.progress_var, maximum=100, mode="determinate")
        self.progress_bar.pack(fill="x", expand=True, side="left", padx=(0, 5))

        self.progress_label = ttk.Label(self.frame_progress, text="Idle")
        self.progress_label.pack(side="left")

    def browse_directory(self):
        directory = filedialog.askdirectory(title="Select Timelapse Directory")
        if not directory:
            return

        self.set_directory_text(directory)
        self.scan_images(preserve_selection=True)

    def set_directory_text(self, directory):
        self.selected_dir = os.path.normpath(directory)
        self.suppress_dir_trace = True
        self.dir_var.set(self.selected_dir)
        self.suppress_dir_trace = False

    def on_dir_var_changed(self, *args):
        if self.suppress_dir_trace:
            return

        if self.dir_change_after_id:
            self.root.after_cancel(self.dir_change_after_id)

        self.dir_change_after_id = self.root.after(300, self.handle_dir_change)

    def handle_dir_change(self):
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
        self.image_index = {}
        self.unique_dates = []
        self.rig_options = ["All"]
        self.camera_options = ["All"]
        self.lighting_options = ["All"]

        previous_start = self.combo_start.get() if preserve_selection else None
        previous_end = self.combo_end.get() if preserve_selection else None
        previous_rig = self.combo_rig.get() if preserve_selection else None
        previous_camera = self.combo_camera.get() if preserve_selection else None
        previous_lighting = self.combo_lighting.get() if preserve_selection else None

        images_root = os.path.join(self.selected_dir, "images")
        if not os.path.isdir(images_root):
            messagebox.showwarning("Images folder missing", "Selected directory must contain an 'images' folder.")
            self.disable_filters()
            return

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
            messagebox.showwarning("No Images Found", "No timestamped images were found under the 'images' folder.")
            self.disable_filters()
            return

        self.unique_dates = [d.strftime("%Y-%m-%d") for d in sorted(found_dates)]
        self.rig_options += sorted(rigs)
        self.camera_options += sorted(cameras)
        self.lighting_options += sorted(lightings)

        self.lbl_summary.config(
            text=f"Found {total_images} images across {len(self.unique_dates)} dates with {len(rigs)} rigs, {len(cameras)} cameras, {len(lightings)} lighting settings"
        )

        self.enable_filters(
            previous_start=previous_start,
            previous_end=previous_end,
            previous_rig=previous_rig,
            previous_camera=previous_camera,
            previous_lighting=previous_lighting,
        )

    def enable_filters(self, previous_start=None, previous_end=None, previous_rig=None, previous_camera=None, previous_lighting=None):
        self.combo_start.config(values=self.unique_dates, state="readonly")
        self.combo_end.config(values=self.unique_dates, state="readonly")
        self.combo_rig.config(values=self.rig_options, state="readonly")
        self.combo_camera.config(values=self.camera_options, state="readonly")
        self.combo_lighting.config(values=self.lighting_options, state="readonly")

        if previous_start in self.unique_dates:
            self.combo_start.set(previous_start)
        else:
            self.combo_start.current(0)

        if previous_end in self.unique_dates:
            self.combo_end.set(previous_end)
        else:
            self.combo_end.current(len(self.unique_dates) - 1)

        self.combo_rig.set(previous_rig if previous_rig in self.rig_options else "All")
        self.combo_camera.set(previous_camera if previous_camera in self.camera_options else "All")
        self.combo_lighting.set(previous_lighting if previous_lighting in self.lighting_options else "All")

        self.combo_start.bind("<<ComboboxSelected>>", self.on_filter_change)
        self.combo_end.bind("<<ComboboxSelected>>", self.on_filter_change)
        self.combo_rig.bind("<<ComboboxSelected>>", self.on_filter_change)
        self.combo_camera.bind("<<ComboboxSelected>>", self.on_filter_change)
        self.combo_lighting.bind("<<ComboboxSelected>>", self.on_filter_change)

        self.btn_generate.config(state="normal")
        self.update_match_status()

    def disable_filters(self):
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

    def _set_progress(self, value, message):
        self.progress_var.set(value)
        self.progress_bar.config(mode="determinate")
        self.progress_label.config(text=message)
        self.root.update_idletasks()

    def _start_progress(self, message="Processing..."):
        self.progress_bar.config(mode="indeterminate")
        self.progress_bar.start(10)
        self.progress_label.config(text=message)
        self.root.update_idletasks()

    def _stop_progress(self):
        self.progress_bar.stop()
        self.progress_bar.config(mode="determinate")

    def _build_timestamp_ass(self, matches, fps):
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

    def _extract_image_timestamp(self, image_path):
        base_name = os.path.splitext(os.path.basename(image_path))[0]
        if len(base_name) >= 15 and base_name[8] == "-":
            try:
                dt = datetime.strptime(base_name[:15], "%Y%m%d-%H%M%S")
                return dt.strftime("%Y-%m-%d %H:%M:%S")
            except ValueError:
                pass
        return base_name

    def _run_ffmpeg_export(self, list_path, save_path, scale, fps, codec, preset, crf, total_ms, matches):
        subtitle_path = self._build_timestamp_ass(matches, fps)
        subtitle_path_quoted = os.path.abspath(subtitle_path).replace("\\", "/")
        subtitle_path_escaped = (
            subtitle_path_quoted
            .replace(":", "\\:")
            .replace(",", "\\,")
            .replace("'", "\\'")
        )
        scale_filter = (
            f"scale=trunc(iw*{scale}/2)*2:trunc(ih*{scale}/2)*2," \
            f"subtitles='{subtitle_path_escaped}'"
        )
        save_path = os.path.abspath(save_path)
        command = [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel", "error",
            "-f", "concat",
            "-safe", "0",
            "-r", str(fps),
            "-i", list_path,
            "-vf", scale_filter,
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

        percent = 5
        self.root.after(0, self._set_progress, percent, "Exporting... 0%")
        try:
            while True:
                line = process.stdout.readline()
                if not line and process.poll() is not None:
                    break
                if not line:
                    continue

                line = line.strip()
                if line.startswith("out_time_ms="):
                    try:
                        current_time_ms = int(line.split("=", 1)[1])
                    except ValueError:
                        current_time_ms = None

                    if total_ms and current_time_ms is not None:
                        mapped_progress = 5 + 85 * (current_time_ms / total_ms)
                        progress_value = min(90, max(5, mapped_progress))
                        if progress_value > percent:
                            percent = progress_value
                            self.root.after(0, self._set_progress, percent, f"Exporting... {percent:.0f}%")
                elif line.startswith("progress="):
                    progress_state = line.split("=", 1)[1]
                    if progress_state == "end":
                        percent = 95
                        self.root.after(0, self._set_progress, percent, "Finalizing render...")
        finally:
            retcode = process.poll()
            if retcode is None:
                process.wait()
                retcode = process.returncode

            try:
                os.remove(list_path)
            except OSError:
                pass

            try:
                os.remove(subtitle_path)
            except OSError:
                pass

            if retcode != 0:
                self.root.after(0, self._stop_progress)
                stderr = process.stderr.read() if process.stderr else ""
                self.root.after(0, self._set_progress, 0, "Export failed")
                self.root.after(0, lambda: self.btn_generate.config(state="normal"))
                self.root.after(0, lambda: messagebox.showerror("FFmpeg Error", f"FFmpeg failed with return code {retcode}.\n\n{stderr}"))
                return

            self.root.after(0, self._set_progress, 100, "Export complete")
            self.root.after(0, self._stop_progress)
            self.root.after(0, lambda: self.btn_generate.config(state="normal"))
            self.root.after(0, lambda: messagebox.showinfo("Timelapse Export Complete", f"Exported {len(self.get_matching_images())} images to {save_path}."))

    def on_filter_change(self, event=None):
        self.update_match_status()

    def get_matching_images(self):
        start = self.combo_start.get()
        end = self.combo_end.get()
        rig_filter = self.combo_rig.get()
        camera_filter = self.combo_camera.get()
        lighting_filter = self.combo_lighting.get()

        if not start or not end:
            return []

        try:
            start_date = datetime.strptime(start, "%Y-%m-%d").date()
            end_date = datetime.strptime(end, "%Y-%m-%d").date()
        except ValueError:
            return []

        if start_date > end_date:
            return []

        matches = []
        for date_key in self.unique_dates:
            if not (start <= date_key <= end):
                continue
            for entry in self.image_index.get(date_key, []):
                if rig_filter != "All" and entry["rig"] != rig_filter:
                    continue
                if camera_filter != "All" and entry["camera"] != camera_filter:
                    continue
                if lighting_filter != "All" and entry["lighting"] != lighting_filter:
                    continue
                matches.append(entry)

        return sorted(matches, key=lambda x: x["path"])

    def update_match_status(self):
        matches = self.get_matching_images()
        self.lbl_match_status.config(
            text=f"Matched {len(matches)} images across {len({m['date'] for m in matches})} dates"
        )

        self.match_listbox.delete(0, tk.END)
        for entry in matches[:200]:
            self.match_listbox.insert(tk.END, f"{entry['date']} | {entry['rig']} | {entry['camera']} | {entry['lighting']}")

        if len(matches) > 200:
            self.match_listbox.insert(tk.END, f"... and {len(matches) - 200} more images")

    def generate_timelapse(self):
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

        self._set_progress(0, "Loading and indexing frames...")
        with tempfile.NamedTemporaryFile(delete=False, mode="w", encoding="utf-8", suffix=".txt") as list_file:
            list_path = list_file.name
            for entry in matches:
                path_for_list = os.path.abspath(entry["path"]).replace("\\", "/")
                safe_path = path_for_list.replace("'", "'\\''")
                list_file.write(f"file '{safe_path}'\n")

        total_ms = int(len(matches) / fps * 1000)
        self._set_progress(5, "Preparing export...")
        self.btn_generate.config(state="disabled")

        export_thread = threading.Thread(
            target=self._run_ffmpeg_export,
            args=(list_path, save_path, scale, fps, codec, preset, crf, total_ms, matches),
            daemon=True,
        )
        export_thread.start()

if __name__ == "__main__":
    root = tk.Tk()
    app = TimelapseGeneratorApp(root)
    root.mainloop()
