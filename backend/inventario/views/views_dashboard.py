from django.shortcuts import render
from django.db.models import F
from django.contrib.auth.decorators import login_required

from inventario.models import Insumo, Alerta

from ..services import (
    verificar_stock_bajo,
    limpiar_alertas_stock,
    verificar_vencimientos,
    calcular_dias_stock,
    calcular_stock_minimo
)


# =====================================================
# 📊 DASHBOARD PRINCIPAL
# =====================================================

@login_required
def dashboard(request):
    """
    Dashboard de inventario:
    - KPIs generales
    - Alertas
    - Gráfico de stock
    - Prioridad inteligente
    """

    # =====================================================
    # 🔄 ACTUALIZACIÓN AUTOMÁTICA
    # =====================================================
    verificar_stock_bajo()
    limpiar_alertas_stock()
    verificar_vencimientos()

    # =====================================================
    # 📦 DATOS BASE
    # =====================================================
    insumos = Insumo.objects.all()
    alertas = Alerta.objects.all()

    # =====================================================
    # 📊 KPIs
    # =====================================================
    total_insumos = insumos.count()

    bajo_stock = insumos.filter(
        stock_actual__lte=F('stock_minimo')
    ).count()

    stock_total = sum(i.stock_actual for i in insumos)

    porcentaje_critico = (
        int((bajo_stock / total_insumos) * 100)
        if total_insumos > 0 else 0
    )

    # =====================================================
    # 📈 DATOS PARA GRÁFICOS
    # =====================================================
    nombres = [i.nombre for i in insumos]
    stocks = [i.stock_actual for i in insumos]

    # =====================================================
    # 🧠 PRIORIDAD INTELIGENTE
    # =====================================================
    prioridad = []

    for insumo in insumos:
        dias = calcular_dias_stock(insumo)
        minimo = calcular_stock_minimo(insumo)

        # 🎯 Clasificación de urgencia
        if dias <= 3:
            nivel = "CRITICO"
            color = "danger"
        elif dias <= 7:
            nivel = "MEDIO"
            color = "warning"
        else:
            nivel = "BAJO"
            color = "success"

        prioridad.append({
            'nombre': insumo.nombre,
            'stock': insumo.stock_actual,
            'dias': dias,
            'minimo': minimo,
            'nivel': nivel,
            'color': color
        })

    # 🔥 Ordenar por urgencia real
    prioridad.sort(key=lambda x: x['dias'])

    # =====================================================
    # 🎯 CONTEXTO
    # =====================================================
    context = {
        'total_insumos': total_insumos,
        'total_alertas': alertas.count(),
        'bajo_stock': bajo_stock,
        'stock_total': stock_total,
        'porcentaje_critico': porcentaje_critico,
        'alertas': alertas,
        'nombres': nombres,
        'stocks': stocks,
        'prioridad': prioridad
    }

    return render(request, 'dashboard.html', context)