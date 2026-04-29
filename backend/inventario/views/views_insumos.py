from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone

from ..models import (
    Insumo,
    Movimiento,
    Consumo,
    Compra,
    DetalleCompra,
    Lote
)
from ..forms import InsumoForm
from ..services import registrar_entrada, registrar_salida


# ======================
# 🔐 DECORADOR DE ROLES
# ======================
def requiere_rol(*roles):
    def decorator(view_func):
        def wrapper(request, *args, **kwargs):
            if request.user.is_authenticated:
                if request.user.is_superuser or request.user.groups.filter(name__in=roles).exists():
                    return view_func(request, *args, **kwargs)
            return redirect('dashboard')
        return wrapper
    return decorator


# ======================
# 📦 CRUD INSUMOS
# ======================

@login_required
def lista_insumos(request):
    """
    Lista todos los insumos
    """
    return render(request, 'insumos/lista.html', {
        'insumos': Insumo.objects.all()
    })


@login_required
@requiere_rol('Bodega', 'Administrador')
def crear_insumo(request):
    """
    Crear nuevo insumo
    """
    form = InsumoForm(request.POST or None)

    if form.is_valid():
        form.save()
        messages.success(request, "Insumo creado correctamente")
        return redirect('lista_insumos')

    return render(request, 'insumos/form.html', {'form': form})


@login_required
@requiere_rol('Bodega', 'Administrador')
def editar_insumo(request, id):
    """
    Editar insumo existente
    """
    insumo = get_object_or_404(Insumo, id=id)
    form = InsumoForm(request.POST or None, instance=insumo)

    if form.is_valid():
        form.save()
        messages.success(request, "Insumo actualizado correctamente")
        return redirect('lista_insumos')

    return render(request, 'insumos/form.html', {'form': form})


@login_required
def eliminar_insumo(request, id):
    """
    Eliminar insumo
    """
    insumo = get_object_or_404(Insumo, id=id)
    insumo.delete()

    messages.success(request, "Insumo eliminado correctamente")
    return redirect('lista_insumos')


# ======================
# 🚚 SALIDA DE INSUMOS (FEFO)
# ======================

@login_required
@requiere_rol('Clinico', 'Administrador')
def crear_salida(request):
    """
    Registra salida de insumos usando lógica FEFO
    """

    if request.method == 'POST':
        insumo_id = request.POST.get('insumo')

        # 🔴 Validación básica
        if not insumo_id:
            messages.error(request, "Debe seleccionar un insumo")
            return redirect('reporte_movimientos')

        insumo = get_object_or_404(Insumo, id=insumo_id)
        cantidad = int(request.POST.get('cantidad', 0))

        try:
            # 🔥 Lógica FEFO
            lote_usado = registrar_salida(insumo, cantidad)

            # 📊 Movimiento (auditoría)
            Movimiento.objects.create(
                insumo=insumo,
                usuario=request.user,
                tipo='salida',
                cantidad=cantidad,
                lote=lote_usado
            )

            # 📉 Consumo
            Consumo.objects.create(
                insumo=insumo,
                usuario=request.user,
                cantidad=cantidad,
                fecha=timezone.now().date()
            )

            messages.success(request, "Salida registrada correctamente")

        except ValueError as e:
            messages.error(request, str(e))

    return redirect('reporte_movimientos')