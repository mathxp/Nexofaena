from django.db import transaction
from django.utils import timezone
from django.db.models import Sum, Min

from datetime import timedelta

from .models import Insumo, Lote, Movimiento, Consumo, Alerta


# =====================================================
# 🔥 CORE FEFO (First Expire First Out)
# =====================================================

@transaction.atomic
def consumir_por_lotes(insumo, cantidad):
    """
    Consume stock usando lógica FEFO (primero en vencer, primero en salir)
    """
    lotes = Lote.objects.filter(
        insumo=insumo,
        cantidad__gt=0
    ).order_by('fecha_vencimiento')

    restante = cantidad
    ultimo_lote = None

    for lote in lotes:
        if restante <= 0:
            break

        usado = min(lote.cantidad, restante)

        lote.cantidad -= usado
        lote.save()

        restante -= usado
        ultimo_lote = lote

    if restante > 0:
        raise ValueError("No hay suficiente stock en lotes")

    return ultimo_lote


# =====================================================
# 📦 MOVIMIENTOS DE STOCK
# =====================================================

@transaction.atomic
def registrar_entrada(insumo, cantidad):
    """
    Aumenta el stock del insumo
    """
    insumo.stock_actual += cantidad
    insumo.save()
    return insumo


@transaction.atomic
def registrar_salida(insumo, cantidad):
    """
    Reduce el stock utilizando FEFO
    """
    lote_usado = consumir_por_lotes(insumo, cantidad)

    insumo.stock_actual -= cantidad
    insumo.save()

    return lote_usado


# =====================================================
# 📊 MÉTRICAS Y ESTADÍSTICAS
# =====================================================

def consumo_total_insumo(insumo):
    """
    Total consumido históricamente
    """
    return (
        Consumo.objects.filter(insumo=insumo)
        .aggregate(total=Sum('cantidad'))['total'] or 0
    )


def dias_periodo(insumo):
    """
    Días desde el primer consumo registrado
    """
    primer = Consumo.objects.filter(insumo=insumo).aggregate(
        fecha=Min('fecha')
    )['fecha']

    if not primer:
        return 0

    hoy = timezone.now().date()
    return (hoy - primer).days or 1


def promedio_consumo_diario(insumo):
    """
    Promedio diario de consumo
    """
    total = consumo_total_insumo(insumo)
    dias = dias_periodo(insumo)

    if dias == 0:
        return 0

    return total / dias


def calcular_dias_stock(insumo):
    """
    Cuántos días durará el stock actual
    """
    promedio = promedio_consumo_diario(insumo)

    if promedio == 0:
        return 0

    return int(insumo.stock_actual / promedio)


def calcular_stock_minimo(insumo):
    """
    Stock mínimo recomendado (7 días)
    """
    promedio = promedio_consumo_diario(insumo)

    if promedio == 0:
        return insumo.stock_minimo

    return int(promedio * 7)


def calcular_compra_sugerida(insumo):
    """
    Cantidad sugerida a comprar (14 días de stock)
    """
    promedio = promedio_consumo_diario(insumo)

    if promedio == 0:
        return 0

    recomendado = promedio * 14
    sugerido = recomendado - insumo.stock_actual

    return max(int(sugerido), 0)


# =====================================================
# 🤖 LÓGICA INTELIGENTE (IA SIMULADA)
# =====================================================

def calcular_score(insumo):
    """
    Score de riesgo del insumo (0 a 100)
    """
    promedio = promedio_consumo_diario(insumo)

    if promedio == 0:
        return 100

    dias = calcular_dias_stock(insumo)

    if dias <= 3:
        return 10
    elif dias <= 7:
        return 40
    elif dias <= 14:
        return 70
    else:
        return 100


def detectar_consumo_anormal(insumo):
    """
    Detecta si el último consumo es anormal (mayor al doble del promedio)
    """
    promedio = promedio_consumo_diario(insumo)

    ultimo = (
        Consumo.objects.filter(insumo=insumo)
        .order_by('-fecha')
        .first()
    )

    if not ultimo or promedio == 0:
        return False

    return ultimo.cantidad > (promedio * 2)


def tendencia_consumo(insumo, dias=7):
    """
    Calcula tendencia de consumo en los últimos días
    > 0 = sube
    < 0 = baja
    = 0 = estable
    """
    hoy = timezone.now().date()
    inicio = hoy - timedelta(days=dias)

    consumos = Consumo.objects.filter(
        insumo=insumo,
        fecha__gte=inicio
    ).order_by('fecha')

    if consumos.count() < 2:
        return 0

    valores = [c.cantidad for c in consumos]

    return valores[-1] - valores[0]


# =====================================================
# 🚨 ALERTAS AUTOMÁTICAS
# =====================================================

def verificar_stock_bajo():
    """
    Genera alertas de stock bajo
    """
    for insumo in Insumo.objects.all():
        if insumo.stock_actual <= insumo.stock_minimo:
            Alerta.objects.get_or_create(
                insumo=insumo,
                tipo='stock',
                defaults={'mensaje': f'Stock bajo: {insumo.nombre}'}
            )


def limpiar_alertas_stock():
    """
    Elimina alertas si el stock ya se normalizó
    """
    for alerta in Alerta.objects.filter(tipo='stock'):
        if alerta.insumo.stock_actual > alerta.inso.stock_minimo:
            alerta.delete()


def verificar_vencimientos():
    """
    Genera alertas de vencimiento cercano (<= 7 días)
    """
    hoy = timezone.now().date()

    for lote in Lote.objects.all():
        dias = (lote.fecha_vencimiento - hoy).days

        if dias <= 7:
            Alerta.objects.update_or_create(
                insumo=lote.insumo,
                tipo='vencimiento',
                defaults={
                    'mensaje': f'Lote {lote.numero_lote} vence en {dias} días'
                }
            )