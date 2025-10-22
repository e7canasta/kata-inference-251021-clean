# Consultoría de Diseño - Adeline

## Contexto

Sistema de inferencia YOLO con control MQTT. Principio: **"La complejidad se ataca por diseño"**.

---

## 1. FORTALEZAS DEL DISEÑO

### 1.1 Separación Control/Data Plane ⭐⭐⭐⭐⭐

**Excelente decisión arquitectónica.**

```python
# Control Plane: QoS 1 (confiable)
control_plane.on_stop = self._handle_stop

# Data Plane: QoS 0 (performance)
data_plane.publish_inference(predictions)
```

**Por qué funciona:**
- Garantías diferentes según criticidad (control vs datos)
- Dos clientes MQTT independientes (fallo aislado)
- Responsabilidades claramente separadas

**Impacto:** Si Data Plane se satura, Control sigue funcionando. Comando STOP siempre funciona.

---

### 1.2 Factory Pattern para Estrategias ⭐⭐⭐⭐⭐

**Bien aplicado en ROI y Stabilization.**

```python
# ROI Strategy Factory
roi_state = validate_and_create_roi_strategy(
    mode=config.ROI_MODE,  # "none" | "adaptive" | "fixed"
    config=roi_config,
)

# Stabilization Strategy Factory
stabilizer = create_stabilization_strategy(stab_config)
```

**Por qué funciona:**
- Validación centralizada en factory (`validate_and_create_roi_strategy`)
- Fácil agregar nuevas estrategias sin tocar código existente
- Configuración valida antes de construir

**Ejemplo de extensibilidad:**
```yaml
# Agregar "grid" strategy solo requiere:
# 1. Crear GridROIState
# 2. Agregar case en factory
# 3. CERO cambios en controller
roi_strategy:
  mode: grid  # Nueva estrategia
```

---

### 1.3 Configuration-Driven Behavior ⭐⭐⭐⭐

**Todo configurable desde YAML.**

```python
# config.py centraliza TODA la lógica de carga
config = PipelineConfig("config/adeline/config.yaml")

# Controller NO tiene hardcoded logic
if config.ROI_MODE == 'adaptive':
    # Construir desde config
elif config.ROI_MODE == 'fixed':
    # Construir desde config
```

**Beneficio:** Cambiar comportamiento sin recompilar. Testear diferentes configs sin cambiar código.

---

### 1.4 Multi-Sink Composition ⭐⭐⭐⭐⭐

**Patrón funcional bien aplicado.**

```python
# Composición de sinks
pipeline.on_prediction = multi_sink(
    mqtt_sink,           # Publicar MQTT
    roi_update_sink,     # Actualizar ROI state
    visualization_sink,  # OpenCV display
)
```

**Por qué funciona:**
- No modifica pipeline (extensión, no modificación)
- Agregar/quitar sinks sin tocar lógica core
- Cada sink es independiente (SRP)

---

### 1.5 Abstracción de Estrategias con ABC ⭐⭐⭐⭐

**Stabilization usa ABC correctamente.**

```python
class BaseDetectionStabilizer(ABC):
    @abstractmethod
    def process(self, detections, source_id) -> List[Dict]:
        pass

    @abstractmethod
    def reset(self, source_id):
        pass
```

**Beneficio:** Contract explícito. Nuevas estrategias DEBEN implementar interface.

---

## 2. DEBILIDADES Y ÁREAS DE MEJORA

### 2.1 God Controller ⚠️⚠️⚠️

**Problema:** `InferencePipelineController` tiene demasiadas responsabilidades.

**Evidencia:**
```python
class InferencePipelineController:
    def setup(self):
        # 1. Configurar Data Plane
        self.data_plane = MQTTDataPlane(...)

        # 2. Configurar Stabilization
        if self.config.STABILIZATION_MODE != 'none':
            self.stabilizer = create_stabilization_strategy(...)

        # 3. Configurar ROI Strategy (lógica condicional compleja)
        if self.config.ROI_MODE in ['adaptive', 'fixed']:
            # 50 líneas de lógica de decisión
            if self.config.ROI_MODE == 'adaptive':
                self.inference_handler = AdaptiveInferenceHandler(...)
            elif self.config.ROI_MODE == 'fixed':
                self.inference_handler = FixedROIInferenceHandler(...)

        # 4. Configurar Control Plane
        self.control_plane = MQTTControlPlane(...)

        # 5. Signal handling
        # 6. Cleanup
        # 7. Logging
```

