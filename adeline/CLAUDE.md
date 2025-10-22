# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the Application

```bash
# Run main inference pipeline
python -m adeline

# Run control CLI (send MQTT commands)
python -m adeline.control.cli <command>
# Commands: pause, resume, stop, status, toggle_crop

# Run MQTT monitors
python -m adeline.data.monitors           # data monitor (default)
python -m adeline.data.monitors data      # data monitor
python -m adeline.data.monitors status    # status monitor
```

## Architecture Overview

Adeline is a **computer vision inference pipeline** (YOLO) with MQTT remote control, organized using a **control/data plane separation pattern**.

### Core Components

**Control Plane** (`control/plane.py`):
- MQTT QoS 1 (reliable delivery)
- Receives commands: pause/resume/stop/status/toggle_crop/stabilization_stats
- Publishes status updates
- Controls pipeline lifecycle

**Data Plane** (`data/plane.py`):
- MQTT QoS 0 (fire-and-forget for performance)
- Publishes inference results (detections)
- Publishes metrics from watchdog
- Optional full frame publishing

**Pipeline Controller** (`app/controller.py`):
- Orchestrates control plane, data plane, and InferencePipeline
- Manages signal handling (SIGINT/SIGTERM)
- Coordinates visualization sinks and MQTT sinks using `multi_sink` pattern

### Configuration System (`config.py`)

**Critical initialization order**:
1. `disable_models_from_config()` is called BEFORE importing `inference` module
2. This prevents `ModelDependencyMissing` warnings for unused heavy models
3. Config is loaded from `config/adeline/config.yaml` and `.env`

**Configuration hierarchy**:
- Sensitive data (API keys, MQTT credentials) → `.env` file
- Application settings → `config.yaml`
- Models disabled via `models_disabled.disabled` array in config

### Inference Pipeline Features

**ROI Strategy** (`inference/roi/`):
- Factory pattern: `none`, `adaptive`, `fixed`
- **Adaptive ROI** (`adaptive.py`): Dynamic crop based on previous detections with temporal smoothing
- **Fixed ROI** (`fixed.py`): Static region of interest
- Toggle via MQTT command `toggle_crop` (only if ROI enabled)

**Detection Stabilization** (`inference/stabilization/core.py`):
- Factory pattern for stabilization strategies
- **Temporal + Hysteresis**: Requires N consecutive frames to confirm detection
- Reduces flickering with small/fast models
- High threshold to appear (e.g., 0.5), low threshold to persist (e.g., 0.3)
- Stats available via MQTT command `stabilization_stats`

**Model Management** (`inference/models.py`):
- Supports both Roboflow API models and local ONNX models
- Local models: set `models.use_local: true` in config

### Module Organization

```
adeline/
├── app/              # Main pipeline controller
├── control/          # Control plane (MQTT QoS 1)
│   ├── plane.py      # MQTTControlPlane class
│   └── cli.py        # CLI for sending commands
├── data/             # Data plane (MQTT QoS 0)
│   ├── plane.py      # MQTTDataPlane class
│   ├── sinks.py      # MQTT sink factory
│   └── monitors/     # Standalone MQTT monitors
├── inference/        # Inference logic
│   ├── roi/          # ROI strategies (adaptive/fixed)
│   ├── stabilization/# Detection stabilization
│   └── models.py     # Model configuration
├── visualization/    # OpenCV visualization sinks
└── config.py         # Configuration loading
```

## Design Principles

**Complexity by Design** (per CLAUDE.md in parent):
- Factory patterns for ROI and stabilization strategies
- Separation of concerns: control vs data plane
- Configuration-driven behavior (avoid hardcoded logic)

**MQTT QoS Strategy**:
- Control plane: QoS 1 (reliable, command delivery is critical)
- Data plane: QoS 0 (performance, some data loss acceptable)

**Model Loading**:
- Heavy models are disabled by default to avoid memory issues
- Explicit opt-in via config (`models_disabled.disabled` list)
- `disable_models_from_config()` MUST run before importing `inference`

## Common Patterns

**Multi-sink pattern** (from `inference` library):
```python
from inference.core.interfaces.stream.sinks import multi_sink

pipeline.on_prediction = multi_sink(
    create_mqtt_sink(...),
    create_visualization_sink(...)
)
```

**Factory pattern for strategies**:
- `create_roi_strategy()` in `inference/roi/__init__.py`
- `create_stabilization_strategy()` in `inference/stabilization/core.py`

**MQTT command format**:
```json
{"command": "pause|resume|stop|status|toggle_crop|stabilization_stats"}
```

## Configuration Files

- `config/adeline/config.yaml` - Main configuration
- `.env` - Sensitive credentials (ROBOFLOW_API_KEY, MQTT credentials)
- Both are excluded from git (see gitignore)

## Entry Points

- `python -m adeline` → `__main__.py` → `app.main()`
- `python -m adeline.control.cli` → `control/cli.py`
- `python -m adeline.data.monitors` → `data/monitors/__main__.py`
