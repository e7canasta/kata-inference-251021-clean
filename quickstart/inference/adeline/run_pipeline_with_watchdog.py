import os
import time
from threading import Thread

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
from inference.core.interfaces.stream.watchdog import BasePipelineWatchDog


# ============================================================================
# CUSTOM WATCHDOG - Para métricas de rendimiento
# ============================================================================
class CustomWatchdog(BasePipelineWatchDog):
    """
    Watchdog personalizado que extiende BasePipelineWatchDog.
    
    Útil para:
    - Monitorear latencia de inferencia
    - Calcular throughput (FPS)
    - Detectar cuellos de botella
    """
    
    def __init__(self):
        super().__init__()
        self.inference_count = 0
    
    def on_status_update(self, status_update: StatusUpdate) -> None:
        """Override para logging personalizado de status updates"""
        super().on_status_update(status_update)
        
        if status_update.severity.value >= UpdateSeverity.WARNING.value:
            print(f"⚠️ [{status_update.severity.name}] {status_update.event_type}")
    
    def get_metrics_summary(self):
        """Método helper para obtener métricas formateadas"""
        report = self.get_report()
        
        print("\n" + "="*60)
        print("📊 MÉTRICAS DEL PIPELINE")
        print("="*60)
        
        if report:
            print(f"🚀 Throughput: {report.inference_throughput:.2f} FPS")
            
            for latency_report in report.latency_reports:
                print(f"\n📹 Source ID: {latency_report.source_id}")
                if latency_report.frame_decoding_latency:
                    print(f"  ⏱️  Decoding latency: {latency_report.frame_decoding_latency*1000:.2f} ms")
                if latency_report.inference_latency:
                    print(f"  🤖 Inference latency: {latency_report.inference_latency*1000:.2f} ms")
                if latency_report.e2e_latency:
                    print(f"  🎯 E2E latency: {latency_report.e2e_latency*1000:.2f} ms")
        
        print("="*60 + "\n")


# ============================================================================
# STATUS UPDATE HANDLER - Para eventos específicos
# ============================================================================
def status_update_handler(status: StatusUpdate) -> None:
    """Handler separado para lógica de negocio basada en eventos"""
    
    # Ejemplo: Enviar alertas si hay errores de conexión
    if "CONNECTION" in status.event_type and status.severity == UpdateSeverity.ERROR:
        print(f"🚨 ALERTA: Conexión perdida - {status.timestamp}")
        # Aquí podrías: enviar email, webhook, log a sistema externo, etc.


# ============================================================================
# MONITOR THREAD - Para reportes periódicos
# ============================================================================
def monitor_pipeline_metrics(watchdog: CustomWatchdog, interval_seconds: int = 10):
    """Thread separado que imprime métricas periódicamente"""
    try:
        while True:
            time.sleep(interval_seconds)
            watchdog.get_metrics_summary()
    except KeyboardInterrupt:
        print("Monitor detenido")


# ============================================================================
# CONFIGURACIÓN Y ARRANQUE
# ============================================================================
def main():
    api_key = "5RumS6P9422UwlsBx5VL"
    rtsp_url = "rtsp://127.0.0.1:8554/live"
    model_id = "yolov11n-640"
    max_fps = 2
    
    # Crear watchdog personalizado
    watchdog = CustomWatchdog()
    
    # Crear pipeline con watchdog y status handlers
    pipeline = InferencePipeline.init(
        max_fps=max_fps,
        model_id=model_id,
        video_reference=rtsp_url,
        on_prediction=render_boxes,
        api_key=api_key,
        # Watchdog para métricas de rendimiento
        watchdog=watchdog,
        # Status handlers adicionales para lógica de negocio
        status_update_handlers=[status_update_handler],
    )
    
    # Iniciar thread de monitoreo de métricas
    monitor_thread = Thread(
        target=monitor_pipeline_metrics,
        args=(watchdog, 10),  # Reportar cada 10 segundos
        daemon=True
    )
    monitor_thread.start()
    
    print("🚀 Iniciando pipeline...")
    print("📊 Métricas se mostrarán cada 10 segundos")
    print("⌨️  Presiona Ctrl+C para detener\n")
    
    try:
        pipeline.start()
        pipeline.join()
    except KeyboardInterrupt:
        print("\n🛑 Deteniendo pipeline...")
        pipeline.terminate()
        watchdog.get_metrics_summary()  # Métricas finales


if __name__ == "__main__":
    main()

