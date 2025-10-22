# Manifiesto de Diseño - Visiona Team
**Para agentes de código (Claude) trabajando en este proyecto**

---

## Principio Central

> **"Un diseño limpio NO es un diseño complejo"**
>
> — Ernesto, durante refactor de adaptive.py (Oct 2025)

La simplicidad estructural no sacrifica claridad conceptual.
La modularidad bien aplicada **reduce** complejidad, no la aumenta.

---

## I. Complejidad por Diseño (No por Código)

**Atacar complejidad real, no imaginaria.**

### ✅ Hacer:
- Diseñar arquitectura que maneja complejidad inherente del dominio
- Separar bounded contexts cuando cohesión lo demanda
- Usar patterns (Factory, Builder, Strategy) para variabilidad conocida

### ❌ No hacer:
- Sobre-abstraer "por si acaso" (YAGNI)
- Crear capas de indirección sin problema concreto
- Aplicar patterns porque "es best practice" (sin contexto)

**Ejemplo:**
- ✅ Factory para ROI strategies (3 modos conocidos: none, adaptive, fixed)
- ❌ Abstract Factory + Dependency Injection para 1 solo uso

---

## II. Diseño Evolutivo > Diseño Especulativo

**La evolución del módulo te dirá cuando modularizar.**

### Estrategia:
1. **Identificar bounded contexts claros** (DDD)
2. **Extraer solo lo que duele HOY** (no anticipar dolor futuro)
3. **Diseñar para extensión** (no para todas las extensiones posibles)
4. **Refactorizar cuando el feedback lo pide** (tests complicados, archivos grandes, bugs recurrentes)

**Ejemplo:**
- Opción A (DDD puro): 5 módulos desde día 1 → Especulativo
- Opción C (Híbrida): 3 módulos, extensible → Evolutivo ✅

### Quick Win Strategy:
> **"Modulariza lo suficiente para habilitar evolución, no para predecirla"**

- Crea package structure temprano
- Extrae bounded contexts independientes (geometry, matching)
- Deja que el resto emerja orgánicamente

---

## III. Big Picture Siempre Primero

**Entender el sistema completo antes de tocar una línea.**

### Antes de codear:
1. **Leer CLAUDE.md** (filosofía del proyecto)
2. **Mapear arquitectura actual** (Control/Data Plane, Factories, Handlers)
3. **Identificar bounded contexts** (DDD whiteboard session)
4. **Evaluar trade-offs** (modularidad vs overhead, pureza vs pragmatismo)

**Pregunta clave:**
> *"¿Este cambio mejora la arquitectura o solo la fragmenta?"*

**Ejemplo:**
- ✅ Modularizar adaptive.py → Separa bounded contexts claros
- ❌ Modularizar controller.py → Rompe Application Service cohesivo

---

## IV. KISS ≠ Simplicidad Ingenua

**KISS es diseño limpio, no diseño simplista.**

### KISS correcto:
- **Geometry.py (223 líneas)**: Cohesión alta, acoplamiento bajo, zero deps → KISS ✅
- **Pipeline.py (452 líneas)**: Orquestación completa en un lugar → KISS ✅

### KISS incorrecto:
- **adaptive.py (804 líneas)**: "Todo en un archivo es más simple" → NO ❌
  - Mezcla 3 bounded contexts (geometry, state, orchestration)
  - Testing requiere mocks pesados
  - Extensión toca código no relacionado

**Regla:**
> **"Simple para leer, NO simple para escribir una vez"**

Prefiere:
- 3 archivos de 250 líneas (1 concepto cada uno)
- vs 1 archivo de 800 líneas (3 conceptos mezclados)

---

## V. Cohesión > Ubicación

**Módulos se definen por cohesión conceptual, no por tamaño.**

### Preguntas para modularizar:

1. **¿Este código tiene un solo "motivo para cambiar"?** (SRP)
   - ✅ geometry.py → Solo cambia si geometría ROI cambia
   - ❌ adaptive.py → Cambia por geometry, state, orchestration, metrics...

2. **¿Este código es independiente?**
   - ✅ matching.py (IoU) → Zero deps, reutilizable
   - ✅ geometry.py (ROIBox) → Solo numpy, reutilizable
   - ❌ pipeline.py → Usa geometry + state + inference SDK (orquestador)

3. **¿Este código es testeable en aislación?**
   - ✅ geometry.py → Property tests sin mocks
   - ❌ adaptive.py (monolito) → Mocks de VideoFrame, model, inference_config

### Anti-pattern:
> **"Separar solo por tamaño de archivo"**

- 800 líneas cohesivas (Application Service) → OK mantener junto
- 300 líneas con 3 bounded contexts → Separar

