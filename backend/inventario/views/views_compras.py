from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Sum, F

from decimal import Decimal

from inventario.models import (
    Proveedor, Compra, DetalleCompra,
    Insumo, Lote, Movimiento
)
from inventario.services import registrar_entrada


# =====================================================
# 🛒 CREAR COMPRA
# =====================================================

@login_required
def crear_compra(request):
    """
    Crea una compra base (sin detalles aún)
    """
    proveedores = Proveedor.objects.all()

    if request.method == 'POST':
        try:
            proveedor_id = request.POST.get('proveedor')
            proveedor = get_object_or_404(Proveedor, id=proveedor_id)

            archivo = request.FILES.get('comprobante')

            compra = Compra.objects.create(
                proveedor=proveedor,
                usuario=request.user,
                total=0,
                comprobante=archivo
            )

            return redirect('agregar_detalle', compra.id)

        except Exception as e:
            messages.error(request, f"Error al crear compra: {e}")

    return render(request, 'compras/crear_compra.html', {
        'proveedores': proveedores
    })


# =====================================================
# 📦 AGREGAR DETALLE A COMPRA
# =====================================================

@login_required
def agregar_detalle(request, compra_id):
    """
    Agrega insumos a una compra:
    - Crea lote
    - Registra stock
    - Genera movimiento
    - Recalcula total
    """
    compra = get_object_or_404(Compra, id=compra_id)

    if request.method == 'POST':
        try:
            # ======================
            # DATOS FORM
            # ======================
            insumo_id = request.POST.get('insumo')
            cantidad = int(request.POST.get('cantidad'))
            precio = Decimal(request.POST.get('precio'))
            fecha_vencimiento = request.POST.get('fecha_vencimiento')

            insumo = get_object_or_404(Insumo, id=insumo_id)

            # ======================
            # VALIDACIONES
            # ======================
            if cantidad <= 0:
                raise ValueError("La cantidad debe ser mayor a 0")

            if precio <= 0:
                raise ValueError("El precio debe ser mayor a 0")

            # ======================
            # CREAR LOTE (FEFO)
            # ======================
            lote = Lote.objects.create(
                insumo=insumo,
                numero_lote=f"L-{compra.id}-{insumo.id}-{int(timezone.now().timestamp())}",
                cantidad=cantidad,
                fecha_vencimiento=fecha_vencimiento
            )

            # ======================
            # DETALLE COMPRA
            # ======================
            DetalleCompra.objects.create(
                compra=compra,
                insumo=insumo,
                cantidad=cantidad,
                precio_unitario=precio
            )

            # ======================
            # STOCK + MOVIMIENTO
            # ======================
            registrar_entrada(insumo, cantidad)

            Movimiento.objects.create(
                insumo=insumo,
                usuario=request.user,
                tipo='entrada',
                cantidad=cantidad,
                lote=lote
            )

            # ======================
            # 💰 RECALCULAR TOTAL
            # ======================
            total = DetalleCompra.objects.filter(compra=compra).aggregate(
                total=Sum(F('cantidad') * F('precio_unitario'))
            )['total'] or 0

            compra.total = total
            compra.save()

            messages.success(request, "Insumo agregado correctamente")

        except Exception as e:
            messages.error(request, f"Error: {e}")

        return redirect('agregar_detalle', compra.id)

    return render(request, 'compras/detalle_compra.html', {
        'compra': compra,
        'insumos': Insumo.objects.all(),
        'detalles': DetalleCompra.objects.filter(compra=compra)
    })


# =====================================================
# 📊 HISTORIAL DE COMPRAS
# =====================================================

@login_required
def historial_compras(request):
    """
    Lista compras con filtros:
    - Fecha inicio / fin
    - Proveedor
    """
    compras = Compra.objects.select_related(
        'proveedor', 'usuario'
    ).all().order_by('-fecha')

    # ======================
    # FILTROS
    # ======================
    fecha_inicio = request.GET.get('fecha_inicio')
    fecha_fin = request.GET.get('fecha_fin')
    proveedor_id = request.GET.get('proveedor')

    if fecha_inicio:
        compras = compras.filter(fecha__gte=fecha_inicio)

    if fecha_fin:
        compras = compras.filter(fecha__lte=fecha_fin)

    if proveedor_id:
        compras = compras.filter(proveedor__id=proveedor_id)

    proveedores = Proveedor.objects.all()

    return render(request, 'compras/historial.html', {
        'compras': compras,
        'proveedores': proveedores,
        'filtros': {
            'fecha_inicio': fecha_inicio,
            'fecha_fin': fecha_fin,
            'proveedor': proveedor_id
        }
    })