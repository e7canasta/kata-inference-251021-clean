# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## Running the Application

```bash
# Main inference pipeline
python -m adeline

# Control CLI (send MQTT commands)
python -m adeline.control.cli pause
python -m adeline.control.cli resume
python -m adeline.control.cli stop
python -m adeline.control.cli toggle_crop    # Only if ROI mode = adaptive
python -m adeline.control.cli stabilization_stats

# MQTT data monitors
python -m adeline.data.monitors data      # Detections monitor
python -m adeline.data.monitors status    # Status monitor
```

**Entry point:** `__main__.py` → `app/controller.py:main()`

---

## Project Overview

**Adeline** is a real-time computer vision inference pipeline (YOLO-based) with MQTT remote control capabilities. Designed for edge deployment with configurable ROI strategies and detection stabilization.

**Core Philosophy:** **"Complejidad por Diseño"** - Attack complexity through architecture, not complicated code.

**Current Version:** v2.0 (post-refactoring FASES 1-7)
**Architecture Score:** 8.5/10 (see `ANALISIS_ARQUITECTURA_GABY.md` for detailed assessment)

---

## Big Picture: System Architecture

### Control/Data Plane Separation ⭐

**The most important architectural decision** - separates reliability from performance.

```
┌──────────────────┐              ┌──────────────────┐
│  Control Plane   │              │   Data Plane     │
│  (QoS 1 - ACK)   │              │  (QoS 0 - fast)  │
└────────┬─────────┘              └────────┬─────────┘
         │                                  │
         ├─ Commands (~1 msg/min)          ├─ Detections (~120 msg/min @ 2fps)
         ├─ STOP/PAUSE/RESUME              ├─ Inference results
         ├─ TOGGLE_CROP                    ├─ ROI metrics
         └─ CommandRegistry                └─ Pipeline metrics
              ↓                                  ↓
         ┌─────────────────────────────────────────┐
         │      InferencePipelineController        │
         │      (Orchestration + Lifecycle)        │
         └──────────────┬──────────────────────────┘
                        │
         ┌──────────────┴──────────────┐
         │      PipelineBuilder        │
         │  (Construction via Factories)│
         └──────────────┬──────────────┘
                        │
         ┌──────────────┴──────────────┐
         │     InferencePipeline       │
         │  ┌─────────────────────┐    │
         │  │ BaseInferenceHandler │   │
         │  │  ├─ Adaptive         │   │
         │  │  ├─ Fixed            │   │
         │  │  └─ Standard         │   │
         │  └─────────────────────┘    │
         │                              │
         │  ┌─────────────────────┐    │
         │  │ Multi-Sink           │   │
         │  │  ├─ MQTT (stabilized)│   │
         │  │  ├─ Visualization    │   │
         │  │  └─ ROI Update       │   │
         │  └─────────────────────┘    │
         └──────────────────────────────┘
```

