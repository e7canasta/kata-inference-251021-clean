"""
ROI Invariant Tests
===================

Property-based tests para invariantes críticas de ROI.

Invariantes testeadas:
1. make_square_multiple() → siempre cuadrado
2. expand(preserve_square=True) → mantiene cuadrado
3. smooth_with() con inputs cuadrados → output cuadrado
4. make_square_multiple() → múltiplo de imgsz
5. expand() → nunca excede frame bounds
"""
import pytest
from inference.roi.adaptive import ROIBox


@pytest.mark.unit
@pytest.mark.roi
class TestROIBoxSquareInvariant:
    """Tests de invariante: ROI cuadrado se mantiene cuadrado"""

    def test_make_square_multiple_always_square(self):
        """
        Invariante: make_square_multiple() SIEMPRE retorna ROI cuadrado.

        Property: ∀ roi, roi.make_square_multiple(...).is_square == True
        """
        # Caso 1: ROI rectangular horizontal
        roi = ROIBox(x1=10, y1=20, x2=100, y2=80)
        assert not roi.is_square, "Precondición: ROI debe ser rectangular"

        square = roi.make_square_multiple(
            imgsz=320,
            min_multiple=1,
            max_multiple=4,
            frame_shape=(1080, 1920),
        )

        assert square.is_square, "Postcondición: Resultado debe ser cuadrado"
        assert square.width == square.height

    def test_make_square_multiple_various_sizes(self):
        """
        Invariante: make_square_multiple() es cuadrado para todos los tamaños.

        Casos: rectangular vertical, horizontal, casi cuadrado
        """
        test_cases = [
            # (x1, y1, x2, y2, description)
            (0, 0, 100, 200, "vertical"),
            (0, 0, 200, 100, "horizontal"),
            (10, 20, 110, 115, "casi cuadrado"),
            (50, 50, 150, 250, "vertical offset"),
        ]

        for x1, y1, x2, y2, desc in test_cases:
            roi = ROIBox(x1=x1, y1=y1, x2=x2, y2=y2)

            square = roi.make_square_multiple(
                imgsz=320,
                min_multiple=1,
                max_multiple=4,
                frame_shape=(1080, 1920),
            )

            assert square.is_square, f"Falló para caso: {desc}"
            assert square.width == square.height, f"Width != height para: {desc}"

    def test_make_square_multiple_respects_imgsz_multiple(self):
        """
        Invariante: make_square_multiple() retorna tamaño múltiplo de imgsz.

        Property: ∀ roi, (roi.make_square_multiple(...).width % imgsz) == 0
        """
        roi = ROIBox(x1=10, y1=10, x2=450, y2=300)  # 440x290
        imgsz = 320

        square = roi.make_square_multiple(
            imgsz=imgsz,
            min_multiple=1,
            max_multiple=4,
            frame_shape=(1080, 1920),
        )

        # Verificar múltiplo
        assert square.width % imgsz == 0, f"Width {square.width} no es múltiplo de {imgsz}"
        assert square.height % imgsz == 0, f"Height {square.height} no es múltiplo de {imgsz}"

        # Verificar en rango [min, max]
        multiple = square.width // imgsz
        assert 1 <= multiple <= 4, f"Múltiplo {multiple} fuera de rango [1, 4]"

    def test_expand_preserves_square(self):
        """
        Invariante: expand(preserve_square=True) mantiene forma cuadrada.

        Property: ∀ roi cuadrado, roi.expand(..., preserve_square=True).is_square == True
        """
        # Crear ROI cuadrado
        roi = ROIBox(x1=100, y1=100, x2=200, y2=200)
        assert roi.is_square, "Precondición: ROI debe ser cuadrado"

        expanded = roi.expand(
            margin=0.2,
            frame_shape=(1080, 1920),
            preserve_square=True,
        )

        assert expanded.is_square, "Postcondición: Resultado debe ser cuadrado"
        assert expanded.width == expanded.height

    def test_expand_preserves_square_multiple_margins(self):
        """
        Invariante: expand() preserva cuadrado para diferentes márgenes.
        """
        roi = ROIBox(x1=100, y1=100, x2=400, y2=400)
        assert roi.is_square

        margins = [0.0, 0.1, 0.2, 0.3, 0.5]

        for margin in margins:
            expanded = roi.expand(
                margin=margin,
                frame_shape=(1080, 1920),
                preserve_square=True,
            )

            assert expanded.is_square, f"Falló para margin={margin}"
            assert expanded.width == expanded.height

    def test_smooth_with_preserves_square(self):
        """
        Invariante: smooth_with() mantiene cuadrado si ambos inputs son cuadrados.

        Property: ∀ roi1, roi2 cuadrados, roi1.smooth_with(roi2).is_square == True
        """
        roi1 = ROIBox(x1=100, y1=100, x2=200, y2=200)
        roi2 = ROIBox(x1=110, y1=110, x2=210, y2=210)

        assert roi1.is_square and roi2.is_square, "Precondición: ambos cuadrados"

        # Probar diferentes alphas
        alphas = [0.0, 0.3, 0.5, 0.7, 1.0]

        for alpha in alphas:
            smoothed = roi1.smooth_with(roi2, alpha=alpha)

            assert smoothed.is_square, f"Falló para alpha={alpha}"
            assert smoothed.width == smoothed.height


