"""
MQTT Command Tests
==================

Tests de comandos críticos del Control Plane.

Invariantes testeadas:
1. Registry básico: register, execute, is_available
2. CommandNotAvailableError cuando comando no existe
3. Comandos condicionales: toggle_crop solo si handler supports_toggle
4. shutdown_event se activa con comando STOP
"""
import pytest
from control.registry import CommandRegistry, CommandNotAvailableError


@pytest.mark.unit
@pytest.mark.mqtt
class TestCommandRegistry:
    """Tests de CommandRegistry (infraestructura)"""

    def test_register_and_execute(self):
        """
        Invariante: Comando registrado debe ejecutarse correctamente.
        """
        registry = CommandRegistry()

        # Mock handler
        executed = []
        def mock_handler():
            executed.append(True)

        # Register + Execute
        registry.register('test_cmd', mock_handler, "Test command")
        registry.execute('test_cmd')

        assert len(executed) == 1, "Handler debe ejecutarse una vez"

    def test_execute_unregistered_raises_error(self):
        """
        Invariante: Ejecutar comando no registrado debe lanzar CommandNotAvailableError.
        """
        registry = CommandRegistry()

        with pytest.raises(CommandNotAvailableError) as exc_info:
            registry.execute('nonexistent_command')

        # Verificar que el error menciona comandos disponibles
        assert 'nonexistent_command' in str(exc_info.value)
        assert 'Available commands' in str(exc_info.value)

    def test_is_available(self):
        """
        Propiedad: is_available() retorna True solo para comandos registrados.
        """
        registry = CommandRegistry()

        # Antes de registrar
        assert not registry.is_available('test_cmd')

        # Después de registrar
        registry.register('test_cmd', lambda: None, "Test")
        assert registry.is_available('test_cmd')

    def test_available_commands_property(self):
        """
        Propiedad: available_commands retorna set de comandos registrados.
        """
        registry = CommandRegistry()

        # Vacío inicialmente
        assert registry.available_commands == set()

        # Después de registrar
        registry.register('cmd1', lambda: None, "Command 1")
        registry.register('cmd2', lambda: None, "Command 2")

        assert registry.available_commands == {'cmd1', 'cmd2'}

    def test_get_help(self):
        """
        Propiedad: get_help() retorna dict con descripciones.
        """
        registry = CommandRegistry()

        registry.register('cmd1', lambda: None, "Description 1")
        registry.register('cmd2', lambda: None, "Description 2")

        help_dict = registry.get_help()

        assert help_dict['cmd1'] == "Description 1"
        assert help_dict['cmd2'] == "Description 2"

    def test_overwrite_command_logs_warning(self, caplog):
        """
        Comportamiento: Sobrescribir comando existente debe loggear warning.
        """
        registry = CommandRegistry()

        registry.register('cmd', lambda: None, "First")

        # Sobrescribir
        with caplog.at_level('WARNING'):
            registry.register('cmd', lambda: None, "Second")

        # Verificar warning
        assert any("sobrescribiendo" in record.message.lower() for record in caplog.records)