**Violación:** Single Responsibility Principle. Controller conoce detalles de:
- MQTT setup
- ROI strategy selection
- Stabilization wrapping
- Sink composition
- Signal handling

**Impacto:**
- Difícil testear (muchas dependencias)
- Cambios en ROI requieren tocar Controller
- setup() tiene >200 líneas

**Recomendación:**

```python
# Crear PipelineBuilder
class PipelineBuilder:
    def build_inference_handler(self, config):
        # Lógica de ROI strategies
        pass

    def build_sinks(self, config, data_plane, roi_state):
        # Lógica de sink composition
        pass

class InferencePipelineController:
    def __init__(self, config, builder: PipelineBuilder):
        self.builder = builder

    def setup(self):
        # Delega construcción a builder
        self.inference_handler = self.builder.build_inference_handler(config)
        self.sinks = self.builder.build_sinks(config, data_plane, roi_state)
```

---

### 2.2 Acoplamiento Temporal Frágil ⚠️⚠️⚠️

**Problema:** Orden de imports CRÍTICO pero no enforced.

**Evidencia:**
```python
# app/controller.py líneas 22-28
from ..config import disable_models_from_config

# Disable models ANTES de imports
disable_models_from_config()  # <-- SI ESTO SE MUEVE, EXPLOTA

# NOW import inference (warnings should be suppressed)
from inference import InferencePipeline
```

**Por qué es frágil:**
1. Un refactor automático puede reordenar imports
2. No hay nada que impida hacer `from inference import X` en otro archivo
3. Docstring dice "ANTES" pero no hay enforcement

**Impacto:**
- Warnings de ModelDependencyMissing si se rompe el orden
- Memoria inflada cargando modelos innecesarios
- Depende de disciplina del desarrollador

**Recomendación:**

```python
# config.py - Crear lazy loader
class InferenceLoader:
    _inference_module = None

    @classmethod
    def get_inference(cls):
        if cls._inference_module is None:
            disable_models_from_config()  # Automático
            import inference
            cls._inference_module = inference
        return cls._inference_module

# Usage
InferenceLoader.get_inference().InferencePipeline(...)
```

Ahora el orden es **enforced por diseño**, no por comentarios.

---

### 2.3 Conditional Callbacks ⚠️⚠️

**Problema:** Callbacks opcionales según modo.

**Evidencia:**
```python
# controller.py líneas 295-301
# Callback TOGGLE_CROP solo para adaptive
if self.config.ROI_MODE == 'adaptive':
    self.control_plane.on_toggle_crop = self._handle_toggle_crop

# Callback STABILIZATION_STATS solo si habilitado
if self.config.STABILIZATION_MODE != 'none':
    self.control_plane.on_stabilization_stats = self._handle_stabilization_stats
```

**Por qué es problemático:**
1. Control Plane no sabe qué callbacks están disponibles
2. Si envías `toggle_crop` en modo fixed, warning genérico
3. Lógica de negocio distribuida (parte en controller, parte en handler)

**Evidencia del problema:**
```python
# control/plane.py línea 158
elif command == 'toggle_crop':
    if self.on_toggle_crop:
        # Ejecuta
    else:
        logger.warning("on_toggle_crop callback no configurado")
```

Control Plane NO SABE si toggle_crop es válido para el modo actual.

**Recomendación:**

