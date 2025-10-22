# CLAUDE.md

This file provides guidance for **hybrid teams** (AI Agents + Engineers) working with Adeline.

**Purpose:** Enable both AI agents (Claude Code, etc.) and human engineers to quickly understand the **Big Picture** and design patterns.

---

## Running the Application

```bash
# Run main inference pipeline
python -m adeline

# Run control CLI (send MQTT commands)
python -m adeline.control.cli <command>
# Commands: pause, resume, stop, status, metrics, toggle_crop, stabilization_stats

# Run MQTT monitors
python -m adeline.data.monitors           # data monitor (default)
python -m adeline.data.monitors data      # data monitor
python -m adeline.data.monitors status    # status monitor
```

---

## Big Picture: Architecture Overview

Adeline is a **computer vision inference pipeline** (YOLO) with MQTT remote control.

**Core Design Principle:** **Complejidad por Diseño** (Complexity by Design)
- Attack complexity through architecture, not complicated code
- Separation of concerns enforced by design
- Explicit patterns over implicit conventions

### Control/Data Plane Separation

```
Control Plane (QoS 1)          Data Plane (QoS 0)
     ↓                               ↓
  Commands                       Detections
  Reliable                       Performance
     ↓                               ↓
         Pipeline Controller
                ↓
         InferencePipeline
```

**Why separate planes?**
- Different guarantees: Control must be reliable, Data must be fast
- Independent failure: Data saturation doesn't affect Control
- QoS optimization: Control (QoS 1 = ACK), Data (QoS 0 = fire-and-forget)

### Post-Refactoring Architecture (v2.0)

```
┌─────────────────────────────────────────────────┐
│        InferencePipelineController              │
│    Responsibility: Orchestration + Lifecycle    │
└────────────┬────────────────────────────────────┘
             │
             ├──> PipelineBuilder
             │    └─> Orchestrates factories
             │        ├─> InferenceHandlerFactory
             │        ├─> SinkFactory
             │        └─> StrategyFactory
             │
             ├──> ControlPlane (QoS 1)
             │    └─> CommandRegistry (explicit commands)
             │
             ├──> DataPlane (QoS 0)
             │    ├─> DetectionPublisher (formats detections)
             │    └─> MetricsPublisher (formats metrics)
             │
             └──> InferencePipeline
                  ├─> BaseInferenceHandler (ABC)
                  │   ├─> AdaptiveHandler
                  │   ├─> FixedHandler
                  │   └─> StandardHandler
                  │
                  └─> Sinks (multi_sink)
                      ├─> MQTT
                      ├─> Visualization
                      └─> ROI Update
```

**Key Changes (Refactoring FASES 1-7):**
- ✅ Builder pattern separates construction from orchestration
- ✅ Factory pattern for all strategies
- ✅ CommandRegistry for explicit command validation
- ✅ Publisher pattern separates business logic from infrastructure
- ✅ InferenceLoader enforces initialization order by design
- ✅ ABC contracts for handlers

See `CONSULTORIA_DISEÑO.md` for detailed design analysis.

---

## Key Design Patterns (Complejidad por Diseño)

### 1. Builder Pattern (FASE 3)

**Problem:** Controller was a God Object (560 lines, too many responsibilities)

**Solution:** PipelineBuilder orchestrates factories

```python
# app/builder.py
class PipelineBuilder:
    def build_inference_handler(self, config):
        # Delegates to InferenceHandlerFactory
        return InferenceHandlerFactory.create(config)

    def build_sinks(self, data_plane, roi_state, handler):
        # Delegates to SinkFactory
        return SinkFactory.create_sinks(...)

    def build_pipeline(self, handler, sinks, watchdog):
        # Builds InferencePipeline (standard or custom logic)
        return InferencePipeline.init(...)

# Controller only orchestrates
class InferencePipelineController:
    def setup(self):
        handler, roi_state = self.builder.build_inference_handler()
        sinks = self.builder.build_sinks(data_plane, roi_state, handler)
        self.pipeline = self.builder.build_pipeline(handler, sinks, watchdog)
```

