# Guía de Handlers y Listeners en InferencePipeline

## 🎯 Resumen Rápido

| Handler | Propósito | Cuándo Usarlo |
|---------|-----------|---------------|
| **`status_update_handlers`** | Eventos de estado del pipeline | Errores, conexiones, warnings |
| **`watchdog`** | Métricas de rendimiento | Latencia, FPS, profiling |
| **`on_pipeline_start/end`** | Inicio/fin del pipeline | Logging, setup, cleanup |

---

## 1️⃣ `status_update_handlers` - Eventos del Pipeline

### ¿Qué es?
Lista de funciones callback que reciben objetos `StatusUpdate` cuando ocurren eventos en el pipeline.

### ¿Qué información recibo?
```python
StatusUpdate(
    timestamp=datetime,      # Cuándo ocurrió
    severity=UpdateSeverity, # DEBUG, INFO, WARNING, ERROR
    event_type=str,          # Tipo de evento
    payload=dict,            # Datos adicionales
    context=str             # Contexto adicional
)
```

### Tipos de eventos comunes:
- `SOURCE_CONNECTION_ATTEMPT_FAILED`
- `SOURCE_CONNECTION_LOST`
- `INFERENCE_RESULTS_DISPATCHING_ERROR`
- `INFERENCE_THREAD_STARTED`
- `INFERENCE_THREAD_FINISHED`
- `INFERENCE_COMPLETED`
- `INFERENCE_ERROR`

### Casos de uso:
- ✅ Detectar problemas de conexión
- ✅ Logging de errores
- ✅ Enviar alertas/notificaciones
- ✅ Reintentar operaciones fallidas
- ✅ Actualizar UI con estado del pipeline

### Ejemplo básico:
```python
def my_status_handler(status: StatusUpdate) -> None:
    if status.severity == UpdateSeverity.ERROR:
        send_alert(f"Error en pipeline: {status.event_type}")
    
    if "CONNECTION" in status.event_type:
        log_connection_issue(status)

pipeline = InferencePipeline.init(
    ...,
    status_update_handlers=[my_status_handler]
)
```

---

## 2️⃣ `watchdog` (PipelineWatchDog) - Métricas de Rendimiento

### ¿Qué es?
Objeto que monitorea el rendimiento del pipeline (latencias, throughput, etc.)

### ¿Qué información recibo?
```python
PipelineStateReport(
    inference_throughput=float,           # FPS del pipeline
    latency_reports=[                     # Por cada source
        LatencyMonitorReport(
            source_id=int,
            frame_decoding_latency=float, # Tiempo de decodificación
            inference_latency=float,      # Tiempo de inferencia
            e2e_latency=float,           # Latencia total
        )
    ],
    video_source_status_updates=[...],    # Histórico de updates
    sources_metadata=[...]                # Info de cada source
)
```

### Casos de uso:
- ✅ Profiling del pipeline
- ✅ Detectar cuellos de botella
- ✅ Optimizar rendimiento
- ✅ Dashboards de métricas
- ✅ Análisis de capacidad

### Implementaciones disponibles:
- `NullPipelineWatchdog` - No hace nada (default)
- `BasePipelineWatchDog` - Implementación base con métricas
- Custom - Puedes extender `BasePipelineWatchDog`

### Ejemplo básico:
```python
from inference.core.interfaces.stream.watchdog import BasePipelineWatchDog

watchdog = BasePipelineWatchDog()

pipeline = InferencePipeline.init(
    ...,
    watchdog=watchdog
)

pipeline.start()

# En cualquier momento puedes obtener métricas:
report = watchdog.get_report()
print(f"FPS: {report.inference_throughput}")
```

---

## 3️⃣ `on_pipeline_start` / `on_pipeline_end` - Lifecycle Hooks

### ¿Qué son?
Callbacks simples que se ejecutan al inicio y fin del pipeline.

### Casos de uso:
- ✅ Logging de inicio/fin
- ✅ Inicializar recursos externos
- ✅ Cleanup de recursos
- ✅ Métricas de tiempo total
- ✅ Notificaciones de lifecycle

### Ejemplo:
```python
def on_start():
    logger.info("Pipeline iniciado")
    db.mark_pipeline_running()

def on_end():
    logger.info("Pipeline finalizado")
    db.mark_pipeline_stopped()

# NOTA: init() NO acepta estos parámetros en modelos estándar
# Solo están disponibles en init_with_workflow() y init_with_custom_logic()
```

---

## 🏗️ Arquitectura Recomendada

### Opción 1: Simple (solo status handlers)
```python
pipeline = InferencePipeline.init(
    ...,
    status_update_handlers=[my_handler]
)
```
**Úsalo cuando:** Solo necesitas saber qué está pasando (errores, conexiones)

### Opción 2: Con Métricas (watchdog)
```python
watchdog = BasePipelineWatchDog()
pipeline = InferencePipeline.init(
    ...,
    watchdog=watchdog,
    status_update_handlers=[my_handler]
)
```
**Úsalo cuando:** Necesitas optimizar rendimiento o dashboards

### Opción 3: Completo (todo integrado)
```python
class MyWatchdog(BasePipelineWatchDog):
    def on_status_update(self, status):
        # Lógica personalizada
        super().on_status_update(status)

watchdog = MyWatchdog()
pipeline = InferencePipeline.init(
    ...,
    watchdog=watchdog,
    status_update_handlers=[
        handler1,
        handler2,
        handler3,
    ]
)
```
**Úsalo cuando:** Aplicación en producción con monitoreo completo

---

## 📋 Checklist de Decisión

¿Qué necesito monitorear?

- [ ] **Errores de conexión** → `status_update_handlers`
- [ ] **Warnings del pipeline** → `status_update_handlers`
- [ ] **FPS/Throughput** → `watchdog`
- [ ] **Latencia de inferencia** → `watchdog`
- [ ] **Tiempo de decodificación** → `watchdog`
- [ ] **Setup inicial** → `on_pipeline_start` (si disponible)
- [ ] **Cleanup final** → `on_pipeline_end` (si disponible)

---

## 🔍 Debugging Tips

### Ver todos los eventos:
```python
def debug_handler(status: StatusUpdate):
    print(f"[{status.severity.name}] {status.event_type}")
    print(f"  Payload: {status.payload}")
```

### Ver solo errores críticos:
```python
def error_handler(status: StatusUpdate):
    if status.severity == UpdateSeverity.ERROR:
        print(f"ERROR: {status.event_type}")
```

### Métricas cada N segundos:
```python
import time
from threading import Thread

def monitor(watchdog, interval=10):
    while True:
        time.sleep(interval)
        report = watchdog.get_report()
        print(f"FPS: {report.inference_throughput}")

Thread(target=monitor, args=(watchdog,), daemon=True).start()
```

---

## 📚 Referencias

- `run_pipeline.py` - Ejemplo básico con status_update_handlers
- `run_pipeline_with_watchdog.py` - Ejemplo completo con watchdog y monitoreo
- Documentación Inference SDK: [inference.roboflow.com](https://inference.roboflow.com)

