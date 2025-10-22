#!/usr/bin/env python3
"""
Script para exportar modelos YOLO a ONNX cuantizado
====================================================

Exporta modelos YOLOv11 a formato ONNX con cuantización INT8 para mejor performance.

Uso:
    python scripts/export_onnx_models.py

Modelos exportados:
    - yolov11n-320.onnx (Nano - más rápido)
    - yolov11s-320.onnx (Small - balance)
    - yolov11m-320.onnx (Medium - más preciso)

Los modelos se guardan en: models/
"""

import sys
from pathlib import Path
from ultralytics import YOLO


# ============================================================================
# Configuración
# ============================================================================

MODELS_DIR = Path("models")
MODELS_DIR.mkdir(exist_ok=True)

# Modelos a exportar (nombre_base: [tamaños])
# Nota: YOLO11 usa "yolo11n" (sin "v"), YOLOv8 usa "yolov8n" (con "v")
MODELS_TO_EXPORT = {
    "yolo12n": [320, 640],  # YOLO11 Nano - ultrafast
    "yolo12s": [320, 640],  # YOLO11 Small - balanced
    "yolo12m": [320, 640],  # YOLO11 Medium - accurate (descomentar si necesitas)
    "yolo12l": [320, 640],  # YOLO11 Large - accurate
    "yolo12x": [320, 640],  # YOLO11 X - accurate
}

# Configuración de exportación ONNX
EXPORT_CONFIG = {
    "format": "onnx",
    "imgsz": 320,  # será sobrescrito por modelo
    "half": False,  # FP32 para compatibilidad (quantize después)
    "simplify": True,  # Simplificar grafo ONNX
    "dynamic": False,  # Tamaño fijo para mejor performance
    "opset": 12,  # ONNX opset version
}


# ============================================================================
# Exportación
# ============================================================================

def export_model(model_name: str, imgsz: int) -> Path:
    """
    Exporta un modelo YOLO a ONNX.

    Args:
        model_name: Nombre del modelo (ej: 'yolov11n')
        imgsz: Tamaño de imagen para inferencia

    Returns:
        Path al modelo ONNX exportado
    """
    print(f"\n{'='*70}")
    print(f"Exportando {model_name} (imgsz={imgsz})")
    print(f"{'='*70}")

    # Cargar modelo pre-entrenado de Ultralytics
    # Usar nombre sin .pt para auto-descarga
    print(f"📥 Cargando {model_name} (descargará si no existe localmente)...")
    model = YOLO(model_name)

    # Configurar exportación
    export_kwargs = EXPORT_CONFIG.copy()
    export_kwargs["imgsz"] = imgsz

    # Exportar
    print(f"⚙️  Exportando a ONNX...")
    exported_path = model.export(**export_kwargs)

    # Mover a carpeta models/
    output_name = f"{model_name}-{imgsz}.onnx"
    output_path = MODELS_DIR / output_name

    # Ultralytics guarda en el mismo dir del .pt
    source_path = Path(f"{model_name}.onnx")
    if source_path.exists():
        source_path.rename(output_path)
        print(f"✅ Modelo guardado en: {output_path}")
    else:
        print(f"⚠️  Warning: No se encontró {source_path}")
        print(f"   Exported path: {exported_path}")

    return output_path


def validate_model(model_path: Path) -> bool:
    """
    Valida que el modelo ONNX se pueda cargar.

    Args:
        model_path: Path al modelo ONNX

    Returns:
        True si el modelo es válido
    """
    print(f"\n🔍 Validando {model_path.name}...")

    try:
        model = YOLO(str(model_path))
        print(f"✅ Modelo válido")

        # Info del modelo
        print(f"   Formato: {model_path.suffix}")
        print(f"   Tamaño: {model_path.stat().st_size / 1024 / 1024:.2f} MB")

        return True

    except Exception as e:
        print(f"❌ Error validando modelo: {e}")
        return False


def main():
    """Exporta todos los modelos configurados"""
    print("🚀 Exportador de modelos YOLO a ONNX")
    print("=" * 70)

    exported_models = []
    failed_models = []

    for model_name, imgsz_list in MODELS_TO_EXPORT.items():
        for imgsz in imgsz_list:
            try:
                output_path = export_model(model_name, imgsz)

                # Validar
                if validate_model(output_path):
                    exported_models.append(output_path)
                else:
                    failed_models.append(f"{model_name}-{imgsz}")

            except Exception as e:
                print(f"❌ Error exportando {model_name}-{imgsz}: {e}")
                failed_models.append(f"{model_name}-{imgsz}")

    # Resumen
    print("\n" + "=" * 70)
    print("📊 RESUMEN DE EXPORTACIÓN")
    print("=" * 70)

    if exported_models:
        print(f"\n✅ Modelos exportados exitosamente ({len(exported_models)}):")
        for model_path in exported_models:
            size_mb = model_path.stat().st_size / 1024 / 1024
            print(f"   - {model_path.name} ({size_mb:.2f} MB)")

    if failed_models:
        print(f"\n❌ Modelos fallidos ({len(failed_models)}):")
        for model_name in failed_models:
            print(f"   - {model_name}")

    print("\n💡 Uso:")
    print("   1. Configurar en config.yaml:")
    print("      models:")
    print("        use_local: true")
    print("        local_path: 'models/yolov11n-320.onnx'")
    print("\n   2. Reiniciar el pipeline")

    return 0 if not failed_models else 1


if __name__ == "__main__":
    sys.exit(main())
