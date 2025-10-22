"""
Inference Handler Factory
=========================

Factory pattern para crear inference handlers según configuración.

Unifica lógica de selección ROI + creación de modelo que actualmente
está en InferencePipelineController.setup() (líneas 131-211).

Diseño: Complejidad por diseño
- Factory centraliza decisiones de construcción
- Validación delegada a ROI factory (validate_and_create_roi_strategy)
- Controller solo orquesta, no construye
"""
from typing import Optional, Tuple, Any
import logging

from ..handlers.base import BaseInferenceHandler
from ..handlers.standard import StandardInferenceHandler
from ..roi import (
    AdaptiveInferenceHandler,
    FixedROIInferenceHandler,
    ROIStrategyConfig,
    validate_and_create_roi_strategy,
)
from ..models import get_model_from_config, get_process_frame_function
from inference.core.interfaces.stream.entities import ModelConfig

logger = logging.getLogger(__name__)


class InferenceHandlerFactory:
    """
    Factory para crear inference handlers.

    Responsabilidad:
    - Validar modo ROI (none, adaptive, fixed)
    - Crear ROI state si necesario
    - Crear modelo (local ONNX o Roboflow)
    - Construir handler apropiado

    Returns:
        tuple: (handler, roi_state)
            - handler: BaseInferenceHandler (Standard/Adaptive/Fixed)
            - roi_state: ROIState | FixedROIState | None
    """

    @staticmethod
    def create(config: Any) -> Tuple[BaseInferenceHandler, Optional[Any]]:
        """
        Crea inference handler según configuración.

        Args:
            config: PipelineConfig con toda la configuración

        Returns:
            (handler, roi_state)

        Raises:
            ValueError: Si ROI mode es inválido

        Note:
            Lógica extraída de InferencePipelineController.setup()
            líneas 131-211 (modo custom logic).
        """
        roi_mode = config.ROI_MODE.lower()

        # ====================================================================
        # Standard Pipeline (sin custom logic)
        # ====================================================================
        if roi_mode == 'none':
            logger.info("📦 InferenceHandler: STANDARD (no ROI)")
            handler = StandardInferenceHandler()
            return handler, None

        # ====================================================================
        # Custom Logic con ROI (adaptive o fixed)
        # ====================================================================
        logger.info(f"🔧 InferenceHandler: {roi_mode.upper()} ROI")

        # 1. Crear ROI state (valida config y construye)
        roi_config = ROIStrategyConfig(
            mode=roi_mode,
            # Adaptive params
            adaptive_margin=config.CROP_MARGIN,
            adaptive_smoothing=config.CROP_SMOOTHING,
            adaptive_min_roi_multiple=config.CROP_MIN_ROI_MULTIPLE,
            adaptive_max_roi_multiple=config.CROP_MAX_ROI_MULTIPLE,
            adaptive_show_statistics=config.CROP_SHOW_STATISTICS,
            adaptive_resize_to_model=config.ADAPTIVE_RESIZE_TO_MODEL,
            # Fixed params
            fixed_x_min=config.FIXED_X_MIN,
            fixed_y_min=config.FIXED_Y_MIN,
            fixed_x_max=config.FIXED_X_MAX,
            fixed_y_max=config.FIXED_Y_MAX,
            fixed_show_overlay=config.FIXED_SHOW_OVERLAY,
            fixed_resize_to_model=config.FIXED_RESIZE_TO_MODEL,
            # Model
            imgsz=config.MODEL_IMGSZ,
        )

        roi_state = validate_and_create_roi_strategy(
            mode=roi_mode,
            config=roi_config,
        )

        # 2. Crear modelo (local ONNX o Roboflow según config)
        model = get_model_from_config(
            use_local=config.USE_LOCAL_MODEL,
            local_path=config.LOCAL_MODEL_PATH,
            model_id=config.MODEL_ID,
            api_key=config.API_KEY,
            imgsz=config.MODEL_IMGSZ,
        )

        # 3. Configuración de inferencia
        inference_config = ModelConfig.init(
            confidence=config.MODEL_CONFIDENCE,
            iou_threshold=config.MODEL_IOU_THRESHOLD,
        )

        # 4. Process frame function (según tipo de modelo)
        process_frame_fn = get_process_frame_function(model)

        # 5. Crear handler apropiado según modo ROI
        if roi_mode == 'adaptive':
            logger.info("🔄 Creating AdaptiveInferenceHandler (dynamic ROI)")
            handler = AdaptiveInferenceHandler(
                model=model,
                inference_config=inference_config,
                roi_state=roi_state,
                process_frame_fn=process_frame_fn,
                show_statistics=config.CROP_SHOW_STATISTICS,
            )

        elif roi_mode == 'fixed':
            logger.info("📍 Creating FixedROIInferenceHandler (static ROI)")
            handler = FixedROIInferenceHandler(
                model=model,
                inference_config=inference_config,
                roi_state=roi_state,
                process_frame_fn=process_frame_fn,
                show_statistics=config.CROP_SHOW_STATISTICS,
            )

        else:
            raise ValueError(
                f"Invalid ROI mode: '{roi_mode}'. "
                f"Must be 'none', 'adaptive', or 'fixed'"
            )

        return handler, roi_state