```python
# Crear CommandRegistry
class CommandRegistry:
    def __init__(self):
        self._commands = {}

    def register(self, command: str, handler: Callable):
        self._commands[command] = handler

    def execute(self, command: str):
        if command not in self._commands:
            raise CommandNotAvailableError(f"Command '{command}' not available in current mode")
        return self._commands[command]()

# Usage
registry = CommandRegistry()
registry.register('pause', self._handle_pause)
registry.register('resume', self._handle_resume)

if config.ROI_MODE == 'adaptive':
    registry.register('toggle_crop', self._handle_toggle_crop)

# Control Plane usa registry
self.control_plane.set_command_registry(registry)
```

Ahora los comandos disponibles son **explícitos** y **validables**.

---

### 2.4 Falta de Abstracción Común en Handlers ⚠️⚠️

**Problema:** `AdaptiveInferenceHandler` y `FixedROIInferenceHandler` NO comparten interface.

**Evidencia:**
```python
# adaptive.py
class AdaptiveInferenceHandler:
    def __init__(self, model, inference_config, roi_state, ...):
        self.enabled = True  # Toggle dinámico

    def __call__(self, video_frames):
        # ...

# fixed.py
class FixedROIInferenceHandler:
    def __init__(self, model, inference_config, roi_state, ...):
        self.enabled = True  # Siempre True (no toggle)

    def __call__(self, video_frames):
        # ...
```

Ambos son "duck typed" pero NO hay ABC.

**Por qué es problemático:**
1. No hay contrato explícito
2. No puedes garantizar que nuevos handlers sean compatibles
3. Controller asume `.enabled` existe, pero no está enforced

**Recomendación:**

```python
class BaseInferenceHandler(ABC):
    @abstractmethod
    def __call__(self, video_frames):
        """Process video frames and return predictions"""
        pass

    @property
    @abstractmethod
    def enabled(self) -> bool:
        """Whether handler is currently enabled"""
        pass

    @property
    def supports_toggle(self) -> bool:
        """Whether handler supports dynamic enable/disable"""
        return False  # Default: no toggle

class AdaptiveInferenceHandler(BaseInferenceHandler):
    @property
    def supports_toggle(self) -> bool:
        return True  # Adaptive sí soporta toggle

class FixedROIInferenceHandler(BaseInferenceHandler):
    @property
    def supports_toggle(self) -> bool:
        return False  # Fixed no soporta toggle
```

Ahora el controller puede **validar** antes de registrar toggle_crop:

```python
if handler.supports_toggle:
    control_plane.on_toggle_crop = self._handle_toggle_crop
```

---

### 2.5 State Mutation Directa ⚠️

**Problema:** `inference_handler.enabled` se muta directamente.

**Evidencia:**
```python
# controller.py línea 390
def _handle_toggle_crop(self):
    # Toggle estado
    new_state = not self.inference_handler.enabled
    self.inference_handler.enabled = new_state  # <-- Mutación directa
```

**Por qué es problemático:**
1. No hay validación (qué pasa si enabled no existe?)
2. No hay event/callback cuando cambia
3. Difícil testear (estado mutable)

**Recomendación:**

```python
class AdaptiveInferenceHandler:
    def enable(self):
        self._enabled = True
        logger.info("Adaptive ROI enabled")

    def disable(self):
        self._enabled = False
        self.roi_state.reset()  # Automático
        logger.info("Adaptive ROI disabled")

    @property
    def enabled(self) -> bool:
        return self._enabled

# Controller
def _handle_toggle_crop(self):
    if self.inference_handler.enabled:
        self.inference_handler.disable()
    else:
        self.inference_handler.enable()
```

Ahora el handler **controla su propio ciclo de vida** (encapsulación).

---

### 2.6 Cleanup Agresivo con os._exit(0) ⚠️

**Problema:** Termina proceso sin cleanup de Python.

**Evidencia:**
```python
# controller.py líneas 522-527
def cleanup(self):
    # ... cleanup code ...

    # Forzar salida inmediata (mata threads)
    import os
    os._exit(0)  # <-- Bypass Python cleanup
```

**Por qué es problemático:**
1. `os._exit(0)` NO ejecuta `finally` blocks
2. NO ejecuta context managers (`with` statements)
3. NO permite que threads hagan cleanup
4. Recursos pueden quedar sin liberar (file handles, sockets)