---

## VI. Testing como Feedback Loop

**Tests difíciles = Diseño cuestionable.**

### Señales:

**🚨 Tests necesitan muchos mocks:**
→ Acoplamiento alto, considerar separar dependencies

**🚨 Tests modifican estado global:**
→ Necesitas aislación (módulos independientes)

**🚨 Setup de test > 20 líneas:**
→ Responsabilidad mezclada, revisar cohesión

**✅ Property tests son naturales:**
→ Bounded context bien definido (geometry.py, matching.py)

**✅ Tests con fixtures simples:**
→ Dependencies claras, acoplamiento controlado

---

## VII. Patterns con Propósito

**Usar patterns para resolver problemas concretos, no por CV.**

### Nuestros patterns (con justificación):

| Pattern | Dónde | Por qué |
|---------|-------|---------|
| **Factory** | `StrategyFactory`, `HandlerFactory` | Validación centralizada + extensibilidad (3+ strategies) |
| **Builder** | `PipelineBuilder` | Construcción compleja (10+ pasos con dependencias) |
| **Strategy** | ROI modes, Stabilization | Algoritmos intercambiables (config-driven) |
| **Command** | MQTT Control Plane | Comandos dinámicos con validación |
| **Decorator** | Stabilization sink wrapper | Interceptar sin modificar pipeline |

### Anti-patterns evitados:
- ❌ Singleton (estado global oculto)
- ❌ Service Locator (dependencies implícitas)
- ❌ God Object (evitado vía modularización)

---

## VIII. Documentación Viva

**Código autodocumentado + docs que explican "por qué".**

### Jerarquía:
1. **Nombres claros** (self-documenting code)
   - `make_square_multiple()` > `process_roi()`
   - `TemporalHysteresisStabilizer` > `Stabilizer1`

2. **Docstrings** (qué + cómo)
   - Args, Returns, Examples
   - Performance notes (NumPy views, vectorized ops)

3. **Module headers** (contexto + bounded context)
   ```python
   """
   ROI Geometry Module
   ===================

   Bounded Context: Shape Algebra (operaciones sobre formas 2D)

   Design:
   - Pure functions (no side effects)
   - Immutable data structures
   - Property-testable (invariants)
   """
   ```

4. **CLAUDE.md** (arquitectura + filosofía)
   - Big Picture diagrams
   - Design patterns explicados
   - Extension points documentados

5. **Manifiestos** (principios + trade-offs)
   - Por qué tomamos decisiones
   - Trade-offs evaluados
   - Lecciones aprendidas

---

## IX. Git Commits como Narrativa

**Historia del código debe contar una historia coherente.**

### Formato:
```
<type>: <descripción concisa>

[Cuerpo opcional con contexto/motivación]

Co-Authored-By: Gaby <noreply@visiona.com>
```

### Types:
- `feat`: Nueva funcionalidad
- `fix`: Bug fix
- `refactor`: Mejora sin cambio de behavior (ej: modularización)
- `test`: Agregar/mejorar tests
- `docs`: Documentación
- `perf`: Performance optimization

### Ejemplo (este refactor):
```
refactor: Modularizar adaptive.py en bounded contexts

Separación en 3 módulos (Opción C - Híbrida):
- geometry.py: ROIBox + operaciones geométricas (223L)
- state.py: ROIState + gestión temporal (187L)
- pipeline.py: Transforms + orchestración (452L)

Beneficios:
- Testing aislado habilitado (property tests en geometry)
- Extensibilidad mejorada (fácil agregar geometry_3d)
- Cohesión explícita (1 módulo = 1 bounded context)
- API pública preservada (backward compatible)

Trade-off aceptado: +3 archivos vs mejor separación de concerns

Co-Authored-By: Gaby <noreply@visiona.com>
```

---

## X. Pragmatismo > Purismo

**Resolver problemas reales con soluciones prácticas.**

### Balance:

**Purismo:**
- "Debe ser SOLID/DDD/Clean Architecture perfecto"
- "Toda lógica en domain, cero en infrastructure"
- "Dependency Injection en todo"

**Pragmatismo:**
- "SOLID donde importa, pragmatismo donde no"
- "Lógica en layer apropiado (NumPy en transforms, no en domain)"
- "DI para strategies, imports directos para utilities"

### Ejemplo (este proyecto):
- ✅ DDD para bounded contexts (Geometry, State, Pipeline)
- ✅ SOLID para extensibilidad (Factory, Strategy)
- ✅ Pragmatismo para utilities (NumPy views, CV2 en transforms)
- ✅ No Hexagonal puro (NumPy ops en "infrastructure" sin ports/adapters)

