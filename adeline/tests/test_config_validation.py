"""
Config Validation Tests
=======================

Tests de validación de configuración con Pydantic.

Invariantes testeadas:
1. Valores por defecto son válidos
2. Validación de rangos (confidence, IoU, etc)
3. Validación de relaciones (persist_conf <= appear_conf)
4. Validación de bounds (x_min < x_max, etc)
"""
import pytest
from pydantic import ValidationError
from config.schemas import (
    AdelineConfig,
    ModelsSettings,
    HysteresisStabilizationSettings,
    FixedROISettings,
    AdaptiveROISettings,
)


@pytest.mark.unit
class TestModelsSettingsValidation:
    """Tests de validación de ModelsSettings"""

    def test_default_values_valid(self):
        """
        Invariante: Valores por defecto deben ser válidos.
        """
        settings = ModelsSettings()

        assert settings.use_local == False
        assert settings.imgsz == 320
        assert settings.confidence == 0.25

    def test_imgsz_must_be_multiple_of_32(self):
        """
        Invariante: imgsz debe ser múltiplo de 32 (YOLO requirement).
        """
        # Válido: múltiplo de 32
        settings = ModelsSettings(imgsz=320)
        assert settings.imgsz == 320

        settings = ModelsSettings(imgsz=640)
        assert settings.imgsz == 640

        # Inválido: no múltiplo de 32
        with pytest.raises(ValidationError) as exc_info:
            ModelsSettings(imgsz=300)

        assert 'multiple of 32' in str(exc_info.value).lower()

    def test_confidence_range_validation(self):
        """
        Invariante: confidence debe estar en [0.0, 1.0].
        """
        # Válido
        settings = ModelsSettings(confidence=0.5)
        assert settings.confidence == 0.5

        # Inválido: < 0.0
        with pytest.raises(ValidationError):
            ModelsSettings(confidence=-0.1)

        # Inválido: > 1.0
        with pytest.raises(ValidationError):
            ModelsSettings(confidence=1.5)

    def test_iou_threshold_range_validation(self):
        """
        Invariante: iou_threshold debe estar en [0.0, 1.0].
        """
        # Válido
        settings = ModelsSettings(iou_threshold=0.45)
        assert settings.iou_threshold == 0.45

        # Inválido: < 0.0
        with pytest.raises(ValidationError):
            ModelsSettings(iou_threshold=-0.1)

        # Inválido: > 1.0
        with pytest.raises(ValidationError):
            ModelsSettings(iou_threshold=1.5)


@pytest.mark.unit
class TestHysteresisValidation:
    """Tests de validación de HysteresisStabilizationSettings"""

    def test_persist_must_be_less_or_equal_appear(self):
        """
        Invariante CRÍTICO: persist_confidence <= appear_confidence.

        Hysteresis requiere umbral alto para aparecer, bajo para persistir.
        """
        # Válido: persist <= appear
        settings = HysteresisStabilizationSettings(
            appear_confidence=0.5,
            persist_confidence=0.3
        )
        assert settings.persist_confidence <= settings.appear_confidence

        # Inválido: persist > appear
        with pytest.raises(ValidationError) as exc_info:
            HysteresisStabilizationSettings(
                appear_confidence=0.3,
                persist_confidence=0.5  # Inválido
            )

        assert 'persist' in str(exc_info.value).lower()
        assert 'appear' in str(exc_info.value).lower()

    def test_hysteresis_range_validation(self):
        """
        Invariante: Ambos thresholds deben estar en [0.0, 1.0].
        """
        # Inválido: appear_conf > 1.0
        with pytest.raises(ValidationError):
            HysteresisStabilizationSettings(appear_confidence=1.5)

        # Inválido: persist_conf < 0.0
        with pytest.raises(ValidationError):
            HysteresisStabilizationSettings(persist_confidence=-0.1)


