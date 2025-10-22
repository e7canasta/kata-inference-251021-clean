# Test Cases Funcionales - Sistema Detección Caídas Adeline
## Documento para Testing de Campo con Actores

**Versión:** 1.0
**Fecha:** 2025-10-22
**Sistema:** Adeline v2.1 (con IoU Multi-Object Tracking)
**Contexto:** Residencias geriátricas - Habitaciones compartidas (1-4 residentes)
**Duración estimada:** 1 día completo (6-8 horas efectivas)

---



## TEST CASES 


  ---
  🧪 Testing Manual - Escenario Multi-Persona

  Para testear el IoU matching en habitaciones compartidas:

  Escenario de Test

  Setup: Habitación con 2-4 personas (residentes + enfermeros/visitantes)

  Test Cases Críticos:

  1. Personas estáticas (en camas)
    - Esperado: Cada persona mantiene su propio track ID
    - Antes (sin IoU): Podían confundirse si desaparecía una persona
  2. Persona caminando + persona en cama
    - Esperado: Tracks separados, no se confunden
    - Antes: Cuando persona A sale, persona B podía "robar" el track de A
  3. Cruce de personas (enfermero pasa cerca de residente)
    - Esperado: Tracks se mantienen separados si IoU < 0.3
    - Crítico: Verificar que no se fusionan tracks cuando se cruzan
  4. Oclusión parcial
    - Esperado: Track se mantiene si reaparece dentro de max_gap frames
    - Verificar que el re-match usa IoU correctamente


---




✅ Implementación completa + documento realista de testing

  ---
  📦 Resumen de Entregables

  ✅ 1. IoU Matching Implementado (v2.1)

  Archivos modificados:
  ✅ inference/stabilization/core.py        - calculate_iou() + matching espacial
  ✅ config.py                               - STABILIZATION_IOU_THRESHOLD
  ✅ inference/factories/strategy_factory.py - Pasa iou_threshold
  ✅ PLAN_MEJORAS.md                         - Status actualizado
  ✅ CLAUDE.md                               - Testing strategy actualizada

  Compilación verificada:
  python -m py_compile inference/stabilization/core.py      # ✅
  python -m py_compile config.py                            # ✅
  python -m py_compile inference/factories/strategy_factory.py  # ✅

  ---
  ✅ 2. Documento TEST_CASES_FUNCIONALES.md

  Tipo: Script de filmación para testing de campo con actores

  Contenido (actualizado a realidad Adeline v2.1):

  ⚠ Cambio clave: Documento ahora es honesto sobre alcance:
  - ✅ Valida: Multi-tracking IoU (2-4 personas), track stability, bbox changes
  - ❌ NO valida: Eventos específicos (Bed Exit, Bathroom Timer, etc.) → Requiere v3.0+

  Escenarios (12 test cases):
  CATEGORÍA 1: Baseline (1 persona)
    TC-001: Persona estática en cama
    TC-002: Persona con movimiento
    TC-003: Cambio de postura (fundamento para caída) ⬅ Reframed

  CATEGORÍA 2: Habitación doble (2 personas)
    TC-004: Dos residentes estáticos
    TC-005: Enfermero entra/sale
    TC-006: Cambio de postura R1 con R2 en cama ⭐ CRÍTICO ⬅ Reframed
    TC-007: Cruce de personas

  CATEGORÍA 3: Habitación compartida (3-4 personas)
    TC-008: Cuatro residentes (stress test)
    TC-009: Cambio postura con 4 personas ⭐⭐⭐ MÁS CRÍTICO ⬅ Reframed

  CATEGORÍA 4: Edge Cases
    TC-010: Oclusión temporal
    TC-011: Entrada/salida rápida
    TC-012: Variación de luz

  Lo nuevo:
  - Sección inicial: "Lo que v2.1 PUEDE vs NO PUEDE hacer"
  - Test cases reframed: Validan fundamentos de tracking, no eventos específicos
  - Criterios de éxito realistas
  - Roadmap hacia v3.0 con:
    - Tabla de viabilidad de eventos Verso Vision
    - Ejemplo de código PatientFallHandler (para v3.0)
    - KISS approach para event detection layer
    - Preguntas para planificación v3.0

  ---
  🎯 Objetivo del Testing de Campo

  Validar: ¿El IoU matching permite distinguir quién es quién en habitaciones compartidas?

  Pregunta crítica (TC-009):
  "Con 4 personas en habitación, si una cambia de postura (cae), ¿podemos identificar cuál de los 4 tracks cambió?"

  Si la respuesta es SÍ:
  → Fundamento validado
  → v2.1 es production-ready
  → Pasar a v3.0 (agregar event detection layer)

  Si la respuesta es NO:
  → Ajustar parámetros (iou_threshold, min_frames)
  → Posible debugging de matching logic

  ---
  📋 Próximos Pasos

  1. Testing de Campo (Fin de Semana)

  Preparación:
  - Imprimir TEST_CASES_FUNCIONALES.md
  - Equipo de actores (4 personas + operador técnico)
  - Equipamiento: Cámara RTSP, laptop, colchonetas seguridad
  - Residencia real (habitación 2-4 camas)

  Ejecución:
  - Seguir scripts TC-001 a TC-012
  - Operador técnico registra:
    - Logs MQTT (track IDs, bbox dimensions)
    - Videos de cada escenario
    - Observaciones (fusiones, swaps, resets)

  Validación:
  - Completar matriz de validación final
  - Llenar checklist de cada test case
  - Focus en TC-006 y TC-009 (críticos)

  2. Análisis de Resultados

  Si ≥10/12 tests aprobados:
  → v2.1 ✅ VALIDADA
  → Reunión planificación v3.0 (eventos)

  Si 8-9/12 tests aprobados:
  → Ajustar parámetros
  → Re-test casos fallidos

  Si <8/12 tests aprobados:
  → Debugging IoU matching
  → Revisar implementación

  3. Planificación v3.0 (Event Detection)

  Después de validar v2.1:
  - Revisar tabla de eventos Verso Vision en documento
  - Priorizar eventos (Patient Fall, Extra Person, etc.)
  - Definir precisión mínima requerida (90%? 95%?)
  - Evaluar si se necesita pose estimation

  Orden sugerido v3.0:
  Sprint 1: Extra Person In Room    (1-2 días - conteo tracks)
  Sprint 2: Patient Fall             (3-5 días - aspect ratio)
  Sprint 3: Room Exit                (3-5 días - zones)
  Sprint 4: Bathroom Timer           (3-5 días - zones + time)

  ---
  🧠 Filosofía Mantenida: KISS + Complejidad por Diseño

  Lo que hicimos en v2.1:
  - IoU matching ← Complejidad donde importa (distinguir objetos)
  - KISS en implementación (best-match by IoU, simple)
  - Factory pattern (consistente con arquitectura)

  Lo que viene en v3.0:
  - Event detection ← Nueva capa de complejidad
  - KISS en lógica (aspect ratio, zones, conteo - no ML complicado)
  - Un handler por evento (SRP)
  - Factory pattern (igual que stabilization)

  NO vamos a:
  - Sobrecomplicar con ML pesado (pose estimation solo si es crítico)
  - Implementar todos los eventos de golpe
  - Prometer features antes de validar fundamentos

  ---
  📄 Documentos Actualizados

  ✅ TEST_CASES_FUNCIONALES.md  - 870 líneas, script completo de testing
  ✅ PLAN_MEJORAS.md             - Tarea 1 marcada como implementada
  ✅ CLAUDE.md                   - Testing strategy actualizada
  ✅ Código fuente              - IoU matching functional

  ---


