#!/usr/bin/env bash
# ---- SHARED PARAMS (same for every tile) ----
DATA_DIR="/mnt/sdb1/lotus-data/"
OUT_DIR="$HOME"
START="2026-07-07"
END="2026-07-07"
RIG="rig1"
CAMERA="20pAutoExp"
LIGHTING="demoAll"
FPS=1
CROP_W=850
CROP_H=850
# ---- 4x4 GRID OF crop-x,crop-y PAIRS ---- Fill these in with your real 16 top-left corners. Order below is row-major: row0 (crop01-04), row1 (crop05-08), etc.
CROPS=(
 "129,29,850,850,A00"
 "968,40,850,850,B10"
 "1784,44,850,850,C20"
 "2658,17,850,850,D30"
 "148,968,850,850,B01"
 "980,972,850,850,C11"
 "1792,976,850,850,D21"
 "2624,926,850,850,E31"
 "133,1811,850,850,E02"
 "960,1773,850,850,A12"
 "1784,1769,850,850,B22"
 "2600,1761,850,850,C32"
 "117,2698,850,850,D03"
 "1792,2647,850,850,E23"
 "2639,2698,850,850,A33"
)

for entry in "${CROPS[@]}"; do
 IFS=',' read -r CROP_X CROP_Y CROP_W CROP_H LABEL <<< "$entry"
 OUT_FILE="${OUT_DIR}/${LABEL}_${START//-/}_${END//-/}_${CAMERA}_${LIGHTING}.mp4"
 echo "=== ${LABEL}: x=${CROP_X} y=${CROP_Y} w=${CROP_W} h=${CROP_H} -> ${OUT_FILE} ==="
 python utils/timelapse_generator.py "$DATA_DIR" "$OUT_FILE" "$START" "$END" --rig "$RIG" --fps "$FPS" --camera "$CAMERA" --lighting "$LIGHTING" --crop "$CROP_X" "$CROP_Y" "$CROP_W" "$CROP_H" --overlay "${LABEL} [${CAMERA}] [${LIGHTING}]" --preset veryfast
done
