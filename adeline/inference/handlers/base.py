"""
Base Handler Interface
======================

ABC para todos los inference handlers.
Define el contrato explícito que todos los handlers deben cumplir.

Diseño: Complejidad por diseño
- Interface clara y explícita (no duck typing implícito)
- Métodos abstractos para enforcement
- Defaults sensatos para métodos opcionales
"""
from abc import ABC, abstractmethod
from typing import Any, List
from inference.core.interfaces.camera.entities import VideoFrame


class BaseInferenceHandler(ABC):
    """
    Clase base abstracta para inference handlers.

    Contract:
    - __call__: Procesa frames y retorna predictions (REQUIRED)
    - enabled: Property para habilitar/deshabilitar (REQUIRED)
    - supports_toggle: Si soporta toggle dinámico (OPTIONAL, default False)
    - enable/disable: Métodos para toggle (OPTIONAL, raise si no soportado)

    Implementaciones concretas:
    - AdaptiveInferenceHandler: ROI adaptativo con toggle
    - FixedROIInferenceHandler: ROI fijo sin toggle
    - StandardInferenceHandler: Pipeline standard sin custom logic
    """

    @abstractmethod
    def __call__(self, video_frames: List[VideoFrame]) -> List[Any]:
        """
        Procesa video frames y retorna predictions.

        Args:
            video_frames: Lista de frames a procesar

        Returns:
            Lista de predictions (formato depende de implementación)

        Note:
            Este método es llamado por InferencePipeline en cada frame.
        """
        pass

    @property
    @abstractmethod
    def enabled(self) -> bool:
        """
        Si el handler está habilitado.

        Returns:
            True si habilitado, False si deshabilitado

        Note:
            Para handlers inmutables (ej: Fixed), siempre retornar True.
        """
        pass

    @property
    def supports_toggle(self) -> bool:
        """
        Si el handler soporta toggle dinámico (enable/disable).

        Default: False (inmutable)

        Override: True para handlers que permiten enable/disable dinámico
        (ej: AdaptiveInferenceHandler)

        Returns:
            True si soporta toggle, False si es inmutable
        """
        return False

    def enable(self):
        """
        Habilita el handler (solo si supports_toggle=True).

        Raises:
            NotImplementedError: Si handler no soporta toggle

        Note:
            Override este método solo si supports_toggle=True.
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} does not support dynamic enable/disable. "
            f"supports_toggle={self.supports_toggle}"
        )

    def disable(self):
        """
        Deshabilita el handler (solo si supports_toggle=True).

        Raises:
            NotImplementedError: Si handler no soporta toggle

        Note:
            Override este método solo si supports_toggle=True.
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} does not support dynamic enable/disable. "
            f"supports_toggle={self.supports_toggle}"
        )