**Pregunta guía:**
> *"¿Este cambio resuelve un problema real o satisface un principio teórico?"*

---

## XI. Métricas de Éxito

**Cómo evaluar si el diseño es bueno.**

### ✅ Buenas señales:
1. **Fácil agregar features** sin tocar código no relacionado
2. **Tests rápidos y simples** (pocos mocks)
3. **Bugs localizados** (1 bug = 1 módulo típicamente)
4. **Onboarding rápido** (nuevo dev entiende arquitectura en <1 día)
5. **Refactors seguros** (cambio en 1 módulo, 0 regresiones)

### 🚨 Malas señales:
1. **"Shotgun surgery"** (1 feature toca 10 archivos)
2. **Tests frágiles** (cambio pequeño rompe 20 tests)
3. **Bugs recurrentes** en mismo lugar (diseño inadecuado)
4. **"No sé dónde poner esto"** (bounded contexts poco claros)
5. **Miedo a refactorizar** (acoplamiento alto, sin tests)

### Score actual: **9.0/10** ⬆
- v2.0 (pre-modularización): 8.5/10
- v2.1 (post-modularización): 9.0/10

---

## XII. Checklist para Futuros Claudes

Antes de hacer un refactor mayor:

### 1. Entender (Big Picture)
- [ ] Leí `CLAUDE.md` y entendí arquitectura actual
- [ ] Identifiqué bounded contexts en whiteboard
- [ ] Evalué trade-offs de modularización vs monolito
- [ ] Pregunté a Ernesto si hay dudas de diseño

### 2. Planear (Diseño Evolutivo)
- [ ] Propuse 2-3 opciones (DDD puro, Hexagonal, Híbrido)
- [ ] Justifiqué recomendación con ejemplos concretos
- [ ] Evaluamos juntos pros/contras de cada opción
- [ ] Elegimos "quick win" (minimal disruption, máximo aprendizaje)

### 3. Ejecutar (Incremental)
- [ ] Creé package structure
- [ ] Extraje bounded contexts independientes primero
- [ ] Preservé API pública (backward compatible)
- [ ] Compilé después de cada paso
- [ ] Commits atómicos (1 concepto = 1 commit)

### 4. Validar (Testing)
- [ ] Tests existentes pasan
- [ ] Consideré property tests para bounded contexts puros
- [ ] Documenté módulos (bounded context + design notes)
- [ ] Actualicé CLAUDE.md si arquitectura cambió

### 5. Iterar (Feedback)
- [ ] Revisamos juntos (pair programming style)
- [ ] Identificamos próximos pasos (más modularización vs feature work)
- [ ] Documentamos lecciones aprendidas (este manifiesto)

---

## XIII. Lecciones de Este Refactor

### ✅ Lo que funcionó:
1. **Whiteboard session primero** → Mapeo de bounded contexts antes de codear
2. **Opción C (Híbrida)** → Balance pragmático (3 módulos, extensible)
3. **Preservar API pública** → Zero breaking changes, refactor seguro
4. **Commits atómicos** → Historia clara, fácil rollback si necesario

### 🔄 Lo que mejoraríamos:
1. **Property tests inmediatos** → Habilitar después de extraer geometry.py
2. **Git history preservation** → Considerar `git mv` para mantener history
3. **Documentación inline** → Más ejemplos de uso en docstrings

### 📈 Impacto:
- **Cohesión:** ⭐⭐⭐⭐⭐ (1 módulo = 1 bounded context)
- **Testability:** ⭐⭐⭐⭐⭐ (property tests habilitados)
- **Extensibilidad:** ⭐⭐⭐⭐⭐ (fácil agregar geometry_3d, state_distributed)
- **Overhead:** ⭐⭐⭐⭐ (4 archivos vs 1, navegación multi-file)

**Balance final: ✅ Beneficios >> Costos**

---

## Epílogo

> **"Complejidad por Diseño significa:**
> **Diseñar para manejar complejidad inherente,**
> **No crear complejidad artificial."**
>
> — Visiona Team Philosophy

### Principios en una frase:
1. **Big Picture** → Entender antes de codear
2. **KISS** → Simple para leer, no para escribir una vez
3. **DDD** → Bounded contexts claros
4. **Evolutivo** → Modularizar cuando duele, no antes
5. **Pragmático** → Resolver problemas reales

### Pregunta final antes de cualquier cambio:
> *"¿Este diseño habilita evolución o la predice?"*

**Habilitar ✅ | Predecir ❌**

---

**Versión:** 1.0
**Fecha:** 2025-10-22
**Autores:** Ernesto (Visiona) + Gaby (AI Companion)
**Contexto:** Post-refactor adaptive.py (v2.1)

