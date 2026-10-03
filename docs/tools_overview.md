# Tools scripts
`tools/` contains composites, timelapses, crop selection, and camera-node dump scripts. Full usage is documented in [`docs/tools_overview.md`](docs/tools_overview.md):
- `make_composits.py` — mean/median/percentile composite images.
- `timelapse_generator.py` + `timelapse_generator_gui.py` — filtered timelapse videos.
- `basler_export_nodes.py` — export GenICam nodes to XML/YAML/Markdown.
- `get_crop_coordinates.py` — interactive crop-region selector to retrieve coordinates for crops and camera_configs
- `generate_crops.sh` — batch timelapse generation for predefined crops.
- `sync_push.sh` — sync captured image sets to another machine.

## basler_export_nodes.py
This script connects to the first available Basler camera and exports the camera's GenICam nodes to XML, YAML, or Markdown. It is mainly used to inspect and document camera parameters and feature settings.
Using markdown makes it way more humanly readable, however YAML and XML flavors are superior for parsing.

### Arguments:
#### Optional
- `--format/-f` selects the exported file format as `xml`, `yaml`, or `markdown`.
- `--capture-only/-c` limits the export to image-capture related settings rather than all camera nodes.
- `--output/-o` writes the result to a specific file path instead of the default output name.
- `--debug-tree/-d` prints the raw GenICam category tree for troubleshooting.
- `--list-categories/-l` lists the camera category names so it is easier to understand what the camera exposes.

### Examples:
Write all available GeniCam nodes to an XML file in the current directory
```bash
python tools/basler_export_nodes.py

```

Write only image capture related Genicam nodes to an XML file
```bash
python tools/basler_export_nodes.py --capture-only  
```

Output the file in a specific format (XML, YAML, Markdown)
```bash
    python tools/basler_export_nodes.py --format xml
    python tools/basler_export_nodes.py --format yaml
    python tools/basler_export_nodes.py --format markdown
```

## generate_crops.sh
This shell script loops through a predefined set of crop regions and calls the timelapse generator once for each crop so that a separate output video can be produced for each area of interest. It uses the 'timelapse_generator.py' tool to generate the different crops.

Arguments:
- This script does not take command-line arguments. Instead, you configure the values at the top of the file before running it.
- `DATA_DIR` is the folder containing the source image data.
- `OUT_DIR` is where the generated videos will be written.
- `START` and `END` define the date range to process.
- `RIG` is the setup name or rig identifier to match in the data.
- `CAMERA` and `LIGHTING` select the camera and lighting configuration labels to use.
- `FPS` sets the output frame rate for each generated timelapse video.
- `CROPS` is the list of crop regions, each one with x/y/width/height values and a label for the output file.

## make_composits.py
This script builds composite images from sets of timestamped images by grouping them into time bins and combining each group with a selected method such as mean, median, or percentile.

### Arguments:
#### Positional
- `input` is the folder containing the image data
- `output` is the output directory for the composites
- `start` is the starting date of the daterange
- `end` is the end date of the daterange (inclusive)
#### Optional
Filtering
- `--filter_options` prints the available camera and lighting options instead of creating composites.
- `--rig` filters the input to a specific setup or rig name.
- `--camera` filter by camera configuration names.
- `--lighting` filter by lighting configuration names.
- `--time_period` limits the images to a specific time window each day.
Binning 
- `--bin_freq` control the time interval between each bin
- `--bin_width` control how wide each time bin is.
Composition method
- `--method` chooses how each bin is combined, such as `mean`, `median`, or `percentile`.
- `-a/--method_args` passes extra options to the selected composite method.
- `-v/--verbose` enables more detailed logging.

Examples:

