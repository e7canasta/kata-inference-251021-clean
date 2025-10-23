"""
Pydantic Configuration Schemas
================================

Type-safe configuration validation usando Pydantic v2.

Benefits:
- Validación en load time (no en runtime)
- Type safety con IDE autocomplete
- Mejores mensajes de error
- Documentación auto-generada

Usage:
    config = AdelineConfig.from_yaml("config/adeline/config.yaml")
    # Config ya está validado, tipos garantizados
"""
from typing import Literal, Optional, List
from pathlib import Path
from pydantic import BaseModel, Field, field_validator, model_validator
from pydantic_settings import BaseSettings
import os


# ============================================================================
# Pipeline Configuration
# ============================================================================

class PipelineSettings(BaseModel):
    """Pipeline inference settings"""
    rtsp_url: str = Field(
        default="rtsp://127.0.0.1:8554/live",
        description="RTSP stream URL"
    )
    model_id: str = Field(
        default="yolov11n-640",
        description="Roboflow model ID"
    )
    max_fps: int = Field(
        default=2,
        ge=1,
        le=30,
        description="Maximum frames per second"
    )
    enable_visualization: bool = Field(
        default=True,
        description="Enable visualization window"
    )
    display_statistics: bool = Field(
        default=True,
        description="Display statistics in visualization"
    )


class ModelsSettings(BaseModel):
    """Model configuration (local ONNX or Roboflow)"""
    use_local: bool = Field(
        default=False,
        description="Use local ONNX model instead of Roboflow"
    )
    local_path: str = Field(
        default="models/yolov11n-320.onnx",
        description="Path to local ONNX model"
    )
    imgsz: int = Field(
        default=320,
        ge=64,
        le=1280,
        description="Model input size (must be multiple of 32)"
    )
    confidence: float = Field(
        default=0.25,
        ge=0.0,
        le=1.0,
        description="Confidence threshold"
    )
    iou_threshold: float = Field(
        default=0.45,
        ge=0.0,
        le=1.0,
        description="IoU threshold for NMS"
    )

    @field_validator('imgsz')
    @classmethod
    def validate_imgsz_multiple_of_32(cls, v: int) -> int:
        """Validate that imgsz is multiple of 32 (YOLO requirement)"""
        if v % 32 != 0:
            raise ValueError(f"imgsz must be multiple of 32, got {v}")
        return v


# ============================================================================
# MQTT Configuration
# ============================================================================

class MQTTBrokerSettings(BaseModel):
    """MQTT broker connection settings"""
    host: str = Field(
        default="localhost",
        description="MQTT broker hostname"
    )
    port: int = Field(
        default=1883,
        ge=1,
        le=65535,
        description="MQTT broker port"
    )
    username: Optional[str] = Field(
        default=None,
        description="MQTT username (optional, from env)"
    )
    password: Optional[str] = Field(
        default=None,
        description="MQTT password (optional, from env)"
    )


class MQTTTopicsSettings(BaseModel):
    """MQTT topic configuration"""
    control_commands: str = Field(
        default="inference/control/commands",
        description="Control commands topic (QoS 1)"
    )
    control_status: str = Field(
        default="inference/control/status",
        description="Control status topic"
    )
    data: str = Field(
        default="inference/data/detections",
        description="Data detections topic (QoS 0)"
    )
    metrics: str = Field(
        default="inference/data/metrics",
        description="Metrics topic"
    )


class MQTTQoSSettings(BaseModel):
    """MQTT QoS levels"""
    control: Literal[0, 1, 2] = Field(
        default=1,
        description="Control plane QoS (recommended: 1 for reliability)"
    )
    data: Literal[0, 1, 2] = Field(
        default=0,
        description="Data plane QoS (recommended: 0 for performance)"
    )


class MQTTSettings(BaseModel):
    """Complete MQTT configuration"""
    broker: MQTTBrokerSettings = Field(default_factory=MQTTBrokerSettings)
    topics: MQTTTopicsSettings = Field(default_factory=MQTTTopicsSettings)
    qos: MQTTQoSSettings = Field(default_factory=MQTTQoSSettings)


# ============================================================================
# Stabilization Configuration
# ============================================================================

