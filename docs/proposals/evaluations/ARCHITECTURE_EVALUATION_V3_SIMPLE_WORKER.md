# Evaluación de Arquitectura: Adeline - Simple & Controllable Worker

**Evaluación FINAL:** 22 de Octubre, 2025  
**Sistema:** Adeline - "Jefe de Cocina" (Simple Worker)  
**Principio:** **KISS** - Keep It Simple, Stupid

---

## 🎯 Contexto COMPLETO: Arquitectura Orquestada

### El Sistema Real

```
┌──────────────────────────────────────────────────────────────────┐
│                    ARQUITECTURA ORQUESTADA                       │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  🎯 ORQUESTADOR (Jefe de Turno)                                 │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ RESPONSABILIDADES:                                         │ │
│  │ ✅ Coordina todo el sistema                                │ │
│  │ ✅ Evalúa desempeño de Adeline                             │ │
│  │ ✅ Toma decisiones: "sube FPS", "cambia confianza"         │ │
│  │ ✅ Ajusta parámetros de Adeline vía MQTT commands          │ │
│  │ ✅ Optimiza globalmente                                    │ │
│  └────────────────────────────────────────────────────────────┘ │
│              │ Control                           ▲               │
│              │ (set_fps, set_confidence, ...)   │ Metrics+Data  │
│              ▼                                   │               │
│  📹 ADELINE (Jefe de Cocina)                                    │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ RESPONSABILIDADES:                                         │ │
│  │ ✅ "Así viene la cocina" (reporta estado)                  │ │
│  │ ✅ Detecta objetos (inference simple)                      │ │
│  │ ✅ Estabiliza detecciones (filtro básico)                  │ │
│  │ ✅ Obedece comandos del orquestador                        │ │
│  │ ✅ Reporta métricas detalladas                             │ │
│  │ ✅ MANTENERSE SIMPLE ⭐⭐⭐                                  │ │
│  │                                                            │ │
│  │ ❌ NO auto-tuning complejo                                 │ │
│  │ ❌ NO optimización sofisticada                             │ │
│  │ ❌ NO decisiones globales                                  │ │
│  └────────────────────────────────────────────────────────────┘ │
│              │ Data                                              │
│              │ (detecciones crudas)                              │
│              ▼                                                   │
│  🧠 ANALIZADOR (Mozos)                                          │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ RESPONSABILIDADES:                                         │ │
│  │ ✅ Van a las mesas (escuchan detecciones)                  │ │
│  │ ✅ Llevan/traen información                                │ │
│  │ ✅ Generan gemelo digital de habitación                    │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

### Analogía del Restaurante

| Componente | Rol | Responsabilidad |
|------------|-----|-----------------|
| **Orquestador** | Jefe de turno | "Mesa 5 necesita prioridad", "Cocina va lenta, acelera" |
| **Adeline** | Jefe de cocina | "3 platos listos", "horno a 180°", "nos quedan 5 min" |
| **Analizador** | Mozos | Llevan platos, traen pedidos, conocen el estado de las mesas |

**Lo crítico:** El jefe de cocina (Adeline) NO decide la estrategia del restaurante, **solo reporta y obedece**.

---

## 🚨 Recomendaciones DESCARTADAS (Sobre-ingeniería)

### ❌ TODO LO QUE AGREGABA COMPLEJIDAD

De mis evaluaciones anteriores, **descartar:**

#### 1. ~~Circuit Breakers Sofisticados~~
**Por qué NO:** Demasiado complejo para un worker simple
- ❌ State machine (CLOSED/OPEN/HALF_OPEN)
- ❌ Recovery testing automático
- ❌ Adaptive thresholds

**Qué sí hacer:**
- ✅ Simple retry (3 intentos)
- ✅ Log error y continuar
- ✅ Reportar al orquestador que MQTT falló

```python
# ❌ DEMASIADO COMPLEJO (circuit breaker con state machine)
class CircuitBreaker:
    def __init__(self, failure_threshold, recovery_timeout, ...):
        self.state = CircuitState.CLOSED
        # 50 líneas de lógica de state transitions...

# ✅ SIMPLE (retry básico)
def publish_with_retry(message, max_retries=3):
    """Simple retry sin state machine"""
    for attempt in range(max_retries):
        try:
            result = client.publish(message)
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                return True
        except Exception as e:
            if attempt == max_retries - 1:
                logger.error(f"Publish failed after {max_retries} attempts: {e}")
                # Reportar al orquestador
                metrics['mqtt_errors'] += 1
                return False
        time.sleep(0.1 * (2 ** attempt))  # Exponential backoff simple
    return False
