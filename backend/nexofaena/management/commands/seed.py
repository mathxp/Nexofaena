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
from nexofaena.models.auditoria_inventario import AuditoriaInventario
from decimal import Decimal

fake = Faker("es_CL")


class Command(BaseCommand):
    help = "Carga datos masivos de prueba para NexoFaena SGI"

    @transaction.atomic
    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.WARNING("Iniciando seed NexoFaena..."))

        roles = self.crear_roles()
        usuarios = self.crear_usuarios(roles)
        bodegas = self.crear_bodegas()
        trabajadores = self.crear_trabajadores()
        inventarios = self.crear_inventario_masivo(bodegas)

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
        self.stdout.write(self.style.SUCCESS(f"Movimientos: {MovimientoInventario.objects.count()}"))
        self.stdout.write(self.style.SUCCESS(f"Entregas EPP: {EntregaEPP.objects.count()}"))
        self.stdout.write(self.style.SUCCESS(f"Alertas: {Alerta.objects.count()}"))
        self.stdout.write(self.style.SUCCESS(f"Auditorías: {AuditoriaInventario.objects.count()}"))

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

        for i in range(20):
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
                "nombre": "Pañol Mina Norte",
                "ubicacion": "Sector Mina Norte",
                "responsable": "Bodeguero Norte",
                "estado": True,
            },
            {
                "nombre": "Pañol Mina Sur",
                "ubicacion": "Sector Mina Sur",
                "responsable": "Bodeguero Sur",
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

        for i in range(120):
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

        productos_base = [
            ("Casco de seguridad", "EPP", "MSA", "V-Gard", "UN"),
            ("Lentes de seguridad", "EPP", "3M", "SecureFit", "UN"),
            ("Guantes de cabritilla", "EPP", "Steelpro", "Classic", "PAR"),
            ("Guantes anticorte", "EPP", "Ansell", "HyFlex", "PAR"),
            ("Zapato de seguridad", "EPP", "Norseg", "Miner", "PAR"),
            ("Bota de seguridad", "EPP", "Bata", "Industrial", "PAR"),
            ("Chaleco reflectante", "EPP", "Steelpro", "Alta Visibilidad", "UN"),
            ("Protector auditivo", "EPP", "3M", "Optime", "UN"),
            ("Respirador medio rostro", "EPP", "3M", "6200", "UN"),
            ("Arnés de seguridad", "EPP", "Segma", "Dieléctrico", "UN"),
            ("Cabo de vida", "EPP", "Segma", "Doble Cola", "UN"),
            ("Overol piloto", "EPP", "Worksafe", "Industrial", "UN"),
            ("Bloqueador solar FPS 50", "EPP", "Raytan", "FPS50", "UN"),
            ("Mascarilla N95", "EPP", "3M", "N95", "CAJA"),
            ("Disco de corte", "Insumo", "Bosch", "Metal 4.5", "UN"),
            ("Disco de desbaste", "Insumo", "Bosch", "Metal 7", "UN"),
            ("Electrodo 6011", "Insumo", "Indura", "6011", "KG"),
            ("Electrodo 7018", "Insumo", "Indura", "7018", "KG"),
            ("Grasa multipropósito", "Insumo", "Shell", "Gadus", "KG"),
            ("Aceite hidráulico ISO 68", "Insumo", "Mobil", "DTE 26", "LT"),
            ("Aceite motor 15W40", "Insumo", "Mobil", "Delvac", "LT"),
            ("Lubricante WD-40", "Insumo", "WD-40", "Multiuso", "UN"),
            ("Paño industrial", "Insumo", "WypAll", "Industrial", "PAQ"),
            ("Cinta aisladora", "Insumo", "3M", "Temflex", "UN"),
            ("Cinta de peligro", "Insumo", "Genérica", "Amarilla Negra", "UN"),
            ("Amarra plástica", "Insumo", "Genérica", "Nylon", "PAQ"),
            ("Perno hexagonal M12", "Insumo", "Genérico", "M12", "UN"),
            ("Tuerca hexagonal M12", "Insumo", "Genérica", "M12", "UN"),
            ("Golilla plana M12", "Insumo", "Genérica", "M12", "UN"),
        ]

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
            for nombre, categoria, marca, modelo, unidad in productos_base:
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
                )

                inventarios.append(inventario)

        return inventarios

    def crear_movimientos_entregas_alertas(self, usuarios, bodegas, trabajadores, inventarios):
        for _ in range(250):
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

            MovimientoInventario.objects.create(
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

        epp_items = [inv for inv in inventarios if inv.codigo.startswith("EPP")]

        tallas = ["S", "M", "L", "XL", "XXL", "38", "39", "40", "41", "42", "43", "44"]

        for _ in range(80):
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
                fecha_entrega=timezone.now(),
                observacion="Entrega EPP generada por seed.",
                firma_base64="",
                estado="ENTREGADO",
            )

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
                )

                MovimientoInventario.objects.create(
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

            for _ in range(4):
                estado = random.choice(["ABIERTA", "CERRADA"])

                auditoria = AuditoriaInventario.objects.create(
                    bodega=bodega,
                    usuario=random.choice(usuarios),
                    fecha_inicio=timezone.now(),
                    fecha_cierre=timezone.now() if estado == "CERRADA" else None,
                    estado=estado,
                    observacion=f"Auditoría {estado.lower()} generada por seed.",
                )

                seleccionados = random.sample(
                    inventarios_bodega,
                    min(random.randint(8, 15), len(inventarios_bodega))
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