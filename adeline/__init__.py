"""
Adeline - Inference Pipeline with MQTT Control
===============================================

Sistema de inferencia de visión por computadora (YOLO) con control remoto MQTT.

Public API:
- PipelineConfig: Configuración del sistema
- InferencePipelineController: Controlador principal
- MQTTControlPlane: Control plane (QoS 1)
- MQTTDataPlane: Data plane (QoS 0)

Usage:
    # Run main pipeline
    python -m adeline

    # Or programmatically
    from adeline import PipelineConfig, InferencePipelineController

    config = PipelineConfig()
    controller = InferencePipelineController(config)
    controller.run()
"""

__version__ = "1.0.0"

from .config import PipelineConfig, disable_models_from_config
from .app import InferencePipelineController, main
from .control import MQTTControlPlane
from .data import MQTTDataPlane, create_mqtt_sink

__all__ = [
    # Config
    "PipelineConfig",
    "disable_models_from_config",
    # App
    "InferencePipelineController",
    "main",
    # Control Plane
    "MQTTControlPlane",
    # Data Plane
    "MQTTDataPlane",
    "create_mqtt_sink",
]
