# Análisis de Modularización - Sesión Whiteboard
**Fecha:** 2025-10-22
**Participantes:** Ernesto (Visiona) + Gaby (AI Companion)
**Objetivo:** Analizar bounded contexts y proponer modularización para mejorar cohesión/acoplamiento

---

## 📋 Contexto

**Score actual:** 9.0/10 (post-refactoring v2.1)

**Archivos candidatos:**
1. `inference/roi/adaptive.py` - 804 líneas
2. `inference/stabilization/core.py` - 594 líneas
3. `app/controller.py` - 475 líneas

**Pregunta clave:**
¿La longitud de estos archivos refleja **cohesión monolítica** (un solo concepto) o **múltiples bounded contexts** que merecen separación?

---

## 🔍 ANÁLISIS #1: adaptive.py (804 líneas)

### Estado Actual: Mapa de Conceptos

```
┌─────────────────────────────────────────────────────────────┐
│                    adaptive.py (804L)                       │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  [1] ROI GEOMETRY (lines 50-237)                           │
│      - ROIBox dataclass                                    │
│      - expand(), smooth_with(), make_square_multiple()    │
│      - Conceptos: cuadrados, múltiplos, clipping          │
│      🔹 Dominio: Geometría 2D + invariantes de forma       │
│                                                             │
│  [2] ROI STATE MANAGEMENT (lines 240-387)                  │
│      - ROIState class                                      │
│      - _roi_by_source: Dict[int, ROIBox]                  │
│      - update_from_detections(), reset()                  │
│      🔹 Dominio: Gestión de estado temporal por source     │
│                                                             │
│  [3] FRAME PROCESSING (lines 390-502)                      │
│      - crop_frame_if_roi() - NumPy views                  │
│      - transform_predictions_vectorized()                 │
│      - convert_predictions_to_sv_detections()             │
│      🔹 Dominio: Transformaciones de frames/coordenadas    │
│                                                             │
│  [4] INFERENCE PIPELINE (lines 547-681)                    │
│      - adaptive_roi_inference() - orquestación            │
│      - Flow: get_roi → crop → infer → transform → metrics │
│      🔹 Dominio: Orquestación de inferencia                │
│                                                             │
│  [5] SINK INTEGRATION (lines 683-721)                      │
│      - roi_update_sink() - callback para updates          │
│      🔹 Dominio: Integración con pipeline                  │
│                                                             │
│  [6] HANDLER (MUTABLE INTERFACE) (lines 723-804)           │
│      - AdaptiveInferenceHandler - callable wrapper        │
│      - enable(), disable(), supports_toggle               │
│      🔹 Dominio: Interface adaptador para InferencePipeline│
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Análisis de Cohesión/Acoplamiento

| Concepto | Cohesión | Acoplamiento | ¿Independiente? |
|----------|----------|--------------|-----------------|
| **ROI Geometry** | ⭐⭐⭐⭐⭐ Alta (solo geometría) | ⭐⭐⭐⭐⭐ Bajo (no depende de nadie) | ✅ SÍ |
| **ROI State** | ⭐⭐⭐⭐ Alta (gestión de estado) | ⭐⭐⭐ Medio (usa ROIBox) | ✅ SÍ |
| **Frame Processing** | ⭐⭐⭐⭐ Alta (transformaciones) | ⭐⭐⭐ Medio (usa ROIBox) | ✅ SÍ |
| **Inference Pipeline** | ⭐⭐⭐ Media (orquestación) | ⭐⭐ Alto (usa TODO) | ❌ NO |
| **Sink Integration** | ⭐⭐⭐⭐ Alta (sink específico) | ⭐⭐⭐ Medio (usa State + Frame) | ⚠️ TAL VEZ |
| **Handler** | ⭐⭐⭐⭐ Alta (interface adaptador) | ⭐⭐ Alto (usa Pipeline + State) | ❌ NO |

**Observaciones:**
- **Conceptos [1], [2], [3] son independientes** → Buenos candidatos para módulos
- **[4], [5], [6] son orquestación/integración** → Deben quedarse juntos (cohesión alta a nivel "feature")

---

## 🎯 Propuesta de Modularización: adaptive.py

### Opción A: Modularización por Bounded Context (DDD)

```
inference/roi/adaptive/
├── __init__.py                  # Exports públicos
├── geometry.py                  # [1] ROI Geometry (ROIBox + operaciones)
├── state.py                     # [2] ROI State Management (ROIState)
├── transforms.py                # [3] Frame Processing (crop, transform coords)
└── pipeline.py                  # [4,5,6] Inference Pipeline + Sink + Handler
```

**Beneficios:**
- ✅ Cada módulo = 1 bounded context (DDD puro)
- ✅ Fácil testing aislado (geometry sin mocks, state con fixture simple)
- ✅ Extensible: Agregar `geometry_3d.py` o `state_distributed.py` sin tocar existentes

**Trade-offs:**
- ⚠️ 4 archivos vs 1 (más navegación)
- ⚠️ Imports cruzados: `state.py` importa `geometry.py`, `pipeline.py` importa todos

**Justificación (DDD):**
- **Geometry**: Bounded context "Shape Algebra" (operaciones sobre formas 2D)
- **State**: Bounded context "Temporal ROI Tracking" (historial por source)
- **Transforms**: Bounded context "Coordinate Space Mapping" (frame ↔ crop ↔ model)
- **Pipeline**: Bounded context "Inference Orchestration" (flow end-to-end)

---

### Opción B: Modularización por Capa (Hexagonal Architecture)

```
inference/roi/adaptive/
├── __init__.py
├── domain.py                    # [1,2] Entities + Logic pura (ROIBox, ROIState)
├── infrastructure.py            # [3] I/O + Transformaciones (crop, NumPy ops)
└── application.py               # [4,5,6] Use Cases (pipeline, handler)
```

**Beneficios:**
- ✅ Separación por "pureza": domain sin I/O, infrastructure con NumPy/CV2
- ✅ Testeable: domain con property tests, infrastructure con integration tests
- ✅ 3 archivos (menos overhead que Opción A)

**Trade-offs:**
- ⚠️ Mezcla conceptos: `domain.py` tiene tanto Geometry como State (menos granular)
- ⚠️ Menos extensible: Agregar nuevo dominio requiere modificar `domain.py`

**Justificación (Hexagonal):**
- **Domain**: Lógica de negocio pura (ROI rules, invariantes)
- **Infrastructure**: Detalles técnicos (NumPy, CV2, VideoFrame)
- **Application**: Orquestación y use cases

---

### Opción C: Modularización Híbrida (Pragmática)

```
inference/roi/adaptive/
├── __init__.py                  # Exports públicos
├── geometry.py                  # [1] ROI Geometry (ROIBox)
├── state.py                     # [2] ROI State (ROIState)
└── pipeline.py                  # [3,4,5,6] TODO LO DEMÁS
```

**Beneficios:**
- ✅ Extrae lo más reutilizable (geometry, state)
- ✅ Solo 3 archivos (overhead mínimo)
- ✅ Fácil refactor incremental: empezar por geometry, luego state

**Trade-offs:**
- ⚠️ `pipeline.py` sigue siendo grande (~500 líneas)
- ⚠️ Mezcla transforms + orquestación en mismo archivo

**Justificación (KISS):**
- Geometry y State son claramente independientes → Separar
- Transforms, Pipeline, Sink, Handler están fuertemente acoplados → Dejar juntos

---

## 🔍 ANÁLISIS #2: stabilization/core.py (594 líneas)

### Estado Actual: Mapa de Conceptos

```
┌─────────────────────────────────────────────────────────────┐
│              stabilization/core.py (594L)                   │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  [1] CONFIGURATION (lines 38-60)                            │
│      - StabilizationConfig dataclass                       │
│      🔹 Dominio: Configuration schema                      │
│                                                             │
│  [2] TRACKING STATE (lines 62-115)                          │
│      - DetectionTrack dataclass                            │
│      - Lifecycle: TRACKING → CONFIRMED → REMOVED          │
│      🔹 Dominio: State machine de detecciones              │
│                                                             │
│  [3] IoU MATCHING (lines 117-172)                           │
│      - calculate_iou() - pure function                     │
│      🔹 Dominio: Geometría de matching                     │
│                                                             │
│  [4] BASE STABILIZER (ABC) (lines 174-225)                  │
│      - BaseDetectionStabilizer                             │
│      - Interface: process(), reset(), get_stats()          │
│      🔹 Dominio: Strategy pattern interface                │
│                                                             │
│  [5] TEMPORAL+HYSTERESIS STRATEGY (lines 227-511)           │
│      - TemporalHysteresisStabilizer                        │
│      - Algoritmo complejo: matching, tracking, hysteresis │
│      🔹 Dominio: Implementación concreta de estrategia     │
│                                                             │
│  [6] NOOP STRATEGY (lines 513-537)                          │
│      - NoOpStabilizer (baseline)                           │
│      🔹 Dominio: Null Object pattern                       │
│                                                             │
│  [7] FACTORY (lines 539-604)                                │
│      - create_stabilization_strategy()                     │
│      - Validación + construcción                          │
│      🔹 Dominio: Factory pattern                           │
│                                                             │
│  [8] SINK WRAPPER (lines 606-680)                           │
│      - create_stabilization_sink()                         │
│      - Decorator pattern para sinks                        │
│      🔹 Dominio: Integration con pipeline                  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Análisis de Cohesión/Acoplamiento

