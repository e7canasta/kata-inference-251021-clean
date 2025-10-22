"""
Strategy Factory
================

Factory unificado para estrategias de stabilization.

Unifica lógica de creación que actualmente está en
InferencePipelineController.setup() (líneas 95-125).

Diseño: Complejidad por diseño
- Factory centraliza decisiones de estrategia
- Validación delegada a create_stabilization_strategy()
"""
from typing import Optional, Any
import logging

logger = logging.getLogger(__name__)


class StrategyFactory:
    """
    Factory unificado para estrategias.

    Actualmente solo maneja stabilization.
    En el futuro podría manejar otras estrategias (tracking, filtering, etc).

    Responsabilidad:
    - Crear estrategia de stabilization según config
    - Validar configuración
    - Retornar None si mode='none'

    Returns:
        BaseDetectionStabilizer | None
    """

    @staticmethod
    def create_stabilization_strategy(config: Any) -> Optional[Any]:
        """
        Crea estrategia de stabilization.

        Args:
            config: PipelineConfig

        Returns:
            BaseDetectionStabilizer | None

        Note:
            Lógica extraída de InferencePipelineController.setup()
            líneas 95-125 (detection stabilization wrapping).
        """
        from ..stabilization import (
            create_stabilization_strategy,
            StabilizationConfig,
        )

        if config.STABILIZATION_MODE == 'none':
            logger.info("🔲 Stabilization: NONE (baseline)")
            return None

        logger.info("🔧 Creating stabilization strategy...")

        # Crear configuración validada
        stab_config = StabilizationConfig(
            mode=config.STABILIZATION_MODE,
            temporal_min_frames=config.STABILIZATION_MIN_FRAMES,
            temporal_max_gap=config.STABILIZATION_MAX_GAP,
            hysteresis_appear_conf=config.STABILIZATION_APPEAR_CONF,
            hysteresis_persist_conf=config.STABILIZATION_PERSIST_CONF,
            iou_threshold=config.STABILIZATION_IOU_THRESHOLD,
        )

        # Factory: Crear stabilizer
        stabilizer = create_stabilization_strategy(stab_config)

        logger.info(f"✅ Stabilization: {config.STABILIZATION_MODE.upper()}")
        return stabilizer
