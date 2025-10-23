# 🎯 PLAN DE QUICK WINS - ADELINE v3.0

**Basado en**: INFORME_CONSULTORIA_DISENIO.md
**Objetivo**: Implementar mejoras de alto impacto con bajo esfuerzo
**Filosofía**: "Complejidad por diseño" + Pragmatismo > Purismo

---

## 📊 MATRIZ DE PRIORIZACIÓN

```
         │ Alto Impacto       │ Medio Impacto      │ Bajo Impacto
─────────┼────────────────────┼────────────────────┼──────────────────
Bajo     │ ✅ QUICK WINS      │ ⚡ Considerar      │ 📝 Backlog
Esfuerzo │ (Hacer ahora)      │ (Si hay tiempo)    │ (Futuro)
─────────┼────────────────────┼────────────────────┼──────────────────
Alto     │ 🎯 Planificar      │ ⏸️ Postponer       │ ❌ No hacer
Esfuerzo │ (Sprint dedicado)  │ (Bajo ROI)         │ (YAGNI)
```

---

## ✅ QUICK WINS - SPRINT ACTUAL (2-3 días)

### 🔧 CÓDIGO - Quick Wins

#### 1. **Fix Type Hints con TYPE_CHECKING** 🟡 [30 min]

**Archivo**: `app/builder.py`

**Problema actual**:
```python
def build_sinks(
    self,
    data_plane: Any,  # ← Type hint débil
    roi_state: Optional[Any] = None,
    inference_handler: Optional[BaseInferenceHandler] = None,
) -> List[Callable]:
```

**Solución**:
```python
from typing import TYPE_CHECKING, Optional, List, Callable, Union

if TYPE_CHECKING:
    from ..data import MQTTDataPlane
    from ..inference.roi import ROIState, FixedROIState

def build_sinks(
    self,
    data_plane: 'MQTTDataPlane',
    roi_state: Optional[Union['ROIState', 'FixedROIState']] = None,
    inference_handler: Optional[BaseInferenceHandler] = None,
) -> List[Callable]:
```

**Beneficios**:
- ✅ Mypy validation completa
- ✅ IDE autocomplete
- ✅ Sin costo en runtime
- ✅ Patrón estándar Python

**Archivos a modificar**:
- `app/builder.py` (líneas 88-93)
- Verificar otros `Any` en codebase con: `grep -n "data_plane: Any" **/*.py`

---

#### 2. **Best-Effort Cleanup con Error Handling** 🟢 [45 min]

**Archivo**: `app/controller.py`

**Problema actual** (líneas 398-443):
```python
def cleanup(self):
    if self.pipeline:
        self.pipeline.terminate()
        self.pipeline.join(timeout=10.0)

    if self.control_plane:
        self.control_plane.disconnect()  # Si falla, data_plane no se desconecta

    if self.data_plane:
        stats = self.data_plane.get_stats()
        self.data_plane.disconnect()
```

**Solución**:
```python
def cleanup(self):
    """Cleanup con best-effort error handling"""
    errors = []

    # 1. Terminate pipeline (independiente)
    if self.pipeline:
        try:
            logger.info("Terminating pipeline...")
            self.pipeline.terminate()
            self.pipeline.join(timeout=10.0)
            logger.info("Pipeline terminated successfully")
        except Exception as e:
            errors.append(f"Pipeline cleanup: {e}")
            logger.error("Pipeline cleanup error", exc_info=True)

    # 2. Disconnect control plane (independiente)
    if self.control_plane:
        try:
            logger.info("Disconnecting control plane...")
            self.control_plane.publish_status("disconnected")
            self.control_plane.disconnect()
            logger.info("Control plane disconnected")
        except Exception as e:
            errors.append(f"Control plane disconnect: {e}")
            logger.error("Control plane cleanup error", exc_info=True)

    # 3. Disconnect data plane (independiente)
    if self.data_plane:
        try:
            logger.info("Disconnecting data plane...")
            stats = self.data_plane.get_stats()
            logger.info(f"Data plane stats: {stats}")
            self.data_plane.disconnect()
            logger.info("Data plane disconnected")
        except Exception as e:
            errors.append(f"Data plane disconnect: {e}")
            logger.error("Data plane cleanup error", exc_info=True)

    # Summary
    if errors:
        logger.warning(
            f"Cleanup completed with {len(errors)} errors",
            extra={"errors": errors, "component": "controller", "event": "cleanup_partial"}
        )
    else:
        logger.info(
            "Cleanup completed successfully",
            extra={"component": "controller", "event": "cleanup_complete"}
        )
```