```

---

#### 2. ~~Auto-tuning de Parámetros~~
**Por qué NO:** El orquestador decide, no Adeline
- ❌ Adaptive smoothing basado en velocidad
- ❌ Kalman filters para predecir ROI
- ❌ Ajuste dinámico de confidence

**Qué sí hacer:**
- ✅ Parámetros configurables vía MQTT commands
- ✅ Reportar métricas al orquestador
- ✅ El orquestador decide ajustes

```python
# ❌ COMPLEJO: Auto-tuning dentro de Adeline
class AdaptiveROIState:
    def update(self, detections):
        # Calcular velocidad de cambio
        velocity = self._calculate_velocity(detections)
        # Ajustar alpha dinámicamente
        adaptive_alpha = self._tune_alpha(velocity)  # ❌ Demasiado smart
        # ...

# ✅ SIMPLE: Parámetros fijos, ajustables por orquestador
class ROIState:
    def __init__(self, smoothing_alpha: float = 0.3):
        self.smoothing_alpha = smoothing_alpha  # Fijo, configurable
    
    def update(self, detections):
        # Usar smoothing_alpha fijo (sin auto-tuning)
        new_roi = new_roi.smooth_with(prev_roi, self.smoothing_alpha)
    
    def set_smoothing(self, alpha: float):
        """Orquestador puede cambiar vía MQTT command"""
        self.smoothing_alpha = alpha
        logger.info(f"Smoothing updated to {alpha} (by orchestrator)")
```

---

#### 3. ~~Vendor Abstraction Layer~~
**Por qué NO (ahora):** YAGNI - No lo necesitas aún
- Funciona con Inference SDK
- No hay planes de cambiar
- Refactoring grande sin beneficio inmediato

**Cuándo sí hacerlo:** Cuando SDK rompa compatibilidad o necesites cambiar vendor

---

#### 4. ~~Persistent Storage Complejo~~
**Por qué NO:** Analizador/Orquestador ya persisten
- ❌ SQLite repository
- ❌ Event sourcing
- ❌ Historical queries

**Qué sí hacer:**
- ✅ Checkpoint ligero para restart (pickle de tracks activos)
- ✅ Circular buffer de últimas 100 detections (debugging)

---

## ✅ Recomendaciones AJUSTADAS (Simplicidad + Controlabilidad)

### Principio Guía: **KISS + YAGNI**

1. **KISS** (Keep It Simple, Stupid)
2. **YAGNI** (You Ain't Gonna Need It)
3. **Orquestador decide, Adeline obedece**
4. **Reportar bien > Ser inteligente**

---

## 🔴 Prioridad 1: Controlabilidad (Crítico)

### 1. **Comandos MQTT Extensibles** ⭐⭐⭐⭐⭐

**Problema actual:** Comandos hardcoded, difícil agregar nuevos

**Situación actual:**
```python
# Comandos actuales (básicos)
- pause
- resume
- stop
- status
- metrics
- toggle_crop (condicional)
- stabilization_stats (condicional)
```

**Necesidad del orquestador:**
```python
# Comandos que el orquestador NECESITA para ajustar Adeline
- set_fps (ajustar velocidad)
- set_confidence (ajustar sensibilidad)
- set_iou_threshold (ajustar NMS)
- set_roi_smoothing (ajustar suavizado)
- set_stabilization_params (ajustar filtrado temporal)
- get_detailed_metrics (métricas granulares)
- reset_roi (forzar reset de ROI)
- enable_stabilization / disable_stabilization
```

**Solución: Comandos Parametrizados**

```python
# adeline/control/registry.py (MEJORADO)

class CommandRegistry:
    """
    Registry con soporte para comandos parametrizados
    
    Evolución:
    - V1: Comandos nullary (sin params) ✅ Actual
    - V2: Comandos con params + validation ⭐ Nueva feature
    """
    
    def __init__(self):
        self._commands: Dict[str, Callable] = {}
        self._descriptions: Dict[str, str] = {}
        self._arg_schemas: Dict[str, dict] = {}  # JSON Schema para validar
    
    def register(
        self,
        command: str,
        handler: Callable,
        description: str = "",
        arg_schema: Optional[dict] = None
    ):
        """
        Registra comando con schema de argumentos
        
        Args:
            command: Nombre del comando
            handler: Función (puede recibir **kwargs)
            description: Descripción
            arg_schema: JSON Schema para validar argumentos
        """
        self._commands[command] = handler
        self._descriptions[command] = description
        self._arg_schemas[command] = arg_schema
    
    def execute(self, command: str, args: Optional[dict] = None):
        """
        Ejecuta comando con argumentos validados
        
        Args:
            command: Nombre del comando
            args: Argumentos (dict)
        
        Raises:
            CommandNotAvailableError: Si comando no existe
            CommandValidationError: Si args inválidos
        """
        if command not in self._commands:
            raise CommandNotAvailableError(...)
        
        # Validar args si hay schema
        if args and self._arg_schemas.get(command):
            self._validate_args(command, args)
        
        handler = self._commands[command]
        
        # Ejecutar con args (si los acepta)
        import inspect
        sig = inspect.signature(handler)
        if len(sig.parameters) > 0:
            return handler(**args if args else {})
        else:
            return handler()
    
    def _validate_args(self, command: str, args: dict):
        """Valida args contra schema"""
        import jsonschema
        
        schema = self._arg_schemas[command]
        try:
            jsonschema.validate(instance=args, schema=schema)
        except jsonschema.ValidationError as e:
            raise CommandValidationError(
                f"Invalid arguments for command '{command}': {e.message}"
            )

