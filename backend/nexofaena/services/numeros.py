"""Números enteros en todo el sistema.

El pañol entrega unidades, pares o cajas completas: no existe "1,5 cascos".
Las cantidades se guardan como enteros y los promedios o proyecciones se
redondean recién al mostrarlos, para que los cálculos internos no pierdan
precisión.
"""

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation


def redondear(valor) -> int:
    """Redondea como se hace a mano (2,5 -> 3).

    El round() de Python redondea al par más cercano (round(2.5) == 2), lo
    que en un informe se ve como un error.
    """
    return int(Decimal(str(valor or 0)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def cantidad_entera(valor) -> Decimal:
    """Convierte lo que llega de un formulario en una cantidad entera.

    Acepta 3, "3" o "3.00", y rechaza 1.5 o un texto con ValueError. Devuelve
    un Decimal porque los campos de stock del modelo son DecimalField.
    """
    try:
        numero = Decimal(str(valor).strip().replace(",", "."))
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError("La cantidad debe ser un número entero.")

    if not numero.is_finite() or numero != numero.to_integral_value():
        raise ValueError("La cantidad debe ser un número entero.")

    return numero.quantize(Decimal("1"))
