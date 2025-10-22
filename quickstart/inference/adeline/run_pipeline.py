import os

# Disable warnings for unused model dependencies
os.environ["PALIGEMMA_ENABLED"] = "False"
os.environ["FLORENCE2_ENABLED"] = "False"
os.environ["QWEN_2_5_ENABLED"] = "False"
os.environ["CORE_MODEL_SAM_ENABLED"] = "False"
os.environ["CORE_MODEL_SAM2_ENABLED"] = "False"
os.environ["CORE_MODEL_CLIP_ENABLED"] = "False"
os.environ["CORE_MODEL_GAZE_ENABLED"] = "False"
os.environ["SMOLVLM2_ENABLED"] = "False"
os.environ["DEPTH_ESTIMATION_ENABLED"] = "False"
os.environ["MOONDREAM2_ENABLED"] = "False"
os.environ["CORE_MODEL_TROCR_ENABLED"] = "False"
os.environ["CORE_MODEL_GROUNDINGDINO_ENABLED"] = "False"
os.environ["CORE_MODEL_YOLO_WORLD_ENABLED"] = "False"
os.environ["CORE_MODEL_PE_ENABLED"] = "False"

from inference import InferencePipeline
from inference.core.interfaces.stream.sinks import render_boxes
from inference.core.interfaces.camera.entities import StatusUpdate, UpdateSeverity


# ============================================================================
# STATUS UPDATE HANDLER - Para monitorear el estado del pipeline
# ============================================================================
def status_update_handler(status: StatusUpdate) -> None:
    """
    Handler que recibe actualizaciones de estado del pipeline.
    
    StatusUpdate incluye:
    - timestamp: cuando ocurrió el evento
    - severity: DEBUG, INFO, WARNING, ERROR
    - event_type: tipo de evento (conexión, error, etc.)
    - payload: datos adicionales
    - context: contexto adicional
    """
    # Solo mostrar warnings y errors
    if status.severity.value >= UpdateSeverity.WARNING.value:
        print(f"[{status.timestamp}] [{status.severity.name}] {status.event_type}")
        if status.payload:
            print(f"  Payload: {status.payload}")
        if status.context:
            print(f"  Context: {status.context}")
    
    # Puedes agregar lógica específica por tipo de evento
    if "CONNECTION" in status.event_type:
        print(f"  ⚠️ Problema de conexión detectado!")
    elif "ERROR" in status.event_type:
        print(f"  ❌ Error en el pipeline!")


# ============================================================================
# PIPELINE START/END - Para logging general
# ============================================================================
def on_pipeline_start() -> None:
    print("🚀 Pipeline iniciado")

def on_pipeline_end() -> None:
    print("🛑 Pipeline finalizado")


# ============================================================================
# CONFIGURACIÓN Y ARRANQUE
# ============================================================================
api_key = "5RumS6P9422UwlsBx5VL"
rtsp_url = "rtsp://127.0.0.1:8554/live"
model_id = "yolov11n-640"
max_fps = 2  

pipeline = InferencePipeline.init(
    max_fps=max_fps,
    model_id=model_id,
    video_reference=rtsp_url,
    on_prediction=render_boxes,
    api_key=api_key,
    # Lista de handlers para status updates
    status_update_handlers=[status_update_handler],
    # Callbacks para inicio/fin (opcional, pero útil para logging)
    # on_pipeline_start=on_pipeline_start,  # Comentado porque init() no acepta este parámetro
    # on_pipeline_end=on_pipeline_end,
)

pipeline.start()
pipeline.join()