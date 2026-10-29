"""
Genera una faena de demostración con 12 semanas de actividad que termina
HOY, para que el Panel Gerencial muestre los modelos funcionando (productos
por agotarse, qué comprar, consumos fuera de lo normal, exceso de stock).

Por qué hace falta: los modelos solo miran ventanas recientes (consumo de
los últimos 30 días, anomalías del mes en curso, 12 semanas de historial).
Datos cargados hace semanas quedan fuera de esas ventanas y el panel se
vacía solo con el paso del tiempo.

Todo lo que crea queda aislado y marcado:
- bodega con código DEMO-PAN ("Faena Demo"),
- productos con código DEMO-*,
- trabajadores con los RUT de TRABAJADORES_DEMO,
- un usuario inactivo (demo.bodeguero) como responsable de los movimientos,
- movimientos con observación "[DEMO]".

Uso:
    python manage.py generar_demo_dashboard          # crea o regenera (fechas al día)
    python manage.py generar_demo_dashboard --borrar # elimina todo lo de la demo

No envía notificaciones: los movimientos se insertan en bloque (sin
signals) y no se crean Alertas, así que no dispara el bot de Telegram.
"""

import random
from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from nexofaena.models.bodega import Bodega
from nexofaena.models.inventario import Inventario
from nexofaena.models.movimiento_inventario import MovimientoInventario
from nexofaena.models.rol import Rol
from nexofaena.models.trabajador import Trabajador
from nexofaena.models.usuario import Usuario
from nexofaena.services.dashboard_service import DashboardService

CODIGO_BODEGA = "DEMO-PAN"
NOMBRE_BODEGA = "Faena Demo"
USERNAME_DEMO = "demo.bodeguero"
MARCA = "[DEMO]"
DIAS_HISTORIAL = 84  # 12 semanas, lo que miran los modelos de consumo

# (código, nombre, precio CLP, stock final, consumo diario, stock mínimo,
#  stock máximo, días de reposición del proveedor). El stock final y el
#  consumo definen el escenario: pocos días de cobertura frente al tiempo de
#  reposición = riesgo de quiebre; muchos meses de cobertura = exceso de stock.
PRODUCTOS_DEMO = [
    ("DEMO-CASCO", "Casco de seguridad", 12990, 14, 4.0, 20, 120, 10),            # urgente
    ("DEMO-GUANTE", "Guantes de nitrilo (par)", 1490, 55, 14.0, 60, 500, 7),      # urgente
    ("DEMO-RESPIR", "Filtro respirador medio rostro", 4590, 20, 3.0, 25, 150, 14),  # urgente
    ("DEMO-LENTE", "Lentes de seguridad", 2490, 38, 5.0, 20, 200, 7),             # pronto
    ("DEMO-TAPON", "Tapón auditivo desechable", 150, 900, 10.0, 100, 1200, 7),
    ("DEMO-CHALECO", "Chaleco reflectante", 5990, 70, 1.5, 15, 120, 10),
    ("DEMO-ZAPATO", "Zapato de seguridad", 39990, 45, 0.8, 10, 80, 21),
    ("DEMO-SOLAR", "Bloqueador solar FPS 50", 5990, 120, 2.0, 30, 200, 7),
    ("DEMO-ARNES", "Arnés de altura", 89990, 38, 0.08, 5, 20, 20),                # exceso de stock
]

# (número de RUT sin DV, nombres, apellido, cargo, consumo inusual este mes)
TRABAJADORES_DEMO = [
    (21900001, "Pedro", "Rojas", "Rigger", True),
    (21900002, "Luis", "Muñoz", "Rigger", False),
    (21900003, "Camila", "Soto", "Rigger", False),
    (21900004, "Jorge", "Díaz", "Rigger", False),
    (21900005, "Andrea", "Pérez", "Rigger", False),
    (21900006, "Felipe", "Contreras", "Rigger", False),
    (21900007, "Ricardo", "Silva", "Rigger", False),
    (21900008, "Daniela", "Morales", "Rigger", False),
    (21900011, "Matías", "Fuentes", "Soldador", True),
    (21900012, "Sebastián", "Araya", "Soldador", False),
    (21900013, "Valentina", "Reyes", "Soldador", False),
    (21900014, "Cristián", "Vargas", "Soldador", False),
    (21900015, "Francisca", "Castro", "Soldador", False),
    (21900016, "Tomás", "Herrera", "Soldador", False),
]