class TemporalStabilizationSettings(BaseModel):
    """Temporal filtering parameters"""
    min_frames: int = Field(
        default=3,
        ge=1,
        description="Minimum consecutive frames to confirm detection"
    )
    max_gap: int = Field(
        default=2,
        ge=0,
        description="Maximum gap frames before removing track"
    )


class HysteresisStabilizationSettings(BaseModel):
    """Hysteresis filtering parameters"""
    appear_confidence: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="High threshold for new detections"
    )
    persist_confidence: float = Field(
        default=0.3,
        ge=0.0,
        le=1.0,
        description="Low threshold for confirmed detections"
    )

    @model_validator(mode='after')
    def validate_hysteresis_order(self):
        """Persist confidence must be <= appear confidence"""
        if self.persist_confidence > self.appear_confidence:
            raise ValueError(
                f"persist_confidence ({self.persist_confidence}) must be <= "
                f"appear_confidence ({self.appear_confidence})"
            )
        return self


class IoUStabilizationSettings(BaseModel):
    """IoU matching parameters for multi-object tracking"""
    threshold: float = Field(
        default=0.3,
        ge=0.0,
        le=1.0,
        description="Minimum IoU to consider same object"
    )


class StabilizationSettings(BaseModel):
    """Detection stabilization configuration"""
    mode: Literal['none', 'temporal'] = Field(
        default='none',
        description="Stabilization mode"
    )
    temporal: TemporalStabilizationSettings = Field(
        default_factory=TemporalStabilizationSettings
    )
    hysteresis: HysteresisStabilizationSettings = Field(
        default_factory=HysteresisStabilizationSettings
    )
    iou: IoUStabilizationSettings = Field(
        default_factory=IoUStabilizationSettings
    )


# ============================================================================
# ROI Strategy Configuration
# ============================================================================

class AdaptiveROISettings(BaseModel):
    """Adaptive ROI parameters"""
    margin: float = Field(
        default=0.2,
        ge=0.0,
        le=1.0,
        description="Expansion margin around detections"
    )
    smoothing: float = Field(
        default=0.3,
        ge=0.0,
        le=1.0,
        description="Temporal smoothing factor"
    )
    min_roi_multiple: int = Field(
        default=1,
        ge=1,
        description="Minimum ROI size as multiple of imgsz"
    )
    max_roi_multiple: int = Field(
        default=4,
        ge=1,
        description="Maximum ROI size as multiple of imgsz"
    )
    show_statistics: bool = Field(
        default=True,
        description="Show ROI statistics in visualization"
    )
    resize_to_model: bool = Field(
        default=False,
        description="Resize ROI to model size (zoom) vs padding"
    )

    @model_validator(mode='after')
    def validate_roi_multiples(self):
        """Min multiple must be <= max multiple"""
        if self.min_roi_multiple > self.max_roi_multiple:
            raise ValueError(
                f"min_roi_multiple ({self.min_roi_multiple}) must be <= "
                f"max_roi_multiple ({self.max_roi_multiple})"
            )
        return self


class FixedROISettings(BaseModel):
    """Fixed ROI parameters (normalized coordinates)"""
    x_min: float = Field(
        default=0.2,
        ge=0.0,
        le=1.0,
        description="Left boundary (normalized)"
    )
    y_min: float = Field(
        default=0.2,
        ge=0.0,
        le=1.0,
        description="Top boundary (normalized)"
    )
    x_max: float = Field(
        default=0.8,
        ge=0.0,
        le=1.0,
        description="Right boundary (normalized)"
    )
    y_max: float = Field(
        default=0.8,
        ge=0.0,
        le=1.0,
        description="Bottom boundary (normalized)"
    )
    show_overlay: bool = Field(
        default=True,
        description="Show fixed ROI overlay"
    )
    resize_to_model: bool = Field(
        default=False,
        description="Resize ROI to model size vs padding"
    )

    @model_validator(mode='after')
    def validate_bounds(self):
        """Validate that min < max for both dimensions"""
        if self.x_min >= self.x_max:
            raise ValueError(
                f"x_min ({self.x_min}) must be < x_max ({self.x_max})"
            )
        if self.y_min >= self.y_max:
            raise ValueError(
                f"y_min ({self.y_min}) must be < y_max ({self.y_max})"
            )
        return self


