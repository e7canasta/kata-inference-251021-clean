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
# LAZY LOADING INFERENCE (con disable automático)
# ============================================================================
# InferenceLoader garantiza que disable_models_from_config() se ejecute
# ANTES de importar inference (enforced por diseño, no por comentarios)
from ..inference.loader import InferenceLoader

# Get inference module (disable automático)
inference_module = InferenceLoader.get_inference()
InferencePipeline = inference_module.InferencePipeline

# Otros imports de inference (estos NO necesitan lazy loading)
from inference.core.interfaces.stream.sinks import multi_sink
from inference.core.interfaces.camera.entities import StatusUpdate, UpdateSeverity
from inference.core.interfaces.stream.watchdog import BasePipelineWatchDog

# Internal imports (new package structure)
from ..control import MQTTControlPlane
from ..data import MQTTDataPlane
from ..config import PipelineConfig, AdelineConfig
from .builder import PipelineBuilder

# Pydantic validation
from pydantic import ValidationError

# Logger (será configurado en main() con config values)
logger = logging.getLogger(__name__)


# ============================================================================
# PIPELINE CONTROLLER
# ============================================================================
# Note: PipelineConfig ahora está en ../config.py

# ============================================================================
# PIPELINE CONTROLLER
# ============================================================================
class InferencePipelineController:
    """
    Controlador del pipeline con MQTT control y data plane.

    Responsabilidad: Orquestación y lifecycle management
    - Setup de componentes (delega construcción a Builder)
    - Lifecycle management (start/stop/pause/resume)
    - Signal handling (Ctrl+C)
    - Cleanup de recursos

    Diseño: Complejidad por diseño
    - Controller orquesta, no construye (delega a Builder)
    - SRP: Solo maneja lifecycle, no detalles de construcción
    """

    def __init__(self, config: PipelineConfig):
        self.config = config
        self.builder = PipelineBuilder(config)  # Builder para construcción

        # Componentes (serán creados por builder en setup)
        self.pipeline = None
        self.control_plane = None
        self.data_plane = None
        self.watchdog = BasePipelineWatchDog()  # Monitoreo de métricas

        # Estado (será seteado por builder)
        self.inference_handler = None
        self.roi_state = None
        self.stabilizer = None

        # Lifecycle
        self.shutdown_event = Event()
        self.is_running = False
        
    def setup(self):
        """
        Inicializa el pipeline y las conexiones MQTT.

        Responsabilidad: Orquestación
        - Setup de Data/Control Plane
        - Delega construcción a PipelineBuilder
        - Auto-inicia pipeline

        Returns:
            bool: True si setup exitoso, False si falla
        """
        logger.info("🚀 Inicializando InferencePipeline con MQTT...")

        # ====================================================================
        # 1. Configurar Data Plane (publicador de inferencias)
        # ====================================================================
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

        # Conectar watchdog para publicar métricas
        self.data_plane.set_watchdog(self.watchdog)

        # ====================================================================
        # 2. Build Inference Handler (DELEGADO A BUILDER)
        # ====================================================================
        self.inference_handler, self.roi_state = self.builder.build_inference_handler()

        # ====================================================================
        # 3. Build Sinks (DELEGADO A BUILDER)
        # ====================================================================
        sinks = self.builder.build_sinks(
            data_plane=self.data_plane,
            roi_state=self.roi_state,
            inference_handler=self.inference_handler,
        )

        # ====================================================================
        # 4. Wrap con Stabilization si necesario (DELEGADO A BUILDER)
        # ====================================================================
        if self.config.STABILIZATION_MODE != 'none':
            sinks = self.builder.wrap_sinks_with_stabilization(sinks)
            self.stabilizer = self.builder.stabilizer
        else:
            self.stabilizer = None

        # ====================================================================
        # 5. Build Pipeline (DELEGADO A BUILDER)
        # ====================================================================
        self.pipeline = self.builder.build_pipeline(
            inference_handler=self.inference_handler,
            sinks=sinks,
            watchdog=self.watchdog,
            status_update_handlers=[self._status_update_handler],
        )

        # ====================================================================
        # 6. Configurar Control Plane (receptor de comandos)
        # ====================================================================
        logger.info("🎮 Configurando Control Plane...")
        self.control_plane = MQTTControlPlane(
            broker_host=self.config.MQTT_BROKER,
            broker_port=self.config.MQTT_PORT,
            command_topic=self.config.CONTROL_COMMAND_TOPIC,
            status_topic=self.config.CONTROL_STATUS_TOPIC,
            username=self.config.MQTT_USERNAME,
            password=self.config.MQTT_PASSWORD,
        )

        # Configurar callbacks
        self._setup_control_callbacks()

        if not self.control_plane.connect(timeout=10):
            logger.error("❌ No se pudo conectar Control Plane")
            return False

        # ====================================================================
        # 7. Auto-iniciar el pipeline
        # ====================================================================
        logger.info("▶️ Iniciando pipeline automáticamente...")
        try:
            self.is_running = True
            self.pipeline.start()
            logger.info("✅ Pipeline iniciado y corriendo")
        except Exception as e:
            logger.error(f"❌ Error iniciando pipeline: {e}", exc_info=True)
            self.is_running = False
            return False

        logger.info("✅ Setup completado")
        return True

    def _setup_control_callbacks(self):
        """
        Registra comandos en CommandRegistry del Control Plane.

        Comandos condicionales basados en capabilities del handler.
        """
        registry = self.control_plane.command_registry

        # Comandos básicos (siempre disponibles)
        registry.register('pause', self._handle_pause, "Pausa el procesamiento")
        registry.register('resume', self._handle_resume, "Reanuda el procesamiento")
        registry.register('stop', self._handle_stop, "Detiene y finaliza el pipeline")
        registry.register('status', self._handle_status, "Consulta estado actual")
        registry.register('metrics', self._handle_metrics, "Publica métricas del pipeline")

        # Comando TOGGLE_CROP solo si handler soporta toggle
        if self.inference_handler and self.inference_handler.supports_toggle:
            registry.register('toggle_crop', self._handle_toggle_crop, "Toggle adaptive ROI crop")
            logger.info("✅ toggle_crop command registered (handler supports toggle)")

        # Comando STABILIZATION_STATS solo si stabilization habilitado
        if self.stabilizer is not None:
            registry.register('stabilization_stats', self._handle_stabilization_stats, "Estadísticas de estabilización")
            logger.info("✅ stabilization_stats command registered")
    
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

        # Publicar status
        self.control_plane.publish_status("stopped")

        # Siempre setear shutdown_event para terminar el programa
        logger.info("🛑 Finalizando servicio...")
        self.shutdown_event.set()
    
    def _handle_pause(self):
        """Callback para comando PAUSE - pausa temporalmente el procesamiento"""
        logger.info("⏸️ Comando PAUSE recibido")
        if self.is_running:
            try:
                self.pipeline.pause_stream()
                self.control_plane.publish_status("paused")
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
                self.control_plane.publish_status("running")
                logger.info("✅ Pipeline resumido")
            except Exception as e:
                logger.error(f"❌ Error resumiendo pipeline: {e}", exc_info=True)
        else:
            logger.warning("⚠️ Pipeline no está corriendo, no se puede resumir (usa STOP para terminar correctamente)")

    def _handle_status(self):
        """Callback para comando STATUS - publica estado actual"""
        logger.info("📋 Comando STATUS recibido")
        status = "running" if self.is_running else "stopped"
        self.control_plane.publish_status(status)

    def _handle_metrics(self):
        """Callback para comando METRICS - publica métricas del watchdog vía MQTT"""
        logger.info("📊 Comando METRICS recibido")
        try:
            self.data_plane.publish_metrics()
        except Exception as e:
            logger.error(f"❌ Error publicando métricas: {e}", exc_info=True)

    def _handle_toggle_crop(self):
        """
        Callback para comando TOGGLE_CROP.

        Usa métodos enable/disable del handler (encapsulación).
        """
        logger.info("🔲 Comando TOGGLE_CROP recibido")

        # Validación: handler debe soportar toggle
        if not self.inference_handler.supports_toggle:
            logger.warning(
                f"⚠️ Handler {self.inference_handler.__class__.__name__} "
                f"no soporta toggle dinámico"
            )
            return

        # Toggle usando métodos del handler
        if self.inference_handler.enabled:
            self.inference_handler.disable()  # Llama disable() que resetea ROI
        else:
            self.inference_handler.enable()

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
        """
        Limpia recursos al finalizar (mejorado).

        Cambios respecto a versión anterior:
        - Timeout aumentado de 3s a 10s para pipeline.join()
        - Manejo de errores con try/except en todos los disconnects
        - Eliminado os._exit(0) (deja que Python maneje salida normalmente)
        """
        logger.info("🧹 Limpiando recursos...")

        # 1. Terminar pipeline si está corriendo
        if self.pipeline and self.is_running:
            try:
                logger.info("🛑 Deteniendo pipeline...")
                self.pipeline.terminate()
                self.is_running = False

                # Esperar con timeout más largo (10s en lugar de 3s)
                logger.info("⏳ Esperando threads del pipeline (timeout 10s)...")
                self.pipeline.join(timeout=10.0)
                logger.info("✅ Pipeline detenido")

            except Exception as e:
                logger.error(f"❌ Error deteniendo pipeline: {e}")

        # 2. Desconectar Control Plane
        if self.control_plane:
            try:
                self.control_plane.disconnect()
                logger.info("✅ Control Plane desconectado")
            except Exception as e:
                logger.error(f"❌ Error desconectando Control Plane: {e}")

        # 3. Desconectar Data Plane
        if self.data_plane:
            try:
                stats = self.data_plane.get_stats()
                logger.info(f"📊 Data Plane stats: {stats}")
                self.data_plane.disconnect()
                logger.info("✅ Data Plane desconectado")
            except Exception as e:
                logger.error(f"❌ Error desconectando Data Plane: {e}")

        logger.info("👋 Hasta luego!")
        # Eliminado os._exit(0) - dejamos que Python maneje cleanup normalmente


