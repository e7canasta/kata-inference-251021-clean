# Complejidad por Diseño - Adeline

## Principio Core

**La complejidad se ataca por diseño, no por código complicado.**

## Estrategias de Diseño

### 1. Separación de Responsabilidades

```
Control Plane (QoS 1)     Data Plane (QoS 0)
     ↓                           ↓
  Comandos                  Detecciones
  Confiable                 Performance
     ↓                           ↓
Pipeline Controller
     ↓
InferencePipeline
```

**Beneficio**: Cada plano tiene garantías propias. Control es confiable, Data es rápido.

### 2. Factory Pattern para Variabilidad

```python
# ROI Strategy
roi_mode = "none" | "adaptive" | "fixed"
strategy = create_roi_strategy(mode)

# Stabilization Strategy
stabilization_mode = "none" | "temporal"
stabilizer = create_stabilization_strategy(mode)
```

**Beneficio**: Agregar nuevas estrategias sin tocar código existente. La complejidad está en elegir, no en implementar.

### 3. Configuration-Driven Behavior

```yaml
# Toda la lógica de negocio está en config, no hardcoded
roi_strategy:
  mode: adaptive
  adaptive:
    margin: 0.2
    smoothing: 0.3
```

**Beneficio**: Cambiar comportamiento sin recompilar. La complejidad está en el diseño del config schema.

### 4. Lazy Loading with Enforced Order

```python
# ANTES (frágil - depende de disciplina)
disable_models_from_config()  # Debe ir ANTES
from inference import InferencePipeline  # Puede romperse con refactor

# AHORA (enforced - garantizado por diseño)
from adeline.inference.loader import InferenceLoader
inference = InferenceLoader.get_inference()  # Auto-disable
InferencePipeline = inference.InferencePipeline
```

**Beneficio**: Orden enforced por diseño, no por comentarios. La complejidad está en el loader, que es explícito.

### 5. Multi-Sink Composition

```python
pipeline.on_prediction = multi_sink(
    mqtt_sink,        # Publicar vía MQTT
    visualization_sink # Mostrar en OpenCV
)
```

**Beneficio**: Composición funcional. Agregar sinks sin modificar pipeline. La complejidad está en la orquestación.

### 6. Builder Pattern for Construction

```python
# Separar orquestación de construcción
class PipelineBuilder:
    def build_inference_handler(self, config):
        return InferenceHandlerFactory.create(config)

    def build_sinks(self, data_plane, roi_state, handler):
        return SinkFactory.create_sinks(...)

    def build_pipeline(self, handler, sinks, watchdog):
        return InferencePipeline.init(...)

# Controller solo orquesta
class Controller:
    def setup(self):
        handler, roi = self.builder.build_inference_handler()
        sinks = self.builder.build_sinks(data_plane, roi, handler)
        self.pipeline = self.builder.build_pipeline(handler, sinks, watchdog)
```

**Beneficio**: SRP enforced. Builder construye, Controller orquesta, Factories especializan.

### 7. Registry Pattern for Explicit Commands

```python
# Comandos explícitos, no callbacks opcionales
registry = CommandRegistry()
registry.register('pause', handler_pause, "Pausa procesamiento")
registry.register('stop', handler_stop, "Detiene pipeline")

# Condicionales explícitos
if handler.supports_toggle:
    registry.register('toggle_crop', handler_toggle, "Toggle ROI")

# Validación automática
registry.execute('pause')  # OK
registry.execute('invalid')  # CommandNotAvailableError
```

**Beneficio**: Comandos descubribles. Validación centralizada. La complejidad está en el registry.

### 8. Publisher Pattern for Business Logic Separation

```python
# Separar infraestructura de lógica de negocio
class DetectionPublisher:
    def format_message(self, predictions, video_frame) -> Dict:
        # Business logic: estructura de detecciones
        return {"detections": [...], "roi_metrics": {...}}

class MQTTDataPlane:
    def __init__(self):
        self.detection_publisher = DetectionPublisher()  # Business logic

    def publish_inference(self, predictions, video_frame):
        message = self.detection_publisher.format_message(...)  # Delega formateo
        self.client.publish(self.data_topic, json.dumps(message))  # Solo infra
```

**Beneficio**: DataPlane es canal puro (MQTT). Publisher es lógica pura (formateo). Fácil testear.

## Patrones Anti-Complejidad

### ✅ Hacer

- **Factory para variantes**: ROI strategies, stabilization strategies
- **Builder para construcción**: Separar orquestación de construcción
- **Registry para comandos**: Explícito, validado, discoverable
- **Publisher para lógica de negocio**: Separar infra (MQTT) de negocio (formato)
- **Config para behavior**: Separar "qué hacer" de "cómo hacerlo"
- **Planes separados**: Control (confiable) vs Data (performance)
- **Composition over modification**: Multi-sink pattern
- **Enforce por diseño**: Loader, Registry, ABC (no confiar en disciplina)

### ❌ Evitar

- **God objects**: Un objeto que hace todo (resuelto con Builder)
- **Hardcoded logic**: `if mode == "adaptive"` en 10 lugares (usar Factory)
- **Tight coupling**: Control plane que publique datos (usar Publisher)
- **Magic initialization**: Imports frágiles (resuelto con InferenceLoader)
- **Callbacks opcionales**: No saber qué está disponible (resuelto con Registry)
- **State mutation directa**: Usar métodos enable/disable (encapsulación)

## Decisiones de Diseño Clave

### Control vs Data Plane
**Problema**: MQTT único no diferencia criticidad
**Solución**: Dos planes, dos QoS, dos responsabilidades

### Factory para Strategies
**Problema**: ROI y stabilization tienen múltiples implementaciones
**Solución**: Factory pattern + config para elegir

### Config-Driven
**Problema**: Comportamiento hardcoded es inflexible
**Solución**: YAML config con validación temprana

### Model Disabling
**Problema**: Import de `inference` carga modelos pesados, orden frágil
**Solución**: InferenceLoader con lazy loading y disable automático

### Builder for Construction
**Problema**: Controller era God Object (560 líneas, demasiadas responsabilidades)
**Solución**: PipelineBuilder separa construcción de orquestación

### Command Registry
**Problema**: Callbacks opcionales, comandos no descubribles
**Solución**: CommandRegistry con registro explícito y validación

### Publisher Pattern
**Problema**: DataPlane conocía lógica de negocio (formato de mensajes)
**Solución**: DetectionPublisher y MetricsPublisher separan infra de negocio

## Resultado

**Complejidad controlada** (Post-Refactoring v2.0):
- Fácil agregar nuevas estrategias (factory)
- Fácil cambiar comportamiento (config)
- Fácil debuggear (separación clara)
- Fácil testear (cada componente aislado)
- Fácil extender (builder, registry, publisher)
- Fácil refactorizar (enforced by design, no discipline)

**Código simple, arquitectura sólida.**

**Score de diseño:**
- v1.0 (pre-refactoring): 7.5/10
- v2.0 (post-refactoring): 9.0/10

Ver CONSULTORIA_DISEÑO.md para análisis detallado.