@pytest.mark.unit
@pytest.mark.mqtt
class TestConditionalCommands:
    """Tests de comandos condicionales (solo disponibles en ciertos modos)"""

    def test_toggle_crop_only_if_handler_supports(self):
        """
        Invariante: toggle_crop solo se registra si handler.supports_toggle == True.

        Este test simula la lógica de controller.py:209-211
        """
        registry = CommandRegistry()

        # Mock handler SIN soporte de toggle
        class MockHandlerNoToggle:
            supports_toggle = False

        handler = MockHandlerNoToggle()

        # Registrar comandos básicos
        registry.register('pause', lambda: None, "Pause")
        registry.register('stop', lambda: None, "Stop")

        # toggle_crop NO se registra
        if handler.supports_toggle:
            registry.register('toggle_crop', lambda: None, "Toggle")

        # Verificar que toggle_crop NO está disponible
        assert registry.is_available('pause')
        assert registry.is_available('stop')
        assert not registry.is_available('toggle_crop')

    def test_toggle_crop_registered_if_handler_supports(self):
        """
        Invariante: toggle_crop se registra si handler.supports_toggle == True.
        """
        registry = CommandRegistry()

        # Mock handler CON soporte de toggle
        class MockHandlerWithToggle:
            supports_toggle = True

        handler = MockHandlerWithToggle()

        # Registrar comandos básicos
        registry.register('pause', lambda: None, "Pause")

        # toggle_crop SÍ se registra
        if handler.supports_toggle:
            registry.register('toggle_crop', lambda: None, "Toggle")

        # Verificar que toggle_crop SÍ está disponible
        assert registry.is_available('toggle_crop')

    def test_stabilization_stats_only_if_stabilizer_exists(self):
        """
        Invariante: stabilization_stats solo se registra si stabilizer is not None.

        Simula controller.py:214-216
        """
        registry = CommandRegistry()

        # Caso 1: Sin stabilizer
        stabilizer = None

        if stabilizer is not None:
            registry.register('stabilization_stats', lambda: None, "Stats")

        assert not registry.is_available('stabilization_stats')

        # Caso 2: Con stabilizer
        class MockStabilizer:
            pass

        stabilizer = MockStabilizer()

        if stabilizer is not None:
            registry.register('stabilization_stats', lambda: None, "Stats")

        assert registry.is_available('stabilization_stats')


@pytest.mark.integration
@pytest.mark.mqtt
class TestCommandInvariants:
    """Tests de invariantes de comandos (comportamiento esperado)"""

    def test_stop_command_sets_shutdown_event(self):
        """
        Invariante CRÍTICO: Comando STOP debe activar shutdown_event.

        Este es el comportamiento que garantiza terminación del programa.
        Basado en controller.py:225-241
        """
        from threading import Event

        # Mock estado del controller
        shutdown_event = Event()
        is_running = [True]  # Lista para poder modificar en closure

        # Mock pipeline
        class MockPipeline:
            def terminate(self):
                pass

        pipeline = MockPipeline()

        # Simular _handle_stop()
        def handle_stop():
            if is_running[0]:
                pipeline.terminate()
                is_running[0] = False

            # CRÍTICO: shutdown_event debe setearse
            shutdown_event.set()

        # Ejecutar
        registry = CommandRegistry()
        registry.register('stop', handle_stop, "Stop")
        registry.execute('stop')

        # INVARIANTE: shutdown_event DEBE estar seteado
        assert shutdown_event.is_set(), "shutdown_event debe activarse con comando STOP"
        assert not is_running[0], "is_running debe ser False después de STOP"

    def test_pause_resume_commands_exist(self):
        """
        Invariante: Comandos pause y resume siempre deben estar disponibles.

        Comandos básicos que siempre se registran (controller.py:202-203)
        """
        registry = CommandRegistry()

        # Simular registro de comandos básicos
        registry.register('pause', lambda: None, "Pause")
        registry.register('resume', lambda: None, "Resume")
        registry.register('stop', lambda: None, "Stop")

        # Verificar que están disponibles
        assert registry.is_available('pause')
        assert registry.is_available('resume')
        assert registry.is_available('stop')

        # Verificar que forman parte de available_commands
        assert 'pause' in registry.available_commands
        assert 'resume' in registry.available_commands
        assert 'stop' in registry.available_commands


@pytest.mark.unit
@pytest.mark.mqtt
class TestCommandEdgeCases:
    """Tests de edge cases en comandos"""

    def test_execute_returns_handler_result(self):
        """
        Propiedad: execute() debe retornar resultado del handler.
        """
        registry = CommandRegistry()

        def handler_with_return():
            return "result_value"

        registry.register('cmd', handler_with_return, "Test")
        result = registry.execute('cmd')

        assert result == "result_value"

    def test_empty_registry_has_no_commands(self):
        """
        Edge case: Registry vacío no tiene comandos disponibles.
        """
        registry = CommandRegistry()

        assert len(registry.available_commands) == 0
        assert registry.get_help() == {}

    def test_execute_on_empty_registry_raises_error(self):
        """
        Edge case: Ejecutar cualquier comando en registry vacío debe fallar.
        """
        registry = CommandRegistry()

        with pytest.raises(CommandNotAvailableError):
            registry.execute('any_command')