# ============================================================================
# MAIN
# ============================================================================
def main():
    """Punto de entrada principal"""
    # Cargar configuración con validación Pydantic
    config_path = "config/adeline/config.yaml"

    try:
        # Intentar cargar desde YAML con validación
        if Path(config_path).exists():
            pydantic_config = AdelineConfig.from_yaml(config_path)
            print(f"✅ Config loaded and validated from {config_path}")
        else:
            # Usar defaults si no existe YAML
            pydantic_config = AdelineConfig()
            print(f"⚠️  Config file not found ({config_path}), using defaults")

        # Convertir a legacy config (backward compatibility)
        config = pydantic_config.to_legacy_config()

    except ValidationError as e:
        # Fail fast con mensaje claro
        print(f"❌ Invalid configuration:")
        for error in e.errors():
            field = " -> ".join(str(loc) for loc in error['loc'])
            print(f"   • {field}: {error['msg']}")
        print(f"\nPlease fix {config_path} and try again.")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error loading config: {e}")
        sys.exit(1)

    # Configurar logging basado en config
    logging.basicConfig(
        level=getattr(logging, config.LOG_LEVEL.upper()),
        format=config.LOG_FORMAT
    )

    global logger
    logger = logging.getLogger(__name__)
    logger.info("🔧 Adeline Inference Pipeline starting...")

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

