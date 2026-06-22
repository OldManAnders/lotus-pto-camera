"""
Demo GUI for the LOTUS-PTO capture rig.

This panel is a thin wrapper around `CaptureController` (see main.py): it builds a
*sequence* of capture steps (camera config + light setting) and then runs them all
through the same rig setup/teardown path used by the CLI script. Light settings for
each step can either be a named config pulled from config.yaml's `light_configs`, or
typed in manually (LED1/LED2/LED3), mirroring the original simple GUI.
"""
import os
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import yaml

from main import CaptureController


class CameraGuiApp:

    def __init__(self, root):
        self.root = root
        self.root.title("Camera & Light Control Panel")
        self.root.geometry("560x980")
        self.root.resizable(False, False)

        self.config_path = "./config.yaml"
        self.config = {}
        self.sequence = []  # list of dicts, see _add_step()
        self.cc = None      # active CaptureController, set while a run is in progress

        main_frame = ttk.Frame(root, padding="15")
        main_frame.pack(fill=tk.BOTH, expand=True)

        self._build_config_section(main_frame)
        self._build_rig_section(main_frame)
        self._build_io_section(main_frame)
        self._build_step_builder_section(main_frame)
        self._build_sequence_list_section(main_frame)
        self._build_run_section(main_frame)
        self._build_log_section(main_frame)

        self.load_config(self.config_path)

    # ------------------------------------------------------------------ #
    # Section builders
    # ------------------------------------------------------------------ #
    def _build_config_section(self, parent):
        frame = ttk.LabelFrame(parent, text=" Config File ", padding="10")
        frame.pack(fill=tk.X, pady=5)

        self.config_path_ent = ttk.Entry(frame)
        self.config_path_ent.insert(0, self.config_path)
        self.config_path_ent.grid(row=0, column=0, sticky=tk.EW, pady=2)
        frame.columnconfigure(0, weight=1)

        ttk.Button(frame, text="Browse...", command=self.browse_config, width=10).grid(
            row=0, column=1, padx=(5, 0))
        ttk.Button(frame, text="Reload", command=self.reload_config, width=10).grid(
            row=0, column=2, padx=(5, 0))

    def _build_rig_section(self, parent):
        frame = ttk.LabelFrame(parent, text=" Rig Selection ", padding="10")
        frame.pack(fill=tk.X, pady=5)

        ttk.Label(frame, text="Rig:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.rig_cmb = ttk.Combobox(frame, state="readonly")
        self.rig_cmb.grid(row=0, column=1, sticky=tk.EW, pady=2, padx=5)
        frame.columnconfigure(1, weight=1)

        self.enable_camera_var = tk.BooleanVar(value=True)
        self.enable_mc_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(frame, text="Enable Camera", variable=self.enable_camera_var).grid(
            row=1, column=0, sticky=tk.W, pady=2)
        ttk.Checkbutton(frame, text="Enable Microcontroller", variable=self.enable_mc_var).grid(
            row=1, column=1, sticky=tk.W, pady=2)

    def _build_io_section(self, parent):
        frame = ttk.LabelFrame(parent, text=" Session & Storage ", padding="10")
        frame.pack(fill=tk.X, pady=5)

        ttk.Label(frame, text="Session Name:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.session_ent = ttk.Entry(frame)
        self.session_ent.insert(0, "test_session")
        self.session_ent.grid(row=0, column=1, columnspan=2, sticky=tk.EW, pady=2)
        frame.columnconfigure(1, weight=1)

        ttk.Label(frame, text="Output Folder:").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.folder_ent = ttk.Entry(frame)
        self.folder_ent.insert(0, "./output/")
        self.folder_ent.grid(row=1, column=1, sticky=tk.EW, pady=2)

        ttk.Button(frame, text="Browse...", command=self.browse_folder, width=10).grid(
            row=1, column=2, padx=(5, 0), pady=2)

    def _build_step_builder_section(self, parent):
        frame = ttk.LabelFrame(parent, text=" Add Capture Step ", padding="10")
        frame.pack(fill=tk.X, pady=5)

        ttk.Label(frame, text="Camera Config:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.cam_cfg_cmb = ttk.Combobox(frame, state="readonly")
        self.cam_cfg_cmb.grid(row=0, column=1, columnspan=3, sticky=tk.EW, pady=2, padx=5)
        frame.columnconfigure(1, weight=1)

        # Light source mode: named config vs manual LED values
        self.light_mode_var = tk.StringVar(value="named")
        ttk.Radiobutton(frame, text="Named Light Config", variable=self.light_mode_var,
                         value="named", command=self._on_light_mode_change).grid(
            row=1, column=0, columnspan=2, sticky=tk.W, pady=(8, 2))
        ttk.Radiobutton(frame, text="Manual LED Values", variable=self.light_mode_var,
                         value="manual", command=self._on_light_mode_change).grid(
            row=1, column=2, columnspan=2, sticky=tk.W, pady=(8, 2))

        # Named-config row
        self.light_cfg_lbl = ttk.Label(frame, text="Light Config:")
        self.light_cfg_lbl.grid(row=2, column=0, sticky=tk.W, pady=2)
        self.light_cfg_cmb = ttk.Combobox(frame, state="readonly")
        self.light_cfg_cmb.grid(row=2, column=1, columnspan=3, sticky=tk.EW, pady=2, padx=5)

        # Manual-LED row (built but only gridded when selected)
        self.led_lbl = ttk.Label(frame, text="LED 1 / 2 / 3:")
        self.led1_ent = ttk.Entry(frame, width=8)
        self.led1_ent.insert(0, "100")
        self.led2_ent = ttk.Entry(frame, width=8)
        self.led2_ent.insert(0, "100")
        self.led3_ent = ttk.Entry(frame, width=8)
        self.led3_ent.insert(0, "100")

        ttk.Button(frame, text="+ Add Step to Sequence", command=self.add_step).grid(
            row=3, column=0, columnspan=4, sticky=tk.EW, pady=(10, 0))

        self._on_light_mode_change()

    def _build_sequence_list_section(self, parent):
        frame = ttk.LabelFrame(parent, text=" Capture Sequence ", padding="10")
        frame.pack(fill=tk.BOTH, pady=5)

        self.sequence_list = tk.Listbox(frame, height=6)
        self.sequence_list.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)

        btn_col = ttk.Frame(frame)
        btn_col.pack(side=tk.LEFT, fill=tk.Y, padx=(5, 0))
        ttk.Button(btn_col, text="Remove Selected", command=self.remove_step).pack(
            fill=tk.X, pady=2)
        ttk.Button(btn_col, text="Clear All", command=self.clear_sequence).pack(
            fill=tk.X, pady=2)
        ttk.Button(btn_col, text="Move Up", command=lambda: self.move_step(-1)).pack(
            fill=tk.X, pady=2)
        ttk.Button(btn_col, text="Move Down", command=lambda: self.move_step(1)).pack(
            fill=tk.X, pady=2)

    def _build_run_section(self, parent):
        self.run_btn = ttk.Button(parent, text="RUN SEQUENCE", command=self.run_sequence_threaded)
        self.run_btn.pack(fill=tk.X, pady=15, ipady=5)

    def _build_log_section(self, parent):
        frame = ttk.LabelFrame(parent, text=" System Logs ", padding="5")
        frame.pack(fill=tk.BOTH, expand=True)

        self.log_text = tk.Text(frame, height=10, state='disabled', wrap='word',
                                 background="#f0f0f0")
        self.log_text.pack(fill=tk.BOTH, expand=True)

    # ------------------------------------------------------------------ #
    # Config loading
    # ------------------------------------------------------------------ #
    def browse_config(self):
        path = filedialog.askopenfilename(
            title="Select config.yaml",
            filetypes=[("YAML files", "*.yaml *.yml"), ("All files", "*.*")])
        if path:
            self.config_path_ent.delete(0, tk.END)
            self.config_path_ent.insert(0, path)
            self.reload_config()

    def reload_config(self):
        self.load_config(self.config_path_ent.get().strip())

    def load_config(self, path):
        try:
            with open(path, 'r') as f:
                self.config = yaml.safe_load(f) or {}
            self.config_path = path
            self.log(f"Loaded config: {path}")
        except Exception as e:
            self.config = {}
            self.log(f"Error: Failed to load config '{path}': {e}")
            messagebox.showerror("Config Error", f"Failed to load config:\n{e}")
            return

        rigs = sorted(self.config.get("setups", {}).keys())
        cam_cfgs = sorted(self.config.get("camera_configs", {}).keys())
        light_cfgs = sorted(self.config.get("light_configs", {}).keys())

        self.rig_cmb["values"] = rigs
        if rigs:
            self.rig_cmb.current(0)

        self.cam_cfg_cmb["values"] = cam_cfgs
        if cam_cfgs:
            self.cam_cfg_cmb.current(0)

        self.light_cfg_cmb["values"] = light_cfgs
        if light_cfgs:
            self.light_cfg_cmb.current(0)

        if not rigs:
            self.log("Warning: No 'setups' found in config.")
        if not cam_cfgs:
            self.log("Warning: No 'camera_configs' found in config.")
        if not light_cfgs:
            self.log("Warning: No 'light_configs' found in config.")

    # ------------------------------------------------------------------ #
    # Sequence builder
    # ------------------------------------------------------------------ #
    def _on_light_mode_change(self):
        if self.light_mode_var.get() == "named":
            self.led_lbl.grid_forget()
            self.led1_ent.grid_forget()
            self.led2_ent.grid_forget()
            self.led3_ent.grid_forget()
            self.light_cfg_lbl.grid(row=2, column=0, sticky=tk.W, pady=2)
            self.light_cfg_cmb.grid(row=2, column=1, columnspan=3, sticky=tk.EW, pady=2, padx=5)
        else:
            self.light_cfg_lbl.grid_forget()
            self.light_cfg_cmb.grid_forget()
            self.led_lbl.grid(row=2, column=0, sticky=tk.W, pady=2)
            self.led1_ent.grid(row=2, column=1, sticky=tk.W, pady=2, padx=5)
            self.led2_ent.grid(row=2, column=2, sticky=tk.W, pady=2, padx=5)
            self.led3_ent.grid(row=2, column=3, sticky=tk.W, pady=2, padx=5)

    def add_step(self):
        cam_config = self.cam_cfg_cmb.get()
        if not cam_config:
            messagebox.showerror("Error", "Select a camera config first.")
            return

        if self.light_mode_var.get() == "named":
            light_config = self.light_cfg_cmb.get()
            if not light_config:
                messagebox.showerror("Error", "Select a light config first.")
                return
            step = {"cam_config": cam_config, "light_type": "named", "light_config": light_config}
            label = f"cam={cam_config} | light='{light_config}'"
        else:
            try:
                leds = (int(self.led1_ent.get()), int(self.led2_ent.get()), int(self.led3_ent.get()))
            except ValueError:
                messagebox.showerror("Error", "LED values must be integers.")
                return
            step = {"cam_config": cam_config, "light_type": "manual", "leds": leds}
            label = f"cam={cam_config} | leds={leds}"

        self.sequence.append(step)
        self.sequence_list.insert(tk.END, f"[{len(self.sequence)}] {label}")

    def remove_step(self):
        sel = self.sequence_list.curselection()
        if not sel:
            return
        idx = sel[0]
        del self.sequence[idx]
        self._refresh_sequence_list()

    def clear_sequence(self):
        self.sequence = []
        self._refresh_sequence_list()

    def move_step(self, direction):
        sel = self.sequence_list.curselection()
        if not sel:
            return
        idx = sel[0]
        new_idx = idx + direction
        if 0 <= new_idx < len(self.sequence):
            self.sequence[idx], self.sequence[new_idx] = self.sequence[new_idx], self.sequence[idx]
            self._refresh_sequence_list()
            self.sequence_list.selection_set(new_idx)

    def _refresh_sequence_list(self):
        self.sequence_list.delete(0, tk.END)
        for i, step in enumerate(self.sequence, start=1):
            if step["light_type"] == "named":
                label = f"cam={step['cam_config']} | light='{step['light_config']}'"
            else:
                label = f"cam={step['cam_config']} | leds={step['leds']}"
            self.sequence_list.insert(tk.END, f"[{i}] {label}")

    # ------------------------------------------------------------------ #
    # Misc helpers
    # ------------------------------------------------------------------ #
    def log(self, message):
        self.log_text.config(state='normal')
        self.log_text.insert(tk.END, f"{message}\n")
        self.log_text.see(tk.END)
        self.log_text.config(state='disabled')

    def browse_folder(self):
        selected_dir = filedialog.askdirectory()
        if selected_dir:
            self.folder_ent.delete(0, tk.END)
            self.folder_ent.insert(0, selected_dir)

    # ------------------------------------------------------------------ #
    # Capture execution
    # ------------------------------------------------------------------ #
    def run_sequence_threaded(self):
        """Runs the capture sequence on a background thread so the GUI stays responsive."""
        if not self.sequence:
            messagebox.showerror("Error", "Add at least one step to the sequence first.")
            return

        self.run_btn.config(state='disabled')
        thread = threading.Thread(target=self._run_sequence_safe, daemon=True)
        thread.start()

    def _run_sequence_safe(self):
        try:
            self.run_sequence()
        finally:
            self.root.after(0, lambda: self.run_btn.config(state='normal'))

    def run_sequence(self):
        rig = self.rig_cmb.get()
        session_name = self.session_ent.get().strip()
        output_folder = self.folder_ent.get().strip()

        if not rig:
            self.root.after(0, lambda: messagebox.showerror("Error", "Select a rig first."))
            return
        if not session_name or not output_folder:
            self.root.after(0, lambda: messagebox.showerror(
                "Error", "Session Name and Output Folder must be filled!"))
            return

        os.makedirs(output_folder, exist_ok=True)
        self.log(f"--- Starting Capture Sequence ({session_name}) on rig '{rig}' ---")

        self.cc = None
        try:
            self.cc = CaptureController(
                rig=rig,
                config=self.config,
                enable_camera=self.enable_camera_var.get(),
                enable_microcontroller=self.enable_mc_var.get(),
                output_path=output_folder,
                log_level="debug",
            )

            self.log("Starting rig (powering camera, connecting handlers)...")
            self.cc.start_rig()

            self.log("Preparing for capture (wipe + buffer flush)...")
            self.cc.prepare_for_capture()

            for i, step in enumerate(self.sequence, start=1):
                cam_config_name = step["cam_config"]
                self.log(f"--- Step {i}/{len(self.sequence)}: cam='{cam_config_name}' ---")

                if self.cc.microcontroller_handler:
                    if step["light_type"] == "named":
                        light_config_name = step["light_config"]
                        led_kwargs = self.cc.get_subconfig("lights")[light_config_name]
                        self.log(f"Setting LEDs from named config '{light_config_name}': {led_kwargs}")
                        self.cc.microcontroller_handler.set_leds(**led_kwargs)
                    else:
                        leds = step["leds"]
                        light_config_name = f"manual_{leds[0]}_{leds[1]}_{leds[2]}"
                        self.log(f"Setting LEDs manually: {leds}")
                        self.cc.microcontroller_handler.set_leds(*leds)
                else:
                    light_config_name = (step["light_config"] if step["light_type"] == "named"
                                          else f"manual_{step['leds'][0]}_{step['leds'][1]}_{step['leds'][2]}")
                    self.log("Microcontroller disabled - skipping LED set.")

                if self.cc.camera_handler:
                    self.log(f"Loading camera config '{cam_config_name}'...")
                    self.cc.camera_handler.load_config(self.cc.get_subconfig("camera")[cam_config_name])

                    self.log("Capturing image...")
                    img = self.cc.camera_handler.capture_image(
                        cam_config_name=cam_config_name, light_config_name=light_config_name)

                    print(img.shape)
                    self.log(f"Saving image to {output_folder}...")
                    self.cc.camera_handler.save_image(
                        img, cam_config_name=f"{session_name}_{cam_config_name}",
                        light_config_name=light_config_name)
                else:
                    self.log("Camera disabled - skipping capture.")

            if self.cc.microcontroller_handler:
                self.log("Turning lights off...")
                self.cc.microcontroller_handler.set_leds(0, 0, 0)

            if self.cc.camera_handler:
                self.cc.camera_handler.close()

            self.log("Success: Capture sequence complete!")
            self.root.after(0, lambda: messagebox.showinfo(
                "Success", f"Captured {len(self.sequence)} image(s) successfully."))

        except Exception as e:
            self.log(f"Error: Capture sequence failed: {e}")
            self.root.after(0, lambda err=e: messagebox.showerror(
                "Capture Error", f"Failed during capture execution:\n{err}"))
        finally:
            if self.cc is not None:
                self.log("Powering off camera...")
                self.cc.power_off_camera()


if __name__ == "__main__":
    root = tk.Tk()
    app = CameraGuiApp(root)
    root.mainloop()