class CommandValidationError(Exception):
    """Args no cumplen schema"""
    pass


# adeline/app/controller.py (COMANDOS PARAMETRIZADOS)

class InferencePipelineController:
    
    def _setup_control_callbacks(self):
        """Registra comandos (básicos + parametrizados)"""
        registry = self.control_plane.command_registry
        
        # ===================================================================
        # Comandos básicos (sin params) - YA EXISTEN
        # ===================================================================
        registry.register('pause', self._handle_pause, "Pausa el procesamiento")
        registry.register('resume', self._handle_resume, "Reanuda el procesamiento")
        registry.register('stop', self._handle_stop, "Detiene y finaliza")
        registry.register('status', self._handle_status, "Consulta estado")
        registry.register('metrics', self._handle_metrics, "Métricas del pipeline")
        
        # ===================================================================
        # Comandos parametrizados (NUEVOS - para orquestador)
        # ===================================================================
        
        # SET_FPS: Ajustar velocidad
        registry.register(
            command='set_fps',
            handler=self._handle_set_fps,
            description="Ajusta FPS máximo del pipeline",
            arg_schema={
                'type': 'object',
                'properties': {
                    'value': {'type': 'number', 'minimum': 0.5, 'maximum': 30}
                },
                'required': ['value']
            }
        )
        
        # SET_CONFIDENCE: Ajustar sensibilidad
        registry.register(
            command='set_confidence',
            handler=self._handle_set_confidence,
            description="Ajusta threshold de confianza",
            arg_schema={
                'type': 'object',
                'properties': {
                    'value': {'type': 'number', 'minimum': 0.0, 'maximum': 1.0}
                },
                'required': ['value']
            }
        )
        
        # SET_ROI_SMOOTHING: Ajustar suavizado de ROI
        registry.register(
            command='set_roi_smoothing',
            handler=self._handle_set_roi_smoothing,
            description="Ajusta suavizado temporal de ROI",
            arg_schema={
                'type': 'object',
                'properties': {
                    'value': {'type': 'number', 'minimum': 0.0, 'maximum': 1.0}
                },
                'required': ['value']
            }
        )
        
        # SET_STABILIZATION: Ajustar filtrado temporal
        registry.register(
            command='set_stabilization',
            handler=self._handle_set_stabilization,
            description="Ajusta parámetros de estabilización",
            arg_schema={
                'type': 'object',
                'properties': {
                    'min_frames': {'type': 'integer', 'minimum': 1, 'maximum': 10},
                    'max_gap': {'type': 'integer', 'minimum': 0, 'maximum': 10},
                    'appear_conf': {'type': 'number', 'minimum': 0.0, 'maximum': 1.0},
                    'persist_conf': {'type': 'number', 'minimum': 0.0, 'maximum': 1.0}
                },
                'minProperties': 1  # Al menos un param
            }
        )
        
        # RESET_ROI: Forzar reset
        registry.register(
            command='reset_roi',
            handler=self._handle_reset_roi,
            description="Resetea ROI a frame completo"
        )
        
        # GET_CONFIG: Consultar config actual
        registry.register(
            command='get_config',
            handler=self._handle_get_config,
            description="Retorna configuración actual"
        )
        
        logger.info(f"✅ {len(registry.available_commands)} comandos registrados")
    
    # ===================================================================
    # Handlers para comandos parametrizados
    # ===================================================================
    
    def _handle_set_fps(self, value: float):
        """
        Ajusta FPS máximo
        
        Uso (MQTT):
        {
            "command": "set_fps",
            "args": {"value": 3.0}
        }
        """
        logger.info(f"🎬 Comando SET_FPS recibido: {value}")
        
        # Validar que pipeline esté corriendo
        if not self.is_running:
            logger.warning("⚠️ Pipeline no está corriendo, cambio se aplicará al reiniciar")
        
        # Actualizar config
        old_fps = self.config.MAX_FPS
        self.config.MAX_FPS = value
        
        # Hot reload en pipeline (si es posible)
        if hasattr(self.pipeline, 'set_max_fps'):
            self.pipeline.set_max_fps(value)
            logger.info(f"✅ FPS actualizado: {old_fps} → {value}")
        else:
            logger.warning("⚠️ FPS actualizado en config, requiere restart para aplicar")
        
        # Publicar confirmación
        self.control_plane.publish_status(
            "fps_updated",
            metadata={'old': old_fps, 'new': value}
        )
    
    def _handle_set_confidence(self, value: float):
        """
        Ajusta threshold de confianza
        
        Uso (MQTT):
        {
            "command": "set_confidence",
            "args": {"value": 0.5}
        }
        """
        logger.info(f"🎯 Comando SET_CONFIDENCE recibido: {value}")
        
        old_conf = self.config.MODEL_CONFIDENCE
        self.config.MODEL_CONFIDENCE = value
        
        # Actualizar en inference handler si posible
        if hasattr(self.inference_handler, 'set_confidence'):
            self.inference_handler.set_confidence(value)
            logger.info(f"✅ Confidence actualizado: {old_conf:.2f} → {value:.2f}")
        else:
            logger.warning("⚠️ Confidence actualizado en config, requiere restart")
        
        self.control_plane.publish_status(
            "confidence_updated",
            metadata={'old': old_conf, 'new': value}
        )
    
    def _handle_set_roi_smoothing(self, value: float):
        """
        Ajusta suavizado de ROI
        
        Uso (MQTT):
        {
            "command": "set_roi_smoothing",
            "args": {"value": 0.5}
        }
        """
        logger.info(f"🔲 Comando SET_ROI_SMOOTHING recibido: {value}")
        
        if self.roi_state is None:
            logger.warning("⚠️ ROI no habilitado (mode='none')")
            return
        
        old_smooth = self.roi_state._smoothing_alpha
        self.roi_state._smoothing_alpha = value
        
        logger.info(f"✅ ROI smoothing actualizado: {old_smooth:.2f} → {value:.2f}")
        
        self.control_plane.publish_status(
            "roi_smoothing_updated",
            metadata={'old': old_smooth, 'new': value}
        )
    
    def _handle_set_stabilization(self, **params):
        """
        Ajusta parámetros de estabilización
        
        Uso (MQTT):
        {
            "command": "set_stabilization",
            "args": {
                "min_frames": 5,
                "max_gap": 3,
                "appear_conf": 0.6,
                "persist_conf": 0.4
            }
        }
        """
        logger.info(f"📊 Comando SET_STABILIZATION recibido: {params}")
        
        if self.stabilizer is None:
            logger.warning("⚠️ Stabilization no habilitado (mode='none')")
            return
        
        # Aplicar cambios
        changes = {}
        if 'min_frames' in params:
            old = self.stabilizer.min_frames
            self.stabilizer.min_frames = params['min_frames']
            changes['min_frames'] = {'old': old, 'new': params['min_frames']}
        
        if 'max_gap' in params:
            old = self.stabilizer.max_gap
            self.stabilizer.max_gap = params['max_gap']
            changes['max_gap'] = {'old': old, 'new': params['max_gap']}
        
        if 'appear_conf' in params:
            old = self.stabilizer.appear_conf
            self.stabilizer.appear_conf = params['appear_conf']
            changes['appear_conf'] = {'old': old, 'new': params['appear_conf']}
        
        if 'persist_conf' in params:
            old = self.stabilizer.persist_conf
            self.stabilizer.persist_conf = params['persist_conf']
            changes['persist_conf'] = {'old': old, 'new': params['persist_conf']}
        
        logger.info(f"✅ Stabilization actualizado: {changes}")
        
        self.control_plane.publish_status(
            "stabilization_updated",
            metadata=changes
        )
    
    def _handle_reset_roi(self):
        """
        Resetea ROI a frame completo
        
        Uso (MQTT):
        {"command": "reset_roi"}
        """
        logger.info("🔄 Comando RESET_ROI recibido")
        
        if self.roi_state is None:
            logger.warning("⚠️ ROI no habilitado")
            return
        
        self.roi_state.reset()
        logger.info("✅ ROI reseteado")
        
        self.control_plane.publish_status("roi_reset")
    
    def _handle_get_config(self):
        """
        Retorna configuración actual
        
        Uso (MQTT):
        {"command": "get_config"}
        """
        logger.info("📋 Comando GET_CONFIG recibido")
        
        config_snapshot = {
            'pipeline': {
                'max_fps': self.config.MAX_FPS,
                'model_id': self.config.MODEL_ID,
                'rtsp_url': self.config.RTSP_URL
            },
            'model': {
                'confidence': self.config.MODEL_CONFIDENCE,
                'iou_threshold': self.config.MODEL_IOU_THRESHOLD,
                'imgsz': self.config.MODEL_IMGSZ
            },
            'roi': {
                'mode': self.config.ROI_MODE,
                'smoothing': self.roi_state._smoothing_alpha if self.roi_state else None
            },
            'stabilization': {
                'mode': self.config.STABILIZATION_MODE,
                'min_frames': self.stabilizer.min_frames if self.stabilizer else None,
                'max_gap': self.stabilizer.max_gap if self.stabilizer else None,
                'appear_conf': self.stabilizer.appear_conf if self.stabilizer else None,
                'persist_conf': self.stabilizer.persist_conf if self.stabilizer else None
            }
        }
        
        # Publicar en topic de status
        self.control_plane.client.publish(
            self.control_plane.status_topic,
            json.dumps({
                'type': 'config_snapshot',
                'timestamp': time.time(),
                'config': config_snapshot
            }),
            qos=1
        )
        
        logger.info("✅ Config snapshot publicado")


