"""
InferencePipeline con MQTT Control y Data Plane
================================================

Control Plane: Controla el pipeline (start/stop/pause) vía MQTT
Data Plane: Publica resultados de inferencia vía MQTT
"""
import os
import signal
import sys
import logging
import yaml
from functools import partial
from pathlib import Path
from threading import Event
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# ============================================================================
# DISABLE UNUSED MODELS (BEFORE importing inference)
# ============================================================================
# IMPORTANTE: Setear env vars ANTES de importar inference para evitar warnings
def _disable_models_from_config(config_path: str = "config.yaml"):
    """
    Lee config.yaml y deshabilita modelos antes de importar inference.
    Esto previene los warnings de ModelDependencyMissing.
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

# Disable models ANTES de imports
_disable_models_from_config()

# NOW import inference (warnings should be suppressed)
from inference import InferencePipeline
from inference.core.interfaces.stream.sinks import multi_sink
from inference.core.interfaces.camera.entities import StatusUpdate, UpdateSeverity
from inference.core.interfaces.stream.watchdog import BasePipelineWatchDog

from .mqtt_bridge import MQTTControlPlane, MQTTDataPlane, create_mqtt_sink
from .visualization import create_visualization_sink

# Logger (será configurado en main() con config values)
logger = logging.getLogger(__name__)


# ============================================================================
# CONFIGURACIÓN
# ============================================================================
class PipelineConfig:
    """Configuración del pipeline y MQTT desde config.yaml y .env"""

    def __init__(self, config_path: str = "config.yaml"):
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
                f"Please create it from config.yaml.example"
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

        # NOTE: Model disabling ya se hizo en _disable_models_from_config()
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


# ============================================================================
# PIPELINE CONTROLLER
# ============================================================================
class InferencePipelineController:
    """
    Controlador del pipeline con MQTT control y data plane.
    """
    
    def __init__(self, config: PipelineConfig):
        self.config = config
        self.pipeline = None
        self.control_plane = None
        self.data_plane = None
        self.watchdog = BasePipelineWatchDog()  # Monitoreo de métricas
        self.shutdown_event = Event()
        self.is_running = False
        
    def setup(self):
        """Inicializa el pipeline y las conexiones MQTT"""
        logger.info("🚀 Inicializando InferencePipeline con MQTT...")
        
        # 1. Configurar Data Plane (publicador de inferencias)
        logger.info("📡 Configurando Data Plane...")
        self.data_plane = MQTTDataPlane(
            broker_host=self.config.MQTT_BROKER,
            broker_port=self.config.MQTT_PORT,
            data_topic=self.config.DATA_TOPIC,
            metrics_topic=self.config.METRICS_TOPIC,
            username=self.config.MQTT_USERNAME,
            password=self.config.MQTT_PASSWORD,
            qos=self.config.DATA_QOS,
        )
        
        if not self.data_plane.connect(timeout=10):
            logger.error("❌ No se pudo conectar Data Plane")
            return False

        # Conectar watchdog al Data Plane para publicar métricas
        self.data_plane.set_watchdog(self.watchdog)

        # 2. Crear sink para publicar inferencias
        mqtt_sink = create_mqtt_sink(self.data_plane)

        # 2b. Detection Stabilization (wrappea mqtt_sink si está habilitado)
        if self.config.STABILIZATION_MODE != 'none':
            from .detection_stabilization import (
                create_stabilization_strategy,
                create_stabilization_sink,
                StabilizationConfig,
            )

            logger.info("🔧 Configurando Detection Stabilization...")

            # Crear configuración validada
            stab_config = StabilizationConfig(
                mode=self.config.STABILIZATION_MODE,
                temporal_min_frames=self.config.STABILIZATION_MIN_FRAMES,
                temporal_max_gap=self.config.STABILIZATION_MAX_GAP,
                hysteresis_appear_conf=self.config.STABILIZATION_APPEAR_CONF,
                hysteresis_persist_conf=self.config.STABILIZATION_PERSIST_CONF,
            )

            # Factory: Crear stabilizer
            self.stabilizer = create_stabilization_strategy(stab_config)

            # Wrappear mqtt_sink con stabilization
            mqtt_sink = create_stabilization_sink(
                stabilizer=self.stabilizer,
                downstream_sink=mqtt_sink,
            )

            logger.info(f"✅ Detection Stabilization habilitado: mode={self.config.STABILIZATION_MODE}")
        else:
            self.stabilizer = None
            logger.info("🔲 Detection Stabilization: NONE (baseline, sin filtrado)")

        # ====================================================================
        # 3 & 4. PIPELINE CREATION: Default vs Custom Logic (ROI Strategy)
        # ====================================================================

        if self.config.ROI_MODE in ['adaptive', 'fixed']:
            # ================================================================
            # CUSTOM LOGIC: ROI Strategy (Adaptive or Fixed)
            # ================================================================
            from .roi_strategies import (
                validate_and_create_roi_strategy,
                ROIStrategyConfig,
                FixedROIInferenceHandler,
            )
            from .adaptive_roi import (
                AdaptiveInferenceHandler,
                roi_update_sink,
            )

            # Crear configuración validada
            roi_config = ROIStrategyConfig(
                mode=self.config.ROI_MODE,
                # Adaptive params
                adaptive_margin=self.config.CROP_MARGIN,
                adaptive_smoothing=self.config.CROP_SMOOTHING,
                adaptive_min_roi_multiple=self.config.CROP_MIN_ROI_MULTIPLE,
                adaptive_max_roi_multiple=self.config.CROP_MAX_ROI_MULTIPLE,
                adaptive_show_statistics=self.config.CROP_SHOW_STATISTICS,
                adaptive_resize_to_model=self.config.ADAPTIVE_RESIZE_TO_MODEL,
                # Fixed params
                fixed_x_min=self.config.FIXED_X_MIN,
                fixed_y_min=self.config.FIXED_Y_MIN,
                fixed_x_max=self.config.FIXED_X_MAX,
                fixed_y_max=self.config.FIXED_Y_MAX,
                fixed_show_overlay=self.config.FIXED_SHOW_OVERLAY,
                fixed_resize_to_model=self.config.FIXED_RESIZE_TO_MODEL,
                # Model config
                imgsz=self.config.MODEL_IMGSZ,
            )

            # Factory: Crear ROI state apropiado (Adaptive o Fixed)
            self.roi_state = validate_and_create_roi_strategy(
                mode=self.config.ROI_MODE,
                config=roi_config,
            )

            # Crear modelo (local ONNX o Roboflow según config)
            from .local_models import get_model_from_config, get_process_frame_function
            from inference.core.interfaces.stream.entities import ModelConfig

            model = get_model_from_config(
                use_local=self.config.USE_LOCAL_MODEL,
                local_path=self.config.LOCAL_MODEL_PATH,
                model_id=self.config.MODEL_ID,
                api_key=self.config.API_KEY,
                imgsz=self.config.MODEL_IMGSZ,
            )

            # Configuración de inferencia
            inference_config = ModelConfig.init(
                confidence=self.config.MODEL_CONFIDENCE,
                iou_threshold=self.config.MODEL_IOU_THRESHOLD,
            )

            # Función de procesamiento apropiada según tipo de modelo
            process_frame_fn = get_process_frame_function(model)

            # Factory: Crear handler apropiado según estrategia ROI
            if self.config.ROI_MODE == 'adaptive':
                logger.info("🔄 Using AdaptiveInferenceHandler (dynamic ROI)")
                self.inference_handler = AdaptiveInferenceHandler(
                    model=model,
                    inference_config=inference_config,
                    roi_state=self.roi_state,
                    process_frame_fn=process_frame_fn,
                    show_statistics=self.config.CROP_SHOW_STATISTICS,
                )
            elif self.config.ROI_MODE == 'fixed':
                logger.info("📍 Using FixedROIInferenceHandler (static ROI)")
                self.inference_handler = FixedROIInferenceHandler(
                    model=model,
                    inference_config=inference_config,
                    roi_state=self.roi_state,
                    process_frame_fn=process_frame_fn,
                    show_statistics=self.config.CROP_SHOW_STATISTICS,
                )
            else:
                raise ValueError(f"Invalid ROI_MODE for custom logic: {self.config.ROI_MODE}")

            # Configurar sinks: MQTT + ROI update (solo adaptive) + visualización
            sinks_list = [mqtt_sink]

            # ROI update sink solo para adaptive (fixed es inmutable)
            if self.config.ROI_MODE == 'adaptive':
                roi_sink = partial(roi_update_sink, roi_state=self.roi_state)
                sinks_list.append(roi_sink)

            if self.config.ENABLE_VISUALIZATION:
                # Window name según estrategia
                window_name = f"Inference Pipeline ({self.config.ROI_MODE.capitalize()} ROI)"

                # Sink unificado: detecciones + ROI en una sola ventana
                viz_sink = create_visualization_sink(
                    roi_state=self.roi_state,
                    inference_handler=self.inference_handler,
                    display_stats=self.config.DISPLAY_STATISTICS,
                    window_name=window_name,
                )
                sinks_list.append(viz_sink)

            on_prediction = partial(multi_sink, sinks=sinks_list)

            # Pipeline con custom logic
            logger.info("🔧 Creando InferencePipeline (custom logic)...")
            self.pipeline = InferencePipeline.init_with_custom_logic(
                video_reference=self.config.RTSP_URL,
                on_video_frame=self.inference_handler,  # Custom wrapper
                on_prediction=on_prediction,
                max_fps=self.config.MAX_FPS,
                watchdog=self.watchdog,
                status_update_handlers=[self._status_update_handler],
            )

        else:
            # ================================================================
            # DEFAULT PIPELINE: Standard Roboflow model inference
            # ================================================================
            logger.info("📦 Usando pipeline standard (default)")

            # Configurar sinks (MQTT + visualización opcional)
            if self.config.ENABLE_VISUALIZATION:
                # Sink unificado de visualización
                viz_sink = create_visualization_sink(
                    roi_state=None,
                    inference_handler=None,
                    display_stats=self.config.DISPLAY_STATISTICS,
                    window_name="Inference Pipeline (Standard)",
                )
                on_prediction = partial(multi_sink, sinks=[mqtt_sink, viz_sink])
            else:
                on_prediction = mqtt_sink

            # Pipeline standard
            logger.info("🔧 Creando InferencePipeline (standard)...")
            self.pipeline = InferencePipeline.init(
                max_fps=self.config.MAX_FPS,
                model_id=self.config.MODEL_ID,
                video_reference=self.config.RTSP_URL,
                on_prediction=on_prediction,
                api_key=self.config.API_KEY,
                watchdog=self.watchdog,
                status_update_handlers=[self._status_update_handler],
            )
        
        # 5. Configurar Control Plane (receptor de comandos)
        logger.info("🎮 Configurando Control Plane...")
        self.control_plane = MQTTControlPlane(
            broker_host=self.config.MQTT_BROKER,
            broker_port=self.config.MQTT_PORT,
            command_topic=self.config.CONTROL_COMMAND_TOPIC,
            status_topic=self.config.CONTROL_STATUS_TOPIC,
            username=self.config.MQTT_USERNAME,
            password=self.config.MQTT_PASSWORD,
        )
        
        # Configurar callbacks de control (sin START, pipeline auto-inicia)
        self.control_plane.on_stop = self._handle_stop
        self.control_plane.on_pause = self._handle_pause
        self.control_plane.on_resume = self._handle_resume
        self.control_plane.on_metrics = self._handle_metrics

        # Callback TOGGLE_CROP solo para adaptive (fixed no tiene toggle)
        if self.config.ROI_MODE == 'adaptive':
            self.control_plane.on_toggle_crop = self._handle_toggle_crop

        # Callback STABILIZATION_STATS solo si stabilization habilitado
        if self.config.STABILIZATION_MODE != 'none':
            self.control_plane.on_stabilization_stats = self._handle_stabilization_stats

        if not self.control_plane.connect(timeout=10):
            logger.error("❌ No se pudo conectar Control Plane")
            return False
        
        # 6. Auto-iniciar el pipeline
        logger.info("▶️ Iniciando pipeline automáticamente...")
        try:
            self.is_running = True  # Setear ANTES porque start() puede bloquear
            self.pipeline.start()
            logger.info("✅ Pipeline iniciado y corriendo")
        except Exception as e:
            logger.error(f"❌ Error iniciando pipeline: {e}", exc_info=True)
            self.is_running = False  # Revertir si falla
            return False

        logger.info("✅ Setup completado")
        return True
    
    def _status_update_handler(self, status: StatusUpdate):
        """Handler para status updates del pipeline"""
        if status.severity.value >= UpdateSeverity.WARNING.value:
            logger.warning(
                f"Pipeline Status: [{status.severity.name}] {status.event_type}"
            )
    
    def _handle_stop(self):
        """Callback para comando STOP - detiene y finaliza el programa"""
        logger.info("⏹️ Comando STOP recibido")
        if self.is_running:
            try:
                self.pipeline.terminate()
                self.is_running = False
                logger.info("✅ Pipeline detenido")
            except Exception as e:
                logger.error(f"❌ Error deteniendo pipeline: {e}")

        # Siempre setear shutdown_event para terminar el programa
        logger.info("🛑 Finalizando servicio...")
        self.shutdown_event.set()
    
    def _handle_pause(self):
        """Callback para comando PAUSE - pausa temporalmente el procesamiento"""
        logger.info("⏸️ Comando PAUSE recibido")
        if self.is_running:
            try:
                self.pipeline.pause_stream()
                logger.info("✅ Pipeline pausado (usa RESUME para continuar)")
            except Exception as e:
                logger.error(f"❌ Error pausando pipeline: {e}", exc_info=True)
        else:
            logger.warning("⚠️ Pipeline no está corriendo, no se puede pausar")
    
    def _handle_resume(self):
        """Callback para comando RESUME - reanuda después de PAUSE"""
        logger.info("▶️ Comando RESUME recibido")
        if self.is_running:
            try:
                self.pipeline.resume_stream()
                logger.info("✅ Pipeline resumido")
            except Exception as e:
                logger.error(f"❌ Error resumiendo pipeline: {e}", exc_info=True)
        else:
            logger.warning("⚠️ Pipeline no está corriendo, no se puede resumir (usa STOP para terminar correctamente)")

    def _handle_metrics(self):
        """Callback para comando METRICS - publica métricas del watchdog vía MQTT"""
        logger.info("📊 Comando METRICS recibido")
        try:
            self.data_plane.publish_metrics()
        except Exception as e:
            logger.error(f"❌ Error publicando métricas: {e}", exc_info=True)

    def _handle_toggle_crop(self):
        """Callback para comando TOGGLE_CROP - habilita/deshabilita crop (solo adaptive)"""
        logger.info("🔲 Comando TOGGLE_CROP recibido")

        if self.config.ROI_MODE != 'adaptive':
            logger.warning(f"⚠️ TOGGLE_CROP no disponible en modo '{self.config.ROI_MODE}'")
            logger.info("💡 Para usar TOGGLE_CROP, configurar roi_strategy.mode: adaptive en config.yaml")
            return

        if not hasattr(self, 'inference_handler'):
            logger.warning("⚠️ TOGGLE_CROP no disponible - pipeline en modo standard")
            return

        # Toggle estado
        new_state = not self.inference_handler.enabled
        self.inference_handler.enabled = new_state

        logger.info(f"✅ Adaptive Crop {'ENABLED' if new_state else 'DISABLED'}")

        # Opcional: resetear ROI al deshabilitar
        if not new_state and hasattr(self, 'roi_state'):
            self.roi_state.reset()
            logger.info("🔄 ROI state reset to full frame")

    def _handle_stabilization_stats(self):
        """Callback para comando STABILIZATION_STATS - publica estadísticas de estabilización"""
        logger.info("📊 Comando STABILIZATION_STATS recibido")

        if self.config.STABILIZATION_MODE == 'none':
            logger.warning("⚠️ Detection Stabilization no habilitado (mode='none')")
            logger.info("💡 Para habilitar, configurar detection_stabilization.mode en config.yaml")
            return

        if not hasattr(self, 'stabilizer') or self.stabilizer is None:
            logger.warning("⚠️ Stabilizer no disponible")
            return

        try:
            # Obtener estadísticas del stabilizer
            stats = self.stabilizer.get_stats(source_id=0)

            # Log estadísticas
            logger.info("📈 Detection Stabilization Stats:")
            logger.info(f"   Mode: {self.config.STABILIZATION_MODE}")
            logger.info(f"   Total detected: {stats.get('total_detected', 0)}")
            logger.info(f"   Total confirmed: {stats.get('total_confirmed', 0)}")
            logger.info(f"   Total ignored: {stats.get('total_ignored', 0)}")
            logger.info(f"   Total removed: {stats.get('total_removed', 0)}")
            logger.info(f"   Active tracks: {stats.get('active_tracks', 0)}")
            logger.info(f"   Confirm ratio: {stats.get('confirm_ratio', 0.0):.2%}")

            # Breakdown por clase
            tracks_by_class = stats.get('tracks_by_class', {})
            if tracks_by_class:
                logger.info("   Tracks by class:")
                for class_name, count in tracks_by_class.items():
                    logger.info(f"     - {class_name}: {count}")

        except Exception as e:
            logger.error(f"❌ Error obteniendo estadísticas de estabilización: {e}", exc_info=True)

    def run(self):
        """Ejecuta el pipeline"""
        if not self.setup():
            logger.error("❌ Setup falló")
            return
        
        logger.info("\n" + "="*70)
        logger.info("🎬 InferencePipeline con MQTT activo y corriendo")
        logger.info("="*70)
        logger.info(f"📡 Control Topic: {self.config.CONTROL_COMMAND_TOPIC}")
        logger.info(f"📊 Data Topic: {self.config.DATA_TOPIC}")
        logger.info(f"▶️  Estado: RUNNING")
        logger.info("\n💡 Comandos MQTT disponibles:")
        logger.info('   PAUSE:   {"command": "pause"}   - Pausa el procesamiento')
        logger.info('   RESUME:  {"command": "resume"}  - Reanuda el procesamiento')
        logger.info('   STOP:    {"command": "stop"}    - Detiene y finaliza')
        logger.info('   STATUS:  {"command": "status"}  - Consulta estado actual')
        logger.info('   METRICS: {"command": "metrics"} - Publica métricas del pipeline')
        if self.config.ROI_MODE == 'adaptive':
            logger.info('   TOGGLE_CROP: {"command": "toggle_crop"} - Toggle adaptive ROI crop (solo modo adaptive)')
        if self.config.STABILIZATION_MODE != 'none':
            logger.info('   STABILIZATION_STATS: {"command": "stabilization_stats"} - Estadísticas de detección estabilizada')
        logger.info("\n⌨️  Presiona Ctrl+C para salir")
        logger.info("="*70 + "\n")
        
        # Configurar signal handler
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        # Esperar a que se detenga (con timeout para evitar bloqueos)
        try:
            while not self.shutdown_event.is_set():
                self.shutdown_event.wait(timeout=1.0)
        except KeyboardInterrupt:
            logger.info("\n\n⚠️ Interrupción forzada...")
            self.shutdown_event.set()

        # Cleanup
        self.cleanup()
    
    def _signal_handler(self, signum, frame):
        """Handler para señales (Ctrl+C)"""
        logger.info("\n\n⚠️ Señal de terminación recibida...")
        self.shutdown_event.set()
        # Forzar terminación del pipeline inmediatamente
        if self.pipeline and self.is_running:
            logger.info("🛑 Deteniendo pipeline...")
            try:
                self.pipeline.terminate()
                self.is_running = False
            except Exception as e:
                logger.error(f"Error deteniendo pipeline: {e}")
    
    def cleanup(self):
        """Limpia recursos al finalizar"""
        logger.info("🧹 Limpiando recursos...")

        # Solo terminar pipeline si aún está corriendo
        if self.pipeline and self.is_running:
            try:
                self.pipeline.terminate()
                self.is_running = False
                logger.info("✅ Pipeline detenido")

                # Esperar a que los threads del pipeline terminen (con timeout)
                logger.debug("⏳ Esperando a que terminen los threads del pipeline...")
                try:
                    self.pipeline.join(timeout=3.0)
                    logger.debug("✅ Threads del pipeline terminados")
                except Exception as e:
                    logger.warning(f"⚠️ Timeout esperando pipeline.join(): {e}")
            except Exception as e:
                logger.error(f"❌ Error deteniendo pipeline: {e}")

        if self.control_plane:
            self.control_plane.disconnect()
            logger.info("✅ Control Plane desconectado")

        if self.data_plane:
            stats = self.data_plane.get_stats()
            logger.info(f"📊 Data Plane stats: {stats}")
            self.data_plane.disconnect()
            logger.info("✅ Data Plane desconectado")

        logger.info("👋 Hasta luego!")

        # Forzar salida inmediata del programa (mata todos los threads)
        # Usamos os._exit() en lugar de sys.exit() para bypass cleanup de Python
        # y matar threads non-daemon del pipeline inmediatamente
        logger.debug("🚪 Saliendo del programa (forzando terminación)...")
        import os
        os._exit(0)


# ============================================================================
# MAIN
# ============================================================================
def main():
    """Punto de entrada principal"""
    # Cargar configuración
    config = PipelineConfig()

    # Configurar logging basado en config
    logging.basicConfig(
        level=getattr(logging, config.LOG_LEVEL.upper()),
        format=config.LOG_FORMAT
    )

    global logger
    logger = logging.getLogger(__name__)

    # Reducir verbosidad de paho-mqtt
    logging.getLogger('paho').setLevel(getattr(logging, config.PAHO_LOG_LEVEL.upper()))

    # Crear y ejecutar controller
    controller = InferencePipelineController(config)

    try:
        controller.run()
    except Exception as e:
        logger.error(f"❌ Error fatal: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()

