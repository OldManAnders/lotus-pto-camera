# Basler Camera Feature Reference

| Property | Value |
|---|---|
| Model | `a2A3536-9gcBAS` |
| Serial Number | `*******` |
| Device Version | `109493-06` |
| Device Class | `BaslerGigE` |
| Total Parameters | 111 (88 read/write, 23 read-only) |

## Table of Contents

- [Acquisition Control](#acquisition-control) — 41 parameters
- [Analog Control](#analog-control) — 7 parameters
- [Auto Function Control](#auto-function-control) — 14 parameters
- [Image Format Control](#image-format-control) — 17 parameters
- [Image Processing Control](#image-processing-control) — 32 parameters

---

## Acquisition Control

### `AcquisitionMode`

**Acquisition Mode** &nbsp; ![Enum](https://img.shields.io/badge/type-Enum-purple) &nbsp; ![ReadWrite](https://img.shields.io/badge/access-ReadWrite-green)

Sets the image acquisition mode.

| Property | Value |
|---|---|
| Current value | `N/A` |
| Options | `Continuous` `SingleFrame` |

**pypylon API**

```python
# Get
value = camera.AcquisitionMode.Value

# Set (choose one option)
camera.AcquisitionMode.Value = "Continuous"
camera.AcquisitionMode.Value = "SingleFrame"
```

### `BslAcquisitionStopMode`

**Acquisition Stop Mode** &nbsp; ![Enum](https://img.shields.io/badge/type-Enum-purple) &nbsp; ![ReadWrite](https://img.shields.io/badge/access-ReadWrite-green)

Sets how Acquisition Stop commands end image acquisition.

| Property | Value |
|---|---|
| Current value | `N/A` |
| Options | `CompleteExposure` `AbortExposure` |

**pypylon API**

```python
# Get
value = camera.BslAcquisitionStopMode.Value

# Set (choose one option)
camera.BslAcquisitionStopMode.Value = "CompleteExposure"
camera.BslAcquisitionStopMode.Value = "AbortExposure"
```

### `AcquisitionStopMode`

**Acquisition Stop Mode** &nbsp; ![Enum](https://img.shields.io/badge/type-Enum-purple) &nbsp; ![ReadWrite](https://img.shields.io/badge/access-ReadWrite-green)

Sets how Acquisition Stop commands end image acquisition.

| Property | Value |
|---|---|
| Current value | `N/A` |
| Options | `Complete` `AbortExposure` |

**pypylon API**

```python
# Get
value = camera.AcquisitionStopMode.Value

# Set (choose one option)
camera.AcquisitionStopMode.Value = "Complete"
camera.AcquisitionStopMode.Value = "AbortExposure"
```

### `AcquisitionStart`

**Acquisition Start** &nbsp; ![Command](https://img.shields.io/badge/type-Command-red) &nbsp; ![ReadWrite](https://img.shields.io/badge/access-ReadWrite-green)

Starts the acquisition of images. If the camera is configured for single frame acquisition, it will start the acquisition of one frame. If the camera is configured for continuous frame acquisition, it will start the continuous acquisition of frames.

| Property | Value |
|---|---|
| Current value | `(executable command)` |

**pypylon API**

```python
camera.AcquisitionStart.Execute()
```

### `AcquisitionStop`

**Acquisition Stop** &nbsp; ![Command](https://img.shields.io/badge/type-Command-red) &nbsp; ![ReadWrite](https://img.shields.io/badge/access-ReadWrite-green)

Stops the acquisition of images if a continuous image acquisition is in progress.

| Property | Value |
|---|---|
| Current value | `(executable command)` |

**pypylon API**

```python
camera.AcquisitionStop.Execute()
```

### `AcquisitionAbort`

**Acquisition Abort** &nbsp; ![Command](https://img.shields.io/badge/type-Command-red) &nbsp; ![ReadWrite](https://img.shields.io/badge/access-ReadWrite-green)

Aborts the acquisition of images. If the camera is currently exposing a frame, the camera stops exposing immediately. The readout process, if already started, is aborted. The current frame will be incomplete. Afterwards, image acquisition is switched off.

| Property | Value |
|---|---|
| Current value | `(executable command)` |

**pypylon API**

```python
camera.AcquisitionAbort.Execute()
```

### `SensorShutterMode`

**Sensor Shutter Mode** &nbsp; ![Enum](https://img.shields.io/badge/type-Enum-purple) &nbsp; ![ReadWrite](https://img.shields.io/badge/access-ReadWrite-green)

Sets the shutter mode of the camera.

| Property | Value |
|---|---|
| Current value | `N/A` |
| Options | `Rolling` |

**pypylon API**

```python
# Get
value = camera.SensorShutterMode.Value

# Set (choose one option)
camera.SensorShutterMode.Value = "Rolling"
```

### `ExposureTimeMode`

**Exposure Time Mode** &nbsp; ![Enum](https://img.shields.io/badge/type-Enum-purple) &nbsp; ![ReadWrite](https://img.shields.io/badge/access-ReadWrite-green)

Sets the exposure time mode.

| Property | Value |
|---|---|
| Current value | `N/A` |
| Options | `Common` |

**pypylon API**

```python
# Get
value = camera.ExposureTimeMode.Value

# Set (choose one option)
camera.ExposureTimeMode.Value = "Common"
```

### `BslExposureTimeMode`

**Exposure Time Mode** &nbsp; ![Enum](https://img.shields.io/badge/type-Enum-purple) &nbsp; ![ReadWrite](https://img.shields.io/badge/access-ReadWrite-green)

Sets the exposure time mode.

| Property | Value |
|---|---|
| Current value | `N/A` |
| Options | `Standard` |

**pypylon API**

```python
# Get
value = camera.BslExposureTimeMode.Value

# Set (choose one option)
camera.BslExposureTimeMode.Value = "Standard"
```

### `ExposureTimeSelector`

**Exposure Time Selector** &nbsp; ![Enum](https://img.shields.io/badge/type-Enum-purple) &nbsp; ![ReadWrite](https://img.shields.io/badge/access-ReadWrite-green)

Sets the region to which the specified exposure time applies.

| Property | Value |
|---|---|
| Current value | `N/A` |
| Options | `Common` |

**pypylon API**

```python
# Get
value = camera.ExposureTimeSelector.Value

# Set (choose one option)
camera.ExposureTimeSelector.Value = "Common"
```

### `ExposureTime`

**Exposure Time** &nbsp; ![Float](https://img.shields.io/badge/type-Float-blue) &nbsp; ![ReadWrite](https://img.shields.io/badge/access-ReadWrite-green)

Exposure time of the camera in microseconds.

| Property | Value |
|---|---|
| Current value | `15000.0` |
| Range | `12.0` → `10000000.0` us |

**pypylon API**

```python
# Get
value = camera.ExposureTime.Value

# Set
camera.ExposureTime.Value = <value>
```

### `BslEffectiveExposureTime`

**Effective Exposure Time** &nbsp; ![Float](https://img.shields.io/badge/type-Float-blue) &nbsp; ![ReadOnly](https://img.shields.io/badge/access-ReadOnly-lightgrey)

Current exposure time of the camera in microseconds.

| Property | Value |
|---|---|
| Current value | `15007.0` |
| Range | `0.0` → `4294967295.0` us |

**pypylon API**

```python
# Get
value = camera.BslEffectiveExposureTime.Value

# Set
camera.BslEffectiveExposureTime.Value = <value>
```

### `ExposureAuto`

**Exposure Auto** &nbsp; ![Enum](https://img.shields.io/badge/type-Enum-purple) &nbsp; ![ReadWrite](https://img.shields.io/badge/access-ReadWrite-green)

Sets the operation mode of the Exposure Auto auto function. The Exposure Auto auto function automatically adjusts the exposure time within set limits until a target brightness value has been reached.

| Property | Value |
|---|---|
| Current value | `N/A` |
| Options | `Off` `Once` `Continuous` |

**pypylon API**

```python
# Get
value = camera.ExposureAuto.Value

# Set (choose one option)
camera.ExposureAuto.Value = "Off"
camera.ExposureAuto.Value = "Once"
camera.ExposureAuto.Value = "Continuous"
```

### `ExposureMode`

**Exposure Mode** &nbsp; ![Enum](https://img.shields.io/badge/type-Enum-purple) &nbsp; ![ReadWrite](https://img.shields.io/badge/access-ReadWrite-green)

Sets the exposure mode.

| Property | Value |
|---|---|
| Current value | `N/A` |
| Options | `Timed` |

**pypylon API**

```python
# Get
value = camera.ExposureMode.Value

# Set (choose one option)
camera.ExposureMode.Value = "Timed"
```

### `BslTransferBitDepthMode`

**Transfer Bit Depth Mode** &nbsp; ![Enum](https://img.shields.io/badge/type-Enum-purple) &nbsp; ![ReadWrite](https://img.shields.io/badge/access-ReadWrite-green)

Sets the transfer bit depth mode.

| Property | Value |
|---|---|
| Current value | `N/A` |
| Options | `Auto` `Manual` |

**pypylon API**

```python
# Get
value = camera.BslTransferBitDepthMode.Value

# Set (choose one option)
camera.BslTransferBitDepthMode.Value = "Auto"
camera.BslTransferBitDepthMode.Value = "Manual"
```

### `BslTransferBitDepth`

**Transfer Bit Depth** &nbsp; ![Enum](https://img.shields.io/badge/type-Enum-purple) &nbsp; ![ReadOnly](https://img.shields.io/badge/access-ReadOnly-lightgrey)

Sets the bit depth used for internal image processing. Lowering the transfer bit depth increases the frame rate, but image quality may degrade.

| Property | Value |
|---|---|
| Current value | `N/A` |
| Options | `Bpp10` |

**pypylon API**

```python
# Get
value = camera.BslTransferBitDepth.Value

# Set (choose one option)
camera.BslTransferBitDepth.Value = "Bpp10"
```

### `BslSensorBitDepthMode`

**Sensor Bit Depth Mode** &nbsp; ![Enum](https://img.shields.io/badge/type-Enum-purple) &nbsp; ![ReadWrite](https://img.shields.io/badge/access-ReadWrite-green)

Sets the sensor bit depth mode.

| Property | Value |
|---|---|
| Current value | `N/A` |
| Options | `Auto` `Manual` |

**pypylon API**

```python
# Get
value = camera.BslSensorBitDepthMode.Value

# Set (choose one option)
camera.BslSensorBitDepthMode.Value = "Auto"
camera.BslSensorBitDepthMode.Value = "Manual"
```

### `BslSensorBitDepth`

**Sensor Bit Depth** &nbsp; ![Enum](https://img.shields.io/badge/type-Enum-purple) &nbsp; ![ReadOnly](https://img.shields.io/badge/access-ReadOnly-lightgrey)

Sets the bit depth of the image sensor's data output. You can set the sensor bit depth independently of the pixel format used if the Sensor Bit Depth Mode parameter is set to Manual. If that parameter is set to Auto, the sensor bit depth is adjusted automatically depending on the pixel format used.

| Property | Value |
|---|---|
| Current value | `N/A` |
| Options | `Bpp10` |

**pypylon API**

```python
# Get
value = camera.BslSensorBitDepth.Value

# Set (choose one option)
camera.BslSensorBitDepth.Value = "Bpp10"
```

### `AcquisitionFrameRate`

**Acquisition Frame Rate** &nbsp; ![Float](https://img.shields.io/badge/type-Float-blue) &nbsp; ![ReadWrite](https://img.shields.io/badge/access-ReadWrite-green)

Acquisition frame rate of the camera in frames per second.

| Property | Value |
|---|---|
| Current value | `100.0` |
| Range | `0.2` → `1000000.0` Hz |

**pypylon API**

```python
# Get
value = camera.AcquisitionFrameRate.Value

# Set
camera.AcquisitionFrameRate.Value = <value>
```

### `AcquisitionFrameRateEnable`

**Enable Acquisition Frame Rate** &nbsp; ![Boolean](https://img.shields.io/badge/type-Boolean-orange) &nbsp; ![ReadWrite](https://img.shields.io/badge/access-ReadWrite-green)

Enables setting the camera's acquisition frame rate to a specified value.

| Property | Value |
|---|---|
| Current value | `False` |
| Options | `True` `False` |

**pypylon API**

```python
# Get
value = camera.AcquisitionFrameRateEnable.Value

# Set
camera.AcquisitionFrameRateEnable.Value = True   # or False
```

### `SensorReadoutTime`

**Sensor Readout Time** &nbsp; ![Float](https://img.shields.io/badge/type-Float-blue) &nbsp; ![ReadOnly](https://img.shields.io/badge/access-ReadOnly-lightgrey)

Sensor readout time with current settings.

| Property | Value |
|---|---|
| Current value | `23051.0` |
| Range | `0.0` → `4294967295.0` us |

**pypylon API**

```python
# Get
value = camera.SensorReadoutTime.Value

# Set
camera.SensorReadoutTime.Value = <value>
```

### `BslExposureStartDelay`

**Exposure Start Delay** &nbsp; ![Float](https://img.shields.io/badge/type-Float-blue) &nbsp; ![ReadOnly](https://img.shields.io/badge/access-ReadOnly-lightgrey)

Exposure start delay with current settings.

| Property | Value |
|---|---|
| Current value | `107329.0` |
| Range | `0.0` → `4294967295.0` us |

**pypylon API**

```python
# Get
value = camera.BslExposureStartDelay.Value

# Set
camera.BslExposureStartDelay.Value = <value>
```

### `ResultingFrameRate`

**Resulting Frame Rate** &nbsp; ![Float](https://img.shields.io/badge/type-Float-blue) &nbsp; ![ReadOnly](https://img.shields.io/badge/access-ReadOnly-lightgrey)

Maximum frame acquisition rate with current camera settings (in frames per second).

| Property | Value |
|---|---|
| Current value | `8.221723437667004` |
| Range | `-1.7976931348623157e+308` → `1.7976931348623157e+308` Hz |

**pypylon API**

```python
# Get
value = camera.ResultingFrameRate.Value

# Set
camera.ResultingFrameRate.Value = <value>
```

### `BslResultingAcquisitionFrameRate`

**Resulting Acquisition Frame Rate** &nbsp; ![Float](https://img.shields.io/badge/type-Float-blue) &nbsp; ![ReadOnly](https://img.shields.io/badge/access-ReadOnly-lightgrey)

Maximum number of frames that can be acquired per second with current camera settings. In High Speed burst mode, this value is usually higher than the Resulting Transfer Frame Rate parameter value.

| Property | Value |
|---|---|
| Current value | `8.221723437667004` |
| Range | `-1.7976931348623157e+308` → `1.7976931348623157e+308` Hz |

**pypylon API**

```python
# Get
value = camera.BslResultingAcquisitionFrameRate.Value

# Set
camera.BslResultingAcquisitionFrameRate.Value = <value>
```

### `BslResultingTransferFrameRate`

**Resulting Transfer Frame Rate** &nbsp; ![Float](https://img.shields.io/badge/type-Float-blue) &nbsp; ![ReadOnly](https://img.shields.io/badge/access-ReadOnly-lightgrey)

Maximum number of frames that can be transferred per second with current camera settings. This value indicates the peak frame rate to be expected at the camera's output. In High Speed burst mode, this value is usually lower than the Resulting Acquisition Frame Rate parameter value.

| Property | Value |
|---|---|
| Current value | `8.221723437667004` |
| Range | `-1.7976931348623157e+308` → `1.7976931348623157e+308` Hz |

**pypylon API**

```python
# Get
value = camera.BslResultingTransferFrameRate.Value

# Set
camera.BslResultingTransferFrameRate.Value = <value>
```

### `BslFlashWindowDelay`

**Flash Window Delay** &nbsp; ![Float](https://img.shields.io/badge/type-Float-blue) &nbsp; ![ReadOnly](https://img.shields.io/badge/access-ReadOnly-lightgrey)

Indicates the delay between the start of exposure and the start of the flash window in microseconds.

| Property | Value |
|---|---|
| Current value | `22730.0` |
| Range | `0.0` → `4294967295.0` us |

**pypylon API**

```python
# Get
value = camera.BslFlashWindowDelay.Value

# Set
camera.BslFlashWindowDelay.Value = <value>
```

### `BslFlashWindowDuration`

**Flash Window Duration** &nbsp; ![Float](https://img.shields.io/badge/type-Float-blue) &nbsp; ![ReadOnly](https://img.shields.io/badge/access-ReadOnly-lightgrey)

Indicates the width of the flash window in microseconds.

| Property | Value |
|---|---|
| Current value | `0.0` |
| Range | `-9.223372036854776e+18` → `9.223372036854776e+18` us |

**pypylon API**

```python
# Get
value = camera.BslFlashWindowDuration.Value

# Set
camera.BslFlashWindowDuration.Value = <value>
```

### `TriggerSelector`

**Trigger Selector** &nbsp; ![Enum](https://img.shields.io/badge/type-Enum-purple) &nbsp; ![ReadWrite](https://img.shields.io/badge/access-ReadWrite-green)

Sets the trigger type to be configured. All changes to the trigger settings will be applied to the selected trigger.

| Property | Value |
|---|---|
| Current value | `N/A` |
| Options | `FrameBurstStart` `FrameBurstEnd` `FrameBurstActive` `FrameStart` `FrameEnd` `FrameActive` `ExposureStart` `ExposureEnd` `ExposureActive` |

**pypylon API**

```python
# Get
value = camera.TriggerSelector.Value

# Set (choose one option)
camera.TriggerSelector.Value = "FrameBurstStart"
camera.TriggerSelector.Value = "FrameBurstEnd"
camera.TriggerSelector.Value = "FrameBurstActive"
camera.TriggerSelector.Value = "FrameStart"
camera.TriggerSelector.Value = "FrameEnd"
camera.TriggerSelector.Value = "FrameActive"
camera.TriggerSelector.Value = "ExposureStart"
camera.TriggerSelector.Value = "ExposureEnd"
camera.TriggerSelector.Value = "ExposureActive"
```

### `TriggerMode`

**Trigger Mode** &nbsp; ![Enum](https://img.shields.io/badge/type-Enum-purple) &nbsp; ![ReadWrite](https://img.shields.io/badge/access-ReadWrite-green)

Sets the mode for the currently selected trigger.

| Property | Value |
|---|---|
| Current value | `N/A` |
| Options | `Off` `On` |

**pypylon API**

```python
# Get
value = camera.TriggerMode.Value

# Set (choose one option)
camera.TriggerMode.Value = "Off"
camera.TriggerMode.Value = "On"
```

### `TriggerSource`

**Trigger Source** &nbsp; ![Enum](https://img.shields.io/badge/type-Enum-purple) &nbsp; ![ReadWrite](https://img.shields.io/badge/access-ReadWrite-green)

Sets the source signal for the selected trigger.

| Property | Value |
|---|---|
| Current value | `N/A` |
| Options | `Software` `Line1` `Line2` `Line3` `SoftwareSignal1` `SoftwareSignal2` `SoftwareSignal3` `PeriodicSignal1` `Action1` `Counter1Active` `Counter1End` `Counter1Start` `Counter2Active` `Counter2End` `Counter2Start` `Timer1Active` `Timer1End` `Timer2Active` `Timer2End` |

**pypylon API**

```python
# Get
value = camera.TriggerSource.Value

# Set (choose one option)
camera.TriggerSource.Value = "Software"
camera.TriggerSource.Value = "Line1"
camera.TriggerSource.Value = "Line2"
camera.TriggerSource.Value = "Line3"
camera.TriggerSource.Value = "SoftwareSignal1"
camera.TriggerSource.Value = "SoftwareSignal2"
camera.TriggerSource.Value = "SoftwareSignal3"
camera.TriggerSource.Value = "PeriodicSignal1"
camera.TriggerSource.Value = "Action1"
camera.TriggerSource.Value = "Counter1Active"
camera.TriggerSource.Value = "Counter1End"
camera.TriggerSource.Value = "Counter1Start"
camera.TriggerSource.Value = "Counter2Active"
camera.TriggerSource.Value = "Counter2End"
camera.TriggerSource.Value = "Counter2Start"
camera.TriggerSource.Value = "Timer1Active"
camera.TriggerSource.Value = "Timer1End"
camera.TriggerSource.Value = "Timer2Active"
camera.TriggerSource.Value = "Timer2End"
```

### `TriggerSoftware`

**Generate Software Trigger** &nbsp; ![Command](https://img.shields.io/badge/type-Command-red) &nbsp; ![ReadWrite](https://img.shields.io/badge/access-ReadWrite-green)

Generates a software trigger signal. The software trigger signal will be used if the Trigger Source parameter is set to Trigger Software.

| Property | Value |
|---|---|
| Current value | `(executable command)` |

**pypylon API**

```python
camera.TriggerSoftware.Execute()
```

### `TriggerDelay`

**Trigger Delay** &nbsp; ![Float](https://img.shields.io/badge/type-Float-blue) &nbsp; ![ReadWrite](https://img.shields.io/badge/access-ReadWrite-green)

Trigger delay time in microseconds. The delay is applied after the trigger has been received and before effectively activating the trigger.

| Property | Value |
|---|---|
| Current value | `0.0` |
| Range | `0.0` → `10000.0` us |

**pypylon API**

```python
# Get
value = camera.TriggerDelay.Value

# Set
camera.TriggerDelay.Value = <value>
```

### `BslAcquisitionBurstMode`

**Acquisition Burst Mode** &nbsp; ![Enum](https://img.shields.io/badge/type-Enum-purple) &nbsp; ![ReadWrite](https://img.shields.io/badge/access-ReadWrite-green)

Sets the burst mode.

| Property | Value |
|---|---|
| Current value | `N/A` |
| Options | `Standard` |

**pypylon API**

```python
# Get
value = camera.BslAcquisitionBurstMode.Value

# Set (choose one option)
camera.BslAcquisitionBurstMode.Value = "Standard"
```

### `AcquisitionBurstFrameCount`

**Acquisition Burst Frame Count** &nbsp; ![Integer](https://img.shields.io/badge/type-Integer-blue) &nbsp; ![ReadWrite](https://img.shields.io/badge/access-ReadWrite-green)

Number of frames to acquire for each Frame Burst Start trigger.

| Property | Value |
|---|---|
| Current value | `1` |
| Range | `1` → `1023` (step `1`) |

**pypylon API**

```python
# Get
value = camera.AcquisitionBurstFrameCount.Value

# Set
camera.AcquisitionBurstFrameCount.Value = <value>
```

### `BslResultingFrameBurstRate`

**Resulting Frame Burst Rate** &nbsp; ![Float](https://img.shields.io/badge/type-Float-blue) &nbsp; ![ReadOnly](https://img.shields.io/badge/access-ReadOnly-lightgrey)

Maximum number of bursts per second with current camera settings.

| Property | Value |
|---|---|
| Current value | `4.110861718833502` |
| Range | `-1.7976931348623157e+308` → `1.7976931348623157e+308` Hz |

**pypylon API**

```python
# Get
value = camera.BslResultingFrameBurstRate.Value

# Set
camera.BslResultingFrameBurstRate.Value = <value>
```

### `AcquisitionStatusSelector`

**Acquisition Status Selector** &nbsp; ![Enum](https://img.shields.io/badge/type-Enum-purple) &nbsp; ![ReadWrite](https://img.shields.io/badge/access-ReadWrite-green)

Sets the signal whose status you want to check. Its status can be checked by reading the Acquisition Status parameter value.

| Property | Value |
|---|---|
| Current value | `N/A` |
| Options | `AcquisitionActive` `ExposureActive` `ExposureTriggerWait` `FlashWindow` `FrameBurstActive` `FrameBurstTriggerWait` `FrameTriggerWait` |

**pypylon API**

```python
# Get
value = camera.AcquisitionStatusSelector.Value

# Set (choose one option)
camera.AcquisitionStatusSelector.Value = "AcquisitionActive"
camera.AcquisitionStatusSelector.Value = "ExposureActive"
camera.AcquisitionStatusSelector.Value = "ExposureTriggerWait"
camera.AcquisitionStatusSelector.Value = "FlashWindow"
camera.AcquisitionStatusSelector.Value = "FrameBurstActive"
camera.AcquisitionStatusSelector.Value = "FrameBurstTriggerWait"
camera.AcquisitionStatusSelector.Value = "FrameTriggerWait"
```

### `AcquisitionStatus`

**Acquisition Status** &nbsp; ![Boolean](https://img.shields.io/badge/type-Boolean-orange) &nbsp; ![ReadOnly](https://img.shields.io/badge/access-ReadOnly-lightgrey)

Indicates whether the camera is waiting for trigger signals. You should only use this feature if the camera is configured for software triggering. If the camera is configured for hardware triggering, monitor the camera's Trigger Wait signals instead.

| Property | Value |
|---|---|
| Current value | `False` |
| Options | `True` `False` |

**pypylon API**

```python
# Get
value = camera.AcquisitionStatus.Value

# Set
camera.AcquisitionStatus.Value = True   # or False
```

### `BslSensorState`

**Sensor State** &nbsp; ![Enum](https://img.shields.io/badge/type-Enum-purple) &nbsp; ![ReadOnly](https://img.shields.io/badge/access-ReadOnly-lightgrey)

Returns the current power state of the sensor.

| Property | Value |
|---|---|
| Current value | `N/A` |
| Options | `Off` `Standby` `On` |

**pypylon API**

```python
# Get
value = camera.BslSensorState.Value

# Set (choose one option)
camera.BslSensorState.Value = "Off"
camera.BslSensorState.Value = "Standby"
camera.BslSensorState.Value = "On"
```

### `BslSensorOff`

**Sensor Off** &nbsp; ![Command](https://img.shields.io/badge/type-Command-red) &nbsp; ![ReadWrite](https://img.shields.io/badge/access-ReadWrite-green)

Switches the sensor power off.

| Property | Value |
|---|---|
| Current value | `(executable command)` |

**pypylon API**

```python
camera.BslSensorOff.Execute()
```

### `BslSensorStandby`

**Sensor Standby** &nbsp; ![Command](https://img.shields.io/badge/type-Command-red) &nbsp; ![ReadWrite](https://img.shields.io/badge/access-ReadWrite-green)

Puts the sensor in standby mode. In standby mode, power consumption is reduced significantly, which results in a lower camera temperature. Certain parameters can only be configured when the sensor is in standby mode.

| Property | Value |
|---|---|
| Current value | `(executable command)` |

**pypylon API**

```python
camera.BslSensorStandby.Execute()
```

### `BslSensorOn`

**Sensor On** &nbsp; ![Command](https://img.shields.io/badge/type-Command-red) &nbsp; ![ReadWrite](https://img.shields.io/badge/access-ReadWrite-green)

Switches the sensor power on.

| Property | Value |
|---|---|
| Current value | `(executable command)` |

**pypylon API**

```python
camera.BslSensorOn.Execute()
```

---

## Analog Control

### `GainSelector`

**Gain Selector** &nbsp; ![Enum](https://img.shields.io/badge/type-Enum-purple) &nbsp; ![ReadWrite](https://img.shields.io/badge/access-ReadWrite-green)

Sets the gain type to be adjusted. All changes to the Gain parameter will be applied to the selected gain type.

| Property | Value |
|---|---|
| Current value | `N/A` |
| Options | `All` |

**pypylon API**

```python
# Get
value = camera.GainSelector.Value

# Set (choose one option)
camera.GainSelector.Value = "All"
```

### `Gain`

**Gain** &nbsp; ![Float](https://img.shields.io/badge/type-Float-blue) &nbsp; ![ReadWrite](https://img.shields.io/badge/access-ReadWrite-green)

Value of the currently selected gain in dB.

| Property | Value |
|---|---|
| Current value | `0.0` |
| Range | `0.0` → `48.00000004350822` dB |

**pypylon API**

```python
# Get
value = camera.Gain.Value

# Set
camera.Gain.Value = <value>
```

### `GainAuto`

**Gain Auto** &nbsp; ![Enum](https://img.shields.io/badge/type-Enum-purple) &nbsp; ![ReadWrite](https://img.shields.io/badge/access-ReadWrite-green)

Sets the operation mode of the Gain Auto auto function. The Gain Auto auto function automatically adjusts the gain within set limits until a target brightness value has been reached.

| Property | Value |
|---|---|
| Current value | `N/A` |
| Options | `Off` `Once` `Continuous` |

**pypylon API**

```python
# Get
value = camera.GainAuto.Value

# Set (choose one option)
camera.GainAuto.Value = "Off"
camera.GainAuto.Value = "Once"
camera.GainAuto.Value = "Continuous"
```

### `BlackLevelSelector`

**Black Level Selector** &nbsp; ![Enum](https://img.shields.io/badge/type-Enum-purple) &nbsp; ![ReadWrite](https://img.shields.io/badge/access-ReadWrite-green)

Sets the type of black level adjustment to be configured.

| Property | Value |
|---|---|
| Current value | `N/A` |
| Options | `All` |

**pypylon API**

```python
# Get
value = camera.BlackLevelSelector.Value

# Set (choose one option)
camera.BlackLevelSelector.Value = "All"
```

### `BlackLevel`

**Black Level** &nbsp; ![Float](https://img.shields.io/badge/type-Float-blue) &nbsp; ![ReadWrite](https://img.shields.io/badge/access-ReadWrite-green)

Black level value to be applied to the currently selected sensor tap.

| Property | Value |
|---|---|
| Current value | `0.0` |
| Range | `0.0` → `1023.0` DN |

**pypylon API**

```python
# Get
value = camera.BlackLevel.Value

# Set
camera.BlackLevel.Value = <value>
```

### `Gamma`

**Gamma** &nbsp; ![Float](https://img.shields.io/badge/type-Float-blue) &nbsp; ![ReadWrite](https://img.shields.io/badge/access-ReadWrite-green)

Gamma correction to be applied. Gamma correction allows you to optimize the brightness of acquired images for display on a monitor.

| Property | Value |
|---|---|
| Current value | `1.0` |
| Range | `0.0` → `3.9999847412109375` |

**pypylon API**

```python
# Get
value = camera.Gamma.Value

# Set
camera.Gamma.Value = <value>
```

### `DigitalShift`

**Digital Shift** &nbsp; ![Integer](https://img.shields.io/badge/type-Integer-blue) &nbsp; ![ReadWrite](https://img.shields.io/badge/access-ReadWrite-green)

Digital shift allows you to multiply the pixel values in an image. This increases the brightness of the image. If the parameter is set to zero, digital shift is disabled.

| Property | Value |
|---|---|
| Current value | `0` |
| Range | `0` → `4` (step `1`) |

**pypylon API**

```python
# Get
value = camera.DigitalShift.Value

# Set
camera.DigitalShift.Value = <value>
```

---

## Auto Function Control

### `AutoTargetBrightness`

**Auto Target Brightness** &nbsp; ![Float](https://img.shields.io/badge/type-Float-blue) &nbsp; ![ReadWrite](https://img.shields.io/badge/access-ReadWrite-green)

Target brightness for the Gain Auto and the Exposure Auto auto functions.

| Property | Value |
|---|---|
| Current value | `0.5001221001221001` |
| Range | `0.0` → `1.0` |

**pypylon API**

```python
# Get
value = camera.AutoTargetBrightness.Value

# Set
camera.AutoTargetBrightness.Value = <value>
```

### `AutoFunctionProfile`

**Auto Function Profile** &nbsp; ![Enum](https://img.shields.io/badge/type-Enum-purple) &nbsp; ![ReadWrite](https://img.shields.io/badge/access-ReadWrite-green)

Sets how gain and exposure time will be balanced when the camera is making automatic adjustments.

| Property | Value |
|---|---|
| Current value | `N/A` |
| Options | `MinimizeGain` `MinimizeExposureTime` |

**pypylon API**

```python
# Get
value = camera.AutoFunctionProfile.Value

# Set (choose one option)
camera.AutoFunctionProfile.Value = "MinimizeGain"
camera.AutoFunctionProfile.Value = "MinimizeExposureTime"
```

### `AutoGainLowerLimit`

**Gain Lower Limit** &nbsp; ![Float](https://img.shields.io/badge/type-Float-blue) &nbsp; ![ReadWrite](https://img.shields.io/badge/access-ReadWrite-green)

Lower limit of the Gain parameter when the Gain Auto auto function is active.

| Property | Value |
|---|---|
| Current value | `0.0` |
| Range | `0.0` → `48.00000004350822` dB |

**pypylon API**

```python
# Get
value = camera.AutoGainLowerLimit.Value

# Set
camera.AutoGainLowerLimit.Value = <value>
```

### `AutoGainUpperLimit`

**Gain Upper Limit** &nbsp; ![Float](https://img.shields.io/badge/type-Float-blue) &nbsp; ![ReadWrite](https://img.shields.io/badge/access-ReadWrite-green)

Upper limit of the Gain parameter when the Gain Auto auto function is active.

| Property | Value |
|---|---|
| Current value | `24.000003323148814` |
| Range | `0.0` → `48.00000004350822` dB |

**pypylon API**

```python
# Get
value = camera.AutoGainUpperLimit.Value

# Set
camera.AutoGainUpperLimit.Value = <value>
```

### `AutoExposureTimeLowerLimit`

**Exposure Time Lower Limit** &nbsp; ![Float](https://img.shields.io/badge/type-Float-blue) &nbsp; ![ReadWrite](https://img.shields.io/badge/access-ReadWrite-green)

Lower limit of the Exposure Time parameter when the Exposure Auto auto function is active.

| Property | Value |
|---|---|
| Current value | `1.0` |
| Range | `1.0` → `10000000.0` us |

**pypylon API**

```python
# Get
value = camera.AutoExposureTimeLowerLimit.Value

# Set
camera.AutoExposureTimeLowerLimit.Value = <value>
```

### `AutoExposureTimeUpperLimit`

**Exposure Time Upper Limit** &nbsp; ![Float](https://img.shields.io/badge/type-Float-blue) &nbsp; ![ReadWrite](https://img.shields.io/badge/access-ReadWrite-green)

Upper limit of the Exposure Time parameter when the Exposure Auto auto function is active.

| Property | Value |
|---|---|
| Current value | `100000.0` |
| Range | `1.0` → `10000000.0` us |

**pypylon API**

```python
# Get
value = camera.AutoExposureTimeUpperLimit.Value

# Set
camera.AutoExposureTimeUpperLimit.Value = <value>
```

### `AutoFunctionROISelector`

**ROI Selector** &nbsp; ![Enum](https://img.shields.io/badge/type-Enum-purple) &nbsp; ![ReadWrite](https://img.shields.io/badge/access-ReadWrite-green)

Sets which auto function ROI can be configured.

| Property | Value |
|---|---|
| Current value | `N/A` |
| Options | `ROI1` `ROI2` |

**pypylon API**

```python
# Get
value = camera.AutoFunctionROISelector.Value

# Set (choose one option)
camera.AutoFunctionROISelector.Value = "ROI1"
camera.AutoFunctionROISelector.Value = "ROI2"
```

### `AutoFunctionROIWidth`

**Width** &nbsp; ![Integer](https://img.shields.io/badge/type-Integer-blue) &nbsp; ![ReadWrite](https://img.shields.io/badge/access-ReadWrite-green)

Width of the auto function ROI (in pixels).

| Property | Value |
|---|---|
| Current value | `3536` |
| Range | `2` → `3548` (step `2`) |

**pypylon API**

```python
# Get
value = camera.AutoFunctionROIWidth.Value

# Set
camera.AutoFunctionROIWidth.Value = <value>
```

### `AutoFunctionROIHeight`

**Height** &nbsp; ![Integer](https://img.shields.io/badge/type-Integer-blue) &nbsp; ![ReadWrite](https://img.shields.io/badge/access-ReadWrite-green)

Height of the auto function ROI (in pixels).

| Property | Value |
|---|---|
| Current value | `3536` |
| Range | `2` → `3552` (step `2`) |

**pypylon API**

```python
# Get
value = camera.AutoFunctionROIHeight.Value

# Set
camera.AutoFunctionROIHeight.Value = <value>
```

### `AutoFunctionROIOffsetX`

**Offset X** &nbsp; ![Integer](https://img.shields.io/badge/type-Integer-blue) &nbsp; ![ReadWrite](https://img.shields.io/badge/access-ReadWrite-green)

Horizontal offset of the auto function ROI from the left side of the sensor (in pixels).

| Property | Value |
|---|---|
| Current value | `6` |
| Range | `0` → `12` (step `2`) |

**pypylon API**

```python
# Get
value = camera.AutoFunctionROIOffsetX.Value

# Set
camera.AutoFunctionROIOffsetX.Value = <value>
```

### `AutoFunctionROIOffsetY`

**Offset Y** &nbsp; ![Integer](https://img.shields.io/badge/type-Integer-blue) &nbsp; ![ReadWrite](https://img.shields.io/badge/access-ReadWrite-green)

Vertical offset of the auto function ROI from the top of the sensor (in pixels).

| Property | Value |
|---|---|
| Current value | `8` |
| Range | `0` → `16` (step `2`) |

**pypylon API**

```python
# Get
value = camera.AutoFunctionROIOffsetY.Value

# Set
camera.AutoFunctionROIOffsetY.Value = <value>
```

### `AutoFunctionROIUseBrightness`

**Brightness** &nbsp; ![Boolean](https://img.shields.io/badge/type-Boolean-orange) &nbsp; ![ReadWrite](https://img.shields.io/badge/access-ReadWrite-green)

Assigns the Gain Auto and the Exposure Auto auto functions to the currently selected auto function ROI. For this parameter, Gain Auto and Exposure Auto are considered as a single auto function named 'Brightness'.

| Property | Value |
|---|---|
| Current value | `True` |
| Options | `True` `False` |

**pypylon API**

```python
# Get
value = camera.AutoFunctionROIUseBrightness.Value

# Set
camera.AutoFunctionROIUseBrightness.Value = True   # or False
```

### `AutoFunctionROIUseWhiteBalance`

**White Balance** &nbsp; ![Boolean](https://img.shields.io/badge/type-Boolean-orange) &nbsp; ![ReadWrite](https://img.shields.io/badge/access-ReadWrite-green)

Assigns the Balance White Auto auto function to the currently selected auto function ROI.

| Property | Value |
|---|---|
| Current value | `False` |
| Options | `True` `False` |

**pypylon API**

```python
# Get
value = camera.AutoFunctionROIUseWhiteBalance.Value

# Set
camera.AutoFunctionROIUseWhiteBalance.Value = True   # or False
```

### `AutoFunctionROIHighlight`

**Highlight ROI** &nbsp; ![Boolean](https://img.shields.io/badge/type-Boolean-orange) &nbsp; ![ReadWrite](https://img.shields.io/badge/access-ReadWrite-green)

Highlights the current auto function ROI in the image window. Areas that do not belong to the current ROI appear darker.

| Property | Value |
|---|---|
| Current value | `False` |
| Options | `True` `False` |

**pypylon API**

```python
# Get
value = camera.AutoFunctionROIHighlight.Value

# Set
camera.AutoFunctionROIHighlight.Value = True   # or False
```

---

## Image Format Control

### `SensorWidth`

**Sensor Width** &nbsp; ![Integer](https://img.shields.io/badge/type-Integer-blue) &nbsp; ![ReadOnly](https://img.shields.io/badge/access-ReadOnly-lightgrey)

Width of the camera's sensor in pixels.

| Property | Value |
|---|---|
| Current value | `3548` |
| Range | `0` → `4294967295` (step `1`) |

**pypylon API**

```python
# Get
value = camera.SensorWidth.Value

# Set
camera.SensorWidth.Value = <value>
```

### `SensorHeight`

**Sensor Height** &nbsp; ![Integer](https://img.shields.io/badge/type-Integer-blue) &nbsp; ![ReadOnly](https://img.shields.io/badge/access-ReadOnly-lightgrey)

Height of the camera's sensor in pixels.

| Property | Value |
|---|---|
| Current value | `3552` |
| Range | `0` → `4294967295` (step `1`) |

**pypylon API**

```python
# Get
value = camera.SensorHeight.Value

# Set
camera.SensorHeight.Value = <value>
```

### `ReverseX`

**Reverse X** &nbsp; ![Boolean](https://img.shields.io/badge/type-Boolean-orange) &nbsp; ![ReadWrite](https://img.shields.io/badge/access-ReadWrite-green)

Enables horizontal mirroring of the image. The pixel values of every line in a captured image will be swapped along the line's center. You can use the ROI feature when using the Reverse X feature. The position of the ROI relative to the sensor remains the same.

| Property | Value |
|---|---|
| Current value | `False` |
| Options | `True` `False` |

**pypylon API**

```python
# Get
value = camera.ReverseX.Value

# Set
camera.ReverseX.Value = True   # or False
```

### `ReverseY`

**Reverse Y** &nbsp; ![Boolean](https://img.shields.io/badge/type-Boolean-orange) &nbsp; ![ReadWrite](https://img.shields.io/badge/access-ReadWrite-green)

Enables vertical mirroring of the image. The pixel values of every column in a captured image will be swapped along the column's center. You can use the ROI feature when using the Reverse Y feature. The position of the ROI relative to the sensor remains the same.

| Property | Value |
|---|---|
| Current value | `False` |
| Options | `True` `False` |

**pypylon API**

```python
# Get
value = camera.ReverseY.Value

# Set
camera.ReverseY.Value = True   # or False
```

### `WidthMax`

**Max Width** &nbsp; ![Integer](https://img.shields.io/badge/type-Integer-blue) &nbsp; ![ReadOnly](https://img.shields.io/badge/access-ReadOnly-lightgrey)

Maximum width of the region of interest (area of interest) in pixels. The value takes into account any function that may limit the maximum width.

| Property | Value |
|---|---|
| Current value | `3548` |
| Range | `-9223372036854775808` → `9223372036854775807` (step `1`) |

**pypylon API**

```python
# Get
value = camera.WidthMax.Value

# Set
camera.WidthMax.Value = <value>
```

### `HeightMax`

**Max Height** &nbsp; ![Integer](https://img.shields.io/badge/type-Integer-blue) &nbsp; ![ReadOnly](https://img.shields.io/badge/access-ReadOnly-lightgrey)

Maximum height of the region of interest (area of interest) in pixels. The value takes into account any features that may limit the maximum height, e.g., binning.

| Property | Value |
|---|---|
| Current value | `3552` |
| Range | `-9223372036854775808` → `9223372036854775807` (step `1`) |

**pypylon API**

```python
# Get
value = camera.HeightMax.Value

# Set
camera.HeightMax.Value = <value>
```

### `Width`

**Width** &nbsp; ![Integer](https://img.shields.io/badge/type-Integer-blue) &nbsp; ![ReadWrite](https://img.shields.io/badge/access-ReadWrite-green)

Width of the camera's region of interest (area of interest) in pixels. Depending on the camera model, the parameter can be set in different increments.

| Property | Value |
|---|---|
| Current value | `3536` |
| Range | `2` → `3548` (step `2`) |

**pypylon API**

```python
# Get
value = camera.Width.Value

# Set
camera.Width.Value = <value>
```

### `Height`

**Height** &nbsp; ![Integer](https://img.shields.io/badge/type-Integer-blue) &nbsp; ![ReadWrite](https://img.shields.io/badge/access-ReadWrite-green)

Height of the camera's region of interest (area of interest) in pixels. Depending on the camera model, the parameter can be set in different increments.

| Property | Value |
|---|---|
| Current value | `3536` |
| Range | `2` → `3552` (step `2`) |

**pypylon API**

```python
# Get
value = camera.Height.Value

# Set
camera.Height.Value = <value>
```

### `OffsetX`

**Offset X** &nbsp; ![Integer](https://img.shields.io/badge/type-Integer-blue) &nbsp; ![ReadWrite](https://img.shields.io/badge/access-ReadWrite-green)

Horizontal offset from the left side of the sensor to the region of interest (area of interest) (in pixels).

| Property | Value |
|---|---|
| Current value | `6` |
| Range | `0` → `12` (step `2`) |

**pypylon API**

```python
# Get
value = camera.OffsetX.Value

# Set
camera.OffsetX.Value = <value>
```

### `OffsetY`

**Offset Y** &nbsp; ![Integer](https://img.shields.io/badge/type-Integer-blue) &nbsp; ![ReadWrite](https://img.shields.io/badge/access-ReadWrite-green)

Vertical offset from the top of the sensor to the region of interest (area of interest) (in pixels).

| Property | Value |
|---|---|
| Current value | `8` |
| Range | `0` → `16` (step `2`) |

**pypylon API**

```python
# Get
value = camera.OffsetY.Value

# Set
camera.OffsetY.Value = <value>
```

### `BslCenterX`

**Center X** &nbsp; ![Command](https://img.shields.io/badge/type-Command-red) &nbsp; ![ReadWrite](https://img.shields.io/badge/access-ReadWrite-green)

Centers the image horizontally.

| Property | Value |
|---|---|
| Current value | `(executable command)` |

**pypylon API**

```python
camera.BslCenterX.Execute()
```

### `BslCenterY`

**Center Y** &nbsp; ![Command](https://img.shields.io/badge/type-Command-red) &nbsp; ![ReadWrite](https://img.shields.io/badge/access-ReadWrite-green)

Centers the image vertically.

| Property | Value |
|---|---|
| Current value | `(executable command)` |

**pypylon API**

```python
camera.BslCenterY.Execute()
```

### `PixelFormat`

**Pixel Format** &nbsp; ![Enum](https://img.shields.io/badge/type-Enum-purple) &nbsp; ![ReadWrite](https://img.shields.io/badge/access-ReadWrite-green)

Sets the format of the pixel data transmitted by the camera. The available pixel formats depend on the camera model and whether the camera is monochrome or color.

| Property | Value |
|---|---|
| Current value | `N/A` |
| Options | `Mono8` `Mono10` `Mono10p` `Mono12` `Mono12p` `RGB8` `BGR8` `YCbCr422_8` `BayerRG8` `BayerRG10` `BayerRG10p` `BayerRG12` `BayerRG12p` |

**pypylon API**

```python
# Get
value = camera.PixelFormat.Value

# Set (choose one option)
camera.PixelFormat.Value = "Mono8"
camera.PixelFormat.Value = "Mono10"
camera.PixelFormat.Value = "Mono10p"
camera.PixelFormat.Value = "Mono12"
camera.PixelFormat.Value = "Mono12p"
camera.PixelFormat.Value = "RGB8"
camera.PixelFormat.Value = "BGR8"
camera.PixelFormat.Value = "YCbCr422_8"
camera.PixelFormat.Value = "BayerRG8"
camera.PixelFormat.Value = "BayerRG10"
camera.PixelFormat.Value = "BayerRG10p"
camera.PixelFormat.Value = "BayerRG12"
camera.PixelFormat.Value = "BayerRG12p"
```

### `PixelSize`

**Pixel Size** &nbsp; ![Enum](https://img.shields.io/badge/type-Enum-purple) &nbsp; ![ReadOnly](https://img.shields.io/badge/access-ReadOnly-lightgrey)

Indicates the depth of the pixel values in the image (in bits per pixel). The potential values depend on the pixel format setting.

| Property | Value |
|---|---|
| Current value | `N/A` |
| Options | `Bpp8` `Bpp10` `Bpp12` `Bpp16` `Bpp24` `Bpp30` `Bpp32` `Bpp36` |

**pypylon API**

```python
# Get
value = camera.PixelSize.Value

# Set (choose one option)
camera.PixelSize.Value = "Bpp8"
camera.PixelSize.Value = "Bpp10"
camera.PixelSize.Value = "Bpp12"
camera.PixelSize.Value = "Bpp16"
camera.PixelSize.Value = "Bpp24"
camera.PixelSize.Value = "Bpp30"
camera.PixelSize.Value = "Bpp32"
camera.PixelSize.Value = "Bpp36"
```

### `PixelDynamicRangeMin`

**Dynamic Range Min** &nbsp; ![Integer](https://img.shields.io/badge/type-Integer-blue) &nbsp; ![ReadOnly](https://img.shields.io/badge/access-ReadOnly-lightgrey)

Minimum possible pixel value that can be transferred from the camera.

| Property | Value |
|---|---|
| Current value | `0` |
| Range | `-9223372036854775808` → `9223372036854775807` (step `1`) |

**pypylon API**

```python
# Get
value = camera.PixelDynamicRangeMin.Value

# Set
camera.PixelDynamicRangeMin.Value = <value>
```

### `PixelDynamicRangeMax`

**Dynamic Range Max** &nbsp; ![Integer](https://img.shields.io/badge/type-Integer-blue) &nbsp; ![ReadOnly](https://img.shields.io/badge/access-ReadOnly-lightgrey)

Maximum possible pixel value that can be transferred from the camera.

| Property | Value |
|---|---|
| Current value | `255` |
| Range | `0` → `4294967295` (step `1`) |

**pypylon API**

```python
# Get
value = camera.PixelDynamicRangeMax.Value

# Set
camera.PixelDynamicRangeMax.Value = <value>
```

### `TestPattern`

**Test Pattern** &nbsp; ![Enum](https://img.shields.io/badge/type-Enum-purple) &nbsp; ![ReadWrite](https://img.shields.io/badge/access-ReadWrite-green)

Sets the test pattern to display.

| Property | Value |
|---|---|
| Current value | `N/A` |
| Options | `Off` `Black` `White` `Testimage1` `Testimage2` `Testimage3` `Testimage6` |

**pypylon API**

```python
# Get
value = camera.TestPattern.Value

# Set (choose one option)
camera.TestPattern.Value = "Off"
camera.TestPattern.Value = "Black"
camera.TestPattern.Value = "White"
camera.TestPattern.Value = "Testimage1"
camera.TestPattern.Value = "Testimage2"
camera.TestPattern.Value = "Testimage3"
camera.TestPattern.Value = "Testimage6"
```

---

## Image Processing Control

### `BslColorSpace`

**Color Space** &nbsp; ![Enum](https://img.shields.io/badge/type-Enum-purple) &nbsp; ![ReadWrite](https://img.shields.io/badge/access-ReadWrite-green)

Sets the color space for image acquisitions. Note that the gamma correction value also influences the perception of brightness in the resulting images.

| Property | Value |
|---|---|
| Current value | `N/A` |
| Options | `Off` `sRgb` |

**pypylon API**

```python
# Get
value = camera.BslColorSpace.Value

# Set (choose one option)
camera.BslColorSpace.Value = "Off"
camera.BslColorSpace.Value = "sRgb"
```

### `BslLightSourcePreset`

**Light Source Preset** &nbsp; ![Enum](https://img.shields.io/badge/type-Enum-purple) &nbsp; ![ReadWrite](https://img.shields.io/badge/access-ReadWrite-green)

Sets the light source preset. The colors in the image will be corrected so that they are appropriate for the selected light source.

| Property | Value |
|---|---|
| Current value | `N/A` |
| Options | `Off` `Tungsten` `Daylight5000K` `Daylight6500K` `FactoryLED6000K` |

**pypylon API**

```python
# Get
value = camera.BslLightSourcePreset.Value

# Set (choose one option)
camera.BslLightSourcePreset.Value = "Off"
camera.BslLightSourcePreset.Value = "Tungsten"
camera.BslLightSourcePreset.Value = "Daylight5000K"
camera.BslLightSourcePreset.Value = "Daylight6500K"
camera.BslLightSourcePreset.Value = "FactoryLED6000K"
```

### `BslLightSourcePresetFeatureSelector`

**Light Source Preset Feature Selector** &nbsp; ![Enum](https://img.shields.io/badge/type-Enum-purple) &nbsp; ![ReadWrite](https://img.shields.io/badge/access-ReadWrite-green)

Sets which features the camera adjusts when you select a light source preset. By default, the camera adjust all features.

| Property | Value |
|---|---|
| Current value | `N/A` |
| Options | `WhiteBalance` `ColorTransformation` `ColorAdjustment` |

**pypylon API**

```python
# Get
value = camera.BslLightSourcePresetFeatureSelector.Value

# Set (choose one option)
camera.BslLightSourcePresetFeatureSelector.Value = "WhiteBalance"
camera.BslLightSourcePresetFeatureSelector.Value = "ColorTransformation"
camera.BslLightSourcePresetFeatureSelector.Value = "ColorAdjustment"
```

### `BslLightSourcePresetFeatureEnable`

**Light Source Preset Feature Enable** &nbsp; ![Boolean](https://img.shields.io/badge/type-Boolean-orange) &nbsp; ![ReadWrite](https://img.shields.io/badge/access-ReadWrite-green)

Enables adjustment of the feature specified by the Light Source Preset Feature Selector parameter.

| Property | Value |
|---|---|
| Current value | `True` |
| Options | `True` `False` |

**pypylon API**

```python
# Get
value = camera.BslLightSourcePresetFeatureEnable.Value

# Set
camera.BslLightSourcePresetFeatureEnable.Value = True   # or False
```

### `BslHue`

**Hue** &nbsp; ![Float](https://img.shields.io/badge/type-Float-blue) &nbsp; ![ReadWrite](https://img.shields.io/badge/access-ReadWrite-green)

Adjusting the hue shifts the colors of the image. This can be useful, e.g., to correct minor color shifts or to create false-color images.

| Property | Value |
|---|---|
| Current value | `0.0` |
| Range | `-180.0` → `180.0` |

**pypylon API**

```python
# Get
value = camera.BslHue.Value

# Set
camera.BslHue.Value = <value>
```

### `BslHueRaw`

**Hue (Raw)** &nbsp; ![Integer](https://img.shields.io/badge/type-Integer-blue) &nbsp; ![ReadWrite](https://img.shields.io/badge/access-ReadWrite-green)

Adjusting the hue shifts the colors of the image. This can be useful, e.g., to correct minor color shifts or to create false-color images.

| Property | Value |
|---|---|
| Current value | `0` |
| Range | `-180` → `180` (step `1`) |

**pypylon API**

```python
# Get
value = camera.BslHueRaw.Value

# Set
camera.BslHueRaw.Value = <value>
```

### `BslSaturation`

**Saturation** &nbsp; ![Float](https://img.shields.io/badge/type-Float-blue) &nbsp; ![ReadWrite](https://img.shields.io/badge/access-ReadWrite-green)

Adjusting the saturation changes the colorfulness (intensity) of the colors. A higher saturation, for example, makes colors easier to distinguish.

| Property | Value |
|---|---|
| Current value | `1.0` |
| Range | `0.0` → `2.0` |

**pypylon API**

```python
# Get
value = camera.BslSaturation.Value

# Set
camera.BslSaturation.Value = <value>
```

### `BslSaturationRaw`

**Saturation (Raw)** &nbsp; ![Integer](https://img.shields.io/badge/type-Integer-blue) &nbsp; ![ReadWrite](https://img.shields.io/badge/access-ReadWrite-green)

Adjusting the saturation changes the colorfulness (intensity) of the colors. A higher saturation, for example, makes colors easier to distinguish.

| Property | Value |
|---|---|
| Current value | `256` |
| Range | `0` → `512` (step `1`) |

**pypylon API**

```python
# Get
value = camera.BslSaturationRaw.Value

# Set
camera.BslSaturationRaw.Value = <value>
```

### `BslBrightness`

**Brightness** &nbsp; ![Float](https://img.shields.io/badge/type-Float-blue) &nbsp; ![ReadWrite](https://img.shields.io/badge/access-ReadWrite-green)

Adjusting the brightness lightens or darkens the entire image.

| Property | Value |
|---|---|
| Current value | `0.0` |
| Range | `-1.0` → `1.0` |

**pypylon API**

```python
# Get
value = camera.BslBrightness.Value

# Set
camera.BslBrightness.Value = <value>
```

### `BslContrastMode`

**Contrast Mode** &nbsp; ![Enum](https://img.shields.io/badge/type-Enum-purple) &nbsp; ![ReadWrite](https://img.shields.io/badge/access-ReadWrite-green)

Sets the contrast mode.

| Property | Value |
|---|---|
| Current value | `N/A` |
| Options | `Linear` `SCurve` |

**pypylon API**

```python
# Get
value = camera.BslContrastMode.Value

# Set (choose one option)
camera.BslContrastMode.Value = "Linear"
camera.BslContrastMode.Value = "SCurve"
```

### `BslContrast`

**Contrast** &nbsp; ![Float](https://img.shields.io/badge/type-Float-blue) &nbsp; ![ReadWrite](https://img.shields.io/badge/access-ReadWrite-green)

Adjusting the contrast increases the difference between light and dark areas in the image.

| Property | Value |
|---|---|
| Current value | `0.0` |
| Range | `-1.0` → `1.0` |

**pypylon API**

```python
# Get
value = camera.BslContrast.Value

# Set
camera.BslContrast.Value = <value>
```

### `BslDemosaicingMode`

**Demosaicing Mode** &nbsp; ![Enum](https://img.shields.io/badge/type-Enum-purple) &nbsp; ![ReadWrite](https://img.shields.io/badge/access-ReadWrite-green)

Sets the demosaicing mode.

| Property | Value |
|---|---|
| Current value | `N/A` |
| Options | `Auto` `Manual` |

**pypylon API**

```python
# Get
value = camera.BslDemosaicingMode.Value

# Set (choose one option)
camera.BslDemosaicingMode.Value = "Auto"
camera.BslDemosaicingMode.Value = "Manual"
```

### `BslDemosaicingMethod`

**Demosaicing Method** &nbsp; ![Enum](https://img.shields.io/badge/type-Enum-purple) &nbsp; ![ReadOnly](https://img.shields.io/badge/access-ReadOnly-lightgrey)

Sets the demosaicing method.

| Property | Value |
|---|---|
| Current value | `N/A` |
| Options | `NearestNeighbor` |

**pypylon API**

```python
# Get
value = camera.BslDemosaicingMethod.Value

# Set (choose one option)
camera.BslDemosaicingMethod.Value = "NearestNeighbor"
```

### `BalanceRatioSelector`

**Balance Ratio Selector** &nbsp; ![Enum](https://img.shields.io/badge/type-Enum-purple) &nbsp; ![ReadWrite](https://img.shields.io/badge/access-ReadWrite-green)

Sets which color channel can be adjusted when performing manual white balance. All changes to the Balance Ratio parameter will be applied to the selected color channel.

| Property | Value |
|---|---|
| Current value | `N/A` |
| Options | `Red` `Green` `Blue` |

**pypylon API**

```python
# Get
value = camera.BalanceRatioSelector.Value

# Set (choose one option)
camera.BalanceRatioSelector.Value = "Red"
camera.BalanceRatioSelector.Value = "Green"
camera.BalanceRatioSelector.Value = "Blue"
```

### `BalanceRatio`

**Balance Ratio** &nbsp; ![Float](https://img.shields.io/badge/type-Float-blue) &nbsp; ![ReadWrite](https://img.shields.io/badge/access-ReadWrite-green)

Balance Ratio value to be applied to the currently selected channel.

| Property | Value |
|---|---|
| Current value | `1.0` |
| Range | `0.25` → `15.999755859375` |

**pypylon API**

```python
# Get
value = camera.BalanceRatio.Value

# Set
camera.BalanceRatio.Value = <value>
```

### `BalanceWhiteAuto`

**Balance White Auto** &nbsp; ![Enum](https://img.shields.io/badge/type-Enum-purple) &nbsp; ![ReadWrite](https://img.shields.io/badge/access-ReadWrite-green)

Sets the operation mode of the Balance White Auto auto function.

| Property | Value |
|---|---|
| Current value | `N/A` |
| Options | `Off` `Once` `Continuous` |

**pypylon API**

```python
# Get
value = camera.BalanceWhiteAuto.Value

# Set (choose one option)
camera.BalanceWhiteAuto.Value = "Off"
camera.BalanceWhiteAuto.Value = "Once"
camera.BalanceWhiteAuto.Value = "Continuous"
```

### `ColorTransformationSelector`

**Color Transformation Selector** &nbsp; ![Enum](https://img.shields.io/badge/type-Enum-purple) &nbsp; ![ReadWrite](https://img.shields.io/badge/access-ReadWrite-green)

Sets which type of color transformation will be performed.

| Property | Value |
|---|---|
| Current value | `N/A` |
| Options | `RGBtoRGB` |

**pypylon API**

```python
# Get
value = camera.ColorTransformationSelector.Value

# Set (choose one option)
camera.ColorTransformationSelector.Value = "RGBtoRGB"
```

### `ColorTransformationEnable`

**Color Transformation Enable** &nbsp; ![Boolean](https://img.shields.io/badge/type-Boolean-orange) &nbsp; ![ReadWrite](https://img.shields.io/badge/access-ReadWrite-green)

Enables color transformation.

| Property | Value |
|---|---|
| Current value | `False` |
| Options | `True` `False` |

**pypylon API**

```python
# Get
value = camera.ColorTransformationEnable.Value

# Set
camera.ColorTransformationEnable.Value = True   # or False
```

### `ColorTransformationValueSelector`

**Color Transformation Value Selector** &nbsp; ![Enum](https://img.shields.io/badge/type-Enum-purple) &nbsp; ![ReadWrite](https://img.shields.io/badge/access-ReadWrite-green)

Sets which element will be entered in the color transformation matrix. Depending on the camera model, some elements in the color transformation matrix may be preset and can't be changed.

| Property | Value |
|---|---|
| Current value | `N/A` |
| Options | `Gain00` `Gain01` `Gain02` `Gain10` `Gain11` `Gain12` `Gain20` `Gain21` `Gain22` `Offset0` `Offset1` `Offset2` |

**pypylon API**

```python
# Get
value = camera.ColorTransformationValueSelector.Value

# Set (choose one option)
camera.ColorTransformationValueSelector.Value = "Gain00"
camera.ColorTransformationValueSelector.Value = "Gain01"
camera.ColorTransformationValueSelector.Value = "Gain02"
camera.ColorTransformationValueSelector.Value = "Gain10"
camera.ColorTransformationValueSelector.Value = "Gain11"
camera.ColorTransformationValueSelector.Value = "Gain12"
camera.ColorTransformationValueSelector.Value = "Gain20"
camera.ColorTransformationValueSelector.Value = "Gain21"
camera.ColorTransformationValueSelector.Value = "Gain22"
camera.ColorTransformationValueSelector.Value = "Offset0"
camera.ColorTransformationValueSelector.Value = "Offset1"
camera.ColorTransformationValueSelector.Value = "Offset2"
```

### `ColorTransformationValue`

**Color Transformation Value** &nbsp; ![Float](https://img.shields.io/badge/type-Float-blue) &nbsp; ![ReadWrite](https://img.shields.io/badge/access-ReadWrite-green)

Transformation value for the selected element in the color transformation matrix.

| Property | Value |
|---|---|
| Current value | `1.0` |
| Range | `-4.0` → `3.99609375` |

**pypylon API**

```python
# Get
value = camera.ColorTransformationValue.Value

# Set
camera.ColorTransformationValue.Value = <value>
```

### `BslColorAdjustmentEnable`

**Color Adjustment Enable** &nbsp; ![Boolean](https://img.shields.io/badge/type-Boolean-orange) &nbsp; ![ReadWrite](https://img.shields.io/badge/access-ReadWrite-green)

Enables color adjustment.

| Property | Value |
|---|---|
| Current value | `False` |
| Options | `True` `False` |

**pypylon API**

```python
# Get
value = camera.BslColorAdjustmentEnable.Value

# Set
camera.BslColorAdjustmentEnable.Value = True   # or False
```

### `BslColorAdjustmentSelector`

**Color Adjustment Selector** &nbsp; ![Enum](https://img.shields.io/badge/type-Enum-purple) &nbsp; ![ReadWrite](https://img.shields.io/badge/access-ReadWrite-green)

Sets which color in your images will be adjusted.

| Property | Value |
|---|---|
| Current value | `N/A` |
| Options | `Red` `Yellow` `Green` `Cyan` `Blue` `Magenta` |

**pypylon API**

```python
# Get
value = camera.BslColorAdjustmentSelector.Value

# Set (choose one option)
camera.BslColorAdjustmentSelector.Value = "Red"
camera.BslColorAdjustmentSelector.Value = "Yellow"
camera.BslColorAdjustmentSelector.Value = "Green"
camera.BslColorAdjustmentSelector.Value = "Cyan"
camera.BslColorAdjustmentSelector.Value = "Blue"
camera.BslColorAdjustmentSelector.Value = "Magenta"
```

### `BslColorAdjustmentHue`

**Color Adjustment Hue** &nbsp; ![Float](https://img.shields.io/badge/type-Float-blue) &nbsp; ![ReadWrite](https://img.shields.io/badge/access-ReadWrite-green)

Hue adjustment value to be applied to the currently selected color channel.

| Property | Value |
|---|---|
| Current value | `0.0` |
| Range | `-0.8980392156862745` → `1.0` |

**pypylon API**

```python
# Get
value = camera.BslColorAdjustmentHue.Value

# Set
camera.BslColorAdjustmentHue.Value = <value>
```

### `BslColorAdjustmentSaturation`

**Color Adjustment Saturation** &nbsp; ![Float](https://img.shields.io/badge/type-Float-blue) &nbsp; ![ReadWrite](https://img.shields.io/badge/access-ReadWrite-green)

Saturation adjustment value to be applied to the currently selected color channel.

| Property | Value |
|---|---|
| Current value | `1.0` |
| Range | `0.0` → `1.87890625` |

**pypylon API**

```python
# Get
value = camera.BslColorAdjustmentSaturation.Value

# Set
camera.BslColorAdjustmentSaturation.Value = <value>
```

### `LUTSelector`

**LUT Selector** &nbsp; ![Enum](https://img.shields.io/badge/type-Enum-purple) &nbsp; ![ReadWrite](https://img.shields.io/badge/access-ReadWrite-green)

Sets the lookup table (LUT) to be configured. All changes to the LUT settings will be applied to the selected LUT.

| Property | Value |
|---|---|
| Current value | `N/A` |
| Options | `Luminance` |

**pypylon API**

```python
# Get
value = camera.LUTSelector.Value

# Set (choose one option)
camera.LUTSelector.Value = "Luminance"
```

### `LUTEnable`

**LUT Enable** &nbsp; ![Boolean](https://img.shields.io/badge/type-Boolean-orange) &nbsp; ![ReadWrite](https://img.shields.io/badge/access-ReadWrite-green)

Enables the selected lookup table (LUT).

| Property | Value |
|---|---|
| Current value | `True` |
| Options | `True` `False` |

**pypylon API**

```python
# Get
value = camera.LUTEnable.Value

# Set
camera.LUTEnable.Value = True   # or False
```

### `LUTIndex`

**LUT Index** &nbsp; ![Integer](https://img.shields.io/badge/type-Integer-blue) &nbsp; ![ReadWrite](https://img.shields.io/badge/access-ReadWrite-green)

Pixel value to be replaced with the LUT Value pixel value.

| Property | Value |
|---|---|
| Current value | `0` |
| Range | `0` → `4095` (step `1`) |

**pypylon API**

```python
# Get
value = camera.LUTIndex.Value

# Set
camera.LUTIndex.Value = <value>
```

### `LUTValue`

**LUT Value** &nbsp; ![Integer](https://img.shields.io/badge/type-Integer-blue) &nbsp; ![ReadWrite](https://img.shields.io/badge/access-ReadWrite-green)

New pixel value to replace the LUT Index pixel value.

| Property | Value |
|---|---|
| Current value | `0` |
| Range | `0` → `4095` (step `1`) |

**pypylon API**

```python
# Get
value = camera.LUTValue.Value

# Set
camera.LUTValue.Value = <value>
```

### `BslStaticDefectPixelCorrectionMaxDefects`

**Static Defect Pixel Correction Max Defects** &nbsp; ![Integer](https://img.shields.io/badge/type-Integer-blue) &nbsp; ![ReadOnly](https://img.shields.io/badge/access-ReadOnly-lightgrey)

Maximum number of defect pixels that the factory or user correction file can contain.

| Property | Value |
|---|---|
| Current value | `4096` |
| Range | `-9223372036854775808` → `9223372036854775807` (step `1`) |

**pypylon API**

```python
# Get
value = camera.BslStaticDefectPixelCorrectionMaxDefects.Value

# Set
camera.BslStaticDefectPixelCorrectionMaxDefects.Value = <value>
```

### `BslStaticDefectPixelCorrectionMode`

**Static Defect Pixel Correction Mode** &nbsp; ![Enum](https://img.shields.io/badge/type-Enum-purple) &nbsp; ![ReadWrite](https://img.shields.io/badge/access-ReadWrite-green)

Sets the static defect pixel correction mode.

| Property | Value |
|---|---|
| Current value | `N/A` |
| Options | `Factory` `User` `Off` |

**pypylon API**

```python
# Get
value = camera.BslStaticDefectPixelCorrectionMode.Value

# Set (choose one option)
camera.BslStaticDefectPixelCorrectionMode.Value = "Factory"
camera.BslStaticDefectPixelCorrectionMode.Value = "User"
camera.BslStaticDefectPixelCorrectionMode.Value = "Off"
```

### `BslStaticDefectPixelCorrectionFileStatus`

**Static Defect Pixel Correction File Status** &nbsp; ![Enum](https://img.shields.io/badge/type-Enum-purple) &nbsp; ![ReadOnly](https://img.shields.io/badge/access-ReadOnly-lightgrey)

Returns the file status of the defect pixel correction file.

| Property | Value |
|---|---|
| Current value | `N/A` |
| Options | `FileStatusUnknown` `FileOk` `FileNotFound` `FileEmpty` `InvalidHeader` `InvalidSize` `InvalidSorting` `InvalidClustering` `InvalidFileEntry` |

**pypylon API**

```python
# Get
value = camera.BslStaticDefectPixelCorrectionFileStatus.Value

# Set (choose one option)
camera.BslStaticDefectPixelCorrectionFileStatus.Value = "FileStatusUnknown"
camera.BslStaticDefectPixelCorrectionFileStatus.Value = "FileOk"
camera.BslStaticDefectPixelCorrectionFileStatus.Value = "FileNotFound"
camera.BslStaticDefectPixelCorrectionFileStatus.Value = "FileEmpty"
camera.BslStaticDefectPixelCorrectionFileStatus.Value = "InvalidHeader"
camera.BslStaticDefectPixelCorrectionFileStatus.Value = "InvalidSize"
camera.BslStaticDefectPixelCorrectionFileStatus.Value = "InvalidSorting"
camera.BslStaticDefectPixelCorrectionFileStatus.Value = "InvalidClustering"
camera.BslStaticDefectPixelCorrectionFileStatus.Value = "InvalidFileEntry"
```

### `BslStaticDefectPixelCorrectionReload`

**Static Defect Pixel Correction Reload** &nbsp; ![Command](https://img.shields.io/badge/type-Command-red) &nbsp; ![ReadWrite](https://img.shields.io/badge/access-ReadWrite-green)

Reloads the user defect pixel correction file. This command must be executed if the user defect pixel correction file has been uploaded for the first time or has been updated.

| Property | Value |
|---|---|
| Current value | `(executable command)` |

**pypylon API**

```python
camera.BslStaticDefectPixelCorrectionReload.Execute()
```