**Contexto:** Comentario dice "matar threads non-daemon del pipeline inmediatamente".

**Recomendación:**

```python
def cleanup(self):
    # Cleanup actual
    if self.pipeline:
        self.pipeline.terminate()
        self.pipeline.join(timeout=5.0)  # Esperar más tiempo

    if self.control_plane:
        self.control_plane.disconnect()

    if self.data_plane:
        self.data_plane.disconnect()

    # Si REALMENTE necesitas forzar (último recurso):
    # threading.enumerate() para matar threads específicos
    # Pero NO os._exit()
```

Si hay threads bloqueados, identifica **por qué** están bloqueados, no los mates a la fuerza.

---

### 2.7 Validación Distribuida ⚠️

**Problema:** Validación en múltiples lugares.

**Evidencia:**
```python
# config.py - Primera validación
if not config_file.exists():
    raise FileNotFoundError("Config file not found")

# base.py - Segunda validación
def validate_and_create_roi_strategy(...):
    if mode not in ["none", "adaptive", "fixed"]:
        raise ValueError(f"Invalid ROI mode: '{mode}'")

    if not (0.0 <= config.adaptive_margin <= 1.0):
        raise ValueError(...)

# fixed.py - Tercera validación (redundante)
def __init__(self, x_min, y_min, x_max, y_max):
    # Validación básica (ya validado en config, pero doble check)
    if not (0.0 <= x_min < x_max <= 1.0):
        raise ValueError(...)
```

**Por qué es problemático:**
1. Lógica duplicada (validación en 3 lugares)
2. Difícil mantener consistencia
3. Mensajes de error inconsistentes

**Recomendación:**

```python
# Usar pydantic para validación centralizada
from pydantic import BaseModel, validator, Field

class ROIStrategyConfig(BaseModel):
    mode: Literal["none", "adaptive", "fixed"]

    # Adaptive
    adaptive_margin: float = Field(default=0.2, ge=0.0, le=1.0)
    adaptive_smoothing: float = Field(default=0.3, ge=0.0, le=1.0)

    # Fixed
    fixed_x_min: float = Field(default=0.2, ge=0.0, lt=1.0)
    fixed_x_max: float = Field(default=0.8, gt=0.0, le=1.0)

    @validator('fixed_x_max')
    def x_max_greater_than_x_min(cls, v, values):
        if 'fixed_x_min' in values and v <= values['fixed_x_min']:
            raise ValueError('x_max must be > x_min')
        return v

# Validación automática al construir
config = ROIStrategyConfig(**yaml_data)  # Valida TODO de una vez
```

---

## 3. DECISIONES Y TRADE-OFFS

### 3.1 ¿Por qué Multi-Sink en vez de Observer Pattern?

**Decisión:** Usar `multi_sink(sinks=[...])` funcional.

**Trade-off:**
- ✅ Simple, funcional, fácil de componer
- ❌ No permite agregar/quitar sinks dinámicamente durante ejecución

**Contexto:** Para Adeline, sinks son estáticos (configurados al inicio). Multi-sink es suficiente.

**Si necesitaras dinámico:**
```python
class SinkManager:
    def __init__(self):
        self._sinks = []

    def add_sink(self, sink):
        self._sinks.append(sink)

    def remove_sink(self, sink):
        self._sinks.remove(sink)

    def __call__(self, predictions, video_frames):
        for sink in self._sinks:
            sink(predictions, video_frames)
```

---

### 3.2 ¿Por qué QoS 1 para Control y QoS 0 para Data?

**Decisión correcta basada en requisitos.**

**Análisis:**

| Aspecto | Control (QoS 1) | Data (QoS 0) |
|---------|-----------------|--------------|
| **Criticidad** | Alta (stop debe llegar) | Baja (un frame perdido es OK) |
| **Frecuencia** | Baja (~1 msg/min) | Alta (~2 FPS = 120 msg/min) |
| **Latencia** | Tolerante | Crítica |
| **Overhead** | Aceptable (ACK small) | Inaceptable (doblaría tráfico) |

