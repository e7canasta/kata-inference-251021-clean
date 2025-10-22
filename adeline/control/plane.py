"""
MQTT Control Plane
==================

Control Plane para InferencePipeline vía MQTT (QoS 1).
Recibe comandos para controlar el pipeline (pause/resume/stop).
"""
import json
import logging
from datetime import datetime
from threading import Event
from typing import Callable, Optional

import paho.mqtt.client as mqtt

logger = logging.getLogger(__name__)


class MQTTControlPlane:
    """
    Control Plane para InferencePipeline vía MQTT.

    Recibe comandos:
    - pause: Pausa el pipeline
    - resume: Reanuda el pipeline
    - stop: Detiene el pipeline completamente
    - status: Solicita estado actual
    - metrics: Publica métricas del watchdog vía MQTT
    - toggle_crop: Activa/desactiva adaptive ROI (solo si está habilitado)
    - stabilization_stats: Publica estadísticas de detection stabilization

    Nota: El pipeline se inicia automáticamente, no hay comando START.
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

        # Callbacks para acciones (sin on_start, pipeline auto-inicia)
        self.on_stop: Optional[Callable[[], None]] = None
        self.on_pause: Optional[Callable[[], None]] = None
        self.on_resume: Optional[Callable[[], None]] = None
        self.on_metrics: Optional[Callable[[], None]] = None
        self.on_toggle_crop: Optional[Callable[[], None]] = None  # Para adaptive ROI
        self.on_stabilization_stats: Optional[Callable[[], None]] = None  # Para detection stabilization

        # MQTT Client
        self.client = mqtt.Client(client_id=client_id, protocol=mqtt.MQTTv5)
        if username and password:
            self.client.username_pw_set(username, password)

        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.client.on_disconnect = self._on_disconnect

        self._connected = Event()
        self._running = False

    def _on_connect(self, client, userdata, flags, rc, properties=None):
        """Callback cuando se conecta al broker"""
        if rc == 0:
            logger.info(f"✅ Control Plane conectado a {self.broker_host}:{self.broker_port}")
            self.client.subscribe(self.command_topic, qos=1)
            logger.info(f"📡 Suscrito a: {self.command_topic}")
            self._connected.set()
            self._publish_status("connected")
        else:
            logger.error(f"❌ Error conectando al broker MQTT: {rc}")

    def _on_disconnect(self, client, userdata, rc, properties=None):
        """Callback cuando se desconecta del broker"""
        logger.warning(f"⚠️ Control Plane desconectado (rc={rc})")
        self._connected.clear()

    def _on_message(self, client, userdata, msg):
        """Callback cuando recibe un mensaje"""
        logger.debug(f"🔔 Mensaje MQTT recibido en topic: {msg.topic}")
        try:
            payload = msg.payload.decode('utf-8')
            logger.debug(f"📦 Payload: {payload}")
            command_data = json.loads(payload)
            command = command_data.get('command', '').lower()

            logger.info(f"📥 Comando recibido: {command}")

            if command == 'pause':
                logger.debug("📝 Procesando comando PAUSE")
                if self.on_pause:
                    try:
                        self.on_pause()
                        self._publish_status("paused")
                        logger.debug("✅ Comando PAUSE procesado")
                    except Exception as e:
                        logger.error(f"❌ Error en callback on_pause: {e}", exc_info=True)
                else:
                    logger.warning("⚠️ on_pause callback no configurado")

            elif command == 'resume':
                logger.debug("📝 Procesando comando RESUME")
                if self.on_resume:
                    try:
                        self.on_resume()
                        self._publish_status("running")
                        logger.debug("✅ Comando RESUME procesado")
                    except Exception as e:
                        logger.error(f"❌ Error en callback on_resume: {e}", exc_info=True)
                else:
                    logger.warning("⚠️ on_resume callback no configurado")

            elif command == 'stop':
                logger.debug("📝 Procesando comando STOP")
                if self.on_stop:
                    try:
                        self.on_stop()
                        self._publish_status("stopped")
                        logger.debug("✅ Comando STOP procesado")
                    except Exception as e:
                        logger.error(f"❌ Error en callback on_stop: {e}", exc_info=True)
                else:
                    logger.warning("⚠️ on_stop callback no configurado")

            elif command == 'status':
                logger.debug("📝 Procesando comando STATUS")
                self._publish_status("running" if self._running else "stopped")

            elif command == 'metrics':
                logger.debug("📝 Procesando comando METRICS")
                if self.on_metrics:
                    try:
                        self.on_metrics()
                        logger.debug("✅ Comando METRICS procesado")
                    except Exception as e:
                        logger.error(f"❌ Error en callback on_metrics: {e}", exc_info=True)
                else:
                    logger.warning("⚠️ on_metrics callback no configurado")

            elif command == 'toggle_crop':
                logger.debug("📝 Procesando comando TOGGLE_CROP")
                if self.on_toggle_crop:
                    try:
                        self.on_toggle_crop()
                        logger.debug("✅ Comando TOGGLE_CROP procesado")
                    except Exception as e:
                        logger.error(f"❌ Error en callback on_toggle_crop: {e}", exc_info=True)
                else:
                    logger.warning("⚠️ on_toggle_crop callback no configurado (requiere adaptive_crop.enabled: true)")

            elif command == 'stabilization_stats':
                logger.debug("📝 Procesando comando STABILIZATION_STATS")
                if self.on_stabilization_stats:
                    try:
                        self.on_stabilization_stats()
                        logger.debug("✅ Comando STABILIZATION_STATS procesado")
                    except Exception as e:
                        logger.error(f"❌ Error en callback on_stabilization_stats: {e}", exc_info=True)
                else:
                    logger.warning("⚠️ on_stabilization_stats callback no configurado (requiere detection_stabilization.mode != 'none')")

            else:
                logger.warning(f"⚠️ Comando desconocido: {command}")

            logger.debug(f"✅ Callback _on_message completado para comando: {command}")

        except json.JSONDecodeError:
            logger.error(f"❌ Error decodificando JSON: {msg.payload}")
        except Exception as e:
            logger.error(f"❌ Error procesando mensaje: {e}")

    def _publish_status(self, status: str):
        """Publica el estado actual"""
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
        logger.info(f"📤 Status publicado: {status}")

    def connect(self, timeout: float = 5.0) -> bool:
        """Conecta al broker MQTT"""
        try:
            logger.info(f"🔌 Conectando a MQTT broker: {self.broker_host}:{self.broker_port}")
            self.client.connect(self.broker_host, self.broker_port, keepalive=60)
            self.client.loop_start()
            return self._connected.wait(timeout=timeout)
        except Exception as e:
            logger.error(f"❌ Error conectando a MQTT: {e}")
            return False

    def disconnect(self):
        """Desconecta del broker MQTT"""
        logger.info("🔌 Desconectando Control Plane...")
        self._publish_status("disconnected")
        self.client.loop_stop()
        self.client.disconnect()
