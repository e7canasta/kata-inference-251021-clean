# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Adeline is a computer vision inference pipeline for **fall detection in geriatric residences**. The system processes RTSP video streams using YOLO models to detect persons and their postures, supporting **1-4 residents per room** with multi-object tracking capabilities.

**Core Philosophy: "Complejidad por diseño, no por accidente"** - Complexity is managed through architectural boundaries and intentional design patterns, not complicated code.

## Key Commands

### Running the System

```bash
# Run the pipeline
python -m adeline

# The system uses config/adeline/config.yaml by default
```

### Testing

```bash
# Run all tests
pytest

# Run tests by category
pytest -m unit              # Fast unit tests only
pytest -m integration       # Integration tests
pytest -m roi               # ROI-related tests
pytest -m mqtt              # MQTT command tests
pytest -m stabilization     # Stabilization logic tests

# Run specific test file
pytest tests/test_roi.py
pytest tests/test_mqtt_commands.py
pytest tests/test_stabilization.py

# Verbose output
pytest -v

# With coverage
pytest --cov=adeline --cov-report=term-missing
```

**Testing Philosophy**: Property-based tests focus on invariants and critical paths, not 100% coverage. Manual pair programming testing is still used for integration scenarios (see TEST_CASES_FUNCIONALES.md).

### Type Checking

```bash
# Type check entire codebase
mypy . --config-file mypy.ini

# Type check specific file
mypy adeline/config/schemas.py
mypy adeline/control/registry.py

# Detailed output
mypy . --config-file mypy.ini --show-error-context
```

**Type Checking Approach**: Gradual typing with full strictness on critical modules (schemas.py, registry.py) and moderate strictness elsewhere. See mypy.ini for per-module configuration.

### Validation Script

```bash
# Full validation (mypy + pytest + config validation)
./scripts/validate.sh

# Fast mode (unit tests only)
./scripts/validate.sh --fast
```

### Development

```bash
# Manual compilation check (as per pair programming approach)
python -m py_compile adeline/inference/roi/adaptive.py
python -m py_compile adeline/inference/stabilization/core.py
```

## Architecture Overview

### Dual-Plane MQTT Architecture

The system separates control from data using two independent MQTT planes:

- **Control Plane** (QoS 1): Reliable command delivery (pause/resume/stop)
  - Topic: `inference/control/commands`
  - Implementation: `control/plane.py` + `control/registry.py`

- **Data Plane** (QoS 0): High-throughput data publishing (detections, metrics)
  - Topics: `inference/data/detections`, `inference/data/metrics`
  - Implementation: `data/plane.py` + `data/publishers.py`

### Core Components

```
app/
  ├── controller.py      # InferencePipelineController - Main orchestrator
  ├── builder.py         # PipelineBuilder - Component construction
  └── factories/         # SinkFactory for output sinks
      └── sink_factory.py

control/
  ├── plane.py          # MQTTControlPlane - Command handling
  └── registry.py       # CommandRegistry - Explicit command registration

data/
  ├── plane.py          # MQTTDataPlane - Result publishing
  └── publishers.py     # DetectionPublisher, MetricsPublisher

inference/
  ├── pipeline.py       # InferencePipeline - Video processing loop
  ├── handlers/         # InferenceHandler variants (Standard, Adaptive, Fixed ROI)
  ├── roi/              # ROI strategies (adaptive, fixed)
  ├── stabilization/    # Detection stabilization (temporal hysteresis, IoU matching)
  └── factories/        # InferenceHandlerFactory, StrategyFactory

config/
  └── schemas.py        # Pydantic v2 schemas - Type-safe configuration
```

### Key Design Patterns

1. **Builder Pattern**: `PipelineBuilder` constructs all components, separating construction from orchestration
2. **Factory Pattern**: Three factories (HandlerFactory, SinkFactory, StrategyFactory) create components based on configuration
3. **Strategy Pattern**: ROI modes (none/adaptive/fixed) and stabilization strategies selected at build time
4. **Registry Pattern**: `CommandRegistry` requires explicit command registration (no optional callbacks)

### Separation of Concerns

**Critical Design Rule**: Components have single responsibilities:

- `InferencePipelineController`: Lifecycle management, signal handling - **never constructs components**
- `PipelineBuilder`: Component construction - **never manages lifecycle**
- Factories: Component creation - **never orchestrate or manage lifecycle**
- Handlers: Processing logic - separated from state objects (ROIState, FixedROIState)

## Configuration System

**Location**: `config/adeline/config.yaml`

**Schema**: `config/schemas.py` (Pydantic v2)

**Philosophy**: Fail-fast at load time, not runtime. Invalid configuration prevents startup entirely.

### Key Configuration Sections

```yaml
pipeline:
  rtsp_url: "rtsp://127.0.0.1:8554/live"
  max_fps: 2

models:
  imgsz: 320              # Must be multiple of 32 (validated)
  confidence: 0.25
  iou_threshold: 0.45

mqtt:
  broker:
    host: "localhost"
    port: 1883
  control:
    qos: 1                # Reliable delivery for commands
  data:
    qos: 0                # Best-effort for detections

roi:
  mode: "adaptive"        # Options: "none" | "adaptive" | "fixed"
  adaptive:
    min_roi_multiple: 320
    max_roi_multiple: 640

stabilization:
  mode: "spatial_iou"     # Options: "none" | "spatial_iou"
  hysteresis:
    appear_confidence: 0.5
    persist_confidence: 0.25  # Must be <= appear_confidence (validated)
  temporal:
    min_frames: 3
    max_gap: 5
```

### Critical Validation Rules

- `imgsz % 32 == 0` (YOLO requirement)
- `persist_confidence <= appear_confidence` (hysteresis constraint)
- Fixed ROI requires `x_min < x_max`, `y_min < y_max`
- Adaptive ROI requires `min_roi_multiple <= max_roi_multiple`

## ROI Strategies

### No ROI (`roi.mode: "none"`)
- Full frame inference
- Handler: `StandardInferenceHandler`

### Adaptive ROI (`roi.mode: "adaptive"`)
- Dynamic expansion around detections
- Square ROI constraints (sides are multiples of `imgsz`)
- Zero-copy NumPy views for cropping
- Handler: `AdaptiveInferenceHandler`
- Coordinate transformation: ROI → Frame coordinates
- See: `inference/roi/adaptive.py`

### Fixed ROI (`roi.mode: "fixed"`)
- Static crop region defined in config
- Handler: `FixedROIInferenceHandler`
- See: `inference/handlers/fixed_roi_inference_handler.py`

**Performance Note**: Square ROI constraints eliminate unnecessary resizing operations and simplify coordinate transformations.

## Detection Stabilization

**Location**: `inference/stabilization/`

### Temporal Hysteresis Stabilizer

**Pattern**: Dual-threshold hysteresis + temporal tracking

**Key Concepts**:
- **Appear Confidence**: Higher threshold for new detections (default: 0.5)
- **Persist Confidence**: Lower threshold for tracked objects (default: 0.25)
- **Min Frames**: Consecutive frames required to confirm track (default: 3)
- **Max Gap**: Frames without detection before track expires (default: 5)
- **IoU Matching**: Spatial overlap for multi-object association

**Invariants Tested**:
- IoU(A, B) == IoU(B, A) (symmetry)
- IoU(A, A) == 1.0 (identity)
- IoU with no overlap == 0.0
- Requires `min_frames` consecutive detections
- Tolerates `max_gap` frames without detection

## MQTT Commands

**Control Topic**: `inference/control/commands`

### Available Commands

Commands are **explicitly registered** in `CommandRegistry`. Availability depends on system capabilities:

| Command | Always Available | Conditional Registration |
|---------|------------------|--------------------------|
| `pause` | ✓ | - |
| `resume` | ✓ | - |
| `stop` | ✓ | - |
| `status` | ✓ | - |
| `toggle_crop` | - | Only if `handler.supports_toggle == True` |
| `stabilization_stats` | - | Only if `stabilizer is not None` |

**Critical Invariant**: `STOP` command **must** activate `shutdown_event` (tested in `test_mqtt_commands.py`).

### Command Format

```json
{
  "command": "pause",
  "timestamp": "2025-10-23T12:00:00Z"
}
```

## Development Guidelines

### Adding New Components