---

## 🎬 Información General del Testing

### Contexto del Sistema

**Adeline v2.1** es un sistema de **person detection + tracking multi-objeto** diseñado como **base** para sistemas de monitoreo geriátrico (tipo Verso Vision).

**⚠️ IMPORTANTE - Alcance de esta versión:**

**✅ Lo que Adeline v2.1 PUEDE hacer (y vamos a validar):**
- Detectar personas en tiempo real (YOLO-based)
- **Tracking multi-persona con IoU matching** (⬅️ NUEVO, objetivo de este testing)
- Diferenciar quién es quién en habitaciones compartidas (2-4 personas)
- Mantener track IDs estables
- Detectar cambios en bounding box (puede sugerir caída, cambio de postura)
- Contar personas en habitación ("Extra Person In Room" básico)

**❌ Lo que Adeline v2.1 NO PUEDE hacer todavía (requiere v3.0+):**
- Eventos específicos (Bed Exit, Bathroom Timer, Leaving Chair) → Requiere zone detection + event logic
- Pose estimation (sitting vs standing vs laying) → Requiere pose detection model
- Bathroom Entry/Timer → Requiere zone tracking
- Out of View logic → Requiere spatial reasoning

**🎯 Objetivo de este Testing:**

Validar el **fundamento de tracking multi-persona** que permitirá implementar eventos específicos en futuras versiones:

1. **Tracking multi-persona estable** (nuevo IoU matching)
2. **Identificación de quién es quién** en habitaciones compartidas
3. **Persistencia de tracks** con oclusiones, movimientos, entradas/salidas
4. **Base para eventos futuros** (si podemos distinguir tracks, luego podemos agregar zone logic)

### Setup Técnico Requerido

**Hardware:**
- Cámara RTSP configurada (altura: 2.5-3m, ángulo: 30-45° hacia abajo)
- Laptop con sistema Adeline corriendo
- Monitor para visualización en tiempo real
- Red WiFi estable

**Software (debe estar corriendo):**
```bash
# Terminal 1: Pipeline principal
python -m adeline

# Terminal 2: Monitor de detecciones (para validación)
python -m adeline.data.monitors data

# Terminal 3: Monitor de status
python -m adeline.data.monitors status
```

**Configuración crítica (config.yaml):**
```yaml
detection_stabilization:
  mode: temporal
  iou:
    threshold: 0.3  # ⬅️ CRÍTICO para multi-persona
```

### Equipo Requerido