**Beneficios**:
- ✅ Cleanup garantizado (best-effort)
- ✅ No cascade failures
- ✅ Logging estructurado de errores
- ✅ Más robusto en producción

**Test manual**:
1. Killear MQTT broker mientras pipeline corre
2. Hacer Ctrl+C
3. Verificar que cleanup completo se ejecute aunque broker esté caído

---

#### 3. **Health Check Endpoint** 🟢 [1 hora]

**Archivos**: `app/controller.py`, `control/plane.py`

**Implementación**:

```python
# En app/controller.py, agregar método:

def _handle_health_check(self):
    """
    Health check multi-nivel para monitoring externo.

    Status:
    - healthy: Todos los checks pasan
    - degraded: Algunos checks fallan pero core funciona
    - unhealthy: Checks críticos fallan
    """
    health = {
        'status': 'healthy',
        'timestamp': time.time(),
        'version': '3.0.0',  # TODO: Read from __version__
        'checks': {
            # Critical checks
            'pipeline_running': self.pipeline and self.pipeline.is_alive(),
            'control_plane_connected': self.control_plane and self.control_plane.is_connected(),
            'data_plane_connected': self.data_plane and self.data_plane.is_connected(),

            # Health checks
            'recent_frames': self.watchdog.get_frames_in_last_n_seconds(30) > 0,
            'avg_fps': self.watchdog.get_average_fps(),
        }
    }

    # Determine overall status
    critical_checks = [
        health['checks']['pipeline_running'],
        health['checks']['control_plane_connected'],
        health['checks']['data_plane_connected'],
    ]

    if all(critical_checks) and health['checks']['recent_frames']:
        health['status'] = 'healthy'
    elif any(critical_checks):
        health['status'] = 'degraded'
    else:
        health['status'] = 'unhealthy'

    # Publish
    self.control_plane.publish_status(json.dumps(health))
    logger.info(
        f"Health check: {health['status']}",
        extra={
            "component": "controller",
            "event": "health_check",
            "status": health['status'],
            "checks": health['checks']
        }
    )

# En _setup_control_callbacks(), agregar:
registry.register('health', self._handle_health_check, "Health check del sistema")
```

**Test**:
```bash
# Publicar health check command
mosquitto_pub -t "inference/control/commands" -m '{"command": "health"}'

# Escuchar respuesta
mosquitto_sub -t "inference/control/status" -v
```

**Beneficios**:
- ✅ K8s/Docker health probes
- ✅ Monitoring externo (Grafana, etc)
- ✅ Debugging de problemas en producción

---

### 📝 WIKI - Quick Wins

#### 4. **Aclarar ROI Square Constraint** 📄 [15 min]

**Archivo**: `docs/wiki/1  Overview/1.1  Core Concepts.md`

**Cambio** (línea 76):

**Antes**:
```markdown
- **Square constraint**: Adaptive ROI maintains square aspect ratio to prevent model distortion
```

**Después**:
```markdown
- **Square constraint**: Adaptive ROI maintains square aspect ratio to prevent model distortion.
  Square sides are multiples of configurable values (`min_roi_multiple`, `max_roi_multiple`),
  not necessarily `imgsz`. Default: 320-640 pixels for 320x320 model.
```

---

#### 5. **Documentar Sink Priority Values** 📄 [10 min]

**Archivo**: `docs/wiki/5  Inference Pipeline/5.4 Output-Sinks.md`

**Agregar sección**:

```markdown
### Sink Priority System

Sinks are registered with explicit priority values to control execution order:

| Priority | Sink Type | Purpose | Critical for Stabilization? |
|----------|-----------|---------|----------------------------|
| **1** | MQTT Sink | Publish detections to MQTT broker | ✅ Yes - wrapped by stabilizer |
| **50** | ROI Update Sink | Update adaptive ROI state | ❌ No |
| **100** | Visualization Sink | OpenCV display window | ❌ No |

**Important**: The stabilization wrapper assumes the MQTT sink is first (priority 1).
Changing sink priorities requires updating `PipelineBuilder.wrap_sinks_with_stabilization()`.

See: `app/factories/sink_factory.py:131-148`
```

---

#### 6. **Documentar Health Check Command** 📄 [20 min]

**Archivo**: `docs/wiki/4  MQTT Communication/4.3  Command Reference.md`

**Agregar sección**:

