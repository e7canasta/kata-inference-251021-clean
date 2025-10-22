# Adeline Test Suite

Property-based tests para invariantes críticas del sistema.

## Filosofía de Testing

**NO buscamos 100% coverage** → Enfoque en:
1. **Invariantes** (properties que siempre deben ser true)
2. **Critical paths** (MQTT commands, pipeline lifecycle)
3. **Edge cases conocidos** (división por cero, bounds checking)

**Pair programming sigue siendo válido** para integration testing manual.

---

## Setup

### 1. Instalar dependencias

```bash
pip install -r requirements.txt
```

Esto instala:
- `pytest>=7.0.0` - Test framework
- `pytest-cov>=4.0.0` - Coverage reporting (opcional)

### 2. Verificar instalación

```bash
pytest --version
```

---

## Ejecutar Tests

### Todos los tests

```bash
pytest
```

### Tests por módulo

```bash
# ROI tests
pytest tests/test_roi.py

# MQTT commands tests
pytest tests/test_mqtt_commands.py

# Stabilization tests
pytest tests/test_stabilization.py
```

### Tests por marker

```bash
# Solo unit tests (rápidos)
pytest -m unit

# Solo integration tests
pytest -m integration

# Tests de ROI
pytest -m roi

# Tests de MQTT
pytest -m mqtt

# Tests de stabilization
pytest -m stabilization
```

### Modo verbose

```bash
pytest -v
```

### Con coverage

```bash
pytest --cov=adeline --cov-report=term-missing
```

---

## Estructura de Tests

```
tests/
├── __init__.py              # Test suite documentation
├── README.md                # Este archivo
├── test_roi.py              # ROI invariants (square, expand, bounds)
├── test_mqtt_commands.py    # MQTT control commands (stop, pause, resume)
├── test_stabilization.py    # Stabilization logic (hysteresis, IoU, temporal)
└── test_config_validation.py # Pydantic config validation
```

---

## Test Coverage

### test_roi.py (ROI Invariantes)

**Clases de prueba:**
- `TestROIBoxSquareInvariant` - Invariante: cuadrado se mantiene cuadrado
- `TestROIBoxBoundsInvariant` - Invariante: respeta límites del frame
- `TestROIBoxProperties` - Propiedades calculadas (width, height, area)
- `TestROIBoxEdgeCases` - Edge cases (min/max multiple, zero margin)

**Invariantes testeadas:**
- ✅ `make_square_multiple()` → siempre cuadrado
- ✅ `expand(preserve_square=True)` → mantiene cuadrado
- ✅ `smooth_with()` con inputs cuadrados → output cuadrado
- ✅ `make_square_multiple()` → múltiplo de imgsz
- ✅ `expand()` → nunca excede frame bounds

**Total:** 18 tests

---

### test_mqtt_commands.py (MQTT Commands)

**Clases de prueba:**
- `TestCommandRegistry` - Registry básico (register, execute, is_available)
- `TestConditionalCommands` - Comandos condicionales (toggle_crop, stabilization_stats)
- `TestCommandInvariants` - Invariantes de comandos (STOP activa shutdown_event)
- `TestCommandEdgeCases` - Edge cases

**Invariantes testeadas:**
- ✅ Comando registrado se ejecuta correctamente
- ✅ Comando no registrado lanza `CommandNotAvailableError`
- ✅ `toggle_crop` solo disponible si `handler.supports_toggle == True`
- ✅ `stabilization_stats` solo disponible si `stabilizer is not None`
- ✅ Comando `STOP` activa `shutdown_event` (CRÍTICO)

**Total:** 13 tests

---

### test_stabilization.py (Stabilization Logic)

**Clases de prueba:**
- `TestIoUCalculation` - IoU matching (spatial)
- `TestHysteresisFiltering` - Hysteresis (appear/persist thresholds)
- `TestTemporalTracking` - Temporal tracking (min_frames, max_gap)
- `TestIoUMatching` - Multi-object tracking (IoU distingue objetos)
- `TestNoOpStabilizer` - Baseline sin estabilización
- `TestStabilizationFactory` - Factory validation

**Invariantes testeadas:**
- ✅ IoU de bboxes idénticos = 1.0
- ✅ IoU sin overlap = 0.0
- ✅ IoU es simétrico: IoU(A, B) == IoU(B, A)
- ✅ Confidence < appear_conf → ignora
- ✅ Track confirmado usa persist_conf (más bajo)
- ✅ Requiere min_frames consecutivos para confirmar
- ✅ Tolera max_gap frames sin detección
- ✅ IoU matching distingue múltiples objetos de misma clase

**Total:** 22 tests

---

### test_config_validation.py (Config Validation)

