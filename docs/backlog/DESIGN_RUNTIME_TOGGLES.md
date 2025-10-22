# Runtime Toggles Architecture Design

**Proyecto:** Adeline v2.0 → v2.5
**Fecha:** 2025-10-22
**Filosofía:** "Complejidad por Diseño - Runtime Flexibility sin Restart"

---

## Executive Summary

**Problema:** Muchos comportamientos requieren reiniciar pipeline para cambiar (ROI, stabilization, visualization, FPS, etc.)

**Solución:** Sistema unificado de toggles dinámicos que permiten cambiar comportamiento en runtime vía MQTT, sin detener pipeline.

**Principio guía:** Toggle como **first-class citizen** - no hacks, no workarounds, diseño arquitectónico limpio.

---

## The Big Picture: Stream Processing Pipeline

### Current Pipeline Architecture

```
                     ┌─────────────────────────────────────────┐
                     │      InferencePipeline (Roboflow)      │
                     │        (Immutable after init)           │
                     └─────────────┬───────────────────────────┘
                                   │
                         Video Frame Stream
                                   │
                                   ↓
┌────────────────────────────────────────────────────────────────────────┐
│                    PROCESSING PIPELINE                                  │
├────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  1. ┌──────────────────────┐                                          │
│     │ InferenceHandler     │  ← Toggle: ROI crop (adaptive only)      │
│     │  - Standard          │                                           │
│     │  - Adaptive ROI ✓    │  🔄 TOGGLEABLE (YA IMPLEMENTADO)        │
│     │  - Fixed ROI         │                                           │
│     └──────────┬───────────┘                                           │
│                │                                                        │
│           Predictions                                                   │
│                │                                                        │
│  2. ┌──────────▼───────────┐                                          │
│     │ Stabilization Layer  │  ← Toggle: Temporal filtering            │
│     │  - None              │                                           │
│     │  - Temporal ⚠️       │  ⚠️ NO TOGGLEABLE (debería serlo)       │
│     │  - IoU Tracking      │                                           │
│     └──────────┬───────────┘                                           │
│                │                                                        │
│         Filtered Predictions                                            │
│                │                                                        │
│  3. ┌──────────▼───────────┐                                          │
│     │   Multi-Sink         │                                           │
│     │                      │                                           │
│     │  A. MQTT Sink        │  ← Toggle: Publishing on/off             │
│     │     (QoS 0) ⚠️       │  ⚠️ NO TOGGLEABLE (debería serlo)       │
│     │                      │                                           │
│     │  B. ROI Update       │  N/A (tied to adaptive ROI)              │
│     │     (adaptive) ✓     │                                           │
│     │                      │                                           │
│     │  C. Visualization ⚠️ │  ← Toggle: Display on/off                │
│     │     (if enabled)     │  ⚠️ NO TOGGLEABLE (debería serlo)       │
│     │                      │                                           │
│     └──────────────────────┘                                           │
│                                                                         │
└────────────────────────────────────────────────────────────────────────┘

     ┌─────────────────────────────────────────────────────┐
     │         MQTT Control Plane (QoS 1)                  │
     │  Commands: pause, resume, stop, toggle_crop, ...   │
     │                                                      │
     │  ⚡ AGREGAR: toggle_stabilization,                  │
     │             toggle_visualization,                   │
     │             toggle_mqtt,                            │
     │             set_fps                                 │
     └─────────────────────────────────────────────────────┘
```

### Toggle Points in Pipeline

**Existen 3 niveles donde se puede hacer toggle:**

#### Level 1: Handler Level (Pre-inference)
```
Video Frame → [Toggle ROI Crop] → Inference → Predictions
```
- **Componente:** InferenceHandler (adaptive)
- **Toggle:** enable_crop / disable_crop
- **Estado actual:** ✅ IMPLEMENTADO
- **Impacto:** Cambia input a modelo (full frame vs cropped)

#### Level 2: Processing Level (Post-inference)
```
Predictions → [Toggle Stabilization] → Filtered Predictions → Sinks
```
- **Componente:** DetectionStabilizer
- **Toggle:** enable_filter / disable_filter
- **Estado actual:** ❌ NO IMPLEMENTADO
- **Impacto:** Cambia output (raw vs filtered detections)

#### Level 3: Sink Level (Output)
```
Predictions → Sink A [Toggle MQTT] → Publish/Skip
                   ├─ Sink B [Toggle Viz] → Display/Skip
                   └─ Sink C [ROI Update] → Update
```
- **Componente:** Individual sinks
- **Toggle:** enable_sink / disable_sink
- **Estado actual:** ❌ NO IMPLEMENTADO
- **Impacto:** Cambia qué outputs se generan

---

## Design Problem: Why Toggles are Hard

### Challenge 1: Pipeline is Immutable

**InferencePipeline.init() es constructor - no puedes cambiar después:**