```markdown
### `health` - System Health Check

**Description**: Returns multi-level health status for external monitoring.

**Availability**: Always

**Request**:
```json
{
  "command": "health",
  "timestamp": "2025-10-23T12:00:00Z"
}
```

**Response** (via `inference/control/status` topic):
```json
{
  "status": "healthy",  // "healthy" | "degraded" | "unhealthy"
  "timestamp": 1698062400.0,
  "version": "3.0.0",
  "checks": {
    "pipeline_running": true,
    "control_plane_connected": true,
    "data_plane_connected": true,
    "recent_frames": true,
    "avg_fps": 2.1
  }
}
```

**Status Levels**:
- `healthy`: All critical checks pass, pipeline is processing frames
- `degraded`: Some non-critical checks fail but pipeline is operational
- `unhealthy`: Critical checks fail (pipeline stopped, MQTT disconnected)

**Use Cases**:
- Kubernetes liveness/readiness probes
- Grafana alerting rules
- External monitoring dashboards
- CI/CD health verification
```

---

## ⚡ CONSIDERAR SI HAY TIEMPO (1-2 días)

### 7. **Refactor Stabilization Wrapping para ser Explícito** 🟡 [2 horas]

**Archivo**: `app/builder.py`

**Problema**: Asume que `sinks[0]` es MQTT sink basado en priority implícito.

**Opción A - Buscar por nombre** (Más simple):

```python
def wrap_sinks_with_stabilization(self, sinks: List[Callable]) -> List[Callable]:
    """
    Wrappea MQTT sink con stabilization.

    Note:
        Busca explícitamente el MQTT sink por nombre en lugar de asumir posición.
    """
    if self.config.STABILIZATION_MODE == 'none':
        self.stabilizer = None
        return sinks

    # Buscar MQTT sink explícitamente
    mqtt_sink_idx = None
    for i, sink in enumerate(sinks):
        # MQTT sink tiene __name__ == 'mqtt_sink' (set by create_mqtt_sink)
        if hasattr(sink, '__name__') and 'mqtt' in sink.__name__.lower():
            mqtt_sink_idx = i
            break

    if mqtt_sink_idx is None:
        raise ValueError(
            "No MQTT sink found to wrap with stabilization. "
            "Ensure SinkFactory creates MQTT sink with recognizable name."
        )

    logger.info(f"Found MQTT sink at index {mqtt_sink_idx}")

    from ..inference.stabilization import create_stabilization_sink

    # Crear stabilizer
    self.stabilizer = StrategyFactory.create_stabilization_strategy(self.config)

    # Wrap MQTT sink
    mqtt_sink = sinks[mqtt_sink_idx]
    stabilized_sink = create_stabilization_sink(
        stabilizer=self.stabilizer,
        downstream_sink=mqtt_sink,
    )

    # Reconstruir lista (immutable)
    new_sinks = (
        sinks[:mqtt_sink_idx] +
        [stabilized_sink] +
        sinks[mqtt_sink_idx+1:]
    )

    logger.info(
        "Stabilization wrapper complete",
        extra={
            "component": "builder",
            "event": "stabilization_wrap_complete",
            "stabilization_mode": self.config.STABILIZATION_MODE,
            "mqtt_sink_index": mqtt_sink_idx
        }
    )
    return new_sinks
```

**Cambio en** `data/publishers.py` (agregar `__name__`):

```python
def create_mqtt_sink(data_plane: MQTTDataPlane) -> Callable:
    """Factory para MQTT sink"""
    def mqtt_sink(predictions, video_frame):
        data_plane.publish_detection(predictions, video_frame)

    mqtt_sink.__name__ = 'mqtt_sink'  # ← Agregar esto
    return mqtt_sink
```

**Beneficios**:
- ✅ Explícito en lugar de implícito
- ✅ Fail-fast si MQTT sink no existe
- ✅ Robusto ante cambios de priority

**Test**:
- Cambiar priority de MQTT sink a 10
- Verificar que stabilization sigue funcionando

---

### 8. **Agregar `__version__` al Package** 📄 [30 min]

**Archivo**: `adeline/__init__.py`

**Agregar**:
```python
"""
Adeline Inference Pipeline
==========================

Fall detection system for geriatric residences.
"""

__version__ = "3.0.0"
__author__ = "Visiona Team"

# Re-exports para API pública
from .config import PipelineConfig, AdelineConfig

__all__ = [
    '__version__',
    'PipelineConfig',
    'AdelineConfig',
]
```

**Uso en health check**:
```python
from adeline import __version__

health['version'] = __version__
```

---

## 🎯 PLANIFICAR PARA SPRINT SIGUIENTE (3-5 días)

