# Ejemplos de Integración MQTT

Casos de uso y ejemplos de integración del InferencePipeline con MQTT.

## 📱 Ejemplo 1: Node-RED Dashboard

```json
[
  {
    "id": "mqtt_in",
    "type": "mqtt in",
    "topic": "inference/data/detections",
    "broker": "localhost:1883",
    "qos": "0"
  },
  {
    "id": "process",
    "type": "function",
    "func": "msg.payload = JSON.parse(msg.payload);\nreturn msg;"
  },
  {
    "id": "dashboard",
    "type": "ui_chart",
    "label": "Detections Over Time"
  }
]
```

## 🏠 Ejemplo 2: Home Assistant

```yaml
# configuration.yaml
mqtt:
  sensor:
    - name: "Pipeline Status"
      state_topic: "inference/control/status"
      value_template: "{{ value_json.status }}"
      icon: mdi:cctv
    
    - name: "Detection Count"
      state_topic: "inference/data/detections"
      value_template: "{{ value_json.detection_count }}"
      unit_of_measurement: "detections"
      icon: mdi:target
    
    - name: "Person Detected"
      state_topic: "inference/data/detections"
      value_template: >
        {% set persons = value_json.detections | selectattr('class', 'equalto', 'person') | list %}
        {{ persons | length > 0 }}
      icon: mdi:human
  
  button:
    - name: "Start Pipeline"
      command_topic: "inference/control/commands"
      payload_press: '{"command": "start"}'
      icon: mdi:play
    
    - name: "Stop Pipeline"
      command_topic: "inference/control/commands"
      payload_press: '{"command": "stop"}'
      icon: mdi:stop
    
    - name: "Pause Pipeline"
      command_topic: "inference/control/commands"
      payload_press: '{"command": "pause"}'
      icon: mdi:pause

automation:
  - alias: "Alert on Person Detection"
    trigger:
      - platform: mqtt
        topic: "inference/data/detections"
    condition:
      - condition: template
        value_template: >
          {% set persons = trigger.payload_json.detections | selectattr('class', 'equalto', 'person') | list %}
          {{ persons | length > 0 }}
    action:
      - service: notify.mobile_app
        data:
          title: "Person Detected"
          message: "{{ trigger.payload_json.detection_count }} detections"
```

## 🐍 Ejemplo 3: Consumer Python con Analytics

```python
#!/usr/bin/env python3
"""
Consumer de detecciones con analytics en tiempo real
"""
import json
from collections import defaultdict
from datetime import datetime
import paho.mqtt.client as mqtt
from influxdb_client import InfluxDBClient, Point

class DetectionAnalytics:
    def __init__(self, mqtt_broker, influx_url, influx_token, influx_org, influx_bucket):
        self.stats = defaultdict(int)
        
        # MQTT Setup
        self.mqtt_client = mqtt.Client(protocol=mqtt.MQTTv5)
        self.mqtt_client.on_connect = self.on_connect
        self.mqtt_client.on_message = self.on_message
        self.mqtt_client.connect(mqtt_broker, 1883)
        
        # InfluxDB Setup
        self.influx_client = InfluxDBClient(
            url=influx_url,
            token=influx_token,
            org=influx_org
        )
        self.write_api = self.influx_client.write_api()
        self.bucket = influx_bucket
    
    def on_connect(self, client, userdata, flags, rc, properties=None):
        print(f"✅ Connected to MQTT")
        client.subscribe("inference/data/detections")
    
    def on_message(self, client, userdata, msg):
        try:
            data = json.loads(msg.payload.decode())
            self.process_detections(data)
        except Exception as e:
            print(f"Error: {e}")
    
    def process_detections(self, data):
        timestamp = datetime.fromisoformat(data['timestamp'])
        detections = data['detections']
        
        # Analytics
        for det in detections:
            class_name = det['class']
            confidence = det['confidence']
            
            # Update stats
            self.stats[class_name] += 1
            
            # Write to InfluxDB
            point = Point("detection") \
                .tag("class", class_name) \
                .field("confidence", confidence) \
                .field("count", 1) \
                .time(timestamp)
            
            self.write_api.write(bucket=self.bucket, record=point)
        
        # Log stats
        if len(detections) > 0:
            print(f"[{timestamp}] Detections: {self.stats}")
    
    def run(self):
        print("🚀 Starting analytics consumer...")
        self.mqtt_client.loop_forever()

if __name__ == "__main__":
    analytics = DetectionAnalytics(
        mqtt_broker="localhost",
        influx_url="http://localhost:8086",
        influx_token="your-token",
        influx_org="your-org",
        influx_bucket="detections"
    )
    analytics.run()
```

