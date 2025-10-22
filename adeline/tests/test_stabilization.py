"""
Stabilization Tests
===================

Property-based tests para estabilización de detecciones.

Invariantes testeadas:
1. Hysteresis: Umbral alto para aparecer, bajo para persistir
2. Temporal: Requiere min_frames consecutivos para confirmar
3. Gap tolerance: Tolera max_gap frames sin detección
4. IoU matching: Distingue objetos de misma clase por posición
5. NoOp stabilizer: Pass-through sin modificar detecciones



  1. TestIoUMatchingStrategy (7 tests):
  - ✅ Diferentes clases → score 0.0
  - ✅ Misma clase + IoU alto → score alto (>0.9)
  - ✅ Misma clase + IoU bajo → score bajo
  - ✅ get_threshold() retorna threshold configurado
  - ✅ enabled flag funciona (toggle on/off)
  - ✅ get_name() retorna 'IoUMatchingStrategy'

  2. TestClassOnlyStrategy (5 tests):
  - ✅ Misma clase → score 1.0
  - ✅ Diferentes clases → score 0.0
  - ✅ NO considera posición espacial (score igual lejos/cerca)
  - ✅ get_threshold() retorna 0.5
  - ✅ get_name() retorna 'ClassOnlyStrategy'

  3. TestHierarchicalMatcher (10 tests):
  - ✅ Usa [IoU, ClassOnly] por defecto
  - ✅ Acepta strategies custom
  - ✅ IoU gana cuando high overlap
  - ✅ ClassOnly fallback cuando IoU bajo
  - ✅ Respeta enabled flag
  - ✅ No re-match tracks ya matched (matched_indices)
  - ✅ Retorna None cuando no hay match
  - ✅ Edge case: todos los tracks matched
  - ✅ Edge case: lista vacía

  ---



"""
import pytest
from inference.stabilization.core import (
    TemporalHysteresisStabilizer,
    NoOpStabilizer,
    calculate_iou,
    StabilizationConfig,
    create_stabilization_strategy,
    DetectionTrack,
)
from inference.stabilization.matching import (
    IoUMatchingStrategy,
    ClassOnlyStrategy,
    HierarchicalMatcher,
)


@pytest.mark.unit
@pytest.mark.stabilization
class TestIoUCalculation:
    """Tests de calculate_iou() (spatial matching)"""

    def test_iou_perfect_match(self):
        """
        Propiedad: IoU de bboxes idénticos debe ser 1.0.
        """
        bbox1 = {'x': 0.5, 'y': 0.5, 'width': 0.2, 'height': 0.2}
        bbox2 = {'x': 0.5, 'y': 0.5, 'width': 0.2, 'height': 0.2}

        iou = calculate_iou(bbox1, bbox2)

        assert iou == pytest.approx(1.0, abs=1e-6), "IoU de bboxes idénticos debe ser 1.0"

    def test_iou_no_overlap(self):
        """
        Propiedad: IoU de bboxes sin overlap debe ser 0.0.
        """
        bbox1 = {'x': 0.25, 'y': 0.25, 'width': 0.1, 'height': 0.1}  # Left
        bbox2 = {'x': 0.75, 'y': 0.75, 'width': 0.1, 'height': 0.1}  # Right

        iou = calculate_iou(bbox1, bbox2)

        assert iou == 0.0, "IoU sin overlap debe ser 0.0"

    def test_iou_partial_overlap(self):
        """
        Propiedad: IoU de bboxes con overlap parcial debe estar en (0.0, 1.0).
        """
        bbox1 = {'x': 0.5, 'y': 0.5, 'width': 0.2, 'height': 0.2}
        bbox2 = {'x': 0.55, 'y': 0.5, 'width': 0.2, 'height': 0.2}  # Shifted right

        iou = calculate_iou(bbox1, bbox2)

        assert 0.0 < iou < 1.0, f"IoU con overlap parcial debe estar en (0, 1), got {iou}"

    def test_iou_high_overlap(self):
        """
        Propiedad: Bboxes casi idénticos deben tener IoU alto (>0.8).
        """
        bbox1 = {'x': 0.5, 'y': 0.5, 'width': 0.2, 'height': 0.2}
        bbox2 = {'x': 0.505, 'y': 0.505, 'width': 0.2, 'height': 0.2}  # Muy similar

        iou = calculate_iou(bbox1, bbox2)

        assert iou > 0.8, f"IoU de bboxes casi idénticos debe ser >0.8, got {iou}"

    def test_iou_symmetry(self):
        """
        Invariante: IoU debe ser simétrico: IoU(A, B) == IoU(B, A).
        """
        bbox1 = {'x': 0.5, 'y': 0.5, 'width': 0.2, 'height': 0.2}
        bbox2 = {'x': 0.6, 'y': 0.6, 'width': 0.15, 'height': 0.15}

        iou_ab = calculate_iou(bbox1, bbox2)
        iou_ba = calculate_iou(bbox2, bbox1)

        assert iou_ab == pytest.approx(iou_ba, abs=1e-6), "IoU debe ser simétrico"

    def test_iou_zero_size_bbox(self):
        """
        Edge case: Bbox de tamaño cero debe retornar IoU 0.0.
        """
        bbox1 = {'x': 0.5, 'y': 0.5, 'width': 0.0, 'height': 0.0}
        bbox2 = {'x': 0.5, 'y': 0.5, 'width': 0.2, 'height': 0.2}

        iou = calculate_iou(bbox1, bbox2)

        assert iou == 0.0, "IoU con bbox de tamaño 0 debe ser 0.0"


