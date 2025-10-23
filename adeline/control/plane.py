"""
MQTT Control Plane
==================

Control Plane para InferencePipeline vía MQTT (QoS 1).
Recibe comandos para controlar el pipeline (pause/resume/stop).

Diseño: Complejidad por diseño
- Usa CommandRegistry para comandos explícitos
- No más callbacks opcionales (on_pause, on_stop, etc.)
- Validación de comandos centralizada en registry
- Structured logging con trace correlation
"""
import json
import logging
from datetime import datetime
from threading import Event
from typing import Optional

import paho.mqtt.client as mqtt

from .registry import CommandRegistry, CommandNotAvailableError
from ..logging import (
    trace_context,
    generate_trace_id,
    log_mqtt_command,
    log_error_with_context
)

logger = logging.getLogger(__name__)


class MQTTControlPlane:
    """
    Control Plane para InferencePipeline vía MQTT.

    Usa CommandRegistry para comandos explícitos:
    - Comandos disponibles están registrados en registry
    - Validación automática de comandos
    - Mejor UX: error claro si comando no existe

    Comandos típicos:
    - pause: Pausa el pipeline
    - resume: Reanuda el pipeline
    - stop: Detiene el pipeline completamente
    - status: Solicita estado actual
    - metrics: Publica métricas del watchdog vía MQTT
    - toggle_crop: Activa/desactiva adaptive ROI (solo si handler lo soporta)
    - stabilization_stats: Estadísticas de detection stabilization (solo si habilitado)

    Nota: El pipeline se inicia automáticamente, no hay comando START.

    Usage:
        control_plane = MQTTControlPlane(...)

        # Registrar comandos disponibles
        control_plane.command_registry.register('pause', handler.pause, "Pausa el procesamiento")
        control_plane.command_registry.register('stop', handler.stop, "Detiene el pipeline")

        control_plane.connect()
    """

    def __init__(
        self,
        broker_host: str,
        broker_port: int = 1883,
        command_topic: str = "inference/control/commands",
        status_topic: str = "inference/control/status",
        client_id: str = "inference_control",
        username: Optional[str] = None,
        password: Optional[str] = None,
    ):
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.command_topic = command_topic
        self.status_topic = status_topic
        self.client_id = client_id

        # CommandRegistry (nuevo - reemplaza callbacks opcionales)
        self.command_registry = CommandRegistry()

        # MQTT Client
        self.client = mqtt.Client(client_id=client_id, protocol=mqtt.MQTTv5)
        if username and password:
            self.client.username_pw_set(username, password)

        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.client.on_disconnect = self._on_disconnect

        self._connected = Event()
        self._running = False  # Tracked for status updates

    def _on_connect(self, client, userdata, flags, rc, properties=None):
        """Callback cuando se conecta al broker"""
        if rc == 0:
            logger.info(
                "Control Plane connected to broker",
                extra={
                    "component": "control_plane",
                    "event": "broker_connected",
                    "broker_host": self.broker_host,
                    "broker_port": self.broker_port
                }
            )
            self.client.subscribe(self.command_topic, qos=1)
            logger.info(
                "Subscribed to command topic",
                extra={
                    "component": "control_plane",
                    "event": "topic_subscribed",
                    "topic": self.command_topic,
                    "qos": 1
                }
            )
            self._connected.set()
            self.publish_status("connected")
        else:
            logger.error(
                "Failed to connect to MQTT broker",
                extra={
                    "component": "control_plane",
                    "event": "connection_error",
                    "broker_host": self.broker_host,
                    "broker_port": self.broker_port,
                    "return_code": rc
                }
            )

    def _on_disconnect(self, client, userdata, rc, properties=None):
        """Callback cuando se desconecta del broker"""
        logger.warning(
            "Control Plane disconnected from broker",
            extra={
                "component": "control_plane",
                "event": "broker_disconnected",
                "return_code": rc
            }
        )
        self._connected.clear()

    def _on_message(self, client, userdata, msg):
        """
        Callback cuando recibe un mensaje MQTT.

        Usa CommandRegistry para ejecutar comandos.
        Propaga trace_id para correlation en toda la call stack.
        """
        try:
            payload = msg.payload.decode('utf-8')
            command_data = json.loads(payload)
            command = command_data.get('command', '').lower()

            # Generar trace_id para este comando (permite seguir todo el flujo)
            trace_id = generate_trace_id(prefix=f"cmd-{command}")

            # Trace context propaga el ID en toda la ejecución
            with trace_context(trace_id):
                # Log comando con contexto estructurado
                log_mqtt_command(
                    logger,
                    command=command,
                    topic=msg.topic,
                    payload=command_data,
                    trace_id=trace_id
                )

                # Ejecutar comando vía registry
                try:
                    self.command_registry.execute(command)
                    logger.debug(
                        f"✅ Comando '{command}' ejecutado correctamente",
                        extra={"command": command, "trace_id": trace_id}
                    )

                except CommandNotAvailableError as e:
                    logger.warning(
                        f"⚠️ {e}",
                        extra={
                            "command": command,
                            "trace_id": trace_id,
                            "available_commands": sorted(self.command_registry.available_commands)
                        }
                    )

        except json.JSONDecodeError as e:
            logger.error(
                f"❌ Error decodificando JSON: {msg.payload}",
                extra={
                    "component": "control_plane",
                    "mqtt_topic": msg.topic,
                    "raw_payload": str(msg.payload)
                }
            )
        except Exception as e:
            log_error_with_context(
                logger,
                message="Error procesando mensaje MQTT",
                exception=e,
                component="control_plane",
                event="message_processing_error",
                mqtt_topic=msg.topic
            )

    def publish_status(self, status: str):
        """
        Publica el estado actual (público para uso desde handlers).

        Args:
            status: Estado a publicar (ej: "paused", "running", "stopped")
        """
        message = {
            "status": status,
            "timestamp": datetime.now().isoformat(),
            "client_id": self.client_id
        }
        self.client.publish(
            self.status_topic,
            json.dumps(message),
            qos=1,
            retain=True
        )
        logger.info(
            "Status published",
            extra={
                "component": "control_plane",
                "event": "status_published",
                "status": status,
                "topic": self.status_topic
            }
        )

    def connect(self, timeout: float = 5.0) -> bool:
        """Conecta al broker MQTT"""
        try:
            logger.info(
                "Connecting to MQTT broker",
                extra={
                    "component": "control_plane",
                    "event": "connection_attempt",
                    "broker_host": self.broker_host,
                    "broker_port": self.broker_port
                }
            )
            self.client.connect(self.broker_host, self.broker_port, keepalive=60)
            self.client.loop_start()
            return self._connected.wait(timeout=timeout)
        except Exception as e:
            logger.error(
                "Failed to connect to MQTT",
                extra={
                    "component": "control_plane",
                    "event": "connection_exception",
                    "broker_host": self.broker_host,
                    "broker_port": self.broker_port,
                    "error": str(e),
                    "error_type": type(e).__name__
                }
            )
            return False

    def disconnect(self):
        """Desconecta del broker MQTT"""
        logger.info("🔌 Desconectando Control Plane...")
        self.publish_status("disconnected")
        self.client.loop_stop()
        self.client.disconnect()