**Resultado:**
- Control: Confiable (always delivered)
- Data: Performance (fire-and-forget)

**Beneficio:** Sistema degrada gracefully. Si broker se satura, data se pierde pero control funciona.

---

### 3.3 ¿Por qué FixedROI reutiliza adaptive_roi_inference()?

**Decisión:** `FixedROIInferenceHandler` llama `adaptive_roi_inference()`.

**Evidencia:**
```python
# fixed.py línea 164
def __call__(self, video_frames):
    return adaptive_roi_inference(
        roi_state=self.roi_state,  # FixedROIState compatible
        ...
    )
```

**Trade-off:**
- ✅ DRY (no duplicar lógica de crop/inference)
- ✅ FixedROIState y ROIState comparten interface (duck typing)
- ❌ Nombre confuso (`adaptive_roi_inference` para fixed?)
- ❌ Acoplamiento implícito (si cambias adaptive, afecta fixed)

**Recomendación:**
```python
# Renombrar para claridad
def roi_based_inference(roi_state, ...):
    """Generic ROI-based inference (works with any ROI strategy)"""
    pass

# Usage
adaptive_inference = partial(roi_based_inference, roi_state=adaptive_state)
fixed_inference = partial(roi_based_inference, roi_state=fixed_state)
```

---

## 4. RECOMENDACIONES PRIORIZADAS

### 🔥 CRÍTICO (hacer YA)

1. **Eliminar `os._exit(0)`** en cleanup
   - Riesgo: Recursos sin liberar, corrupción de estado
   - Fix: Identificar threads bloqueados y arreglar raíz del problema

2. **Enforced initialization order** para model disabling
   - Riesgo: Refactor rompe orden de imports
   - Fix: Lazy loader con disable automático

### ⚠️ IMPORTANTE (planificar)

3. **Extraer PipelineBuilder** del Controller
   - Beneficio: Testeable, SRP, fácil mantener
   - Esfuerzo: ~2-3 horas

4. **Crear BaseInferenceHandler ABC**
   - Beneficio: Contract explícito, type safety
   - Esfuerzo: ~1 hora

5. **CommandRegistry para Control Plane**
   - Beneficio: Comandos explícitos, mejor UX
   - Esfuerzo: ~2 horas

### 💡 DESEABLE (cuando haya tiempo)

6. **Migrar a Pydantic** para validación
   - Beneficio: Validación centralizada, mejor mensajes de error
   - Esfuerzo: ~4 horas

7. **Encapsular state mutation** (enable/disable)
   - Beneficio: Mejor encapsulación
   - Esfuerzo: ~1 hora

---

## 5. PATRONES POSITIVOS A MANTENER

### ✅ Sigue haciendo esto:

1. **Factory para strategies** - Excelente extensibilidad
2. **Config-driven behavior** - Evita hardcoding
3. **Separación Control/Data** - Garantías diferentes
4. **ABC para abstractions** - Contracts explícitos (donde está)
5. **Logging exhaustivo** - Debug friendly
6. **Dataclasses para state** - Inmutabilidad, claridad

---

## 6. ANTI-PATRONES A EVITAR

### ❌ No hagas esto:

1. **God objects** - Controller ya está grande
2. **Temporal coupling** - Orden de imports frágil
3. **os._exit()** - Cleanup agresivo
4. **Validación distribuida** - Centralizar en una sola capa
5. **State mutation directa** - Usar métodos
6. **Callbacks opcionales** - Registry explícito mejor

---

## 7. ARQUITECTURA IDEAL (NORTE)