@pytest.mark.unit
@pytest.mark.stabilization
class TestHysteresisFiltering:
    """Tests de hysteresis: umbral alto para aparecer, bajo para persistir"""

    def test_low_confidence_ignored(self):
        """
        Invariante: Detección con confidence < appear_conf debe ignorarse.

        Frame 1: person 0.45 → IGNORE (< 0.5 appear_threshold)
        """
        stabilizer = TemporalHysteresisStabilizer(
            min_frames=3,
            max_gap=2,
            appear_conf=0.5,
            persist_conf=0.3,
        )

        detections = [
            {'class': 'person', 'confidence': 0.45, 'x': 0.5, 'y': 0.5, 'width': 0.2, 'height': 0.2}
        ]

        stabilized = stabilizer.process(detections, source_id=0)

        # Debe ignorar (confidence < appear_conf)
        assert len(stabilized) == 0, "Detección con conf < appear_conf debe ignorarse"

    def test_high_confidence_starts_tracking(self):
        """
        Invariante: Detección con confidence >= appear_conf inicia tracking.

        Frame 1: person 0.52 → TRACKING (>= 0.5, pero frames=1/3, no emite aún)
        """
        stabilizer = TemporalHysteresisStabilizer(
            min_frames=3,
            max_gap=2,
            appear_conf=0.5,
            persist_conf=0.3,
        )

        detections = [
            {'class': 'person', 'confidence': 0.52, 'x': 0.5, 'y': 0.5, 'width': 0.2, 'height': 0.2}
        ]

        stabilized = stabilizer.process(detections, source_id=0)

        # No debe emitir aún (necesita min_frames=3)
        assert len(stabilized) == 0, "Primer frame no debe emitir (necesita min_frames)"

        # Verificar que track fue creado (consultar stats)
        stats = stabilizer.get_stats(source_id=0)
        assert stats['active_tracks'] == 1, "Debe haber 1 track activo"

    def test_confirmed_track_uses_lower_threshold(self):
        """
        Invariante: Track confirmado usa persist_conf (más bajo) en vez de appear_conf.

        Hysteresis: Una vez confirmado, tolera confidence más baja.
        """
        stabilizer = TemporalHysteresisStabilizer(
            min_frames=2,  # Reducir para test más rápido
            max_gap=2,
            appear_conf=0.5,
            persist_conf=0.3,
        )

        # Frame 1: conf=0.52 → TRACKING
        detections_f1 = [
            {'class': 'person', 'confidence': 0.52, 'x': 0.5, 'y': 0.5, 'width': 0.2, 'height': 0.2}
        ]
        stabilizer.process(detections_f1, source_id=0)

        # Frame 2: conf=0.51 → CONFIRMED (frames=2/2)
        detections_f2 = [
            {'class': 'person', 'confidence': 0.51, 'x': 0.5, 'y': 0.5, 'width': 0.2, 'height': 0.2}
        ]
        stabilized_f2 = stabilizer.process(detections_f2, source_id=0)
        assert len(stabilized_f2) == 1, "Frame 2 debe confirmar track"

        # Frame 3: conf=0.35 (< appear_conf pero >= persist_conf) → MANTIENE
        detections_f3 = [
            {'class': 'person', 'confidence': 0.35, 'x': 0.5, 'y': 0.5, 'width': 0.2, 'height': 0.2}
        ]
        stabilized_f3 = stabilizer.process(detections_f3, source_id=0)

        # Hysteresis: Debe mantener porque conf >= persist_conf
        assert len(stabilized_f3) == 1, "Debe mantener track con conf >= persist_conf"