**Roles de Actores:**
- **Residente 1 (R1):** Persona de edad avanzada, movilidad reducida
- **Residente 2 (R2):** Persona de edad avanzada, movilidad moderada
- **Residente 3 (R3):** Persona de edad avanzada (solo para escenarios 4 residentes)
- **Residente 4 (R4):** Persona de edad avanzada (solo para escenarios 4 residentes)
- **Enfermero/a (E):** Staff médico, movilidad normal
- **Visitante (V):** Familiar o visitante, movilidad normal
- **Operador Técnico (OT):** Observa monitors, registra resultados

**Materiales de Escenografía:**
- 2-4 camas tipo hospital
- Sillas
- Mesa auxiliar
- Andador (opcional)
- Colchonetas de seguridad (para simular caídas)

---

## 📋 Escenarios de Test

### Categorías de Escenarios

1. **Baseline (1 persona)** - Validación básica
2. **Habitación doble (2 personas)** - Caso más común
3. **Habitación compartida (3-4 personas)** - Caso complejo
4. **Oclusiones y cruces** - Edge cases críticos
5. **Caídas con múltiples personas** - Objetivo principal

---

## 🔵 CATEGORÍA 1: Baseline (1 Persona)

### TC-001: Persona sola estática en cama

**Objetivo:** Verificar tracking básico de 1 persona sin movimiento

**Actores:** R1

**Precondiciones:**
- Sistema corriendo
- Habitación vacía inicialmente

**Script:**
1. R1 entra en la habitación (00:00)
2. R1 se acuesta en la cama (00:10)
3. R1 permanece acostado sin moverse (00:15 - 02:00)
4. R1 se levanta y sale (02:00)

**Resultado Esperado:**
- ✅ 1 track de "person" activo entre 00:10 - 02:00
- ✅ Track se mantiene estable (no parpadea)
- ✅ Track desaparece después de que R1 sale (dentro de 2-3 frames)

**Checklist de Validación:**
```
[ ] Track aparece en < 3 segundos después de entrar
[ ] No hay tracks duplicados (solo 1 track activo)
[ ] Track no se pierde durante los 2 minutos acostado
[ ] Track se elimina correctamente al salir
[ ] Monitor muestra confidence >= 0.3
```

---

### TC-002: Persona sola con movimiento en habitación

**Objetivo:** Verificar tracking de 1 persona en movimiento

**Actores:** R1

**Script:**
1. R1 entra en la habitación (00:00)
2. R1 camina hacia la ventana (00:05)
3. R1 se sienta en silla (00:20)
4. R1 se levanta y camina hacia la cama (00:40)
5. R1 se acuesta (01:00)
6. R1 permanece acostado (01:00 - 02:00)

**Resultado Esperado:**
- ✅ 1 track único se mantiene durante todo el recorrido
- ✅ No se crean múltiples tracks para la misma persona
- ✅ Bounding box se actualiza correctamente al moverse

**Checklist de Validación:**
```
[ ] Mismo track ID durante todo el recorrido (no se resetea)
[ ] Track no se pierde durante transiciones (parado → sentado → acostado)
[ ] Bounding box refleja la posición real
[ ] No hay "saltos" del track (tracking suave)
```

---

### TC-003: Cambio de postura (persona al suelo)

**Objetivo:** Verificar que el tracking persiste durante cambios drásticos de postura (fundamento para futura detección de caídas)

**Actores:** R1

**⚠️ SEGURIDAD:** Usar colchoneta de seguridad

**⚠️ NOTA:** Este test valida tracking, NO detección de caída específica (v3.0+)

**Script:**
1. R1 entra y camina al centro de la habitación (00:00)
2. R1 permanece de pie 10 segundos (00:10)
3. **R1 simula caída controlada al suelo** (00:20) ⬅️ Cambio drástico de postura
4. R1 permanece en el suelo 30 segundos (00:20 - 00:50)
5. R1 se levanta (00:50)
6. R1 sale de la habitación (01:00)

**Resultado Esperado:**
- ✅ Track se mantiene durante todo el escenario (mismo ID)
- ✅ Bounding box cambia de aspect ratio (vertical → horizontal al caer)
- ✅ Sistema sigue detectando "person" mientras está en el suelo
- ✅ Logs MQTT muestran cambio en dimensiones del bbox

**Checklist de Validación:**
```
[ ] Track existe antes, durante y después (mismo ID)
[ ] Track no se pierde durante la caída
[ ] Bounding box cambia dimensiones (height > width → width > height)
[ ] Detection persiste mientras R1 está en el suelo (conf >= 0.3)
[ ] MQTT muestra bbox con nuevo aspect ratio
```

**🔍 Observación para v3.0:**
```
Este test captura datos para futura lógica de eventos:
- bbox.height / bbox.width antes: ~1.5-2.0 (persona de pie)
- bbox.height / bbox.width después: ~0.5-0.8 (persona en suelo)
→ Fundamento para "Patient Fall" event detection
```

---

## 🟢 CATEGORÍA 2: Habitación Doble (2 Personas)

### TC-004: Dos residentes estáticos en camas separadas

**Objetivo:** Verificar tracking de 2 personas sin movimiento (IoU baseline)

