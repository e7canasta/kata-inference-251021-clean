# Evaluación de Arquitectura: Adeline Inference Pipeline (Sensor-Focused)

**Evaluación actualizada:** 22 de Octubre, 2025  
**Sistema:** Adeline - "Los Ojos" del Sistema (Sensor Layer)  
**Contexto:** Adeline es el **técnico radiólogo**, no el médico. Reporta lo que ve, no analiza.

---

## 🎯 Contexto Crítico: Arquitectura Distribuida

### Separación de Responsabilidades

```
┌──────────────────────────────────────────────────────────────────┐
│                     SISTEMA COMPLETO                             │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  📹 ADELINE (Sensor Layer - "Los Ojos")                         │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ RESPONSABILIDADES:                                         │ │
│  │ ✅ Capturar video (RTSP)                                   │ │
│  │ ✅ Detectar objetos (inference)                            │ │
│  │ ✅ Estabilizar detecciones (reduce flickering)             │ │
│  │ ✅ Reportar vía MQTT (fire-and-forget)                     │ │
│  │ ✅ Ser confiable (uptime, low latency)                     │ │
│  │ ✅ Observabilidad (health, metrics)                        │ │
│  │                                                            │ │
│  │ ❌ NO analiza escenas                                      │ │
│  │ ❌ NO toma decisiones                                      │ │
│  │ ❌ NO persiste historia (más allá de checkpoints)         │ │
│  │ ❌ NO genera gemelo digital                               │ │
│  └────────────────────────────────────────────────────────────┘ │
│                              │                                   │
│                              │ MQTT Data Plane                   │
│                              │ (detections stream)               │
│                              ▼                                   │
│  🧠 ANALIZADOR (Analysis Layer - "El Médico")                   │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ RESPONSABILIDADES:                                         │ │
│  │ ✅ Escuchar detecciones (MQTT subscriber)                  │ │
│  │ ✅ Generar gemelo digital de habitación                    │ │
│  │ ✅ Analizar patrones/comportamientos                       │ │
│  │ ✅ Tomar decisiones (alertas, acciones)                    │ │
│  │ ✅ Persistir estado/historia (database)                    │ │
│  │ ✅ Analytics avanzado (ML, predicciones)                   │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

---

## 📋 Re-Evaluación de Recomendaciones

### ❌ RECOMENDACIONES DESCARTADAS (Fuera de scope de Adeline)

#### 1. ~~Persistent State Management~~ → **RESPONSABILIDAD DEL ANALIZADOR**

**Por qué NO en Adeline:**
- Historia de detecciones → El analizador ya persiste
- Event sourcing → El analizador tiene el modelo completo
- Analytics queries → El analizador hace análisis

**Qué SÍ debe hacer Adeline:**
- ✅ Checkpointing mínimo de stabilization state (para restart sin flicker)
- ✅ Circular buffer de últimas N detecciones (para debugging/health check)
- ✅ NO base de datos completa, NO queries complejos

```python
# ✅ CORRECTO: Checkpoint ligero
class StabilizationCheckpointer:
    """Minimal checkpointing (solo para restart graceful)"""
    
    def save_checkpoint(self, stabilizer):
        """Save only active tracks (no history)"""
        checkpoint = {
            'active_tracks': stabilizer.get_active_tracks(),
            'timestamp': time.time()
        }
        # Save to local file (lightweight)
        with open('checkpoint.pkl', 'wb') as f:
            pickle.dump(checkpoint, f)

# ✅ CORRECTO: Circular buffer para debugging
class RecentDetectionsBuffer:
    """Last N detections for health check/debugging"""
    
    def __init__(self, maxlen: int = 100):
        self.buffer = deque(maxlen=maxlen)
    
    def add(self, detection):
        self.buffer.append(detection)
    
    def get_health_stats(self):
        """Return simple stats for health check"""
        if not self.buffer:
            return {'status': 'no_detections', 'count': 0}
        
        return {
            'status': 'ok',
            'count': len(self.buffer),
            'last_detection': self.buffer[-1]['timestamp'],
            'classes': Counter(d['class'] for d in self.buffer)
        }

