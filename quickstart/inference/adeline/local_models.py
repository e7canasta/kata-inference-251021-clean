"""
Local Model Adapter - ONNX Models with Ultralytics
===================================================

Adaptador para usar modelos YOLO locales (ONNX) con Ultralytics,
manteniendo compatibilidad con el pipeline existente.

Features:
- Carga modelos ONNX locales
- Interfaz compatible con inference de Roboflow
- Conversión de resultados usando supervision
- Performance optimizada con ONNX

Usage:
    model = LocalONNXModel("models/yolov11n-320.onnx")
    predictions = process_frame_with_local_model(
        [video_frame],
        model=model,
        inference_config=config
    )
"""

from typing import List, Dict, Any, Optional
from pathlib import Path
import logging

import numpy as np
import supervision as sv
from ultralytics import YOLO
from inference.core.interfaces.camera.entities import VideoFrame

logger = logging.getLogger(__name__)


# ============================================================================
# Local Model Wrapper
# ============================================================================

class LocalONNXModel:
    """
    Wrapper para modelos YOLO locales (ONNX) usando Ultralytics.

    Mantiene interfaz similar a modelos de Roboflow para compatibilidad
    con el código existente de adaptive_roi.py

    Attributes:
        model: Instancia de YOLO de Ultralytics
        model_path: Path al archivo ONNX
        imgsz: Tamaño de imagen para inferencia
    """

    def __init__(self, model_path: str, imgsz: int = 320):
        """
        Carga modelo ONNX local.

        Args:
            model_path: Path al archivo .onnx
            imgsz: Tamaño de imagen (debe coincidir con el exportado)

        Raises:
            FileNotFoundError: Si el modelo no existe
            ValueError: Si el modelo no es válido
        """
        self.model_path = Path(model_path)

        if not self.model_path.exists():
            raise FileNotFoundError(f"Modelo no encontrado: {model_path}")

        if self.model_path.suffix != ".onnx":
            raise ValueError(f"Solo se soportan modelos ONNX, recibido: {self.model_path.suffix}")

        logger.info(f"🔧 Cargando modelo local: {self.model_path.name}")

        # Validación: detectar mismatch común entre nombre de archivo y imgsz
        # Ejemplo: yolo11n-640.onnx pero imgsz=320
        if '-' in self.model_path.stem:
            parts = self.model_path.stem.split('-')
            if len(parts) >= 2 and parts[-1].isdigit():
                model_size = int(parts[-1])
                if model_size != imgsz:
                    logger.warning(
                        f"⚠️ MISMATCH DETECTADO: Modelo '{self.model_path.name}' parece ser {model_size}×{model_size}, "
                        f"pero imgsz configurado es {imgsz}. "
                        f"Esto causará RuntimeError en ONNX Runtime."
                    )
                    logger.warning(
                        f"💡 Solución: Cambiar 'models.imgsz: {model_size}' en config.yaml "
                        f"o usar modelo 'yolo11n-{imgsz}.onnx'"
                    )

        try:
            self.model = YOLO(str(self.model_path))
            self.imgsz = imgsz
            logger.info(f"✅ Modelo cargado: {self.model_path.name} (imgsz={imgsz})")

        except Exception as e:
            logger.error(f"❌ Error cargando modelo: {e}")

            # Mensaje de ayuda si es RuntimeError de dimensiones
            if "Got invalid dimensions" in str(e) or "Expected:" in str(e):
                logger.error(
                    f"💡 Este error ocurre cuando el tamaño de imagen (imgsz={imgsz}) no coincide "
                    f"con el tamaño con el que se exportó el modelo ONNX."
                )
                logger.error(
                    f"   Solución: Verificar que 'models.imgsz' en config.yaml coincida con el modelo."
                )

            raise ValueError(f"Error cargando modelo ONNX: {e}") from e

    def __call__(
        self,
        image: np.ndarray,
        conf: float = 0.25,
        iou: float = 0.45,
        **kwargs
    ) -> sv.Detections:
        """
        Ejecuta inferencia sobre una imagen.

        Args:
            image: Imagen BGR (formato OpenCV/numpy)
            conf: Confidence threshold
            iou: IOU threshold para NMS
            **kwargs: Argumentos adicionales para YOLO

        Returns:
            sv.Detections con los resultados
        """
        try:
            # Inferencia con Ultralytics
            results = self.model.predict(
                image,
                conf=conf,
                iou=iou,
                imgsz=self.imgsz,
                verbose=False,  # Silenciar logs de Ultralytics
                **kwargs
            )

            # Convertir a supervision Detections
            # Ultralytics devuelve una lista de Results, tomamos el primero
            if len(results) > 0:
                detections = sv.Detections.from_ultralytics(results[0])
            else:
                detections = sv.Detections.empty()

            return detections

        except RuntimeError as e:
            # Error común: mismatch entre imgsz y modelo ONNX
            if "Got invalid dimensions" in str(e) or "Expected:" in str(e):
                logger.error(
                    f"❌ ONNX Runtime Error: El modelo espera un tamaño diferente de imagen. "
                    f"Configurado: {self.imgsz}×{self.imgsz}, Imagen recibida: {image.shape}"
                )
                logger.error(
                    f"💡 Solución: Cambiar 'models.imgsz' en config.yaml para coincidir con el modelo ONNX."
                )
                logger.error(f"   Modelo: {self.model_path.name}")
            raise

    @property
    def model_id(self) -> str:
        """ID del modelo para logging/monitoring"""
        return self.model_path.stem