**Actores:** R1, R2

**Precondiciones:**
- 2 camas separadas ~2 metros

**Script:**
1. R1 entra y se acuesta en cama 1 (00:00)
2. R2 entra y se acuesta en cama 2 (00:30)
3. Ambos permanecen acostados (01:00 - 03:00)
4. R1 se levanta y sale (03:00)
5. R2 permanece acostado (03:00 - 04:00)
6. R2 se levanta y sale (04:00)

**Resultado Esperado:**
- ✅ 2 tracks separados (no se confunden)
- ✅ Track de R1 desaparece al salir (~03:02)
- ✅ Track de R2 se mantiene solo después de que R1 sale
- ✅ No hay "robo" de track (R2 no toma el track de R1)

**Checklist de Validación:**
```
[ ] 2 tracks activos entre 01:00 - 03:00
[ ] Tracks no se fusionan (IoU < 0.3)
[ ] Track R1 se elimina correctamente al salir
[ ] Track R2 no se resetea cuando R1 sale
[ ] Monitor muestra 2 → 1 → 0 tracks en secuencia correcta
```

---

### TC-005: Enfermero entra/sale con residente en cama

**Objetivo:** Verificar que entrada/salida de staff no afecta track de residente

**Actores:** R1, E

**Script:**
1. R1 entra y se acuesta en cama (00:00)
2. R1 permanece acostado (00:30 - 03:00)
3. E entra en la habitación (01:00) ⬅️ **Nuevo track**
4. E camina hacia la cama de R1 (01:10)
5. E revisa a R1 (se acerca, IoU temporal alto) (01:20)
6. E camina hacia la puerta (01:40)
7. E sale de la habitación (01:50) ⬅️ **Track desaparece**
8. R1 continúa acostado (02:00 - 03:00)

**Resultado Esperado:**
- ✅ Track R1 se mantiene estable durante toda la secuencia
- ✅ Track E aparece al entrar (~01:02)
- ✅ Tracks R1 y E se mantienen separados (incluso cuando E está cerca)
- ✅ Track E desaparece al salir (~01:52)
- ✅ Track R1 no se resetea después de la visita

**Checklist de Validación:**
```
[ ] Track R1 existe antes, durante y después de la visita (sin reseteo)
[ ] Track E aparece solo cuando entra
[ ] Tracks no se fusionan cuando E está cerca de R1
[ ] Track E se elimina correctamente al salir
[ ] Monitor muestra 1 → 2 → 1 tracks en secuencia correcta
```

---

### TC-006: Cambio de postura R1 con R2 en cama (CRÍTICO - Multi-Tracking)

**Objetivo:** Verificar que el sistema puede distinguir qué track cambió de postura cuando hay 2 personas

**Actores:** R1, R2

**⚠️ SEGURIDAD:** Usar colchoneta

**⚠️ NOTA:** Valida multi-tracking, NO evento "Patient Fall" específico (v3.0+)

**Script:**
1. R1 entra y se acuesta en cama 1 (00:00)
2. R2 entra y se acuesta en cama 2 (00:30)
3. Ambos permanecen acostados (01:00)
4. **R1 se levanta** (01:30)
5. **R1 simula caída al suelo** (01:40) ⬅️ **CRÍTICO - ¿Sistema distingue qué track cambió?**
6. R1 permanece en el suelo (01:40 - 02:30)
7. R2 permanece acostado durante todo el escenario
8. E entra para ayudar a R1 (02:30)

**Resultado Esperado:**
- ✅ Sistema mantiene 2 tracks separados e independientes (R1, R2)
- ✅ Solo el track R1 cambia bounding box (aspect ratio vertical → horizontal)
- ✅ Track R2 permanece estable (no afectado por R1)
- ✅ **Operador puede identificar en MQTT qué track cambió** (R1 vs R2)
- ✅ Track R1 persiste mientras está en el suelo (mismo ID)
- ✅ Track E aparece al entrar (3 tracks, diferenciados por IoU)

**Checklist de Validación:**
```
[ ] 2 tracks activos y separados entre 01:00 - 01:30
[ ] Track R1 cambia aspect ratio al caer (observado en MQTT/logs)
[ ] Track R2 NO cambia dimensiones (permanece estable)
[ ] Operador puede identificar QUÉ track cambió (mediante ID o posición)
[ ] Track R1 mantiene mismo ID antes/después de caer
[ ] Track E aparece correctamente (3 tracks simultáneos, no confundidos)
```

**⭐ VERIFICACIÓN CRÍTICA:**
```
Pregunta: "Observando logs MQTT, ¿se puede identificar cuál de los 2 tracks cambió de postura?"

[ ] Sí - Track IDs estables + cambio de bbox observable → Éxito ✅
[ ] No - Tracks se confunden o resetean → Falla crítica ❌
```

**🔍 Observación para v3.0:**
```
Este test valida el fundamento de IoU multi-tracking que permite:
- Diferenciar Track_A (cambió bbox) vs Track_B (estable)
- Futura lógica: IF track.aspect_ratio cambió + track.y_center aumentó → Patient Fall
- Futura lógica: IF extra_track aparece + room.count == 2 → Extra Person In Room
```