**Benefit:** SRP - Controller orchestrates, Builder constructs, Factories specialize

### 2. CommandRegistry Pattern (FASE 5)

**Problem:** Optional callbacks, unclear which commands available

**Solution:** Explicit command registration

```python
# control/registry.py
class CommandRegistry:
    def register(self, command: str, handler: Callable, description: str):
        self._commands[command] = handler

    def execute(self, command: str):
        if command not in self._commands:
            raise CommandNotAvailableError(...)
        return self._commands[command]()

    @property
    def available_commands(self) -> Set[str]:
        return set(self._commands.keys())

# Controller registers commands explicitly
registry = control_plane.command_registry
registry.register('pause', self._handle_pause, "Pausa el procesamiento")
registry.register('stop', self._handle_stop, "Detiene el pipeline")

# Conditional commands (only if supported)
if handler.supports_toggle:
    registry.register('toggle_crop', self._handle_toggle_crop, "Toggle ROI")
```

**Benefit:** Commands are discoverable, validated, and explicit

### 3. Publisher Pattern (FASE 6)

**Problem:** DataPlane knew business logic (detection structure, metrics format)

**Solution:** Separate infrastructure (MQTT) from business logic (formatting)

```python
# data/publishers/detection.py
class DetectionPublisher:
    def format_message(self, predictions, video_frame) -> Dict:
        # Business logic: knows detection structure
        return {
            "detections": [...],
            "roi_metrics": {...},
            "timestamp": ...
        }

# data/publishers/metrics.py
class MetricsPublisher:
    def format_message(self) -> Dict:
        # Business logic: knows metrics structure
        return {
            "throughput_fps": ...,
            "latency_reports": [...]
        }

# data/plane.py
class MQTTDataPlane:
    def __init__(self):
        self.detection_publisher = DetectionPublisher()  # Business logic
        self.metrics_publisher = MetricsPublisher()      # Business logic

    def publish_inference(self, predictions, video_frame):
        message = self.detection_publisher.format_message(...)  # Delegate
        self.client.publish(self.data_topic, json.dumps(message))  # Infrastructure
```

**Benefit:** MQTTDataPlane is pure infrastructure (MQTT channel), Publishers are pure business logic

Same pattern as Control Plane (FASE 5):
- ControlPlane = MQTT infrastructure
- CommandRegistry = business logic (which commands)
- DataPlane = MQTT infrastructure
- Publishers = business logic (message format)

### 4. InferenceLoader Pattern (FASE 7)

**Problem:** Import order was fragile (disable_models must be BEFORE import inference)

**Solution:** Lazy loading with enforced initialization order

```python
# inference/loader.py
class InferenceLoader:
    _inference_module = None
    _models_disabled = False

    @classmethod
    def get_inference(cls):
        if cls._inference_module is None:
            # 1. Disable models FIRST (enforced)
            if not cls._models_disabled:
                cls.disable_models_from_config()

            # 2. NOW import inference
            import inference
            cls._inference_module = inference

        return cls._inference_module

# Usage (order doesn't matter anymore)
from ..inference.loader import InferenceLoader
inference = InferenceLoader.get_inference()  # Automatic disable
InferencePipeline = inference.InferencePipeline
```

**Before (fragile):**
```python
# ❌ Manual, fragile, refactor-unsafe
from ..config import disable_models_from_config
disable_models_from_config()  # MUST be before import
from inference import InferencePipeline
```

**After (enforced):**
```python
# ✅ Automatic, enforced, refactor-safe
from ..inference.loader import InferenceLoader
inference = InferenceLoader.get_inference()
```

**Benefit:** Design enforcement, not discipline

### 5. Factory Pattern (Original Design)

**Already excellent in original design:**

