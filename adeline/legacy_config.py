"""
Pipeline Configuration
======================

Carga configuración desde config.yaml y variables de entorno (.env).
"""
import os
import logging
import yaml
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

logger = logging.getLogger(__name__)


# ============================================================================
# MODEL DISABLING (before importing inference)
# ============================================================================
def disable_models_from_config(config_path: str = "config/adeline/config.yaml"):
    """
    Lee config.yaml y deshabilita modelos antes de importar inference.
    Esto previene los warnings de ModelDependencyMissing.

    Esta función debe ser llamada ANTES de importar el módulo inference.
    """
    config_file = Path(config_path)
    if not config_file.exists():
        # Si no hay config, usar defaults (deshabilitar todos los modelos pesados)
        default_disabled = [
            "PALIGEMMA", "FLORENCE2", "QWEN_2_5",
            "CORE_MODEL_SAM", "CORE_MODEL_SAM2", "CORE_MODEL_CLIP",
            "CORE_MODEL_GAZE", "SMOLVLM2", "DEPTH_ESTIMATION",
            "MOONDREAM2", "CORE_MODEL_TROCR", "CORE_MODEL_GROUNDINGDINO",
            "CORE_MODEL_YOLO_WORLD", "CORE_MODEL_PE",
        ]
        for model in default_disabled:
            os.environ[f"{model}_ENABLED"] = "False"
        return

    with open(config_file, 'r') as f:
        config = yaml.safe_load(f)

    models_disabled_cfg = config.get('models_disabled', {})
    disabled_models = models_disabled_cfg.get('disabled', [])

    for model in disabled_models:
        os.environ[f"{model}_ENABLED"] = "False"