```python
# NO PUEDES HACER ESTO
pipeline = InferencePipeline.init(max_fps=2.0, ...)
pipeline.set_max_fps(1.0)  # ❌ No existe este método

# Tampoco puedes cambiar sinks dinámicamente
pipeline.add_sink(new_sink)  # ❌ Sinks son tuple inmutable
pipeline.remove_sink(viz_sink)  # ❌ No existe
```

**Por qué es inmutable:**
- Performance: Optimization en construcción
- Thread safety: No locks necesarios
- Simplicity: Constructor único, no state machines complejos

**Implicación:**
- ✅ Toggles **dentro** de componentes (handler, sinks) → Posible
- ❌ Toggles de **estructura** de pipeline → Imposible sin rebuild

### Challenge 2: Sink Composition

**Multi-sink es tuple inmutable:**

```python
# sinks/core.py - Roboflow inference
def multi_sink(predictions, video_frames, sinks: tuple):
    for sink in sinks:  # sinks es TUPLE
        sink(predictions, video_frames)
```

**No puedes:**
- Agregar sink después de construcción
- Remover sink después de construcción
- Reordenar sinks dinámicamente

**Puedes:**
- ✅ Sink puede decidir "skip" internamente (if not enabled: return)
- ✅ Sink puede tener flag mutable (self._enabled)

### Challenge 3: Stabilization Wrapping

**Stabilization es wrapper sobre primer sink:**

```python
# Actual
stabilized_sink = create_stabilization_sink(
    stabilizer=self.stabilizer,
    downstream_sink=mqtt_sink,
)
sinks = [stabilized_sink, roi_sink, viz_sink]

# Si quieres toggle stabilization, ¿cómo?
# Opción A: Stabilizer tiene flag enabled (pass-through)
# Opción B: Unwrap/rewrap sink (difícil, requiere rebuild)
```

**Opción A es más simple y no requiere rebuild.**

---

## Design Solution: Toggleable Component Pattern

### Pattern: Runtime Toggleable via Internal State

**Principio:** Componente tiene estructura **immutable** pero comportamiento **mutable** via internal flag.

```python
class ToggleableComponent:
    """
    Pattern para componentes toggleables.

    Diseño:
    - Estructura immutable (no cambia connections/pipeline)
    - Comportamiento mutable (via _enabled flag)
    - Thread-safe (flag es atomic bool)
    """

    def __init__(self, config):
        self._enabled = config.get('enabled', True)
        self._lock = threading.Lock()  # Thread safety

    @property
    def enabled(self) -> bool:
        """Thread-safe read"""
        with self._lock:
            return self._enabled

    @property
    def supports_toggle(self) -> bool:
        """Override to False si componente es immutable"""
        return True

    def enable(self):
        """Thread-safe enable"""
        with self._lock:
            self._enabled = True
        self._on_enable()  # Hook para subclases

    def disable(self):
        """Thread-safe disable"""
        with self._lock:
            self._enabled = False
        self._on_disable()  # Hook para subclases

    def toggle(self):
        """Thread-safe toggle"""
        if self.enabled:
            self.disable()
        else:
            self.enable()

    def _on_enable(self):
        """Override en subclases para custom behavior"""
        pass

    def _on_disable(self):
        """Override en subclases para custom behavior"""
        pass
```

---

## Architecture: Toggleable Components Design

### 1. Toggleable Stabilization

**Diseño:** Stabilizer con pass-through cuando disabled

```python
# inference/stabilization/core.py - DISEÑO PROPUESTO

class BaseDetectionStabilizer(ABC):
    """
    Base para stabilizers con toggle support.

    Diseño: Toggleable pattern
    - _enabled flag controla pass-through
    - State preservado cuando disabled (tracks no se pierden)
    - Re-enable suave (continúa tracking)
    """

    def __init__(self, config: StabilizationConfig):
        self.config = config
        self._enabled = True
        self._lock = threading.Lock()

    @property
    def enabled(self) -> bool:
        with self._lock:
            return self._enabled

    @property
    def supports_toggle(self) -> bool:
        return True

    def enable(self):
        with self._lock:
            self._enabled = True
        logger.info("✅ Detection stabilization ENABLED")

    def disable(self):
        with self._lock:
            self._enabled = False
        logger.info("🔲 Detection stabilization DISABLED (pass-through)")
        # NOTE: NO reseteamos tracks - preservamos state para re-enable suave

    def toggle(self):
        if self.enabled:
            self.disable()
        else:
            self.enable()

    @abstractmethod
    def _process_enabled(
        self,
        detections: List[Dict],
        source_id: int
    ) -> List[Dict]:
        """
        Procesamiento cuando enabled.

        Subclases implementan lógica de stabilization aquí.
        """
        pass

    def process(
        self,
        detections: List[Dict],
        source_id: int = 0
    ) -> List[Dict]:
        """
        Procesa detections (público).

        Diseño: Template method
        - Si disabled: pass-through (no filtering)
        - Si enabled: delega a _process_enabled()
        """
        if not self.enabled:
            return detections  # Pass-through sin filtering

        return self._process_enabled(detections, source_id)


class TemporalHysteresisStabilizer(BaseDetectionStabilizer):
    """Stabilizer temporal con toggle support"""

    def __init__(self, config: StabilizationConfig):
        super().__init__(config)
        # Tracking state
        self.active_tracks: Dict[int, Dict[str, DetectionTrack]] = defaultdict(dict)
        self.stats: Dict[int, StabilizationStats] = {}

    def _process_enabled(self, detections, source_id):
        """Implementa lógica temporal + hysteresis"""
        # ... lógica actual de stabilization
        pass

    def reset(self, source_id: int = 0):
        """Reset state (usado en tests, debugging)"""
        self.active_tracks[source_id].clear()
        logger.info(f"🔄 Stabilizer reset for source {source_id}")
```