```python
# ROI Strategy Factory
roi_state = validate_and_create_roi_strategy(
    mode=config.ROI_MODE,  # "none" | "adaptive" | "fixed"
    config=roi_config,
)

# Stabilization Strategy Factory
stabilizer = create_stabilization_strategy(stab_config)
```

**Why it works:**
- Easy to add new strategies (extend, not modify)
- Config-driven (behavior change without code change)
- Validation centralized in factory

### 6. Multi-Sink Composition (Original Design)

**Functional composition pattern:**

```python
from inference.core.interfaces.stream.sinks import multi_sink

pipeline.on_prediction = multi_sink(
    mqtt_sink,           # Publish MQTT
    roi_update_sink,     # Update ROI state
    visualization_sink,  # OpenCV display
)
```

**Why it works:**
- No pipeline modification (open/closed principle)
- Add/remove sinks without touching core logic
- Each sink is independent (SRP)

---

## Module Organization (Post-Refactoring)

```
adeline/
├── app/                    # Main pipeline controller
│   ├── controller.py       # InferencePipelineController (orchestration)
│   ├── builder.py          # PipelineBuilder (construction)
│   └── factories/          # Factories for app components
│       └── sink_factory.py # SinkFactory
│
├── control/                # Control plane (MQTT QoS 1)
│   ├── plane.py            # MQTTControlPlane (infrastructure)
│   ├── registry.py         # CommandRegistry (business logic)
│   └── cli.py              # CLI for sending commands
│
├── data/                   # Data plane (MQTT QoS 0)
│   ├── plane.py            # MQTTDataPlane (infrastructure)
│   ├── publishers/         # Publishers (business logic)
│   │   ├── detection.py    # DetectionPublisher
│   │   └── metrics.py      # MetricsPublisher
│   ├── sinks.py            # MQTT sink factory
│   └── monitors/           # Standalone MQTT monitors
│
├── inference/              # Inference logic
│   ├── loader.py           # InferenceLoader (enforced init order)
│   ├── handlers/           # Inference handlers
│   │   ├── base.py         # BaseInferenceHandler (ABC)
│   │   ├── standard.py     # StandardInferenceHandler
│   │   └── (adaptive/fixed in roi/)
│   ├── factories/          # Inference factories
│   │   ├── handler_factory.py  # InferenceHandlerFactory
│   │   └── strategy_factory.py # StrategyFactory
│   ├── roi/                # ROI strategies (adaptive/fixed)
│   ├── stabilization/      # Detection stabilization
│   └── models.py           # Model configuration
│
├── visualization/          # OpenCV visualization sinks
└── config.py               # Configuration loading
```

**Key additions from refactoring:**
- `app/builder.py` - Construction logic
- `app/factories/` - App-level factories
- `control/registry.py` - Command registry
- `data/publishers/` - Message formatting
- `inference/loader.py` - Enforced initialization
- `inference/handlers/base.py` - ABC contract
- `inference/factories/` - Inference factories

---

## Configuration System

**Critical:** InferenceLoader handles initialization order automatically

**Before (manual):**
```python
# controller.py - FRAGILE
from ..config import disable_models_from_config
disable_models_from_config()  # Must be BEFORE import
from inference import InferencePipeline
```

**After (automatic):**
```python
# controller.py - ENFORCED
from ..inference.loader import InferenceLoader
inference = InferenceLoader.get_inference()  # Auto-disables models
```

**Configuration hierarchy:**
- Sensitive data (API keys, MQTT credentials) → `.env` file
- Application settings → `config/adeline/config.yaml`
- Models disabled via `models_disabled.disabled` array in config

---

## Inference Pipeline Features

### ROI Strategy (Factory Pattern)

**Modes:** `none`, `adaptive`, `fixed`

```yaml
# config.yaml
roi_strategy:
  mode: adaptive
  adaptive:
    margin: 0.2
    smoothing: 0.3
```

