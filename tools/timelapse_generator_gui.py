"""
GUI for the timelapse generator tool.

A thin tkinter wrapper around `TimelapseGenerator` (see timelapse_generator.py)
and `utils.parsing`: pick an image folder, filter the captured records by rig /
camera / lighting / date range / daily time windows, configure the ffmpeg export
(fps, scale, codec, preset, crf, crop, overlay), then run the generation from a
background thread so the GUI stays responsive.
"""
import json
import logging
import os
import sys
import threading
import tkinter as tk
from datetime import datetime
from tkinter import filedialog, messagebox, ttk

# Make the project root and this script's folder importable regardless of
# how the script is launched (utils lives in the root, timelapse_generator here).
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_SCRIPT_DIR))
sys.path.insert(0, _SCRIPT_DIR)

from utils import parsing
from timelapse_generator import TimelapseGenerator

CODECS = ["libx264", "libx265", "mpeg4"]
PRESETS = ["ultrafast", "superfast", "veryfast", "faster", "fast", "medium",
           "slow", "slower", "veryslow"]


class _LogHandler(logging.Handler):
    """Route logging records to a GUI callback (safe across threads)."""

    def __init__(self, callback):
        super().__init__()
        self.callback = callback

    def emit(self, record):
        try:
            self.callback(f"[{record.levelname}] {record.getMessage()}")
        except Exception:
            pass


