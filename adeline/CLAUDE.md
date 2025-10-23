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

### Structured Logging (JSON)

**Design Philosophy**: Solo JSON, queryable en producción

**Setup** (adeline/logging.py):
```python
from adeline.logging import setup_logging

# Desarrollo (pretty-print)
setup_logging(level="DEBUG", indent=2)

# Producción (compact JSON)
setup_logging(level="INFO", indent=None)
```

**Trace Correlation** - Seguir comando MQTT → acciones del pipeline:
```python
from adeline.logging import trace_context, get_trace_id

# Propagar trace_id en toda la call stack
with trace_context(f"cmd-pause-{uuid}"):
    process_command()
    logger.info("Pipeline pausado", extra={"trace_id": get_trace_id()})
```

**Helper Functions** (casos comunes):
```python
from adeline.logging import (
    log_mqtt_command,         # Control plane commands
    log_pipeline_metrics,     # FPS, latency
    log_stabilization_stats,  # Multi-object tracking
    log_error_with_context    # Errores con contexto completo
)

log_mqtt_command(logger, command="pause", topic="inference/control/commands")
log_pipeline_metrics(logger, fps=30.5, latency_ms=15.2)
log_stabilization_stats(logger, raw_count=12, stabilized_count=8, active_tracks=3)
log_error_with_context(logger, "Error conectando", exception=e, component="data_plane",
                       broker_host="localhost", broker_port=1883)
```

**Output Format**:
```json
{
  "timestamp": "2025-10-22T16:30:45.123Z",
  "level": "INFO",
  "logger": "adeline.control.plane",
  "message": "📥 Comando recibido: pause",
  "component": "control_plane",
  "command": "pause",
  "mqtt_topic": "inference/control/commands",
  "trace_id": "cmd-pause-abc123"
}
```

**Query Examples**:
```bash
# Trace comando específico
jq 'select(.trace_id == "cmd-pause-abc123")' logs.json

# Errores de componente
jq 'select(.level == "ERROR" and .component == "control_plane")' logs.json

# FPS promedio
jq -s 'map(select(.metrics.fps)) | map(.metrics.fps) | add/length' logs.json
```

**Configuration** (config/adeline/config.yaml):
```yaml
logging:
  level: INFO
  json_indent: null  # null=compact (producción), 2=pretty (desarrollo)
  paho_level: WARNING

  # File rotation (opcional - si null, logs van a stdout)
  file: null  # Ej: "logs/adeline.log" para habilitar file logging
  max_bytes: 10485760  # 10 MB
  backup_count: 5  # Mantener 5 backups (50 MB total)

  # Producción:
  # file: "/var/log/adeline/adeline.log"
  # max_bytes: 10485760  # 10 MB
  # backup_count: 7  # 70 MB total
```

**File Rotation**:
- **Built-in** (Python RotatingFileHandler): Configurar `file` en config.yaml
  - Archivos rotados: `adeline.log`, `adeline.log.1`, `adeline.log.2`, ...
  - Rotación automática cuando `adeline.log` alcanza `max_bytes`
  - Mantiene `backup_count` archivos históricos

- **Alternativa** (logrotate - Linux): Usar `config/logrotate.d/adeline`
  - Instalación: `sudo cp config/logrotate.d/adeline /etc/logrotate.d/adeline`
  - Testing: `sudo logrotate -d /etc/logrotate.d/adeline`
  - Cron diario automático vía `/etc/cron.daily/logrotate`
  - Soporte para compresión gzip, dateformat, retention policies

**Migration Status**:

| Fase   | Módulos                                                                                            | Logs      | Status |
|--------|----------------------------------------------------------------------------------------------------|-----------|--------|
| Fase 3 | control/plane.py, data/plane.py, inference/stabilization/core.py, app/controller.py                | ~60       | ✅      |
| Fase 4 | app/builder.py, app/sinks/registry.py, control/registry.py, inference/factories/handler_factory.py | 21        | ✅      |
| Fase 5 | inference/models.py, inference/loader.py, inference/roi/adaptive/state.py, factories               | 24        | ✅      |
| Fase 6 | legacy_config.py, inference/roi/base.py, inference/roi/fixed.py, adaptive/pipeline.py, matching.py, publishers/metrics.py | 21 | ✅ |
| **Total** | **19 módulos críticos**                                                                             | **~126 logs** | ✅  |

**Status**: Migración completa de logs estructurados JSON. Sistema 100% queryable en producción.

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
Co-Authored-By: Gaby <noreply@visiona.com>
```

Do NOT include "Generated with [Claude Code]" footer (already explicit via Co-Authored-By).
- La wiki está viva y documentando la complejidad por diseño de Adeline. 🎸✨