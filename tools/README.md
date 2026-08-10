# Tools scripts
This folder contains small utilities for exporting camera metadata, building composite images, and generating timelapse videos from captured image data.

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