```
┌─────────────────────────────────────────────────┐
│           InferencePipelineController           │
│  Responsabilidad: Orquestación + Lifecycle      │
└────────────┬────────────────────────────────────┘
             │
             ├──> PipelineBuilder
             │    Responsabilidad: Construcción
             │    ├─> InferenceHandlerFactory
             │    ├─> SinkFactory
             │    └─> StrategyFactory
             │
             ├──> ControlPlane (QoS 1)
             │    ├─> CommandRegistry (explícito)
             │    └─> StatusPublisher
             │
             ├──> DataPlane (QoS 0)
             │    ├─> DetectionPublisher
             │    └─> MetricsPublisher
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

**Beneficios:**
- SRP en cada componente
- Fácil testear (mocks)
- Extensible sin modificar
- Contracts explícitos (ABC)

---

## 8. CONCLUSIÓN

### Lo que está EXCELENTE:
- Separación Control/Data Plane
- Factory patterns
- Configuration-driven
- Multi-sink composition

### Lo que necesita MEJORA:
- God Controller (refactor a Builder)
- Initialization order frágil (lazy loader)
- Cleanup agresivo (eliminar os._exit)
- Falta ABC en handlers

### Resultado:
**Diseño sólido con algunos puntos de fricción que son fáciles de arreglar.**

La arquitectura base es **correcta**. Los problemas son de **implementación**, no de diseño fundamental.

**Score: 7.5/10**
- Con los fixes propuestos: **9/10**

---

## 9. POST-REFACTORING UPDATE

### Estado: REFACTORING COMPLETADO ✅

**Fecha**: 2025-10-22
**Commits**: 5a9c29d → 226c413 (FASES 1-7)
**Resultado**: Score mejorado de **7.5/10** a **9.0/10**

---

### Problemas Resueltos

#### ✅ 2.1 God Controller (Crítico ⚠️⚠️⚠️)

**RESUELTO en FASES 2-4:**

**Antes:**
```python
class InferencePipelineController:
    def setup(self):  # 250+ líneas
        # Lógica de ROI inline
        if config.ROI_MODE == 'adaptive':
            # 50 líneas...
        # Lógica de sinks inline
        # Lógica de stabilization inline
```

**Después:**
```python
class InferencePipelineController:
    def __init__(self, config):
        self.builder = PipelineBuilder(config)  # Delegación

    def setup(self):  # 105 líneas (58% reducción)
        handler, roi = self.builder.build_inference_handler()
        sinks = self.builder.build_sinks(...)
        self.pipeline = self.builder.build_pipeline(...)
```

**Evidencia:**
- FASE 2: Factories (InferenceHandlerFactory, SinkFactory, StrategyFactory)
- FASE 3: PipelineBuilder orquesta factories
- FASE 4: Controller refactorizado (-109 líneas netas)
- Commit: `233f789`

**Impacto:**
- ✅ SRP enforced
- ✅ Testeable (mocks)
- ✅ Mantenible (cambios localizados)

---

#### ✅ 2.2 Acoplamiento Temporal Frágil (Crítico ⚠️⚠️⚠️)

**RESUELTO en FASE 7:**

**Antes:**
```python
# ❌ Orden crítico, frágil, dependiente de disciplina
from ..config import disable_models_from_config
disable_models_from_config()  # SI ESTO SE MUEVE, EXPLOTA
from inference import InferencePipeline
```

**Después:**
```python
# ✅ Orden irrelevante, enforced por diseño
from ..inference.loader import InferenceLoader
inference = InferenceLoader.get_inference()  # Auto-disable
InferencePipeline = inference.InferencePipeline
```

**Evidencia:**
- FASE 7: InferenceLoader con singleton + lazy loading
- Archivo: `inference/loader.py`
- Commit: `226c413`

**Impacto:**
- ✅ Refactoring-safe (auto-formatters no rompen)
- ✅ Design enforcement (no disciplina)
- ✅ No más warnings de ModelDependencyMissing

---

#### ✅ 2.3 Conditional Callbacks (Importante ⚠️⚠️)

**RESUELTO en FASE 5:**

**Antes:**
```python
# ❌ Callbacks opcionales, comandos no descubribles
if config.ROI_MODE == 'adaptive':
    control_plane.on_toggle_crop = self._handle_toggle_crop

# Control Plane no sabe qué callbacks existen
if self.on_toggle_crop:  # Puede ser None
    self.on_toggle_crop()