class ROIStrategySettings(BaseModel):
    """ROI strategy configuration"""
    mode: Literal['none', 'adaptive', 'fixed'] = Field(
        default='none',
        description="ROI mode"
    )
    adaptive: AdaptiveROISettings = Field(
        default_factory=AdaptiveROISettings
    )
    fixed: FixedROISettings = Field(
        default_factory=FixedROISettings
    )


# ============================================================================
# Logging Configuration
# ============================================================================

class LoggingSettings(BaseModel):
    """Logging configuration (JSON structured logging)"""
    level: Literal['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'] = Field(
        default='INFO',
        description="Log level"
    )
    json_indent: Optional[int] = Field(
        default=None,
        ge=0,
        le=4,
        description="JSON indent for pretty-print (None=compact, 2=readable)"
    )
    paho_level: Literal['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'] = Field(
        default='WARNING',
        description="Paho MQTT library log level"
    )
    file: Optional[str] = Field(
        default=None,
        description="Path to log file (None=stdout). If specified, enables file rotation."
    )
    max_bytes: int = Field(
        default=10485760,  # 10 MB
        ge=1024,
        description="Maximum bytes per log file before rotation (default 10 MB)"
    )
    backup_count: int = Field(
        default=5,
        ge=0,
        description="Number of backup log files to keep"
    )


# ============================================================================
# Models Disabled Configuration
# ============================================================================

class ModelsDisabledSettings(BaseModel):
    """Models to disable (prevent ModelDependencyMissing warnings)"""
    disabled: List[str] = Field(
        default_factory=lambda: [
            "PALIGEMMA",
            "FLORENCE2",
            "QWEN_2_5",
            "CORE_MODEL_SAM",
            "CORE_MODEL_SAM2",
            "CORE_MODEL_CLIP",
            "CORE_MODEL_GAZE",
            "SMOLVLM2",
            "DEPTH_ESTIMATION",
            "MOONDREAM2",
            "CORE_MODEL_TROCR",
            "CORE_MODEL_GROUNDINGDINO",
            "CORE_MODEL_YOLO_WORLD",
            "CORE_MODEL_PE",
        ],
        description="List of models to disable"
    )


# ============================================================================
# Root Configuration
# ============================================================================