## 🔔 Ejemplo 4: Alertas con Telegram

```python
#!/usr/bin/env python3
"""
Bot de Telegram que envía alertas basadas en detecciones
"""
import json
import paho.mqtt.client as mqtt
from telegram import Bot
from telegram.ext import Updater
from datetime import datetime, timedelta

class TelegramAlerter:
    def __init__(self, telegram_token, chat_id, mqtt_broker):
        self.bot = Bot(token=telegram_token)
        self.chat_id = chat_id
        self.last_alert = {}
        self.cooldown = timedelta(seconds=30)  # No spam
        
        # MQTT
        self.client = mqtt.Client(protocol=mqtt.MQTTv5)
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.connect(mqtt_broker, 1883)
    
    def on_connect(self, client, userdata, flags, rc, properties=None):
        print(f"✅ Connected")
        client.subscribe("inference/data/detections")
    
    def on_message(self, client, userdata, msg):
        data = json.loads(msg.payload.decode())
        self.check_alerts(data)
    
    def check_alerts(self, data):
        detections = data['detections']
        
        # Buscar personas con alta confianza
        persons = [d for d in detections 
                   if d['class'] == 'person' and d['confidence'] > 0.8]
        
        if persons:
            now = datetime.now()
            last = self.last_alert.get('person')
            
            # Respetar cooldown
            if last is None or (now - last) > self.cooldown:
                count = len(persons)
                message = f"🚨 Alerta: {count} persona(s) detectada(s)"
                
                self.bot.send_message(
                    chat_id=self.chat_id,
                    text=message
                )
                
                self.last_alert['person'] = now
                print(f"📤 Alert sent: {message}")
    
    def run(self):
        print("🤖 Telegram alerter running...")
        self.client.loop_forever()

if __name__ == "__main__":
    alerter = TelegramAlerter(
        telegram_token="YOUR_TELEGRAM_TOKEN",
        chat_id="YOUR_CHAT_ID",
        mqtt_broker="localhost"
    )
    alerter.run()
```

## 📊 Ejemplo 5: Grafana Dashboard

Configurar datasource de MQTT en Grafana usando plugin MQTT Datasource:

```json
{
  "datasources": [{
    "name": "MQTT",
    "type": "mqtt-datasource",
    "url": "mqtt://localhost:1883",
    "jsonData": {
      "topic": "inference/data/detections"
    }
  }]
}
```

Luego crear panel con query:
```sql
SELECT 
  COUNT(*) as detections,
  class
FROM mqtt_data
WHERE $__timeFilter(timestamp)
GROUP BY class, time(1m)
```

## 🌐 Ejemplo 6: Web Dashboard con WebSocket

```html
<!DOCTYPE html>
<html>
<head>
    <title>Detection Dashboard</title>
    <script src="https://cdn.jsdelivr.net/npm/paho-mqtt@1.1.0/paho-mqtt.min.js"></script>
</head>
<body>
    <h1>Live Detections</h1>
    <div id="status">Connecting...</div>
    <div id="detections"></div>
    
    <script>
        const client = new Paho.MQTT.Client(
            "localhost", 9001, "web_dashboard"
        );
        
        client.onConnectionLost = (response) => {
            document.getElementById('status').textContent = 
                'Connection lost: ' + response.errorMessage;
        };
        
        client.onMessageArrived = (message) => {
            const data = JSON.parse(message.payloadString);
            displayDetections(data);
        };
        
        client.connect({
            onSuccess: () => {
                document.getElementById('status').textContent = 'Connected';
                client.subscribe("inference/data/detections");
            }
        });
        
        function displayDetections(data) {
            const div = document.getElementById('detections');
            const html = `
                <div class="detection">
                    <strong>${data.detection_count} detections</strong>
                    <ul>
                        ${data.detections.map(d => 
                            `<li>${d.class} (${(d.confidence*100).toFixed(1)}%)</li>`
                        ).join('')}
                    </ul>
                    <small>${data.timestamp}</small>
                </div>
            `;
            div.innerHTML = html + div.innerHTML;
        }
    </script>
</body>
</html>
```

## 🐳 Ejemplo 7: Docker Compose Stack Completo