1. **New Inference Handler**: Add to `InferenceHandlerFactory` in `inference/factories/handler_factory.py`
2. **New Output Sink**: Add to `SinkFactory` in `app/factories/sink_factory.py` with explicit priority
3. **New Stabilization Strategy**: Add to `StrategyFactory` in `inference/factories/strategy_factory.py`
4. **New MQTT Command**: Register in `InferencePipelineController._setup_control_callbacks()`

### Invariants to Maintain

**ROI Invariants**:
- `make_square_multiple()` → always returns square box
- `expand(preserve_square=True)` → maintains square property
- `expand()` → never exceeds frame bounds
- Square sides are multiples of `imgsz`

**Stabilization Invariants**:
- IoU calculation is symmetric
- Confidence filtering respects appear/persist thresholds
- Temporal tracking requires consecutive frames
- Multi-object tracking distinguishes objects via IoU

**Configuration Invariants**:
- Config validation happens at load time (fail-fast)
- Invalid config prevents startup
- No runtime config changes (requires restart)

### Performance Considerations

- **Zero-Copy Operations**: ROI cropping uses NumPy views (`frame[y_min:y_max, x_min:x_max]`)
- **QoS Tuning**: Control (QoS 1) vs Data (QoS 0) separation
- **Lazy Loading**: `InferenceLoader` ensures model downloads are disabled before imports
- **Vectorized Operations**: Coordinate transformations use NumPy operations

### When to Use Factories vs Direct Construction

**Use Factories when**:
- Component type depends on configuration (`roi.mode`, `stabilization.mode`)
- Multiple implementations of same interface
- Construction logic is complex

**Direct construction when**:
- Single implementation
- Simple object creation
- No configuration-driven selection

## Common Workflows

### Adding a New ROI Strategy

1. Create new handler class inheriting `BaseInferenceHandler`
2. Implement `infer()` and `supports_toggle` property
3. Add to `InferenceHandlerFactory.create()` with new mode string
4. Update `ROIStrategySettings` in `config/schemas.py` with new mode literal
5. Add property-based tests for invariants in `tests/test_roi.py`

### Adding a New MQTT Command

1. Implement handler method in `InferencePipelineController` (e.g., `_handle_my_command()`)
2. Register in `_setup_control_callbacks()` using `registry.register()`
3. Optionally: Make registration conditional based on capabilities
4. Add tests in `tests/test_mqtt_commands.py` for command execution
5. Update this CLAUDE.md with new command documentation

### Debugging Pipeline Issues

1. Check logs in `log.json` (structured JSON logging)
2. Verify config validation: `python -c "from adeline.config.schemas import AdelineConfig; AdelineConfig.from_yaml('config/adeline/config.yaml')"`
3. Test individual components via unit tests
4. Use `stabilization_stats` command to inspect stabilizer state
5. Enable visualization (`enable_visualization: true`) to see detections visually

## Important Notes

### Commit Conventions

- Co-author commits with: `Co-Authored-By: Gaby <noreply@anthropic.com>`
- **Do not** use "Generated with Claude Code" footer
- Use "Gaby de Visiona" as the pair programming partner name

### Testing Philosophy

- Property-based tests focus on **invariants**, not implementation
- Manual pair programming testing complements automated tests
- Testing markers: `@pytest.mark.unit`, `@pytest.mark.integration`, `@pytest.mark.roi`, etc.
- Compilation checks are part of the testing workflow (not automated tests)

### Design Principles

1. **Complejidad por diseño, no por accidente**: Attack complexity through architecture
2. **Fail-fast**: Validate at load time, not runtime
3. **Explicit over implicit**: No optional callbacks, explicit registration
4. **Zero-copy where possible**: Use NumPy views, avoid unnecessary copies
5. **Separation of concerns**: Clear boundaries between orchestration, construction, and execution

## References

- **Comprehensive Documentation**: `docs/wiki/` (Markdown files with architecture details)
- **Functional Test Cases**: `TEST_CASES_FUNCIONALES.md` (Field testing scenarios)
- **Test Suite README**: `tests/README.md` (Detailed testing guide)
- **Testing Philosophy**: Focus on invariants, critical paths, and edge cases
