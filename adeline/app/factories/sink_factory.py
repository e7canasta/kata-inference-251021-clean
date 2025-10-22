"""
Sink Factory
============

Factory para crear y componer sinks del pipeline.

Diseño: Registry-based desacoplamiento
- Factory usa SinkRegistry internamente
- Sinks desacoplados vía factory functions
- Priority explícito, extensible

Filosofía: "Complejidad por diseño"
- Desacoplamiento sin plugin system completo
- Evolutivo: registry crece si necesitamos más features
"""
from functools import partial
from typing import List, Callable, Optional
import logging

from ..sinks import SinkRegistry

logger = logging.getLogger(__name__)


# ============================================================================
# Sink Factory Functions
# ============================================================================

def _create_mqtt_sink_factory(config, data_plane, **kwargs):
    """Factory para MQTT sink (siempre presente)."""
    from ...data import create_mqtt_sink
    sink = create_mqtt_sink(data_plane)
    logger.info("✅ MQTT sink added")
    return sink


def _create_roi_update_sink_factory(config, roi_state, **kwargs):
    """Factory para ROI update sink (solo adaptive mode)."""
    if config.ROI_MODE != 'adaptive' or roi_state is None:
        return None  # Skip

    from ...inference.roi import roi_update_sink
    sink = partial(roi_update_sink, roi_state=roi_state)
    logger.info("✅ ROI update sink added (adaptive mode)")
    return sink


def _create_visualization_sink_factory(config, roi_state, inference_handler, **kwargs):
    """Factory para visualization sink (si habilitado)."""
    if not config.ENABLE_VISUALIZATION:
        return None  # Skip

    from ...visualization import create_visualization_sink

    # Window name según estrategia
    if config.ROI_MODE == 'none':
        window_name = "Inference Pipeline (Standard)"
    else:
        window_name = f"Inference Pipeline ({config.ROI_MODE.capitalize()} ROI)"

    sink = create_visualization_sink(
        roi_state=roi_state,
        inference_handler=inference_handler,
        display_stats=config.DISPLAY_STATISTICS,
        window_name=window_name,
    )
    logger.info(f"✅ Visualization sink added: {window_name}")
    return sink


class SinkFactory:
    """
    Factory para crear sinks usando SinkRegistry.

    Diseño: Registry-based
    - Usa SinkRegistry internamente para desacoplamiento
    - API backward compatible (create_sinks método estático)
    - Priority explícito: MQTT(1) → ROI(50) → Viz(100)

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
        Crea lista de sinks según configuración usando registry.

        Args:
            config: PipelineConfig
            data_plane: MQTTDataPlane para publicar
            roi_state: ROIState | FixedROIState | None
            inference_handler: BaseInferenceHandler | None

        Returns:
            Lista de sinks para multi_sink()

        Note:
            Usa SinkRegistry internamente para desacoplamiento.
            Factory functions retornan None si sink no aplica.
        """
        # Crear registry y registrar sinks con priority
        registry = SinkRegistry()

        registry.register(
            name='mqtt',
            factory=_create_mqtt_sink_factory,
            priority=1  # Primero (stabilization wrappea este)
        )

        registry.register(
            name='roi_update',
            factory=_create_roi_update_sink_factory,
            priority=50  # Medio
        )

        registry.register(
            name='visualization',
            factory=_create_visualization_sink_factory,
            priority=100  # Último (más lento)
        )

        # Crear todos los sinks
        sinks = registry.create_all(
            config=config,
            data_plane=data_plane,
            roi_state=roi_state,
            inference_handler=inference_handler,
        )

        return sinks
