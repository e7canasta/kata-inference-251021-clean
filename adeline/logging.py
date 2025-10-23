"""
Structured Logging Infrastructure
==================================

Logging JSON-based para queryability en producción.

Design Philosophy:
- Solo JSON (no dual output - pragmatismo > complejidad)
- Trace correlation vía contextvars
- Helpers para casos comunes (MQTT, métricas, errores)
- Mantiene emojis en mensaje (human-readable dentro de JSON)
- File rotation automático (RotatingFileHandler)

Usage:
    # Setup (una vez al inicio)
    from adeline.logging import setup_logging

    # Stdout (desarrollo)
    setup_logging(level="INFO")

    # File con rotation (producción)
    setup_logging(
        level="INFO",
        log_file="logs/adeline.log",
        max_bytes=10*1024*1024,  # 10 MB
        backup_count=5  # mantener 5 backups (50 MB total)
    )

    # Logging con contexto
    logger.info("📥 Comando recibido", extra={
        "command": "pause",
        "mqtt_topic": "inference/control/commands"
    })

    # Con trace propagation
    from adeline.logging import trace_context, get_trace_id

    with trace_context(f"cmd-{uuid.uuid4().hex[:8]}"):
        logger.info("Procesando comando", extra={"trace_id": get_trace_id()})
"""
import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from contextvars import ContextVar
from contextlib import contextmanager
from typing import Optional, Dict, Any
import uuid

# ============================================================================
# Trace Context (propagación de trace_id)
# ============================================================================

# ContextVar para thread-safe trace propagation
trace_id_var: ContextVar[Optional[str]] = ContextVar('trace_id', default=None)


def get_trace_id() -> Optional[str]:
    """
    Obtiene el trace_id actual del contexto.

    Returns:
        Trace ID actual o None si no hay contexto activo
    """
    return trace_id_var.get()


def generate_trace_id(prefix: str = "trace") -> str:
    """
    Genera un nuevo trace ID único.

    Args:
        prefix: Prefijo para el trace ID (ej: "cmd", "inference", "mqtt")

    Returns:
        Trace ID en formato: {prefix}-{short_uuid}
    """
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


@contextmanager
def trace_context(trace_id: Optional[str] = None):
    """
    Context manager para propagar trace_id en toda la call stack.

    Args:
        trace_id: ID de trace a propagar. Si None, genera uno automático.

    Usage:
        with trace_context(f"cmd-{uuid.uuid4().hex[:8]}"):
            # Todo lo que se ejecute aquí tiene acceso al trace_id
            process_command()
            logger.info("Action", extra={"trace_id": get_trace_id()})
    """
    if trace_id is None:
        trace_id = generate_trace_id()

    token = trace_id_var.set(trace_id)
    try:
        yield trace_id
    finally:
        trace_id_var.reset(token)


# ============================================================================
# Logger Setup
# ============================================================================