class TimelapseGuiApp:

    def __init__(self, root):
        self.root = root
        self.root.title("Timelapse Generator")
        self.root.geometry("760x920")
        self.root.resizable(False, False)

        self.time_periods = []  # list of (start_str, end_str)

        self._records_cache = None  # parsed records for the current input folder
        self._cache_input_dir = None
        self._filtered_records = []  # result of the latest filter pass

        self._build_scrollable_layout()
        self._set_defaults()

    # ------------------------------------------------------------------ #
    # Layout
    # ------------------------------------------------------------------ #
    def _build_scrollable_layout(self):
        canvas = tk.Canvas(self.root, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.root, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)

        main_frame = ttk.Frame(canvas, padding="15")
        main_frame.bind("<Configure>",
                        lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=main_frame, anchor="nw")

        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Mouse wheel scrolling
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-event.delta / 120), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        self._build_io_section(main_frame)
        self._build_date_section(main_frame)
        self._build_filter_section(main_frame)
        self._build_time_period_section(main_frame)
        self._build_video_section(main_frame)
        self._build_overlay_section(main_frame)
        self._build_settings_section(main_frame)
        self._build_run_section(main_frame)
        self._build_log_section(main_frame)

    def _build_io_section(self, parent):
        frame = ttk.LabelFrame(parent, text=" Input & Output ", padding="10")
        frame.pack(fill=tk.X, pady=5)

        ttk.Label(frame, text="Input Folder:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.input_ent = ttk.Entry(frame)
        self.input_ent.grid(row=0, column=1, sticky=tk.EW, pady=2, padx=5)
        frame.columnconfigure(1, weight=1)
        ttk.Button(frame, text="Browse...", command=self.browse_input, width=10).grid(
            row=0, column=2, pady=2)

        ttk.Label(frame, text="Output File:").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.output_ent = ttk.Entry(frame)
        self.output_ent.grid(row=1, column=1, sticky=tk.EW, pady=2, padx=5)
        ttk.Button(frame, text="Browse...", command=self.browse_output, width=10).grid(
            row=1, column=2, pady=2)

    def _build_date_section(self, parent):
        frame = ttk.LabelFrame(parent, text=" Date Range ", padding="10")
        frame.pack(fill=tk.X, pady=5)

        ttk.Label(frame, text="Start (YYYY-MM-DD):").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.start_ent = ttk.Entry(frame, width=14)
        self.start_ent.grid(row=0, column=1, sticky=tk.W, pady=2, padx=5)

        ttk.Label(frame, text="End (YYYY-MM-DD):").grid(row=0, column=2, sticky=tk.W, pady=2)
        self.end_ent = ttk.Entry(frame, width=14)
        self.end_ent.grid(row=0, column=3, sticky=tk.W, pady=2, padx=5)

    def _build_filter_section(self, parent):
        frame = ttk.LabelFrame(parent, text=" Filters ", padding="10")
        frame.pack(fill=tk.X, pady=5)

        ttk.Label(frame, text="Rig:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.rig_cmb = ttk.Combobox(frame, state="readonly")
        self.rig_cmb.grid(row=0, column=1, sticky=tk.EW, pady=2, padx=5)
        frame.columnconfigure(1, weight=1)
        ttk.Button(frame, text="Scan Options", command=self.scan_options, width=12).grid(
            row=0, column=2, sticky=tk.EW, pady=2)

        lists = ttk.Frame(frame)
        lists.grid(row=1, column=0, columnspan=3, sticky=tk.EW, pady=(6, 0))

        cam_frame = ttk.LabelFrame(lists, text=" Camera Configs (multi-select) ", padding="5")
        cam_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.camera_lb = tk.Listbox(cam_frame, height=4, selectmode=tk.EXTENDED,
                                    exportselection=False)
        cam_scroll = ttk.Scrollbar(cam_frame, orient="vertical", command=self.camera_lb.yview)
        self.camera_lb.configure(yscrollcommand=cam_scroll.set)
        self.camera_lb.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        cam_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        light_frame = ttk.LabelFrame(lists, text=" Lighting Configs (multi-select) ", padding="5")
        light_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(6, 0))
        self.lighting_lb = tk.Listbox(light_frame, height=4, selectmode=tk.EXTENDED,
                                      exportselection=False)
        light_scroll = ttk.Scrollbar(light_frame, orient="vertical", command=self.lighting_lb.yview)
        self.lighting_lb.configure(yscrollcommand=light_scroll.set)
        self.lighting_lb.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        light_scroll.pack(side=tk.RIGHT, fill=tk.Y)

    def _build_time_period_section(self, parent):
        frame = ttk.LabelFrame(parent, text=" Time Periods (daily time windows) ", padding="10")
        frame.pack(fill=tk.X, pady=5)

        ttk.Label(frame, text="Start (HH:MM):").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.tp_start_ent = ttk.Entry(frame, width=8)
        self.tp_start_ent.grid(row=0, column=1, sticky=tk.W, pady=2, padx=5)
        ttk.Label(frame, text="End (HH:MM):").grid(row=0, column=2, sticky=tk.W, pady=2)
        self.tp_end_ent = ttk.Entry(frame, width=8)
        self.tp_end_ent.grid(row=0, column=3, sticky=tk.W, pady=2, padx=5)
        ttk.Button(frame, text="+ Add", command=self.add_time_period, width=8).grid(
            row=0, column=4, padx=(5, 0), pady=2)

        self.time_period_list = tk.Listbox(frame, height=3, exportselection=False)
        self.time_period_list.grid(row=1, column=0, columnspan=4, sticky=tk.EW, pady=(6, 0))
        ttk.Button(frame, text="Remove Selected", command=self.remove_time_period).grid(
            row=1, column=4, padx=(5, 0), sticky=tk.N)

    def _build_video_section(self, parent):
        frame = ttk.LabelFrame(parent, text=" Video Options ", padding="10")
        frame.pack(fill=tk.X, pady=5)

        ttk.Label(frame, text="FPS:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.fps_spin = ttk.Spinbox(frame, from_=1, to=120, width=8)
        self.fps_spin.grid(row=0, column=1, sticky=tk.W, pady=2, padx=5)

        ttk.Label(frame, text="Scale:").grid(row=0, column=2, sticky=tk.W, pady=2)
        self.scale_ent = ttk.Entry(frame, width=8)
        self.scale_ent.grid(row=0, column=3, sticky=tk.W, pady=2, padx=5)

        ttk.Label(frame, text="Codec:").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.codec_cmb = ttk.Combobox(frame, values=CODECS, state="readonly", width=10)
        self.codec_cmb.grid(row=1, column=1, sticky=tk.W, pady=2, padx=5)

        ttk.Label(frame, text="Preset:").grid(row=1, column=2, sticky=tk.W, pady=2)
        self.preset_cmb = ttk.Combobox(frame, values=PRESETS, state="readonly", width=10)
        self.preset_cmb.grid(row=1, column=3, sticky=tk.W, pady=2, padx=5)

        ttk.Label(frame, text="CRF:").grid(row=2, column=0, sticky=tk.W, pady=2)
        self.crf_spin = ttk.Spinbox(frame, from_=0, to=51, width=8)
        self.crf_spin.grid(row=2, column=1, sticky=tk.W, pady=2, padx=5)

        ttk.Label(frame, text="Crop (x y w h):").grid(row=2, column=2, sticky=tk.W, pady=2)
        crop = ttk.Frame(frame)
        crop.grid(row=2, column=3, sticky=tk.W, pady=2, padx=5)
        self.crop_x_ent = ttk.Entry(crop, width=6)
        self.crop_x_ent.pack(side=tk.LEFT)
        self.crop_y_ent = ttk.Entry(crop, width=6)
        self.crop_y_ent.pack(side=tk.LEFT, padx=(4, 0))
        self.crop_w_ent = ttk.Entry(crop, width=6)
        self.crop_w_ent.pack(side=tk.LEFT, padx=(4, 0))
        self.crop_h_ent = ttk.Entry(crop, width=6)
        self.crop_h_ent.pack(side=tk.LEFT, padx=(4, 0))

        self.verbose_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(frame, text="Verbose Logging", variable=self.verbose_var).grid(
            row=3, column=2, columnspan=2, sticky=tk.W, pady=(6, 0))

    def _build_overlay_section(self, parent):
        frame = ttk.LabelFrame(parent, text=" Overlay ", padding="10")
        frame.pack(fill=tk.X, pady=5)

        ttk.Label(frame, text="Overlay Text:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.overlay_ent = ttk.Entry(frame)
        self.overlay_ent.grid(row=0, column=1, sticky=tk.EW, pady=2, padx=5)
        frame.columnconfigure(1, weight=1)

    def _build_settings_section(self, parent):
        frame = ttk.LabelFrame(parent, text=" Settings ", padding="10")
        frame.pack(fill=tk.X, pady=5)

        ttk.Button(frame, text="Export JSON", command=self.export_settings).pack(
            side=tk.LEFT, fill=tk.X, expand=True, ipady=2)
        ttk.Button(frame, text="Import JSON", command=self.import_settings).pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=(6, 0), ipady=2)

    def _build_run_section(self, parent):
        frame = ttk.Frame(parent)
        frame.pack(fill=tk.X, pady=10)

        self.preview_btn = ttk.Button(frame, text="Preview Match Count",
                                      command=self.preview_threaded)
        self.preview_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5), ipady=4)

        self.generate_btn = ttk.Button(frame, text="GENERATE TIMELAPSE",
                                       command=self.generate_threaded)
        self.generate_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=4)

        self.progress = ttk.Progressbar(parent, maximum=100, mode="determinate")
        self.progress.pack(fill=tk.X, pady=(8, 4))
        self.status_lbl = ttk.Label(parent, text="Ready")
        self.status_lbl.pack(fill=tk.X)

    def _build_log_section(self, parent):
        frame = ttk.LabelFrame(parent, text=" Logs ", padding="5")
        frame.pack(fill=tk.BOTH, expand=True, pady=(5, 0))

        self.log_text = tk.Text(frame, height=8, state="disabled", wrap="word",
                                background="#f0f0f0")
        self.log_text.pack(fill=tk.BOTH, expand=True)

    def _set_defaults(self):
        today = datetime.now().strftime("%Y-%m-%d")
        self.start_ent.insert(0, today)
        self.end_ent.insert(0, today)

        self.fps_spin.set("15")
        self.crf_spin.set("23")
        self.scale_ent.insert(0, "1.0")
        self.codec_cmb.current(0)
        self.preset_cmb.current(PRESETS.index("medium"))

        self.rig_cmb["values"] = ["All"]
        self.rig_cmb.current(0)

    # ------------------------------------------------------------------ #
    # Browse helpers
    # ------------------------------------------------------------------ #
    def browse_input(self):
        selected = filedialog.askdirectory(title="Select input image folder")
        if selected:
            self.input_ent.delete(0, tk.END)
            self.input_ent.insert(0, selected)

    def browse_output(self):
        selected = filedialog.asksaveasfilename(
            title="Save timelapse as", defaultextension=".mp4",
            filetypes=[("Video files", "*.mp4 *.mkv *.avi"), ("All files", "*.*")])
        if selected:
            self.output_ent.delete(0, tk.END)
            self.output_ent.insert(0, selected)

    # ------------------------------------------------------------------ #
    # Settings (JSON import/export)
    # ------------------------------------------------------------------ #
    def export_settings(self):
        path = filedialog.asksaveasfilename(
            title="Export settings", defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")])
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self._collect_settings(), f, indent=2)
            self.log(f"Settings exported to {path}")
        except Exception as e:
            messagebox.showerror("Export Error", f"Could not save settings:\n{e}")

    def import_settings(self):
        path = filedialog.askopenfilename(
            title="Import settings", filetypes=[("JSON files", "*.json"), ("All files", "*.*")])
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                raise ValueError("Settings file must contain a JSON object.")
        except Exception as e:
            messagebox.showerror("Import Error", f"Could not read settings file:\n{e}")
            return
        try:
            self._apply_settings(data)
            self.log(f"Settings imported from {path}")
        except Exception as e:
            messagebox.showerror("Import Error", f"Could not apply settings:\n{e}")

    def _collect_settings(self):
        crop = None
        crop_vals = [self.crop_x_ent.get().strip(), self.crop_y_ent.get().strip(),
                     self.crop_w_ent.get().strip(), self.crop_h_ent.get().strip()]
        if all(crop_vals):
            try:
                crop = [int(v) for v in crop_vals]
            except ValueError:
                crop = crop_vals
        return {
            "input": self.input_ent.get().strip(),
            "output": self.output_ent.get().strip(),
            "start_date": self.start_ent.get().strip(),
            "end_date": self.end_ent.get().strip(),
            "rig": self.rig_cmb.get(),
            "rigs": list(self.rig_cmb["values"])[1:],
            "camera_configs": self._selected(self.camera_lb),
            "camera_options": list(self.camera_lb.get(0, tk.END)),
            "lighting_configs": self._selected(self.lighting_lb),
            "lighting_options": list(self.lighting_lb.get(0, tk.END)),
            "time_periods": [list(t) for t in self.time_periods],
            "fps": self.fps_spin.get(),
            "scale": self.scale_ent.get().strip(),
            "codec": self.codec_cmb.get(),
            "preset": self.preset_cmb.get(),
            "crf": self.crf_spin.get(),
            "crop": crop,
            "overlay": self.overlay_ent.get().strip(),
            "verbose": self.verbose_var.get(),
        }

    def _apply_settings(self, data):
        def _set(entry, value):
            entry.delete(0, tk.END)
            entry.insert(0, str(value))

        _set(self.input_ent, data.get("input", ""))
        _set(self.output_ent, data.get("output", ""))
        _set(self.start_ent, data.get("start_date", datetime.now().strftime("%Y-%m-%d")))
        _set(self.end_ent, data.get("end_date", datetime.now().strftime("%Y-%m-%d")))

        # Rig: restore the available rigs first so the selection can resolve
        rigs = data.get("rigs") or []
        self.rig_cmb["values"] = ["All"] + [r for r in rigs if r != "All"]
        rig = data.get("rig", "All")
        if rig not in self.rig_cmb["values"]:
            rig = "All"
        self.rig_cmb.current(self.rig_cmb["values"].index(rig))

        self._populate_and_select(self.camera_lb, data.get("camera_options") or [],
                                  data.get("camera_configs") or [])
        self._populate_and_select(self.lighting_lb, data.get("lighting_options") or [],
                                  data.get("lighting_configs") or [])

        # Time periods
        self.time_periods.clear()
        self.time_period_list.delete(0, tk.END)
        for period in data.get("time_periods") or []:
            try:
                datetime.strptime(period[0], "%H:%M")
                datetime.strptime(period[1], "%H:%M")
            except (ValueError, IndexError, TypeError):
                continue
            self.time_periods.append((period[0], period[1]))
            self.time_period_list.insert(tk.END, f"{period[0]} - {period[1]}")

        # Video options
        if data.get("fps") is not None:
            self.fps_spin.set(str(data["fps"]))
        if data.get("scale") is not None:
            _set(self.scale_ent, data["scale"])
        if data.get("codec") in CODECS:
            self.codec_cmb.set(data["codec"])
        if data.get("preset") in PRESETS:
            self.preset_cmb.set(data["preset"])
        if data.get("crf") is not None:
            self.crf_spin.set(str(data["crf"]))

        # Crop
        crop = data.get("crop")
        if isinstance(crop, (list, tuple)) and len(crop) == 4:
            _set(self.crop_x_ent, crop[0])
            _set(self.crop_y_ent, crop[1])
            _set(self.crop_w_ent, crop[2])
            _set(self.crop_h_ent, crop[3])
        else:
            for entry in (self.crop_x_ent, self.crop_y_ent, self.crop_w_ent, self.crop_h_ent):
                entry.delete(0, tk.END)

        _set(self.overlay_ent, data.get("overlay", ""))
        self.verbose_var.set(bool(data.get("verbose", False)))

    def _populate_and_select(self, listbox, options, selected):
        listbox.delete(0, tk.END)
        selected = set(selected)
        for i, opt in enumerate(options):
            listbox.insert(tk.END, opt)
            if opt in selected:
                listbox.selection_set(i)

    # ------------------------------------------------------------------ #
    # Scan / filter options
    # ------------------------------------------------------------------ #
    def scan_options(self):
        if not self.input_ent.get().strip():
            messagebox.showerror("Error", "Select an input folder first.")
            return
        self._set_busy(True)
        threading.Thread(target=self._scan_options_safe, daemon=True).start()

    def _scan_options_safe(self):
        try:
            input_dir = self.input_ent.get().strip()
            self.log(f"Scanning '{input_dir}' for available filter options...")
            records = self._load_records()
            rigs = sorted({r.camera_rig for r in records})
            cams = sorted({r.camera_config for r in records if r.camera_config is not None})
            lights = sorted({r.lighting_config for r in records if r.lighting_config is not None})
            self.root.after(0, lambda: self._populate_filter_options(rigs, cams, lights, len(records)))
        except Exception as e:
            self.root.after(0, lambda err=e: messagebox.showerror("Scan Error", str(err)))
        finally:
            self.root.after(0, self._set_busy, False)

    def _populate_filter_options(self, rigs, cams, lights, total):
        self.rig_cmb["values"] = ["All"] + rigs
        self.rig_cmb.current(0)
        self.camera_lb.delete(0, tk.END)
        for cam in cams:
            self.camera_lb.insert(tk.END, cam)
        self.lighting_lb.delete(0, tk.END)
        for light in lights:
            self.lighting_lb.insert(tk.END, light)
        self.log(f"Found {total} timestamped image(s): {len(rigs)} rig(s), "
                 f"{len(cams)} camera config(s), {len(lights)} lighting config(s).")

    # ------------------------------------------------------------------ #
    # Time period helpers
    # ------------------------------------------------------------------ #
    def add_time_period(self):
        start = self.tp_start_ent.get().strip()
        end = self.tp_end_ent.get().strip()
        if not start or not end:
            messagebox.showerror("Error", "Fill in both a start and end hour.")
            return
        try:
            datetime.strptime(start, "%H:%M")
            datetime.strptime(end, "%H:%M")
        except ValueError:
            messagebox.showerror("Error", "Time periods must use HH:MM format (e.g. 00:00).")
            return
        self.time_periods.append((start, end))
        self.time_period_list.insert(tk.END, f"{start} - {end}")
        self.tp_start_ent.delete(0, tk.END)
        self.tp_end_ent.delete(0, tk.END)

    def remove_time_period(self):
        sel = self.time_period_list.curselection()
        if not sel:
            return
        idx = sel[0]
        del self.time_periods[idx]
        self.time_period_list.delete(idx)

    # ------------------------------------------------------------------ #
    # Parse / filter pipeline
    # ------------------------------------------------------------------ #
    def _selected(self, listbox):
        indices = listbox.curselection()
        return [listbox.get(i) for i in indices]

    def _load_records(self, logger=None):
        input_dir = self.input_ent.get().strip()
        if not input_dir:
            raise ValueError("Input folder is required.")
        if self._records_cache is None or self._cache_input_dir != input_dir:
            self._records_cache = parsing.parse_images(input_dir, logger=logger)
            self._cache_input_dir = input_dir
        return self._records_cache

    def _parse_and_filter(self, logger=None):
        input_dir = self.input_ent.get().strip()
        if not input_dir:
            raise ValueError("Input folder is required.")

        start = self.start_ent.get().strip()
        end = self.end_ent.get().strip()
        try:
            start_date = datetime.strptime(start, "%Y-%m-%d").date()
            end_date = datetime.strptime(end, "%Y-%m-%d").date()
        except ValueError:
            raise ValueError("Dates must use YYYY-MM-DD format (e.g. 2026-07-01).")

        records = sorted(self._load_records(logger=logger), key=lambda r: r.timestamp)
        if not records:
            raise ValueError(f"No timestamped images were found in '{input_dir}'.")

        rig = self.rig_cmb.get()
        rig = None if rig in ("", "All") else rig

        camera_configs = self._selected(self.camera_lb) or None
        lighting_configs = self._selected(self.lighting_lb) or None

        time_ranges = None
        if self.time_periods:
            time_ranges = [(datetime.strptime(t[0], "%H:%M").time(),
                            datetime.strptime(t[1], "%H:%M").time())
                           for t in self.time_periods]

        self._filtered_records = parsing.filter_records(
            records,
            camera_rig=rig,
            camera_configs=camera_configs,
            lighting_configs=lighting_configs,
            date_range=(start_date, end_date),
            time_ranges=time_ranges,
            logger=logger,
        )
        self._filtered_records.sort(key=lambda r: r.timestamp)
        return self._filtered_records

    def _build_logger(self):
        logger = logging.getLogger("timelapse_generator_gui")
        logger.handlers.clear()
        handler = _LogHandler(self.log)
        handler.setLevel(logging.DEBUG if self.verbose_var.get() else logging.INFO)
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG if self.verbose_var.get() else logging.INFO)
        logger.propagate = False
        return logger

    # ------------------------------------------------------------------ #
    # Preview / generate
    # ------------------------------------------------------------------ #
    def preview_threaded(self):
        threading.Thread(target=self._preview_safe, daemon=True).start()

    def _preview_safe(self):
        try:
            records = self._parse_and_filter(logger=self._build_logger())
            count = len(records)
            self.log(f"Preview: {count} image(s) match the current filters.")
            self.root.after(0, lambda c=count: messagebox.showinfo(
                "Preview", f"{c} image(s) match the current filters."))
        except Exception as e:
            self.root.after(0, lambda err=e: messagebox.showerror("Preview Error", str(err)))

    def generate_threaded(self):
        if not self.output_ent.get().strip():
            messagebox.showerror("Error", "Output file is required.")
            return
        self._set_busy(True)
        threading.Thread(target=self._generate_safe, daemon=True).start()

    def _generate_safe(self):
        try:
            logger = self._build_logger()
            records = self._parse_and_filter(logger=logger)
            if not records:
                raise ValueError("No images match the current filters.")

            output = self.output_ent.get().strip()
            params = self._video_params()
            self.log(f"Exporting {len(records)} frame(s) -> {output} "
                     f"[fps={params['fps']}, scale={params['scale']}, codec={params['codec']}, "
                     f"preset={params['preset']}, crf={params['crf']}]")

            generator = TimelapseGenerator()
            generator.export(records=records, output=output,
                             progress_callback=self._on_progress, **params)
            self.root.after(0, lambda: messagebox.showinfo(
                "Success", "Timelapse generated successfully!"))
        except Exception as e:
            self.root.after(0, lambda err=e: messagebox.showerror("Export Error", str(err)))
        finally:
            self.root.after(0, self._on_generate_done)

    def _video_params(self):
        try:
            fps = int(self.fps_spin.get())
            scale = float(self.scale_ent.get())
            crf = int(self.crf_spin.get())
        except ValueError:
            raise ValueError("FPS, scale and CRF must be numbers.")

        codec = self.codec_cmb.get()
        preset = self.preset_cmb.get()

        crop = None
        crop_vals = [self.crop_x_ent.get().strip(), self.crop_y_ent.get().strip(),
                     self.crop_w_ent.get().strip(), self.crop_h_ent.get().strip()]
        if any(crop_vals):
            if not all(crop_vals):
                raise ValueError("Crop requires x, y, width and height.")
            try:
                crop = tuple(int(v) for v in crop_vals)
            except ValueError:
                raise ValueError("Crop values must be integers.")

        return {"fps": fps, "scale": scale, "codec": codec, "preset": preset,
                "crf": crf, "crop": crop,
                "overlay_text": self.overlay_ent.get().strip() or None}

    # ------------------------------------------------------------------ #
    # Progress / status
    # ------------------------------------------------------------------ #
    def _on_progress(self, frame, total):
        pct = (frame / total * 100) if total else 0
        self.root.after(0, lambda: self._set_progress(pct, f"Rendering frame {frame}/{total}"))

    def _set_progress(self, pct, text):
        self.progress["value"] = pct
        self.status_lbl.config(text=text)

    def _on_generate_done(self):
        self._set_busy(False)
        self.progress["value"] = 0
        self.status_lbl.config(text="Ready")

    def _set_busy(self, busy):
        state = "disabled" if busy else "normal"
        for widget in (self.generate_btn, self.preview_btn):
            widget.config(state=state)

    # ------------------------------------------------------------------ #
    # Logging
    # ------------------------------------------------------------------ #
    def log(self, message):
        def _append():
            self.log_text.config(state="normal")
            self.log_text.insert(tk.END, f"{message}\n")
            self.log_text.see(tk.END)
            self.log_text.config(state="disabled")
        self.root.after(0, _append)


if __name__ == "__main__":
    root = tk.Tk()
    app = TimelapseGuiApp(root)
    root.mainloop()