# ❌ INCORRECTO: Database completa (responsabilidad del analizador)
# class DetectionRepository:
#     def save(self, detection):
#         self.db.execute("INSERT INTO detections ...")  # NO en Adeline
```

---

#### 2. ~~Analytics en Adeline~~ → **RESPONSABILIDAD DEL ANALIZADOR**

**Por qué NO en Adeline:**
- Pattern detection → El analizador tiene contexto completo
- Behavioral analysis → Requiere historia y múltiples fuentes
- Predictions → El analizador tiene el modelo de la escena

**Qué SÍ debe hacer Adeline:**
- ✅ Métricas de sensor (FPS, latency, error rate)
- ✅ Health checks (está vivo?, está detectando?)
- ✅ NO análisis de comportamientos, NO predicciones

---

### ✅ RECOMENDACIONES AJUSTADAS (Sensor-Focused)

Con el contexto correcto, las prioridades cambian:

---

## 🔴 Prioridad 1: Reliability del Sensor (Crítico)

### 1. **Guaranteed Delivery de Detecciones** ⭐⭐⭐⭐⭐

**Problema:** QoS 0 en Data Plane = puede perder detecciones

```python
# ACTUAL: Fire-and-forget (puede perder mensajes)
self.client.publish(
    self.data_topic,
    json.dumps(message),
    qos=0  # ⚠️ Sin garantía de delivery
)
```

**Impacto en sistema distribuido:**
- Analizador pierde detecciones → Gemelo digital incompleto
- Gaps en timeline → Análisis de comportamiento erróneo
- No hay forma de saber si mensaje llegó

**Solución: Hybrid QoS Strategy**

```python
class MQTTDataPlane:
    """
    Sensor-focused data plane con guaranteed delivery
    
    Strategy:
    - QoS 1 por default (at least once)
    - Confirmación de publish (puback)
    - Retry automático si falla
    - Circuit breaker si broker down
    """
    
    def __init__(
        self,
        broker_host: str,
        data_topic: str,
        qos: int = 1,  # ✅ Cambio a QoS 1
        max_retries: int = 3,
        retry_backoff: float = 0.1,
    ):
        self.qos = qos
        self.max_retries = max_retries
        self.retry_backoff = retry_backoff
        
        # Metrics
        self._publish_success = 0
        self._publish_failed = 0
        self._publish_retries = 0
    
    def publish_inference(
        self, 
        predictions, 
        video_frame,
        critical: bool = True  # Si es crítico, retry más agresivo
    ):
        """Publish con retry automático"""
        
        message = self.detection_publisher.format_message(predictions, video_frame)
        
        for attempt in range(self.max_retries if critical else 1):
            try:
                result = self.client.publish(
                    self.data_topic,
                    json.dumps(message, default=str),
                    qos=self.qos
                )
                
                # Wait for puback (confirmation)
                if self.qos > 0:
                    result.wait_for_publish(timeout=1.0)
                
                if result.rc == mqtt.MQTT_ERR_SUCCESS:
                    self._publish_success += 1
                    return True
                
                # Failed, retry
                self._publish_retries += 1
                logger.warning(
                    f"Publish failed (rc={result.rc}), "
                    f"retry {attempt+1}/{self.max_retries}"
                )
                time.sleep(self.retry_backoff * (2 ** attempt))
                
            except Exception as e:
                logger.error(f"Publish error: {e}", exc_info=True)
                if attempt == self.max_retries - 1:
                    self._publish_failed += 1
                    return False
        
        return False
    
    def get_reliability_metrics(self):
        """Metrics del sensor (para health check)"""
        total = self._publish_success + self._publish_failed
        if total == 0:
            return {'success_rate': 0.0, 'total': 0}
        
        return {
            'success_rate': self._publish_success / total,
            'total_published': self._publish_success,
            'total_failed': self._publish_failed,
            'total_retries': self._publish_retries,
            'avg_retries': self._publish_retries / total if total > 0 else 0
        }
```

**Configuración recomendada:**

```yaml
# config/adeline/config.yaml
mqtt:
  qos:
    control: 1  # Comandos (keep as is)
    data: 1     # ✅ Cambio: Detecciones son críticas (at least once)
  
  data_plane:
    max_retries: 3
    retry_backoff: 0.1  # seconds
    publish_timeout: 1.0  # wait for puback
