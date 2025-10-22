#!/usr/bin/env python3
"""
Monitor para el Data Plane MQTT
================================

Escucha y muestra las detecciones publicadas por el pipeline.

Uso:
    python mqtt_data_monitor.py
    python mqtt_data_monitor.py --broker 192.168.1.100
    python mqtt_data_monitor.py --topic inference/data/detections --verbose
"""
import json
import argparse
import signal
import sys
from datetime import datetime
from collections import defaultdict
from threading import Lock

import paho.mqtt.client as mqtt


class DataMonitor:
    """Monitor de detecciones del Data Plane"""
    
    def __init__(self, broker: str, port: int, topic: str, verbose: bool = False):
        self.broker = broker
        self.port = port
        self.topic = topic
        self.verbose = verbose
        
        self.message_count = 0
        self.detection_count = 0
        self.class_counts = defaultdict(int)
        self.lock = Lock()
        self.running = True
        
        # Cliente MQTT
        self.client = mqtt.Client(
            client_id="data_monitor",
            protocol=mqtt.MQTTv5
        )
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.client.on_disconnect = self._on_disconnect
    
    def _on_connect(self, client, userdata, flags, rc, properties=None):
        """Callback de conexión"""
        if rc == 0:
            print(f"✅ Conectado a {self.broker}:{self.port}")
            self.client.subscribe(self.topic, qos=0)
            print(f"📡 Escuchando: {self.topic}")
            print("\n" + "="*70)
            print("🎧 Monitor activo - Presiona Ctrl+C para salir")
            print("="*70 + "\n")
        else:
            print(f"❌ Error conectando: {rc}")
    
    def _on_disconnect(self, client, userdata, rc, properties=None):
        """Callback de desconexión"""
        print(f"\n⚠️ Desconectado (rc={rc})")
    
    def _on_message(self, client, userdata, msg):
        """Callback cuando recibe un mensaje"""
        try:
            payload = msg.payload.decode('utf-8')
            data = json.loads(payload)
            
            with self.lock:
                self.message_count += 1
                
                # Extraer información
                timestamp = data.get('timestamp', 'N/A')
                detection_count = data.get('detection_count', 0)
                detections = data.get('detections', [])
                frame_info = data.get('frame', {})
                
                self.detection_count += detection_count
                
                # Contar clases
                for det in detections:
                    class_name = det.get('class', 'unknown')
                    self.class_counts[class_name] += 1
                
                # Mostrar información
                if self.verbose or detection_count > 0:
                    self._print_message(timestamp, detection_count, detections, frame_info)
                
        except json.JSONDecodeError:
            print(f"❌ Error decodificando JSON")
        except Exception as e:
            print(f"❌ Error procesando mensaje: {e}")
    
    def _print_message(self, timestamp, detection_count, detections, frame_info):
        """Imprime información del mensaje"""
        now = datetime.now().strftime("%H:%M:%S")
        
        print(f"[{now}] 📦 Detecciones: {detection_count}")
        
        if frame_info:
            frame_id = frame_info.get('frame_id', 'N/A')
            source_id = frame_info.get('source_id', 'N/A')
            print(f"  📹 Frame: {frame_id} | Source: {source_id}")
        
        if self.verbose and detections:
            for i, det in enumerate(detections, 1):
                class_name = det.get('class', 'unknown')
                confidence = det.get('confidence', 0.0)
                bbox = det.get('bbox', {})
                
                print(f"  {i}. {class_name} ({confidence:.2%})", end="")
                if bbox:
                    x = bbox.get('x', 0)
                    y = bbox.get('y', 0)
                    print(f" @ ({x:.0f}, {y:.0f})")
                else:
                    print()
        
        print()
    
    def run(self):
        """Inicia el monitor"""
        # Signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        # Conectar
        print(f"🔌 Conectando a {self.broker}:{self.port}...")
        try:
            self.client.connect(self.broker, self.port, keepalive=60)
            self.client.loop_start()
        except Exception as e:
            print(f"❌ Error conectando: {e}")
            return
        
        # Esperar
        try:
            while self.running:
                import time
                time.sleep(1)
        except KeyboardInterrupt:
            pass
        
        # Cleanup
        self.stop()
    
    def _signal_handler(self, signum, frame):
        """Handler para señales"""
        print("\n\n⚠️ Deteniendo monitor...")
        self.running = False
    
    def stop(self):
        """Detiene el monitor"""
        self.client.loop_stop()
        self.client.disconnect()
        
        # Mostrar estadísticas
        print("\n" + "="*70)
        print("📊 ESTADÍSTICAS")
        print("="*70)
        print(f"Mensajes recibidos: {self.message_count}")
        print(f"Detecciones totales: {self.detection_count}")
        
        if self.class_counts:
            print("\nDetecciones por clase:")
            for class_name, count in sorted(
                self.class_counts.items(),
                key=lambda x: x[1],
                reverse=True
            ):
                print(f"  {class_name}: {count}")
        
        print("="*70)
        print("👋 Monitor detenido")


def main():
    parser = argparse.ArgumentParser(
        description="Monitor de detecciones del Data Plane MQTT"
    )
    parser.add_argument(
        "--broker",
        default="localhost",
        help="MQTT broker host (default: localhost)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=1883,
        help="MQTT broker port (default: 1883)"
    )
    parser.add_argument(
        "--topic",
        default="inference/data/detections",
        help="MQTT topic (default: inference/data/detections)"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Mostrar información detallada de cada detección"
    )
    
    args = parser.parse_args()
    
    monitor = DataMonitor(
        broker=args.broker,
        port=args.port,
        topic=args.topic,
        verbose=args.verbose
    )
    
    monitor.run()


if __name__ == "__main__":
    main()