# ============================================================================
# Frame Processing Function (compatible con adaptive_roi.py)
# ============================================================================

def process_frame_with_local_model(
    video_frames: List[VideoFrame],
    model: LocalONNXModel,
    inference_config,
) -> List[Dict[str, Any]]:
    """
    Procesa frames con modelo local ONNX.

    Esta función es compatible con adaptive_roi_inference() - puede reemplazar
    el uso de default_process_frame() manteniendo la misma interfaz.

    Args:
        video_frames: Lista de frames a procesar
        model: LocalONNXModel instance
        inference_config: Configuración (conf, iou, etc.)

    Returns:
        Lista de predictions en formato compatible con Roboflow
        (dict con 'predictions', 'image', metadata)
    """
    results = []

    # Extraer config (con defaults si no existen)
    conf = getattr(inference_config, 'confidence', 0.25)
    iou = getattr(inference_config, 'iou_threshold', 0.45)

    for video_frame in video_frames:
        # Inferencia con modelo local
        detections = model(
            image=video_frame.image,
            conf=conf,
            iou=iou,
        )

        # Convertir sv.Detections a formato Roboflow-compatible
        prediction = convert_sv_detections_to_roboflow_format(
            detections=detections,
            image_shape=video_frame.image.shape,
        )

        results.append(prediction)

    return results


def convert_sv_detections_to_roboflow_format(
    detections: sv.Detections,
    image_shape: tuple,
) -> Dict[str, Any]:
    """
    Convierte sv.Detections al formato esperado por el resto del pipeline.

    Formato Roboflow esperado:
    {
        'predictions': [
            {
                'x': center_x,
                'y': center_y,
                'width': w,
                'height': h,
                'confidence': conf,
                'class': class_name,
                'class_id': class_id,
            },
            ...
        ],
        'image': {'width': w, 'height': h},
    }

    Args:
        detections: sv.Detections de Ultralytics
        image_shape: (height, width, channels)

    Returns:
        Dict con formato Roboflow
    """
    h, w = image_shape[:2]

    predictions_list = []

    # Convertir cada detección
    for i in range(len(detections)):
        # Extraer bbox en formato xyxy
        x1, y1, x2, y2 = detections.xyxy[i]

        # Convertir a formato center x,y + width,height
        bbox_width = x2 - x1
        bbox_height = y2 - y1
        center_x = x1 + bbox_width / 2
        center_y = y1 + bbox_height / 2

        # Extraer class_id y confidence
        class_id = int(detections.class_id[i]) if detections.class_id is not None else 0
        confidence = float(detections.confidence[i]) if detections.confidence is not None else 1.0

        # Class name (si está disponible)
        # supervision guarda class names en data['class_name'] si están disponibles
        class_name = str(class_id)  # Default: usar class_id como string
        if hasattr(detections, 'data') and 'class_name' in detections.data:
            class_name = detections.data['class_name'][i]

        prediction = {
            'x': float(center_x),
            'y': float(center_y),
            'width': float(bbox_width),
            'height': float(bbox_height),
            'confidence': confidence,
            'class': class_name,
            'class_id': class_id,
        }

        predictions_list.append(prediction)

    return {
        'predictions': predictions_list,
        'image': {
            'width': w,
            'height': h,
        },
    }


# ============================================================================
# Model Factory (para integración con config.yaml)
# ============================================================================

def get_model_from_config(
    use_local: bool,
    local_path: Optional[str] = None,
    model_id: Optional[str] = None,
    api_key: Optional[str] = None,
    imgsz: int = 320,
):
    """
    Factory para crear modelo según configuración.

    Args:
        use_local: Si usar modelo local (True) o Roboflow (False)
        local_path: Path al modelo ONNX local (requerido si use_local=True)
        model_id: ID del modelo Roboflow (requerido si use_local=False)
        api_key: API key de Roboflow (requerido si use_local=False)
        imgsz: Tamaño de imagen para modelos locales

    Returns:
        LocalONNXModel o modelo de Roboflow

    Raises:
        ValueError: Si la configuración es inválida
    """
    if use_local:
        if not local_path:
            raise ValueError("local_path es requerido cuando use_local=True")

        logger.info(f"🔧 Usando modelo local: {local_path}")
        return LocalONNXModel(model_path=local_path, imgsz=imgsz)

    else:
        if not model_id or not api_key:
            raise ValueError("model_id y api_key son requeridos cuando use_local=False")

        logger.info(f"🌐 Usando modelo Roboflow: {model_id}")
        from inference.models.utils import get_model
        return get_model(model_id=model_id, api_key=api_key)


def get_process_frame_function(model):
    """
    Retorna la función de procesamiento apropiada según el tipo de modelo.

    Args:
        model: LocalONNXModel o modelo de Roboflow

    Returns:
        Función para procesar frames
    """
    if isinstance(model, LocalONNXModel):
        return process_frame_with_local_model
    else:
        # Modelo de Roboflow - usar función estándar
        from inference.core.interfaces.stream.model_handlers.roboflow_models import (
            default_process_frame,
        )
        return default_process_frame