```

**Trade-offs:**
- ➕ Garantiza delivery (critical para analizador)
- ➕ Analizador recibe todas las detecciones
- ➖ Slightly más latencia (wait for puback)
- ➖ Posible duplicación (analizador debe deduplicar)

**Esfuerzo:** 1 día  
**ROI:** ⭐⭐⭐⭐⭐ (Crítico para sistema distribuido)

---

### 2. **Observabilidad del Sensor (Health Checks)** ⭐⭐⭐⭐⭐

**Problema:** Analizador no sabe si Adeline está vivo, down, o degradado

**Solución: Health Check HTTP Endpoint + Heartbeat MQTT**

```python
# adeline/observability/health.py
from fastapi import FastAPI, status
from enum import Enum
from typing import Dict, Any
import time

class SensorHealth(str, Enum):
    """Health status del sensor"""
    HEALTHY = "healthy"      # Todo OK
    DEGRADED = "degraded"    # Funcional pero con problemas
    UNHEALTHY = "unhealthy"  # No funcional
    DOWN = "down"            # Completamente caído

app = FastAPI(title="Adeline Sensor Health")

# Global state (inyectado desde controller)
_controller = None

def set_controller(controller):
    global _controller
    _controller = controller

@app.get("/health/live", status_code=200)
def liveness():
    """
    Kubernetes liveness probe
    
    Responde si el proceso está vivo (no necesariamente funcional)
    """
    return {
        "status": "alive",
        "timestamp": time.time()
    }

@app.get("/health/ready")
def readiness():
    """
    Kubernetes readiness probe
    
    Responde si el sensor está listo para detectar
    """
    if _controller is None:
        return {
            "status": SensorHealth.DOWN,
            "reason": "Controller not initialized"
        }, status.HTTP_503_SERVICE_UNAVAILABLE
    
    checks = {
        'pipeline_running': _controller.is_running,
        'mqtt_control_connected': _controller.control_plane._connected.is_set(),
        'mqtt_data_connected': _controller.data_plane._connected.is_set(),
        'model_loaded': _controller.inference_handler is not None,
    }
    
    # All critical checks must pass
    all_ok = all(checks.values())
    
    if all_ok:
        return {
            "status": SensorHealth.HEALTHY,
            "checks": checks,
            "timestamp": time.time()
        }
    
    # Degraded: some checks fail but not all
    critical_ok = checks['pipeline_running'] and checks['model_loaded']
    if critical_ok:
        return {
            "status": SensorHealth.DEGRADED,
            "checks": checks,
            "reason": "MQTT connection issues",
            "timestamp": time.time()
        }, status.HTTP_503_SERVICE_UNAVAILABLE
    
    # Unhealthy: critical checks fail
    return {
        "status": SensorHealth.UNHEALTHY,
        "checks": checks,
        "timestamp": time.time()
    }, status.HTTP_503_SERVICE_UNAVAILABLE

@app.get("/health/sensor")
def sensor_health():
    """
    Sensor-specific health (para el analizador)
    
    Incluye métricas de calidad del sensor:
    - FPS actual
    - Latency
    - Detection rate
    - Publish success rate
    """
    if _controller is None:
        return {
            "status": SensorHealth.DOWN
        }, status.HTTP_503_SERVICE_UNAVAILABLE
    
    # Watchdog metrics
    watchdog = _controller.watchdog
    metrics = watchdog.get_report() if watchdog else {}
    
    # Data plane reliability
    reliability = _controller.data_plane.get_reliability_metrics()
    
    # Recent detections buffer
    recent = _controller.recent_detections.get_health_stats()
    
    # Calculate health based on metrics
    fps = metrics.get('throughput_fps', 0)
    success_rate = reliability.get('success_rate', 0)
    
    # Health thresholds
    if fps >= 1.5 and success_rate >= 0.95:
        sensor_status = SensorHealth.HEALTHY
    elif fps >= 1.0 and success_rate >= 0.80:
        sensor_status = SensorHealth.DEGRADED
    else:
        sensor_status = SensorHealth.UNHEALTHY
    
    return {
        "status": sensor_status,
        "metrics": {
            "fps": fps,
            "latency_ms": metrics.get('latency_ms', 0),
            "publish_success_rate": success_rate,
            "recent_detections": recent['count'],
            "last_detection_age_sec": time.time() - recent.get('last_detection', time.time())
        },
        "timestamp": time.time()
    }

