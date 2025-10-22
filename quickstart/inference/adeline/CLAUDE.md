# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a computer vision inference project built on the Roboflow `inference` library. It implements real-time object detection pipelines with YOLO models, RTSP video streaming via go2rtc, and MQTT-based control and data planes.

## Development Commands

### Environment Setup
```bash
# Install dependencies (using uv package manager)
uv sync

# Activate virtual environment (recommended for long-running processes)
source .venv/bin/activate

# Or run scripts directly with uv (for quick one-off commands)
uv run python <script.py>
```

**Note**: For long-running processes like `run_pipeline_mqtt.py`, it's recommended to activate the venv first instead of using `uv run`, as this ensures signal handling (Ctrl+C) works correctly.

### Running Inference Pipelines

**Basic pipeline with visualization:**
```bash
python quickstart/inference/run_pipeline.py
```

**Pipeline with MQTT control and data publishing:**
```bash
python quickstart/inference/run_pipeline_mqtt.py
```
*Note: Pipeline auto-starts on launch. Use MQTT commands to control (pause/resume/stop).*

**Pipeline with performance watchdog metrics:**
```bash
python quickstart/inference/run_pipeline_with_watchdog.py
```

**Note**: These are long-running processes. Make sure your venv is activated, or use `uv run` for testing but be aware signal handling may require `kill -9` on the Python subprocess.

### MQTT Control

**Control the pipeline remotely:**
```bash
python -m quickstart.inference.mqtt_control_cli {pause|resume|stop|status}
python -m quickstart.inference.mqtt_control_cli pause --broker localhost
```
*Note: No 'start' command - pipeline auto-starts when you run run_pipeline_mqtt.py*

**Monitor inference data:**
```bash
python quickstart/inference/mqtt_data_monitor.py --verbose
```

**Monitor pipeline status:**
```bash
python quickstart/inference/mqtt_status_monitor.py
```

### RTSP Streaming

The project uses go2rtc as an RTSP proxy. Configuration is in `go2rtc.yaml`:
- RTSP server: `rtsp://127.0.0.1:8554/live`
- API endpoint: `:1984`
- Source stream: `rtsp://admin:ddnakmin4@192.168.2.64:554/Streaming/Channels/102`

## Architecture

### Inference Pipeline Configuration

All pipeline scripts disable unused inference models via environment variables to reduce dependencies and startup time. This is done at the top of each script:

```python
os.environ["PALIGEMMA_ENABLED"] = "False"
os.environ["FLORENCE2_ENABLED"] = "False"
# ... etc
```

When creating new pipeline scripts, copy this block from existing scripts.

### MQTT Architecture (Control + Data Planes)

**Control Plane** (`MQTTControlPlane`):
- Receives commands via MQTT to control running pipeline (pause/resume/stop)
- Pipeline auto-starts on launch, no START command needed
- Default topic: `inference/control/commands`
- Status updates published to: `inference/control/status`
- Implements callbacks: `on_stop`, `on_pause`, `on_resume`

**Data Plane** (`MQTTDataPlane`):
- Publishes inference results (detections) via MQTT
- Default topic: `inference/data/detections`
- Used as a sink function in InferencePipeline via `create_mqtt_sink()`
- Publishes JSON with: detections, frame info, timestamp, message_id

**Key Pattern**: Combine both planes using `multi_sink()` with `functools.partial` to enable both MQTT publishing and local visualization:
```python
from functools import partial
on_prediction = partial(multi_sink, sinks=[mqtt_sink, render_boxes])
```

### InferencePipeline Monitoring

**Status Updates**:
- Implement `status_update_handler(status: StatusUpdate)` to receive pipeline events
- Filter by severity: `UpdateSeverity.{DEBUG, INFO, WARNING, ERROR}`
- Register via: `status_update_handlers=[handler_fn]`

**Performance Metrics** (Watchdog):
- Extend `BasePipelineWatchDog` for custom metrics collection
- Provides: throughput (FPS), frame decoding latency, inference latency, E2E latency
- Access via: `watchdog.get_report()`
- Register via: `watchdog=custom_watchdog`

### Configuration

**Common Pipeline Parameters**:
- `api_key`: Roboflow API key (currently: `5RumS6P9422UwlsBx5VL`)
- `rtsp_url`: Video source (default: `rtsp://127.0.0.1:8554/live`)
- `model_id`: YOLO model (default: `yolov11n-640`)
- `max_fps`: Frame rate limit (default: `2`)

**MQTT Configuration** (in `PipelineConfig`):
- Broker: `localhost:1883`
- Control topics: `inference/control/{commands,status}`
- Data topic: `inference/data/detections`

## File Structure

- `main.py`: Placeholder entry point
- `quickstart/inference/`: Inference pipeline examples
  - `run_pipeline.py`: Basic pipeline with status monitoring
  - `run_pipeline_mqtt.py`: Full MQTT-controlled pipeline
  - `run_pipeline_with_watchdog.py`: Pipeline with performance metrics
  - `mqtt_bridge.py`: MQTT control and data plane implementations
  - `mqtt_control_cli.py`: CLI for sending control commands
  - `mqtt_data_monitor.py`: CLI for monitoring detection data
- `quickstart/workflows/time_in_zone/`: Custom workflow example (placeholder)
- `go2rtc.yaml`: RTSP proxy configuration

## Key Dependencies

- `inference`: Roboflow inference SDK for running ML models
- `ultralytics`: YOLO model implementation
- `supervision`: Computer vision utilities
- `paho-mqtt`: MQTT client for control and data planes

## Notes

- All scripts expect go2rtc to be running and serving RTSP on port 8554
- MQTT broker (e.g., Mosquitto) must be running on localhost:1883 for MQTT features
- The project uses Python 3.12+
- Testing approach: Manual testing with pair-programming verification (not automated unit tests)