| Concepto | Cohesión | Acoplamiento | ¿Independiente? |
|----------|----------|--------------|-----------------|
| **Configuration** | ⭐⭐⭐⭐⭐ Alta | ⭐⭐⭐⭐⭐ Bajo (sin deps) | ✅ SÍ |
| **Tracking State** | ⭐⭐⭐⭐⭐ Alta | ⭐⭐⭐⭐⭐ Bajo (sin deps) | ✅ SÍ |
| **IoU Matching** | ⭐⭐⭐⭐⭐ Alta (pure) | ⭐⭐⭐⭐⭐ Bajo (sin deps) | ✅ SÍ |
| **Base Stabilizer** | ⭐⭐⭐⭐⭐ Alta (ABC) | ⭐⭐⭐⭐⭐ Bajo (sin deps) | ✅ SÍ |
| **Temporal Strategy** | ⭐⭐⭐⭐ Alta | ⭐⭐⭐ Medio (usa IoU + Track) | ✅ SÍ |
| **NoOp Strategy** | ⭐⭐⭐⭐⭐ Alta | ⭐⭐⭐⭐ Bajo (solo ABC) | ✅ SÍ |
| **Factory** | ⭐⭐⭐⭐ Alta | ⭐⭐⭐ Medio (usa Config + Strategies) | ⚠️ TAL VEZ |
| **Sink Wrapper** | ⭐⭐⭐⭐ Alta | ⭐⭐⭐ Medio (usa Base + callable) | ⚠️ TAL VEZ |