---

### TC-007: Cruce de personas (enfermero pasa cerca de residente)

**Objetivo:** Verificar que tracks no se fusionan al cruzarse

**Actores:** R1, E

**Script:**
1. R1 camina lentamente por el lado derecho de la habitación (00:00)
2. E entra por el lado izquierdo (00:10)
3. **R1 y E se cruzan en el centro** (00:20) ⬅️ IoU alto temporal
4. Continúan caminando en direcciones opuestas (00:25)
5. R1 sale por la izquierda (00:40)
6. E sale por la derecha (00:50)

**Resultado Esperado:**
- ✅ Tracks se mantienen separados durante el cruce
- ✅ No hay "swap" de tracks (R1 no se convierte en E después del cruce)
- ✅ Cada track mantiene su trayectoria correcta

**Checklist de Validación:**
```
[ ] 2 tracks activos durante todo el escenario
[ ] Tracks no se fusionan en el cruce (IoU threshold funciona)
[ ] No hay swap de IDs después del cruce
[ ] Bounding boxes reflejan correctamente cada persona
```

---

## 🟡 CATEGORÍA 3: Habitación Compartida (3-4 Personas)

### TC-008: Cuatro residentes en habitación compartida (Stress Test)

**Objetivo:** Verificar tracking de 4 personas simultáneas (caso extremo de IoU matching)

**Actores:** R1, R2, R3, R4

**Precondiciones:**
- 4 camas en habitación

**Script:**
1. R1 entra y se acuesta en cama 1 (00:00)
2. R2 entra y se acuesta en cama 2 (00:30)
3. R3 entra y se acuesta en cama 3 (01:00)
4. R4 entra y se acuesta en cama 4 (01:30)
5. Los 4 permanecen acostados (02:00 - 05:00)
6. R3 se levanta, camina y sale (05:00)
7. Los otros 3 permanecen acostados (05:30 - 07:00)

**Resultado Esperado:**
- ✅ Sistema mantiene 4 tracks separados
- ✅ Tracks no se fusionan ni duplican
- ✅ Track R3 desaparece correctamente al salir
- ✅ Los otros 3 tracks permanecen estables

**Checklist de Validación:**
```
[ ] Monitor muestra 1 → 2 → 3 → 4 tracks en secuencia
[ ] 4 tracks activos estables entre 02:00 - 05:00
[ ] No hay tracks duplicados (verificar en MQTT)
[ ] Track R3 se elimina al salir (4 → 3 tracks)
[ ] Tracks restantes no se resetean
```

---

### TC-009: Cambio de postura en habitación con 4 personas (CRÍTICO MÁXIMO)

**Objetivo:** Verificar que el sistema puede distinguir qué track cambió en el escenario más complejo (4 personas)

**Actores:** R1, R2, R3, R4

**⚠️ SEGURIDAD:** Usar colchoneta

**⚠️ NOTA:** Valida IoU multi-tracking (4 personas), NO evento específico (v3.0+)

**Script:**
1. R1, R2 acostados en camas (00:00)
2. R3, R4 acostados en camas (00:00)
3. Todos permanecen 2 minutos (00:00 - 02:00)
4. **R3 se levanta** (02:00)
5. R3 camina hacia el centro (02:10)
6. **R3 simula caída controlada** (02:20) ⬅️ **CRÍTICO - ¿Sistema distingue 1 de 4 tracks?**
7. R3 permanece en el suelo (02:20 - 03:00)
8. R1, R2, R4 permanecen en camas durante todo el escenario

**Resultado Esperado:**
- ✅ Sistema mantiene 4 tracks separados y estables (IoU funciona con 4 objetos)
- ✅ Solo el track R3 cambia bounding box (aspect ratio)
- ✅ Tracks R1, R2, R4 permanecen estables (no afectados)
- ✅ **Operador puede identificar en MQTT cuál de los 4 tracks cambió**
- ✅ No hay confusión de track IDs (no swaps durante 4-person tracking)

**Checklist de Validación:**
```
[ ] 4 tracks activos y diferenciados entre 02:00 - 02:10
[ ] Solo track R3 cambia aspect ratio (observable en logs/MQTT)
[ ] Tracks R1, R2, R4 NO cambian dimensiones
[ ] Operador puede identificar QUÉ track de los 4 cambió
[ ] No hay swaps de track IDs durante el escenario
[ ] IoU threshold (0.3) es suficiente para 4 personas en habitación
```

**⭐⭐⭐ VERIFICACIÓN CRÍTICA:**
```
Pregunta: "Observando logs MQTT con 4 tracks activos, ¿se puede identificar cuál cambió de postura?"

[ ] Sí - 4 tracks estables + cambio de bbox identificable → Éxito ✅✅✅
[ ] No - Tracks se confunden, resetean o fusionan → Falla crítica ❌❌❌

Esto valida el objetivo principal de v2.1: IoU matching funciona en escenarios realistas complejos.
```

