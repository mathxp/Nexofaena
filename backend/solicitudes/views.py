# ======================
# DJANGO IMPORTS
# ======================
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone

# ======================
# MODELOS
# ======================
from inventario.models import Insumo, Compra, DetalleCompra, Area
from .models import Solicitud, DetalleSolicitud


# =========================================================
# 📌 CREAR SOLICITUD
# =========================================================
@login_required
def crear_solicitud(request):

    insumos = Insumo.objects.all()
    areas = Area.objects.all()

    if request.method == 'POST':

        area_id = request.POST.get('area')

        if not area_id:
            messages.error(request, "Debe seleccionar un área")
            return redirect('crear_solicitud')

        # Crear cabecera de solicitud
        solicitud = Solicitud.objects.create(
            usuario=request.user,
            area_id=area_id,
            estado='pendiente'
        )

        # Detalles de la solicitud
        insumo_ids = request.POST.getlist('insumo[]')
        cantidades = request.POST.getlist('cantidad[]')

        for insumo_id, cantidad in zip(insumo_ids, cantidades):
            if insumo_id and cantidad:
                DetalleSolicitud.objects.create(
                    solicitud=solicitud,
                    insumo_id=insumo_id,
                    cantidad=int(cantidad)
                )

        messages.success(request, "Solicitud creada correctamente")
        return redirect('lista_solicitudes')

    return render(request, 'solicitudes/crear.html', {
        'insumos': insumos,
        'areas': areas
    })


# =========================================================
# 📌 LISTAR SOLICITUDES
# =========================================================
@login_required
def lista_solicitudes(request):

    # Admin / Jefatura ven todo
    if request.user.is_superuser or request.user.groups.filter(
        name__in=['Administrador', 'Jefatura']
    ).exists():
        solicitudes = Solicitud.objects.all()

    # Usuario normal ve solo las suyas
    else:
        solicitudes = Solicitud.objects.filter(usuario=request.user)

    solicitudes = solicitudes.order_by('-fecha')

    return render(request, 'solicitudes/lista.html', {
        'solicitudes': solicitudes
    })


# =========================================================
# 📌 CAMBIAR ESTADO (APROBAR / RECHAZAR)
# =========================================================
@login_required
def cambiar_estado_solicitud(request, id, estado):

    solicitud = get_object_or_404(Solicitud, id=id)

    # 🔐 CONTROL DE PERMISOS
    if not (
        request.user.is_superuser or
        request.user.groups.filter(name__in=['Administrador', 'Jefatura']).exists()
    ):
        messages.error(request, "No tienes permisos")
        return redirect('lista_solicitudes')

    # ⚠️ evitar doble procesamiento
    if solicitud.estado != 'pendiente':
        messages.warning(request, "Esta solicitud ya fue procesada")
        return redirect('lista_solicitudes')

    # ======================
    # ACTUALIZAR ESTADO
    # ======================
    solicitud.estado = estado
    solicitud.save()

    # ======================
    # SI SE APRUEBA → GENERAR COMPRA
    # ======================
    if estado == 'aprobado':

        compra = Compra.objects.create(
            proveedor=None,
            usuario=request.user,
            fecha=timezone.now(),
            total=0
        )

        total = 0

        for detalle in solicitud.detalles.all():

            subtotal = detalle.cantidad * 0  # TODO: conectar precio real

            DetalleCompra.objects.create(
                compra=compra,
                insumo=detalle.insumo,
                cantidad=detalle.cantidad,
                precio_unitario=0
            )

            total += subtotal

        compra.total = total
        compra.save()

        messages.success(
            request,
            f"Solicitud aprobada y compra #{compra.id} creada"
        )

    else:
        messages.info(request, "Solicitud rechazada")

    return redirect('lista_solicitudes')