**Observaciones:**
- **Todos los conceptos tienen cohesión alta** ✅
- **Acoplamiento es mayormente bajo/medio** ✅
- **¿Problema?** No, pero la separación ayudaría a:
  - Testing aislado (IoU con property tests)
  - Extensibilidad (agregar nuevas estrategias sin tocar core)

---

## 🎯 Propuesta de Modularización: stabilization/

### Opción A: Modularización por Capa (Estrategia + Infraestructura)

```
inference/stabilization/
├── __init__.py                  # Exports públicos
├── base.py                      # [4] Base ABC + [1] Config
├── matching.py                  # [3] IoU + matching utilities
├── tracking.py                  # [2] DetectionTrack + state machine
├── strategies/
│   ├── __init__.py
│   ├── noop.py                  # [6] NoOpStabilizer
│   └── temporal_hysteresis.py   # [5] TemporalHysteresisStabilizer
├── factory.py                   # [7] create_stabilization_strategy()
└── integration.py               # [8] create_stabilization_sink()
```

**Beneficios:**
- ✅ Estrategias en módulos separados (fácil agregar nuevas)
- ✅ Utilities (IoU, Track) reutilizables
- ✅ Modular testing: property tests en `matching.py`, state machine tests en `tracking.py`

**Trade-offs:**
- ⚠️ 7 archivos vs 1 (overhead de navegación)
- ⚠️ Posible over-engineering para 2 estrategias (NoOp + Temporal)

---

### Opción B: Modularización Pragmática (Estrategias + Core)

