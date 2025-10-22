# Development Guide

Relevant source files

- [README.md](https://github.com/care-foundation/kata-inference-251021-clean2/blob/9a713ffb/README.md)
- [adeline/DESIGN.md](https://github.com/care-foundation/kata-inference-251021-clean2/blob/9a713ffb/adeline/DESIGN.md)
- [adeline/__init__.py](https://github.com/care-foundation/kata-inference-251021-clean2/blob/9a713ffb/adeline/__init__.py)

## Purpose and Scope

This guide is for developers who want to contribute to or extend the Adeline inference system. It covers the development environment setup, code organization principles, core design patterns, and development workflows.

For specific topics:

- Module structure details: see [Module Organization](https://deepwiki.com/care-foundation/kata-inference-251021-clean2/8.1-module-organization)
- Entry point implementations: see [Entry Points](https://deepwiki.com/care-foundation/kata-inference-251021-clean2/8.2-entry-points)
- Adding new strategies: see [Extending with New Strategies](https://deepwiki.com/care-foundation/kata-inference-251021-clean2/8.3-extending-with-new-strategies)
- Testing methodology: see [Testing Approach](https://deepwiki.com/care-foundation/kata-inference-251021-clean2/8.4-testing-approach)

For operational usage of the system, see [Operations Guide](https://deepwiki.com/care-foundation/kata-inference-251021-clean2/7-operations-guide). For architectural concepts, see [System Architecture](https://deepwiki.com/care-foundation/kata-inference-251021-clean2/3-system-architecture).

---

## Prerequisites

Before contributing to the Adeline system, you should have:

- **Python 3.11+** installed
- **uv** package manager for dependency management
- **Docker** and **Docker Compose** for infrastructure services
- Familiarity with:
    - MQTT messaging patterns
    - Object detection and computer vision concepts
    - YOLO models and inference pipelines
    - Configuration-driven architecture

**Sources:** [README.md55-63](https://github.com/care-foundation/kata-inference-251021-clean2/blob/9a713ffb/README.md#L55-L63)

---

## Development Environment Setup

### Initial Setup

```
# 1. Install dependencies
make install

# 2. Start infrastructure services
make services-up

# 3. Copy configuration templates
cp config/adeline/config.yaml.example config/adeline/config.yaml
cp .env.example .env

# 4. Edit configuration as needed
# - Set API_KEY in .env if using Roboflow models
# - Configure RTSP URLs in config.yaml
# - Set disabled models if needed
```

### Verification

```
# Test that imports work correctly
make test-imports

# Run the pipeline
make run

# In another terminal, test control commands
make pause
make status
make resume
```

**Sources:** [README.md55-89](https://github.com/care-foundation/kata-inference-251021-clean2/blob/9a713ffb/README.md#L55-L89) [Makefile](https://github.com/care-foundation/kata-inference-251021-clean2/blob/9a713ffb/Makefile)

---

## Project Structure and Organization

The Adeline system follows a modular package structure with clear separation of concerns:

### Package Structure

### Responsibility Mapping

|Directory|Purpose|Key Files|
|---|---|---|
|`adeline/app/`|Application orchestration and lifecycle management|`controller.py` (InferencePipelineController)|
|`adeline/control/`|Control plane (QoS 1) - reliable command handling|`plane.py` (MQTTControlPlane), `cli.py`|
|`adeline/data/`|Data plane (QoS 0) - high-throughput data publishing|`plane.py` (MQTTDataPlane), `sinks.py`|
|`adeline/inference/`|Machine learning logic, ROI, stabilization|`models.py`, `roi/`, `stabilization/`|
|`adeline/visualization/`|Display and debugging sinks|`sinks.py`|
|`config/adeline/`|User-editable configuration files|`config.yaml`, `go2rtc.yaml`|
|`docker/adeline/`|Infrastructure service definitions|`docker-compose.mqtt.yml`|
|`docs/adeline/`|Module-specific documentation|`DESIGN.md`, `README.md`|

**Sources:** [README.md6-52](https://github.com/care-foundation/kata-inference-251021-clean2/blob/9a713ffb/README.md#L6-L52) [adeline/__init__.py1-44](https://github.com/care-foundation/kata-inference-251021-clean2/blob/9a713ffb/adeline/__init__.py#L1-L44)

---

## Core Design Principles

The Adeline system follows a **complexity by design** philosophy, where complexity is managed through architectural patterns rather than complicated code.

### Design Diagram

### Pattern Implementations

#### 1. Control/Data Plane Separation

The system maintains strict separation between control operations (reliable, QoS 1) and data flow (high-throughput, QoS 0):

- **Control Plane** [adeline/control/plane.py](https://github.com/care-foundation/kata-inference-251021-clean2/blob/9a713ffb/adeline/control/plane.py): Handles commands like `pause`, `resume`, `stop`, `status`
- **Data Plane** [adeline/data/plane.py](https://github.com/care-foundation/kata-inference-251021-clean2/blob/9a713ffb/adeline/data/plane.py): Publishes detection results, metrics, frames

This separation prevents data traffic from impacting control latency.

#### 2. Factory Pattern for Extensibility

New strategies can be added without modifying existing code:

```
# ROI Strategy selection (inference/roi/__init__.py)
def create_roi_strategy(config):
    if mode == "none": return NoneROIStrategy()
    elif mode == "adaptive": return AdaptiveROIStrategy(...)
    elif mode == "fixed": return FixedROIStrategy(...)
```

#### 3. Configuration-Driven Behavior

All behavior is controlled by `config.yaml` rather than hardcoded values:

```
roi_strategy:
  mode: adaptive  # Change behavior without recompilation
  adaptive:
    margin: 0.2
    smoothing: 0.3
```

#### 4. Explicit Initialization Order

The system enforces critical initialization order to prevent import side effects:

```
# adeline/__main__.py or adeline/app/controller.py
disable_models_from_config()  # MUST call first
from inference import InferencePipeline  # NOW safe to import
```

This pattern is documented in [adeline/DESIGN.md52-61](https://github.com/care-foundation/kata-inference-251021-clean2/blob/9a713ffb/adeline/DESIGN.md#L52-L61)

#### 5. Multi-Sink Composition

Output destinations are composed functionally, enabling multiple consumers:

```
# From app/controller.py
pipeline.on_prediction = multi_sink(
    create_mqtt_sink(data_plane),
    create_visualization_sink(config),
    # Add more sinks without modifying pipeline
)
```

**Sources:** [adeline/DESIGN.md1-116](https://github.com/care-foundation/kata-inference-251021-clean2/blob/9a713ffb/adeline/DESIGN.md#L1-L116) [adeline/__init__.py27-44](https://github.com/care-foundation/kata-inference-251021-clean2/blob/9a713ffb/adeline/__init__.py#L27-L44)

---

## Development Workflow

### Standard Development Cycle

### Step-by-Step Workflow

1. **Make Changes**
    
    ```
    # Edit source files in adeline/
    vim adeline/inference/roi/adaptive.py
    ```
    
2. **Verify Imports**
    
    ```
    make test-imports
    ```
    
3. **Start Infrastructure**
    
    ```
    make services-up
    ```
    
4. **Run System**
    
    ```
    make run
    # Pipeline starts automatically with auto_start: true in config
    ```
    
5. **Test Manually**
    
    ```
    # In another terminal
    make pause      # Test pause functionality
    make status     # Verify status reporting
    make resume     # Test resume functionality
    make metrics    # Check metrics collection
    ```
    
6. **Monitor Output**
    
    ```
    # Watch detection data
    make monitor-data
    
    # Watch status updates
    make monitor-status
    ```
    
7. **Verify Behavior**
    
    - Check terminal output for expected behavior
    - Verify MQTT messages are correct
    - Confirm stabilization/ROI strategies work as expected
8. **Stop System**
    
    ```
    make stop  # Sends stop command via MQTT
    # Or Ctrl+C for immediate shutdown
    ```
    

**Sources:** [README.md121-154](https://github.com/care-foundation/kata-inference-251021-clean2/blob/9a713ffb/README.md#L121-L154) [Makefile](https://github.com/care-foundation/kata-inference-251021-clean2/blob/9a713ffb/Makefile)

---

## Key Classes and Their Relationships

### Class Responsibilities

|Class|File|Purpose|
|---|---|---|
|`PipelineConfig`|[adeline/config.py](https://github.com/care-foundation/kata-inference-251021-clean2/blob/9a713ffb/adeline/config.py)|Load, validate, and provide configuration|
|`disable_models_from_config()`|[adeline/config.py](https://github.com/care-foundation/kata-inference-251021-clean2/blob/9a713ffb/adeline/config.py)|Pre-import model disabling (critical for startup)|
|`InferencePipelineController`|[adeline/app/controller.py](https://github.com/care-foundation/kata-inference-251021-clean2/blob/9a713ffb/adeline/app/controller.py)|Orchestrate all components, handle signals|
|`MQTTControlPlane`|[adeline/control/plane.py](https://github.com/care-foundation/kata-inference-251021-clean2/blob/9a713ffb/adeline/control/plane.py)|Subscribe to control commands (QoS 1)|
|`MQTTDataPlane`|[adeline/data/plane.py](https://github.com/care-foundation/kata-inference-251021-clean2/blob/9a713ffb/adeline/data/plane.py)|Publish detection data (QoS 0)|
|`create_roi_strategy()`|[adeline/inference/roi/__init__.py](https://github.com/care-foundation/kata-inference-251021-clean2/blob/9a713ffb/adeline/inference/roi/__init__.py)|Factory for ROI strategies|
|`create_stabilization_strategy()`|[adeline/inference/stabilization/core.py](https://github.com/care-foundation/kata-inference-251021-clean2/blob/9a713ffb/adeline/inference/stabilization/core.py)|Factory for stabilization strategies|
|`create_mqtt_sink()`|[adeline/data/sinks.py](https://github.com/care-foundation/kata-inference-251021-clean2/blob/9a713ffb/adeline/data/sinks.py)|Create MQTT output sink|
|`create_visualization_sink()`|[adeline/visualization/sinks.py](https://github.com/care-foundation/kata-inference-251021-clean2/blob/9a713ffb/adeline/visualization/sinks.py)|Create OpenCV display sink|

**Sources:** [adeline/__init__.py27-44](https://github.com/care-foundation/kata-inference-251021-clean2/blob/9a713ffb/adeline/__init__.py#L27-L44) [README.md36-44](https://github.com/care-foundation/kata-inference-251021-clean2/blob/9a713ffb/README.md#L36-L44)

---

## Common Development Tasks

### Adding a New ROI Strategy

See [Extending with New Strategies](https://deepwiki.com/care-foundation/kata-inference-251021-clean2/8.3-extending-with-new-strategies) for a detailed tutorial.

Brief steps:

1. Create new strategy class in `adeline/inference/roi/`
2. Implement required interface
3. Register in `create_roi_strategy()` factory
4. Add configuration schema
5. Test with `make run`

### Adding a New Control Command

1. Define command handler in [adeline/control/plane.py](https://github.com/care-foundation/kata-inference-251021-clean2/blob/9a713ffb/adeline/control/plane.py)
2. Register callback in `MQTTControlPlane.__init__()`
3. Add CLI command in [adeline/control/cli.py](https://github.com/care-foundation/kata-inference-251021-clean2/blob/9a713ffb/adeline/control/cli.py)
4. Update Makefile with convenience target
5. Test with command line

### Modifying Configuration Schema

1. Update [config/adeline/config.yaml.example](https://github.com/care-foundation/kata-inference-251021-clean2/blob/9a713ffb/config/adeline/config.yaml.example)
2. Update [adeline/config.py](https://github.com/care-foundation/kata-inference-251021-clean2/blob/9a713ffb/adeline/config.py) validation
3. Update documentation
4. Test with `make run`

### Adding a New Sink

1. Create sink function in appropriate module (`data/sinks.py` or `visualization/sinks.py`)
2. Compose into multi-sink in [adeline/app/controller.py](https://github.com/care-foundation/kata-inference-251021-clean2/blob/9a713ffb/adeline/app/controller.py)
3. Test output destination

**Sources:** [adeline/DESIGN.md24-72](https://github.com/care-foundation/kata-inference-251021-clean2/blob/9a713ffb/adeline/DESIGN.md#L24-L72)

---

## Testing and Verification

The Adeline system uses a **manual pair-programming testing approach** rather than automated unit tests. This reflects the project's philosophy that integration testing of real-world system behavior is more valuable than isolated unit tests.

### Testing Methodology

```
# 1. Start the system
make run

# 2. Test control commands
make pause && make resume && make stop

# 3. Monitor data streams
make monitor-data

# 4. Check metrics
make metrics

# 5. Test ROI toggle
make toggle-crop

# 6. Check stabilization stats
make stabilization-stats
```

### Verification Checklist

- [ ]  System starts without errors
- [ ]  Control commands are responsive
- [ ]  Detection data flows to MQTT
- [ ]  Status updates publish correctly
- [ ]  ROI strategies can be toggled
- [ ]  Stabilization reduces flickering
- [ ]  Graceful shutdown on `make stop`
- [ ]  Signal handling works (Ctrl+C)

See [Testing Approach](https://deepwiki.com/care-foundation/kata-inference-251021-clean2/8.4-testing-approach) for detailed testing methodology.

**Sources:** [README.md145-154](https://github.com/care-foundation/kata-inference-251021-clean2/blob/9a713ffb/README.md#L145-L154)

---

## Anti-Patterns to Avoid

Based on [adeline/DESIGN.md74-88](https://github.com/care-foundation/kata-inference-251021-clean2/blob/9a713ffb/adeline/DESIGN.md#L74-L88) avoid these patterns:

|Anti-Pattern|Why It's Bad|Alternative|
|---|---|---|
|**God Objects**|Single class doing too much|Separate concerns (control/data planes)|
|**Hardcoded Logic**|`if mode == "adaptive"` scattered everywhere|Factory pattern + config|
|**Tight Coupling**|Control plane publishing data|Separate control/data responsibilities|
|**Magic Initialization**|Hidden import side effects|Explicit `disable_models_from_config()` call|
|**Configuration in Code**|Hardcoded thresholds/parameters|YAML configuration|

**Sources:** [adeline/DESIGN.md74-88](https://github.com/care-foundation/kata-inference-251021-clean2/blob/9a713ffb/adeline/DESIGN.md#L74-L88)

---

## Debugging Tips

### Common Issues

1. **ModelDependencyMissing Warning**
    
    - Cause: Imported `inference` before calling `disable_models_from_config()`
    - Fix: Ensure [adeline/__main__.py](https://github.com/care-foundation/kata-inference-251021-clean2/blob/9a713ffb/adeline/__main__.py) or [adeline/app/controller.py](https://github.com/care-foundation/kata-inference-251021-clean2/blob/9a713ffb/adeline/app/controller.py) calls `disable_models_from_config()` first
2. **MQTT Connection Failures**
    
    - Check: `make services-status` to verify broker is running
    - Check: `.env` file has correct `MQTT_USERNAME` and `MQTT_PASSWORD`
3. **No Detection Output**
    
    - Verify: RTSP stream is accessible
    - Check: Model is not in `models_disabled.disabled` list
    - Monitor: `make monitor-data` to see if data is publishing
4. **Pipeline Not Responding to Commands**
    
    - Verify: Control plane is connected (`make status`)
    - Check: Topic names in `config.yaml` match CLI usage
    - Monitor: MQTT broker logs with `make services-logs`

### Debug Mode

```
# Run with verbose output
PYTHONPATH=. uv run python -m adeline

# Monitor MQTT traffic
make services-logs

# Check system status
make status
make metrics
```

---

## Next Steps

For specific development topics, see:

- **Module Organization:** [Module Organization](https://deepwiki.com/care-foundation/kata-inference-251021-clean2/8.1-module-organization) - detailed package structure
- **Entry Points:** [Entry Points](https://deepwiki.com/care-foundation/kata-inference-251021-clean2/8.2-entry-points) - how to run different system components
- **Extending Strategies:** [Extending with New Strategies](https://deepwiki.com/care-foundation/kata-inference-251021-clean2/8.3-extending-with-new-strategies) - tutorial on adding new ROI/stabilization strategies
- **Testing:** [Testing Approach](https://deepwiki.com/care-foundation/kata-inference-251021-clean2/8.4-testing-approach) - comprehensive testing methodology

For operational usage:

- **Running the System:** [Operations Guide](https://deepwiki.com/care-foundation/kata-inference-251021-clean2/7-operations-guide)
- **Configuration:** [Configuration Reference](https://deepwiki.com/care-foundation/kata-inference-251021-clean2/6-configuration-reference)

For architectural understanding:

- **System Design:** [System Architecture](https://deepwiki.com/care-foundation/kata-inference-251021-clean2/3-system-architecture)
- **Design Patterns:** [Design Principles and Patterns](https://deepwiki.com/care-foundation/kata-inference-251021-clean2/4-design-principles-and-patterns)

**Sources:** [README.md1-214](https://github.com/care-foundation/kata-inference-251021-clean2/blob/9a713ffb/README.md#L1-L214) [adeline/DESIGN.md1-116](https://github.com/care-foundation/kata-inference-251021-clean2/blob/9a713ffb/adeline/DESIGN.md#L1-L116) [adeline/__init__.py1-44](https://github.com/care-foundation/kata-inference-251021-clean2/blob/9a713ffb/adeline/__init__.py#L1-L44)