**Ventajas:**
- ✅ Pass-through cuando disabled (zero overhead)
- ✅ State preservado (tracks no se pierden)
- ✅ Re-enable suave (continúa tracking donde dejó)
- ✅ Thread-safe (lock en enable/disable)

**Comandos MQTT:**
```json
{"command": "toggle_stabilization"}
{"command": "stabilization_reset"}  // Reset tracks si necesario
```

---

### 2. Toggleable Visualization

**Problema:** Viz sink está en lista immutable, no puedes removerlo

**Diseño:** Wrapper con early return cuando disabled

```python
# visualization/core.py - DISEÑO PROPUESTO

class ToggleableVisualizationSink:
    """
    Visualization sink con toggle support.

    Diseño: Decorator pattern con toggleable behavior
    - enabled: Renderiza frames normalmente
    - disabled: Early return (skip rendering, ahorra CPU)
    """

    def __init__(
        self,
        roi_state=None,
        inference_handler=None,
        display_stats: bool = False,
        window_name: str = "Inference Pipeline"
    ):
        self.roi_state = roi_state
        self.inference_handler = inference_handler
        self.display_stats = display_stats
        self.window_name = window_name

        # Toggle state
        self._enabled = True
        self._lock = threading.Lock()
        self._window_created = False

    @property
    def enabled(self) -> bool:
        with self._lock:
            return self._enabled

    def enable(self):
        with self._lock:
            self._enabled = True
        logger.info(f"✅ Visualization ENABLED: {self.window_name}")

    def disable(self):
        with self._lock:
            self._enabled = False
        logger.info("🔲 Visualization DISABLED (skip rendering)")

        # Destruir ventana si existe (liberar recursos)
        if self._window_created:
            try:
                cv2.destroyWindow(self.window_name)
                self._window_created = False
            except Exception as e:
                logger.warning(f"Error destroying window: {e}")

    def toggle(self):
        if self.enabled:
            self.disable()
        else:
            self.enable()

    def __call__(
        self,
        predictions: dict,
        video_frame: VideoFrame
    ):
        """
        Sink callable.

        Diseño: Early return pattern
        - Si disabled: return inmediato (no rendering)
        - Si enabled: rendering normal
        """
        if not self.enabled:
            return  # Skip rendering - ahorra CPU

        # Rendering normal
        self._render_frame(predictions, video_frame)

    def _render_frame(self, predictions, video_frame):
        """Lógica actual de rendering"""
        # ... código actual de visualización
        if not self._window_created:
            cv2.namedWindow(self.window_name)
            self._window_created = True

        # Render frame con overlays
        # ...


# Factory modificado
def create_visualization_sink(
    roi_state=None,
    inference_handler=None,
    display_stats: bool = False,
    window_name: str = "Inference Pipeline"
) -> ToggleableVisualizationSink:
    """
    Crea visualization sink con toggle support.

    Returns:
        ToggleableVisualizationSink (callable + toggleable)
    """
    return ToggleableVisualizationSink(
        roi_state=roi_state,
        inference_handler=inference_handler,
        display_stats=display_stats,
        window_name=window_name,
    )
```

**Ventajas:**
- ✅ CPU saving cuando disabled (no rendering)
- ✅ Window cleanup automático (cv2.destroyWindow)
- ✅ Re-enable recrea window automáticamente
- ✅ Thread-safe

**Comandos MQTT:**
```json
{"command": "toggle_visualization"}
```

---

### 3. Toggleable MQTT Publishing

**Diseño:** Data plane con publishing flag

