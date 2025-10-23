# Core Architecture

Relevant source files

- [adeline/CLAUDE.md](https://github.com/acare7/kata-inference-251021-clean4/blob/a0662727/adeline/CLAUDE.md)
- [adeline/app/builder.py](https://github.com/acare7/kata-inference-251021-clean4/blob/a0662727/adeline/app/builder.py)
- [adeline/app/controller.py](https://github.com/acare7/kata-inference-251021-clean4/blob/a0662727/adeline/app/controller.py)
- [adeline/control/plane.py](https://github.com/acare7/kata-inference-251021-clean4/blob/a0662727/adeline/control/plane.py)
- [adeline/control/registry.py](https://github.com/acare7/kata-inference-251021-clean4/blob/a0662727/adeline/control/registry.py)

## Purpose and Scope

This document provides a detailed explanation of the Adeline inference pipeline's core architectural components, their responsibilities, and how they interact. The architecture follows a "Complexity by design, not by accident" philosophy, using intentional structural patterns to manage system complexity.

**Scope:**

- Main orchestration components: `InferencePipelineController` and `PipelineBuilder`
- Factory pattern system for component construction
- MQTT dual-plane architecture for control and data
- Separation of concerns and dependency injection flow

**For specific details about:**

- Configuration validation and schemas, see [Configuration System](https://deepwiki.com/acare7/kata-inference-251021-clean4/6-configuration-system)
- Inference processing and ROI strategies, see [Inference Pipeline](https://deepwiki.com/acare7/kata-inference-251021-clean4/5-inference-pipeline)
- Detection stabilization and tracking, see [Multi-Object Tracking](https://deepwiki.com/acare7/kata-inference-251021-clean4/5.3-multi-object-tracking)

## Architectural Overview

The Adeline system is organized around three primary architectural layers:


```mermaid
flowchart LR
  %% Layers
  subgraph Orchestration_Layer["Orchestration Layer"]
    IPC[InferencePipelineController]
  end

  subgraph Construction_Layer["Construction Layer"]
    PB[PipelineBuilder]
    HF[InferenceHandlerFactory]
    SF[SinkFactory]
    STF[StrategyFactory]
  end

  subgraph Execution_Layer["Execution Layer"]
    IH[InferenceHandler]
    STAB[DetectionStabilizer]
    SINKS[Multi-Sink Output]
    IP[InferencePipeline]
  end

  subgraph Communication_Layer["Communication Layer"]
    CP[MQTTControlPlane]
    CR[CommandRegistry]
    DP[MQTTDataPlane]
  end

  %% Orchestration -> Construction
  IPC -- "delegates construction to" --> PB
  PB -- uses --> HF
  PB -- uses --> SF
  PB -- uses --> STF

  %% Factories create components
  HF -- creates --> IH
  SF -- creates --> SINKS
  STF -- creates --> STAB

  %% Wiring / assembly
  PB -- assembles --> IP
  IH -- "plugged into" --> IP
  STAB -- wraps --> SINKS
  SINKS -- "plugged into" --> IP

  %% Orchestration -> Execution & Communication
  IPC -- "manages lifecycle of" --> IP
  IPC -- manages --> CP
  IPC -- manages --> DP

  %% Control path
  CP -- uses --> CR
  CR -- "executes commands on" --> IPC

  %% Data plane publications
  IP -- "publishes results via" --> DP
```

**Sources:** [adeline/CLAUDE.md65-88](https://github.com/acare7/kata-inference-251021-clean4/blob/a0662727/adeline/CLAUDE.md#L65-L88) [adeline/app/controller.py58-91](https://github.com/acare7/kata-inference-251021-clean4/blob/a0662727/adeline/app/controller.py#L58-L91) [adeline/app/builder.py41-70](https://github.com/acare7/kata-inference-251021-clean4/blob/a0662727/adeline/app/builder.py#L41-L70)

## Component Responsibilities

### InferencePipelineController

The `InferencePipelineController` class serves as the main orchestrator with the following responsibilities:

|Responsibility|Description|Code Location|
|---|---|---|
|**Lifecycle Management**|Handles start, stop, pause, resume operations|[adeline/app/controller.py58-91](https://github.com/acare7/kata-inference-251021-clean4/blob/a0662727/adeline/app/controller.py#L58-L91)|
|**Setup Orchestration**|Coordinates component initialization sequence|[adeline/app/controller.py92-194](https://github.com/acare7/kata-inference-251021-clean4/blob/a0662727/adeline/app/controller.py#L92-L194)|
|**Signal Handling**|Manages Ctrl+C and SIGTERM signals|[adeline/app/controller.py385-396](https://github.com/acare7/kata-inference-251021-clean4/blob/a0662727/adeline/app/controller.py#L385-L396)|
|**Resource Cleanup**|Ensures proper shutdown of all components|[adeline/app/controller.py398-443](https://github.com/acare7/kata-inference-251021-clean4/blob/a0662727/adeline/app/controller.py#L398-L443)|
|**Command Delegation**|Registers MQTT command handlers|[adeline/app/controller.py196-219](https://github.com/acare7/kata-inference-251021-clean4/blob/a0662727/adeline/app/controller.py#L196-L219)|

**Key Design Principle:** The controller **orchestrates but does not construct**. All construction logic is delegated to `PipelineBuilder`.

**Sources:** [adeline/app/controller.py58-91](https://github.com/acare7/kata-inference-251021-clean4/blob/a0662727/adeline/app/controller.py#L58-L91) [adeline/CLAUDE.md65-88](https://github.com/acare7/kata-inference-251021-clean4/blob/a0662727/adeline/CLAUDE.md#L65-L88)

### PipelineBuilder

The `PipelineBuilder` class implements the Builder pattern, encapsulating all component construction logic:

|Method|Purpose|Returns|
|---|---|---|
|`build_inference_handler()`|Creates inference handler based on `ROI_MODE`|`(BaseInferenceHandler, roi_state)`|
|`build_sinks()`|Constructs output sinks based on configuration|`List[Callable]`|
|`wrap_sinks_with_stabilization()`|Wraps sinks with stabilization if enabled|`List[Callable]`|
|`build_pipeline()`|Assembles final `InferencePipeline`|`InferencePipeline`|

**Construction Flow:**


```mermaid
sequenceDiagram
  autonumber
  participant C as InferencePipelineController
  participant B as PipelineBuilder
  participant HF as InferenceHandlerFactory
  participant SF as SinkFactory
  participant STF as StrategyFactory

  C->>B: build_inference_handler()
  B->>HF: create(config)
  HF-->>B: handler, roi_state
  B-->>C: handler, roi_state

  C->>B: build_sinks(data_plane, roi_state, handler)
  B->>SF: create_sinks(config, ...)
  SF-->>B: [mqtt_sink, roi_sink, viz_sink]
  B-->>C: sinks

  C->>B: wrap_sinks_with_stabilization(sinks)
  B->>STF: create_stabilization_strategy(config)
  STF-->>B: stabilizer
  B-->>C: wrap first sink
  B->>B: [stabilized_sink, roi_sink, viz_sink]

  C->>B: build_pipeline(handler, sinks, watchdog, ...)
  B->>B: compose with multi_sink
  B->>B: init standard or custom pipeline
  B-->>C: InferencePipeline
```

**Sources:** [adeline/app/builder.py41-70](https://github.com/acare7/kata-inference-251021-clean4/blob/a0662727/adeline/app/builder.py#L41-L70) [adeline/app/builder.py71-208](https://github.com/acare7/kata-inference-251021-clean4/blob/a0662727/adeline/app/builder.py#L71-L208)

### Factory Pattern System

Three specialized factories handle component creation based on configuration:


```mermaid
flowchart LR

subgraph FI[Factory Inputs]
  direction TB
  CFG[PipelineConfig]
end

%% ---------------- InferenceHandlerFactory ----------------
subgraph IHF[InferenceHandlerFactory]
  direction TB
  HF_CREATE[create config ]
  HF_NONE[ROI_MODE='none']
  HF_FIXED[ROI_MODE='fixed']
  HF_ADAPT[ROI_MODE='adaptive']

  STD[StandardInferenceHandler]
  FIXED_IMPL[FixedROIInferenceHandler]
  ADAPT_IMPL[AdaptiveInferenceHandler]

  HF_CREATE --> HF_NONE
  HF_CREATE --> HF_FIXED
  HF_CREATE --> HF_ADAPT

  HF_NONE -- returns --> STD
  HF_FIXED -- returns --> FIXED_IMPL
  HF_ADAPT -- returns --> ADAPT_IMPL
end

%% ---------------- SinkFactory ----------------
subgraph SF[SinkFactory]
  direction TB
  SF_CREATE[create_sinks config, ...]
  MQTT[MQTTPublisherSink priority=1]
  ROI[ROIUpdateSink priority=50]
  VIZ[VisualizationSink priority=100]

  SF_CREATE --> MQTT
  SF_CREATE --> ROI
  SF_CREATE --> VIZ
end

%% ---------------- StrategyFactory ----------------
subgraph STF[StrategyFactory]
  direction TB
  STF_CREATE[create_stabilization_strategy config]
  STF_NONE[STABILIZATION_MODE='none']
  STF_TEMP[STABILIZATION_MODE='temporal']

  NOOP[NoOpStabilizer]
  TEMP[TemporalHysteresisStabilizer]

  STF_CREATE --> STF_NONE
  STF_CREATE --> STF_TEMP

  STF_NONE -- returns --> NOOP
  STF_TEMP -- returns --> TEMP
end

%% Inputs to factories
CFG --> HF_CREATE
CFG --> SF_CREATE
CFG --> STF_CREATE
```


**Factory Characteristics:**

- **InferenceHandlerFactory**: Creates handlers implementing the Strategy pattern for different ROI modes (detailed in [#3.3.1](https://deepwiki.com/acare7/kata-inference-251021-clean4/3.3.1-inferencehandlerfactory))
- **SinkFactory**: Uses registry pattern with explicit priorities for sink ordering (detailed in [#3.3.2](https://deepwiki.com/acare7/kata-inference-251021-clean4/3.3.2-sinkfactory))
- **StrategyFactory**: Creates stabilization strategies based on configuration (detailed in [#3.3.3](https://deepwiki.com/acare7/kata-inference-251021-clean4/3.3.3-strategyfactory))

**Sources:** [adeline/CLAUDE.md83-87](https://github.com/acare7/kata-inference-251021-clean4/blob/a0662727/adeline/CLAUDE.md#L83-L87) [adeline/app/builder.py82-83](https://github.com/acare7/kata-inference-251021-clean4/blob/a0662727/adeline/app/builder.py#L82-L83) [adeline/app/builder.py104-110](https://github.com/acare7/kata-inference-251021-clean4/blob/a0662727/adeline/app/builder.py#L104-L110) [adeline/app/builder.py137-138](https://github.com/acare7/kata-inference-251021-clean4/blob/a0662727/adeline/app/builder.py#L137-L138)

## MQTT Dual-Plane Architecture

The system separates control commands from data publishing using two independent MQTT planes with different QoS guarantees:




```mermaid
flowchart TB

%% ---------------- MQTT Broker ----------------
subgraph BROKER[MQTT Broker]
  B[mosquitto]
end

%% ---------------- Control Plane (QoS 1) ----------------
subgraph CP[Control Plane QoS 1 - Reliable]
  CT_CMD[inference/control/commands]
  CP_NODE[MQTTControlPlane]
  CR[CommandRegistry]
  CT_STATUS[inference/control/status]
end

%% ---------------- InferencePipelineController ----------------
subgraph IPCG[InferencePipelineController]
  IPC[controller instance]
end

%% ---------------- Data Plane (QoS 0) ----------------
subgraph DP[Data Plane QoS 0 - Best Effort]
  DP_NODE[MQTTDataPlane]
  DPUB[DetectionPublisher]
  MPUB[MetricsPublisher]
  DT_DET[inference/data/detections]
  DT_MET[inference/data/metrics]
end

%% -------- Broker ↔ Topics
B <-->|subscribe/publish| CT_CMD
B <-->|subscribe/publish| CT_STATUS
B <-->|publish| DT_DET
B <-->|publish| DT_MET

%% -------- Control flow
CT_CMD -->|receives commands| CP_NODE
CP_NODE -->|uses| CR
CR -->|executes on| IPC

%% -------- Status + Data flow
IPC -->|publishes status| CT_STATUS
IPC -->|publishes results| DP_NODE
DP_NODE -->|via| DPUB
DP_NODE -->|via| MPUB
DPUB -->|to| DT_DET
MPUB -->|to| DT_MET
```

### Control Plane (QoS 1)

The `MQTTControlPlane` receives and executes control commands:

|Feature|Implementation|Purpose|
|---|---|---|
|**QoS Level**|1 (At least once delivery)|Ensures critical commands are not lost|
|**Command Registry**|`CommandRegistry` class|Explicit registration of available commands|
|**Conditional Commands**|Registered based on capabilities|Only registers `toggle_crop` if handler supports it|
|**Command Topic**|`inference/control/commands`|Receives JSON command payloads|
|**Status Topic**|`inference/control/status`|Publishes pipeline state changes|

**Command Registration Pattern:**

```
# From controller._setup_control_callbacks()
registry = self.control_plane.command_registry

# Always available
registry.register('pause', self._handle_pause, "Pausa el procesamiento")
registry.register('resume', self._handle_resume, "Reanuda el procesamiento")
registry.register('stop', self._handle_stop, "Detiene y finaliza el pipeline")

# Conditional - only if handler supports toggle
if self.inference_handler and self.inference_handler.supports_toggle:
    registry.register('toggle_crop', self._handle_toggle_crop, "Toggle adaptive ROI crop")

# Conditional - only if stabilization enabled
if self.stabilizer is not None:
    registry.register('stabilization_stats', self._handle_stabilization_stats, ...)
```

**Sources:** [adeline/control/plane.py26-54](https://github.com/acare7/kata-inference-251021-clean4/blob/a0662727/adeline/control/plane.py#L26-L54) [adeline/control/registry.py28-53](https://github.com/acare7/kata-inference-251021-clean4/blob/a0662727/adeline/control/registry.py#L28-L53) [adeline/app/controller.py196-219](https://github.com/acare7/kata-inference-251021-clean4/blob/a0662727/adeline/app/controller.py#L196-L219)

### Data Plane (QoS 0)

The `MQTTDataPlane` publishes inference results and metrics:

|Feature|Implementation|Purpose|
|---|---|---|
|**QoS Level**|0 (Fire and forget)|High throughput, acceptable data loss|
|**Publishers**|`DetectionPublisher`, `MetricsPublisher`|Formats and publishes different data types|
|**Detection Topic**|`inference/data/detections`|Publishes inference results|
|**Metrics Topic**|`inference/data/metrics`|Publishes pipeline performance metrics|

**Sources:** [adeline/CLAUDE.md90-102](https://github.com/acare7/kata-inference-251021-clean4/blob/a0662727/adeline/CLAUDE.md#L90-L102) [adeline/app/controller.py107-125](https://github.com/acare7/kata-inference-251021-clean4/blob/a0662727/adeline/app/controller.py#L107-L125)

## Component Interaction Flow

The following diagram shows the complete initialization and execution flow:



```mermaid
sequenceDiagram
  participant Main as main()
  participant Config as AdelineConfig
  participant IPC as InferencePipelineController
  participant DP as MQTTDataPlane
  participant Bldr as PipelineBuilder
  participant Pipe as InferencePipeline
  participant CP as MQTTControlPlane
  participant Reg as CommandRegistry

  Main->>Config: from_yaml("config.yaml")
  Config-->>Main: pydantic_config
  Main->>Config: to_legacy_config()
  Config-->>Main: legacy_config

  Main->>IPC: __init__(config)
  Main->>IPC: create PipelineBuilder(config)
  IPC->>Bldr: setup()

  Note over IPC: Step 1: Setup Data Plane
  IPC->>DP: __init__(broker, topics, qos=0)
  IPC->>DP: connect(timeout=10)
  DP-->>IPC: connected

  Note over IPC: Step 2: Build Handler
  IPC->>Bldr: build_inference_handler()
  Bldr->>Bldr: InferenceHandlerFactory.create()
  Bldr-->>IPC: handler, roi_state

  Note over IPC: Step 3: Build Sinks
  IPC->>Bldr: build_sinks(data_plane, roi_state, handler)
  Bldr->>Bldr: SinkFactory.create_sinks()
  Bldr-->>IPC: [mqtt_sink, roi_sink, viz_sink]

  Note over IPC: Step 4: Wrap Stabilization
  IPC->>Bldr: wrap_sinks_with_stabilization(sinks)
  Bldr->>Bldr: StrategyFactory.create_stabilization_strategy()
  Bldr-->>IPC: wrapped_sinks

  Note over IPC: Step 5: Build Pipeline
  IPC->>Bldr: build_pipeline(handler, sinks, watchdog, ...)
  Bldr->>Pipe: InferencePipeline.init_with_custom_logic()
  Pipe-->>Bldr: pipeline instance
  Bldr-->>IPC: pipeline

  Note over IPC: Step 6: Setup Control Plane
  IPC->>CP: __init__(broker, topics, qos=1)
  IPC->>CP: register commands
  IPC->>Reg: connect(timeout=10)
  CP-->>IPC: connected

  Note over IPC: Step 7: Auto-start Pipeline
  IPC->>Pipe: start()
  Pipe-->>IPC: running

  IPC-->>Main: setup complete
  Main->>IPC: run()
  IPC-->>Main: wait on shutdown_event
```

**Sources:** [adeline/app/controller.py92-194](https://github.com/acare7/kata-inference-251021-clean4/blob/a0662727/adeline/app/controller.py#L92-L194) [adeline/app/builder.py71-208](https://github.com/acare7/kata-inference-251021-clean4/blob/a0662727/adeline/app/builder.py#L71-L208) [adeline/app/controller.py449-503](https://github.com/acare7/kata-inference-251021-clean4/blob/a0662727/adeline/app/controller.py#L449-L503)

## Separation of Concerns

The architecture enforces strict separation of concerns:

|Component|**Knows About**|**Does NOT Know About**|
|---|---|---|
|**InferencePipelineController**|- Lifecycle management  <br>- Component coordination  <br>- Signal handling|- How to construct components  <br>- Factory implementation details  <br>- Inference algorithm details|
|**PipelineBuilder**|- Construction sequence  <br>- Factory interfaces  <br>- Component assembly|- Runtime lifecycle  <br>- Command handling  <br>- MQTT communication|
|**Factories**|- Configuration schema  <br>- Component types  <br>- Creation logic|- When to create components  <br>- Pipeline lifecycle  <br>- Other factories|
|**MQTTControlPlane**|- Command reception  <br>- CommandRegistry  <br>- Status publishing|- Command implementation  <br>- Pipeline internals  <br>- Data plane details|
|**MQTTDataPlane**|- Result publishing  <br>- Metrics formatting  <br>- QoS settings|- Inference logic  <br>- Command handling  <br>- Control plane details|

**Design Benefits:**

1. **Single Responsibility**: Each component has one clear purpose
2. **Testability**: Components can be tested in isolation
3. **Extensibility**: New handlers/sinks/strategies added via factories without touching controller
4. **Maintainability**: Changes localized to specific components

**Sources:** [adeline/CLAUDE.md59-64](https://github.com/acare7/kata-inference-251021-clean4/blob/a0662727/adeline/CLAUDE.md#L59-L64) [adeline/CLAUDE.md65-88](https://github.com/acare7/kata-inference-251021-clean4/blob/a0662727/adeline/CLAUDE.md#L65-L88)

## Key Design Patterns

### Builder Pattern

The `PipelineBuilder` separates complex construction from usage:



```mermaid
flowchart TD
  Controller["InferencePipelineController<br/>(Client)"]
  Builder["PipelineBuilder<br/>(Builder)"]
  Product["InferencePipeline<br/>(Product)"]
  Handler["handler, roi_state"]
  Sinks["List[Callable]"]
  Wrapped["wrapped sinks"]

  Controller -->|uses| Builder

  %% Builder steps
  Builder -->|"build_inference_handler()"| Handler
  Builder -->|"build_sinks(...)"| Sinks
  Builder -->|"wrap_sinks_with_stabilization(...)"| Wrapped

  %% Build product
  Builder -->|constructs| Product
  Builder -->|"build_pipeline(...)"| Product

  %% Dotted relation
  Controller -.->|receives| Product
```

**Sources:** [adeline/app/builder.py41-70](https://github.com/acare7/kata-inference-251021-clean4/blob/a0662727/adeline/app/builder.py#L41-L70)

### Registry Pattern

The `CommandRegistry` provides explicit command registration:



```mermaid
flowchart LR
  Registry["CommandRegistry"]
  Commands["Available Commands"]

  Pause["pause handler"]
  Resume["resume handler"]
  Stop["stop handler"]
  Toggle["toggle_crop handler"]

  %% registrations
  Pause -->|register 'pause', ...| Registry
  Resume -->|register 'resume', ...| Registry
  Stop -->|register 'stop', ...| Registry
  Toggle -->|register 'toggle_crop', ... if supported| Registry

  %% execution & listing
  Registry -->|execute 'pause'| Pause
  Registry -->|available_commands| Commands
```

**Benefits:**

- No optional callbacks
- Clear error messages for unavailable commands
- Runtime introspection of available commands
- Conditional command registration based on capabilities

**Sources:** [adeline/control/registry.py28-142](https://github.com/acare7/kata-inference-251021-clean4/blob/a0662727/adeline/control/registry.py#L28-L142) [adeline/CLAUDE.md90-97](https://github.com/acare7/kata-inference-251021-clean4/blob/a0662727/adeline/CLAUDE.md#L90-L97)

### Strategy Pattern

Different strategies are selected at runtime based on configuration:

|Strategy Type|Configuration Key|Implementations|
|---|---|---|
|**ROI Strategy**|`ROI_MODE`|`none`, `fixed`, `adaptive`|
|**Stabilization Strategy**|`STABILIZATION_MODE`|`none`, `temporal`|

**Sources:** [adeline/CLAUDE.md103-127](https://github.com/acare7/kata-inference-251021-clean4/blob/a0662727/adeline/CLAUDE.md#L103-L127)

### Factory Pattern

Factories encapsulate creation logic:





```mermaid
flowchart TB
  Config["PipelineConfig"]

  subgraph "Factory Layer"
    HF["InferenceHandlerFactory"]
    SF["SinkFactory"]
    STF["StrategyFactory"]
  end

  subgraph "Products"
    Handlers["InferenceHandler variants"]
    Sinks["Sink instances"]
    Strategies["Stabilizer variants"]
  end

  %% wiring
  Config --> HF
  Config --> SF
  Config --> STF

  HF -->|create| Handlers
  SF -->|create_sinks| Sinks
  STF -->|create_stabilization_strategy| Strategies
```
**Sources:** [adeline/CLAUDE.md83-87](https://github.com/acare7/kata-inference-251021-clean4/blob/a0662727/adeline/CLAUDE.md#L83-L87)

### Lazy Loading Pattern

The `InferenceLoader` ensures model configuration happens before importing inference modules:

```
# From controller.py
from ..inference.loader import InferenceLoader

inference_module = InferenceLoader.get_inference()
InferencePipeline = inference_module.InferencePipeline
```

This pattern prevents unnecessary model downloads by ensuring `disable_models_from_config()` runs before importing inference modules.

**Sources:** [adeline/app/controller.py22-30](https://github.com/acare7/kata-inference-251021-clean4/blob/a0662727/adeline/app/controller.py#L22-L30) [adeline/CLAUDE.md137-141](https://github.com/acare7/kata-inference-251021-clean4/blob/a0662727/adeline/CLAUDE.md#L137-L141)