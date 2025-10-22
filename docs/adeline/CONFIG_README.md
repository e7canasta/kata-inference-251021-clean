# Configuración del Sistema de Inferencia

Este proyecto separa la configuración en dos archivos para mejor seguridad y mantenibilidad:

## Estructura de Configuración

```
.
├── config.yaml          # Configuración general (commitable)
├── .env                 # Secretos y credenciales (gitignored)
└── .env.example         # Template de .env (commitable)
```

## Setup Inicial

### 1. Configurar Variables de Entorno

```bash
# Copiar el template
cp .env.example .env

# Editar .env y agregar tu API key de Roboflow
# ROBOFLOW_API_KEY=tu_api_key_aqui
```

### 2. Configurar Parámetros del Pipeline

Editar `config.yaml` según tus necesidades:

```yaml
pipeline:
  rtsp_url: "rtsp://127.0.0.1:8554/live"
  model_id: "yolov11n-640"
  max_fps: 2
  enable_visualization: true
  display_statistics: true
```

## Archivos de Configuración

### `config.yaml` - Configuración General

Contiene todos los parámetros no sensibles del sistema:

**Pipeline:**
- `rtsp_url`: URL del stream RTSP (via go2rtc)
- `model_id`: Modelo YOLO a usar
- `max_fps`: FPS máximo de procesamiento
- `enable_visualization`: Mostrar ventana con detecciones
- `display_statistics`: Mostrar FPS y latencia en ventana

**MQTT:**
- `broker.host`: Hostname del broker MQTT
- `broker.port`: Puerto del broker
- `topics.*`: Topics para control y data plane
- `qos.*`: Quality of Service por plano

**Logging:**
- `level`: DEBUG | INFO | WARNING | ERROR | CRITICAL
- `format`: Formato de logs
- `paho_level`: Log level para biblioteca paho-mqtt

**Models:**
- `disabled`: Lista de modelos a deshabilitar (reduce startup time)

### `.env` - Secretos y Credenciales

**⚠️ Este archivo está en `.gitignore` y NO debe committearse**

Variables:
```bash
# Required
ROBOFLOW_API_KEY=your_api_key_here

# Optional (si tu broker MQTT requiere autenticación)
MQTT_USERNAME=
MQTT_PASSWORD=
```

## Obtener API Key de Roboflow

1. Crear cuenta en [Roboflow](https://app.roboflow.com/)
2. Ir a [Settings → API](https://app.roboflow.com/settings/api)
3. Copiar tu API key
4. Pegarla en `.env`:
   ```bash
   ROBOFLOW_API_KEY=tu_key_aqui
   ```

## Precedencia de Configuración

**Credenciales MQTT:**
1. Variables de entorno (`.env`) - **Prioridad más alta**
2. Valores en `config.yaml` - Fallback
3. `None` si no está en ninguno

**API Key:**
- Solo desde `.env` (requerido)

## Validación de Configuración

Testear que la configuración se carga correctamente:

```bash
.venv/bin/python -c "
from quickstart.inference.adeline.run_pipeline_mqtt import PipelineConfig
config = PipelineConfig()
print(f'API_KEY: {config.API_KEY[:10]}...')
print(f'MODEL_ID: {config.MODEL_ID}')
print(f'MQTT_BROKER: {config.MQTT_BROKER}')
"
```

Salida esperada:
```
✅ Config cargado correctamente
API_KEY: 5RumS6P942...
MODEL_ID: yolov11n-640
MQTT_BROKER: localhost
```

## ROI Strategy: resize_to_model Feature

El parámetro `resize_to_model` controla cómo se maneja el ROI cuando es más pequeño que el tamaño del modelo.

### Trade-off: Zoom vs. Padding

**`resize_to_model: false` (default) - Padding con negro:**
- Mantiene escala original de objetos
- Píxeles negros desperdiciados
- ✅ Mejor para: Detección de personas, vehículos (escala importa)

**`resize_to_model: true` - Resize/Zoom:**
- Aprovecha toda la resolución del modelo
- Cambia escala de objetos
- ✅ Mejor para: Objetos pequeños en zona específica (mesa con teléfonos)

### Ejemplo de Uso

```yaml
roi_strategy:
  mode: "fixed"

  fixed:
    x_min: 0.3
    y_min: 0.3
    x_max: 0.7
    y_max: 0.7

    # Zoom para mejor detección de objetos pequeños
    resize_to_model: true
```

**Caso de uso:**
- Cámara fija → mesa de trabajo (1920×1080)
- ROI fijo → zona de picking 400×400px
- Model → yolo11n-320 (320×320px)
- `true`: 400×400 → resize 320×320 (aprovecha resolución)
- `false`: 400×400 + padding → 320×320 (desperdicia píxeles)

## Configuraciones Comunes

### Producción (sin visualización)

```yaml
pipeline:
  enable_visualization: false
  display_statistics: false
  max_fps: 10

logging:
  level: "WARNING"
```

### Debugging

```yaml
pipeline:
  max_fps: 1
  display_statistics: true

logging:
  level: "DEBUG"
  paho_level: "DEBUG"
```

### High Performance

```yaml
pipeline:
  max_fps: 30
  enable_visualization: false

mqtt:
  qos:
    data: 0  # Fire and forget
```

## Troubleshooting

### Error: "ROBOFLOW_API_KEY not found"

```bash
# Verificar que .env existe
ls -la .env

# Verificar contenido (sin mostrar el key)
grep ROBOFLOW_API_KEY .env | cut -d'=' -f1
# Debería mostrar: ROBOFLOW_API_KEY
```

### Error: "Config file not found: config.yaml"

```bash
# Verificar que config.yaml está en la raíz del proyecto
ls -la config.yaml

# Si no existe, crear desde ejemplo
# (No hay ejemplo aún, usar el config.yaml actual)
```

### Warnings de modelos deshabilitados

Son esperados y pueden ignorarse. Los modelos listados en `config.yaml` bajo `models.disabled` no se cargarán.

## Seguridad

**✅ Commitear:**
- `config.yaml`
- `.env.example`
- `.gitignore`

**❌ NO Commitear:**
- `.env`
- Archivos con API keys
- Credenciales MQTT

El archivo `.gitignore` ya está configurado para proteger `.env`.
