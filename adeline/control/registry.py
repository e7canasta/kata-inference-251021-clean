"""
Command Registry
================

Registry explícito de comandos MQTT disponibles.

Problema resuelto:
- Callbacks opcionales (on_toggle_crop solo si adaptive)
- No hay forma de saber qué comandos están disponibles
- Errores confusos cuando comando no está registrado

Solución:
- Registry explícito: solo registras comandos disponibles
- Validación temprana: error si comando no existe
- Introspección: listar comandos disponibles
"""
from typing import Callable, Dict, Set
import logging

logger = logging.getLogger(__name__)


class CommandNotAvailableError(Exception):
    """Comando no está disponible en el modo actual."""
    pass


class CommandRegistry:
    """
    Registry de comandos MQTT.

    Diseño: Complejidad por diseño
    - Comandos explícitos (se registran solo si están disponibles)
    - Validación temprana (error claro si comando no existe)
    - Introspección (listar comandos disponibles)

    Usage:
        registry = CommandRegistry()

        # Registrar comandos básicos
        registry.register('pause', handler.pause, "Pausa el procesamiento")
        registry.register('resume', handler.resume, "Reanuda el procesamiento")

        # Registrar comandos condicionales
        if handler.supports_toggle:
            registry.register('toggle_crop', handler.toggle, "Toggle ROI crop")

        # Ejecutar
        try:
            registry.execute('pause')
        except CommandNotAvailableError as e:
            logger.warning(str(e))
    """

    def __init__(self):
        """Inicializa registry vacío."""
        self._commands: Dict[str, Callable] = {}
        self._descriptions: Dict[str, str] = {}

    def register(self, command: str, handler: Callable, description: str = ""):
        """
        Registra un comando.

        Args:
            command: Nombre del comando (ej: 'pause', 'toggle_crop')
            handler: Función a ejecutar
            description: Descripción del comando para help/logging

        Note:
            Si comando ya existe, se sobrescribe con warning.
        """
        if command in self._commands:
            logger.warning(f"⚠️ Comando '{command}' ya registrado, sobrescribiendo")

        self._commands[command] = handler
        self._descriptions[command] = description
        logger.debug(f"📝 Comando registrado: '{command}' - {description}")

    def execute(self, command: str):
        """
        Ejecuta un comando.

        Args:
            command: Nombre del comando

        Returns:
            Resultado del handler (o None)

        Raises:
            CommandNotAvailableError: Si comando no está registrado
        """
        if command not in self._commands:
            available = ', '.join(sorted(self.available_commands))
            raise CommandNotAvailableError(
                f"Command '{command}' not available. "
                f"Available commands: {available}"
            )

        handler = self._commands[command]
        logger.debug(f"⚙️ Ejecutando comando: '{command}'")
        return handler()

    def is_available(self, command: str) -> bool:
        """
        Verifica si comando está disponible.

        Args:
            command: Nombre del comando

        Returns:
            True si comando está registrado
        """
        return command in self._commands

    @property
    def available_commands(self) -> Set[str]:
        """
        Set de comandos disponibles.

        Returns:
            Set de nombres de comandos registrados
        """
        return set(self._commands.keys())

    def get_help(self) -> Dict[str, str]:
        """
        Retorna diccionario de comandos con descripciones.

        Returns:
            Dict[comando, descripción]

        Usage:
            for cmd, desc in registry.get_help().items():
                print(f"{cmd}: {desc}")
        """
        return dict(self._descriptions)

    def __repr__(self) -> str:
        """String representation para debugging."""
        cmds = ', '.join(sorted(self.available_commands))
        return f"CommandRegistry({len(self._commands)} commands: {cmds})"