@pytest.mark.unit
@pytest.mark.stabilization
class TestTemporalTracking:
    """Tests de tracking temporal (min_frames, max_gap)"""

    def test_requires_min_frames_to_confirm(self):
        """
        Invariante: Requiere min_frames consecutivos para confirmar.

        Frame 1-2: TRACKING
        Frame 3: CONFIRMED (emite)
        """
        stabilizer = TemporalHysteresisStabilizer(
            min_frames=3,
            max_gap=2,
            appear_conf=0.5,
            persist_conf=0.3,
        )

        detection = {'class': 'person', 'confidence': 0.6, 'x': 0.5, 'y': 0.5, 'width': 0.2, 'height': 0.2}

        # Frame 1: NO emite
        stabilized_f1 = stabilizer.process([detection], source_id=0)
        assert len(stabilized_f1) == 0

        # Frame 2: NO emite
        stabilized_f2 = stabilizer.process([detection], source_id=0)
        assert len(stabilized_f2) == 0

        # Frame 3: CONFIRMA y emite
        stabilized_f3 = stabilizer.process([detection], source_id=0)
        assert len(stabilized_f3) == 1, "Debe emitir después de min_frames=3"

    def test_gap_tolerance(self):
        """
        Invariante: Tolera max_gap frames sin detección antes de eliminar.

        Frame 4: (no detection) → GAP 1/2 (tolera)
        Frame 5: (no detection) → REMOVED (gap > max_gap)
        """
        stabilizer = TemporalHysteresisStabilizer(
            min_frames=2,
            max_gap=2,
            appear_conf=0.5,
            persist_conf=0.3,
        )

        detection = {'class': 'person', 'confidence': 0.6, 'x': 0.5, 'y': 0.5, 'width': 0.2, 'height': 0.2}

        # Frames 1-2: Confirmar track
        stabilizer.process([detection], source_id=0)
        stabilized_f2 = stabilizer.process([detection], source_id=0)
        assert len(stabilized_f2) == 1

        # Frame 3: GAP 1/2 (sin detección, pero tolera)
        stabilized_f3 = stabilizer.process([], source_id=0)
        stats = stabilizer.get_stats(source_id=0)
        assert stats['active_tracks'] == 1, "Debe tolerar gap=1"

        # Frame 4: GAP 2/2 (aún tolera)
        stabilized_f4 = stabilizer.process([], source_id=0)
        stats = stabilizer.get_stats(source_id=0)
        assert stats['active_tracks'] == 1, "Debe tolerar gap=2"

        # Frame 5: GAP 3/2 (excede max_gap, elimina)
        stabilized_f5 = stabilizer.process([], source_id=0)
        stats = stabilizer.get_stats(source_id=0)
        assert stats['active_tracks'] == 0, "Debe eliminar track cuando gap > max_gap"