```python
# data/plane.py - DISEÑO PROPUESTO

class MQTTDataPlane:
    """
    Data plane con toggleable publishing.

    Use cases:
    - Testing: Disable publishing para testing local sin saturar broker
    - Debugging: Disable temporalmente para analizar performance sin MQTT
    - Broker relief: Disable si broker saturado
    """

    def __init__(self, ...):
        # ... init actual
        self._publishing_enabled = True
        self._lock = threading.Lock()

    @property
    def publishing_enabled(self) -> bool:
        with self._lock:
            return self._publishing_enabled

    def enable_publishing(self):
        with self._lock:
            self._publishing_enabled = True
        logger.info("✅ MQTT publishing ENABLED")

    def disable_publishing(self):
        with self._lock:
            self._publishing_enabled = False
        logger.info("🔲 MQTT publishing DISABLED (messages dropped)")

    def toggle_publishing(self):
        if self.publishing_enabled:
            self.disable_publishing()
        else:
            self.enable_publishing()

    def publish_inference(
        self,
        predictions: Union[Dict, List[Dict]],
        video_frame: Optional[Union[VideoFrame, List[VideoFrame]]] = None
    ):
        """
        Publica resultados (con early return si disabled).
        """
        if not self.publishing_enabled:
            logger.debug("Publishing disabled, skipping message")
            return  # Drop message

        # ... lógica actual de publish
        if not self._connected.is_set():
            logger.warning("Not connected, message dropped")
            return

        try:
            message = self.detection_publisher.format_message(predictions, video_frame)
            result = self.client.publish(self.data_topic, json.dumps(message), qos=self.qos)
            # ...
        except Exception as e:
            logger.error(f"Error publishing: {e}")
```

**Ventajas:**
- ✅ Testing local sin MQTT noise
- ✅ Broker relief (temporal stop publishing)
- ✅ Mantiene connection (solo drop messages)

**Comandos MQTT:**
```json
{"command": "toggle_mqtt_publishing"}
```

---

### 4. Toggleable Statistics Display

**Diseño:** Handler con stats flag

```python
# inference/handlers/base.py - DISEÑO PROPUESTO

class BaseInferenceHandler(ABC):
    """Base handler con statistics toggle"""

    def __init__(self, ...):
        self._show_statistics = False
        self._stats_lock = threading.Lock()

    @property
    def show_statistics(self) -> bool:
        with self._stats_lock:
            return self._show_statistics

    def enable_statistics(self):
        with self._stats_lock:
            self._show_statistics = True
        logger.info("✅ Statistics display ENABLED")

    def disable_statistics(self):
        with self._stats_lock:
            self._show_statistics = False
        logger.info("🔲 Statistics display DISABLED")

    def toggle_statistics(self):
        if self.show_statistics:
            self.disable_statistics()
        else:
            self.enable_statistics()


# inference/roi/adaptive/pipeline.py
class AdaptiveInferenceHandler(BaseInferenceHandler):
    def __call__(self, video_frames):
        # ... inferencia

        # Log statistics solo si enabled
        if self.show_statistics:
            self._log_statistics(roi_metrics)

        return predictions
```

**Comandos MQTT:**
```json
{"command": "toggle_statistics"}
```

---

### 5. Dynamic FPS Throttling

**Problema:** max_fps se pasa en InferencePipeline.init() - immutable

**Solución A (Preferred): FPS Throttler Sink**

```python
# app/sinks/fps_throttler.py - DISEÑO PROPUESTO

class FPSThrottlerSink:
    """
    Sink que controla FPS efectivo mediante throttling.

    Diseño: Decorator pattern
    - Wrappea otro sink
    - Controla cuántos frames/sec procesa
    - Adjustable en runtime (no requiere rebuild pipeline)
    """

    def __init__(self, downstream_sink: SinkFunction, target_fps: float):
        self.downstream_sink = downstream_sink
        self._target_fps = target_fps
        self._last_process_time = 0.0
        self._lock = threading.Lock()

    @property
    def target_fps(self) -> float:
        with self._lock:
            return self._target_fps

    def set_fps(self, fps: float):
        """
        Cambia target FPS en runtime.

        Args:
            fps: Nuevo target FPS (> 0.0)
        """
        if fps <= 0:
            raise ValueError(f"FPS must be > 0, got {fps}")

        with self._lock:
            old_fps = self._target_fps
            self._target_fps = fps

        logger.info(f"🎛️ FPS throttle: {old_fps:.1f} → {fps:.1f}")

    def __call__(
        self,
        predictions: dict,
        video_frame: VideoFrame
    ):
        """
        Throttle basado en timestamp.

        Diseño:
        - Si elapsed < 1/target_fps: skip frame (drop)
        - Si elapsed >= 1/target_fps: procesa frame
        """
        now = time.time()

        with self._lock:
            min_interval = 1.0 / self._target_fps
            elapsed = now - self._last_process_time

            if elapsed < min_interval:
                # Skip frame - throttling
                logger.debug(f"FPS throttle: skipping frame (elapsed={elapsed:.3f}s)")
                return

            # Procesar frame
            self._last_process_time = now

        # Forward a downstream sink
        self.downstream_sink(predictions, video_frame)


# Usage en Builder
def build_sinks(self, ...):
    # Sinks normales
    mqtt_sink = create_mqtt_sink(data_plane)
    viz_sink = create_visualization_sink(...)

    # Wrappear sinks con FPS throttler
    throttled_mqtt = FPSThrottlerSink(mqtt_sink, target_fps=self.config.max_fps)
    throttled_viz = FPSThrottlerSink(viz_sink, target_fps=self.config.max_fps)

    # FPS throttler debe ser ANTES de stabilization (throttle input, no output)
    sinks = [throttled_mqtt, throttled_viz]
    return sinks
```

