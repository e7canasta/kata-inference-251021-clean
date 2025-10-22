# Migration Guide - Nueva Estructura de Paquetes

## 📦 Estructura Reorganizada

El módulo `adeline` ha sido reorganizado por capas según el diseño 4+1 (ver DESIGN.md).

## ⚡ Nuevos Comandos

### Pipeline Principal

**Antes:**
```bash
python quickstart/inference/run_pipeline_mqtt.py
```

**Ahora:**
```bash
python -m adeline
# o
uv run python -m adeline
```

### Control CLI

**Antes:**
```bash
python -m quickstart.inference.mqtt_control_cli {pause|resume|stop|status}
```

**Ahora:**
```bash
python -m adeline.control.cli {pause|resume|stop|status|metrics|toggle_crop|stabilization_stats}
# o
uv run python -m adeline.control.cli stop
```

### Data Monitors

**Antes:**
```bash
python quickstart/inference/mqtt_data_monitor.py
python quickstart/inference/mqtt_status_monitor.py
```

**Ahora:**
```bash
# Data monitor
python -m adeline.data.monitors data

# Status monitor
python -m adeline.data.monitors status
```

## 📂 Imports Actualizados

### Antes (estructura flat):
```python
from quickstart.inference.mqtt_bridge import MQTTControlPlane, MQTTDataPlane
from quickstart.inference.roi_strategies import ROIStrategyConfig
from quickstart.inference.detection_stabilization import TemporalHysteresisStabilizer
```

### Ahora (estructura por capas):
```python
# Public API (recomendado)
from adeline import (
    PipelineConfig,
    InferencePipelineController,
    MQTTControlPlane,
    MQTTDataPlane,
)

# O imports internos específicos
from adeline.control import MQTTControlPlane
from adeline.data import MQTTDataPlane, create_mqtt_sink
from adeline.inference.roi import ROIStrategyConfig, validate_and_create_roi_strategy
from adeline.inference.stabilization import TemporalHysteresisStabilizer
from adeline.visualization import create_visualization_sink
```

## 🗂️ Mapeo de Archivos

| Archivo Anterior | Ubicación Nueva |
|-----------------|-----------------|
| `run_pipeline_mqtt.py` | `app/controller.py` + `__main__.py` |
| `mqtt_bridge.py` | `control/plane.py` + `data/plane.py` + `data/sinks.py` |
| `mqtt_control_cli.py` | `control/cli.py` + `control/__main__.py` |
| `mqtt_data_monitor.py` | `data/monitors/data_monitor.py` |
| `mqtt_status_monitor.py` | `data/monitors/status_monitor.py` |
| `roi_strategies.py` + `adaptive_roi.py` | `inference/roi/{base,adaptive,fixed}.py` |
| `detection_stabilization.py` | `inference/stabilization/core.py` |
| `local_models.py` | `inference/models.py` |
| `visualization.py` | `visualization/sinks.py` |

## 🔄 Backward Compatibility

Los archivos originales están en `_archive/` para referencia, pero **no se deben usar** ya que tienen imports incorrectos.

## ✅ Testing

Verifica que todo funcione:

```bash
# Test imports
python -c "from adeline import PipelineConfig; print('✅ Imports OK')"

# Test pipeline
python -m adeline  # Debería conectar a MQTT y empezar

# Test control (en otra terminal)
python -m adeline.control.cli status
```
