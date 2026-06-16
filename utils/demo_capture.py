import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import requests
from camera.camera_handler import CameraHandler
import yaml

__CONFIG__ = "./config.yaml"
with open(__CONFIG__, 'r') as f:
    __CONFIG__ = yaml.safe_load(f)


class CameraGuiApp:

    def __init__(self, root):
        self.root = root
        self.root.title("Camera & Light Control Panel")
        self.root.geometry("480x550")
        self.root.resizable(False, False)

        # Main Layout Padding
        main_frame = ttk.Frame(root, padding="15")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # --- 1. Network Settings Group ---
        net_frame = ttk.LabelFrame(main_frame, text=" Network Configuration ", padding="10")
        net_frame.pack(fill=tk.X, pady=5)

        ttk.Label(net_frame, text="Camera IP:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.cam_ip_ent = ttk.Entry(net_frame)
        self.cam_ip_ent.insert(0, "192.168.1.11")
        self.cam_ip_ent.grid(row=0, column=1, pady=2)

        ttk.Label(net_frame, text="Microcontroller IP:").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.mc_ip_ent = ttk.Entry(net_frame)
        self.mc_ip_ent.insert(0, "192.168.1.30")
        self.mc_ip_ent.grid(row=1, column=1, pady=2)

        # --- 2. Session & Storage Group ---
        io_frame = ttk.LabelFrame(main_frame, text=" Session & Storage ", padding="10")
        io_frame.pack(fill=tk.X, pady=5)

        ttk.Label(io_frame, text="Session Name:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.session_ent = ttk.Entry(io_frame)
        self.session_ent.insert(0, "test_session")
        self.session_ent.grid(row=0, column=1, columnspan=2, pady=2)

        ttk.Label(io_frame, text="Output Folder:").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.folder_ent = ttk.Entry(io_frame)
        self.folder_ent.insert(0, "./output/")
        self.folder_ent.grid(row=1, column=1, pady=2)
        
        browse_btn = ttk.Button(io_frame, text="Browse...", command=self.browse_folder, width=10)
        browse_btn.grid(row=1, column=2, padx=(5, 0), pady=2)

        # --- 3. Light Control Group ---
        light_frame = ttk.LabelFrame(main_frame, text=" LED Strengths (0 - 255) ", padding="10")
        light_frame.pack(fill=tk.X, pady=5)

        ttk.Label(light_frame, text="LED 1:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.led1_ent = ttk.Entry(light_frame, width=10)
        self.led1_ent.insert(0, "100")
        self.led1_ent.grid(row=0, column=1, sticky=tk.W, pady=2, padx=5)

        ttk.Label(light_frame, text="LED 2:").grid(row=0, column=2, sticky=tk.W, pady=2, padx=(15, 0))
        self.led2_ent = ttk.Entry(light_frame, width=10)
        self.led2_ent.insert(0, "100")
        self.led2_ent.grid(row=0, column=3, sticky=tk.W, pady=2, padx=5)

        ttk.Label(light_frame, text="LED 3:").grid(row=0, column=4, sticky=tk.W, pady=2, padx=(15, 0))
        self.led3_ent = ttk.Entry(light_frame, width=10)
        self.led3_ent.insert(0, "100")
        self.led3_ent.grid(row=0, column=5, sticky=tk.W, pady=2, padx=5)

        # --- 4. Action Trigger Button ---
        self.capture_btn = ttk.Button(main_frame, text="CAPTURE IMAGE", command=self.execute_capture)
        self.capture_btn.pack(fill=tk.X, pady=15, ipady=5)

        # --- 5. Status / Log Output ---
        log_frame = ttk.LabelFrame(main_frame, text=" System Logs ", padding="5")
        log_frame.pack(fill=tk.BOTH, expand=True)
        
        self.log_text = tk.Text(log_frame, height=8, state='disabled', wrap='word', background="#f0f0f0")
        self.log_text.pack(fill=tk.BOTH, expand=True)

    def log(self, message):
        """Helper to append messages to the internal GUI log console."""
        self.log_text.config(state='normal')
        self.log_text.insert(tk.END, f"{message}\n")
        self.log_text.see(tk.END)
        self.log_text.config(state='disabled')

    def browse_folder(self):
        """Opens a native directory chooser dialog."""
        selected_dir = filedialog.askdirectory()
        if selected_dir:
            self.folder_ent.delete(0, tk.END)
            self.folder_ent.insert(0, selected_dir)

    def execute_capture(self):
        """Extracts settings from UI fields dynamically and runs the process."""
        # 1. Fetch Dynamic UI Values
        cam_ip = self.cam_ip_ent.get().strip()
        mc_ip = self.mc_ip_ent.get().strip()
        session_name = self.session_ent.get().strip()
        output_folder = self.folder_ent.get().strip()
        
        led1 = self.led1_ent.get().strip() or None
        led2 = self.led2_ent.get().strip() or None
        led3 = self.led3_ent.get().strip() or None

        #Temporarily disable capture button
        self.capture_btn.config(state='disabled')

        # Basic input validation
        if not cam_ip or not mc_ip or not session_name or not output_folder:
            messagebox.showerror("Error", "All IP, Session, and Folder fields must be filled!")
            return

        self.log(f"--- Starting Capture Sequence ({session_name}) ---")
    

        # 3. Instantiate Camera Handler with current UI configuration
        try:
            self.log(f"Connecting to camera at {cam_ip}...")
            cam_handler = CameraHandler(name="cam1", ip=cam_ip, output_folder=output_folder)
            cam_handler.camera.Open()

            self.log("Loading config")

            cam_handler.load_config(__CONFIG__["camera_configs"]["default"])

            self.log("Clearing buffer")
            for i in range(6):
                _ = cam_handler.capture_image()

            # 2. Trigger Microcontroller (Lights)
            leds = [("led1", led1), ("led2", led2), ("led3", led3)]
            for name, strength in leds:
                if strength is not None:
                    url = f"http://{mc_ip}/{name}/{strength}"
                    try:
                        self.log(f"Sending request: {url}")
                        # Added a timeout so the GUI doesn't permanently freeze if the MC is offline
                        response = requests.get(url, timeout=3)
                        self.log(f"MC Response: {response.status_code}")
                    except requests.exceptions.RequestException as e:
                        self.log(f"Warning: Failed to reach Microcontroller for {name}: {e}")

            self.log("Capturing image...")
            im = cam_handler.capture_image()
            
            # Formatting the saved filename safely
            light_config_string = f"{led1 or 0}_{led2 or 0}_{led3 or 0}.jpg"
            
            self.log(f"Saving image to {output_folder}...")
            cam_handler.save_image(
                img=im, 
                cam_config_name=session_name, 
                light_config_name=light_config_string,
            )
            
            self.log("Success: Capture Complete!")
            messagebox.showinfo("Success", "Image captured and saved successfully.")
            cam_handler.camera.Close()
            
        except Exception as e:
            self.log(f"Error: Camera operation failed: {e}")
            messagebox.showerror("Camera Error", f"Failed during camera execution:\n{e}")
        finally:
            self.capture_btn.config(state='normal')

if __name__ == "__main__":
    root = tk.Tk()
    app = CameraGuiApp(root)
    root.mainloop()