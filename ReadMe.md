# LOTUS-PTO: Basler ace 2 python controller
## Setup
### Python venv
1. ```python3 -m venv venv```
2. ```source venv/bin/activate```
3. ```pip install -r requirements.txt```

### Systemd timer and service schedule
We use systemd for service calling and scheduling of the capturing process. That way we can ensure that capture is run routinely when the system is up, and it is can retain persistency (i.e. trigger after reboot if time-window was during server downtime).
**lotus-capture.sh**: Bash script that specifies image acquisition arguments and sequence.
**lotus-capture.service**: systemd Service to register (calls lotus-capture.sh when triggered)
**lotus-capture.timer**: systemd Timer to trigger capture service with controlled intervals

#### Initial Setup
1. Copy service file into linux system
```
sudo mv ./systemd/lotus-capture.service  /etc/systemd/system/lotus-capture.service
```

2. Copy timer file into linux system
```
sudo mv ./systemd/lotus-capture.timer /etc/systemd/system/lotus-capture.timer
```

3. Update path to lotus-capture.sh
```
sudo nano /etc/systemd/system/lotus-capture.service
``` 

5. Reboot daemon 
```
sudo systemctl daemon-reload
```

5. Enable timer
```
sudo systemctl enable --now lotus-capture.timer
```

#### Debugging
Verify timer is enabled:
```
systemctl list-timers --all
```

Check lotus-capture log
```
journalctl -u lotus-capture.service
```

Manually trigger service right now
```
sudo systemctl start lotus-capture.service
```


## Configuration
### Default configurations
The config file ('config.yaml') contains the following keys:
**DEFAULT**: Nested dicts with default parameters for camera, lighting and sbc configurations. These are used as a baseline for any subsequent configuration so the defined parameters can be assumed to allways be present.
**setups**: Named configurations of the physical setups that retain the information and parameters needed to connect and control the physical setups (camera, sbc, lighting)
**camera_configs**: Nested dicts with named camera configurations that inherit the default configurations, these are used for 'capture.py' to specify capture conditions. (i.e. 'python3 capture.py setup1 -c named_camera_config1 named_lighting_config1')
**light_config**: Nested dicts with named lighting configurations that inherit the default configurations, these are used for 'capture.py' to specify capture conditions. (i.e. 'python3 capture.py setup1 -c named_camera_config1 named_lighting_config1')

### Configuration of light and cameras
By default the camera, lighting and sbc settings are outlined in the DEFAULT key of the config file, any specified config under the 'camera_configs' or 'light_configs' will inherit properties from DEFAULT so variation of any variable herein must be specified in subsequent configurations.

## Execution of code

### main.py
1. Headless Control (CLI Only)
Use this for simple command-line interaction with the camera

```python3 -m Camera.camera_control```

2. Full Dashboard
Launches the full interactive terminal interface with live logs

```python3 main.py```

3. Automated Snapper Mode
To start the script with the auto-snapping background task enabled, use the -a or --auto flag (defaulted to 60 sec intervals)

```python3 main.py -a 60```

### capture.py
1. Single image capture
Capture an image from a specific setup with named lighting and capture configurations
```python3 capture.py rig1 -c low_light dim```

2. Image sequence capture
Capture a series of images with a series of named lighting and capture configurations
```python3 capture.py rig1 -c low_light dim -c low_light bright -c high_light dim```
