"""
Inference Module Loader
=======================

Lazy loader para módulo inference con model disabling automático.

PROBLEMA RESUELTO:
- Orden de imports frágil (disable_models_from_config debe ir ANTES de import inference)
- Refactors automáticos pueden romper el orden
- Comentarios tipo "# IMPORTANT: DISABLE MODELS BEFORE IMPORT" son frágiles

SOLUCIÓN:
- Lazy loading con disable automático
- Enforced por diseño, no por comentarios
- Orden de imports NO IMPORTA

Diseño: Complejidad por diseño
- Singleton pattern para garantizar una sola inicialización
- Lazy loading retrasa import hasta que se necesite
- Disable automático enforced por código, no por disciplina
"""
import logging
from typing import Optional, Any

logger = logging.getLogger(__name__)


class InferenceLoader:
    """
    Singleton lazy loader para módulo inference.

    Garantiza que disable_models_from_config() se ejecute
    ANTES de importar inference.

    Usage:
        # En lugar de:
        from inference import InferencePipeline  # ❌ Frágil

        # Usar:
        from adeline.inference.loader import InferenceLoader
        inference = InferenceLoader.get_inference()  # ✅ Safe
        InferencePipeline = inference.InferencePipeline
    """

    _inference_module: Optional[Any] = None
    _models_disabled: bool = False

    @classmethod
    def disable_models_from_config(cls, config_path: str = "config/adeline/config.yaml"):
        """
        Deshabilita modelos según config (solo si no se hizo antes).

        IMPORTANTE: Se ejecuta automáticamente en get_inference()
        No necesitas llamar esto manualmente.

        Args:
            config_path: Path al config.yaml (default: config/adeline/config.yaml)
        """
        if cls._models_disabled:
            logger.debug("Models already disabled, skipping")
            return

        # Importar función desde config
        from ..config import disable_models_from_config as _disable_fn

        _disable_fn(config_path)
        cls._models_disabled = True
        logger.debug("✅ Models disabled from config")

    @classmethod
    def get_inference(cls) -> Any:
        """
        Retorna módulo inference (lazy load).

        Garantiza que models se deshabiliten ANTES de import.

        Returns:
            Módulo inference ya inicializado

        Example:
            inference = InferenceLoader.get_inference()
            pipeline = inference.InferencePipeline.init(...)
        """
        if cls._inference_module is None:
            logger.info("🔧 Lazy loading inference module...")

            # 1. Disable models PRIMERO (enforced)
            if not cls._models_disabled:
                cls.disable_models_from_config()

            # 2. AHORA importar inference (models ya disabled)
            import inference
            cls._inference_module = inference

            logger.info("✅ Inference module loaded")

        return cls._inference_module

    @classmethod
    def reset(cls):
        """
        Reset loader (útil para tests).

        ADVERTENCIA: Solo usar en tests.
        """
        cls._inference_module = None
        cls._models_disabled = False
        logger.debug("🔄 InferenceLoader reset")