**Ventajas:**
- ✅ No requiere rebuild pipeline
- ✅ Per-sink FPS control (viz puede ser 0.5 FPS, MQTT 2 FPS)
- ✅ Runtime adjustable
- ✅ Simple (solo timestamp comparison)

**Desventajas:**
- ⚠️ No controla FPS de *inferencia* (solo output)
- ⚠️ Pipeline sigue procesando frames internamente

**Solución B (Ideal pero complejo): Pipeline Rebuild**

```python
# app/controller.py - DISEÑO ALTERNATIVO

class InferencePipelineController:
    def set_max_fps(self, new_fps: float):
        """
        Cambia max_fps rebuilding pipeline.

        Diseño: Hot swap
        - Pausa pipeline actual
        - Rebuild con nuevo FPS
        - Swap pipeline
        - Resume

        WARNING: Breve interrupción durante rebuild
        """
        if not self.is_running:
            logger.warning("Pipeline no está corriendo")
            return

        logger.info(f"🔄 Rebuilding pipeline con FPS={new_fps}...")

        try:
            # 1. Pausar pipeline actual
            self.pipeline.pause_stream()

            # 2. Terminar pipeline actual
            self.pipeline.terminate()
            self.pipeline.join(timeout=5.0)

            # 3. Update config
            old_fps = self.config.max_fps
            self.config.max_fps = new_fps

            # 4. Rebuild pipeline (usa builder)
            self.pipeline = self.builder.build_pipeline(
                inference_handler=self.inference_handler,
                sinks=self.sinks,
                watchdog=self.watchdog,
                status_update_handlers=[self._status_update_handler],
            )

            # 5. Reiniciar
            self.pipeline.start()

            logger.info(f"✅ Pipeline rebuilt: FPS {old_fps:.1f} → {new_fps:.1f}")

        except Exception as e:
            logger.error(f"❌ Error rebuilding pipeline: {e}")
            # Rollback
            self.config.max_fps = old_fps
            raise
```

**Ventajas:**
- ✅ Controla FPS real de inferencia (no solo output)
- ✅ Más "correcto" arquitectónicamente

**Desventajas:**
- ❌ Complejo (rebuild entire pipeline)
- ❌ Breve interrupción (terminate → rebuild → start)
- ❌ Riesgo de bugs en transition

**Recomendación:** Solución A (FPS Throttler) para v2.5, Solución B para v3.0

**Comandos MQTT:**
```json
{"command": "set_fps", "value": 1.0}
{"command": "get_fps"}
```

---

## Control Plane Integration

### Unified Toggle Command System

**Diseño:** Todos los toggleables se registran en CommandRegistry con pattern uniforme