# Cuánto más retira un trabajador "fuera de lo normal" en el mes en curso.
FACTOR_CONSUMO_INUSUAL = 4


def _rut(numero):
    suma, multiplicador = 0, 2
    for digito in reversed(str(numero)):
        suma += int(digito) * multiplicador
        multiplicador = 2 if multiplicador == 7 else multiplicador + 1
    resto = 11 - suma % 11
    dv = {11: "0", 10: "K"}.get(resto, str(resto))
    return f"{numero}-{dv}"


RUTS_DEMO = [_rut(numero) for numero, *_ in TRABAJADORES_DEMO]


class Command(BaseCommand):
    help = "Genera (o borra con --borrar) una faena de demostración con actividad reciente para el Panel Gerencial."

    def add_arguments(self, parser):
        parser.add_argument("--borrar", action="store_true", help="Elimina todos los datos de la demo.")

    def handle(self, *args, **options):
        with transaction.atomic():
            borrados = self._borrar()
            if options["borrar"]:
                DashboardService.invalidar_cache()
                self.stdout.write(self.style.SUCCESS(f"Demo eliminada ({borrados} movimientos borrados)."))
                return

            bodega, usuario, productos, trabajadores = self._crear_base()
            total = self._crear_movimientos(bodega, usuario, productos, trabajadores)

        DashboardService.invalidar_cache()
        self.stdout.write(self.style.SUCCESS(
            f"Demo lista: bodega '{NOMBRE_BODEGA}', {len(productos)} productos, "
            f"{len(trabajadores)} trabajadores y {total} movimientos hasta hoy."
        ))

    def _borrar(self):
        bodega = Bodega.objects.filter(codigo=CODIGO_BODEGA).first()
        borrados = 0
        if bodega:
            borrados, _ = MovimientoInventario.objects.filter(bodega=bodega).delete()
            Inventario.objects.filter(bodega=bodega).delete()
            bodega.delete()
        Trabajador.objects.filter(rut__in=RUTS_DEMO).delete()
        Usuario.objects.filter(username=USERNAME_DEMO).delete()
        return borrados

    def _crear_base(self):
        bodega = Bodega.objects.create(codigo=CODIGO_BODEGA, nombre=NOMBRE_BODEGA, tipo="CENTRAL")

        rol, _ = Rol.objects.get_or_create(nombre="Bodeguero")
        # Inactivo: solo figura como responsable de los movimientos, no puede iniciar sesión.
        usuario = Usuario.objects.create_user(
            username=USERNAME_DEMO, password=None, rut=_rut(21900099), rol=rol, is_active=False,
            first_name="Bodeguero", last_name="Demo",
        )

        productos = []
        for codigo, nombre, precio, stock_final, diario, minimo, maximo, reposicion in PRODUCTOS_DEMO:
            producto = Inventario.objects.create(
                bodega=bodega, codigo=codigo, nombre=nombre,
                precio_unitario=Decimal(precio), stock_actual=Decimal(stock_final),
                stock_minimo=Decimal(minimo), stock_maximo=Decimal(maximo),
                tiempo_reposicion_dias=reposicion,
            )
            productos.append((producto, diario, maximo, minimo))

        trabajadores = [
            (
                Trabajador.objects.create(
                    rut=_rut(numero), nombres=nombres, apellido_paterno=apellido,
                    apellido_materno="Demo", cargo=cargo,
                ),
                inusual,
            )
            for numero, nombres, apellido, cargo, inusual in TRABAJADORES_DEMO
        ]

        return bodega, usuario, productos, trabajadores

    def _crear_movimientos(self, bodega, usuario, productos, trabajadores):
        """
        Reconstruye el historial HACIA ATRÁS desde el stock final de cada
        producto: así el stock de hoy es exactamente el del escenario y cada
        movimiento queda con su stock antes/después coherente. Cuando, yendo
        hacia atrás, el stock superaría el máximo, se intercala el ingreso de
        reposición que lo explica.
        """
        azar = random.Random(42)
        ahora = timezone.localtime()
        inicio_mes = ahora.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        normales = [t for t, inusual in trabajadores if not inusual]
        inusuales = [t for t, inusual in trabajadores if inusual]

        movimientos = []
        for producto, diario, maximo, minimo in productos:
            stock = float(producto.stock_actual)

            for dias_atras in range(DIAS_HISTORIAL + 1):
                dia = ahora - timedelta(days=dias_atras)
                # Turno de 7 a 18 h; hoy, solo hasta la hora anterior a la
                # actual, para no dejar entregas "en el futuro".
                hora_tope = 18 if dias_atras else min(18, ahora.hour - 1)
                if hora_tope < 7:
                    continue

                salidas = self._salidas_del_dia(azar, diario, normales)
                if dia >= inicio_mes and diario >= 1:
                    # Unas FACTOR_CONSUMO_INUSUAL veces lo que retira un compañero del mismo cargo.
                    por_trabajador = max(1, round(diario / len(normales)))
                    for trabajador in inusuales:
                        salidas.append((trabajador, por_trabajador * FACTOR_CONSUMO_INUSUAL))

                # Primero la secuencia del día, de la última operación a la
                # primera (vamos hacia atrás); después se le asignan horas
                # distintas y decrecientes, para que el orden cronológico sea
                # exactamente el de la cadena de stock.
                eventos = []
                for trabajador, cantidad in salidas:
                    antes = stock + cantidad
                    eventos.append((trabajador, "SALIDA", cantidad, antes, stock, "Entrega de EPP"))
                    stock = antes

                    if stock > maximo:
                        # El stock venía de una reposición previa a esta entrega.
                        reposicion = maximo - minimo
                        eventos.append((None, "INGRESO", reposicion, stock - reposicion, stock, "Reposición de proveedor"))
                        stock -= reposicion

                minutos_turno = (hora_tope - 7 + 1) * 60
                minutos = sorted(azar.sample(range(minutos_turno), len(eventos)), reverse=True)
                inicio_turno = dia.replace(hour=7, minute=0, second=0, microsecond=0)
                for (trabajador, tipo, cantidad, antes, despues, detalle), minuto in zip(eventos, minutos):
                    movimientos.append(self._mov(
                        bodega, usuario, producto, trabajador, tipo, cantidad, antes, despues,
                        inicio_turno + timedelta(minutes=minuto), detalle,
                    ))

        creados = MovimientoInventario.objects.bulk_create(movimientos, batch_size=500)
        # "fecha" es auto_now_add: bulk_create la pisa con la hora actual. Se
        # restaura con bulk_update, que no pasa por pre_save.
        for objeto, original in zip(creados, movimientos):
            objeto.fecha = original._fecha_demo
        MovimientoInventario.objects.bulk_update(creados, ["fecha"], batch_size=500)

        return len(creados)

    @staticmethod
    def _salidas_del_dia(azar, diario, trabajadores):
        """Reparte el consumo esperado del día (con variación) en entregas
        de 1 a 3 unidades a trabajadores al azar."""
        if diario < 1:
            # Productos de baja rotación: una entrega ocasional.
            return [(azar.choice(trabajadores), 1)] if azar.random() < diario else []

        restante = max(0, round(diario * azar.uniform(0.6, 1.4)))
        salidas = []
        while restante > 0:
            cantidad = min(restante, azar.randint(1, 3))
            salidas.append((azar.choice(trabajadores), cantidad))
            restante -= cantidad
        return salidas

    @staticmethod
    def _mov(bodega, usuario, producto, trabajador, tipo, cantidad, antes, despues, fecha, detalle):
        movimiento = MovimientoInventario(
            usuario=usuario, bodega=bodega, inventario=producto, trabajador=trabajador,
            tipo_movimiento=tipo, cantidad=Decimal(str(cantidad)),
            stock_anterior=Decimal(str(antes)), stock_actual=Decimal(str(despues)),
            observacion=f"{MARCA} {detalle}",
        )
        movimiento._fecha_demo = fecha
        return movimiento
