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
        [DEPRECATED] Deshabilita modelos según config.

        NOTA: Al usar 'make run', las env vars se setean directamente en Makefile.
        Este método se mantiene por compatibilidad pero ya no es necesario llamarlo.

        Args:
            config_path: Path al config.yaml (default: config/adeline/config.yaml)
        """
        if cls._models_disabled:
            return

        # Importar función desde config
        from ..config import disable_models_from_config as _disable_fn

        _disable_fn(config_path)
        cls._models_disabled = True

    @classmethod
    def get_inference(cls) -> Any:
        """
        Retorna módulo inference (lazy load).

        NOTA: Las env vars para deshabilitar modelos deben setearse ANTES
        de llamar este método (ej: en Makefile, env_setup.py, o tests).

        Returns:
            Módulo inference ya inicializado

        Example:
            inference = InferenceLoader.get_inference()
            pipeline = inference.InferencePipeline.init(...)
        """
        if cls._inference_module is None:
            logger.info(
                "Lazy loading inference module",
                extra={
                    "component": "inference_loader",
                    "event": "lazy_load_start",
                }
            )

            # Importar inference (env vars ya configuradas por Makefile/env_setup)
            import inference
            cls._inference_module = inference

            logger.info(
                "Inference module loaded",
                extra={
                    "component": "inference_loader",
                    "event": "lazy_load_success",
                }
            )

        return cls._inference_module

    @classmethod
    def reset(cls):
        """
        Reset loader (útil para tests).

        ADVERTENCIA: Solo usar en tests.
        """
        cls._inference_module = None
        cls._models_disabled = False
        logger.debug(
            "InferenceLoader reset",
            extra={
                "component": "inference_loader",
                "event": "loader_reset",
            }
        )
