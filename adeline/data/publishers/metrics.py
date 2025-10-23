"""
Metrics Publisher
=================

Publisher especializado en formatear métricas del pipeline.

Responsabilidad:
- Conoce estructura de métricas del watchdog
- Formatea report del watchdog para MQTT
- Extrae throughput, latencias, etc.

Diseño: Complejidad por diseño
- Lógica de negocio separada de infraestructura MQTT
- SRP: solo formateo de métricas
- NO conoce MQTT (eso es del DataPlane)
"""
from datetime import datetime
from typing import Any, Dict, Optional
from inference.core.interfaces.stream.watchdog import BasePipelineWatchDog
import logging

logger = logging.getLogger(__name__)


class MetricsPublisher:
    """
    Publisher de métricas del pipeline.

    Formatea report del watchdog en mensajes MQTT.
    """

    def __init__(self):
        """Inicializa publisher."""
        self._watchdog: Optional[BasePipelineWatchDog] = None

    def set_watchdog(self, watchdog: BasePipelineWatchDog):
        """
        Conecta un watchdog para acceder a sus métricas.

        Args:
            watchdog: Instancia de BasePipelineWatchDog del pipeline
        """
        self._watchdog = watchdog
        logger.info(
            "Watchdog connected to MetricsPublisher",
            extra={
                "component": "metrics_publisher",
                "event": "watchdog_connected"
            }
        )

    def format_message(self) -> Optional[Dict[str, Any]]:
        """
        Formatea métricas del watchdog en mensaje MQTT.

        Returns:
            Diccionario con mensaje formateado, o None si no hay watchdog

        Raises:
            ValueError: Si watchdog no configurado
        """
        if not self._watchdog:
            raise ValueError("Watchdog no configurado. Usa set_watchdog() primero.")

        try:
            report = self._watchdog.get_report()

            # Construir mensaje con métricas
            message = {
                "timestamp": datetime.now().isoformat(),
                "throughput_fps": report.inference_throughput,
                "latency_reports": [
                    {
                        "source_id": getattr(lr, 'source_id', 0),
                        "frame_decoding_latency_ms": getattr(lr, 'frame_decoding_latency', 0),
                        "inference_latency_ms": getattr(lr, 'inference_latency', 0),
                        "e2e_latency_ms": getattr(lr, 'e2e_latency', 0),
                    }
                    for lr in report.latency_reports
                ],
                "sources_count": len(report.sources_metadata),
            }

            return message

        except Exception as e:
            logger.error(
                "Failed to format metrics",
                extra={
                    "component": "metrics_publisher",
                    "event": "format_error",
                    "error": str(e),
                    "error_type": type(e).__name__
                },
                exc_info=True
            )
            return None

    @property
    def has_watchdog(self) -> bool:
        """Retorna True si watchdog está configurado."""
        return self._watchdog is not None