```
inference/stabilization/
├── __init__.py                  # Exports públicos
├── core.py                      # [1,2,3,4] Config, Track, IoU, Base ABC
├── strategies.py                # [5,6] Temporal + NoOp
└── factory.py                   # [7,8] Factory + Sink wrapper
```

**Beneficios:**
- ✅ Solo 3 archivos (minimal overhead)
- ✅ Agrupa utilities/base en `core.py` (cohesión por "fundamentos")
- ✅ Estrategias juntas (fácil comparar implementaciones)

**Trade-offs:**
- ⚠️ `strategies.py` podría crecer si agregamos más estrategias (pero manejable)

---

### Opción C: Modularización Incremental (Extraer solo Matching)

```
inference/stabilization/
├── __init__.py
├── matching.py                  # [3] IoU + spatial utils (reutilizable)
└── core.py                      # [1,2,4,5,6,7,8] TODO LO DEMÁS
```

**Beneficios:**
- ✅ Extrae solo lo más reutilizable (IoU matching)
- ✅ Solo 2 archivos (minimal disruption)
- ✅ `matching.py` puede usarse desde ROI adaptive (shared utility)

**Trade-offs:**
- ⚠️ `core.py` sigue siendo grande (~550 líneas)

---

## 🔍 ANÁLISIS #3: app/controller.py (475 líneas)

### Estado Actual: Mapa de Conceptos