@pytest.mark.unit
class TestFixedROIValidation:
    """Tests de validación de FixedROISettings"""

    def test_x_min_must_be_less_than_x_max(self):
        """
        Invariante: x_min < x_max.
        """
        # Válido
        settings = FixedROISettings(x_min=0.2, x_max=0.8)
        assert settings.x_min < settings.x_max

        # Inválido: x_min >= x_max
        with pytest.raises(ValidationError) as exc_info:
            FixedROISettings(x_min=0.8, x_max=0.2)

        assert 'x_min' in str(exc_info.value).lower()
        assert 'x_max' in str(exc_info.value).lower()

    def test_y_min_must_be_less_than_y_max(self):
        """
        Invariante: y_min < y_max.
        """
        # Válido
        settings = FixedROISettings(y_min=0.2, y_max=0.8)
        assert settings.y_min < settings.y_max

        # Inválido: y_min >= y_max
        with pytest.raises(ValidationError) as exc_info:
            FixedROISettings(y_min=0.8, y_max=0.2)

        assert 'y_min' in str(exc_info.value).lower()
        assert 'y_max' in str(exc_info.value).lower()

    def test_coordinates_range_validation(self):
        """
        Invariante: Coordenadas normalizadas deben estar en [0.0, 1.0].
        """
        # Inválido: x_min < 0.0
        with pytest.raises(ValidationError):
            FixedROISettings(x_min=-0.1)

        # Inválido: x_max > 1.0
        with pytest.raises(ValidationError):
            FixedROISettings(x_max=1.5)


@pytest.mark.unit
class TestAdaptiveROIValidation:
    """Tests de validación de AdaptiveROISettings"""

    def test_min_roi_multiple_less_or_equal_max(self):
        """
        Invariante: min_roi_multiple <= max_roi_multiple.
        """
        # Válido
        settings = AdaptiveROISettings(min_roi_multiple=1, max_roi_multiple=4)
        assert settings.min_roi_multiple <= settings.max_roi_multiple

        # Inválido: min > max
        with pytest.raises(ValidationError) as exc_info:
            AdaptiveROISettings(min_roi_multiple=4, max_roi_multiple=1)

        assert 'min_roi_multiple' in str(exc_info.value).lower()
        assert 'max_roi_multiple' in str(exc_info.value).lower()

    def test_margin_range_validation(self):
        """
        Invariante: margin debe estar en [0.0, 1.0].
        """
        # Válido
        settings = AdaptiveROISettings(margin=0.2)
        assert settings.margin == 0.2

        # Inválido: < 0.0
        with pytest.raises(ValidationError):
            AdaptiveROISettings(margin=-0.1)

        # Inválido: > 1.0
        with pytest.raises(ValidationError):
            AdaptiveROISettings(margin=1.5)

    def test_smoothing_range_validation(self):
        """
        Invariante: smoothing debe estar en [0.0, 1.0].
        """
        # Válido
        settings = AdaptiveROISettings(smoothing=0.3)
        assert settings.smoothing == 0.3

        # Inválido
        with pytest.raises(ValidationError):
            AdaptiveROISettings(smoothing=-0.1)


@pytest.mark.unit
class TestAdelineConfigDefaults:
    """Tests de configuración completa con defaults"""

    def test_default_config_is_valid(self):
        """
        Invariante: Configuración por defecto debe ser válida.

        Esto garantiza que el sistema puede arrancar sin config.yaml.
        """
        config = AdelineConfig()

        # Verificar secciones principales
        assert config.pipeline is not None
        assert config.models is not None
        assert config.mqtt is not None
        assert config.detection_stabilization is not None
        assert config.roi_strategy is not None
        assert config.logging is not None

    def test_nested_defaults_valid(self):
        """
        Invariante: Defaults anidados son válidos.
        """
        config = AdelineConfig()

        # Pipeline
        assert config.pipeline.max_fps == 2
        assert 1 <= config.pipeline.max_fps <= 30

        # Models
        assert config.models.imgsz % 32 == 0

        # Stabilization
        assert config.detection_stabilization.hysteresis.persist_confidence <= \
               config.detection_stabilization.hysteresis.appear_confidence

        # ROI
        assert config.roi_strategy.adaptive.min_roi_multiple <= \
               config.roi_strategy.adaptive.max_roi_multiple