```

**Después:**
```python
# ✅ Comandos explícitos, validados
registry = control_plane.command_registry
registry.register('pause', self._handle_pause, "Pausa procesamiento")

if handler.supports_toggle:
    registry.register('toggle_crop', self._handle_toggle_crop, "Toggle ROI")

# Validación automática
registry.execute('toggle_crop')  # CommandNotAvailableError si no registrado
```

**Evidencia:**
- FASE 5: CommandRegistry pattern
- Archivos: `control/registry.py`, `control/plane.py`
- Commit: `130f539`

**Impacto:**
- ✅ Comandos descubribles (`registry.available_commands`)
- ✅ Mensajes de error claros
- ✅ Introspección (`registry.get_help()`)

---

#### ✅ 2.4 Falta de Abstracción Común (Importante ⚠️⚠️)

**RESUELTO en FASE 1:**

**Antes:**
```python
# ❌ Duck typing, no contract enforcement
class AdaptiveInferenceHandler:
    def __call__(self, video_frames): pass
    enabled = True  # Asumido, no enforced

class FixedROIInferenceHandler:
    def __call__(self, video_frames): pass
    enabled = True  # Asumido, no enforced
```

**Después:**
```python
# ✅ ABC con contract explícito
class BaseInferenceHandler(ABC):
    @abstractmethod
    def __call__(self, video_frames): pass

    @property
    @abstractmethod
    def enabled(self) -> bool: pass

    @property
    def supports_toggle(self) -> bool:
        return False

class AdaptiveInferenceHandler(BaseInferenceHandler):
    @property
    def supports_toggle(self) -> bool:
        return True  # Adaptive soporta toggle

class FixedROIInferenceHandler(BaseInferenceHandler):
    @property
    def supports_toggle(self) -> bool:
        return False  # Fixed NO soporta toggle
```

**Evidencia:**
- FASE 1: BaseInferenceHandler ABC
- Archivos: `inference/handlers/base.py`, `inference/handlers/standard.py`
- Adaptados: `inference/roi/adaptive.py`, `inference/roi/fixed.py`
- Commit: `5a9c29d`

**Impacto:**
- ✅ Type safety
- ✅ Contract enforcement
- ✅ Refactoring confidence

---

#### ✅ 2.5 State Mutation Directa (Deseable ⚠️)

**RESUELTO en FASE 1:**

**Antes:**
```python
# ❌ Mutación directa, sin validación
def _handle_toggle_crop(self):
    new_state = not self.inference_handler.enabled
    self.inference_handler.enabled = new_state  # Mutación directa
```

**Después:**
```python
# ✅ Métodos con encapsulación
class AdaptiveInferenceHandler:
    def enable(self):
        self._enabled = True
        logger.info("Adaptive ROI enabled")

    def disable(self):
        self._enabled = False
        self.roi_state.reset()  # Automático
        logger.info("Adaptive ROI disabled")

    @property
    def enabled(self) -> bool:
        return self._enabled

# Controller usa métodos
def _handle_toggle_crop(self):
    if self.inference_handler.enabled:
        self.inference_handler.disable()
    else:
        self.inference_handler.enable()
```

**Evidencia:**
- FASE 1: Métodos enable/disable en handlers
- FASE 4: Controller usa métodos
- Commit: `5a9c29d`, `233f789`

**Impacto:**
- ✅ Encapsulación (handler controla lifecycle)
- ✅ Reset automático de ROI al disable
- ✅ Logging centralizado

---

#### ✅ 2.6 Cleanup Agresivo con os._exit(0) (Crítico ⚠️⚠️⚠️)

**RESUELTO en FASE 7:**

**Antes:**
```python
# ❌ Bypass Python cleanup
def cleanup(self):
    # ... cleanup code ...
    import os
    os._exit(0)  # NO ejecuta finally, NO ejecuta context managers