@app.get("/health/metrics")
def prometheus_metrics():
    """
    Prometheus-compatible metrics endpoint
    
    Permite scraping por Prometheus para dashboards
    """
    if _controller is None:
        return "# Sensor down\n"
    
    metrics = _controller.watchdog.get_report()
    reliability = _controller.data_plane.get_reliability_metrics()
    
    # Prometheus format
    output = []
    output.append(f"# HELP adeline_fps Frames per second")
    output.append(f"# TYPE adeline_fps gauge")
    output.append(f"adeline_fps {metrics.get('throughput_fps', 0)}")
    
    output.append(f"# HELP adeline_publish_success_rate MQTT publish success rate")
    output.append(f"# TYPE adeline_publish_success_rate gauge")
    output.append(f"adeline_publish_success_rate {reliability.get('success_rate', 0)}")
    
    output.append(f"# HELP adeline_publish_total Total publishes")
    output.append(f"# TYPE adeline_publish_total counter")
    output.append(f"adeline_publish_total {reliability.get('total_published', 0)}")
    
    output.append(f"# HELP adeline_publish_failed_total Failed publishes")
    output.append(f"# TYPE adeline_publish_failed_total counter")
    output.append(f"adeline_publish_failed_total {reliability.get('total_failed', 0)}")
    
    return "\n".join(output)

# Iniciar en thread separado
def start_health_server(controller, port: int = 8000):
    """Start health check server in separate thread"""
    import uvicorn
    from threading import Thread
    
    set_controller(controller)
    
    def run():
        uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning")
    
    thread = Thread(target=run, daemon=True)
    thread.start()
    logger.info(f"✅ Health server started on port {port}")
```

**Heartbeat MQTT (alternativa/complemento):**

```python
# adeline/observability/heartbeat.py
import threading
import time

class SensorHeartbeat:
    """
    Publica heartbeat periódico en MQTT
    
    El analizador puede monitorear si Adeline está vivo
    sin necesidad de HTTP polling
    """
    
    def __init__(
        self,
        control_plane,
        interval: float = 5.0,  # Heartbeat cada 5 segundos
        topic: str = "inference/sensor/heartbeat"
    ):
        self.control_plane = control_plane
        self.interval = interval
        self.topic = topic
        self._stop_event = threading.Event()
        self._thread = None
        
    def start(self):
        """Start heartbeat thread"""
        self._thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        self._thread.start()
        logger.info(f"✅ Heartbeat started (interval={self.interval}s)")
    
    def stop(self):
        """Stop heartbeat"""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2.0)
    
    def _heartbeat_loop(self):
        """Heartbeat loop (runs in background thread)"""
        while not self._stop_event.is_set():
            try:
                # Get current health
                metrics = self._get_sensor_metrics()
                
                # Publish heartbeat
                heartbeat = {
                    'sensor_id': self.control_plane.client_id,
                    'timestamp': time.time(),
                    'status': 'alive',
                    'metrics': metrics
                }
                
                self.control_plane.client.publish(
                    self.topic,
                    json.dumps(heartbeat),
                    qos=0,  # Heartbeat no crítico (si se pierde uno, viene otro en 5s)
                    retain=True  # Último heartbeat siempre disponible
                )
                
            except Exception as e:
                logger.error(f"Heartbeat error: {e}")
            
            # Wait for next heartbeat
            self._stop_event.wait(timeout=self.interval)
    
    def _get_sensor_metrics(self):
        """Get current sensor metrics for heartbeat"""
        # TODO: Obtener de watchdog/data plane
        return {
            'fps': 2.0,
            'uptime_seconds': time.time() - self._start_time
        }

# USO en Controller:
class InferencePipelineController:
    def setup(self):
        # ... existing setup ...
        
        # Start health server
        start_health_server(self, port=8000)
        
        # Start heartbeat
        self.heartbeat = SensorHeartbeat(self.control_plane)
        self.heartbeat.start()