```python
# app/controller.py - DISEÑO PROPUESTO

class InferencePipelineController:
    def _setup_control_callbacks(self):
        """
        Registra comandos MQTT (incluye toggles).

        Diseño: Registry pattern con toggleable components
        - Todos los toggleables tienen misma API (enable/disable/toggle)
        - Registry auto-descubre qué componentes soportan toggle
        """
        registry = self.control_plane.command_registry

        # ====================================================================
        # Basic Commands (siempre disponibles)
        # ====================================================================
        registry.register('pause', self._handle_pause, "Pausa el pipeline")
        registry.register('resume', self._handle_resume, "Reanuda el pipeline")
        registry.register('stop', self._handle_stop, "Detiene el pipeline")
        registry.register('status', self._handle_status, "Estado actual")
        registry.register('metrics', self._handle_metrics, "Publica métricas")

        # ====================================================================
        # Toggle Commands (condicionales según componentes)
        # ====================================================================

        # ROI Crop Toggle (solo adaptive)
        if self.inference_handler and self.inference_handler.supports_toggle:
            registry.register(
                'toggle_crop',
                self._handle_toggle_crop,
                "Toggle adaptive ROI crop"
            )

        # Stabilization Toggle (solo si stabilization habilitado)
        if self.stabilizer and hasattr(self.stabilizer, 'supports_toggle'):
            if self.stabilizer.supports_toggle:
                registry.register(
                    'toggle_stabilization',
                    self._handle_toggle_stabilization,
                    "Toggle detection stabilization"
                )
                registry.register(
                    'stabilization_stats',
                    self._handle_stabilization_stats,
                    "Estadísticas de stabilization"
                )
                registry.register(
                    'stabilization_reset',
                    self._handle_stabilization_reset,
                    "Reset stabilization tracks"
                )

        # Statistics Toggle (siempre disponible si handler existe)
        if self.inference_handler:
            registry.register(
                'toggle_statistics',
                self._handle_toggle_statistics,
                "Toggle statistics logging"
            )

        # Visualization Toggle (solo si viz habilitado)
        viz_sink = self._find_visualization_sink()
        if viz_sink and hasattr(viz_sink, 'toggle'):
            registry.register(
                'toggle_visualization',
                lambda: viz_sink.toggle(),
                "Toggle visualization display"
            )

        # MQTT Publishing Toggle (siempre disponible)
        if self.data_plane:
            registry.register(
                'toggle_mqtt',
                lambda: self.data_plane.toggle_publishing(),
                "Toggle MQTT publishing"
            )

        # FPS Control (siempre disponible)
        registry.register(
            'set_fps',
            self._handle_set_fps,
            "Set target FPS (ej: {\"command\": \"set_fps\", \"value\": 1.0})"
        )
        registry.register(
            'get_fps',
            self._handle_get_fps,
            "Get current FPS setting"
        )

    # ========================================================================
    # Toggle Handlers
    # ========================================================================

    def _handle_toggle_stabilization(self):
        """Handler para toggle_stabilization command"""
        logger.info("🔄 Comando TOGGLE_STABILIZATION recibido")

        if self.stabilizer is None:
            logger.warning("⚠️ Stabilizer no disponible")
            return

        self.stabilizer.toggle()

        # Publish status
        status = "enabled" if self.stabilizer.enabled else "disabled"
        self.control_plane.publish_status(f"stabilization_{status}")

    def _handle_stabilization_reset(self):
        """Handler para reset stabilization tracks"""
        logger.info("🔄 Comando STABILIZATION_RESET recibido")

        if self.stabilizer is None:
            logger.warning("⚠️ Stabilizer no disponible")
            return

        self.stabilizer.reset()
        logger.info("✅ Stabilization tracks reset")

    def _handle_toggle_statistics(self):
        """Handler para toggle_statistics command"""
        logger.info("📊 Comando TOGGLE_STATISTICS recibido")

        if self.inference_handler is None:
            logger.warning("⚠️ Handler no disponible")
            return

        self.inference_handler.toggle_statistics()

    def _handle_set_fps(self, command_data: dict):
        """Handler para set_fps command"""
        new_fps = command_data.get('value')

        if new_fps is None:
            logger.error("❌ set_fps requiere 'value' field")
            return

        if not isinstance(new_fps, (int, float)) or new_fps <= 0:
            logger.error(f"❌ FPS inválido: {new_fps}")
            return

        logger.info(f"🎛️ Comando SET_FPS recibido: {new_fps}")

        # Opción A: FPS Throttler (simple)
        throttler = self._find_fps_throttler()
        if throttler:
            throttler.set_fps(new_fps)
        else:
            logger.warning("⚠️ FPS throttler no disponible")
            return

        # Opción B: Pipeline rebuild (complejo - no implementar en v2.5)
        # self.set_max_fps(new_fps)

        self.control_plane.publish_status(f"fps_set_{new_fps}")

    def _handle_get_fps(self):
        """Handler para get_fps command"""
        logger.info("📊 Comando GET_FPS recibido")

        throttler = self._find_fps_throttler()
        if throttler:
            current_fps = throttler.target_fps
            logger.info(f"Current FPS: {current_fps}")
            self.control_plane.publish_status(f"current_fps_{current_fps}")
        else:
            logger.warning("⚠️ FPS throttler no disponible")

    # ========================================================================
    # Helpers
    # ========================================================================

    def _find_visualization_sink(self):
        """Encuentra viz sink en lista de sinks (si existe)"""
        # Necesita acceso a self.sinks (agregar en __init__)
        for sink in getattr(self, 'sinks', []):
            if isinstance(sink, ToggleableVisualizationSink):
                return sink
        return None

    def _find_fps_throttler(self):
        """Encuentra FPS throttler en sinks (si existe)"""
        for sink in getattr(self, 'sinks', []):
            if isinstance(sink, FPSThrottlerSink):
                return sink
        return None
```

---

## State Management for Toggles

### Toggle State Persistence

**Problema:** Si pipeline reinicia, ¿se pierden estados de toggle?

**Diseño:** Toggle state en config (opcional persistence)

