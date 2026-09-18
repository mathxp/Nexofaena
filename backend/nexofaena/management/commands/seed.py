from datetime import timedelta

from django.utils import timezone
from django.core.management.base import BaseCommand
from django.db import transaction
from faker import Faker
import random

from nexofaena.models.rol import Rol
from nexofaena.models.usuario import Usuario
from nexofaena.models.trabajador import Trabajador
from nexofaena.models.bodega import Bodega
from nexofaena.models.inventario import Inventario
from nexofaena.models.movimiento_inventario import MovimientoInventario
from nexofaena.models.entrega import EntregaEPP, DetalleEntregaEPP
from nexofaena.models.auditoria_inventario import AuditoriaInventario, DetalleAuditoriaInventario
from nexofaena.models.alerta import Alerta
from nexofaena.models.unidad_activo import UnidadActivo
from decimal import Decimal

fake = Faker("es_CL")

# Semanas de historial simulado hacia atrás para movimientos/entregas: hace
# falta más de SEMANAS_HISTORICO (ml_service.py) para que la regresión lineal
# y el Random Forest de consumo semanal entrenen de verdad en vez de caer
# siempre al fallback por falta de semanas.
DIAS_HISTORICO_SEED = 91


class Command(BaseCommand):
    help = "Carga datos mínimos de prueba para NexoFaena SGI (idempotente: se puede correr las veces que sea sin duplicar)"

    @transaction.atomic
    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.WARNING("Iniciando seed NexoFaena..."))

        self.limpiar_datos_previos()

        roles = self.crear_roles()
        usuarios = self.crear_usuarios(roles)
        bodegas = self.crear_bodegas()
        trabajadores = self.crear_trabajadores()
        inventarios = self.crear_inventario_masivo(bodegas)
        self.crear_radios_bodega_central(bodegas)

        self.crear_movimientos_entregas_alertas(
            usuarios, bodegas, trabajadores, inventarios
        )

        self.crear_auditorias_inventario(usuarios, bodegas)

        self.stdout.write(self.style.SUCCESS("Seed completado correctamente."))
        self.stdout.write(self.style.SUCCESS(f"Roles: {Rol.objects.count()}"))
        self.stdout.write(self.style.SUCCESS(f"Usuarios: {Usuario.objects.count()}"))
        self.stdout.write(self.style.SUCCESS(f"Bodegas: {Bodega.objects.count()}"))
        self.stdout.write(self.style.SUCCESS(f"Trabajadores: {Trabajador.objects.count()}"))
        self.stdout.write(self.style.SUCCESS(f"Inventarios: {Inventario.objects.count()}"))
        self.stdout.write(self.style.SUCCESS(f"Unidades de activo (radios): {UnidadActivo.objects.count()}"))
        self.stdout.write(self.style.SUCCESS(f"Movimientos: {MovimientoInventario.objects.count()}"))
        self.stdout.write(self.style.SUCCESS(f"Entregas EPP: {EntregaEPP.objects.count()}"))
        self.stdout.write(self.style.SUCCESS(f"Alertas: {Alerta.objects.count()}"))
        self.stdout.write(self.style.SUCCESS(f"Auditorías: {AuditoriaInventario.objects.count()}"))

    def limpiar_datos_previos(self):
        """
        Este seed no tiene una clave natural para hacer get_or_create fila por
        fila en movimientos/entregas/alertas/auditorías/trabajadores/inventario
        (a diferencia de Rol/Usuario/Bodega, que sí la tienen y se dejan
        intactos). Sin este borrado previo, correr `manage.py seed` más de
        una vez duplica todo lo demás cada vez. El orden respeta los
        on_delete=PROTECT del modelo (movimientos y detalles antes que
        trabajadores/inventario).
        """
        MovimientoInventario.objects.all().delete()
        AuditoriaInventario.objects.all().delete()  # cascada -> DetalleAuditoriaInventario
        EntregaEPP.objects.all().delete()  # cascada -> DetalleEntregaEPP
        Alerta.objects.all().delete()
        Trabajador.objects.all().delete()
        UnidadActivo.objects.all().delete()  # PROTECT sobre Inventario: hay que borrar antes
        Inventario.objects.all().delete()

        # Bodegas retiradas del roster de prueba: a esta altura ya no tienen
        # inventario/movimientos/entregas/auditorías apuntándoles (todo lo de
        # arriba se acaba de borrar), así que se pueden eliminar sin chocar
        # con los on_delete=PROTECT del modelo.
        Bodega.objects.filter(nombre__in=["Pañol Mina Norte", "Pañol Mina Sur"]).delete()

    def crear_roles(self):
        roles = {}
        nombres_roles = ["Administrador", "Supervisor", "Bodeguero", "Operador"]

        for nombre in nombres_roles:
            rol, _ = Rol.objects.get_or_create(nombre=nombre)
            roles[nombre] = rol

        return roles

    def generar_rut_unico_usuario(self):
        while True:
            rut = f"{random.randint(10000000, 26000000)}-{random.choice(['0','1','2','3','4','5','6','7','8','9','K'])}"
            if not Usuario.objects.filter(rut=rut).exists():
                return rut

    def generar_rut_unico_trabajador(self):
        while True:
            rut = f"{random.randint(10000000, 26000000)}-{random.choice(['0','1','2','3','4','5','6','7','8','9','K'])}"
            if not Trabajador.objects.filter(rut=rut).exists():
                return rut

    def generar_codigo_unico_inventario(self, prefijo):
        while True:
            codigo = f"{prefijo}-{random.randint(10000, 99999)}"
            if not Inventario.objects.filter(codigo=codigo).exists():
                return codigo

    def crear_usuarios(self, roles):
        usuarios = []

        admin, creado = Usuario.objects.get_or_create(
            username="admin",
            defaults={
                "rut": "20866617-7",
                "email": "admin@nexofaena.cl",
                "rol": roles["Administrador"],
                "is_staff": True,
                "is_superuser": True,
            },
        )

        if creado:
            admin.set_password("admin123")
            admin.save()

        usuarios.append(admin)

        usuarios_base = [
            ("supervisor1", "Supervisor", "supervisor@nexofaena.cl"),
            ("bodeguero1", "Bodeguero", "bodeguero@nexofaena.cl"),
            ("operador1", "Operador", "operador@nexofaena.cl"),
        ]

        for username, rol_nombre, email in usuarios_base:
            usuario, creado = Usuario.objects.get_or_create(
                username=username,
                defaults={
                    "rut": self.generar_rut_unico_usuario(),
                    "email": email,
                    "rol": roles[rol_nombre],
                    "is_staff": False,
                    "is_superuser": False,
                    "telefono": f"+569{random.randint(10000000, 99999999)}",
                },
            )

            if creado:
                usuario.set_password("123456")
                usuario.save()

            usuarios.append(usuario)

        for i in range(8):
            username = f"user_demo_{i + 1}"

            usuario, creado = Usuario.objects.get_or_create(
                username=username,
                defaults={
                    "rut": self.generar_rut_unico_usuario(),
                    "email": f"{username}@nexofaena.cl",
                    "rol": random.choice(list(roles.values())),
                    "telefono": f"+569{random.randint(10000000, 99999999)}",
                },
            )

            if creado:
                usuario.set_password("123456")
                usuario.save()

            usuarios.append(usuario)

        return usuarios

    def crear_bodegas(self):
        bodegas_data = [
            {
                "nombre": "Bodega Central",
                "ubicacion": "Casa matriz - Patio logístico",
                "responsable": "Jefe de Bodega",
                "estado": True,
            },
            {
                "nombre": "Bodega Mantención",
                "ubicacion": "Taller de mantenimiento",
                "responsable": "Supervisor Mantención",
                "estado": True,
            },
        ]

        bodegas = []

        for data in bodegas_data:
            bodega, _ = Bodega.objects.get_or_create(
                nombre=data["nombre"],
                defaults=data,
            )
            bodegas.append(bodega)

        return bodegas

    def crear_trabajadores(self):
        trabajadores = []

        cargos = [
            "Operador Camión",
            "Operador Excavadora",
            "Mecánico",
            "Soldador",
            "Eléctrico",
            "Rigger",
            "Supervisor Terreno",
            "Prevencionista",
            "Ayudante Mantención",
            "Operador Planta",
        ]

        for i in range(40):
            trabajador = Trabajador.objects.create(
                rut=self.generar_rut_unico_trabajador(),
                nombres=fake.first_name(),
                apellido_paterno=fake.last_name(),
                apellido_materno=fake.last_name(),
                cargo=random.choice(cargos),
                telefono=f"+569{random.randint(10000000, 99999999)}",
                correo=f"trabajador{i + 1}@nexofaena.cl",
                activo=True,
            )

            trabajadores.append(trabajador)

        return trabajadores

    def crear_inventario_masivo(self, bodegas):
        inventarios = []

        # Precios referenciales de mercado en CLP (retail/mayorista Chile) para
        # que la valorización de inventario y entregas de pañol sea realista.
        productos_base = [
            ("Casco de seguridad", "EPP", "MSA", "V-Gard", "UN", "15990"),
            ("Lentes de seguridad", "EPP", "3M", "SecureFit", "UN", "4990"),
            ("Guantes de cabritilla", "EPP", "Steelpro", "Classic", "PAR", "3990"),
            ("Guantes anticorte", "EPP", "Ansell", "HyFlex", "PAR", "8990"),
            ("Zapato de seguridad", "EPP", "Norseg", "Miner", "PAR", "45990"),
            ("Bota de seguridad", "EPP", "Bata", "Industrial", "PAR", "35990"),
            ("Chaleco reflectante", "EPP", "Steelpro", "Alta Visibilidad", "UN", "6990"),
            ("Protector auditivo", "EPP", "3M", "Optime", "UN", "7990"),
            ("Respirador medio rostro", "EPP", "3M", "6200", "UN", "28990"),
            ("Arnés de seguridad", "EPP", "Segma", "Dieléctrico", "UN", "65990"),
            ("Cabo de vida", "EPP", "Segma", "Doble Cola", "UN", "45990"),
            ("Overol piloto", "EPP", "Worksafe", "Industrial", "UN", "24990"),
            ("Bloqueador solar FPS 50", "EPP", "Raytan", "FPS50", "UN", "5990"),
            ("Mascarilla N95", "EPP", "3M", "N95", "CAJA", "18990"),
            ("Disco de corte", "Insumo", "Bosch", "Metal 4.5", "UN", "1490"),
            ("Disco de desbaste", "Insumo", "Bosch", "Metal 7", "UN", "2990"),
            ("Electrodo 6011", "Insumo", "Indura", "6011", "KG", "3490"),
            ("Electrodo 7018", "Insumo", "Indura", "7018", "KG", "3990"),
            ("Grasa multipropósito", "Insumo", "Shell", "Gadus", "KG", "4990"),
            ("Aceite hidráulico ISO 68", "Insumo", "Mobil", "DTE 26", "LT", "5990"),
            ("Aceite motor 15W40", "Insumo", "Mobil", "Delvac", "LT", "6990"),
            ("Lubricante WD-40", "Insumo", "WD-40", "Multiuso", "UN", "4990"),
            ("Paño industrial", "Insumo", "WypAll", "Industrial", "PAQ", "12990"),
            ("Cinta aisladora", "Insumo", "3M", "Temflex", "UN", "1990"),
            ("Cinta de peligro", "Insumo", "Genérica", "Amarilla Negra", "UN", "3990"),
            ("Amarra plástica", "Insumo", "Genérica", "Nylon", "PAQ", "4990"),
            ("Perno hexagonal M12", "Insumo", "Genérico", "M12", "UN", "350"),
            ("Tuerca hexagonal M12", "Insumo", "Genérica", "M12", "UN", "150"),
            ("Golilla plana M12", "Insumo", "Genérica", "M12", "UN", "80"),
        ]

        clasificaciones_5s = ["SEIRI", "SEITON", "SEISO", "SEIKETSU", "SHITSUKE"]

        ubicaciones = [
            "Rack A-01",
            "Rack A-02",
            "Rack B-01",
            "Rack B-02",
            "Estante C-01",
            "Estante C-02",
            "Zona EPP",
            "Zona Insumos",
            "Pañol Herramientas",
            "Sector Mantención",
        ]

        for bodega in bodegas:
            for nombre, categoria, marca, modelo, unidad, precio in productos_base:
                stock_minimo = random.randint(5, 25)
                stock_maximo = random.randint(stock_minimo + 30, stock_minimo + 180)

                escenario = random.choices(
                    ["critico", "bajo", "normal", "alto"],
                    weights=[10, 20, 55, 15],
                    k=1,
                )[0]

                if escenario == "critico":
                    stock_actual = random.randint(0, max(1, stock_minimo - 1))
                elif escenario == "bajo":
                    stock_actual = random.randint(stock_minimo, stock_minimo + 10)
                elif escenario == "alto":
                    stock_actual = random.randint(stock_maximo + 1, stock_maximo + 40)
                else:
                    stock_actual = random.randint(stock_minimo + 10, stock_maximo)

                prefijo = "EPP" if categoria == "EPP" else "INS"

                inventario = Inventario.objects.create(
                    codigo=self.generar_codigo_unico_inventario(prefijo),
                    nombre=nombre,
                    descripcion=f"{nombre} para uso operacional en faena minera.",
                    marca=marca,
                    modelo=modelo,
                    unidad_medida=unidad,
                    stock_actual=stock_actual,
                    stock_minimo=stock_minimo,
                    stock_maximo=stock_maximo,
                    ubicacion=random.choice(ubicaciones),
                    estado=True,
                    bodega=bodega,
                    precio_unitario=Decimal(precio),
                    clasificacion_5s=random.choice(clasificaciones_5s),
                )

                inventarios.append(inventario)

        return inventarios

    def crear_radios_bodega_central(self, bodegas):
        """
        Radio de comunicación: el ejemplo canónico de activo devolutivo del
        modelo Inventario (se entrega al inicio del turno y debe devolverse
        al final), con trazabilidad por unidad vía UnidadActivo. Solo va en
        Bodega Central.
        """
        bodega_central = next((b for b in bodegas if b.nombre == "Bodega Central"), None)
        if not bodega_central:
            return

        cantidad_radios = 10

        radio = Inventario.objects.create(
            codigo=self.generar_codigo_unico_inventario("RADIO"),
            nombre="Radio de comunicación",
            descripcion="Radio análoga portátil para coordinación en terreno.",
            marca="Motorola",
            modelo="EP150",
            unidad_medida="UN",
            stock_actual=cantidad_radios,
            stock_minimo=2,
            stock_maximo=cantidad_radios,
            ubicacion="Pañol Herramientas",
            estado=True,
            bodega=bodega_central,
            precio_unitario=Decimal("89990"),
            es_devolutivo=True,
            es_activo_critico=True,
            clasificacion_5s="SEITON",
        )

        for i in range(cantidad_radios):
            UnidadActivo.objects.create(
                inventario=radio,
                codigo=f"RADIO-{i + 1:03d}",
                estado="DISPONIBLE",
            )

    def fecha_historica_aleatoria(self):
        """Instante aleatorio dentro de los últimos DIAS_HISTORICO_SEED días,
        usado para que movimientos/entregas queden repartidos en varias
        semanas en vez de todos con timezone.now() (auto_now_add)."""
        return timezone.now() - timedelta(
            days=random.uniform(0, DIAS_HISTORICO_SEED),
            hours=random.uniform(0, 23),
            minutes=random.uniform(0, 59),
        )

    def crear_movimientos_entregas_alertas(self, usuarios, bodegas, trabajadores, inventarios):
        # Fechas simuladas ordenadas cronológicamente: se procesan los
        # movimientos en ese mismo orden para que stock_anterior/stock_actual
        # avancen de forma coherente con la fecha que van a quedar (si se
        # backdatearan al azar después de crear en orden arbitrario, el
        # "libro mayor" de stock quedaría con saltos ilógicos en el tiempo).
        fechas_movimientos = sorted(self.fecha_historica_aleatoria() for _ in range(100))

        movimientos_creados = []

        for fecha_simulada in fechas_movimientos:
            inventario = random.choice(inventarios)
            usuario = random.choice(usuarios)
            trabajador = random.choice(trabajadores)
            tipo = random.choice(["INGRESO", "SALIDA", "AJUSTE"])

            stock_anterior = inventario.stock_actual

            if tipo == "INGRESO":
                cantidad = random.randint(5, 40)
                nuevo_stock = stock_anterior + cantidad
            elif tipo == "SALIDA":
                if stock_anterior <= 0:
                    continue
                cantidad = random.randint(1, min(10, stock_anterior))
                nuevo_stock = stock_anterior - cantidad
            else:
                cantidad = random.randint(1, 15)
                nuevo_stock = max(0, stock_anterior + random.choice([-cantidad, cantidad]))

            inventario.stock_actual = nuevo_stock
            inventario.save()

            movimiento = MovimientoInventario.objects.create(
                usuario=usuario,
                bodega=inventario.bodega,
                inventario=inventario,
                trabajador=trabajador if tipo == "SALIDA" else None,
                tipo_movimiento=tipo,
                cantidad=cantidad,
                stock_anterior=stock_anterior,
                stock_actual=nuevo_stock,
                observacion=f"Movimiento {tipo} generado por seed.",
            )
            movimiento.fecha = fecha_simulada
            movimientos_creados.append(movimiento)

        if movimientos_creados:
            MovimientoInventario.objects.bulk_update(movimientos_creados, ["fecha"])

        epp_items = [inv for inv in inventarios if inv.codigo.startswith("EPP")]

        tallas = ["S", "M", "L", "XL", "XXL", "38", "39", "40", "41", "42", "43", "44"]

        fechas_entregas = sorted(self.fecha_historica_aleatoria() for _ in range(35))

        entregas_creadas = []
        movimientos_entrega_creados = []

        for fecha_simulada in fechas_entregas:
            bodega = random.choice(bodegas)
            usuario = random.choice(usuarios)
            trabajador = random.choice(trabajadores)

            disponibles = [
                inv for inv in epp_items
                if inv.bodega_id == bodega.id and inv.stock_actual > 0
            ]

            if not disponibles:
                continue

            entrega = EntregaEPP.objects.create(
                trabajador=trabajador,
                usuario=usuario,
                bodega=bodega,
                observacion="Entrega EPP generada por seed.",
                firma_base64="",
                estado="COMPLETADA",
            )
            entrega.fecha_entrega = fecha_simulada
            entrega.turno = EntregaEPP.calcular_turno(fecha_simulada)
            entregas_creadas.append(entrega)

            seleccionados = random.sample(
                disponibles,
                min(random.randint(1, 4), len(disponibles))
            )

            for inventario in seleccionados:
                cantidad = random.randint(1, min(3, inventario.stock_actual))
                stock_anterior = inventario.stock_actual

                inventario.stock_actual -= cantidad
                inventario.save()

                DetalleEntregaEPP.objects.create(
                    entrega=entrega,
                    inventario=inventario,
                    cantidad=cantidad,
                    talla=random.choice(tallas),
                    observacion="Detalle EPP generado por seed.",
                    precio_unitario=inventario.precio_unitario,
                )

                movimiento = MovimientoInventario.objects.create(
                    usuario=usuario,
                    bodega=bodega,
                    inventario=inventario,
                    trabajador=trabajador,
                    tipo_movimiento="SALIDA",
                    cantidad=cantidad,
                    stock_anterior=stock_anterior,
                    stock_actual=inventario.stock_actual,
                    observacion="Salida automática por entrega EPP.",
                )
                movimiento.fecha = fecha_simulada
                movimientos_entrega_creados.append(movimiento)

        if entregas_creadas:
            EntregaEPP.objects.bulk_update(entregas_creadas, ["fecha_entrega", "turno"])
        if movimientos_entrega_creados:
            MovimientoInventario.objects.bulk_update(movimientos_entrega_creados, ["fecha"])

        for inventario in Inventario.objects.all():
            if inventario.stock_actual <= inventario.stock_minimo:
                Alerta.objects.create(
                    inventario=inventario,
                    bodega=inventario.bodega,
                    tipo_alerta="STOCK_BAJO",
                    mensaje=f"El producto {inventario.nombre} está bajo el stock mínimo.",
                    leida=random.choice([True, False]),
                    fecha_alerta=timezone.now(),
                )

            if inventario.stock_actual == 0:
                Alerta.objects.create(
                    inventario=inventario,
                    bodega=inventario.bodega,
                    tipo_alerta="SIN_STOCK",
                    mensaje=f"El producto {inventario.nombre} no tiene stock disponible.",
                    leida=False,
                    fecha_alerta=timezone.now(),
                )

            if inventario.stock_actual > inventario.stock_maximo:
                Alerta.objects.create(
                    inventario=inventario,
                    bodega=inventario.bodega,
                    tipo_alerta="SOBRESTOCK",
                    mensaje=f"El producto {inventario.nombre} supera el stock máximo definido.",
                    leida=random.choice([True, False]),
                    fecha_alerta=timezone.now(),
                )

    def crear_auditorias_inventario(self, usuarios, bodegas):
        for bodega in bodegas:
            inventarios_bodega = list(Inventario.objects.filter(bodega=bodega))

            if not inventarios_bodega:
                continue

            for _ in range(2):
                estado = random.choice(["ABIERTA", "CERRADA"])

                auditoria = AuditoriaInventario.objects.create(
                    bodega=bodega,
                    usuario=random.choice(usuarios),
                    fecha_cierre=timezone.now() if estado == "CERRADA" else None,
                    estado=estado,
                    observacion=f"Auditoría {estado.lower()} generada por seed.",
                )

                seleccionados = random.sample(
                    inventarios_bodega,
                    min(random.randint(5, 9), len(inventarios_bodega))
                )

                for inventario in seleccionados:
                    stock_sistema = inventario.stock_actual
                    con_diferencia = random.choice([True, False, False])

                    if con_diferencia:
                        diferencia = random.randint(-5, 5)
                        stock_fisico = max(0, stock_sistema + diferencia)
                    else:
                        stock_fisico = stock_sistema

                    diferencia_final = stock_fisico - stock_sistema

                    DetalleAuditoriaInventario.objects.create(
                        auditoria=auditoria,
                        inventario=inventario,
                        stock_sistema=stock_sistema,
                        stock_fisico=stock_fisico,
                        diferencia=diferencia_final,
                        observacion="Conteo generado por seed.",
                    )

                    if estado == "CERRADA" and diferencia_final != 0:
                        stock_anterior = inventario.stock_actual

                        inventario.stock_actual = Decimal(stock_fisico)
                        inventario.save()

                        MovimientoInventario.objects.create(
                            usuario=auditoria.usuario,
                            bodega=bodega,
                            inventario=inventario,
                            trabajador=None,
                            tipo_movimiento="AJUSTE",
                            cantidad=abs(diferencia_final),
                            stock_anterior=stock_anterior,
                            stock_actual=stock_fisico,
                            observacion="Ajuste automático por auditoría cerrada.",
                        )