@pytest.mark.unit
@pytest.mark.stabilization
class TestIoUMatching:
    """Tests de IoU matching para multi-object tracking"""

    def test_distinguishes_multiple_objects_same_class(self):
        """
        Invariante CRÍTICO: IoU matching distingue múltiples objetos de misma clase.

        Escenario:
        - 2 personas en posiciones diferentes
        - Deben mantener tracks separados (no confundirse)
        """
        stabilizer = TemporalHysteresisStabilizer(
            min_frames=2,
            max_gap=2,
            appear_conf=0.5,
            persist_conf=0.3,
            iou_threshold=0.3,
        )

        # Frame 1: 2 personas en posiciones distintas
        detections_f1 = [
            {'class': 'person', 'confidence': 0.6, 'x': 0.3, 'y': 0.5, 'width': 0.2, 'height': 0.2},  # Left
            {'class': 'person', 'confidence': 0.6, 'x': 0.7, 'y': 0.5, 'width': 0.2, 'height': 0.2},  # Right
        ]
        stabilizer.process(detections_f1, source_id=0)

        # Frame 2: Mismas posiciones (confirmar tracks)
        detections_f2 = [
            {'class': 'person', 'confidence': 0.6, 'x': 0.3, 'y': 0.5, 'width': 0.2, 'height': 0.2},  # Left
            {'class': 'person', 'confidence': 0.6, 'x': 0.7, 'y': 0.5, 'width': 0.2, 'height': 0.2},  # Right
        ]
        stabilized_f2 = stabilizer.process(detections_f2, source_id=0)

        # Debe emitir 2 detecciones (tracks separados)
        assert len(stabilized_f2) == 2, "Debe mantener 2 tracks separados"

        # Verificar que stats confirma 2 tracks activos
        stats = stabilizer.get_stats(source_id=0)
        assert stats['active_tracks'] == 2

    def test_tracks_dont_swap_positions(self):
        """
        Invariante: Tracks no deben intercambiarse cuando objetos se mueven.

        Escenario:
        - Frame 1: person @ (0.3, 0.5), person @ (0.7, 0.5)
        - Frame 2: person @ (0.35, 0.5), person @ (0.75, 0.5) (ambos se mueven)
        - Debe matchear correctamente (no swap)
        """
        stabilizer = TemporalHysteresisStabilizer(
            min_frames=1,  # Confirmar inmediatamente para simplificar test
            max_gap=2,
            appear_conf=0.5,
            persist_conf=0.3,
            iou_threshold=0.3,
        )

        # Frame 1
        detections_f1 = [
            {'class': 'person', 'confidence': 0.6, 'x': 0.3, 'y': 0.5, 'width': 0.2, 'height': 0.2},
            {'class': 'person', 'confidence': 0.6, 'x': 0.7, 'y': 0.5, 'width': 0.2, 'height': 0.2},
        ]
        stabilized_f1 = stabilizer.process(detections_f1, source_id=0)
        assert len(stabilized_f1) == 2

        # Frame 2: Movimiento leve (IoU > 0.3 con posiciones anteriores)
        detections_f2 = [
            {'class': 'person', 'confidence': 0.6, 'x': 0.32, 'y': 0.5, 'width': 0.2, 'height': 0.2},
            {'class': 'person', 'confidence': 0.6, 'x': 0.72, 'y': 0.5, 'width': 0.2, 'height': 0.2},
        ]
        stabilized_f2 = stabilizer.process(detections_f2, source_id=0)

        # Debe mantener 2 tracks (no confundir)
        assert len(stabilized_f2) == 2

        # Verificar coordenadas (deben corresponder a las detecciones actuales)
        positions = [(d['x'], d['y']) for d in stabilized_f2]
        assert (0.32, 0.5) in positions
        assert (0.72, 0.5) in positions


