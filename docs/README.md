# Documentation Index
## KataInference - Computer Vision Pipeline

**Última Actualización:** 2025-10-21

---

## 📚 Documentos Disponibles

### Architecture Documents

#### [Detection Stabilization](./architecture/DETECTION_STABILIZATION.md)
**Descripción:** Arquitectura completa del sistema de estabilización de detecciones.

**Contenido:**
- Problem Statement & Root Cause Analysis
- Solution Architecture (Strategy + Decorator patterns)
- Decisiones de Diseño (con rationale y alternatives rejected)
- Implementación FASE 1 (Temporal + Hysteresis)
- Roadmap FASE 2 & 3 (IoU Tracking, Confidence-weighted)
- Performance & Benchmarks (real world data)
- Testing Strategy (unit, integration, performance)
- Configuration Guide (parámetros de tuning)

**Status:** ✅ FASE 1 Implementada | 🚧 FASE 2 & 3 Planeadas

**Keywords:** Detection, Stabilization, Filtering, Hysteresis, Tracking, Computer Vision

---

### Project-Wide Architecture

#### [System Design (DESIGN.md)](../quickstart/inference/adeline/DESIGN.md)
**Descripción:** Vista 4+1 del sistema completo de inferencia MQTT.

**Contenido:**
- Vista Lógica (componentes)
- Vista de Proceso (concurrencia)
- Vista de Desarrollo (módulos)
- Vista Física (deployment)
- Escenarios (+1)
- Decisiones de Diseño Clave

**Status:** ✅ Completo (incluye Detection Stabilization en Sección 6)

---

## 🗂️ Estructura de Documentación

```
docs/
├── README.md                           # Este índice
└── architecture/
    └── DETECTION_STABILIZATION.md      # Arquitectura Detection Stabilization
```

---

## 📖 Guías Rápidas

### Para Nuevos Desarrolladores

1. **Start:** Leer [DESIGN.md](../quickstart/inference/adeline/DESIGN.md) (Secciones 1-5)
2. **Feature Deep-dive:** Leer [DETECTION_STABILIZATION.md](./architecture/DETECTION_STABILIZATION.md)
3. **Setup:** Seguir [CONFIG_README.md](../CONFIG_README.md) (si existe)

### Para Arquitectos

1. **System Overview:** [DESIGN.md](../quickstart/inference/adeline/DESIGN.md) - Vista 4+1 completa
2. **Feature Architecture:** [DETECTION_STABILIZATION.md](./architecture/DETECTION_STABILIZATION.md)
3. **Trade-offs:** Ver sección "Decisiones de Diseño" en ambos docs

### Para Usuarios Finales

1. **Configuration:** [config.yaml.example](../config.yaml.example) - Comentarios inline
2. **Tuning Guide:** [DETECTION_STABILIZATION.md § Configuration Guide](./architecture/DETECTION_STABILIZATION.md#configuration-guide)

---

## 🔄 Filosofía de Documentación

**Principios aplicados:**

1. **Complejidad por Diseño**
   - Documentar decisiones arquitectónicas con rationale
   - Incluir alternatives rejected (y por qué)
   - Trade-offs explícitos

2. **Documento Vivo**
   - Actualizar con cada fase implementada
   - Changelog con versiones
   - Status badges (✅ ⚠️ 🚧)

3. **Pair Programming**
   - Testing manual documentado
   - Casos de prueba concretos
   - Métricas reales (no estimadas)

4. **KISS**
   - Ejemplos concretos
   - Diagramas mermaid inline
   - Pseudo-code cuando ayuda

---

## 📝 Convenciones

### Status Badges

- ✅ **Implementado** - Feature completamente funcional
- ⚠️ **Experimental** - Funcional pero puede cambiar
- 🚧 **Planeado** - Diseño completo, pendiente implementación
- ❌ **Deprecated** - No usar, será eliminado

### Versionado

Documentos de arquitectura usan **semantic versioning**:
- **v1.0** - FASE 1 implementada
- **v2.0** - FASE 2 implementada (breaking changes)
- **v1.1** - Mejoras a FASE 1 (backwards compatible)

---

## 🤝 Contribuir

### Agregar Nueva Documentación

1. Crear documento en `docs/architecture/FEATURE_NAME.md`
2. Seguir template de `DETECTION_STABILIZATION.md`
3. Actualizar este índice (README.md)
4. Incluir:
   - Problem Statement
   - Solution Architecture
   - Decisiones de Diseño (con rationale)
   - Testing Strategy
   - Configuration Guide
   - Changelog

### Actualizar Documentación Existente

1. Modificar sección relevante
2. Actualizar fecha en header
3. Agregar entrada en Changelog
4. Incrementar versión si es breaking change

---

## 📧 Contacto

**Mantenedores:**
- Human (Product/Architecture)
- Claude Code (Implementation/Documentation)

**Feedback:** Pair programming sessions