**Clases de prueba:**
- `TestModelsSettingsValidation` - Validación de settings de modelos
- `TestHysteresisValidation` - Validación de hysteresis (persist <= appear)
- `TestFixedROIValidation` - Validación de bounds de Fixed ROI
- `TestAdaptiveROIValidation` - Validación de Adaptive ROI
- `TestAdelineConfigDefaults` - Config por defecto es válida
- `TestConfigFromDict` - Construcción desde dict/YAML
- `TestConfigValidationErrors` - Mensajes de error claros

**Invariantes testeadas:**
- ✅ imgsz debe ser múltiplo de 32 (YOLO requirement)
- ✅ Confidence y IoU thresholds en [0.0, 1.0]
- ✅ persist_confidence <= appear_confidence (hysteresis)
- ✅ x_min < x_max, y_min < y_max (fixed ROI bounds)
- ✅ min_roi_multiple <= max_roi_multiple
- ✅ Config por defecto es válida (puede arrancar sin YAML)
- ✅ Mensajes de error claros para valores inválidos

**Total:** 20 tests

---

## Markers

Los tests usan markers para categorización:

```python
@pytest.mark.unit          # Unit test (rápido, aislado)
@pytest.mark.integration   # Integration test (puede requerir recursos externos)
@pytest.mark.slow          # Test lento (skip con -m "not slow")
@pytest.mark.roi           # Test de ROI
@pytest.mark.mqtt          # Test de MQTT
@pytest.mark.stabilization # Test de stabilization
```

### Ejemplos de uso

```bash
# Solo unit tests (rápidos)
pytest -m unit

# Skip slow tests
pytest -m "not slow"

# Solo tests de ROI + stabilization
pytest -m "roi or stabilization"
```

---

## Type Checking con mypy

Adeline usa mypy para type checking estático.

### Ejecutar mypy

```bash
# Check todo el codebase
mypy . --config-file mypy.ini

# Check archivo específico
mypy adeline/config/schemas.py

# Con output más detallado
mypy . --config-file mypy.ini --show-error-context
```

### Configuración

Ver `mypy.ini` para configuración completa.

**Strictness gradual:**
- `config/schemas.py` - Full strictness (disallow_untyped_defs)
- `control/registry.py` - Full strictness (critical path)
- `inference/roi/adaptive.py` - Moderate strictness
- Otros archivos - Gradual typing (check_untyped_defs)

**Ignorados (no stubs disponibles):**
- `inference.*` - Roboflow SDK
- `supervision.*` - Supervision library
- `cv2.*` - OpenCV
- `paho.mqtt.*` - Paho MQTT

---

## Validation Script

Script todo-en-uno para validar codebase:

```bash
# Full validation (type checking + tests + config)
./scripts/validate.sh

# Fast mode (solo unit tests)
./scripts/validate.sh --fast
```

El script ejecuta:
1. mypy type checking
2. pytest tests
3. Config validation (si existe config.yaml)

---

## Testing Manual (Pair Programming)

Los tests automatizados complementan (no reemplazan) el testing manual:

### Compilación

```bash
python -m py_compile adeline/inference/roi/adaptive.py
python -m py_compile adeline/inference/stabilization/core.py
```

### Testing de campo

Ver `TEST_CASES_FUNCIONALES.md` para escenarios de testing con actores.

---

## CI/CD (Futuro)

Para integrar en CI, agregar a `.github/workflows/test.yml`:

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.10'
      - run: pip install -r requirements.txt
      - run: pytest -v --cov=adeline
```

---

## Troubleshooting

### ImportError: No module named 'inference'

Instalar dependencias:
```bash
pip install -r requirements.txt
```

### ImportError: cannot import name 'ROIBox'

Verificar que estás en el directorio correcto:
```bash
cd /path/to/adeline
pytest
```

O instalar el paquete en modo editable:
```bash
pip install -e .
```

### Tests pasan pero warnings de deprecation

Agregar a pytest.ini:
```ini
addopts = --disable-warnings
```

---

## Contribuir

Al agregar nuevos tests:

1. **Focus en invariantes**, no en implementación
2. **Usar markers** apropiados (`@pytest.mark.unit`, etc)
3. **Documentar** qué invariante se testea
4. **Nombres descriptivos**: `test_<property>_<scenario>`

Ejemplo:
```python
@pytest.mark.unit
@pytest.mark.roi
def test_expand_preserves_square_multiple_margins(self):
    """
    Invariante: expand() preserva cuadrado para diferentes márgenes.
    """
    # ...
```

---

## Referencias

- [pytest documentation](https://docs.pytest.org/)
- [Property-based testing](https://hypothesis.works/articles/what-is-property-based-testing/)
- `PLAN_MEJORAS.md` - Roadmap de mejoras (testing es Tarea #2)
