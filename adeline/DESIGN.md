# Complejidad por Diseño - Adeline

## Principio Core

**La complejidad se ataca por diseño, no por código complicado.**

## Estrategias de Diseño

### 1. Separación de Responsabilidades

```
Control Plane (QoS 1)     Data Plane (QoS 0)
     ↓                           ↓
  Comandos                  Detecciones
  Confiable                 Performance
     ↓                           ↓
Pipeline Controller
     ↓
InferencePipeline
```

**Beneficio**: Cada plano tiene garantías propias. Control es confiable, Data es rápido.

### 2. Factory Pattern para Variabilidad

```python
# ROI Strategy
roi_mode = "none" | "adaptive" | "fixed"
strategy = create_roi_strategy(mode)

# Stabilization Strategy
stabilization_mode = "none" | "temporal"
stabilizer = create_stabilization_strategy(mode)
```

**Beneficio**: Agregar nuevas estrategias sin tocar código existente. La complejidad está en elegir, no en implementar.

### 3. Configuration-Driven Behavior

```yaml
# Toda la lógica de negocio está en config, no hardcoded
roi_strategy:
  mode: adaptive
  adaptive:
    margin: 0.2
    smoothing: 0.3
```

**Beneficio**: Cambiar comportamiento sin recompilar. La complejidad está en el diseño del config schema.

### 4. Initialization Order Matter

```python
# 1. Deshabilitar modelos pesados ANTES de imports
disable_models_from_config()

# 2. AHORA importar inference
from inference import InferencePipeline
```

**Beneficio**: Evitar warnings y cargas innecesarias. La complejidad está en el orden, que es explícito.

### 5. Multi-Sink Composition

```python
pipeline.on_prediction = multi_sink(
    mqtt_sink,        # Publicar vía MQTT
    visualization_sink # Mostrar en OpenCV
)
```

**Beneficio**: Composición funcional. Agregar sinks sin modificar pipeline. La complejidad está en la orquestación.

## Patrones Anti-Complejidad

### ✅ Hacer

- **Factory para variantes**: ROI strategies, stabilization strategies
- **Config para behavior**: Separar "qué hacer" de "cómo hacerlo"
- **Planes separados**: Control (confiable) vs Data (performance)
- **Composition over modification**: Multi-sink pattern

### ❌ Evitar

- **God objects**: Un objeto que hace todo
- **Hardcoded logic**: `if mode == "adaptive"` en 10 lugares
- **Tight coupling**: Control plane que publique datos
- **Magic initialization**: Imports que tienen side effects ocultos

## Decisiones de Diseño Clave

### Control vs Data Plane
**Problema**: MQTT único no diferencia criticidad
**Solución**: Dos planes, dos QoS, dos responsabilidades

### Factory para Strategies
**Problema**: ROI y stabilization tienen múltiples implementaciones
**Solución**: Factory pattern + config para elegir

### Config-Driven
**Problema**: Comportamiento hardcoded es inflexible
**Solución**: YAML config con validación temprana

### Model Disabling
**Problema**: Import de `inference` carga modelos pesados
**Solución**: Deshabilitar antes de import (orden explícito)

## Resultado

**Complejidad controlada**:
- Fácil agregar nuevas estrategias (factory)
- Fácil cambiar comportamiento (config)
- Fácil debuggear (separación clara)
- Fácil testear (cada componente aislado)

**Código simple, arquitectura sólida.**
