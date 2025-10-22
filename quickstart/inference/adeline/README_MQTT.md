# InferencePipeline con MQTT Control y Data Plane

Arquitectura de control y data plane separados usando MQTT para el InferencePipeline.

## 🏗️ Arquitectura

```
┌─────────────────────────────────────────────────────────────┐
│                    MQTT Broker (localhost:1883)             │
├──────────────────┬──────────────────────┬──────────────────┤
│  Control Plane   │   Data Plane         │   Status         │
│  (Commands)      │   (Detections)       │   (State)        │
└──────────────────┴──────────────────────┴──────────────────┘
         ▲                    │                    │
         │                    ▼                    ▼
         │            ┌───────────────┐    ┌─────────────┐
         │            │   Consumers   │    │  Monitors   │
         │            │   - Analytics │    │  - Logging  │
         │            │   - Storage   │    │  - Alerts   │
         │            │   - Alerts    │    │             │
         │            └───────────────┘    └─────────────┘
         │
    ┌────┴─────────────────────┐
    │  InferencePipeline       │
    │  ┌──────────────────┐    │
    │  │ Control Handler  │    │
    │  │ - start          │    │
    │  │ - stop           │    │
    │  │ - pause          │    │
    │  │ - resume         │    │
    │  └──────────────────┘    │
    │  ┌──────────────────┐    │
    │  │ Data Emitter     │    │
    │  │ - Detections     │    │
    │  │ - Metadata       │    │
    │  │ - Timestamps     │    │
    │  └──────────────────┘    │
    └──────────────────────────┘
```

## 📦 Componentes

### 1. Control Plane (`MQTTControlPlane`)
- **Propósito**: Recibir comandos para controlar el pipeline
- **Topic**: `inference/control/commands`
- **Status Topic**: `inference/control/status`
- **Comandos**:
  - `start` - Inicia el pipeline
  - `stop` - Detiene el pipeline
  - `pause` - Pausa el procesamiento
  - `resume` - Reanuda el procesamiento
  - `status` - Solicita estado actual

### 2. Data Plane (`MQTTDataPlane`)
- **Propósito**: Publicar resultados de inferencia
- **Topic**: `inference/data/detections`
- **Formato de mensaje**:
```json
{
  "timestamp": "2025-10-21T10:30:45.123456",
  "message_id": 1234,
  "detection_count": 2,
  "detections": [
    {
      "class": "person",
      "confidence": 0.95,
      "bbox": {
        "x": 100,
        "y": 200,
        "width": 50,
        "height": 100
      },
      "class_id": 0
    }
  ],
  "frame": {
    "frame_id": 5678,
    "source_id": 0,
    "timestamp": "2025-10-21T10:30:45.100000"
  }
}
```

## 🚀 Uso

### 1. Requisitos previos

Instalar dependencias:
```bash
uv sync
```

Tener un broker MQTT corriendo (ejemplo con Mosquitto):
```bash
# Opción 1: Docker
docker run -it -p 1883:1883 eclipse-mosquitto

# Opción 2: Instalación local (Ubuntu/Debian)
sudo apt-get install mosquitto mosquitto-clients
sudo systemctl start mosquitto
```

### 2. Ejecutar el pipeline

```bash
cd quickstart/inference
python run_pipeline_mqtt.py
```

Salida esperada:
```
🚀 Inicializando InferencePipeline con MQTT...
📡 Configurando Data Plane...
✅ Data Plane conectado a localhost:1883
🔧 Creando InferencePipeline...
🎮 Configurando Control Plane...
✅ Control Plane conectado a localhost:1883
✅ Setup completado

======================================================================
🎬 InferencePipeline con MQTT activo
======================================================================
📡 Control Topic: inference/control/commands
📊 Data Topic: inference/data/detections

💡 Envía comandos MQTT para controlar el pipeline:
   START:  {"command": "start"}
   STOP:   {"command": "stop"}
   PAUSE:  {"command": "pause"}
   RESUME: {"command": "resume"}
   STATUS: {"command": "status"}

⌨️  Presiona Ctrl+C para salir
======================================================================
```

### 3. Enviar comandos

#### Opción A: Usando el CLI incluido
```bash
# En otra terminal
python mqtt_control_cli.py start
python mqtt_control_cli.py pause
python mqtt_control_cli.py resume
python mqtt_control_cli.py stop
python mqtt_control_cli.py status
```

#### Opción B: Usando mosquitto_pub
```bash
# Start
mosquitto_pub -h localhost -t inference/control/commands \
  -m '{"command": "start"}'

# Stop
mosquitto_pub -h localhost -t inference/control/commands \
  -m '{"command": "stop"}'

# Pause
mosquitto_pub -h localhost -t inference/control/commands \
  -m '{"command": "pause"}'

# Resume
mosquitto_pub -h localhost -t inference/control/commands \
  -m '{"command": "resume"}'

# Status
mosquitto_pub -h localhost -t inference/control/commands \
  -m '{"command": "status"}'
```

