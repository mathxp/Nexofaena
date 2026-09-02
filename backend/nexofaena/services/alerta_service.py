from django.utils import timezone

from nexofaena.models.alerta import Alerta, TipoAlerta

DIAS_AVISO_VENCIMIENTO = 30


class AlertaService:
    @staticmethod
    def _cerrar_alerta(alerta):
        if not alerta:
            return

        alerta.leida = True
        alerta.save(update_fields=["leida"])

    @staticmethod
    def verificar_stock_producto(producto):
        if not producto or producto.stock_minimo <= 0:
            return None

        stock_actual = producto.stock_actual
        stock_minimo = producto.stock_minimo

        alertas_abiertas = Alerta.objects.filter(
            inventario=producto,
            leida=False,
            tipo_alerta__in=[
                TipoAlerta.STOCK_BAJO,
                TipoAlerta.STOCK_CRITICO,
            ],
        )

        # Si el stock volvió a estar sano, cerrar alertas abiertas.
        if stock_actual > stock_minimo:
            alertas_abiertas.update(leida=True)
            return None

        if stock_actual < stock_minimo:
            tipo = TipoAlerta.STOCK_CRITICO
            mensaje = (
                f"{producto.nombre} está con stock crítico. "
                f"Stock actual: {stock_actual}. Stock mínimo: {stock_minimo}."
            )
        else:
            tipo = TipoAlerta.STOCK_BAJO
            mensaje = (
                f"{producto.nombre} está justo en el stock mínimo. "
                f"Stock actual: {stock_actual}. Stock mínimo: {stock_minimo}."
            )

        # Evita duplicados: si ya existe alerta abierta del mismo tipo, no crea otra.
        alerta_existente = alertas_abiertas.filter(tipo_alerta=tipo).first()

        if alerta_existente:
            return alerta_existente

        # Si cambió de STOCK_BAJO a STOCK_CRITICO, cerramos la anterior.
        alertas_abiertas.exclude(tipo_alerta=tipo).update(leida=True)

        return Alerta.objects.create(
            inventario=producto,
            bodega=producto.bodega,
            tipo_alerta=tipo,
            mensaje=mensaje,
            leida=False,
        )

    @staticmethod
    def verificar_vencimiento_detalle(detalle, dias_aviso=DIAS_AVISO_VENCIMIENTO):
        """
        Regla Minera Teck: genera/actualiza una alerta de VENCIMIENTO cuando
        un EPP entregado está próximo a superar su vida útil o ya la superó.
        """
        if not detalle or not detalle.fecha_vencimiento_vida_util:
            return None

        alerta_existente = Alerta.objects.filter(
            detalle_entrega=detalle,
            tipo_alerta=TipoAlerta.VENCIMIENTO,
            leida=False,
        ).first()

        if detalle.devuelto:
            AlertaService._cerrar_alerta(alerta_existente)
            return None

        dias_restantes = (detalle.fecha_vencimiento_vida_util - timezone.now().date()).days

        if dias_restantes > dias_aviso:
            AlertaService._cerrar_alerta(alerta_existente)
            return None

        trabajador = detalle.entrega.trabajador
        producto = detalle.inventario

        if dias_restantes < 0:
            mensaje = (
                f"{producto.nombre} entregado a {trabajador.nombres} {trabajador.apellido_paterno} "
                f"(RUT {trabajador.rut}) superó su vida útil hace {abs(dias_restantes)} día(s). "
                f"Se exige recambio inmediato."
            )
        else:
            mensaje = (
                f"{producto.nombre} entregado a {trabajador.nombres} {trabajador.apellido_paterno} "
                f"(RUT {trabajador.rut}) vence en {dias_restantes} día(s). Programar recambio."
            )

        if alerta_existente:
            alerta_existente.mensaje = mensaje
            alerta_existente.save(update_fields=["mensaje"])
            return alerta_existente

        return Alerta.objects.create(
            inventario=producto,
            bodega=detalle.entrega.bodega,
            detalle_entrega=detalle,
            tipo_alerta=TipoAlerta.VENCIMIENTO,
            mensaje=mensaje,
            leida=False,
        )

    @staticmethod
    def generar_alerta_descuadre(producto, bodega, diferencia, auditoria_id):
        """
        Conecta el conteo cíclico con el motor de alertas: cuando un ajuste de
        stock proviene de un descuadre crítico (activo de alto valor o
        desviación fuera del umbral normal), se deja una alerta de posible
        pérdida visible en Alertas y en el Dashboard Gerencial.
        """
        mensaje = (
            f"Auditoría #{auditoria_id}: {producto.nombre} presenta un descuadre de "
            f"{diferencia} unidades respecto al stock del sistema. Posible pérdida, merma o robo hormiga."
        )

        return Alerta.objects.create(
            inventario=producto,
            bodega=bodega,
            tipo_alerta=TipoAlerta.ANOMALIA_CONSUMO,
            mensaje=mensaje,
            leida=False,
        )

    @staticmethod
    def generar_alerta_mantenimiento(unidad, detalle):
        """
        Módulo de Activos Retornables: si una radio vuelve marcada como
        DAÑADA, se avisa para que pase a mantención antes de reasignarla.
        """
        trabajador = detalle.entrega.trabajador
        producto = detalle.inventario

        mensaje = (
            f"{producto.nombre} {unidad.codigo} volvió DAÑADA de {trabajador.nombres} "
            f"{trabajador.apellido_paterno} (RUT {trabajador.rut}). Requiere mantención antes de "
            f"volver a asignarse."
        )

        return Alerta.objects.create(
            inventario=producto,
            bodega=detalle.entrega.bodega,
            detalle_entrega=detalle,
            tipo_alerta=TipoAlerta.MANTENIMIENTO,
            mensaje=mensaje,
            leida=False,
        )

    @staticmethod
    def verificar_cierre_turno_detalle(detalle):
        """
        Módulo de Activos Retornables: avisa si una radio (u otro activo
        devolutivo con unidad individual) sigue "Entregada" sin su
        devolución. Pensado para correr una vez al día, al cierre de turno.
        """
        if not detalle or detalle.devuelto or not detalle.unidad_activo_id:
            return None

        alerta_existente = Alerta.objects.filter(
            detalle_entrega=detalle,
            tipo_alerta=TipoAlerta.CIERRE_TURNO,
            leida=False,
        ).first()

        if alerta_existente:
            return alerta_existente

        trabajador = detalle.entrega.trabajador
        producto = detalle.inventario
        fecha = timezone.localtime(detalle.entrega.fecha_entrega).strftime("%d-%m-%Y %H:%M")

        mensaje = (
            f"{producto.nombre} {detalle.unidad_activo.codigo} entregado a {trabajador.nombres} "
            f"{trabajador.apellido_paterno} (RUT {trabajador.rut}) el {fecha} no ha sido devuelto "
            f"al cierre de turno."
        )

        return Alerta.objects.create(
            inventario=producto,
            bodega=detalle.entrega.bodega,
            detalle_entrega=detalle,
            tipo_alerta=TipoAlerta.CIERRE_TURNO,
            mensaje=mensaje,
            leida=False,
        )