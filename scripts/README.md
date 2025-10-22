# Local ONNX Models - Quick Start

Este directorio contiene utilidades para exportar y usar modelos YOLO locales en formato ONNX.

## Ventajas de Modelos Locales

✅ **Performance**: ~2-3x más rápido que modelos de Roboflow
✅ **Offline**: No requiere API key ni conexión a internet
✅ **Optimización**: Modelos cuantizados específicos para tu hardware

❌ **Trade-off**: Requiere exportar modelos manualmente

## Guía Rápida

### 1. Exportar Modelos

```bash
# Desde la raíz del proyecto
python scripts/export_onnx_models.py
```

Esto creará:
- `models/yolo11n-320.onnx` (Nano - ultrafast, ~6MB)
- `models/yolo11s-320.onnx` (Small - balanced, ~22MB)
- `models/yolo11m-320.onnx` (Medium - accurate, ~50MB)

**Nota**: YOLO11 usa nomenclatura `yolo11n` (sin "v"), a diferencia de YOLOv8 que usa `yolov8n` (con "v")

### 2. Configurar Pipeline

Edita `config.yaml`:

```yaml
models:
  use_local: true
  local_path: "models/yolo11n-320.onnx"
  imgsz: 320
  confidence: 0.25
  iou_threshold: 0.45
```

### 3. Ejecutar Pipeline

```bash
# Con adaptive crop
python quickstart/inference/adeline/run_pipeline_mqtt.py
```

El pipeline detectará automáticamente que estás usando un modelo local y usará Ultralytics en lugar de Roboflow.

## Modelos Disponibles

| Modelo | Tamaño | Velocidad | Precisión | Uso Recomendado |
|--------|--------|-----------|-----------|-----------------|
| yolo11n-320 | ~6MB | ⚡⚡⚡ | ⭐⭐ | Dispositivos con recursos limitados |
| yolo11s-320 | ~22MB | ⚡⚡ | ⭐⭐⭐ | Balance general (recomendado) |
| yolo11m-320 | ~50MB | ⚡ | ⭐⭐⭐⭐ | Cuando precisión es crítica |

## Detalles Técnicos

### Formato de Exportación

- **Formato**: ONNX (Open Neural Network Exchange)
- **Precisión**: FP32 (full precision)
- **Tamaño imagen**: 320x320 (configurable)
- **Simplificación**: Sí (grafo ONNX optimizado)
- **Dinámico**: No (tamaño fijo para mejor performance)

### Arquitectura de Integración

```
Pipeline Flow:

┌─────────────────────────────────────┐
│ PipelineConfig                      │
│  - use_local: true                  │
│  - local_path: models/yolov11n.onnx │
└────────────┬────────────────────────┘
             │
             ▼
┌─────────────────────────────────────┐
│ get_model_from_config()             │
│  └─> LocalONNXModel (Ultralytics)   │
└────────────┬────────────────────────┘
             │
             ▼
┌─────────────────────────────────────┐
│ AdaptiveInferenceHandler            │
│  - model: LocalONNXModel            │
│  - process_fn: process_frame_...    │
└────────────┬────────────────────────┘
             │
             ▼
┌─────────────────────────────────────┐
│ adaptive_roi_inference()            │
│  └─> process_frame_with_local_...() │
└────────────┬────────────────────────┘
             │
             ▼
┌─────────────────────────────────────┐
│ YOLO(model.onnx).predict()          │
│  └─> sv.Detections.from_ultralytics │
└────────────┬────────────────────────┘
             │
             ▼
     Roboflow-compatible format
```

### Conversión de Resultados

El adaptador `local_models.py` convierte automáticamente:

**Ultralytics → Supervision → Roboflow Format**

```python
# Ultralytics YOLO prediction
results = model.predict(image)

# → Supervision Detections
detections = sv.Detections.from_ultralytics(results[0])

# → Roboflow-compatible dict
{
    'predictions': [
        {
            'x': center_x,
            'y': center_y,
            'width': w,
            'height': h,
            'confidence': conf,
            'class': class_name,
            'class_id': class_id,
        },
        ...
    ],
    'image': {'width': w, 'height': h},
}
```

Esto garantiza compatibilidad total con:
- Visualización (`visualization.py`)
- ROI adaptativo (`adaptive_roi.py`)
- MQTT data plane (`mqtt_bridge.py`)

## Troubleshooting

### Error: "Modelo no encontrado"

```bash
# Verifica que el modelo existe
ls -lh models/

# Re-exporta si es necesario
python scripts/export_onnx_models.py
```

### Error: "ROBOFLOW_API_KEY not found"

Si usas modelos locales, no necesitas API key. Asegúrate de configurar:

```yaml
models:
  use_local: true
```

### Performance no mejora

1. Verifica que estás usando el modelo local:
   - Logs deben mostrar: "🔧 Usando modelo local: yolov11n-320.onnx"

2. Considera usar un modelo más pequeño:
   - yolov11n-320 es el más rápido

3. Habilita adaptive crop para mayor speedup:
   ```yaml
   adaptive_crop:
     enabled: true
   ```

## Próximos Pasos

### Cuantización INT8 (TODO)

Para aún mejor performance, exportar con cuantización INT8:

```python
# En export_onnx_models.py
model.export(
    format="onnx",
    half=True,  # FP16
    int8=True,  # INT8 quantization
)
```

**Nota**: Requiere calibración dataset. Ver [Ultralytics Export Docs](https://docs.ultralytics.com/modes/export/)

### Custom Models

Para usar tus propios modelos entrenados:

1. Entrena modelo con Ultralytics o Roboflow
2. Exporta a ONNX:
   ```python
   from ultralytics import YOLO
   model = YOLO("path/to/your/model.pt")
   model.export(format="onnx", imgsz=320)
   ```
3. Coloca en `models/` y actualiza `config.yaml`
