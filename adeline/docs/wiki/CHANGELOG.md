# Changelog - Architectural Evolution

This changelog documents significant architectural decisions and design milestones in the Adeline inference pipeline system. It focuses on design evolution rather than individual commits.

---

## [v3.0] - 2025-10-22 - Structured Logging & Observability

### Added

- **JSON Structured Logging** across 19 core modules (~126 logs migrated)
  - Complete migration from string-based to structured JSON logging
  - Consistent schema across all components (Control Plane, Data Plane, Stabilization)
  - Production-ready queryable logs via `jq`

- **Trace Context Propagation**
  - Correlate MQTT commands to pipeline actions via `trace_id`
  - Context manager API for trace propagation through call stacks
  - Enable end-to-end request tracing (command → handler → pipeline → sinks)

- **Helper Functions** for common log patterns
  - `log_mqtt_command()` - Control plane command events
  - `log_pipeline_metrics()` - FPS, latency, throughput metrics
  - `log_stabilization_stats()` - Multi-object tracking statistics
  - `log_error_with_context()` - Errors with full architectural context

- **Log Rotation**
  - Built-in Python `RotatingFileHandler` with configurable thresholds
  - Logrotate configuration for Linux environments (`config/logrotate.d/adeline`)
  - Dual rotation strategy (application-level + OS-level)

- **Queryable Logs in Production**
  - `jq` query examples for common debugging scenarios
  - Trace specific commands, filter by component, aggregate metrics
  - Performance analysis tooling (average FPS, error rates by component)

### Design Philosophy

- **Fail Fast (Load Time vs Runtime)** - Logs structured at design time, queryable at runtime
- **Eventos como vocabulario de diseño** - Log patterns reflect architectural boundaries
  - Control Plane events, Data Plane events, Stabilization events
  - Domain events encode architectural knowledge
- **Complejidad por diseño** - Structured logging enables complex queries without ad-hoc parsing

### Migration Status

- ✅ **Fase 3** (control/plane, data/plane, stabilization, app/controller) - ~60 logs
- ✅ **Fase 4** (app/builder, sinks/registry, control/registry, factories) - 21 logs
- ✅ **Fase 5** (inference/models, loader, roi/adaptive/state, factories) - 24 logs
- ✅ **Fase 6** (legacy_config, roi/base, roi/fixed, adaptive/pipeline, matching, publishers) - 21 logs
- ✅ **Total**: 19 modules, ~126 logs migrated (100% coverage of production-critical paths)

### Configuration

New `logging` section in `config/adeline/config.yaml`:

```yaml
logging:
  level: INFO
  json_indent: null  # null=compact (production), 2=pretty (development)
  paho_level: WARNING
  file: null  # Optional file logging with rotation
  max_bytes: 10485760  # 10 MB per file
  backup_count: 5  # Retention policy
```

### Documentation

- New wiki section: `7  Logging & Observability/`
  - 7.1 Structured Logging Design
  - 7.2 Log Event Patterns
  - 7.3 Production Queries
  - 7.4 Log Rotation

---

## [v2.1] - 2024-12 - Multi-Object Tracking & IoU-Based Stabilization

### Added

- **IoU-based Multi-Object Tracking** (inference/stabilization/core.py)
  - Tracks 2-4 persons using IoU spatial matching
  - Temporal consistency via hysteresis filtering
  - Prevents track ID confusion when people enter/exit frame

- **Stabilization Modes** (Strategy Pattern)
  - `STABILIZATION_MODE='spatial_iou'` - IoU matching + temporal filtering
  - `STABILIZATION_MODE='none'` - Direct detections (no tracking)

### Design Philosophy

- **Strategy Pattern** for stabilization algorithms
- **Separation of concerns** - Matching logic isolated in `inference/stabilization/matching.py`

### Configuration

New `stabilization` section in config:

```yaml
stabilization:
  mode: spatial_iou
  iou_threshold: 0.3
  appear_threshold: 3
  persist_threshold: 2
```

---

## [v2.0] - 2024-11 - Builder Pattern & Factory System

### Added

- **Builder Pattern** (app/builder.py)
  - `PipelineBuilder` separates construction from orchestration
  - Immutable transformations (`wrap_sinks_with_stabilization` returns new list)
  - Centralized construction logic

- **Factory Pattern System**
  - `InferenceHandlerFactory` - ROI mode selection (none/fixed/adaptive)
  - `SinkFactory` - Priority-based sink ordering
  - `StrategyFactory` - Stabilization strategy creation

- **CommandRegistry Pattern** (control/registry.py)
  - Explicit command registration (no optional callbacks)
  - Conditional registration based on capabilities
  - Runtime introspection of available commands

### Changed

- **Separation of Orchestration and Construction**
  - `InferencePipelineController` delegates construction to `PipelineBuilder`
  - Controller no longer knows construction details

### Design Philosophy

- **Complejidad por diseño, no por accidente**
  - Architectural boundaries manage complexity
  - Strict separation of concerns (Orchestration, Construction, Execution)

---

## [v1.0] - 2024-09 - Dual-Plane MQTT Architecture

### Added

- **MQTT Control Plane** (QoS 1)
  - Reliable command delivery (pause, resume, stop, status)
  - Retained status messages for new subscribers

- **MQTT Data Plane** (QoS 0)
  - Best-effort detection publishing
  - High-throughput metrics publishing

- **Adaptive ROI Strategy** (inference/roi/adaptive/)
  - Dynamic ROI tracking based on detection history
  - Square ROI constraints for model compatibility
  - Zero-copy NumPy views for performance

- **Pydantic Configuration System** (config/schemas.py)
  - Load-time validation (fail-fast philosophy)
  - Type-safe configuration
  - Backward compatibility via `to_legacy_config()`

### Design Philosophy

- **Fail Fast** - Pydantic validation at load time, not runtime
- **Performance by Design**
  - QoS tuning by use case (Control=QoS 1, Data=QoS 0)
  - Zero-copy operations for ROI cropping
- **Explicit Over Implicit** - No optional callbacks, explicit registration

---

## Design Principles Evolution

Throughout all versions, the system has maintained core design principles:

1. **Complejidad por diseño, no por accidente** - Attack complexity through architecture, not code
2. **Fail Fast** - Validate at load time, crash early with clear messages
3. **Separation of Concerns** - Strict boundaries between components
4. **Pattern-Based Architecture** - Builder, Factory, Strategy, Registry patterns
5. **Performance by Design** - Zero-copy operations, QoS tuning, lazy loading
6. **Immutability** - Functional transformations over in-place mutations

These principles are documented in detail in [Design Philosophy](https://deepwiki.com/acare7/kata-inference-251021-clean4/1.2-design-philosophy).

---

## Future Considerations

- **Dynamic Configuration Hot-Reload** - Runtime config changes without restart
- **Distributed Tracing** - OpenTelemetry integration for multi-service correlation
- **Metrics Export** - Prometheus/StatsD integration for monitoring
- **Circuit Breaker Pattern** - MQTT reconnection with exponential backoff