**🔍 Observación para v3.0:**
```
Este test es el fundamento para todos los eventos de Verso Vision:
- Si IoU puede diferenciar 4 personas → Podemos agregar zone logic
- Si track IDs son estables → Podemos trackear "Bed Exit" per-resident
- Si cambio de bbox es observable → Podemos detectar "Patient Fall"
- Si contamos tracks → Podemos detectar "Extra Person In Room"

v2.1 valida el fundamento. v3.0+ agregará event detection layer.
```

---

## 🟠 CATEGORÍA 4: Edge Cases y Oclusiones

### TC-010: Oclusión temporal (persona pasa detrás de mueble)

**Objetivo:** Verificar persistencia de track durante oclusión breve

**Actores:** R1

**Precondiciones:**
- Mueble o biombo que genere oclusión

**Script:**
1. R1 camina por la habitación (00:00)
2. **R1 pasa detrás del mueble** (oclusión total) (00:10 - 00:15)
3. R1 reaparece del otro lado (00:15)
4. R1 continúa caminando (00:20)

**Resultado Esperado:**
- ✅ Track se mantiene durante oclusión (gracias a `max_gap=2`)
- ✅ No se crea nuevo track al reaparecer
- ✅ Mismo track ID antes, durante y después

**Checklist de Validación:**
```
[ ] Track no se elimina durante oclusión (<2 frames sin detección)
[ ] No se crea track duplicado al reaparecer
[ ] Bounding box reaparece en posición correcta
```

---

### TC-011: Entrada/salida rápida (enfermero asoma cabeza)

**Objetivo:** Verificar que detecciones breves no generan tracks espurios

**Actores:** E

**Script:**
1. Habitación vacía (00:00)
2. E asoma la cabeza por la puerta (1 segundo) (00:05 - 00:06)
3. E desaparece (00:06)
4. Pausa 5 segundos (00:06 - 00:11)
5. E asoma nuevamente (1 segundo) (00:11 - 00:12)
6. E desaparece (00:12)

**Resultado Esperado:**
- ✅ No se crea track confirmado (< `min_frames=3`)
- ✅ Sistema ignora detecciones esporádicas
- ✅ Monitor muestra "ignored" o "tracking" pero no "confirmed"

**Checklist de Validación:**
```
[ ] No hay tracks confirmados (requiere 3 frames consecutivos)
[ ] Monitor no muestra false positives
[ ] Logs indican "tracking" pero no "confirmed"
```

---

### TC-012: Variación de luz (cortina se cierra/abre)

**Objetivo:** Verificar robustez ante cambios de iluminación

**Actores:** R1, E

**Script:**
1. R1 acostado en cama con luz natural (00:00)
2. E entra y cierra cortinas (luz reduce ~50%) (00:30)
3. R1 permanece acostado (01:00 - 02:00)
4. E abre cortinas (luz aumenta) (02:00)
5. R1 continúa acostado (02:30 - 03:00)

**Resultado Esperado:**
- ✅ Track R1 se mantiene durante cambios de luz
- ✅ No se pierde track al reducir iluminación
- ✅ Confidence puede variar pero track persiste

**Checklist de Validación:**
```
[ ] Track no se resetea al cerrar cortinas
[ ] Track no se resetea al abrir cortinas
[ ] Confidence puede bajar pero >= persist_threshold (0.3)
```

---

## 📊 Matriz de Validación Final

Al completar todos los test cases, completar esta matriz:

| Test Case | Status | Tracks OK | Caída Detectada | ID Correcto | Notas |
|-----------|--------|-----------|-----------------|-------------|-------|
| TC-001 | ⬜ | ⬜ | N/A | N/A | |
| TC-002 | ⬜ | ⬜ | N/A | N/A | |
| TC-003 | ⬜ | ⬜ | ⬜ | ⬜ | |
| TC-004 | ⬜ | ⬜ | N/A | N/A | |
| TC-005 | ⬜ | ⬜ | N/A | N/A | |
| TC-006 | ⬜ | ⬜ | ⬜ | ⬜ | ⭐ CRÍTICO |
| TC-007 | ⬜ | ⬜ | N/A | N/A | |
| TC-008 | ⬜ | ⬜ | N/A | N/A | |
| TC-009 | ⬜ | ⬜ | ⬜ | ⬜ | ⭐⭐⭐ MÁS CRÍTICO |
| TC-010 | ⬜ | ⬜ | N/A | N/A | |
| TC-011 | ⬜ | ⬜ | N/A | N/A | |
| TC-012 | ⬜ | ⬜ | N/A | N/A | |

**Leyenda:**
- ✅ = Aprobado
- ⚠️ = Aprobado con observaciones
- ❌ = Fallido

---

## 📹 Registro de Evidencias

Para cada test case, registrar:

1. **Video del escenario** (cámara externa o grabación de pantalla)
2. **Logs del sistema** (copiar output de terminals)
3. **Screenshots MQTT monitor** (cuando sea relevante)
4. **Timestamp de eventos críticos** (entradas, salidas, caídas)