```

**Configuración Kubernetes:**

```yaml
# kubernetes/adeline-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: adeline-sensor
spec:
  template:
    spec:
      containers:
      - name: adeline
        image: adeline:latest
        ports:
        - containerPort: 8000
          name: health
        
        # Liveness probe (restart si muerto)
        livenessProbe:
          httpGet:
            path: /health/live
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
          timeoutSeconds: 5
          failureThreshold: 3
        
        # Readiness probe (quitar del load balancer si no ready)
        readinessProbe:
          httpGet:
            path: /health/ready
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 5
          timeoutSeconds: 3
          failureThreshold: 2
        
        # Resources
        resources:
          requests:
            cpu: 1000m
            memory: 2Gi
          limits:
            cpu: 2000m
            memory: 4Gi

---
# Prometheus ServiceMonitor
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: adeline-sensor
spec:
  selector:
    matchLabels:
      app: adeline
  endpoints:
  - port: health
    path: /health/metrics
    interval: 15s
```

**Esfuerzo:** 1-2 días  
**ROI:** ⭐⭐⭐⭐⭐ (Critical - analizador necesita saber si sensor está vivo)

---

### 3. **Circuit Breaker para MQTT** ⭐⭐⭐⭐

**Problema:** Si broker cae, Adeline sigue intentando publicar (waste resources)

**Solución:**

```python
# adeline/resilience/circuit_breaker.py
from enum import Enum
from datetime import datetime, timedelta
import threading

class CircuitState(Enum):
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, stop trying
    HALF_OPEN = "half_open"  # Testing recovery

class CircuitBreaker:
    """
    Circuit breaker para MQTT broker
    
    States:
    - CLOSED: Normal (todas las requests pasan)
    - OPEN: Broker down (fail fast sin intentar)
    - HALF_OPEN: Testing (permite algunas requests para probar recovery)
    """
    
    def __init__(
        self,
        failure_threshold: int = 5,      # Failures antes de abrir circuito
        recovery_timeout: float = 30.0,  # Segundos antes de intentar recovery
        success_threshold: int = 2,      # Successes para cerrar circuito
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.success_threshold = success_threshold
        
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None
        self._lock = threading.Lock()
    
    def call(self, func, *args, **kwargs):
        """
        Execute function through circuit breaker
        
        Returns:
            (success: bool, result: Any)
        """
        with self._lock:
            # Check if we should attempt call
            if not self._should_attempt():
                logger.warning("Circuit breaker OPEN, skipping call")
                return False, None
            
            # Attempt call
            try:
                result = func(*args, **kwargs)
                self._on_success()
                return True, result
                
            except Exception as e:
                self._on_failure()
                raise
    
    def _should_attempt(self) -> bool:
        """Should we attempt the call?"""
        if self.state == CircuitState.CLOSED:
            return True
        
        if self.state == CircuitState.OPEN:
            # Check if recovery timeout passed
            if self.last_failure_time is None:
                return False
            
            elapsed = (datetime.now() - self.last_failure_time).total_seconds()
            if elapsed >= self.recovery_timeout:
                # Try recovery
                logger.info("Circuit breaker entering HALF_OPEN state (testing recovery)")
                self.state = CircuitState.HALF_OPEN
                return True
            
            return False
        
        if self.state == CircuitState.HALF_OPEN:
            # Allow some requests to test
            return True
        
        return False
    
    def _on_success(self):
        """Handle successful call"""
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            
            if self.success_count >= self.success_threshold:
                logger.info("Circuit breaker CLOSED (recovery successful)")
                self.state = CircuitState.CLOSED
                self.failure_count = 0
                self.success_count = 0
    
    def _on_failure(self):
        """Handle failed call"""
        self.last_failure_time = datetime.now()
        self.failure_count += 1
        
        if self.state == CircuitState.CLOSED:
            if self.failure_count >= self.failure_threshold:
                logger.error(
                    f"Circuit breaker OPEN ({self.failure_count} consecutive failures)"
                )
                self.state = CircuitState.OPEN
        
        elif self.state == CircuitState.HALF_OPEN:
            # Failed during recovery, back to OPEN
            logger.warning("Circuit breaker back to OPEN (recovery failed)")
            self.state = CircuitState.OPEN
            self.success_count = 0

# USO:
class MQTTDataPlane:
    def __init__(self, ...):
        # ...
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=5,
            recovery_timeout=30.0,
            success_threshold=2
        )
    
    def publish_inference(self, predictions, video_frame):
        """Publish con circuit breaker"""
        
        # Wrap publish en circuit breaker
        success, result = self.circuit_breaker.call(
            self._do_publish,
            predictions,
            video_frame
        )
        
        if not success:
            # Circuit breaker open, log y continuar
            logger.warning(
                "Skipping publish (circuit breaker OPEN). "
                "Broker likely down, will retry in 30s"
            )
            return False
        
        return result
    
    def _do_publish(self, predictions, video_frame):
        """Actual publish logic"""
        message = self.detection_publisher.format_message(predictions, video_frame)
        result = self.client.publish(...)
        
        if result.rc != mqtt.MQTT_ERR_SUCCESS:
            raise Exception(f"Publish failed: {result.rc}")
        
        return True