Create a composit of all images captured at each capture session between June 1st and August 1st with differnt filtering techniques
```bash
#Pixelwise median
python tools/make_composits.py ~/lotus-data/ ~/composite-median/ 2026-07-01 2026-08-01 --method median
#Pixelwise mean
python tools/make_composits.py ~/lotus-data/ ~/composite-mean/ 2026-07-01 2026-08-01 --method mean
#30th percentile pixelvalue of a pixelwise sorted list
python tools/make_composits.py ~/lotus-data/ ~/composite-percentile/ 2026-07-01 2026-08-01 --method percentile
```

Overide default filtering parameters (40th percentile instead of the default 30)
```bash
python tools/make_composits.py ~/lotus-data/ ~/composite-percentile/ 2026-07-01 2026-08-01 --method percentile -a percentile=40
```

Specify that the median composites should only contain images between 00:00 and 02:00
```bash
python tools/make_composits.py ~/lotus-data/ ~/composite-median/ 2026-07-01 2026-08-01 --time_period 00:00 02:00
```

Only include images of a specific lighting condition
```bash
python tools/make_composits.py ~/lotus-data/ ~/composite-median/ 2026-07-01 2026-08-01 --lighting demoAll

```
Or camera configuration
```bash
python tools/make_composits.py ~/lotus-data/ ~/composite-median/ 2026-07-01 2026-08-01 --camera 20pAutoExp
```

Filters can be stacked as many times as desired and act as an excluding filter, i.e. samples that match any of the elements of each filter type (e.g. any of the passed --camera arguments)
```bash
python tools/make_composits.py ~/lotus-data/ ~/composite-median/ 2026-07-01 2026-08-01 --camera 20pAutoExp --camera default
```

Make a composit of all images for each day:
```bash
python tools/make_composits.py ~/lotus-data/ ~/composite-median/ 2026-07-01 2026-08-01 --bin_freq 1440 --bin_width 1440
```

## timelapse_generator.py
This script exports filtered image sequences to a video file, with options for scaling, cropping, overlays, subtitle timestamps, and ffmpeg encoding presets.

### Arguments:
#### Positional
- `input` is the folder containing the source images
- `output` is the output video file
- `start` is the starting date of the daterange
- `end` is the end date of the daterange (inclusive)
#### Optional
Filtering
- `--rig` filters the images to a specific setup or rig name.
- `--camera` filter the imaages by camera configuration names.
- `--lighting` filter the images by lighting configuration names.
- `--time_period` limits the input to selected hours of each day.
Rendering
- `--fps` sets the playback speed of the generated timelapse.
- `--codec`, `--preset`, and `--crf` control the ffmpeg encoding method and compression quality.
On screen overlay
- `--overlay` adds a text label to the video, such as a crop name or experiment label.
Image
- `--scale` resizes the video up or down by a multiplier.
- `--crop` trims the output to a specific rectangle using `x`, `y`, `width`, and `height` values.
Verbosity
- `-v/--verbose` enables more detailed output while running.

### Examples:
Generate a timelapse of all images between June 1st and August 1st
```bash
python timelapse_generator.py ~/lotus-data/ ~/20260701_20260801.mp4 2026-07-01 2026-08-01 
```

Generate a timelapse of only a specific camera configuration
```bash
python timelapse_generator.py ~/lotus-data/ ~/20260701_20260801.mp4 2026-07-01 2026-08-01 --camera 20pAutoExp
```
or lighting configuration

```bash
python timelapse_generator.py ~/lotus-data/ ~/20260701_20260801.mp4 2026-07-01 2026-08-01 --lighting lightsOff
```


Filters can be stacked as many times as desired and act as an excluding filter, i.e. samples that match any of the elements of each filter type (e.g. any of the passed --lighting arguments)
```bash
python timelapse_generator.py ~/lotus-data/ ~/20260701_20260801.mp4 2026-07-01 2026-08-01 --lighting lightsOff --lighting demoAll
```

Custom text can be overlayed in the top right (Usefull for detailing a specific composite or sequence by name )
```bash
python timelapse_generator.py ~/lotus-data/ ~/20260701_20260801.mp4 2026-07-01 2026-08-01 --overlay "The best video is this one"
```