@pytest.mark.unit
class TestConfigFromDict:
    """Tests de construcción desde dict (YAML loading simulation)"""

    def test_construct_from_minimal_dict(self):
        """
        Propiedad: Config puede construirse con dict mínimo (usa defaults).
        """
        minimal_dict = {
            'pipeline': {
                'model_id': 'yolov11n-640'
            }
        }

        config = AdelineConfig(**minimal_dict)

        assert config.pipeline.model_id == 'yolov11n-640'
        # Otros valores usan defaults
        assert config.pipeline.max_fps == 2
        assert config.models.imgsz == 320

    def test_construct_from_complete_dict(self):
        """
        Propiedad: Config puede construirse con dict completo.
        """
        complete_dict = {
            'pipeline': {
                'rtsp_url': 'rtsp://test.com',
                'model_id': 'test-model',
                'max_fps': 5,
                'enable_visualization': True,
                'display_statistics': True,
            },
            'models': {
                'use_local': True,
                'local_path': 'models/test.onnx',
                'imgsz': 640,
                'confidence': 0.3,
                'iou_threshold': 0.5,
            },
            'mqtt': {
                'broker': {
                    'host': 'mqtt.test.com',
                    'port': 1883,
                },
                'topics': {
                    'control_commands': 'test/control',
                    'control_status': 'test/status',
                    'data': 'test/data',
                    'metrics': 'test/metrics',
                },
                'qos': {
                    'control': 1,
                    'data': 0,
                },
            },
            'detection_stabilization': {
                'mode': 'temporal',
                'temporal': {
                    'min_frames': 3,
                    'max_gap': 2,
                },
                'hysteresis': {
                    'appear_confidence': 0.5,
                    'persist_confidence': 0.3,
                },
                'iou': {
                    'threshold': 0.3,
                },
            },
            'roi_strategy': {
                'mode': 'adaptive',
                'adaptive': {
                    'margin': 0.2,
                    'smoothing': 0.3,
                    'min_roi_multiple': 1,
                    'max_roi_multiple': 4,
                    'show_statistics': True,
                    'resize_to_model': False,
                },
                'fixed': {
                    'x_min': 0.2,
                    'y_min': 0.2,
                    'x_max': 0.8,
                    'y_max': 0.8,
                    'show_overlay': True,
                    'resize_to_model': False,
                },
            },
            'logging': {
                'level': 'INFO',
                'format': '%(asctime)s - %(message)s',
                'paho_level': 'WARNING',
            },
            'models_disabled': {
                'disabled': ['PALIGEMMA', 'FLORENCE2'],
            },
        }

        config = AdelineConfig(**complete_dict)

        # Verificar algunos valores
        assert config.pipeline.max_fps == 5
        assert config.models.imgsz == 640
        assert config.mqtt.broker.host == 'mqtt.test.com'
        assert config.detection_stabilization.mode == 'temporal'
        assert config.roi_strategy.mode == 'adaptive'


@pytest.mark.unit
class TestConfigValidationErrors:
    """Tests de mensajes de error de validación"""

    def test_invalid_roi_mode_error(self):
        """
        Propiedad: Modo inválido produce error claro.
        """
        with pytest.raises(ValidationError) as exc_info:
            AdelineConfig(roi_strategy={'mode': 'invalid_mode'})

        error_str = str(exc_info.value)
        # Pydantic debe mencionar los valores válidos
        assert 'none' in error_str or 'adaptive' in error_str or 'fixed' in error_str

    def test_invalid_stabilization_mode_error(self):
        """
        Propiedad: Modo de stabilization inválido produce error claro.
        """
        with pytest.raises(ValidationError) as exc_info:
            AdelineConfig(detection_stabilization={'mode': 'invalid_mode'})

        error_str = str(exc_info.value)
        # Debe mencionar valores válidos
        assert 'none' in error_str or 'temporal' in error_str