```

**Esfuerzo:** 1 día  
**ROI:** ⭐⭐⭐⭐ (Resilience importante)

---

## 🟡 Prioridad 2: Data Quality (Importante)

### 4. **Message Timestamping + Sequence Numbers** ⭐⭐⭐⭐

**Problema:** Analizador no puede detectar:
- Mensajes fuera de orden
- Gaps en detecciones
- Clock drift entre sensores

**Solución:**

```python
# adeline/data/publishers/detection.py
class DetectionPublisher:
    def __init__(self):
        self._sequence_number = 0
        self._lock = threading.Lock()
    
    def format_message(self, predictions, video_frame):
        """Format con timestamp + sequence"""
        
        with self._lock:
            self._sequence_number += 1
            seq = self._sequence_number
        
        return {
            # Metadata del sensor
            'sensor_id': 'adeline-01',  # ID único del sensor
            'sensor_type': 'vision',
            
            # Timing
            'timestamp': time.time(),  # Unix timestamp (sensor time)
            'frame_timestamp': video_frame.timestamp if hasattr(video_frame, 'timestamp') else None,
            'sequence_number': seq,  # Monotonic sequence (detectar gaps)
            
            # Detections
            'detections': [
                {
                    'class': pred.get('class'),
                    'confidence': pred.get('confidence'),
                    'bbox': {
                        'x': pred.get('x'),
                        'y': pred.get('y'),
                        'width': pred.get('width'),
                        'height': pred.get('height')
                    },
                    # Metadata de estabilización (si aplica)
                    'stabilization': pred.get('_stabilization', {})
                }
                for pred in predictions.get('predictions', [])
            ],
            
            # Source info
            'source_id': video_frame.source_id if hasattr(video_frame, 'source_id') else 0,
            
            # Frame info
            'frame_id': video_frame.frame_id if hasattr(video_frame, 'frame_id') else None,
            'frame_shape': {
                'width': video_frame.image.shape[1] if hasattr(video_frame, 'image') else None,
                'height': video_frame.image.shape[0] if hasattr(video_frame, 'image') else None
            }
        }
```

**El analizador puede entonces:**

```python
# Analyzer side (ejemplo conceptual)
class DetectionConsumer:
    def __init__(self):
        self.last_sequence = {}  # sensor_id -> last seq
    
    def on_detection(self, message):
        sensor_id = message['sensor_id']
        seq = message['sequence_number']
        
        # Detectar gaps
        if sensor_id in self.last_sequence:
            expected = self.last_sequence[sensor_id] + 1
            if seq != expected:
                gap_size = seq - expected
                logger.warning(
                    f"Gap detected from {sensor_id}: "
                    f"expected seq={expected}, got seq={seq} "
                    f"(gap of {gap_size} messages)"
                )
                # Puede decidir interpolar, alertar, etc.
        
        self.last_sequence[sensor_id] = seq
        
        # Detectar out-of-order
        timestamp = message['timestamp']
        if self._is_out_of_order(sensor_id, timestamp):
            logger.warning(f"Out-of-order message from {sensor_id}")
        
        # Process detections...