```python
# config/schemas.py - TOGGLE STATE

class ToggleState(BaseModel):
    """Estado de toggles (persistible)"""

    roi_crop_enabled: bool = True
    stabilization_enabled: bool = True
    statistics_enabled: bool = False
    visualization_enabled: bool = True
    mqtt_publishing_enabled: bool = True
    target_fps: float = 2.0

    class Config:
        extra = 'forbid'


class PipelineConfig(BaseModel):
    # ... campos existentes

    # Toggle state (runtime mutable)
    toggle_state: ToggleState = Field(default_factory=ToggleState)


# app/controller.py - STATE SYNC

class InferencePipelineController:
    def setup(self):
        # ... setup normal

        # Sync toggle state from config
        self._sync_toggle_state()

    def _sync_toggle_state(self):
        """
        Sincroniza estado de toggles desde config.

        Permite persistir toggle state entre reinicios.
        """
        state = self.config.toggle_state

        # Sync handler ROI
        if self.inference_handler and self.inference_handler.supports_toggle:
            if state.roi_crop_enabled:
                self.inference_handler.enable()
            else:
                self.inference_handler.disable()

        # Sync stabilization
        if self.stabilizer and hasattr(self.stabilizer, 'supports_toggle'):
            if state.stabilization_enabled:
                self.stabilizer.enable()
            else:
                self.stabilizer.disable()

        # Sync statistics
        if self.inference_handler:
            if state.statistics_enabled:
                self.inference_handler.enable_statistics()
            else:
                self.inference_handler.disable_statistics()

        # Sync visualization
        viz_sink = self._find_visualization_sink()
        if viz_sink:
            if state.visualization_enabled:
                viz_sink.enable()
            else:
                viz_sink.disable()

        # Sync MQTT publishing
        if self.data_plane:
            if state.mqtt_publishing_enabled:
                self.data_plane.enable_publishing()
            else:
                self.data_plane.disable_publishing()

        # Sync FPS
        throttler = self._find_fps_throttler()
        if throttler:
            throttler.set_fps(state.target_fps)

    def _persist_toggle_state(self):
        """
        Persiste toggle state actual a config (opcional).

        Útil para mantener estado entre reinicios.
        """
        state = ToggleState()

        # Collect current toggle states
        if self.inference_handler and self.inference_handler.supports_toggle:
            state.roi_crop_enabled = self.inference_handler.enabled

        if self.stabilizer:
            state.stabilization_enabled = self.stabilizer.enabled

        if self.inference_handler:
            state.statistics_enabled = self.inference_handler.show_statistics

        viz_sink = self._find_visualization_sink()
        if viz_sink:
            state.visualization_enabled = viz_sink.enabled

        if self.data_plane:
            state.mqtt_publishing_enabled = self.data_plane.publishing_enabled

        throttler = self._find_fps_throttler()
        if throttler:
            state.target_fps = throttler.target_fps

        # Update config
        self.config.toggle_state = state

        # Opcionalmente, escribir a archivo
        # self._write_config_to_file()

        logger.info("💾 Toggle state persisted")
```

---

## Stream Processor Big Picture

### Information Flow with Toggles

```
                            MQTT Control Plane
                                   │
                                   │ Commands
                                   ↓
                    ┌──────────────────────────────┐
                    │  InferencePipelineController │
                    │   (Toggle Orchestrator)      │
                    └───────────────┬──────────────┘
                                    │
                    ╔═══════════════╧═══════════════╗
                    ║    TOGGLEABLE COMPONENTS      ║
                    ╚═══════════════╤═══════════════╝
                                    │
       ┌────────────────────────────┼────────────────────────────┐
       │                            │                            │
       ↓                            ↓                            ↓
┌──────────────┐          ┌─────────────────┐        ┌──────────────────┐
│  Handler     │          │  Stabilization  │        │     Sinks        │
│  (ROI Crop)  │          │   (Filtering)   │        │  (Output Layer)  │
│              │          │                 │        │                  │
│  ├─enable    │          │  ├─enable       │        │  ├─MQTT          │
│  └─disable   │          │  └─disable      │        │  │  └─toggle     │
│              │          │                 │        │  ├─Visualization │
│  🔄 Toggle   │          │  🔄 Toggle      │        │  │  └─toggle     │
│              │          │                 │        │  └─FPS Throttle  │
│  Impact:     │          │  Impact:        │        │     └─set_fps    │
│  • Input     │          │  • Processing   │        │                  │
│  • Full vs   │          │  • Raw vs       │        │  Impact:         │
│    Cropped   │          │    Filtered     │        │  • Output        │
└──────────────┘          └─────────────────┘        │  • Where data    │
                                                      │    goes          │
                                                      └──────────────────┘

Stream Flow:
═══════════
Video Frame → [Handler Toggle: Crop?] → Inference → Predictions
                                                         ↓
              [Stabilization Toggle: Filter?] → Filtered Predictions
                                                         ↓
              [Sinks Toggle: Publish? Display? Throttle?] → Outputs
```