@pytest.mark.unit
@pytest.mark.stabilization
class TestNoOpStabilizer:
    """Tests de NoOpStabilizer (baseline sin estabilización)"""

    def test_noop_pass_through(self):
        """
        Invariante: NoOpStabilizer debe pasar detecciones sin modificar.
        """
        stabilizer = NoOpStabilizer()

        detections = [
            {'class': 'person', 'confidence': 0.6, 'x': 0.5, 'y': 0.5, 'width': 0.2, 'height': 0.2},
            {'class': 'car', 'confidence': 0.8, 'x': 0.3, 'y': 0.3, 'width': 0.1, 'height': 0.1},
        ]

        stabilized = stabilizer.process(detections, source_id=0)

        # Debe retornar exactamente lo mismo
        assert stabilized == detections

    def test_noop_no_stats(self):
        """
        Propiedad: NoOpStabilizer.get_stats() retorna dict básico.
        """
        stabilizer = NoOpStabilizer()

        stats = stabilizer.get_stats(source_id=0)

        assert stats == {'mode': 'none'}


@pytest.mark.unit
@pytest.mark.stabilization
class TestStabilizationFactory:
    """Tests de factory para crear estrategias"""

    def test_factory_creates_noop_for_none_mode(self):
        """
        Propiedad: Factory con mode='none' debe crear NoOpStabilizer.
        """
        config = StabilizationConfig(mode='none')
        stabilizer = create_stabilization_strategy(config)

        assert isinstance(stabilizer, NoOpStabilizer)

    def test_factory_creates_temporal_hysteresis_for_temporal_mode(self):
        """
        Propiedad: Factory con mode='temporal' debe crear TemporalHysteresisStabilizer.
        """
        config = StabilizationConfig(
            mode='temporal',
            temporal_min_frames=3,
            temporal_max_gap=2,
            hysteresis_appear_conf=0.5,
            hysteresis_persist_conf=0.3,
            iou_threshold=0.3,
        )
        stabilizer = create_stabilization_strategy(config)

        assert isinstance(stabilizer, TemporalHysteresisStabilizer)

    def test_factory_validates_invalid_mode(self):
        """
        Invariante: Factory debe rechazar modos inválidos.
        """
        config = StabilizationConfig(mode='invalid_mode')

        with pytest.raises(ValueError) as exc_info:
            create_stabilization_strategy(config)

        assert 'invalid_mode' in str(exc_info.value).lower()

    def test_factory_validates_min_frames(self):
        """
        Invariante: min_frames debe ser >= 1.
        """
        config = StabilizationConfig(
            mode='temporal',
            temporal_min_frames=0,  # Inválido
        )

        with pytest.raises(ValueError) as exc_info:
            create_stabilization_strategy(config)

        assert 'min_frames' in str(exc_info.value).lower()

    def test_factory_validates_hysteresis_order(self):
        """
        Invariante: persist_conf debe ser <= appear_conf.
        """
        config = StabilizationConfig(
            mode='temporal',
            hysteresis_appear_conf=0.3,
            hysteresis_persist_conf=0.5,  # Inválido (> appear_conf)
        )

        with pytest.raises(ValueError) as exc_info:
            create_stabilization_strategy(config)

        assert 'persist' in str(exc_info.value).lower()


# ============================================================================
# Matching Strategies Tests (Strategy Pattern)
# ============================================================================