The resolution can also be downscaled by a scalar to reduce file size
```bash
python timelapse_generator.py ~/lotus-data/ ~/20260701_20260801.mp4 2026-07-01 2026-08-01 --scale 0.5
```

Or cropped to only be off a specific region (using top left x,y, width height boundingbox coordinates)
```bash
python timelapse_generator.py ~/lotus-data/ ~/20260701_20260801.mp4 2026-07-01 2026-08-01 --crop 100 500 1200 1400
```

## timelapse_generator_gui.py
A Tkinter front end for `timelapse_generator.py`. It parses the input folder with `utils/parsing.py`, lets you filter by rig, camera configs, lighting configs, date range, and daily time windows, then renders the video from a background thread. The filter lists fill in after a Scan Options pass over the input folder.

The panel has these sections:
- Input & Output: source image folder and output video file.
- Date Range: start and end dates in `YYYY-MM-DD`.
- Filters: rig, plus multi-select camera and lighting config lists.
- Time Periods: one or more daily `HH:MM` windows.
- Video Options: FPS, scale, codec (`libx264`, `libx265`, `mpeg4`), preset, CRF, crop box, and verbose logging.
- Overlay: text drawn onto the video.
- Settings: export and import the whole form as JSON.

Preview Match Count reports how many images match without rendering. GENERATE TIMELAPSE renders the video and reports progress.

### Running
```bash
python3 tools/timelapse_generator_gui.py
```

## get_crop_coordinates.py
It opens the selected image and lets the user click on the image to choose the top-left coordinate of a crop box. It also optionally highlights an inner ROI box and prints a ready-to-paste configuration block for use in config files or scripts.

### Arguments:
#### Positional
- `image_path` is the path to the source image to inspect.
- `box_width` is the full crop width in pixels.
- `box_height` is the full crop height in pixels.
#### Optional
- `--roi_width` optionally define an inner ROI region
- `--roi_height` optionally define an inner ROI region

### Examples:
Select a full crop region from an image without an ROI
```bash
python tools/get_crop_coordinates.py image.png 850 850
```

Select a crop box and also show a nested ROI region centered inside it
```bash
python tools/get_crop_coordinates.py image.png 850 850 400 400
```

Typical output after clicking a location in the image:
```text
sample_01:
    <<: *sample_crop_settings
    OffsetX: 1270
    OffsetY: 940
    AutoOffsetX: 1445
    AutoOffsetY: 1115
```

This yaml format can be directly pasted in the camera config settings of the Config.yaml

## sync_push.sh
Copies a local image tree to another machine over SSH. It is written for one specific setup, and its own header warns that it is not general purpose, so edit the values at the top (`GATEWAY`, `MACHINE_B`) before using it.

By default it does an inventory diff: it lists files on the remote and locally, diffs the two, and sends only the missing ones with `rsync --files-from`. `--full-scan` falls back to a plain recursive `rsync`. `--dry-run` prints what would transfer without copying. SSH is authenticated once through a ControlMaster with a ProxyJump through `GATEWAY`, so an MFA prompt only appears once.

### Arguments:
#### Positional
- `<local_path>` is the source directory, which must exist.
- `<destination_path>` is the absolute destination path on the remote machine.
#### Optional
- `--full-scan` runs a plain `rsync` full scan instead of the inventory diff.
- `--dry-run` shows what would be transferred without copying.
- `-h/--help` prints usage.

Requires `ssh`, `rsync`, `find`, `sort`, and `comm` on the host.

### Examples:
Copy only the files missing on the remote machine
```bash
./tools/sync_push.sh /home/user/lotus-data /home/user/lotus-data
```

Preview the transfer
```bash
./tools/sync_push.sh /home/user/lotus-data /home/user/lotus-data --dry-run
```

Force a plain full scan
```bash
./tools/sync_push.sh /home/user/lotus-data /home/user/lotus-data --full-scan
```