# ============================================================================
# PIPELINE CONFIGURATION
# ============================================================================
class PipelineConfig:
    """Configuración del pipeline y MQTT desde config.yaml y .env"""

    def __init__(self, config_path: str = "config/adeline/config.yaml"):
        """
        Carga configuración desde archivo YAML y variables de entorno.

        Args:
            config_path: Ruta al archivo de configuración YAML
        """
        # Cargar config.yaml
        config_file = Path(config_path)
        if not config_file.exists():
            raise FileNotFoundError(
                f"Config file not found: {config_path}\n"
                f"Please create it from config/adeline/config.yaml.example"
            )

        with open(config_file, 'r') as f:
            config = yaml.safe_load(f)

        # Inference Pipeline
        pipeline_cfg = config.get('pipeline', {})
        self.RTSP_URL = pipeline_cfg.get('rtsp_url', 'rtsp://127.0.0.1:8554/live')
        self.MODEL_ID = pipeline_cfg.get('model_id', 'yolov11n-640')
        self.MAX_FPS = pipeline_cfg.get('max_fps', 2)
        self.ENABLE_VISUALIZATION = pipeline_cfg.get('enable_visualization', True)
        self.DISPLAY_STATISTICS = pipeline_cfg.get('display_statistics', True)

        # Models configuration
        models_cfg = config.get('models', {})
        self.USE_LOCAL_MODEL = models_cfg.get('use_local', False)
        self.LOCAL_MODEL_PATH = models_cfg.get('local_path', 'models/yolov11n-320.onnx')
        self.MODEL_IMGSZ = models_cfg.get('imgsz', 320)
        self.MODEL_CONFIDENCE = models_cfg.get('confidence', 0.25)
        self.MODEL_IOU_THRESHOLD = models_cfg.get('iou_threshold', 0.45)

        # API Key from environment variable (sensitive, only needed for Roboflow models)
        self.API_KEY = os.getenv('ROBOFLOW_API_KEY')
        if not self.USE_LOCAL_MODEL and not self.API_KEY:
            raise ValueError(
                "ROBOFLOW_API_KEY not found in environment variables.\n"
                "Please set it in your .env file (copy from .env.example)\n"
                "Or set models.use_local: true to use local ONNX models"
            )

        # MQTT Broker
        mqtt_cfg = config.get('mqtt', {})
        broker_cfg = mqtt_cfg.get('broker', {})
        self.MQTT_BROKER = broker_cfg.get('host', 'localhost')
        self.MQTT_PORT = broker_cfg.get('port', 1883)

        # MQTT credentials from environment variables (sensitive)
        self.MQTT_USERNAME = os.getenv('MQTT_USERNAME') or broker_cfg.get('username')
        self.MQTT_PASSWORD = os.getenv('MQTT_PASSWORD') or broker_cfg.get('password')

        # MQTT Topics
        topics_cfg = mqtt_cfg.get('topics', {})
        self.CONTROL_COMMAND_TOPIC = topics_cfg.get('control_commands', 'inference/control/commands')
        self.CONTROL_STATUS_TOPIC = topics_cfg.get('control_status', 'inference/control/status')
        self.DATA_TOPIC = topics_cfg.get('data', 'inference/data/detections')
        self.METRICS_TOPIC = topics_cfg.get('metrics', 'inference/data/metrics')

        # MQTT QoS
        qos_cfg = mqtt_cfg.get('qos', {})
        self.CONTROL_QOS = qos_cfg.get('control', 1)
        self.DATA_QOS = qos_cfg.get('data', 0)

        # Logging
        logging_cfg = config.get('logging', {})
        self.LOG_LEVEL = logging_cfg.get('level', 'INFO')
        self.LOG_FORMAT = logging_cfg.get('format', '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        self.PAHO_LOG_LEVEL = logging_cfg.get('paho_level', 'WARNING')

        # NOTE: Model disabling ya se hizo en disable_models_from_config()
        # ANTES de importar inference (evita warnings de ModelDependencyMissing)

        # ====================================================================
        # Detection Stabilization (Reduce flickering/parpadeos)
        # ====================================================================
        stabilization_cfg = config.get('detection_stabilization', {})
        self.STABILIZATION_MODE = stabilization_cfg.get('mode', 'none').lower()

        # Temporal params
        temporal_cfg = stabilization_cfg.get('temporal', {})
        self.STABILIZATION_MIN_FRAMES = temporal_cfg.get('min_frames', 3)
        self.STABILIZATION_MAX_GAP = temporal_cfg.get('max_gap', 2)

        # Hysteresis params
        hysteresis_cfg = stabilization_cfg.get('hysteresis', {})
        self.STABILIZATION_APPEAR_CONF = hysteresis_cfg.get('appear_confidence', 0.5)
        self.STABILIZATION_PERSIST_CONF = hysteresis_cfg.get('persist_confidence', 0.3)

        # IoU matching params (for multi-object tracking)
        iou_cfg = stabilization_cfg.get('iou', {})
        self.STABILIZATION_IOU_THRESHOLD = iou_cfg.get('threshold', 0.3)

        # ====================================================================
        # ROI Strategy (New unified config structure)
        # ====================================================================
        # Backward compatibility: Check for new roi_strategy OR legacy adaptive_crop
        roi_strategy_cfg = config.get('roi_strategy', {})

        if roi_strategy_cfg:
            # New structure: roi_strategy
            self.ROI_MODE = roi_strategy_cfg.get('mode', 'none').lower()

            # Adaptive ROI parameters
            adaptive_cfg = roi_strategy_cfg.get('adaptive', {})
            self.CROP_MARGIN = adaptive_cfg.get('margin', 0.2)
            self.CROP_SMOOTHING = adaptive_cfg.get('smoothing', 0.3)
            self.CROP_MIN_ROI_MULTIPLE = adaptive_cfg.get('min_roi_multiple', 1)
            self.CROP_MAX_ROI_MULTIPLE = adaptive_cfg.get('max_roi_multiple', 4)
            self.CROP_SHOW_STATISTICS = adaptive_cfg.get('show_statistics', True)
            self.ADAPTIVE_RESIZE_TO_MODEL = adaptive_cfg.get('resize_to_model', False)

            # Fixed ROI parameters
            fixed_cfg = roi_strategy_cfg.get('fixed', {})
            self.FIXED_X_MIN = fixed_cfg.get('x_min', 0.2)
            self.FIXED_Y_MIN = fixed_cfg.get('y_min', 0.2)
            self.FIXED_X_MAX = fixed_cfg.get('x_max', 0.8)
            self.FIXED_Y_MAX = fixed_cfg.get('y_max', 0.8)
            self.FIXED_SHOW_OVERLAY = fixed_cfg.get('show_overlay', True)
            self.FIXED_RESIZE_TO_MODEL = fixed_cfg.get('resize_to_model', False)

        else:
            # Backward compatibility: Legacy adaptive_crop.enabled structure
            adaptive_crop_cfg = config.get('adaptive_crop', {})
            legacy_enabled = adaptive_crop_cfg.get('enabled', False)

            # Convert legacy config to new ROI_MODE
            self.ROI_MODE = 'adaptive' if legacy_enabled else 'none'

            # Legacy adaptive parameters
            self.CROP_MARGIN = adaptive_crop_cfg.get('margin', 0.2)
            self.CROP_SMOOTHING = adaptive_crop_cfg.get('smoothing', 0.3)
            self.CROP_MIN_ROI_MULTIPLE = adaptive_crop_cfg.get('min_roi_multiple', 1)
            self.CROP_MAX_ROI_MULTIPLE = adaptive_crop_cfg.get('max_roi_multiple', 4)
            self.CROP_SHOW_STATISTICS = adaptive_crop_cfg.get('show_statistics', True)
            self.ADAPTIVE_RESIZE_TO_MODEL = adaptive_crop_cfg.get('resize_to_model', False)

            # Fixed defaults (unused in legacy mode)
            self.FIXED_X_MIN = 0.2
            self.FIXED_Y_MIN = 0.2
            self.FIXED_X_MAX = 0.8
            self.FIXED_Y_MAX = 0.8
            self.FIXED_SHOW_OVERLAY = True
            self.FIXED_RESIZE_TO_MODEL = False

            if legacy_enabled:
                logger.warning(
                    "⚠️ Using legacy 'adaptive_crop.enabled' config. "
                    "Consider migrating to 'roi_strategy.mode' structure (see config.yaml.example)"
                )