---

**Para futuros Claudes:**
Este manifiesto nació de una sesión de café ☕ y pizarra 🍕, discutiendo cómo atacar complejidad por diseño. No es dogma, es filosofía destilada de experiencia real. Úsenlo como guía, no como ley. Y siempre pregunten a Ernesto si tienen dudas.

¡Buen código, compañeros! 🚀

---

## 📖 **DOCUMENTACIÓN RELACIONADA**

Este manifiesto es parte de un conjunto de documentos estratégicos:

**📚 Para Futuros AIs:**
- **[BLUEPRINT_FUTUROS_COPILOTS.md](./BLUEPRINT_FUTUROS_COPILOTS.md)** - Guía estratégica definitiva (¡LEE ESTO PRIMERO!)

**📋 Proceso de Modularización:**  
- **[ANALISIS_MODULARIZACION_WHITEBOARD.md](./ANALISIS_MODULARIZACION_WHITEBOARD.md)** - Bounded contexts identificados
- **[RESUMEN_SESION_MODULARIZACION.md](./RESUMEN_SESION_MODULARIZACION.md)** - Tracking completo v2.1

**🔍 Análisis Técnico:**
- **[ANALISIS_ARQUITECTURA_GABY.md](./ANALISIS_ARQUITECTURA_GABY.md)** - Deep analysis (score 8.5/10)
- **[PLAN_MEJORAS.md](./PLAN_MEJORAS.md)** - Roadmap y prioridades
- **[TEST_CASES_FUNCIONALES.md](./TEST_CASES_FUNCIONALES.md)** - Scripts de testing real

**🎯 Score Evolution:**
- v1.0: 6.5/10 → v2.0: 8.5/10 → v2.1: 9.0/10 → v3.0: 9.5/10 (target)



 ✅ Manifiesto Creado - MANIFESTO_DISENO.md

  Ernesto, armé el manifiesto capturando toda nuestra charla de café. ☕

  📋 Contenido del Manifiesto (13 secciones):

  I. Principio Central
  "Un diseño limpio NO es un diseño complejo"

  II-V. Filosofía Core
  - Complejidad por Diseño (atacar complejidad real)
  - Diseño Evolutivo > Especulativo (YAGNI aplicado)
  - Big Picture siempre primero
  - KISS ≠ Simplicidad ingenua

  VI-X. Prácticas Concretas
  - Cohesión > Ubicación (SRP)
  - Testing como feedback loop
  - Patterns con propósito (no por CV)
  - Documentación viva (código + contexto)
  - Pragmatismo > Purismo

  XI-XII. Evaluación
  - Métricas de éxito (9.0/10 actual)
  - Checklist para futuros Claudes

  XIII. Lecciones de Este Refactor
  - ✅ Lo que funcionó (whiteboard primero, Opción C)
  - 🔄 Lo que mejoraríamos (property tests inmediatos)
  - 📈 Impacto (cohesión ⭐⭐⭐⭐⭐, extensibilidad ⭐⭐⭐⭐⭐)

  ---
  🎯 Highlights del Manifiesto:

  1. Quick Win Strategy

  "Modulariza lo suficiente para habilitar evolución, no para predecirla"

  2. Pregunta clave antes de modularizar

  "¿Este cambio mejora la arquitectura o solo la fragmenta?"

  3. KISS correcto vs incorrecto

  ✅ geometry.py (223L): 1 concepto, cohesión alta
  ❌ adaptive.py (804L): 3 conceptos mezclados

  4. Testing como señal de diseño

  - 🚨 Tests necesitan muchos mocks → Acoplamiento alto
  - ✅ Property tests naturales → Bounded context bien definido

  5. Pregunta final

  "¿Este diseño habilita evolución o la predice?"

  Habilitar ✅ | Predecir ❌

  ---
  📊 Resumen de la Sesión Completa

  Análisis (whiteboard):
  - ✅ ANALISIS_MODULARIZACION_WHITEBOARD.md - 6 bounded contexts identificados
  - ✅ Trade-offs evaluados (3 opciones)
  - ✅ Recomendación: Opción C (Híbrida)

  Implementación (refactor):
  - ✅ 4 archivos creados (geometry, state, pipeline, init)
  - ✅ 804 líneas → 919 líneas (3 módulos cohesivos)
  - ✅ API pública preservada (backward compatible)
  - ✅ Compilación limpia

  Documentación (manifiesto):
  - ✅ MANIFESTO_DISENO.md - 13 secciones, filosofía + checklist
  - ✅ Lecciones aprendidas documentadas
  - ✅ Guía para futuros Claudes