@pytest.mark.unit
@pytest.mark.stabilization
class TestIoUMatchingStrategy:
    """Tests para IoUMatchingStrategy (spatial matching)"""

    def test_different_class_returns_zero_score(self):
        """
        Invariante: Diferentes clases → score 0.0 (no match).
        """
        strategy = IoUMatchingStrategy(threshold=0.3)

        detection = {
            'class': 'person',
            'x': 0.5, 'y': 0.5,
            'width': 0.2, 'height': 0.2
        }

        # Track con clase diferente
        track = DetectionTrack(
            class_name='car',
            x=0.5, y=0.5,
            width=0.2, height=0.2,
            confidence=0.8
        )

        score = strategy.calculate_similarity(detection, track)

        assert score == 0.0, "Diferentes clases deben retornar score 0.0"

    def test_same_class_high_iou_returns_high_score(self):
        """
        Invariante: Misma clase + IoU alto → score alto.
        """
        strategy = IoUMatchingStrategy(threshold=0.3)

        detection = {
            'class': 'person',
            'x': 0.5, 'y': 0.5,
            'width': 0.2, 'height': 0.2
        }

        # Track en misma posición (IoU ~1.0)
        track = DetectionTrack(
            class_name='person',
            x=0.5, y=0.5,
            width=0.2, height=0.2,
            confidence=0.8
        )

        score = strategy.calculate_similarity(detection, track)

        assert score > 0.9, f"IoU de bboxes casi idénticos debe ser >0.9, got {score}"

    def test_same_class_low_iou_returns_low_score(self):
        """
        Invariante: Misma clase + IoU bajo → score bajo.
        """
        strategy = IoUMatchingStrategy(threshold=0.3)

        detection = {
            'class': 'person',
            'x': 0.3, 'y': 0.3,  # Left side
            'width': 0.2, 'height': 0.2
        }

        # Track lejos (right side)
        track = DetectionTrack(
            class_name='person',
            x=0.7, y=0.7,
            width=0.2, height=0.2,
            confidence=0.8
        )

        score = strategy.calculate_similarity(detection, track)

        # Debe ser muy bajo o cero (no overlap)
        assert score < 0.1, f"IoU de bboxes separados debe ser <0.1, got {score}"

    def test_get_threshold_returns_configured_threshold(self):
        """
        Propiedad: get_threshold() retorna el threshold configurado.
        """
        strategy = IoUMatchingStrategy(threshold=0.4)
        assert strategy.get_threshold() == 0.4

        strategy2 = IoUMatchingStrategy(threshold=0.5)
        assert strategy2.get_threshold() == 0.5

    def test_enabled_flag_works(self):
        """
        Propiedad: enabled flag se puede toggle on/off.
        """
        strategy = IoUMatchingStrategy(threshold=0.3)

        # Default enabled
        assert strategy.enabled is True

        # Toggle off
        strategy.enabled = False
        assert strategy.enabled is False

        # Toggle on
        strategy.enabled = True
        assert strategy.enabled is True

    def test_get_name_returns_class_name(self):
        """
        Propiedad: get_name() retorna nombre de la clase.
        """
        strategy = IoUMatchingStrategy(threshold=0.3)
        assert strategy.get_name() == 'IoUMatchingStrategy'