**Implementations:**
- **StandardInferenceHandler** (`none`): No ROI, standard pipeline
- **AdaptiveInferenceHandler** (`adaptive`): Dynamic crop based on detections
- **FixedROIInferenceHandler** (`fixed`): Static region of interest

**Toggle via MQTT:** `{"command": "toggle_crop"}` (only if handler.supports_toggle)

### Detection Stabilization (Factory Pattern)

**Modes:** `none`, `temporal`

```yaml
detection_stabilization:
  mode: temporal
  temporal:
    confirm_frames: 3
    remove_frames: 5
```

**How it works:**
- Temporal + Hysteresis filtering
- Requires N consecutive frames to confirm detection
- Reduces flickering with small/fast models
- High threshold to appear, low threshold to persist

**Stats via MQTT:** `{"command": "stabilization_stats"}`

### Model Management

```yaml
models:
  use_local: false  # true = local ONNX, false = Roboflow API

models_disabled:
  disabled:
    - yolov8x-1280
    - sam
    # Heavy models disabled by default
```

---

## Design Principles (Complejidad por Diseño)

### 1. Separation of Concerns

**Infrastructure vs Business Logic:**
- MQTTControlPlane (infrastructure) + CommandRegistry (business logic)
- MQTTDataPlane (infrastructure) + Publishers (business logic)
- Controller (orchestration) + Builder (construction)

### 2. Factory Patterns for Variability

**Strategy selection via config:**
```python
roi_mode = "none" | "adaptive" | "fixed"
strategy = InferenceHandlerFactory.create(config)
```

**Benefit:** Add new strategies without modifying existing code

### 3. Configuration-Driven Behavior

**All business logic in config, not hardcoded:**
```yaml
roi_strategy:
  mode: adaptive
  adaptive:
    margin: 0.2
```

**Benefit:** Change behavior without recompiling

### 4. Explicit Contracts (ABC)

**BaseInferenceHandler enforces interface:**
```python
class BaseInferenceHandler(ABC):
    @abstractmethod
    def __call__(self, video_frames): pass

    @property
    @abstractmethod
    def enabled(self) -> bool: pass

    @property
    def supports_toggle(self) -> bool:
        return False
```

**Benefit:** Type safety, clear contracts, refactoring confidence

### 5. Design Enforcement (not discipline)

**Examples:**
- InferenceLoader enforces initialization order
- CommandRegistry enforces explicit command registration
- ABC enforces handler interface
- Builder enforces separation of construction

**Principle:** If it can be enforced by design, don't rely on comments/discipline

---

## MQTT QoS Strategy

**Why different QoS for Control vs Data?**

| Plane | QoS | Why? |
|-------|-----|------|
| Control | 1 | Commands are critical (STOP must arrive) |
| Data | 0 | Performance critical, data loss acceptable |

**Impact:**
- Control: Reliable (ACK), low frequency (~1 msg/min)
- Data: Fire-and-forget, high frequency (~120 msg/min at 2 FPS)

**Benefit:** System degrades gracefully
- If broker saturates: data lost, but control still works
- STOP command always arrives (QoS 1)

---

## Common Patterns

### MQTT Command Format

```json
{"command": "pause|resume|stop|status|metrics|toggle_crop|stabilization_stats"}
```

### Multi-Sink Pattern

```python
from inference.core.interfaces.stream.sinks import multi_sink

pipeline.on_prediction = multi_sink(
    create_mqtt_sink(...),
    create_visualization_sink(...),
    roi_update_sink(...)
)
```

### Factory Pattern

```python
# ROI Strategy
from inference.factories import InferenceHandlerFactory
handler, roi_state = InferenceHandlerFactory.create(config)

# Stabilization
from inference.factories import StrategyFactory
stabilizer = StrategyFactory.create_stabilization_strategy(config)
```

---

## For AI Agents (Claude Code, etc.)

**When working on this codebase:**