```
┌─────────────────────────────────────────────────────────────┐
│                  app/controller.py (475L)                   │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  [1] IMPORTS + LAZY LOADING (lines 1-44)                    │
│      - InferenceLoader, imports de internal modules        │
│      🔹 Dominio: Setup de dependencias                     │
│                                                             │
│  [2] CONTROLLER INITIALIZATION (lines 55-88)                │
│      - __init__() - setup de atributos                     │
│      🔹 Dominio: State initialization                      │
│                                                             │
│  [3] PIPELINE SETUP (lines 89-191)                          │
│      - setup() - orquestación de construcción              │
│      - Data/Control plane, Builder, Pipeline init         │
│      🔹 Dominio: Bootstrapping + wiring                    │
│                                                             │
│  [4] CONTROL CALLBACKS (lines 193-341)                      │
│      - _setup_control_callbacks()                          │
│      - Handlers: pause, resume, stop, status, metrics, etc │
│      🔹 Dominio: Command handling (Control Plane)          │
│                                                             │
│  [5] LIFECYCLE MANAGEMENT (lines 342-394)                   │
│      - run() - main loop                                   │
│      - Signal handling (Ctrl+C)                            │
│      🔹 Dominio: Event loop + graceful shutdown            │
│                                                             │
│  [6] CLEANUP (lines 395-441)                                │
│      - cleanup() - resource cleanup                        │
│      🔹 Dominio: Teardown + disconnect                     │
│                                                             │
│  [7] MAIN ENTRY POINT (lines 443-475)                       │
│      - main() - config load + logging setup                │
│      🔹 Dominio: Application bootstrap                     │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Análisis de Cohesión/Acoplamiento

| Concepto | Cohesión | Acoplamiento | ¿Independiente? |
|----------|----------|--------------|-----------------|
| **Imports** | ⭐⭐⭐ Media | ⭐⭐⭐⭐⭐ Bajo | ✅ SÍ (pero trivial) |
| **Initialization** | ⭐⭐⭐⭐⭐ Alta | ⭐⭐⭐⭐ Bajo | ❌ NO (parte de Controller) |
| **Pipeline Setup** | ⭐⭐⭐⭐ Alta | ⭐⭐ Alto (usa Builder + Planes) | ⚠️ TAL VEZ |
| **Control Callbacks** | ⭐⭐⭐ Media | ⭐⭐⭐ Medio (usa Pipeline + Planes) | ⚠️ TAL VEZ |
| **Lifecycle** | ⭐⭐⭐⭐⭐ Alta | ⭐⭐⭐ Medio (usa setup + cleanup) | ❌ NO (parte de Controller) |
| **Cleanup** | ⭐⭐⭐⭐⭐ Alta | ⭐⭐⭐ Medio (usa Pipeline + Planes) | ❌ NO (parte de Controller) |
| **Main** | ⭐⭐⭐⭐⭐ Alta | ⭐⭐⭐⭐ Bajo | ✅ SÍ |

**Observaciones:**
- **Controller.py es un "Application Service" (DDD)** → Orquesta todo el lifecycle
- **No es monolítico por error, es monolítico por diseño** (un solo feature: "run app")
- **¿Modularizar?** Posible, pero **trade-off cuestionable**

---

## 🎯 Propuesta de Modularización: controller.py

### Opción A: Modularización por Responsabilidad (SRP)

```
app/
├── __init__.py
├── main.py                      # [7] Entry point + logging setup
├── controller.py                # [2,5,6] Lifecycle + orchestration
├── setup.py                     # [3] Pipeline setup (wiring)
└── commands.py                  # [4] Control callbacks (command handlers)
```

**Beneficios:**
- ✅ Separación clara: bootstrapping, orchestration, command handling
- ✅ `commands.py` testeable en aislación (mock pipeline)

**Trade-offs:**
- ⚠️ **Cohesión cuestionable:** Setup y Controller están fuertemente acoplados
- ⚠️ Fragmenta un feature cohesivo (application lifecycle)

---

### Opción B: Extraer solo Commands (Minimal)

```
app/
├── __init__.py
├── commands.py                  # [4] Control callbacks
└── controller.py                # [1,2,3,5,6,7] TODO LO DEMÁS
```

**Beneficios:**
- ✅ Extrae solo lo más testeable (command handlers)
- ✅ Minimal disruption (2 archivos)

**Trade-offs:**
- ⚠️ `controller.py` sigue grande (~350 líneas)

---

### Opción C: No modularizar (Keep as-is)

**Justificación:**
- ✅ Controller es un **Application Service cohesivo** (DDD pattern)
- ✅ 475 líneas para un application service completo es **razonable**
- ✅ Modularizar podría **romper cohesión** (setup/cleanup dependen de state compartido)

---

## 🎯 RECOMENDACIÓN FINAL: Plan de Modularización Incremental

### Prioridad 1: adaptive.py (Alto impacto, bajo riesgo)

**Elegir Opción C (Híbrida):**
```
inference/roi/adaptive/
├── __init__.py                  # Re-exports (API pública sin cambios)
├── geometry.py                  # ROIBox + operaciones
├── state.py                     # ROIState
└── pipeline.py                  # Resto (transforms, pipeline, handler)
```

**Justificación:**
- ✅ Extrae bounded contexts claros (Geometry, State)
- ✅ Minimal overhead (3 archivos)
- ✅ Fácil rollback (solo mover código)
- ✅ Habilita property tests aislados en `geometry.py`

**Estimación:** 2-3 horas

---

### Prioridad 2: stabilization/core.py (Medio impacto, bajo riesgo)

**Elegir Opción C (Incremental):**
```
inference/stabilization/
├── __init__.py
├── matching.py                  # IoU + spatial utilities (reutilizable)
└── core.py                      # TODO LO DEMÁS
```

**Justificación:**
- ✅ Extrae utility más reutilizable (IoU)
- ✅ Puede usarse desde ROI adaptive (shared utility)
- ✅ Minimal disruption (2 archivos)

**Estimación:** 1-2 horas

---

### Prioridad 3: controller.py (Bajo impacto, evaluar necesidad)

**Opción recomendada: NO MODULARIZAR (por ahora)**

**Justificación:**
- ✅ Controller es Application Service cohesivo (DDD)
- ✅ 475 líneas es razonable para un service completo
- ⚠️ Modularizar podría romper cohesión sin beneficio claro

**Alternativa (si crece a 700+ líneas):**
```
app/
├── main.py                      # Entry point + config
├── controller.py                # Lifecycle + orchestration
└── commands.py                  # Command handlers
```

---

## 🎨 Diagrama de Dependencias (Post-Modularización)

### Antes (Actual)
```
┌──────────────┐
│ adaptive.py  │ (804L - monolítico)
└──────────────┘
       ↓
  [todo mezclado]