def setup_logging(
    level: str = "INFO",
    indent: Optional[int] = None,
    add_fields: Optional[Dict[str, Any]] = None,
    log_file: Optional[str] = None,
    max_bytes: int = 10 * 1024 * 1024,  # 10 MB
    backup_count: int = 5,
) -> None:
    """
    Configura structured logging (JSON) para toda la aplicación.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        indent: JSON indent para pretty-print (None = compact, 2 = readable)
        add_fields: Campos adicionales globales (ej: {"environment": "production"})
        log_file: Path al archivo de logs (None = stdout). Si se especifica, usa rotation.
        max_bytes: Tamaño máximo por archivo antes de rotar (default 10 MB)
        backup_count: Número de archivos backup a mantener (default 5)

    Usage:
        # Desarrollo (stdout, pretty-print)
        setup_logging(level="DEBUG", indent=2)

        # Producción (file con rotation, compact)
        setup_logging(
            level="INFO",
            log_file="logs/adeline.log",
            max_bytes=10*1024*1024,  # 10 MB
            backup_count=5  # Total: 50 MB
        )

    File Rotation:
        - Archivos rotados: adeline.log, adeline.log.1, adeline.log.2, ...
        - Cuando adeline.log alcanza max_bytes:
          1. Renombra adeline.log.4 → adeline.log.5 (elimina el más viejo)
          2. Renombra adeline.log.3 → adeline.log.4
          3. Renombra adeline.log.2 → adeline.log.3
          4. Renombra adeline.log.1 → adeline.log.2
          5. Renombra adeline.log → adeline.log.1
          6. Crea nuevo adeline.log vacío
    """
    try:
        from pythonjsonlogger import jsonlogger
    except ImportError:
        raise ImportError(
            "pythonjsonlogger no encontrado. Instalar con: pip install python-json-logger"
        )

    # Custom formatter que agrega campos globales
    class CustomJsonFormatter(jsonlogger.JsonFormatter):
        def add_fields(self, log_record, record, message_dict):
            super().add_fields(log_record, record, message_dict)

            # Renombrar campos para consistencia
            if 'levelname' in log_record:
                log_record['level'] = log_record.pop('levelname')

            if 'name' in log_record:
                log_record['logger'] = log_record.pop('name')

            # Agregar trace_id del contexto si existe
            current_trace_id = get_trace_id()
            if current_trace_id and 'trace_id' not in log_record:
                log_record['trace_id'] = current_trace_id

            # Campos adicionales globales
            if add_fields:
                for key, value in add_fields.items():
                    if key not in log_record:
                        log_record[key] = value

    # Configurar handler (stdout o file con rotation)
    if log_file:
        # File handler con rotation automático
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        handler = RotatingFileHandler(
            filename=str(log_path),
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding='utf-8'
        )

        # Log inicial para confirmar rotation setup
        print(f"📄 Logging to file: {log_file} (max: {max_bytes//1024//1024}MB, backups: {backup_count})", file=sys.stderr)
    else:
        # Stdout handler (desarrollo)
        handler = logging.StreamHandler(sys.stdout)

    formatter = CustomJsonFormatter(
        '%(timestamp)s %(level)s %(logger)s %(message)s',
        timestamp=True,
        json_indent=indent
    )
    handler.setFormatter(formatter)

    # Configurar root logger
    root_logger = logging.getLogger()
    root_logger.handlers.clear()  # Remove default handlers
    root_logger.addHandler(handler)
    root_logger.setLevel(getattr(logging, level.upper()))


# ============================================================================
# Helper Functions (DRY para casos comunes)
# ============================================================================

def log_mqtt_command(
    logger: logging.Logger,
    command: str,
    topic: str,
    payload: Optional[Dict[str, Any]] = None,
    trace_id: Optional[str] = None
) -> None:
    """
    Helper para logs de comandos MQTT (Control Plane).

    Args:
        logger: Logger instance
        command: Nombre del comando (pause, resume, stop, etc.)
        topic: MQTT topic
        payload: Payload completo del comando (opcional)
        trace_id: Trace ID (usa contexto si no se especifica)
    """
    extra = {
        "component": "control_plane",
        "command": command,
        "mqtt_topic": topic,
        "trace_id": trace_id or get_trace_id()
    }

    if payload:
        extra["payload"] = payload

    logger.info(f"📥 Comando recibido: {command}", extra=extra)


def log_mqtt_publish(
    logger: logging.Logger,
    topic: str,
    qos: int,
    payload_size: int,
    success: bool = True,
    error_code: Optional[int] = None,
    num_detections: Optional[int] = None,
    component: str = "data_plane",
) -> None:
    """
    Helper para logs de publicación MQTT (Data Plane).

    Args:
        logger: Logger instance
        topic: MQTT topic
        qos: QoS level
        payload_size: Tamaño del payload en bytes
        success: Si la publicación fue exitosa
        error_code: Código de error MQTT (si success=False)
        num_detections: Número de detecciones en el payload (opcional)
        component: Componente que genera el log
    """
    extra = {
        "component": component,
        "mqtt_topic": topic,
        "qos": qos,
        "payload_size_bytes": payload_size,
        "success": success
    }

    if error_code is not None:
        extra["mqtt_error_code"] = error_code

    if num_detections is not None:
        extra["num_detections"] = num_detections

    if success:
        logger.debug(f"📤 Mensaje publicado a {topic}", extra=extra)
    else:
        logger.warning(f"⚠️ Error publicando a {topic}", extra=extra)


