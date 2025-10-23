"""
Pipeline Builder
================

Builder pattern para construir InferencePipeline con todas sus dependencias.

Responsabilidad:
- Orquestar factories para construir componentes
- Construir inference handler
- Construir sinks
- Construir pipeline (standard o custom logic)
- Wrappear con stabilization si necesario

Diseño: Complejidad por diseño
- Builder orquesta, Factories construyen
- Controller solo usa Builder (no conoce detalles)
- Toda la lógica de construcción centralizada aquí
"""
from functools import partial
from typing import Optional, Tuple, List, Callable, Any, Union, TYPE_CHECKING
import logging

# Type-only imports (no circular import en runtime)
if TYPE_CHECKING:
    from ..data import MQTTDataPlane
    from ..inference.roi import ROIState, FixedROIState

# Lazy loading inference con disable automático
from ..inference.loader import InferenceLoader

inference_module = InferenceLoader.get_inference()
InferencePipeline = inference_module.InferencePipeline

# Otros imports de inference
from inference.core.interfaces.stream.sinks import multi_sink
from inference.core.interfaces.stream.watchdog import BasePipelineWatchDog

from ..config import PipelineConfig
from ..inference.factories import InferenceHandlerFactory, StrategyFactory
from ..inference.handlers.base import BaseInferenceHandler
from .factories import SinkFactory

logger = logging.getLogger(__name__)