```

### Después (Propuesta)
```
┌──────────────────────────────────────┐
│   inference/roi/adaptive/            │
├──────────────────────────────────────┤
│                                      │
│  ┌─────────────┐                    │
│  │ geometry.py │  (ROIBox)          │
│  └─────────────┘                    │
│         ↑                            │
│  ┌─────────────┐                    │
│  │  state.py   │  (ROIState)        │
│  └─────────────┘                    │
│         ↑                            │
│  ┌─────────────┐                    │
│  │ pipeline.py │  (orchestration)   │
│  └─────────────┘                    │
│                                      │
└──────────────────────────────────────┘
         ↑
    [clean deps]
```

---

## 📊 Evaluación de Trade-offs

| Aspecto | Antes (Monolítico) | Después (Modular) |
|---------|-------------------|-------------------|
| **Grep/búsqueda** | ⭐⭐⭐⭐⭐ Todo en 1 archivo | ⭐⭐⭐ Buscar en 3 archivos |
| **Navegación IDE** | ⭐⭐ 804 líneas scroll | ⭐⭐⭐⭐ Archivos pequeños |
| **Testing aislado** | ⭐⭐ Mocks pesados | ⭐⭐⭐⭐⭐ Tests puros (geometry) |
| **Extensibilidad** | ⭐⭐⭐ Modificar monolito | ⭐⭐⭐⭐⭐ Agregar módulo nuevo |
| **Cohesión** | ⭐⭐⭐ Conceptos mezclados | ⭐⭐⭐⭐⭐ 1 módulo = 1 concepto |
| **Acoplamiento** | ⭐⭐⭐ Implícito (mismo file) | ⭐⭐⭐⭐ Explícito (imports) |
| **Complejidad mental** | ⭐⭐⭐ 804L para entender | ⭐⭐⭐⭐ 3 archivos ~250L c/u |

**Balance:** Modularización mejora **cohesión, extensibilidad, testing** a cambio de **navegación multi-archivo**.

---

## 🚀 Plan de Ejecución (Incremental)

### Fase 1: Refactor adaptive.py (1 día)
1. Crear `inference/roi/adaptive/` package
2. Mover `ROIBox` + métodos → `geometry.py`
3. Mover `ROIState` → `state.py`
4. Resto → `pipeline.py`
5. Ajustar imports en `__init__.py` (mantener API pública)
6. **Testing:** Compilación + tests existentes pasan

### Fase 2: Refactor stabilization/core.py (medio día)
1. Crear `inference/stabilization/matching.py`
2. Mover `calculate_iou()` → `matching.py`
3. Ajustar imports en `core.py`
4. **Testing:** Compilación + tests existentes pasan

### Fase 3: Property Tests (post-refactor) (1 día)
1. Agregar property tests en `test_geometry.py`
2. Agregar property tests en `test_matching.py`

### Fase 4: Evaluación controller.py (TBD)
- Revisar después de Fase 1-3
- Decisión basada en: ¿Creció? ¿Hay nueva complejidad?

---

## 📝 Criterios de Éxito

1. **Compilación limpia:** Sin errores de import
2. **Tests pasan:** Suite completa (95 tests) sigue en verde
3. **API pública sin cambios:** `from inference.roi.adaptive import AdaptiveInferenceHandler` sigue funcionando
4. **Cohesión mejorada:** Cada módulo tiene 1 responsabilidad clara
5. **Extensibilidad habilitada:** Fácil agregar `geometry_3d.py` o `matching_kf.py` (Kalman Filter)

---

## 🤔 Preguntas para Decisión

1. **¿Preferís Opción A, B o C para adaptive.py?**
   - Mi recomendación: **Opción C (Híbrida)** - Balance óptimo

2. **¿Modularizar controller.py ahora o posponer?**
   - Mi recomendación: **Posponer** - No hay problema claro que resolver

3. **¿Priorizar property tests en Fase 3?**
   - Beneficio: Validar invariantes de `geometry.py` y `matching.py`
   - Costo: 1 día adicional

4. **¿Tiempo disponible para este refactor?**
   - Estimación total: **2-3 días** (Fase 1+2+3)
   - Mínimo viable: **1 día** (solo Fase 1+2, sin property tests)

---

**¿Qué te parece, Ernesto? ¿Seguimos con la Opción C para adaptive.py?**
