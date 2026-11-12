"""Asegura en la Bodega Central los productos que existen en el pañol real.

Uso (primero revisa, después aplica):
    python manage.py agregar_productos_central            # solo muestra el plan
    python manage.py agregar_productos_central --aplicar  # guarda los cambios

Es seguro correrlo varias veces y contra producción:
- Nunca borra ni duplica: si el producto ya está en la Central (mismo nombre),
  lo reutiliza.
- Si falta, lo crea con un código RM-NNNN libre.
- Si su stock está bajo el mínimo (o en cero), lo repone hasta el máximo.
- Todo ingreso de stock queda registrado como movimiento INGRESO, con
  responsable y observación, igual que si se hiciera desde la app.
"""
import re
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from nexofaena.models.bodega import Bodega
from nexofaena.models.inventario import Inventario
from nexofaena.models.movimiento_inventario import MovimientoInventario
from nexofaena.models.usuario import Usuario
from nexofaena.services.dashboard_service import DashboardService

OBSERVACION = "Carga de productos reales del pañol (comando agregar_productos_central)"

# nombre, categoría, marca, modelo, unidad, precio CLP, mínimo, máximo, ¿alto valor?
PRODUCTOS = [
    ("Casco de seguridad", "EPP", "MSA", "V-Gard", "UN", 15990, 8, 40, True),
    ("Lentes de seguridad oscuros", "EPP", "3M", "SecureFit Oscuro", "UN", 5490, 5, 30, False),
    ("Plumón permanente", "Oficina", "Artel", "Punta Fina", "UN", 890, 5, 30, False),
    ("Linterna para casco", "EPP", "Genérica", "LED frontal con clip para casco", "UN", 9990, 3, 15, False),
    ("Guincha de medir 5 m", "Herramientas", "Stanley", "PowerLock 5 m", "UN", 7990, 2, 10, False),
    # Hoja de Teck Carmen de Andacollo para identificar 5 peligros/riesgos
    # antes de una tarea (similar a la HCR). Se entrega por hoja.
    ("Hoja Teck 5 (identificación de 5 peligros)", "Formularios", "Teck", "Teck 5", "UN", 100, 50, 300, False),
]


class Command(BaseCommand):
    help = "Asegura en la Bodega Central los productos del pañol real (sin duplicar ni borrar)."

    def add_arguments(self, parser):
        parser.add_argument("--aplicar", action="store_true", help="Guarda los cambios (sin esto solo muestra el plan).")
        parser.add_argument("--usuario", help="Usuario responsable de los movimientos (por defecto, un administrador).")

    def handle(self, *args, **opciones):
        central = Bodega.objects.filter(nombre="Bodega Central").first()
        if central is None:
            raise CommandError('No existe la "Bodega Central".')

        usuario = self._responsable(opciones.get("usuario"))
        aplicar = opciones["aplicar"]

        self.stdout.write(f"Bodega: {central.nombre} · responsable: {usuario.username}")
        self.stdout.write("MODO: aplicar cambios\n" if aplicar else "MODO: solo revisar (agrega --aplicar para guardar)\n")

        with transaction.atomic():
            cambios = sum(self._asegurar(central, usuario, *producto) for producto in PRODUCTOS)

            if not aplicar:
                transaction.set_rollback(True)

        if aplicar and cambios:
            DashboardService.invalidar_cache()

        resumen = f"\n{cambios} cambio(s) {'guardados' if aplicar else 'pendientes'}."
        self.stdout.write(self.style.SUCCESS(resumen) if aplicar else self.style.WARNING(resumen))

    def _responsable(self, username):
        if username:
            usuario = Usuario.objects.filter(username=username, is_active=True).first()
            if usuario is None:
                raise CommandError(f'No existe un usuario activo "{username}".')
            return usuario

        usuario = (
            Usuario.objects.filter(is_active=True, rol__nombre="Administrador").order_by("id").first()
            or Usuario.objects.filter(is_active=True, is_superuser=True).order_by("id").first()
        )
        if usuario is None:
            raise CommandError("No hay un administrador activo. Indica uno con --usuario.")
        return usuario

    def _asegurar(self, central, usuario, nombre, categoria, marca, modelo, unidad, precio, minimo, maximo, critico):
        producto = (
            Inventario.objects.select_for_update()
            .filter(bodega=central, nombre__iexact=nombre)
            .order_by("id")
            .first()
        )
        cambios = 0

        if producto is None:
            producto = Inventario.objects.create(
                bodega=central,
                codigo=self._codigo_libre(),
                nombre=nombre,
                descripcion=f"{nombre} — {categoria}, uso operacional en faena.",
                marca=marca,
                modelo=modelo,
                unidad_medida=unidad,
                stock_actual=Decimal("0"),
                stock_minimo=Decimal(minimo),
                stock_maximo=Decimal(maximo),
                precio_unitario=Decimal(precio),
                ubicacion=f"Rack {categoria[:3].upper()}-1",
                estado=True,
                es_activo_critico=critico,
                tiempo_reposicion_dias=7,
            )
            self.stdout.write(f"+ {producto.codigo} {nombre}: creado")
            cambios += 1
        else:
            self.stdout.write(f"= {producto.codigo} {nombre}: ya existe (stock {producto.stock_actual})")
            if not producto.estado:
                producto.estado = True
                producto.save(update_fields=["estado"])
                self.stdout.write("    reactivado (estaba inactivo)")
                cambios += 1

        stock = producto.stock_actual
        if stock <= 0 or stock < producto.stock_minimo:
            objetivo = producto.stock_maximo if producto.stock_maximo > 0 else Decimal(maximo)
            cantidad = objetivo - stock
            producto.stock_actual = objetivo
            producto.save(update_fields=["stock_actual"])
            MovimientoInventario.objects.create(
                usuario=usuario,
                bodega=central,
                inventario=producto,
                tipo_movimiento="INGRESO",
                cantidad=cantidad,
                stock_anterior=stock,
                stock_actual=objetivo,
                observacion=OBSERVACION,
            )
            self.stdout.write(f"    ingreso de {cantidad} {producto.unidad_medida}: stock {stock} -> {objetivo}")
            cambios += 1

        return cambios

    @staticmethod
    def _codigo_libre():
        numeros = [
            int(m.group(1))
            for codigo in Inventario.objects.filter(codigo__startswith="RM-").values_list("codigo", flat=True)
            if (m := re.fullmatch(r"RM-(\d+)", codigo))
        ]
        return f"RM-{(max(numeros, default=0) + 1):04d}"