# adeline/control/plane.py (SOPORTE PARA ARGS)

class MQTTControlPlane:
    
    def _on_message(self, client, userdata, msg):
        """
        Callback MEJORADO con soporte para args
        
        Formato esperado:
        {
            "command": "set_fps",
            "args": {"value": 3.0}  // Opcional
        }
        """
        try:
            payload = msg.payload.decode('utf-8')
            command_data = json.loads(payload)
            
            command = command_data.get('command', '').lower()
            args = command_data.get('args', None)  # ✅ Nuevo: extraer args
            
            logger.info(
                f"📥 Comando recibido: {command}" +
                (f" con args: {args}" if args else "")
            )
            
            try:
                # Ejecutar con args
                self.command_registry.execute(command, args)
                logger.debug(f"✅ Comando '{command}' ejecutado")
                
            except CommandNotAvailableError as e:
                logger.warning(f"⚠️ {e}")
                available = ', '.join(sorted(self.command_registry.available_commands))
                logger.info(f"💡 Comandos disponibles: {available}")
            
            except CommandValidationError as e:
                logger.error(f"❌ Validación falló: {e}")
                # Publicar error al orquestador
                self.publish_status("command_validation_error", metadata={'error': str(e)})
        
        except json.JSONDecodeError:
            logger.error(f"❌ Error decodificando JSON: {msg.payload}")
        except Exception as e:
            logger.error(f"❌ Error procesando mensaje: {e}", exc_info=True)
    
    def publish_status(self, status: str, metadata: Optional[dict] = None):
        """
        Publica status con metadata opcional
        
        Args:
            status: Estado (ej: "running", "paused", "fps_updated")
            metadata: Información adicional (ej: {'old': 2, 'new': 3})
        """
        message = {
            "status": status,
            "timestamp": time.time(),
            "client_id": self.client_id
        }
        
        if metadata:
            message['metadata'] = metadata
        
        self.client.publish(
            self.status_topic,
            json.dumps(message),
            qos=1,
            retain=True
        )
        logger.debug(f"📤 Status publicado: {status}")