@pytest.mark.unit
@pytest.mark.roi
class TestROIBoxBoundsInvariant:
    """Tests de invariante: ROI respeta límites del frame"""

    def test_expand_never_exceeds_frame_bounds(self):
        """
        Invariante: expand() nunca excede frame bounds.

        Property: ∀ roi, expanded.x1 >= 0 ∧ expanded.y1 >= 0 ∧
                        expanded.x2 <= width ∧ expanded.y2 <= height
        """
        frame_shape = (1080, 1920)  # height, width
        h, w = frame_shape

        # Caso 1: ROI cerca del borde superior izquierdo
        roi = ROIBox(x1=10, y1=10, x2=100, y2=100)
        expanded = roi.expand(margin=0.5, frame_shape=frame_shape)

        assert expanded.x1 >= 0, "x1 debe ser >= 0"
        assert expanded.y1 >= 0, "y1 debe ser >= 0"
        assert expanded.x2 <= w, f"x2={expanded.x2} debe ser <= {w}"
        assert expanded.y2 <= h, f"y2={expanded.y2} debe ser <= {h}"

        # Caso 2: ROI cerca del borde inferior derecho
        roi = ROIBox(x1=1800, y1=980, x2=1900, y2=1060)
        expanded = roi.expand(margin=0.5, frame_shape=frame_shape)

        assert expanded.x1 >= 0
        assert expanded.y1 >= 0
        assert expanded.x2 <= w
        assert expanded.y2 <= h

    def test_make_square_multiple_clips_to_frame(self):
        """
        Invariante: make_square_multiple() clip a frame bounds.
        """
        frame_shape = (1080, 1920)
        h, w = frame_shape

        # ROI que al hacer square excedería bounds
        roi = ROIBox(x1=1700, y1=900, x2=1900, y2=1050)

        square = roi.make_square_multiple(
            imgsz=320,
            min_multiple=1,
            max_multiple=4,
            frame_shape=frame_shape,
        )

        assert square.x1 >= 0
        assert square.y1 >= 0
        assert square.x2 <= w
        assert square.y2 <= h