#### Opción C: Usando Python
```python
import json
import paho.mqtt.client as mqtt

client = mqtt.Client(protocol=mqtt.MQTTv5)
client.connect("localhost", 1883)

# Enviar comando start
message = {"command": "start"}
client.publish("inference/control/commands", json.dumps(message), qos=1)

client.disconnect()
```

### 4. Monitorear detecciones

#### Opción A: Usando el monitor incluido
```bash
# En otra terminal
python mqtt_data_monitor.py

# Con más detalles
python mqtt_data_monitor.py --verbose
```

#### Opción B: Usando mosquitto_sub
```bash
mosquitto_sub -h localhost -t inference/data/detections -v
```

#### Opción C: Usando Python
```python
import paho.mqtt.client as mqtt

def on_message(client, userdata, msg):
    print(f"Recibido: {msg.payload.decode()}")

client = mqtt.Client(protocol=mqtt.MQTTv5)
client.on_message = on_message
client.connect("localhost", 1883)
client.subscribe("inference/data/detections")
client.loop_forever()
```

## 🔧 Configuración

Edita `run_pipeline_mqtt.py` para personalizar:

```python
class PipelineConfig:
    # Inference Pipeline
    API_KEY = "tu_api_key"
    RTSP_URL = "rtsp://tu_camara"
    MODEL_ID = "yolov11n-640"
    MAX_FPS = 2
    
    # MQTT Broker
    MQTT_BROKER = "localhost"  # o IP del broker
    MQTT_PORT = 1883
    MQTT_USERNAME = None  # si requiere auth
    MQTT_PASSWORD = None
    
    # MQTT Topics
    CONTROL_COMMAND_TOPIC = "inference/control/commands"
    CONTROL_STATUS_TOPIC = "inference/control/status"
    DATA_TOPIC = "inference/data/detections"
    
    # Visualización
    ENABLE_VISUALIZATION = True
```

## 📊 Topics MQTT

| Topic | Tipo | QoS | Descripción |
|-------|------|-----|-------------|
| `inference/control/commands` | Subscribe | 1 | Comandos de control |
| `inference/control/status` | Publish | 1 | Estado del pipeline (retain) |
| `inference/data/detections` | Publish | 0 | Detecciones en tiempo real |

## 🔍 Casos de uso

### 1. Control remoto del pipeline
```bash
# Desde cualquier cliente MQTT
mosquitto_pub -h pipeline.example.com -t inference/control/commands \
  -m '{"command": "start"}'
```

### 2. Integración con Node-RED
Conectar nodos MQTT para:
- Controlar pipeline desde dashboards
- Procesar detecciones
- Enviar alertas

### 3. Integración con Home Assistant
```yaml
# configuration.yaml
mqtt:
  sensor:
    - name: "Detections Count"
      state_topic: "inference/data/detections"
      value_template: "{{ value_json.detection_count }}"
  
  button:
    - name: "Start Pipeline"
      command_topic: "inference/control/commands"
      payload_press: '{"command": "start"}'
```

### 4. Analytics en tiempo real
```python
# Consumidor que cuenta detecciones
from mqtt_bridge import MQTTDataPlane

class AnalyticsConsumer:
    def __init__(self):
        self.client = mqtt.Client()
        self.client.on_message = self.on_detection
        self.client.connect("localhost", 1883)
        self.client.subscribe("inference/data/detections")
    
    def on_detection(self, client, userdata, msg):
        data = json.loads(msg.payload)
        # Guardar en DB, procesar, etc.
        self.process_detections(data)
```

## 🛠️ Troubleshooting

### Pipeline no se inicia
```bash
# Verificar que MQTT está corriendo
mosquitto -v

# Verificar conectividad
mosquitto_pub -h localhost -t test -m "hello"
mosquitto_sub -h localhost -t test
```

### No se reciben detecciones
```bash
# Verificar que el pipeline está corriendo
mosquitto_sub -h localhost -t inference/control/status

# Verificar que hay video
# Revisar logs del pipeline
```

### Latencia alta
- Usar QoS 0 en data plane (ya configurado)
- Reducir `MAX_FPS`
- Considerar filtrar detecciones (ej: solo con confidence > 0.8)

## 📚 Referencias

- `mqtt_bridge.py` - Implementación de control y data plane
- `run_pipeline_mqtt.py` - Ejemplo completo integrado
- `mqtt_control_cli.py` - CLI para enviar comandos
- `mqtt_data_monitor.py` - Monitor de detecciones
- [Paho MQTT](https://pypi.org/project/paho-mqtt/) - Cliente MQTT Python
- [Mosquitto](https://mosquitto.org/) - Broker MQTT

## 💡 Tips

1. **Producción**: Usar broker MQTT dedicado (no en la misma máquina)
2. **Seguridad**: Configurar autenticación (username/password) o TLS
3. **Persistencia**: Guardar detecciones en DB desde un consumidor separado
4. **Escalabilidad**: Múltiples pipelines publicando al mismo broker
5. **Monitoreo**: Usar retained messages en status topic para ver estado actual