```

**Uso desde el Orquestador:**

```python
# ORQUESTADOR (ejemplo conceptual)

import paho.mqtt.client as mqtt

class AdelineOrchestrator:
    """
    Orquestrador que controla Adeline
    
    Responsabilidades:
    - Monitorear métricas
    - Evaluar desempeño
    - Ajustar parámetros dinámicamente
    """
    
    def __init__(self):
        self.mqtt_client = mqtt.Client("orchestrator")
        self.mqtt_client.connect("localhost", 1883)
        self.mqtt_client.loop_start()
        
        # Suscribirse a métricas de Adeline
        self.mqtt_client.subscribe("inference/data/metrics")
        self.mqtt_client.subscribe("inference/control/status")
        self.mqtt_client.on_message = self._on_message
        
        self.current_fps = 0
        self.current_latency = 0
    
    def _on_message(self, client, userdata, msg):
        """Recibe métricas de Adeline"""
        data = json.loads(msg.payload)
        
        if msg.topic == "inference/data/metrics":
            self.current_fps = data.get('throughput_fps', 0)
            self.current_latency = data.get('latency_ms', 0)
            
            # Evaluar y ajustar
            self.evaluate_and_adjust()
    
    def evaluate_and_adjust(self):
        """
        Lógica de optimización del orquestador
        
        Ejemplos:
        - Si FPS < target → aumentar FPS
        - Si latencia alta → reducir FPS
        - Si muchos false positives → subir confidence
        """
        
        # Ejemplo 1: FPS muy bajo
        if self.current_fps < 1.5:
            logger.warning("FPS bajo detectado, aumentando target FPS")
            self.send_command("set_fps", {"value": 3.0})
        
        # Ejemplo 2: Latencia alta
        if self.current_latency > 500:
            logger.warning("Latencia alta, reduciendo FPS")
            self.send_command("set_fps", {"value": 1.5})
        
        # Ejemplo 3: Ajustar confidence según análisis
        if self.analyze_false_positives() > 0.1:  # 10% FP
            logger.info("Muchos false positives, subiendo confidence")
            self.send_command("set_confidence", {"value": 0.5})
    
    def send_command(self, command: str, args: dict = None):
        """Envía comando a Adeline"""
        message = {"command": command}
        if args:
            message['args'] = args
        
        self.mqtt_client.publish(
            "inference/control/commands",
            json.dumps(message),
            qos=1
        )
        logger.info(f"📤 Comando enviado: {command} {args}")
    
    def get_adeline_config(self):
        """Solicita config actual de Adeline"""
        self.send_command("get_config")
        # Recibirá respuesta en topic status
