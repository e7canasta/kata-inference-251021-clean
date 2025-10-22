"""
Publishers
==========

Publishers especializados para formatear mensajes MQTT.

Responsabilidad:
- Conocen estructura de mensajes (lógica de negocio)
- Formatean datos para publicación
- NO conocen detalles de MQTT (eso es del DataPlane)

Diseño: Complejidad por diseño
- Publishers = lógica de negocio
- DataPlane = infraestructura MQTT
- SRP: cada publisher un tipo de mensaje
"""
from .detection import DetectionPublisher
from .metrics import MetricsPublisher

__all__ = ['DetectionPublisher', 'MetricsPublisher']