```

**Después:**
```python
# ✅ Cleanup normal con timeouts aumentados
def cleanup(self):
    if self.pipeline and self.is_running:
        self.pipeline.terminate()
        self.pipeline.join(timeout=10.0)  # 10s en lugar de 3s

    if self.control_plane:
        try:
            self.control_plane.disconnect()
        except Exception as e:
            logger.error(...)

    if self.data_plane:
        try:
            self.data_plane.disconnect()
        except Exception as e:
            logger.error(...)

    # ✅ NO os._exit() - Python cleanup normal
```

**Evidencia:**
- FASE 7: Cleanup mejorado
- Archivo: `app/controller.py`
- Commit: `226c413`

**Impacto:**
- ✅ No más procesos zombie
- ✅ Finally blocks se ejecutan
- ✅ Context managers funcionan
- ✅ Recursos liberados correctamente

---

#### 🆕 MEJORA ADICIONAL: Publisher Pattern (FASE 6)

**Problema nuevo identificado durante refactoring:**

DataPlane conocía lógica de negocio (estructura de mensajes).

**Solución:**
```python
# ✅ Separación infraestructura (MQTT) vs negocio (formateo)
class DetectionPublisher:
    def format_message(self, predictions, video_frame) -> Dict:
        # Business logic: estructura de detecciones
        return {"detections": [...], "roi_metrics": {...}}

class MQTTDataPlane:
    def __init__(self):
        self.detection_publisher = DetectionPublisher()
        self.metrics_publisher = MetricsPublisher()

    def publish_inference(self, predictions, video_frame):
        message = self.detection_publisher.format_message(...)  # Delega
        self.client.publish(...)  # Solo infraestructura
```

**Evidencia:**
- FASE 6: Publisher pattern
- Archivos: `data/publishers/detection.py`, `data/publishers/metrics.py`
- Commit: `ad00820`

**Impacto:**
- ✅ Misma separación que Control Plane (consistencia)
- ✅ DataPlane es canal puro (MQTT)
- ✅ Publishers son lógica pura (testeable)

---

### Score Final

**Pre-refactoring (v1.0):** 7.5/10

**Fortalezas mantenidas:**
- ⭐⭐⭐⭐⭐ Separación Control/Data Plane
- ⭐⭐⭐⭐⭐ Factory Pattern para estrategias
- ⭐⭐⭐⭐ Configuration-driven
- ⭐⭐⭐⭐⭐ Multi-sink composition

**Problemas resueltos:**
- ✅ God Controller → Builder pattern
- ✅ Temporal coupling → InferenceLoader
- ✅ Conditional callbacks → CommandRegistry
- ✅ Falta ABC → BaseInferenceHandler
- ✅ State mutation → enable/disable methods
- ✅ Cleanup agresivo → Proper cleanup
- ✅ Business logic en DataPlane → Publisher pattern

**Post-refactoring (v2.0):** 9.0/10

**Nuevos patrones agregados:**
- Builder pattern (construcción separada)
- CommandRegistry (comandos explícitos)
- Publisher pattern (separación infra/negocio)
- InferenceLoader (enforcement por diseño)
- ABC contracts (type safety)

---

### Commits del Refactoring

| Fase | Commit | Descripción |
|------|--------|-------------|
| 1 | 5a9c29d | BaseInferenceHandler ABC |
| 2 | 0b6144d | Factories (Handler, Sink, Strategy) |
| 3 | b702cf6 | PipelineBuilder |
| 4 | 233f789 | Controller refactored (-109 lines) |
| Fix | 701d7c2 | Import fix in SinkFactory |
| 5 | 130f539 | CommandRegistry (Control Plane) |
| 6 | ad00820 | Publisher pattern (Data Plane) |
| 7 | 226c413 | InferenceLoader + cleanup fixes |

---

### Conclusión

**Arquitectura base era correcta (7.5/10).**

Los problemas eran de **implementación**, no de diseño fundamental.

**Con refactoring (9.0/10):**
- Todos los problemas críticos resueltos
- Patrones consistentes en todo el código
- Enforced por diseño (no disciplina)
- Fácil de mantener y extender

**Principio aplicado:** **Complejidad por Diseño**

No agregamos complejidad en el código, sino en la arquitectura.
Código simple, arquitectura sólida.