1. **Read DESIGN.md first** for design principles
2. **Read CONSULTORIA_DISEÑO.md** for architecture analysis (pre/post refactoring)
3. **Understand the Big Picture** before modifying code
4. **Follow patterns:**
   - Factory for strategies
   - Builder for construction
   - Registry for explicit command sets
   - Publisher for business logic separation
5. **Always enforce by design:**
   - If initialization order matters → use loader
   - If commands need validation → use registry
   - If interface matters → use ABC
6. **Testing approach:**
   - Testing is done manually in pair-programming style (peer review approach)
   - Compilation verification: `python -m py_compile <file>`
   - Focus on design to manage complexity rather than extensive automated testing
7. **Git commits:**
   - Use "Gaby" as co-author name (from Visiona team), not "Claude"
   - Author is Ernesto
   - Format:
     ```
     feat: Description

     🤖 Generated with [Claude Code](https://claude.com/claude-code)

     Co-Authored-By: Gaby <noreply@visiona.com>
     ```

**Key files to understand architecture:**
- `app/controller.py` - Orchestration
- `app/builder.py` - Construction
- `control/plane.py` + `control/registry.py` - Control pattern
- `data/plane.py` + `data/publishers/` - Data pattern
- `inference/loader.py` - Initialization enforcement

---

## For Engineers (Humans)

**Extending the system:**

1. **Add new ROI strategy:**
   - Create handler in `inference/roi/`
   - Inherit from `BaseInferenceHandler`
   - Add case in `InferenceHandlerFactory.create()`
   - Add config schema in `config.yaml`

2. **Add new MQTT command:**
   - Create handler method in `controller.py`
   - Register in `_setup_control_callbacks()`
   - Command auto-validated by CommandRegistry

3. **Add new sink:**
   - Create sink function (signature: `def sink(predictions, video_frames)`)
   - Add to `SinkFactory.create_sinks()`
   - Configure in `config.yaml` if needed

4. **Add new stabilization strategy:**
   - Inherit from `BaseDetectionStabilizer`
   - Add case in `StrategyFactory.create_stabilization_strategy()`
   - Add config schema

**Design principles to follow:**
- Complexity by design (not complicated code)
- Separation of concerns (infrastructure vs business logic)
- Configuration-driven (avoid hardcoding)
- Explicit over implicit (registry, ABC)

---

## Configuration Files

- `config/adeline/config.yaml` - Main configuration
- `.env` - Sensitive credentials (ROBOFLOW_API_KEY, MQTT credentials)
- Both excluded from git

---

## Entry Points

- `python -m adeline` → `__main__.py` → `app.main()`
- `python -m adeline.control.cli` → `control/cli.py`
- `python -m adeline.data.monitors` → `data/monitors/__main__.py`

---

## Refactoring History

**Completed refactoring (FASES 1-7):**

| Fase | What | Benefit |
|------|------|---------|
| 1 | BaseInferenceHandler ABC | Explicit contracts |
| 2 | Factories (Handler, Sink, Strategy) | Centralized creation |
| 3 | PipelineBuilder | Construction separated from orchestration |
| 4 | Controller refactored | -109 lines, SRP enforced |
| 5 | CommandRegistry (Control Plane) | Explicit command validation |
| 6 | Publisher pattern (Data Plane) | Business logic separated |
| 7 | InferenceLoader + cleanup fixes | Enforced initialization, proper cleanup |

**Result:** Design score improved from 7.5/10 to 9.0/10

See `CONSULTORIA_DISEÑO.md` section 9 for detailed post-refactoring analysis.

---

## Documentation

- **CLAUDE.md** (this file) - Quick start for hybrid teams
- **DESIGN.md** - Design principles ("Complejidad por Diseño")
- **CONSULTORIA_DISEÑO.md** - Deep design analysis (pre/post refactoring)
- **PLAN_REFACTORING.md** - Refactoring plan (COMPLETED)

**Principle:** Documentation for both AI agents and human engineers