```

**Esfuerzo:** 2-3 días  
**ROI:** ⭐⭐⭐⭐⭐ (Crítico para que orquestador pueda controlar Adeline)

---

### 2. **Métricas Detalladas (para Orquestador)** ⭐⭐⭐⭐⭐

**Problema:** Métricas actuales son básicas, orquestador necesita más detalle

**Métricas actuales:**
```python
# Watchdog básico
{
    'throughput_fps': 2.0,
    'latency_ms': 100
}
```

**Métricas que el orquestador NECESITA:**

```python
# adeline/observability/metrics.py

class DetailedMetrics:
    """
    Métricas detalladas para el orquestador
    
    Objetivo: El orquestador necesita entender:
    - Calidad de detecciones (confidence promedio)
    - Estabilidad (cuántas detecciones confirmadas vs ignoradas)
    - Performance (latencies por etapa)
    - Salud (error rates)
    """
    
    def __init__(self):
        self.reset()
    
    def reset(self):
        """Reset counters"""
        self.frame_count = 0
        self.detection_count = 0
        self.confidence_sum = 0.0
        self.confidence_values = deque(maxlen=100)
        
        # Latencies por etapa
        self.latency_inference = deque(maxlen=100)
        self.latency_stabilization = deque(maxlen=100)
        self.latency_publish = deque(maxlen=100)
        
        # Estabilización stats
        self.detections_confirmed = 0
        self.detections_ignored = 0
        
        # Errores
        self.mqtt_errors = 0
        self.inference_errors = 0
    
    def record_detection(self, confidence: float):
        """Registra detección"""
        self.detection_count += 1
        self.confidence_sum += confidence
        self.confidence_values.append(confidence)
    
    def record_latency(self, stage: str, latency_ms: float):
        """Registra latency por etapa"""
        if stage == 'inference':
            self.latency_inference.append(latency_ms)
        elif stage == 'stabilization':
            self.latency_stabilization.append(latency_ms)
        elif stage == 'publish':
            self.latency_publish.append(latency_ms)
    
    def get_metrics_snapshot(self) -> dict:
        """
        Snapshot de métricas para el orquestador
        
        Returns:
            Dict con métricas detalladas
        """
        return {
            # Throughput
            'frames_processed': self.frame_count,
            'detections_total': self.detection_count,
            'detections_per_frame': self.detection_count / max(self.frame_count, 1),
            
            # Quality
            'avg_confidence': self.confidence_sum / max(self.detection_count, 1),
            'confidence_p50': self._percentile(self.confidence_values, 50),
            'confidence_p95': self._percentile(self.confidence_values, 95),
            
            # Latencies (ms)
            'latency_inference_p50': self._percentile(self.latency_inference, 50),
            'latency_inference_p95': self._percentile(self.latency_inference, 95),
            'latency_stabilization_p50': self._percentile(self.latency_stabilization, 50),
            'latency_publish_p50': self._percentile(self.latency_publish, 50),
            'latency_total_p95': (
                self._percentile(self.latency_inference, 95) +
                self._percentile(self.latency_stabilization, 95) +
                self._percentile(self.latency_publish, 95)
            ),
            
            # Estabilización
            'stabilization_confirm_rate': (
                self.detections_confirmed / max(self.detection_count, 1)
            ),
            'stabilization_ignore_rate': (
                self.detections_ignored / max(self.detection_count, 1)
            ),
            
            # Health
            'mqtt_error_rate': self.mqtt_errors / max(self.frame_count, 1),
            'inference_error_rate': self.inference_errors / max(self.frame_count, 1),
            
            # Timestamp
            'snapshot_timestamp': time.time()
        }
    
    @staticmethod
    def _percentile(values, percentile):
        """Calcula percentile simple"""
        if not values:
            return 0.0
        sorted_values = sorted(values)
        index = int(len(sorted_values) * percentile / 100)
        return sorted_values[min(index, len(sorted_values) - 1)]


# adeline/app/controller.py (INTEGRAR METRICS)

class InferencePipelineController:
    
    def __init__(self, config):
        # ...
        self.detailed_metrics = DetailedMetrics()
    
    def _handle_metrics(self):
        """
        Comando METRICS (MEJORADO)
        
        Ahora publica métricas detalladas
        """
        logger.info("📊 Comando METRICS recibido")
        
        try:
            # Obtener métricas básicas del watchdog
            watchdog_metrics = self.watchdog.get_report()
            
            # Obtener métricas detalladas
            detailed = self.detailed_metrics.get_metrics_snapshot()
            
            # Obtener stats de stabilization
            stab_stats = {}
            if self.stabilizer:
                stab_stats = self.stabilizer.get_stats(source_id=0)
            
            # Combinar todo
            full_metrics = {
                'type': 'detailed_metrics',
                'timestamp': time.time(),
                
                # Watchdog (FPS, latency básica)
                'watchdog': watchdog_metrics,
                
                # Detalladas (quality, latencies, health)
                'detailed': detailed,
                
                # Stabilization
                'stabilization': stab_stats
            }
            
            # Publicar
            self.data_plane.client.publish(
                self.config.METRICS_TOPIC,
                json.dumps(full_metrics, default=str),
                qos=0
            )
            
            logger.info(
                f"📊 Métricas detalladas publicadas: "
                f"FPS={watchdog_metrics.get('throughput_fps', 0):.2f}, "
                f"avg_conf={detailed['avg_confidence']:.2f}"
            )
        
        except Exception as e:
            logger.error(f"❌ Error publicando métricas: {e}", exc_info=True)