```

**Esfuerzo:** 0.5 días  
**ROI:** ⭐⭐⭐⭐ (Crítico para confiabilidad del analizador)

---

### 5. **Vendor Abstraction Layer** ⭐⭐⭐

**Por qué sigue siendo importante:**
Aunque Adeline sea solo sensor, si el vendor cambia API (Inference SDK update), todo el código se rompe.

**Pero:** Prioridad BAJA porque:
- Funciona actualmente
- No hay planes de cambiar vendor
- Refactoring grande sin beneficio inmediato

**Recomendación:** Postponer hasta que:
1. Haya necesidad real de cambiar vendor
2. O SDK upgrade rompa compatibilidad

**Esfuerzo:** 3-5 días  
**ROI:** ⭐⭐ (Nice-to-have, no crítico)

---

## 🟢 Prioridad 3: Developer Experience

### 6. **Simulation Mode (Testing sin cámara)** ⭐⭐⭐⭐

**Problema:** Testing requiere RTSP stream real (difícil de automatizar)

**Solución:**

```python
# adeline/simulation/frame_generator.py
class SimulatedFrameGenerator:
    """Genera frames sintéticos para testing"""
    
    def __init__(self, fps: int = 2, duration: int = 60):
        self.fps = fps
        self.duration = duration
    
    def generate_frames(self):
        """Generator de frames sintéticos"""
        import numpy as np
        import cv2
        
        frame_count = int(self.fps * self.duration)
        
        for i in range(frame_count):
            # Generar frame sintético (imagen con formas)
            frame = np.zeros((480, 640, 3), dtype=np.uint8)
            
            # Dibujar "persona" que se mueve
            x = int(320 + 100 * np.sin(i / 10))
            y = 240
            cv2.circle(frame, (x, y), 30, (255, 0, 0), -1)
            
            yield {
                'image': frame,
                'frame_id': i,
                'timestamp': time.time(),
                'source_id': 0
            }
            
            time.sleep(1.0 / self.fps)

# USO en testing:
def test_pipeline_with_simulated_frames():
    """Test pipeline sin cámara real"""
    
    # Setup con simulation mode
    config = AdelineConfig(
        pipeline=PipelineSettings(
            rtsp_url="simulation://person_walking",  # Special URL
            max_fps=2
        )
    )
    
    controller = InferencePipelineController(config.to_legacy_config())
    
    # Inject simulated frame generator
    controller.frame_generator = SimulatedFrameGenerator(fps=2, duration=10)
    
    # Run pipeline
    controller.setup()
    controller.run()
    
    # Verify detections published
    # ...
```

**Esfuerzo:** 1-2 días  
**ROI:** ⭐⭐⭐⭐ (Mejor DX, CI/CD más fácil)

---

## 📊 Contrato Sensor ↔ Analizador

### Message Schema (Contract)

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "Detection Message",
  "description": "Message contract entre Adeline (sensor) y Analizador",
  
  "type": "object",
  "required": ["sensor_id", "timestamp", "sequence_number", "detections"],
  
  "properties": {
    "sensor_id": {
      "type": "string",
      "description": "Unique sensor identifier"
    },
    "sensor_type": {
      "type": "string",
      "enum": ["vision", "audio", "lidar"],
      "default": "vision"
    },
    "timestamp": {
      "type": "number",
      "description": "Unix timestamp (sensor time)"
    },
    "sequence_number": {
      "type": "integer",
      "description": "Monotonic sequence number (detect gaps)"
    },
    "detections": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["class", "confidence", "bbox"],
        "properties": {
          "class": {"type": "string"},
          "confidence": {"type": "number", "minimum": 0, "maximum": 1},
          "bbox": {
            "type": "object",
            "required": ["x", "y", "width", "height"],
            "properties": {
              "x": {"type": "number"},
              "y": {"type": "number"},
              "width": {"type": "number"},
              "height": {"type": "number"}
            }
          },
          "stabilization": {
            "type": "object",
            "properties": {
              "avg_confidence": {"type": "number"},
              "frames_tracked": {"type": "integer"}
            }
          }
        }
      }
    },
    "source_id": {"type": "integer"},
    "frame_id": {"type": "integer"},
    "frame_shape": {
      "type": "object",
      "properties": {
        "width": {"type": "integer"},
        "height": {"type": "integer"}
      }
    }
  }
}
```

**Contract Testing:**

```python
# tests/contract/test_message_schema.py
import jsonschema

def test_detection_message_schema():
    """Verify message contract"""
    
    schema = load_schema('detection_message.schema.json')
    
    # Generate sample message from Adeline
    message = create_sample_detection_message()
    
    # Validate against schema
    jsonschema.validate(instance=message, schema=schema)
    
    # Analizador también valida al recibir
    # (si falla, sensor rompió contrato)
```

---

## 📋 Checklist Final: Adeline como Sensor Perfecto

