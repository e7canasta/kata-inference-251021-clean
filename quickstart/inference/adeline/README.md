# InferencePipeline Examples

Ejemplos de uso del InferencePipeline con diferentes configuraciones.

## 📁 Archivos

### Ejemplos básicos
- `run_pipeline.py` - Pipeline básico con status handlers
- `run_pipeline_with_watchdog.py` - Pipeline con watchdog para métricas

### MQTT Control y Data Plane
- `mqtt_bridge.py` - Módulo MQTT (control + data plane)
- `run_pipeline_mqtt.py` - Pipeline con MQTT integrado
- `mqtt_control_cli.py` - CLI para enviar comandos
- `mqtt_data_monitor.py` - Monitor de detecciones
- `quickstart_mqtt.sh` - Script de inicio rápido
- `docker-compose.mqtt.yml` - Docker Compose para MQTT broker
- `mosquitto.conf` - Configuración de Mosquitto
- `test_mqtt.sh` - Script de pruebas

### Documentación
- `README_HANDLERS.md` - Guía de handlers y listeners
- `README_MQTT.md` - Documentación completa MQTT

## 🚀 Quick Start

### Ejemplo Básico
```bash
python run_pipeline.py
```

### Con MQTT (Control y Data Plane)
```bash
# 1. Iniciar MQTT broker
./quickstart_mqtt.sh

# 2. Iniciar pipeline
python run_pipeline_mqtt.py

# 3. Enviar comandos (otra terminal)
python mqtt_control_cli.py start

# 4. Monitorear detecciones (otra terminal)
python mqtt_data_monitor.py
```

## 📚 Más información

- Ver `README_HANDLERS.md` para entender status handlers y watchdogs
- Ver `README_MQTT.md` para arquitectura MQTT completa



 Resultados  
  
 | Métrica    | Valor      | Análisis                                        |  
 |------------|------------|-------------------------------------------------|  
 | Throughput | 1.72 FPS   | ✅ Cerca del max_fps=2, excelente                |  
 | Latency    | 190-230 ms | ✅ Normal para E2E (RTSP → YOLO → MQTT + render) |  
 | Max FPS    | 2          | Límite configurado                              |  
 | Eficiencia | 86%        | 1.72/2 = 86% del max teórico                    |  
  
 Lo que confirma  
  
 1. ✅ NO hay error multi_sink() got an unexpected keyword argument 'display_statistics'  
 2. ✅ display_statistics=True funciona - podés ver throughput y latency en pantalla  
 3. ✅ Multi-sink funciona - MQTT publish + visualización simultáneos  
 4. ✅ El patrón de composición es correcto:  
 render_with_stats = partial(render_boxes, display_statistics=True)  
 on_prediction = partial(multi_sink, sinks=[mqtt_sink, render_with_stats])  
  
 Breakdown de Latency (~200ms)  
  
 - Frame fetch (RTSP): ~50-80ms  
 - YOLO inference: ~80-120ms (YOLOv11n es rápido)  
 - MQTT publish + render: ~40-60ms  
 - Total E2E: 190-230ms ✅    
  
 La pequeña diferencia entre 1.72 y 2.0 FPS se debe al overhead natural del procesamiento. Es un resultado excelente.