def log_pipeline_metrics(
    logger: logging.Logger,
    fps: float,
    latency_ms: Optional[float] = None,
    frames_processed: Optional[int] = None,
    additional_metrics: Optional[Dict[str, Any]] = None
) -> None:
    """
    Helper para logs de métricas del pipeline.

    Args:
        logger: Logger instance
        fps: Frames per second
        latency_ms: Latencia en milisegundos
        frames_processed: Total de frames procesados
        additional_metrics: Métricas adicionales
    """
    metrics = {"fps": round(fps, 2)}

    if latency_ms is not None:
        metrics["latency_ms"] = round(latency_ms, 2)

    if frames_processed is not None:
        metrics["frames_processed"] = frames_processed

    if additional_metrics:
        metrics.update(additional_metrics)

    extra = {
        "component": "inference_pipeline",
        "metrics": metrics
    }

    logger.info(f"📊 Pipeline metrics: {fps:.2f} FPS", extra=extra)


def log_stabilization_stats(
    logger: logging.Logger,
    raw_count: int,
    stabilized_count: int,
    active_tracks: int,
    total_confirmed: int = 0,
    total_removed: int = 0,
    source_id: int = 0,
    component: str = "stabilization",
) -> None:
    """
    Helper para logs de estadísticas de estabilización.

    Args:
        logger: Logger instance
        raw_count: Número de detecciones raw en frame actual
        stabilized_count: Número de detecciones estabilizadas emitidas
        active_tracks: Tracks activos actualmente
        total_confirmed: Total de tracks confirmados (acumulado)
        total_removed: Total de tracks removidos (acumulado)
        source_id: ID del source
        component: Componente que genera el log
    """
    extra = {
        "component": component,
        "source_id": source_id,
        "stabilization": {
            "raw_count": raw_count,
            "stabilized_count": stabilized_count,
            "active_tracks": active_tracks,
            "total_confirmed": total_confirmed,
            "total_removed": total_removed,
        }
    }

    logger.debug(
        f"Stabilization processed: {raw_count} raw → {stabilized_count} stabilized (active_tracks={active_tracks})",
        extra=extra
    )


def log_error_with_context(
    logger: logging.Logger,
    message: str,
    exception: Optional[Exception] = None,
    component: str = "unknown",
    event: Optional[str] = None,
    trace_id: Optional[str] = None,
    **kwargs: Any
) -> None:
    """
    Helper para logs de errores con contexto completo.

    Args:
        logger: Logger instance
        message: Mensaje de error
        exception: Excepción capturada (opcional)
        component: Componente donde ocurrió el error
        event: Evento que causó el error
        trace_id: Trace ID (usa contexto si no se especifica)
        **kwargs: Contexto adicional (broker_host, topic, etc.)
    """
    extra = {
        "component": component,
        "trace_id": trace_id or get_trace_id()
    }

    if event:
        extra["event"] = event

    if exception:
        extra["error_type"] = type(exception).__name__
        extra["error_message"] = str(exception)

    # Agregar kwargs como contexto adicional
    extra.update(kwargs)

    if exception:
        logger.error(f"{message}: {exception}", extra=extra, exc_info=True)
    else:
        logger.error(message, extra=extra)


# ============================================================================
# Component-specific loggers (optional - para mejor namespace)
# ============================================================================

def get_component_logger(component: str) -> logging.Logger:
    """
    Obtiene un logger con namespace específico.

    Args:
        component: Nombre del componente (control_plane, data_plane, etc.)

    Returns:
        Logger configurado para ese componente
    """
    return logging.getLogger(f"adeline.{component}")


# ============================================================================
# Exports
# ============================================================================

__all__ = [
    # Setup
    "setup_logging",
    # Trace context
    "trace_context",
    "get_trace_id",
    "generate_trace_id",
    # Helpers
    "log_mqtt_command",
    "log_mqtt_publish",
    "log_pipeline_metrics",
    "log_stabilization_stats",
    "log_error_with_context",
    # Component loggers
    "get_component_logger",
]
