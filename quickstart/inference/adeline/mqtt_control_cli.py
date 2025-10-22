#!/usr/bin/env python3
"""
CLI para enviar comandos MQTT al pipeline
==========================================

Uso:
    python mqtt_control_cli.py pause
    python mqtt_control_cli.py resume
    python mqtt_control_cli.py stop
    python mqtt_control_cli.py status
    python mqtt_control_cli.py toggle_crop

Nota: El pipeline se inicia automáticamente al ejecutar run_pipeline_mqtt.py
"""
import sys
import json
import argparse
import paho.mqtt.client as mqtt


def send_command(broker: str, port: int, topic: str, command: str):
    """Envía un comando MQTT al pipeline"""
    
    # Crear cliente
    client = mqtt.Client(client_id="mqtt_control_cli", protocol=mqtt.MQTTv5)
    
    # Conectar
    print(f"🔌 Conectando a {broker}:{port}...")
    try:
        client.connect(broker, port, keepalive=60)
    except Exception as e:
        print(f"❌ Error conectando: {e}")
        return False
    
    # Enviar comando
    message = {"command": command}
    payload = json.dumps(message)
    
    print(f"📤 Enviando comando: {command}")
    result = client.publish(topic, payload, qos=1)
    
    if result.rc == mqtt.MQTT_ERR_SUCCESS:
        print(f"✅ Comando enviado exitosamente")
    else:
        print(f"❌ Error enviando comando: {result.rc}")
        return False
    
    # Desconectar
    client.disconnect()
    return True


def main():
    parser = argparse.ArgumentParser(
        description="CLI para controlar InferencePipeline vía MQTT"
    )
    parser.add_argument(
        "command",
        choices=["pause", "resume", "stop", "status", "toggle_crop"],
        help="Comando a enviar (el pipeline auto-inicia, no hay comando 'start')"
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
        default="inference/control/commands",
        help="MQTT topic (default: inference/control/commands)"
    )
    
    args = parser.parse_args()
    
    success = send_command(args.broker, args.port, args.topic, args.command)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