### ✅ Reliability (Crítico)
- [ ] QoS 1 para detecciones (guaranteed delivery)
- [ ] Retry automático en publish failures
- [ ] Circuit breaker para MQTT broker
- [ ] Health checks HTTP (liveness, readiness, sensor health)
- [ ] Heartbeat MQTT periódico
- [ ] Graceful shutdown (flush pending messages)

### ✅ Data Quality (Importante)
- [ ] Timestamps precisos (Unix time)
- [ ] Sequence numbers (detectar gaps)
- [ ] Message schema validation (contrato claro)
- [ ] Stabilization metadata (confianza promedio, frames tracked)

### ✅ Observability (Importante)
- [ ] Prometheus metrics (FPS, latency, publish rate, errors)
- [ ] Health status (healthy/degraded/unhealthy)
- [ ] Recent detections buffer (debugging)
- [ ] Publish success rate tracking

### ⚠️ Nice-to-Have (No crítico)
- [ ] Vendor abstraction layer (postponer)
- [ ] Simulation mode (testing sin cámara)
- [ ] Config hot reload (ajustes sin restart)

### ❌ Out of Scope (Responsabilidad del Analizador)
- ❌ Persistent storage de detecciones
- ❌ Historical analytics
- ❌ Scene understanding
- ❌ Decision making
- ❌ Gemelo digital

---

## 🎯 Plan de Implementación (1-2 semanas)

### Sprint 1 (Semana 1): Reliability

**Día 1-2: Guaranteed Delivery**
- Cambiar Data Plane a QoS 1
- Implementar retry logic
- Testing con broker down/recovery

**Día 3-4: Health Checks**
- HTTP health endpoints (FastAPI)
- Kubernetes probes configuration
- MQTT heartbeat

**Día 5: Circuit Breaker**
- Implementar circuit breaker
- Testing con broker failures
- Metrics de circuit breaker state

### Sprint 2 (Semana 2): Data Quality + Observability

**Día 1-2: Message Enhancements**
- Agregar timestamps + sequence numbers
- Message schema validation
- Contract testing

**Día 3-4: Prometheus Integration**
- Metrics endpoint
- Grafana dashboard
- Alerting rules

**Día 5: Documentation + Handoff**
- Documentar contrato sensor↔analizador
- README para el analizador (cómo consumir mensajes)
- Runbook (troubleshooting common issues)

---

## 📈 Métricas de Éxito del Sensor

| Métrica | Target | Medición |
|---------|--------|----------|
| **Uptime** | 99.5% | Kubernetes metrics |
| **Detection Delivery Rate** | 99.9% | MQTT publish success / total |
| **Max Latency (detection → publish)** | <100ms | p95 latency |
| **Health Check Response Time** | <50ms | p95 response time |
| **Time to Recovery** | <30s | Circuit breaker recovery time |
| **FPS Stability** | ±10% variance | Watchdog metrics |

---

## 🔚 Conclusión

Con el contexto correcto (**Adeline = Sensor**), las prioridades cambian dramáticamente:

### Top 3 Mejoras (Sensor-Focused):

1. ⭐⭐⭐⭐⭐ **Guaranteed Delivery** (QoS 1, retry, circuit breaker)
   - **Por qué:** Analizador necesita TODAS las detecciones
   - **Esfuerzo:** 3 días

2. ⭐⭐⭐⭐⭐ **Health Checks** (HTTP endpoints, heartbeat, Prometheus)
   - **Por qué:** Analizador debe saber si sensor está vivo
   - **Esfuerzo:** 2 días

3. ⭐⭐⭐⭐ **Message Quality** (timestamps, sequences, schema)
   - **Por qué:** Analizador necesita detectar gaps/out-of-order
   - **Esfuerzo:** 1 día

### Descartadas (Out of Scope):
- ❌ Persistent storage (responsabilidad del analizador)
- ❌ Analytics (responsabilidad del analizador)
- ❌ Scene understanding (responsabilidad del analizador)

**Adeline debe ser el mejor sensor posible:** confiable, observable, y con datos de alta calidad. El análisis lo hace el componente especializado.

---

**Evaluado por:** Claude (Sonnet 4.5)  
**Contexto actualizado:** Adeline es "Los Ojos", no el "Cerebro"  
**Fecha:** 22 de Octubre, 2025