class PipelineBuilder:
    """
    Builder para InferencePipeline.

    Encapsula toda la lógica de construcción que antes estaba en
    InferencePipelineController.setup().

    Usage:
        builder = PipelineBuilder(config)

        # Build components
        handler, roi_state = builder.build_inference_handler()
        sinks = builder.build_sinks(data_plane, roi_state, handler)

        # Wrap con stabilization si necesario
        if config.STABILIZATION_MODE != 'none':
            sinks = builder.wrap_sinks_with_stabilization(sinks)

        # Build pipeline
        pipeline = builder.build_pipeline(handler, sinks, watchdog, status_handlers)
    """

    def __init__(self, config: PipelineConfig):
        """
        Args:
            config: PipelineConfig con toda la configuración
        """
        self.config = config
        self.stabilizer = None  # Se crea en wrap_sinks_with_stabilization()

    def build_inference_handler(
        self
    ) -> Tuple[BaseInferenceHandler, Optional[Union['ROIState', 'FixedROIState']]]:
        """
        Construye inference handler según configuración.

        Delega a InferenceHandlerFactory.

        Returns:
            (handler, roi_state)
                - handler: BaseInferenceHandler
                - roi_state: ROIState | FixedROIState | None
        """
        logger.info(
            "Building inference handler",
            extra={"component": "builder", "event": "handler_build_start"}
        )
        return InferenceHandlerFactory.create(self.config)

    def build_sinks(
        self,
        data_plane: 'MQTTDataPlane',
        roi_state: Optional[Union['ROIState', 'FixedROIState']] = None,
        inference_handler: Optional[BaseInferenceHandler] = None,
    ) -> List[Callable]:
        """
        Construye sinks según configuración.

        Delega a SinkFactory.

        Args:
            data_plane: MQTTDataPlane (type-safe via TYPE_CHECKING)
            roi_state: ROIState | FixedROIState | None
            inference_handler: BaseInferenceHandler | None

        Returns:
            Lista de sinks para multi_sink()
        """
        logger.info(
            "Building sinks",
            extra={"component": "builder", "event": "sinks_build_start"}
        )
        return SinkFactory.create_sinks(
            config=self.config,
            data_plane=data_plane,
            roi_state=roi_state,
            inference_handler=inference_handler,
        )

    def wrap_sinks_with_stabilization(self, sinks: List[Callable]) -> List[Callable]:
        """
        Wrappea MQTT sink con stabilization si está habilitado.

        Args:
            sinks: Lista de sinks (NO se modifica)

        Returns:
            NUEVA lista con MQTT sink wrappeado

        Side effects:
            - Setea self.stabilizer si stabilization habilitado

        Note:
            Functional purity: No modifica input, retorna nuevo array.
            Explicit over implicit: Busca MQTT sink por __name__, no por posición.

        Raises:
            ValueError: Si stabilization está habilitado pero no hay MQTT sink
        """
        if self.config.STABILIZATION_MODE == 'none':
            logger.info(
                "Stabilization wrapper skipped",
                extra={
                    "component": "builder",
                    "event": "stabilization_skipped",
                    "reason": "mode=none"
                }
            )
            self.stabilizer = None
            return sinks

        logger.info(
            "Wrapping sink with stabilization",
            extra={"component": "builder", "event": "stabilization_wrap_start"}
        )

        from ..inference.stabilization import create_stabilization_sink

        # Crear stabilizer usando factory
        self.stabilizer = StrategyFactory.create_stabilization_strategy(self.config)

        # Buscar MQTT sink explícitamente por __name__ (no asumir posición)
        mqtt_sink_idx = None
        for i, sink in enumerate(sinks):
            if hasattr(sink, '__name__') and sink.__name__ == 'mqtt_sink':
                mqtt_sink_idx = i
                break

        if mqtt_sink_idx is None:
            raise ValueError(
                "No MQTT sink found to wrap with stabilization. "
                "Ensure SinkFactory creates MQTT sink with __name__ = 'mqtt_sink'."
            )

        logger.info(
            f"Found MQTT sink at index {mqtt_sink_idx}",
            extra={
                "component": "builder",
                "event": "mqtt_sink_found",
                "index": mqtt_sink_idx
            }
        )

        mqtt_sink = sinks[mqtt_sink_idx]
        stabilized_sink = create_stabilization_sink(
            stabilizer=self.stabilizer,
            downstream_sink=mqtt_sink,
        )

        # Reconstruir lista con MQTT sink wrappeado (immutable operation)
        new_sinks = (
            sinks[:mqtt_sink_idx] +
            [stabilized_sink] +
            sinks[mqtt_sink_idx+1:]
        )

        logger.info(
            "Stabilization wrapper complete",
            extra={
                "component": "builder",
                "event": "stabilization_wrap_complete",
                "stabilization_mode": self.config.STABILIZATION_MODE,
                "mqtt_sink_index": mqtt_sink_idx
            }
        )
        return new_sinks

    def build_pipeline(
        self,
        inference_handler: BaseInferenceHandler,
        sinks: List[Callable],
        watchdog: BasePipelineWatchDog,
        status_update_handlers: List[Callable],
    ) -> InferencePipeline:
        """
        Construye InferencePipeline (standard o custom logic).

        Args:
            inference_handler: Handler de inferencia
            sinks: Lista de sinks (ya wrappeados con stabilization si corresponde)
            watchdog: Watchdog para métricas
            status_update_handlers: Handlers de status updates

        Returns:
            InferencePipeline configurado
        """
        logger.info(
            "Building InferencePipeline",
            extra={"component": "builder", "event": "pipeline_build_start"}
        )

        # Composición de sinks
        on_prediction = partial(multi_sink, sinks=sinks)

        # Standard vs Custom Logic
        if self.config.ROI_MODE == 'none':
            # ============================================================
            # STANDARD PIPELINE (model_id based)
            # ============================================================
            logger.info(
                "Creating standard pipeline",
                extra={
                    "component": "builder",
                    "event": "pipeline_created",
                    "pipeline_type": "standard",
                    "model_id": self.config.MODEL_ID
                }
            )
            pipeline = InferencePipeline.init(
                max_fps=self.config.MAX_FPS,
                model_id=self.config.MODEL_ID,
                video_reference=self.config.RTSP_URL,
                on_prediction=on_prediction,
                api_key=self.config.API_KEY,
                watchdog=watchdog,
                status_update_handlers=status_update_handlers,
            )

        else:
            # ============================================================
            # CUSTOM LOGIC PIPELINE (ROI based)
            # ============================================================
            logger.info(
                "Creating custom logic pipeline",
                extra={
                    "component": "builder",
                    "event": "pipeline_created",
                    "pipeline_type": "custom_logic",
                    "roi_mode": self.config.ROI_MODE
                }
            )
            pipeline = InferencePipeline.init_with_custom_logic(
                video_reference=self.config.RTSP_URL,
                on_video_frame=inference_handler,
                on_prediction=on_prediction,
                max_fps=self.config.MAX_FPS,
                watchdog=watchdog,
                status_update_handlers=status_update_handlers,
            )

        logger.info(
            "Pipeline build complete",
            extra={"component": "builder", "event": "pipeline_build_complete"}
        )
        return pipeline