### 9. **Event Sourcing para Stabilization** 🚀 [3-4 días]

**Descripción**: Ver INFORME_CONSULTORIA_DISENIO.md, Parte 3, sección "Event Sourcing"

**Criterio de decisión**:
- ✅ Implementar SI debugging de stabilization se vuelve difícil
- ✅ Implementar SI necesitamos audit trail para compliance
- ❌ POSTPONER si stabilization actual funciona bien

**Archivos nuevos**:
- `inference/stabilization/events.py` - Event classes
- `inference/stabilization/event_sourced.py` - EventSourcedStabilizer
- `tests/test_event_sourcing.py` - Tests

---

### 10. **Structured Metrics Collector** 📊 [2-3 días]

**Descripción**: Ver INFORME_CONSULTORIA_DISENIO.md, Parte 3, sección "Structured Metrics"

**Archivos nuevos**:
- `metrics/__init__.py`
- `metrics/collector.py` - MetricsCollector class
- `metrics/exporters.py` - Prometheus/JSON exporters

**Integración**:
- Controller registra métricas en cada frame
- MQTT command `metrics_export` retorna formato Prometheus

---

## 📝 BACKLOG - NO URGENTE

### 11. **Factory Instances en lugar de Static Methods** 🟢 [2 días]

**Trigger**: SOLO si necesitamos:
- Dependency injection en factories
- Cachear resultados de creación
- Mockear factories en tests

**Recomendación**: Dejar como está hasta que necesitemos estas features.

---

### 12. **Protocol Types para todas las interfaces** 🟡 [3 días]

**Trigger**: Si mypy strict mode se activa en todo el proyecto

**Archivos**:
- `app/protocols.py` - Definir todos los Protocols
- Refactor gradual de `Any` types

---

## 📋 CHECKLIST DE IMPLEMENTACIÓN

### Sprint Actual - Quick Wins

- [ ] **Código**
  - [ ] Fix type hints con `TYPE_CHECKING` (app/builder.py)
  - [ ] Best-effort cleanup con try/except (app/controller.py)
  - [ ] Health check endpoint (app/controller.py, control/registry.py)
  - [ ] Agregar `__name__` a mqtt_sink (data/publishers.py)

- [ ] **Wiki**
  - [ ] Aclarar ROI square constraint (1.1  Core Concepts.md)
  - [ ] Documentar sink priority values (5.4 Output-Sinks.md)
  - [ ] Documentar health check command (4.3  Command Reference.md)

- [ ] **Testing**
  - [ ] Test manual de cleanup con broker caído
  - [ ] Test health check via mosquitto
  - [ ] Compilar con mypy después de type hints
  - [ ] Run test suite completo: `pytest -v`

### Sprint Siguiente - Planificado

- [ ] **Código**
  - [ ] Refactor stabilization wrapping explícito
  - [ ] Agregar `__version__` al package
  - [ ] (Condicional) Event sourcing si debugging lo amerita
  - [ ] (Condicional) Structured metrics si se necesita Prometheus

---

## 🎸 FILOSOFÍA DE IMPLEMENTACIÓN

**Pragmatismo > Purismo**:
- ✅ Implementar quick wins que agregan valor inmediato
- ✅ Postponer features "nice-to-have" hasta que sean necesarias
- ✅ Testing manual para quick wins, automated tests para features grandes

**"El diablo sabe por diablo, no por viejo"**:
- Los patterns aplicados tienen propósito claro
- No sobre-diseñar soluciones a problemas que no tenemos
- YAGNI aplicado rigurosamente

**"Complejidad por diseño, no por accidente"**:
- Type hints mejoran diseño (contrato claro)
- Error handling previene complejidad accidental (bugs sutiles)
- Health check es diseño intencional (observability)

---

## 📊 MÉTRICAS DE ÉXITO

**Quick Wins implementados**:
- ✅ Mypy pasa sin errores en `app/builder.py`
- ✅ Cleanup funciona aunque broker esté caído
- ✅ Health check responde correctamente
- ✅ Wiki sincronizada con código (100%)

**Timeline**:
- Día 1: Items 1-3 (código)
- Día 2: Items 4-6 (wiki) + testing
- Día 3: (Opcional) Items 7-8 si hay tiempo

**Owner**: Ernesto + Gaby (pair programming)

---

## 🚀 SIGUIENTE SESIÓN

**Prioridad 1**: Implementar Quick Wins 1-3 (código)
**Prioridad 2**: Actualizar wiki (4-6)
**Prioridad 3**: Testing manual

¿Arrancamos con type hints? 🎸