@pytest.mark.unit
@pytest.mark.roi
class TestROIBoxProperties:
    """Tests de propiedades calculadas de ROIBox"""

    def test_width_height_calculation(self):
        """Propiedades: width y height se calculan correctamente"""
        roi = ROIBox(x1=10, y1=20, x2=110, y2=80)

        assert roi.width == 100, "width = x2 - x1"
        assert roi.height == 60, "height = y2 - y1"

    def test_area_calculation(self):
        """Propiedad: area = width * height"""
        roi = ROIBox(x1=0, y1=0, x2=100, y2=200)

        expected_area = 100 * 200
        assert roi.area == expected_area

    def test_is_square_property(self):
        """Propiedad: is_square detecta correctamente cuadrados"""
        # Cuadrado
        square = ROIBox(x1=0, y1=0, x2=100, y2=100)
        assert square.is_square

        # Rectangular
        rect = ROIBox(x1=0, y1=0, x2=100, y2=50)
        assert not rect.is_square

    def test_get_size_multiple(self):
        """Propiedad: get_size_multiple calcula múltiplo correctamente"""
        roi = ROIBox(x1=0, y1=0, x2=640, y2=640)
        imgsz = 320

        multiple = roi.get_size_multiple(imgsz)
        assert multiple == 2.0, "640 / 320 = 2.0"

    def test_get_crop_ratio(self):
        """Propiedad: get_crop_ratio calcula ratio correctamente"""
        roi = ROIBox(x1=0, y1=0, x2=100, y2=100)
        frame_shape = (200, 200)  # height, width

        ratio = roi.get_crop_ratio(frame_shape)
        expected = (100 * 100) / (200 * 200)  # 0.25
        assert ratio == expected


@pytest.mark.unit
@pytest.mark.roi
class TestROIBoxEdgeCases:
    """Tests de edge cases y corner cases"""

    def test_make_square_multiple_respects_min_multiple(self):
        """Edge case: ROI muy pequeño debe respetar min_multiple"""
        # ROI 10x10 (muy pequeño)
        roi = ROIBox(x1=100, y1=100, x2=110, y2=110)
        imgsz = 320

        square = roi.make_square_multiple(
            imgsz=imgsz,
            min_multiple=1,
            max_multiple=4,
            frame_shape=(1080, 1920),
        )

        # Debe ser al menos 1 × imgsz = 320
        assert square.width >= imgsz, f"Width {square.width} debe ser >= {imgsz}"
        assert square.height >= imgsz

    def test_make_square_multiple_respects_max_multiple(self):
        """Edge case: ROI muy grande debe respetar max_multiple"""
        # ROI 2000x2000 (muy grande)
        roi = ROIBox(x1=0, y1=0, x2=2000, y2=2000)
        imgsz = 320
        max_multiple = 4

        square = roi.make_square_multiple(
            imgsz=imgsz,
            min_multiple=1,
            max_multiple=max_multiple,
            frame_shape=(3000, 3000),  # Frame suficientemente grande
        )

        # Debe ser a lo sumo max_multiple × imgsz = 1280
        max_size = max_multiple * imgsz
        assert square.width <= max_size, f"Width {square.width} debe ser <= {max_size}"
        assert square.height <= max_size

    def test_expand_with_zero_margin(self):
        """Edge case: expand con margin=0 debe retornar mismo ROI"""
        roi = ROIBox(x1=100, y1=100, x2=200, y2=200)

        expanded = roi.expand(margin=0.0, frame_shape=(1080, 1920))

        assert expanded.x1 == roi.x1
        assert expanded.y1 == roi.y1
        assert expanded.x2 == roi.x2
        assert expanded.y2 == roi.y2

    def test_smooth_with_alpha_zero(self):
        """Edge case: smooth_with(alpha=0) debe retornar self"""
        roi1 = ROIBox(x1=100, y1=100, x2=200, y2=200)
        roi2 = ROIBox(x1=200, y1=200, x2=300, y2=300)

        smoothed = roi1.smooth_with(roi2, alpha=0.0)

        # alpha=0 → 0*other + 1*self = self
        assert smoothed.x1 == roi1.x1
        assert smoothed.y1 == roi1.y1
        assert smoothed.x2 == roi1.x2
        assert smoothed.y2 == roi1.y2

    def test_smooth_with_alpha_one(self):
        """Edge case: smooth_with(alpha=1) debe retornar other"""
        roi1 = ROIBox(x1=100, y1=100, x2=200, y2=200)
        roi2 = ROIBox(x1=200, y1=200, x2=300, y2=300)

        smoothed = roi1.smooth_with(roi2, alpha=1.0)

        # alpha=1 → 1*other + 0*self = other
        assert smoothed.x1 == roi2.x1
        assert smoothed.y1 == roi2.y1
        assert smoothed.x2 == roi2.x2
        assert smoothed.y2 == roi2.y2
