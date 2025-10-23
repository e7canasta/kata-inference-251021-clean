"""
Environment Setup - MUST be imported first
===========================================

Configura variables de entorno para deshabilitar modelos ANTES de cualquier
import de inference. Este módulo debe importarse antes que cualquier módulo
interno de adeline que importe inference.

Design: Fail Fast - Si config.yaml no existe, usa defaults seguros.

NOTA: Al usar 'make run', las env vars se setean directamente en Makefile,
por lo que este código es redundante pero se mantiene para compatibilidad
con otros entry points (tests, scripts, etc).
"""
import os
import yaml
from pathlib import Path


def setup_model_environment() -> None:
    """
    Configura variables de entorno para deshabilitar modelos.

    Se ejecuta automáticamente al importar este módulo (ver bottom).
    Diseñado para ser idempotente (puede llamarse múltiples veces).
    """
    config_path = "config/adeline/config.yaml"
    config_file = Path(config_path)

    if config_file.exists():
        with open(config_file, 'r') as f:
            config = yaml.safe_load(f)

        models_disabled_cfg = config.get('models_disabled', {})
        disabled_models = models_disabled_cfg.get('disabled', [])

        for model in disabled_models:
            os.environ[f"{model}_ENABLED"] = "False"
    else:
        # Default: deshabilitar todos los modelos pesados
        default_disabled = [
            "PALIGEMMA", "FLORENCE2", "QWEN_2_5",
            "CORE_MODEL_SAM", "CORE_MODEL_SAM2", "CORE_MODEL_CLIP",
            "CORE_MODEL_GAZE", "SMOLVLM2", "DEPTH_ESTIMATION",
            "MOONDREAM2", "CORE_MODEL_TROCR", "CORE_MODEL_GROUNDINGDINO",
            "CORE_MODEL_YOLO_WORLD", "CORE_MODEL_PE",
        ]
        for model in default_disabled:
            os.environ[f"{model}_ENABLED"] = "False"


# ============================================================================
# EXECUTE IMMEDIATELY ON IMPORT
# ============================================================================
# Esto garantiza que las env vars estén configuradas ANTES de que
# cualquier módulo que importe inference sea cargado.
setup_model_environment()