```

**Comando periódico desde el orquestador:**

```python
# ORQUESTADOR: Solicitar métricas cada 10 segundos

import schedule

def request_adeline_metrics():
    """Solicita métricas detalladas de Adeline"""
    mqtt_client.publish(
        "inference/control/commands",
        json.dumps({"command": "metrics"}),
        qos=1
    )

# Schedule
schedule.every(10).seconds.do(request_adeline_metrics)

while True:
    schedule.run_pending()
    time.sleep(1)
```

**Esfuerzo:** 1 día  
**ROI:** ⭐⭐⭐⭐⭐ (Crítico para que orquestador evalúe desempeño)

---

## 🟡 Prioridad 2: Confiabilidad Básica (Importante)

### 3. **QoS 1 + Retry Simple** ⭐⭐⭐⭐

**Cambio de evaluación anterior:**
- ❌ NO circuit breaker complejo (demasiado)
- ✅ SÍ retry simple (3 intentos)
- ✅ SÍ QoS 1 (guaranteed delivery)

```python
# SIMPLE Y EFECTIVO

class MQTTDataPlane:
    def publish_inference(self, predictions, video_frame):
        """Publish con retry simple"""
        
        message = self.detection_publisher.format_message(predictions, video_frame)
        
        # Retry loop simple
        for attempt in range(3):
            try:
                result = self.client.publish(
                    self.data_topic,
                    json.dumps(message, default=str),
                    qos=1  # ✅ At least once
                )
                
                # Wait for puback
                result.wait_for_publish(timeout=1.0)
                
                if result.rc == mqtt.MQTT_ERR_SUCCESS:
                    self.detailed_metrics.publish_success += 1
                    return True
                
                # Failed, retry
                logger.warning(f"Publish falló, retry {attempt+1}/3")
                time.sleep(0.1 * (2 ** attempt))  # Backoff exponencial
                
            except Exception as e:
                logger.error(f"Error en publish (intento {attempt+1}/3): {e}")
        
        # Falló después de 3 intentos
        self.detailed_metrics.mqtt_errors += 1
        logger.error("❌ Publish falló después de 3 intentos")
        return False
```

**Esfuerzo:** 0.5 días  
**ROI:** ⭐⭐⭐⭐ (Confiabilidad básica)

---

### 4. **Health Check Simple** ⭐⭐⭐⭐

**Cambio de evaluación anterior:**
- ❌ NO FastAPI completo (overkill)
- ✅ SÍ endpoint HTTP simple (stdlib)
- ✅ SÍ heartbeat MQTT periódico

```python
# adeline/observability/health_simple.py

from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import threading

class HealthHandler(BaseHTTPRequestHandler):
    """Simple health check handler"""
    
    # Shared state (inyectado desde controller)
    controller = None
    
    def do_GET(self):
        """Handle GET requests"""
        
        if self.path == '/health/live':
            # Liveness: ¿está vivo el proceso?
            self._respond(200, {'status': 'alive'})
        
        elif self.path == '/health/ready':
            # Readiness: ¿está listo para detectar?
            if self.controller is None:
                self._respond(503, {'status': 'not_ready', 'reason': 'controller not initialized'})
                return
            
            ready = (
                self.controller.is_running and
                self.controller.control_plane._connected.is_set() and
                self.controller.data_plane._connected.is_set()
            )
            
            if ready:
                self._respond(200, {'status': 'ready'})
            else:
                self._respond(503, {
                    'status': 'not_ready',
                    'pipeline_running': self.controller.is_running,
                    'mqtt_control_connected': self.controller.control_plane._connected.is_set(),
                    'mqtt_data_connected': self.controller.data_plane._connected.is_set()
                })
        
        else:
            self._respond(404, {'error': 'not_found'})
    
    def _respond(self, code, data):
        """Send JSON response"""
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())
    
    def log_message(self, format, *args):
        """Silenciar logs HTTP"""
        pass