@pytest.mark.unit
@pytest.mark.stabilization
class TestClassOnlyStrategy:
    """Tests para ClassOnlyStrategy (fallback matching)"""

    def test_same_class_returns_one(self):
        """
        Invariante: Misma clase → score 1.0 (perfect match).
        """
        strategy = ClassOnlyStrategy()

        detection = {
            'class': 'person',
            'x': 0.3, 'y': 0.3,
            'width': 0.2, 'height': 0.2
        }

        track = DetectionTrack(
            class_name='person',
            x=0.7, y=0.7,  # Posición diferente (no importa)
            width=0.2, height=0.2,
            confidence=0.8
        )

        score = strategy.calculate_similarity(detection, track)

        assert score == 1.0, "Misma clase debe retornar score 1.0"

    def test_different_class_returns_zero(self):
        """
        Invariante: Diferentes clases → score 0.0.
        """
        strategy = ClassOnlyStrategy()

        detection = {
            'class': 'person',
            'x': 0.5, 'y': 0.5,
            'width': 0.2, 'height': 0.2
        }

        track = DetectionTrack(
            class_name='car',
            x=0.5, y=0.5,  # Misma posición (no importa)
            width=0.2, height=0.2,
            confidence=0.8
        )

        score = strategy.calculate_similarity(detection, track)

        assert score == 0.0, "Diferentes clases deben retornar score 0.0"

    def test_ignores_spatial_position(self):
        """
        Propiedad: ClassOnlyStrategy NO considera posición espacial.
        """
        strategy = ClassOnlyStrategy()

        detection = {
            'class': 'person',
            'x': 0.1, 'y': 0.1,
            'width': 0.1, 'height': 0.1
        }

        # Track muy lejos
        track_far = DetectionTrack(
            class_name='person',
            x=0.9, y=0.9,
            width=0.3, height=0.3,
            confidence=0.8
        )

        # Track cerca
        track_near = DetectionTrack(
            class_name='person',
            x=0.12, y=0.12,
            width=0.1, height=0.1,
            confidence=0.8
        )

        score_far = strategy.calculate_similarity(detection, track_far)
        score_near = strategy.calculate_similarity(detection, track_near)

        # Ambos deben ser 1.0 (solo importa clase)
        assert score_far == score_near == 1.0

    def test_get_threshold_returns_half(self):
        """
        Propiedad: ClassOnly threshold es 0.5 (binary matching).
        """
        strategy = ClassOnlyStrategy()
        assert strategy.get_threshold() == 0.5

    def test_get_name_returns_class_name(self):
        """
        Propiedad: get_name() retorna nombre de la clase.
        """
        strategy = ClassOnlyStrategy()
        assert strategy.get_name() == 'ClassOnlyStrategy'