**Why this works:**
- Control must be reliable (STOP command can't be lost) → QoS 1
- Data must be performant (inference @ 2fps, 120+ msgs/min) → QoS 0
- **Graceful degradation:** If Data Plane saturates, Control still works
- **Independent scaling:** Can optimize each plane separately

**Reference:** `control/plane.py`, `data/plane.py`

---

## Key Design Patterns

### 1. Factory Pattern (Strategy Creation)

All strategies (ROI, Stabilization, Handlers) are created through factories with centralized validation.

```python
# inference/factories/handler_factory.py
handler, roi_state = InferenceHandlerFactory.create(config)
# Returns: StandardHandler | AdaptiveHandler | FixedHandler

# inference/factories/strategy_factory.py
stabilizer = StrategyFactory.create_stabilization_strategy(config)
# Returns: NoOpStabilizer | TemporalHysteresisStabilizer
```

**Benefit:** Easy to extend (add new strategy without modifying existing code)

**Reference:** `inference/factories/`, `roi/base.py`

---

### 2. Builder Pattern (Pipeline Construction)

Separates construction complexity from orchestration logic.

```python
# app/builder.py
builder = PipelineBuilder(config)

# Builder orchestrates factories
handler, roi_state = builder.build_inference_handler()  # → Factory
sinks = builder.build_sinks(...)                        # → Factory
if stabilization_enabled:
    sinks = builder.wrap_sinks_with_stabilization(...)  # → Decorator

pipeline = builder.build_pipeline(...)
```

**Benefit:** Controller only orchestrates lifecycle, doesn't construct components

**Reference:** `app/builder.py`, `app/controller.py`

---

### 3. Command Registry Pattern (Control Plane)

Explicit command registration - only available commands are registered.

```python
# control/registry.py
registry = CommandRegistry()

# Basic commands (always available)
registry.register('pause', handler, "Pausa el procesamiento")
registry.register('stop', handler, "Detiene el pipeline")

# Conditional commands
if handler.supports_toggle:
    registry.register('toggle_crop', handler, "Toggle ROI")

# Validation
try:
    registry.execute('unknown_command')
except CommandNotAvailableError:
    # Clear error message with available commands
```

**Benefit:** Commands are discoverable, validated, and explicit (no silent failures)

**Reference:** `control/registry.py`, `control/plane.py`

---

### 4. Publisher Pattern (Data Plane)

Separates MQTT infrastructure from business logic (message formatting).

```python
# data/plane.py (infrastructure)
class MQTTDataPlane:
    def __init__(self):
        self.detection_publisher = DetectionPublisher()  # Business logic
        self.metrics_publisher = MetricsPublisher()

    def publish_inference(self, predictions, video_frame):
        message = self.detection_publisher.format_message(...)  # Delegate
        self.client.publish(topic, json.dumps(message))  # Infrastructure
```

**Benefit:** Easy to change message format without touching MQTT code

**Reference:** `data/plane.py`, `data/publishers/`

---

### 5. InferenceLoader Pattern (Initialization Order Enforcement)

Guarantees models are disabled BEFORE importing `inference` module (prevents warnings).

```python
# inference/loader.py - Enforces initialization order BY DESIGN
from ..inference.loader import InferenceLoader
inference = InferenceLoader.get_inference()  # Auto-disables models first
InferencePipeline = inference.InferencePipeline
```

**Before (fragile):** Manual `disable_models_from_config()` call - easy to forget
**After (enforced):** Loader guarantees order - can't import without disabling

**Reference:** `inference/loader.py`

---

## ROI Strategy System

Three modes (config-driven):

### 1. `none` - Standard Pipeline
- No ROI, full frame inference
- Uses `InferencePipeline.init()` (model_id based)
- Handler: `StandardInferenceHandler`

### 2. `adaptive` - Dynamic ROI
- ROI adjusts based on detections
- Uses `InferencePipeline.init_with_custom_logic()`
- Handler: `AdaptiveInferenceHandler`
- **Performance optimization:**
  - ROI is always **square** (no distortion)
  - Size in **multiples of imgsz** (clean resize: 640→320 = 2x)
  - NumPy views for zero-copy crop
  - Vectorized coordinate transforms (~20x faster than loops)
- **Toggle support:** `{"command": "toggle_crop"}` via MQTT

### 3. `fixed` - Static ROI
- Fixed region defined by normalized coordinates
- Uses `InferencePipeline.init_with_custom_logic()`
- Handler: `FixedROIInferenceHandler`
- **No toggle support** (immutable)

**Configuration:**
```yaml
roi_strategy:
  mode: adaptive  # none | adaptive | fixed
  adaptive:
    margin: 0.2
    smoothing: 0.3
    min_roi_multiple: 1
    max_roi_multiple: 4
```

**Reference:** `inference/roi/`, `inference/factories/handler_factory.py`

---

## Detection Stabilization

Reduces flickering/false positives by requiring temporal consistency.

### Modes

**1. `none`** - No filtering (baseline)
**2. `temporal`** - Temporal + Hysteresis filtering

**Strategy (temporal mode):**
```
Frame 1: person 0.45 → IGNORE (< 0.5 appear_threshold)
Frame 2: person 0.52 → TRACKING (frames=1/3)
Frame 3: person 0.48 → TRACKING (>= 0.3 persist_threshold, frames=2/3)
Frame 4: person 0.51 → CONFIRMED! Emit detection
Frame 5: (no detection) → GAP 1/2 (tolerate)
Frame 6: (no detection) → REMOVED (gap > max_gap)
```

**Hysteresis:**
- **High threshold to appear** (0.5) - strict for new detections
- **Low threshold to persist** (0.3) - relaxed for confirmed tracks
- Reduces flicker without losing tracking

**Configuration:**
```yaml
detection_stabilization:
  mode: temporal
  temporal:
    min_frames: 3
    max_gap: 2
  hysteresis:
    appear_confidence: 0.5
    persist_confidence: 0.3
```

**⚠️ Known Limitation:** Simple matching (by class only, no IoU)
- Works well for single-object scenarios
- May confuse tracks with multiple objects of same class
- **Improvement planned:** IoU matching (see `PLAN_MEJORAS.md`)

**Reference:** `inference/stabilization/core.py`

---

## Configuration System

**Hierarchy:**
- Sensitive data (API keys, MQTT creds) → `.env` file
- Application settings → `config/adeline/config.yaml`
- Models disabled → `models_disabled.disabled` array in config

**Loading:**
```python
# config.py
config = PipelineConfig()  # Loads YAML + .env

# CRITICAL: Model disabling happens in InferenceLoader (automatic)
# You don't need to call disable_models_from_config() manually
```

**Reference:** `config.py`, `inference/loader.py`

---

## Extension Points

### Add New ROI Strategy

1. Create handler in `inference/roi/`
2. Inherit from `BaseInferenceHandler` (ABC)
3. Add case in `InferenceHandlerFactory.create()`
4. Add config schema in `config.yaml`

### Add New MQTT Command

1. Create handler method in `controller.py`
2. Register in `_setup_control_callbacks()`:
   ```python
   registry.register('my_command', self._handle_my_command, "Description")
   ```
3. Command auto-validated by `CommandRegistry`

### Add New Sink

1. Create sink function: `def my_sink(predictions, video_frames)`
2. Add to `SinkFactory.create_sinks()`
3. Configure in `config.yaml` if needed

### Add New Stabilization Strategy

1. Inherit from `BaseDetectionStabilizer`
2. Implement `process()`, `reset()`, `get_stats()`
3. Add case in `StrategyFactory.create_stabilization_strategy()`
4. Add config schema

**Reference:** `ANALISIS_ARQUITECTURA_GABY.md` (section 5 - Extension examples)

---

## Performance Optimizations

### NumPy Vectorization
```python
# adaptive.py - ~20x faster than Python loops
xs = np.array([d['x'] for d in detections])
xyxy[:, 0] = xs - ws / 2  # Vectorized operation
```

### Zero-Copy Crop
```python
# adaptive.py - NumPy view, no memory copy
cropped = video_frame.image[roi.y1:roi.y2, roi.x1:roi.x2]
```

### ROI Square Multiples
```python
# adaptive.py - Clean resize (640→320 = 2x, no weird interpolation)
square_size = rounded_multiple * imgsz  # Always multiple of model size
```

**Reference:** `inference/roi/adaptive.py`

---

## Testing Strategy

**Current approach:** Manual testing in pair-programming style + Field testing

**Philosophy:**
- Focus on design to manage complexity (not extensive testing)
- Compilation checks: `python -m py_compile <file>`
- Manual integration testing for critical paths
- Peer review approach

**Testing Documents:**
- `TEST_CASES_FUNCIONALES.md` - Field testing scripts for actors (12 scenarios)
  - Focus: Multi-object tracking in shared rooms (2-4 residents)
  - Format: Production-style scripts for real-world validation
  - Critical: TC-006 (2 people), TC-009 (4 people) - Fall detection accuracy

**Planned improvements** (see `PLAN_MEJORAS.md`):
- Property-based tests for invariants (ROI square, expand preserves shape)
- Critical path tests (MQTT commands, pipeline lifecycle)
- Incremental, not blocking feature development

---

## Git Workflow

**Commits:**
```
feat: Description

Co-Authored-By: Gaby <noreply@visiona.com>
```

**Notes:**
- Author: Ernesto
- Co-author: Gaby (AI assistant name, not "Claude")
- No "Generated with Claude Code" message needed

---

## Architecture Analysis & Roadmap

**Current State (v2.0):**
- Score: 8.5/10
- 7 refactoring phases completed
- Solid SOLID principles application
- Production-ready Control/Data plane separation

**See detailed analysis:**
- `ANALISIS_ARQUITECTURA_GABY.md` - Deep architecture analysis
- `PLAN_MEJORAS.md` - Prioritized improvement plan

**Next Steps (v2.1):**
1. IoU matching for multi-object tracking (2-3 days)
2. Property-based tests (1-2 days)
3. Pydantic config validation (3-4 days)
4. Type hints + mypy CI (1 week)

---

## Common Gotchas

### 1. Import Order (SOLVED)
**Before:** Had to manually call `disable_models_from_config()` before importing inference
**Now:** `InferenceLoader` handles this automatically - just use it

### 2. ROI Must Be Square
Adaptive ROI enforces square shape (performance optimization, no distortion)
```python
assert roi.is_square  # Always true after make_square_multiple()
```

### 3. MQTT QoS Difference
- Control commands: QoS 1 (reliable, ACK)
- Data messages: QoS 0 (fast, fire-and-forget)
- **Don't change QoS** without understanding trade-offs

### 4. Stabilization Matching
Current implementation: Simple matching by class (no spatial awareness)
- Works: 1-2 objects of same class
- Issues: 5+ objects of same class (tracks may swap)
- Fix planned: IoU matching (see `PLAN_MEJORAS.md`)

---

## Key Files to Understand

**Core Architecture:**
- `app/controller.py` - Orchestration & lifecycle
- `app/builder.py` - Construction via factories
- `control/plane.py` + `control/registry.py` - Control pattern
- `data/plane.py` + `data/publishers/` - Data pattern

**ROI System:**
- `inference/roi/base.py` - Factory & validation
- `inference/roi/adaptive.py` - Dynamic ROI (804 lines, well-structured)
- `inference/handlers/base.py` - Handler ABC

**Stabilization:**
- `inference/stabilization/core.py` - Temporal + Hysteresis

**Initialization:**
- `inference/loader.py` - Enforced model disabling
- `config.py` - Config loading

---

## Design Principles (Complejidad por Diseño)

1. **Separation of Concerns**
   - Infrastructure (MQTT) ≠ Business Logic (Publishers)
   - Orchestration (Controller) ≠ Construction (Builder)

2. **Configuration-Driven**
   - Behavior changes via config, not code
   - Easy A/B testing, environment-specific configs

3. **Factory Pattern for Variability**
   - Add strategies without modifying existing code
   - Open/Closed Principle

4. **Explicit Contracts (ABC)**
   - Type safety via abstract base classes
   - Clear interfaces, refactoring confidence

5. **Design Enforcement > Discipline**
   - InferenceLoader enforces init order (can't forget)
   - CommandRegistry enforces explicit registration
   - ABC enforces handler interface

---

## Documentation

- `CLAUDE.md` (this file) - Development guide
- `ANALISIS_ARQUITECTURA_GABY.md` - Architecture analysis (8.5/10 score)
- `PLAN_MEJORAS.md` - Improvement roadmap
- Parent `../CLAUDE.md` - Project-level principles

---

**Score:** 8.5/10 (well-designed, production-ready with identified improvements)
