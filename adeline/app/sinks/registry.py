"""
Sink Registry
=============

Registry simple para desacoplar sinks del factory.

Diseño: Práctica de arquitectura
- Desacoplamiento básico (sink no conoce factory)
- Priority explícito (no orden implícito)
- Extensible (se puede agregar is_applicable() después si duele)

Filosofía: "Complejidad por diseño"
- ~50 líneas, no plugin system completo
- Evolutivo: crece si necesitamos más features
"""
from typing import List, Callable, Optional, Any, Dict
import logging

logger = logging.getLogger(__name__)


class SinkRegistry:
    """
    Registry simple de sinks.

    Permite registrar sinks con factory functions y priority para
    desacoplar creación de sinks.

    Usage:
        registry = SinkRegistry()

        # Registrar sinks
        registry.register('mqtt', mqtt_factory, priority=1)
        registry.register('visualization', viz_factory, priority=100)

        # Crear todos
        sinks = registry.create_all(config=config, data_plane=data_plane, ...)
    """

    def __init__(self):
        """Inicializa registry vacío."""
        self._factories: List[tuple[str, Callable, int]] = []

    def register(
        self,
        name: str,
        factory: Callable,
        priority: int = 100,
    ) -> None:
        """
        Registra un sink con su factory function.

        Args:
            name: Nombre único del sink (ej: 'mqtt', 'visualization')
            factory: Callable que crea el sink
                     Signature: factory(config, **kwargs) -> Callable | None
                     Si retorna None, el sink se skippea
            priority: Orden de ejecución (menor = primero)

        Example:
            >>> def mqtt_factory(config, data_plane, **kwargs):
            ...     return create_mqtt_sink(data_plane)
            >>> registry.register('mqtt', mqtt_factory, priority=1)
        """
        self._factories.append((name, factory, priority))
        logger.debug(f"📝 Sink registered: '{name}' (priority={priority})")

    def create_all(
        self,
        config,
        **kwargs
    ) -> List[Callable]:
        """
        Crea todos los sinks registrados según priority.

        Args:
            config: PipelineConfig
            **kwargs: Args para factories (data_plane, roi_state, etc.)

        Returns:
            Lista de sinks ordenados por priority

        Note:
            Si factory retorna None, el sink se skippea.
        """
        sinks = []

        # Ordenar por priority
        sorted_factories = sorted(self._factories, key=lambda x: x[2])

        # Crear sinks
        for name, factory, priority in sorted_factories:
            try:
                sink = factory(config=config, **kwargs)

                # Si factory retorna None, skip
                if sink is None:
                    logger.debug(f"⏭️  Sink skipped: {name}")
                    continue

                sinks.append(sink)
                logger.info(f"✅ Sink created: {name} (priority={priority})")

            except Exception as e:
                logger.error(f"❌ Error creating sink '{name}': {e}")
                raise

        logger.info(f"📊 Total sinks created: {len(sinks)}")
        return sinks