@pytest.mark.unit
@pytest.mark.stabilization
class TestHierarchicalMatcher:
    """Tests para HierarchicalMatcher (Chain of Responsibility)"""

    def test_uses_default_strategies_when_none_provided(self):
        """
        Propiedad: HierarchicalMatcher usa [IoU, ClassOnly] por defecto.
        """
        matcher = HierarchicalMatcher()

        assert len(matcher.strategies) == 2
        assert isinstance(matcher.strategies[0], IoUMatchingStrategy)
        assert isinstance(matcher.strategies[1], ClassOnlyStrategy)

    def test_uses_custom_strategies_when_provided(self):
        """
        Propiedad: Acepta strategies custom en constructor.
        """
        custom_iou = IoUMatchingStrategy(threshold=0.5)
        matcher = HierarchicalMatcher(strategies=[custom_iou])

        assert len(matcher.strategies) == 1
        assert matcher.strategies[0] is custom_iou

    def test_iou_strategy_wins_when_high_overlap(self):
        """
        Invariante: IoU strategy gana cuando hay high overlap.
        """
        matcher = HierarchicalMatcher(iou_threshold=0.3)

        detection = {
            'class': 'person',
            'x': 0.5, 'y': 0.5,
            'width': 0.2, 'height': 0.2
        }

        # Track con IoU alto
        track = DetectionTrack(
            class_name='person',
            x=0.51, y=0.51,  # Muy cerca
            width=0.2, height=0.2,
            confidence=0.8
        )

        result = matcher.find_best_match(detection, [track], matched_indices=set())

        assert result is not None
        best_track, idx, score, strategy_name = result
        assert strategy_name == 'IoUMatchingStrategy'
        assert score > 0.8  # IoU alto

    def test_classonly_fallback_when_iou_low(self):
        """
        Invariante: ClassOnly fallback cuando IoU no encuentra match.
        """
        matcher = HierarchicalMatcher(iou_threshold=0.3)

        detection = {
            'class': 'person',
            'x': 0.2, 'y': 0.2,
            'width': 0.1, 'height': 0.1
        }

        # Track lejos (IoU ~0, pero misma clase)
        track = DetectionTrack(
            class_name='person',
            x=0.8, y=0.8,
            width=0.1, height=0.1,
            confidence=0.8
        )

        result = matcher.find_best_match(detection, [track], matched_indices=set())

        assert result is not None
        best_track, idx, score, strategy_name = result
        assert strategy_name == 'ClassOnlyStrategy'
        assert score == 1.0  # ClassOnly score

    def test_respects_enabled_flag(self):
        """
        Invariante: Respeta enabled flag (skip strategies desactivadas).
        """
        matcher = HierarchicalMatcher(iou_threshold=0.3)

        # Desactivar IoU strategy
        matcher.strategies[0].enabled = False

        detection = {
            'class': 'person',
            'x': 0.5, 'y': 0.5,
            'width': 0.2, 'height': 0.2
        }

        # Track con IoU alto (normalmente ganaría IoU)
        track = DetectionTrack(
            class_name='person',
            x=0.51, y=0.51,
            width=0.2, height=0.2,
            confidence=0.8
        )

        result = matcher.find_best_match(detection, [track], matched_indices=set())

        # Debe usar ClassOnly (IoU desactivado)
        assert result is not None
        _, _, _, strategy_name = result
        assert strategy_name == 'ClassOnlyStrategy'

    def test_skips_already_matched_tracks(self):
        """
        Invariante: No re-match tracks ya matched (matched_indices).
        """
        matcher = HierarchicalMatcher(iou_threshold=0.3)

        detection = {
            'class': 'person',
            'x': 0.5, 'y': 0.5,
            'width': 0.2, 'height': 0.2
        }

        track1 = DetectionTrack(
            class_name='person',
            x=0.5, y=0.5,
            width=0.2, height=0.2,
            confidence=0.8
        )

        track2 = DetectionTrack(
            class_name='person',
            x=0.6, y=0.6,
            width=0.2, height=0.2,
            confidence=0.8
        )

        # track1 (idx=0) ya matched
        matched_indices = {0}

        result = matcher.find_best_match(
            detection,
            [track1, track2],
            matched_indices=matched_indices
        )

        # Debe match con track2 (idx=1), no con track1
        assert result is not None
        _, matched_idx, _, _ = result
        assert matched_idx == 1

    def test_returns_none_when_no_match(self):
        """
        Invariante: Retorna None cuando ninguna strategy encuentra match.
        """
        matcher = HierarchicalMatcher(iou_threshold=0.3)

        detection = {
            'class': 'person',
            'x': 0.5, 'y': 0.5,
            'width': 0.2, 'height': 0.2
        }

        # Track con clase diferente (no match)
        track = DetectionTrack(
            class_name='car',
            x=0.5, y=0.5,
            width=0.2, height=0.2,
            confidence=0.8
        )

        result = matcher.find_best_match(detection, [track], matched_indices=set())

        assert result is None, "Debe retornar None cuando no hay match"

    def test_returns_none_when_all_tracks_matched(self):
        """
        Edge case: Retorna None cuando todos los tracks ya están matched.
        """
        matcher = HierarchicalMatcher(iou_threshold=0.3)

        detection = {
            'class': 'person',
            'x': 0.5, 'y': 0.5,
            'width': 0.2, 'height': 0.2
        }

        track = DetectionTrack(
            class_name='person',
            x=0.5, y=0.5,
            width=0.2, height=0.2,
            confidence=0.8
        )

        # Todos los tracks ya matched
        matched_indices = {0}

        result = matcher.find_best_match(
            detection,
            [track],
            matched_indices=matched_indices
        )

        assert result is None

    def test_returns_none_when_empty_tracks(self):
        """
        Edge case: Retorna None cuando lista de tracks vacía.
        """
        matcher = HierarchicalMatcher(iou_threshold=0.3)

        detection = {
            'class': 'person',
            'x': 0.5, 'y': 0.5,
            'width': 0.2, 'height': 0.2
        }

        result = matcher.find_best_match(detection, [], matched_indices=set())

        assert result is None
