#!/usr/bin/env python3
"""
Monitor de Status del Control Plane
====================================

Escucha el topic de status para ver el estado del pipeline.

Uso:
    python mqtt_status_monitor.py
"""
import json
import argparse
import signal
import sys
from datetime import datetime

import paho.mqtt.client as mqtt


class StatusMonitor:
    """Monitor de status del Control Plane"""

    def __init__(self, broker: str, port: int, topic: str):
        self.broker = broker
        self.port = port
        self.topic = topic
        self.running = True

        # Cliente MQTT
        self.client = mqtt.Client(
            client_id="status_monitor",
            protocol=mqtt.MQTTv5
        )
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.client.on_disconnect = self._on_disconnect

    def _on_connect(self, client, userdata, flags, rc, properties=None):
        """Callback de conexión"""
        if rc == 0:
            print(f"✅ Conectado a {self.broker}:{self.port}")
            self.client.subscribe(self.topic, qos=1)
            print(f"📡 Escuchando status en: {self.topic}")
            print("\n" + "="*70)
            print("👀 Monitor de Status activo - Presiona Ctrl+C para salir")
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

            timestamp = data.get('timestamp', 'N/A')
            status = data.get('status', 'unknown')
            client_id = data.get('client_id', 'unknown')

            now = datetime.now().strftime("%H:%M:%S")

            # Emoji según el estado
            emoji = {
                'connected': '🔗',
                'started': '▶️',
                'stopped': '⏹️',
                'paused': '⏸️',
                'running': '▶️',
                'disconnected': '🔌'
            }.get(status, '❓')

            print(f"[{now}] {emoji} Status: {status.upper()} | Client: {client_id}")
            print(f"         Timestamp: {timestamp}\n")

        except json.JSONDecodeError:
            print(f"❌ Error decodificando JSON")
        except Exception as e:
            print(f"❌ Error procesando mensaje: {e}")

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
        print("👋 Monitor detenido")


def main():
    parser = argparse.ArgumentParser(
        description="Monitor de status del Control Plane"
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
        default="inference/control/status",
        help="MQTT status topic (default: inference/control/status)"
    )

    args = parser.parse_args()

    monitor = StatusMonitor(
        broker=args.broker,
        port=args.port,
        topic=args.topic
    )

    monitor.run()


if __name__ == "__main__":
    main()