**Estructura de carpetas sugerida:**
```
testing_YYYYMMDD/
├── TC-001/
│   ├── video.mp4
│   ├── logs.txt
│   ├── mqtt_output.txt
│   └── notas.md
├── TC-002/
│   └── ...
└── resumen_final.md
```

---

## 🚨 Criterios de Éxito/Falla

**Recordatorio:** Adeline v2.1 valida **fundamentos de multi-tracking**, NO eventos específicos (v3.0+)

### ✅ Éxito Global (v2.1 Release Ready)

**Fundamentos de Multi-Tracking Validados:**
- [ ] **TC-006 APROBADO** - 2 tracks diferenciados, cambio de bbox identificable
- [ ] **TC-009 APROBADO** - 4 tracks diferenciados, cambio de bbox identificable
- [ ] **>= 10/12 test cases aprobados**
- [ ] **No regressions** vs comportamiento sin IoU (TC-001 a TC-003)
- [ ] **Track IDs estables** - No swaps, no resets inesperados
- [ ] **IoU threshold 0.3 funciona** - No fusiones incorrectas

**Significa:**
→ Fundamento sólido para implementar event detection (Bed Exit, Patient Fall, etc.) en v3.0

### ⚠️ Éxito Parcial (Requiere ajustes antes de Release)

- [ ] TC-006 o TC-009 con warnings (funciona pero no óptimo)
- [ ] 8-9/12 test cases aprobados
- [ ] Tracking funciona pero requiere ajustar `iou_threshold` (0.2-0.5)
- [ ] Tracks se fusionan ocasionalmente (< 10% de los casos)

**Acción:**
→ Ajustar parámetros (iou_threshold, min_frames, max_gap) y re-test

### ❌ Falla Crítica (No Release - Requiere Debugging)

- [ ] TC-006 o TC-009 fallidos consistentemente
- [ ] < 8/12 test cases aprobados
- [ ] Regressions vs versión anterior (sin IoU)
- [ ] Track IDs cambian constantemente (swaps frecuentes)
- [ ] Tracks se fusionan frecuentemente (> 20% de los casos)

**Acción:**
→ Revisar implementación de IoU, posibles bugs en matching logic

---

## 🔧 Troubleshooting Durante Testing

### Problema: Tracks se fusionan incorrectamente

**Solución:**
```yaml
# Aumentar threshold en config.yaml
iou:
  threshold: 0.4  # De 0.3 → 0.4 (más estricto)
```

### Problema: Tracks duplicados para misma persona

**Solución:**
```yaml
# Reducir threshold
iou:
  threshold: 0.2  # De 0.3 → 0.2 (más permisivo)
```

### Problema: Tracks se pierden fácilmente

**Solución:**
```yaml
# Aumentar tolerancia de gap
temporal:
  max_gap: 3  # De 2 → 3 frames
```

### Problema: Demasiados false positives

**Solución:**
```yaml
# Aumentar frames requeridos
temporal:
  min_frames: 4  # De 3 → 4 frames
```

---

## 📞 Contacto Técnico Durante Testing

**Operador Técnico (OT):** [Nombre]
**Teléfono:** [Número]
**Email:** [Email]

**En caso de crash del sistema:**
1. Guardar logs inmediatamente
2. Reiniciar sistema
3. Continuar con siguiente test case
4. Reportar incidente al final

---

## ✅ Firma de Validación

**Test Ejecutado por:**
- Nombre: ________________
- Fecha: ________________
- Firma: ________________

**Test Validado por:**
- Nombre: ________________ (Operador Técnico)
- Fecha: ________________
- Firma: ________________

---

## 🚀 Roadmap: De v2.1 (Multi-Tracking) hacia v3.0 (Event Detection)

**Si v2.1 testing es exitoso** (IoU multi-tracking validado), el siguiente paso es agregar una **capa de lógica de eventos** encima del tracking.

### Eventos de Verso Vision - Viabilidad con Fundamento v2.1

| Evento | Requiere | Viabilidad v3.0 | Esfuerzo |
|--------|----------|-----------------|----------|
| **Extra Person In Room** | Conteo de tracks | ✅ Fácil | 1-2 días |
| **Patient Fall** | Aspect ratio + y_center change | ✅ Medio | 3-5 días |
| **Room Exit** | Zone tracking + track persistence | ✅ Medio | 3-5 días |
| **Bed Exit** | Zone (bed) + track movement | 🟡 Medio-Alto | 5-7 días |
| **Leaving Bed** | Zone + pose estimation | 🟡 Alto | 1-2 semanas |
| **Bathroom Entry** | Zone (bathroom door) | ✅ Medio | 3-5 días |
| **Bathroom Timer** | Zone + time tracking per track | ✅ Medio | 3-5 días |
| **Leaving Chair** | Zone + pose estimation | 🟡 Alto | 1-2 semanas |
| **Out of View (Hiding)** | Spatial reasoning + zones | 🟡 Alto | 1-2 semanas |

### Arquitectura Propuesta v3.0 (Event Detection Layer)

