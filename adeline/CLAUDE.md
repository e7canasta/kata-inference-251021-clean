# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Adeline** - Computer vision inference pipeline (YOLO) with MQTT remote control for fall detection in geriatric residences. Supports multi-person tracking (1-4 residents per room) with adaptive ROI and detection stabilization.

## Development Commands

### Running the Application
```bash
# Run main pipeline
python -m adeline

# Entry point expects config at: config/adeline/config.yaml
```

### Testing
```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_roi.py

# Run tests by marker
pytest -m unit          # Fast, isolated tests
pytest -m integration   # May require external resources
pytest -m roi           # ROI-related tests
pytest -m mqtt          # MQTT-related tests
pytest -m stabilization # Stabilization tests

# Skip slow tests
pytest -m "not slow"
```

### Type Checking
```bash
# Run mypy type checking
mypy .

# Critical files have strict typing enabled (see mypy.ini):
# - config/schemas.py (full type coverage)
# - inference/roi/adaptive.py
# - inference/stabilization/core.py
# - control/registry.py
```

### Validation
```bash
# Syntax validation (before commits)
./scripts/validate.sh
```

## Architecture Overview

### Design Philosophy
- **Complejidad por diseño, no por accidente** - Attack complexity through architecture, not complicated code
- **Fail Fast** - Pydantic validation at load time, not runtime
- **Registry Pattern** - Explicit command registration (no optional callbacks)
- **Builder Pattern** - Separation of construction from orchestration
- **Strategy Pattern** - ROI modes (none/fixed/adaptive), Stabilization modes (none/spatial_iou)

### Core Architecture (Separation of Concerns)

```
┌─────────────────────────────────────────────────────────┐
│ app/controller.py - InferencePipelineController         │
│ Orchestration & Lifecycle Management                    │
│ (Setup, start/stop/pause/resume, signal handling)       │
└────────────┬────────────────────────────────────────────┘
             │ delegates construction to
             ▼
┌─────────────────────────────────────────────────────────┐
│ app/builder.py - PipelineBuilder                        │
│ Builder Pattern - Constructs all components             │
│ (Orchestrates factories, builds sinks, wraps stability) │
└────────────┬────────────────────────────────────────────┘
             │ uses
             ▼
┌─────────────────────────────────────────────────────────┐
│ Factories (Strategy Pattern)                            │
│ - inference/factories/handler_factory.py                │
│ - inference/factories/strategy_factory.py               │
│ - app/factories/sink_factory.py                         │
└─────────────────────────────────────────────────────────┘
```

### MQTT Architecture (Dual Plane)

**Control Plane** (control/plane.py - QoS 1):
- Receives commands to control pipeline (pause/resume/stop/status/metrics)
- Uses `CommandRegistry` for explicit command registration
- Commands are registered conditionally based on capabilities:
  - `toggle_crop` only if handler.supports_toggle
  - `stabilization_stats` only if STABILIZATION_MODE != 'none'

**Data Plane** (data/sinks.py - QoS 0):
- Publishes inference results via MQTT
- Low latency, best-effort delivery

### Inference Handler Architecture

**Strategy Pattern for ROI Modes** (app/controller.py:130):
```python
# Factory creates handler based on config.ROI_MODE
handler, roi_state = builder.build_inference_handler()
# Returns: StandardInferenceHandler or subclass
#   - ROI_MODE='none': No ROI
#   - ROI_MODE='fixed': FixedROIHandler with static crop
#   - ROI_MODE='adaptive': AdaptiveROIHandler with dynamic tracking
```

**Handler Capabilities** (inference/handlers/base.py):
- `supports_toggle`: Whether handler supports enable/disable dynamically
- Used for conditional MQTT command registration

### Detection Stabilization (v2.1)

**IoU-based Multi-Object Tracking** (inference/stabilization/core.py):
- Tracks 2-4 persons using IoU spatial matching
- `STABILIZATION_MODE='spatial_iou'`: IoU matching + temporal consistency
- `STABILIZATION_MODE='none'`: Direct detections (no tracking)
- Prevents track ID confusion when people enter/exit frame
- Config: `STABILIZATION_IOU_THRESHOLD` (default 0.3)

### Configuration System

**Pydantic v2 Validation** (config/schemas.py):
- Type-safe configuration with load-time validation (fail fast)
- `AdelineConfig.from_yaml()` validates config on load
- Backward compatibility via `to_legacy_config()`
- Strict validation on critical modules (see mypy.ini)

### Lazy Loading Pattern

**Inference Disable Strategy** (inference/loader.py):
- `InferenceLoader.get_inference()` ensures `disable_models_from_config()` runs BEFORE importing inference
- Prevents unnecessary model downloads
- Enforced by design (not by comments)

## Key Design Patterns in Use

1. **CommandRegistry** (control/registry.py): Explicit command registration, no optional callbacks
2. **Builder Pattern** (app/builder.py): Separates construction logic from controller
3. **Strategy Pattern** (inference/factories): ROI modes, stabilization strategies
4. **Factory Pattern** (inference/factories): Creates handlers/strategies based on config
5. **Sink Pattern** (data/sinks.py): Pipeline output handlers (MQTT, visualization)

## Testing Strategy

Manual testing with actors for field validation (see TEST_CASES_FUNCIONALES.md):
- Multi-person tracking scenarios (1-4 people)
- Track stability across occlusions and crossings
- IoU matching validation in shared rooms

120+ unit/integration tests across 7 test files covering:
- ROI strategies (adaptive, fixed)
- MQTT commands (pause/resume/stop/toggle_crop)
- Config validation (Pydantic)
- Multi-object tracking
- Pipeline lifecycle
- Stabilization logic

## Important Configuration Files

- `config/adeline/config.yaml` - Main configuration (Pydantic validated)
- `pytest.ini` - Test markers and configuration
- `mypy.ini` - Type checking with gradual typing approach
- `.env` - Environment variables (MQTT credentials, etc.)

## Git Commits

Commits should be co-authored:
```
Co-Authored-By: Gaby <noreply@anthropic.com>
```

Do NOT include "Generated with [Claude Code]" footer (already explicit via Co-Authored-By).
