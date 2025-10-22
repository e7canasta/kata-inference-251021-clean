"""
Sink Factory
============

Factory para crear y componer sinks del pipeline.

Unifica lógica de creación de sinks que actualmente está en
InferencePipelineController.setup() (líneas 214-233).

Diseño: Complejidad por diseño
- Factory centraliza decisiones sobre qué sinks crear
- Controller solo orquesta, no decide detalles
"""
from functools import partial
from typing import List, Callable, Optional
import logging

logger = logging.getLogger(__name__)


class SinkFactory:
    """
    Factory para crear sinks.

    Responsabilidad:
    - Crear MQTT sink (siempre)
    - Crear ROI update sink (solo si adaptive)
    - Crear visualization sink (si habilitado)
    - Componer sinks en lista para multi_sink()

    Returns:
        Lista de callables para multi_sink()
    """

    @staticmethod
    def create_sinks(
        config,
        data_plane,
        roi_state=None,
        inference_handler=None,
    ) -> List[Callable]:
        """
        Crea lista de sinks según configuración.

        Args:
            config: PipelineConfig
            data_plane: MQTTDataPlane para publicar
            roi_state: ROIState | FixedROIState | None
            inference_handler: BaseInferenceHandler | None

        Returns:
            Lista de sinks para multi_sink()

        Note:
            Lógica extraída de InferencePipelineController.setup()
            líneas 214-233.
        """
        from ..data import create_mqtt_sink
        from ..visualization import create_visualization_sink
        from ..inference.roi import roi_update_sink

        sinks = []

        # 1. MQTT sink (siempre presente)
        mqtt_sink = create_mqtt_sink(data_plane)
        sinks.append(mqtt_sink)
        logger.info("✅ MQTT sink added")

        # 2. ROI update sink (solo para adaptive)
        if config.ROI_MODE == 'adaptive' and roi_state is not None:
            roi_sink = partial(roi_update_sink, roi_state=roi_state)
            sinks.append(roi_sink)
            logger.info("✅ ROI update sink added (adaptive mode)")

        # 3. Visualization sink (si habilitado)
        if config.ENABLE_VISUALIZATION:
            # Window name según estrategia
            if config.ROI_MODE == 'none':
                window_name = "Inference Pipeline (Standard)"
            else:
                window_name = f"Inference Pipeline ({config.ROI_MODE.capitalize()} ROI)"

            viz_sink = create_visualization_sink(
                roi_state=roi_state,
                inference_handler=inference_handler,
                display_stats=config.DISPLAY_STATISTICS,
                window_name=window_name,
            )
            sinks.append(viz_sink)
            logger.info(f"✅ Visualization sink added: {window_name}")

        logger.info(f"📊 Total sinks created: {len(sinks)}")
        return sinks