def start_health_server(controller, port=8000):
    """Start simple health server in background thread"""
    HealthHandler.controller = controller
    
    server = HTTPServer(('0.0.0.0', port), HealthHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    
    logger.info(f"✅ Health server started on port {port}")
    return server

# USO en controller:
def setup(self):
    # ...
    start_health_server(self, port=8000)
```

**Esfuerzo:** 0.5 días  
**ROI:** ⭐⭐⭐⭐ (Kubernetes necesita probes)

---

## 🟢 Prioridad 3: Nice-to-Have

### 5. **Simulation Mode** ⭐⭐⭐
- Para testing sin cámara
- Esfuerzo: 1-2 días

### 6. **Config Hot Reload** ⭐⭐
- Ajustes sin restart
- Esfuerzo: 2 días

---

## 📊 API de Control (Documentación para Orquestador)

### Comandos Disponibles

| Comando | Args | Descripción | Ejemplo |
|---------|------|-------------|---------|
| `pause` | - | Pausa procesamiento | `{"command": "pause"}` |
| `resume` | - | Reanuda procesamiento | `{"command": "resume"}` |
| `stop` | - | Detiene y finaliza | `{"command": "stop"}` |
| `status` | - | Estado actual | `{"command": "status"}` |
| `metrics` | - | Métricas detalladas | `{"command": "metrics"}` |
| `set_fps` | `value: float` | Ajusta FPS | `{"command": "set_fps", "args": {"value": 3.0}}` |
| `set_confidence` | `value: float` | Ajusta threshold | `{"command": "set_confidence", "args": {"value": 0.5}}` |
| `set_roi_smoothing` | `value: float` | Ajusta suavizado | `{"command": "set_roi_smoothing", "args": {"value": 0.5}}` |
| `set_stabilization` | `min_frames, max_gap, appear_conf, persist_conf` | Ajusta filtrado | Ver ejemplo abajo |
| `reset_roi` | - | Resetea ROI | `{"command": "reset_roi"}` |
| `get_config` | - | Config actual | `{"command": "get_config"}` |
| `toggle_crop` | - | Toggle adaptive ROI | `{"command": "toggle_crop"}` (solo adaptive mode) |

### Ejemplo: Ajustar Stabilization

```json
{
  "command": "set_stabilization",
  "args": {
    "min_frames": 5,
    "max_gap": 3,
    "appear_conf": 0.6,
    "persist_conf": 0.4
  }
}
```

### Topics MQTT

| Topic | QoS | Descripción |
|-------|-----|-------------|
| `inference/control/commands` | 1 | Comandos para Adeline (pub por orquestador) |
| `inference/control/status` | 1 | Status de Adeline (sub por orquestador) |
| `inference/data/detections` | 1 | Detecciones (sub por analizador) |
| `inference/data/metrics` | 0 | Métricas (sub por orquestador) |
| `inference/sensor/heartbeat` | 0 | Heartbeat periódico (sub por orquestador) |

---

## 🎯 Plan de Implementación (1 semana)

### Sprint Único (Semana 1): Controlabilidad + Observabilidad

**Día 1-2: Comandos Parametrizados**
- CommandRegistry con args + validation
- Handlers: set_fps, set_confidence, set_roi_smoothing, set_stabilization
- Testing con orquestador mock

**Día 3: Métricas Detalladas**
- DetailedMetrics class
- Latencies por etapa
- Quality metrics (confidence p50/p95)

**Día 4: Confiabilidad Básica**
- QoS 1 + retry simple
- Health check HTTP simple
- Heartbeat MQTT

**Día 5: Documentation + Handoff**
- API de control (para orquestador)
- Message schemas
- Runbook

---

## 📈 Métricas de Éxito

| Métrica | Target | Medición |
|---------|--------|----------|
| **Comandos implementados** | 12+ | Count |
| **Command latency (p95)** | <100ms | Orquestador mide |
| **Metrics detail** | 15+ campos | Count en snapshot |
| **Delivery rate** | 99%+ | MQTT success / total |
| **Health check response** | <50ms | K8s probes |

---

## 🔚 Conclusión Final

### Cambio de Mentalidad

```diff
- ❌ "Hacer Adeline más inteligente"
+ ✅ "Hacer Adeline más controlable"

- ❌ "Auto-tuning sofisticado"
+ ✅ "Parámetros ajustables por orquestador"

- ❌ "Circuit breakers complejos"
+ ✅ "Retry simple + buenos reportes"

- ❌ "Vendor abstraction now"
+ ✅ "YAGNI - hacerlo cuando sea necesario"
```

### Top 3 Mejoras (Contexto Correcto)

1. ⭐⭐⭐⭐⭐ **Comandos Parametrizados** (2-3 días)
   - Orquestador puede ajustar Adeline en runtime
   - set_fps, set_confidence, set_roi_smoothing, set_stabilization

2. ⭐⭐⭐⭐⭐ **Métricas Detalladas** (1 día)
   - Orquestador evalúa desempeño con datos granulares
   - Latencies p50/p95, confidence stats, error rates

3. ⭐⭐⭐⭐ **Confiabilidad Básica** (1 día)
   - QoS 1 + retry simple (no circuit breaker complejo)
   - Health checks simples

### Principio Rector

> **"Adeline reporta bien y obedece. El orquestador decide."**

---

**Evaluado por:** Claude (Sonnet 4.5)  
**Contexto:** Adeline = Worker simple + Orquestador decide  
**Principio:** KISS (Keep It Simple, Stupid)  
**Fecha:** 22 de Octubre, 2025


