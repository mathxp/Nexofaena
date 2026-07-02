from nexofaena.models.alerta import Alerta, TipoAlerta


class AlertaService:
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