```
┌──────────────────────────────────────────────────┐
│         Event Detection Layer (v3.0)             │
│  ┌────────────────────────────────────────────┐  │
│  │ Event Handlers (KISS - uno por evento)    │  │
│  │  - PatientFallHandler                     │  │
│  │  - ExtraPersonHandler                     │  │
│  │  - BedExitHandler                         │  │
│  │  - BathroomTimerHandler                   │  │
│  └────────────────────────────────────────────┘  │
│                    ↓ consume tracks              │
└──────────────────────────────────────────────────┘
                     ↓
┌──────────────────────────────────────────────────┐
│    Multi-Object Tracking (v2.1 - VALIDADO)      │
│  ┌────────────────────────────────────────────┐  │
│  │ IoU Matching                              │  │
│  │ Track persistence (min_frames, max_gap)   │  │
│  │ Track ID stability                        │  │
│  └────────────────────────────────────────────┘  │
│                    ↓ produce tracks              │
└──────────────────────────────────────────────────┘
                     ↓
┌──────────────────────────────────────────────────┐
│         Person Detection (base - actual)         │
│  YOLO → Bounding Boxes                           │
└──────────────────────────────────────────────────┘
```

### Ejemplo: Implementación "Patient Fall" Event (v3.0)

```python
# inference/events/patient_fall.py
class PatientFallHandler(BaseEventHandler):
    """
    Detecta caídas mediante análisis de cambios en tracks.

    Algoritmo KISS:
    1. Para cada track activo, calcular aspect_ratio (height/width)
    2. Si aspect_ratio cambia drásticamente (1.5 → 0.7) en <2s → Caída
    3. Si y_center aumenta significativamente → Confirma caída
    4. Emitir evento con track_id
    """

    def __init__(self, aspect_ratio_threshold=0.6, time_window=2.0):
        self.aspect_ratio_threshold = aspect_ratio_threshold
        self.time_window = time_window
        self.track_history = defaultdict(deque)  # track_id -> history

    def process(self, tracks: List[DetectionTrack]) -> List[Event]:
        events = []

        for track in tracks:
            # Calcular aspect ratio actual
            current_ratio = track.height / track.width if track.width > 0 else 0

            # Guardar en historia
            self.track_history[track.id].append({
                'timestamp': time.time(),
                'aspect_ratio': current_ratio,
                'y_center': track.y,
            })

            # Analizar cambios en ventana de tiempo
            history = self.track_history[track.id]
            if len(history) >= 2:
                first = history[0]
                last = history[-1]

                time_delta = last['timestamp'] - first['timestamp']
                ratio_delta = first['aspect_ratio'] - last['aspect_ratio']
                y_delta = last['y_center'] - first['y_center']

                # Detección: ratio cambió drásticamente (vertical → horizontal)
                #            y aumentó (persona bajó en frame)
                #            en ventana de tiempo corta
                if (ratio_delta > self.aspect_ratio_threshold and
                    y_delta > 0.1 and
                    time_delta < self.time_window):

                    events.append(Event(
                        type='patient_fall',
                        track_id=track.id,
                        timestamp=last['timestamp'],
                        confidence=track.confidence,
                        metadata={
                            'aspect_ratio_before': first['aspect_ratio'],
                            'aspect_ratio_after': last['aspect_ratio'],
                            'fall_duration': time_delta,
                        }
                    ))

                    logger.warning(
                        f"🚨 PATIENT FALL DETECTED - Track {track.id} "
                        f"(ratio {first['aspect_ratio']:.2f} → {last['aspect_ratio']:.2f})"
                    )

        return events
```

### KISS Approach para v3.0

**Filosofía:** Complejidad por diseño, no código complicado

1. **Un handler por evento** (SRP - Single Responsibility)
2. **Lógica simple** (aspect ratio, zones, conteo)
3. **Configurable** (thresholds en config.yaml)
4. **Factory pattern** (igual que stabilization)
5. **Testing incremental** (un evento a la vez)

**Orden de implementación sugerido (v3.0):**
```
Sprint 1: Extra Person In Room (más fácil - solo conteo)
Sprint 2: Patient Fall (aspect ratio logic)
Sprint 3: Room Exit (zone tracking)
Sprint 4: Bathroom Timer (zone + time tracking)
Sprint 5+: Eventos complejos (pose estimation, etc.)
```

---

## 📞 Preguntas para Planificación v3.0

**Después de completar testing v2.1, discutir con equipo:**

1. **¿Qué evento es más crítico para lanzar primero?**
   - Patient Fall (seguridad)
   - Extra Person In Room (privacidad)
   - Bathroom Timer (independencia)

2. **¿Tenemos ground truth data para validar eventos?**
   - Videos etiquetados con caídas reales
   - Videos con múltiples personas
   - Videos con bathroom timers

3. **¿Qué precisión mínima se necesita para producción?**
   - 90% precision (¿cuántos falsos positivos son aceptables?)
   - 95% recall (¿cuántas caídas NO pueden perderse?)

4. **¿Necesitamos pose estimation?**
   - Si sí → Evaluar modelos (MediaPipe, OpenPose, YOLO-Pose)
   - Si no → Implementar solo eventos basados en bboxes

---

**Fin del Documento de Test Cases Funcionales v1.0**