class AdelineConfig(BaseModel):
    """
    Root Adeline configuration with full validation.

    Loads from YAML and validates all settings.
    Environment variables override YAML for sensitive data.
    """
    pipeline: PipelineSettings = Field(default_factory=PipelineSettings)
    models: ModelsSettings = Field(default_factory=ModelsSettings)
    mqtt: MQTTSettings = Field(default_factory=MQTTSettings)
    detection_stabilization: StabilizationSettings = Field(
        default_factory=StabilizationSettings
    )
    roi_strategy: ROIStrategySettings = Field(default_factory=ROIStrategySettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
    models_disabled: ModelsDisabledSettings = Field(
        default_factory=ModelsDisabledSettings
    )

    @classmethod
    def from_yaml(cls, config_path: str) -> 'AdelineConfig':
        """
        Load and validate configuration from YAML file.

        Args:
            config_path: Path to config.yaml

        Returns:
            Validated AdelineConfig instance

        Raises:
            FileNotFoundError: If config file doesn't exist
            ValidationError: If config is invalid

        Example:
            config = AdelineConfig.from_yaml("config/adeline/config.yaml")
            print(config.pipeline.max_fps)  # Type-safe access
        """
        import yaml

        config_file = Path(config_path)
        if not config_file.exists():
            raise FileNotFoundError(
                f"Config file not found: {config_path}\n"
                f"Please create it from config/adeline/config.yaml.example"
            )

        with open(config_file, 'r') as f:
            config_dict = yaml.safe_load(f)

        # Override sensitive data from environment variables
        if 'mqtt' in config_dict and 'broker' in config_dict['mqtt']:
            if os.getenv('MQTT_USERNAME'):
                config_dict['mqtt']['broker']['username'] = os.getenv('MQTT_USERNAME')
            if os.getenv('MQTT_PASSWORD'):
                config_dict['mqtt']['broker']['password'] = os.getenv('MQTT_PASSWORD')

        # Validate and return
        return cls(**config_dict)

    def to_legacy_config(self) -> 'PipelineConfig':
        """
        Convert to legacy PipelineConfig for backward compatibility.

        This allows gradual migration without breaking existing code.

        Returns:
            PipelineConfig instance with same values
        """
        from ..legacy_config import PipelineConfig

        # Create legacy config manually (bypass __init__ validation)
        legacy = object.__new__(PipelineConfig)

        # Pipeline
        legacy.RTSP_URL = self.pipeline.rtsp_url
        legacy.MODEL_ID = self.pipeline.model_id
        legacy.MAX_FPS = self.pipeline.max_fps
        legacy.ENABLE_VISUALIZATION = self.pipeline.enable_visualization
        legacy.DISPLAY_STATISTICS = self.pipeline.display_statistics

        # Models
        legacy.USE_LOCAL_MODEL = self.models.use_local
        legacy.LOCAL_MODEL_PATH = self.models.local_path
        legacy.MODEL_IMGSZ = self.models.imgsz
        legacy.MODEL_CONFIDENCE = self.models.confidence
        legacy.MODEL_IOU_THRESHOLD = self.models.iou_threshold

        # API Key (from env, only needed for Roboflow)
        legacy.API_KEY = os.getenv('ROBOFLOW_API_KEY')

        # MQTT Broker
        legacy.MQTT_BROKER = self.mqtt.broker.host
        legacy.MQTT_PORT = self.mqtt.broker.port
        legacy.MQTT_USERNAME = self.mqtt.broker.username
        legacy.MQTT_PASSWORD = self.mqtt.broker.password

        # MQTT Topics
        legacy.CONTROL_COMMAND_TOPIC = self.mqtt.topics.control_commands
        legacy.CONTROL_STATUS_TOPIC = self.mqtt.topics.control_status
        legacy.DATA_TOPIC = self.mqtt.topics.data
        legacy.METRICS_TOPIC = self.mqtt.topics.metrics

        # MQTT QoS
        legacy.CONTROL_QOS = self.mqtt.qos.control
        legacy.DATA_QOS = self.mqtt.qos.data

        # Logging
        legacy.LOG_LEVEL = self.logging.level
        legacy.LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'  # DEPRECATED
        legacy.JSON_INDENT = self.logging.json_indent
        legacy.PAHO_LOG_LEVEL = self.logging.paho_level
        legacy.LOG_FILE = self.logging.file
        legacy.LOG_MAX_BYTES = self.logging.max_bytes
        legacy.LOG_BACKUP_COUNT = self.logging.backup_count

        # Stabilization
        legacy.STABILIZATION_MODE = self.detection_stabilization.mode
        legacy.STABILIZATION_MIN_FRAMES = self.detection_stabilization.temporal.min_frames
        legacy.STABILIZATION_MAX_GAP = self.detection_stabilization.temporal.max_gap
        legacy.STABILIZATION_APPEAR_CONF = self.detection_stabilization.hysteresis.appear_confidence
        legacy.STABILIZATION_PERSIST_CONF = self.detection_stabilization.hysteresis.persist_confidence
        legacy.STABILIZATION_IOU_THRESHOLD = self.detection_stabilization.iou.threshold

        # ROI Strategy
        legacy.ROI_MODE = self.roi_strategy.mode
        legacy.CROP_MARGIN = self.roi_strategy.adaptive.margin
        legacy.CROP_SMOOTHING = self.roi_strategy.adaptive.smoothing
        legacy.CROP_MIN_ROI_MULTIPLE = self.roi_strategy.adaptive.min_roi_multiple
        legacy.CROP_MAX_ROI_MULTIPLE = self.roi_strategy.adaptive.max_roi_multiple
        legacy.CROP_SHOW_STATISTICS = self.roi_strategy.adaptive.show_statistics
        legacy.ADAPTIVE_RESIZE_TO_MODEL = self.roi_strategy.adaptive.resize_to_model

        legacy.FIXED_X_MIN = self.roi_strategy.fixed.x_min
        legacy.FIXED_Y_MIN = self.roi_strategy.fixed.y_min
        legacy.FIXED_X_MAX = self.roi_strategy.fixed.x_max
        legacy.FIXED_Y_MAX = self.roi_strategy.fixed.y_max
        legacy.FIXED_SHOW_OVERLAY = self.roi_strategy.fixed.show_overlay
        legacy.FIXED_RESIZE_TO_MODEL = self.roi_strategy.fixed.resize_to_model

        return legacy