```yaml
version: '3.8'

services:
  mosquitto:
    image: eclipse-mosquitto:2.0
    ports:
      - "1883:1883"
      - "9001:9001"
    volumes:
      - ./mosquitto.conf:/mosquitto/config/mosquitto.conf
    networks:
      - inference_net
  
  influxdb:
    image: influxdb:2.7
    ports:
      - "8086:8086"
    environment:
      - DOCKER_INFLUXDB_INIT_MODE=setup
      - DOCKER_INFLUXDB_INIT_USERNAME=admin
      - DOCKER_INFLUXDB_INIT_PASSWORD=adminpass
      - DOCKER_INFLUXDB_INIT_ORG=inference
      - DOCKER_INFLUXDB_INIT_BUCKET=detections
    volumes:
      - influxdb_data:/var/lib/influxdb2
    networks:
      - inference_net
  
  grafana:
    image: grafana/grafana:latest
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
    volumes:
      - grafana_data:/var/lib/grafana
    depends_on:
      - influxdb
    networks:
      - inference_net
  
  node-red:
    image: nodered/node-red:latest
    ports:
      - "1880:1880"
    volumes:
      - node_red_data:/data
    networks:
      - inference_net

volumes:
  influxdb_data:
  grafana_data:
  node_red_data:

networks:
  inference_net:
    driver: bridge
```

## 🔐 Ejemplo 8: MQTT con Autenticación

```python
# run_pipeline_mqtt.py con auth
class PipelineConfig:
    MQTT_BROKER = "mqtt.example.com"
    MQTT_PORT = 1883
    MQTT_USERNAME = "inference_pipeline"
    MQTT_PASSWORD = "secure_password"
    # ... resto de config
```

```conf
# mosquitto.conf con auth
allow_anonymous false
password_file /mosquitto/config/passwd

# Crear password file:
# mosquitto_passwd -c /path/to/passwd inference_pipeline
```

## 📱 Ejemplo 9: Múltiples Pipelines

```python
# Coordinar múltiples pipelines
import paho.mqtt.client as mqtt
import json

class PipelineOrchestrator:
    def __init__(self):
        self.pipelines = {
            "camera1": "inference/camera1/control/commands",
            "camera2": "inference/camera2/control/commands",
            "camera3": "inference/camera3/control/commands",
        }
        
        self.client = mqtt.Client(protocol=mqtt.MQTTv5)
        self.client.connect("localhost", 1883)
    
    def start_all(self):
        for name, topic in self.pipelines.items():
            self.client.publish(topic, '{"command": "start"}', qos=1)
            print(f"✅ Started {name}")
    
    def stop_all(self):
        for name, topic in self.pipelines.items():
            self.client.publish(topic, '{"command": "stop"}', qos=1)
            print(f"⏹️  Stopped {name}")

orchestrator = PipelineOrchestrator()
orchestrator.start_all()
```

## 💾 Ejemplo 10: Persistencia en SQLite

```python
import sqlite3
import json
from datetime import datetime
import paho.mqtt.client as mqtt

class DetectionPersistence:
    def __init__(self, db_path="detections.db"):
        self.conn = sqlite3.connect(db_path)
        self.setup_db()
        
        self.client = mqtt.Client(protocol=mqtt.MQTTv5)
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.connect("localhost", 1883)
    
    def setup_db(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS detections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                class TEXT,
                confidence REAL,
                bbox_x REAL,
                bbox_y REAL,
                bbox_width REAL,
                bbox_height REAL,
                frame_id INTEGER,
                source_id INTEGER
            )
        """)
        self.conn.commit()
    
    def on_connect(self, client, userdata, flags, rc, properties=None):
        client.subscribe("inference/data/detections")
    
    def on_message(self, client, userdata, msg):
        data = json.loads(msg.payload.decode())
        self.save_detections(data)
    
    def save_detections(self, data):
        timestamp = data['timestamp']
        frame_info = data.get('frame', {})
        
        for det in data['detections']:
            bbox = det.get('bbox', {})
            
            self.conn.execute("""
                INSERT INTO detections 
                (timestamp, class, confidence, bbox_x, bbox_y, 
                 bbox_width, bbox_height, frame_id, source_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                timestamp,
                det.get('class'),
                det.get('confidence'),
                bbox.get('x'),
                bbox.get('y'),
                bbox.get('width'),
                bbox.get('height'),
                frame_info.get('frame_id'),
                frame_info.get('source_id')
            ))
        
        self.conn.commit()
    
    def run(self):
        print("💾 Persistence service running...")
        self.client.loop_forever()

if __name__ == "__main__":
    persistence = DetectionPersistence()
    persistence.run()
```

## 🎯 Más Ideas

- **Video Recording Trigger**: Grabar video cuando se detecta algo específico
- **Email Alerts**: Enviar emails con screenshots
- **Webhook Integration**: Enviar detecciones a webhooks externos
- **Time Series Analysis**: Análisis de patrones temporales
- **Multi-Camera Tracking**: Tracking de objetos entre múltiples cámaras
- **Ocupancy Heatmaps**: Mapas de calor de zonas más frecuentadas
- **Rule Engine**: Motor de reglas para alertas complejas

Para más información, ver `README_MQTT.md`.