### Toggle Independence Matrix

| Toggle | Affects | Independent of | State Preserved |
|--------|---------|----------------|-----------------|
| ROI Crop | Input to model | Stabilization, Sinks | ✅ ROI state maintained |
| Stabilization | Processing layer | Handler, Sinks | ✅ Tracks preserved |
| Visualization | Viz output | Handler, MQTT, Stabilization | ❌ Window destroyed |
| MQTT Publishing | MQTT output | Handler, Stabilization, Viz | N/A (stateless) |
| Statistics | Logging | All | N/A (stateless) |
| FPS Throttle | Output rate | Handler, Stabilization | ✅ Target FPS preserved |

**Diseño:** Toggles son **ortogonales** - cada uno controla una dimension diferente:
- Handler: **Input** dimension (what goes into model)
- Stabilization: **Processing** dimension (how predictions are filtered)
- Sinks: **Output** dimension (where results go)

---

## Thread Safety Design

### Concurrent Toggle Access

**Problema:** Pipeline es multi-threaded - toggles deben ser thread-safe

```
Thread 1 (Pipeline):        Thread 2 (MQTT Command):
  ├─ __call__()                 ├─ toggle()
  │  └─ if self.enabled:        │  └─ self._enabled = not self._enabled
  │       # Race condition! ❌
```

**Diseño:** Lock-based synchronization

```python
class ToggleableComponent:
    def __init__(self):
        self._enabled = True
        self._lock = threading.Lock()  # Protect _enabled flag

    @property
    def enabled(self) -> bool:
        """Thread-safe read"""
        with self._lock:
            return self._enabled

    def enable(self):
        """Thread-safe write"""
        with self._lock:
            self._enabled = True

    def disable(self):
        """Thread-safe write"""
        with self._lock:
            self._enabled = False

    def __call__(self, *args):
        """Thread-safe check-and-process"""
        # Read with lock
        should_process = self.enabled

        if not should_process:
            return  # Early return - no lock held

        # Process (lock released - long operations ok)
        result = self._do_processing(*args)
        return result
```

**Importante:** Lock solo protege _enabled flag, NO el processing completo (deadlock risk).

---

## Summary: Toggleable Architecture

### Design Principles

1. **Immutable Structure, Mutable Behavior**
   - Pipeline structure no cambia (no add/remove components)
   - Component behavior cambia (enable/disable/toggle)

2. **Early Return Pattern**
   - `if not enabled: return` en top de processing
   - Zero overhead cuando disabled

3. **State Preservation**
   - Stabilization tracks preserved cuando disabled
   - ROI state maintained cuando disabled
   - Smooth re-enable (no reset necesario)

4. **Thread Safety**
   - Lock en toggle operations
   - Atomic flag reads
   - No locks durante processing

5. **Unified API**
   - Todos los toggleables: enable/disable/toggle/enabled
   - Registry-based discovery
   - MQTT command pattern uniforme

### Toggle Catalog

| Toggle | Component | Pattern | State Preserved | Thread-Safe |
|--------|-----------|---------|-----------------|-------------|
| ROI Crop | Handler | Internal flag | ✅ ROI state | ✅ Lock |
| Stabilization | Stabilizer | Pass-through | ✅ Tracks | ✅ Lock |
| Visualization | Sink | Early return | ❌ Window | ✅ Lock |
| MQTT Publishing | Data Plane | Drop message | N/A | ✅ Lock |
| Statistics | Handler | Conditional log | N/A | ✅ Lock |
| FPS Throttle | Throttler Sink | Timestamp check | ✅ Target FPS | ✅ Lock |

### Commands Summary

```json
// Lifecycle
{"command": "pause"}
{"command": "resume"}
{"command": "stop"}

// Status
{"command": "status"}
{"command": "metrics"}

// ROI Toggles
{"command": "toggle_crop"}  // Adaptive only

// Stabilization Toggles
{"command": "toggle_stabilization"}
{"command": "stabilization_stats"}
{"command": "stabilization_reset"}

// Visualization Toggles
{"command": "toggle_visualization"}

// Statistics Toggle
{"command": "toggle_statistics"}

// MQTT Toggle
{"command": "toggle_mqtt"}

// FPS Control
{"command": "set_fps", "value": 1.0}
{"command": "get_fps"}
```

---

## Non-Goals

❌ **No es:** Cambiar estructura de pipeline dinámicamente (add/remove components)
❌ **No es:** Hot-reload de config completo
❌ **No es:** State machine complejo con transitions

✅ **Sí es:** Enable/disable comportamiento sin rebuild
✅ **Sí es:** Control granular de qué procesa/publica
✅ **Sí es:** Diseño simple con early returns

---

**Fin del documento de diseño**

Estos dos documentos proveen la base arquitectónica. ¿Listo para revisarlos y decidir próximos pasos?
