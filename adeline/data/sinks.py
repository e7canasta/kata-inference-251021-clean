"""
MQTT Sink Factory
=================

Factory function para crear sinks compatibles con InferencePipeline.
"""
from typing import Any, Callable, Dict, List, Optional, Union

from inference.core.interfaces.camera.entities import VideoFrame

from .plane import MQTTDataPlane


def create_mqtt_sink(data_plane: MQTTDataPlane) -> Callable:
    """
    Crea un sink function para InferencePipeline que publica vía MQTT.

    Args:
        data_plane: Instancia de MQTTDataPlane

    Returns:
        Función sink compatible con InferencePipeline

    Note:
        La función retornada tiene __name__ = 'mqtt_sink' para identificación
        explícita en el pipeline builder (usado por stabilization wrapper).
    """
    def mqtt_sink(
        predictions: Union[Dict[str, Any], List[Dict[str, Any]]],
        video_frame: Optional[Union[VideoFrame, List[VideoFrame]]] = None
    ):
        """Sink que publica predicciones vía MQTT"""
        data_plane.publish_inference(predictions, video_frame)

    # Agregar __name__ explícito para identificación
    mqtt_sink.__name__ = 'mqtt_sink'

    return mqtt_sink
