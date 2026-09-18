"""
Seed de datos reales del pañol de RentaMaq (faena), a partir de fotografías
del pañol y conversación directa con el stakeholder (Carlos Guerrero,
RentaMaq). No reemplaza `seed.py` (comando genérico de demo): este comando
es específico para el cliente y se puede correr las veces que sea sin
duplicar datos (usa get_or_create/update_or_create).

IMPORTANTE — antes de correr con --reset:
    1. Respalda la base actual:
       pg_dump -U <usuario> -d <basedatos> -F c -f respaldo_antes_rentamaq.dump
    2. Recién entonces vuelve a correr con --reset --confirmo-respaldo.

Ver docs/SEED_RENTAMAQ.md para el detalle de qué cifras son estimación desde
fotos (marcadas [ESTIMADO] en este archivo) y cuáles vienen confirmadas
directamente por el stakeholder.
"""

import random
from datetime import date, timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from faker import Faker

from nexofaena.models.auditoria_inventario import AuditoriaInventario, DetalleAuditoriaInventario
from nexofaena.models.bodega import Bodega
from nexofaena.models.entrega import DetalleEntregaEPP, EntregaEPP
from nexofaena.models.inventario import Inventario
from nexofaena.models.movimiento_inventario import MovimientoInventario
from nexofaena.models.rol import Rol
from nexofaena.models.trabajador import Trabajador
from nexofaena.models.unidad_activo import UnidadActivo
from nexofaena.models.usuario import Usuario
from nexofaena.services.auditoria_service import AuditoriaInventarioService

fake = Faker("es_CL")

MIN_TRABAJADORES = 50
MAX_TRABAJADORES = 200
DIAS_HISTORIAL = 365

# Radios observadas en fotografías del rack de carga + estante secundario.
# [ESTIMADO] — confirmar con bodega antes de tomarlo como cifra oficial.
CANTIDAD_RADIOS = 30

# Meses de verano austral: más bloqueador solar / repelente sale del pañol.
MESES_VERANO = {12, 1, 2}


# =====================================================================
# UTILIDADES: RUT chileno con dígito verificador válido
# =====================================================================
def _digito_verificador(numero):
    suma = 0
    multiplicador = 2
    for digito in reversed(str(numero)):
        suma += int(digito) * multiplicador
        multiplicador = 2 if multiplicador == 7 else multiplicador + 1

    resto = 11 - (suma % 11)
    if resto == 11:
        return "0"
    if resto == 10:
        return "K"
    return str(resto)


def _rut(numero):
    return f"{numero}-{_digito_verificador(numero)}"


class ContadorRut:
    """Generador secuencial de RUTs válidos sin colisión entre trabajadores
    y usuarios (rangos numéricos separados)."""

    def __init__(self, inicio):
        self._siguiente = inicio

    def nuevo(self):
        rut = _rut(self._siguiente)
        self._siguiente += 1
        return rut


# Cargos con distribución despareja y realista: más operadores/ayudantes que
# especialistas. "cargo" es el agrupamiento estable para comparar consumo
# (las cuadrillas se reasignan sin aviso; el cargo no cambia de un día a otro).
CARGOS_PESOS = [
    ("Operador", 26),
    ("Ayudante", 20),
    ("Mecánico", 12),
    ("Chofer", 10),
    ("Soldador", 8),
    ("Eléctrico", 7),
    ("Rigger", 6),
    ("Supervisor Terreno", 5),
    ("Prevencionista", 4),
    ("Geólogo", 2),
]

# Catálogo real del pañol (fotografías + conversación con el stakeholder).
# Tupla: (nombre, categoria, marca, modelo, unidad_medida, precio_clp,
#         es_devolutivo, tallas_o_None, unidades_por_pack, es_activo_critico)
# Precios [ESTIMADO] a partir de referencias de mercado chileno, no son lista
# de precios real de RentaMaq — ver docs/SEED_RENTAMAQ.md.
CATALOGO = [
    # --- EPP ---
    ("Guantes anticorte", "EPP", "Ansell", "HyFlex", "PAR", 8990, False, ["M", "L", "XL"], 1, False),
    ("Guantes cabritilla", "EPP", "Steelpro", "Classic", "PAR", 3990, False, None, 1, False),
    ("Guantes de nitrilo", "EPP", "Vinilo Chile", "Nitrilo", "PAR", 1490, False, None, 1, False),
    ("Lentes de seguridad claros", "EPP", "3M", "SecureFit Claro", "UN", 4990, False, None, 1, False),
    ("Lentes de seguridad oscuros", "EPP", "3M", "SecureFit Oscuro", "UN", 5490, False, None, 1, False),
    ("Protector auditivo tipo tapón", "EPP", "3M", "1100", "PAR", 990, False, None, 1, False),
    ("Protector auditivo tipo fono", "EPP", "3M", "Optime 98", "UN", 12990, False, None, 1, False),
    ("Cubre nuca", "EPP", "Worksafe", "Térmico", "UN", 2990, False, None, 1, False),
    ("Casco de seguridad", "EPP", "MSA", "V-Gard", "UN", 15990, False, None, 1, True),
    ("Buzo de papel desechable", "EPP", "Lakeland", "Tyvek", "UN", 6990, False, ["M", "L", "XL"], 1, False),
    ("Chaleco reflectante", "EPP", "Steelpro", "Alta Visibilidad", "UN", 6990, False, None, 1, False),
    ("Chaleco geólogo", "EPP", "Steelpro", "Multibolsillo", "UN", 18990, False, None, 1, False),
    ("Mascarilla KN95", "EPP", "3M", "KN95", "UN", 990, False, None, 1, False),
    ("Respirador media cara 3M", "EPP", "3M", "6200", "UN", 28990, False, None, 1, True),
    ("Filtro para respirador 3M", "EPP", "3M", "6001 (repuesto)", "PAR", 7990, False, None, 1, False),
    ("Zapato de seguridad", "EPP", "Norsse", "Miner", "PAR", 45990, False,
     ["38", "39", "40", "41", "42", "43", "44", "45", "46"], 1, True),
    ("Bloqueador solar", "EPP", "Raytan", "FPS50", "UN", 5990, False, None, 1, False),
    ("Repelente de insectos", "EPP", "Raid", "Repelente Familiar", "UN", 4490, False, None, 1, False),
    ("Silbato", "EPP", "Genérico", "Salvavidas", "UN", 1990, False, None, 1, False),

    # --- Izaje y amarre ---
    ("Eslinga", "Izaje", "Segma", "Poliéster", "UN", 24990, False, ["1m", "1.5m", "2m"], 1, True),
    ("Grillete", "Izaje", "Crosby", "3/8", "UN", 8990, False, None, 1, False),
    ("Chicharra / tensor de carga", "Izaje", "Genérico", "Ratchet", "UN", 14990, False, None, 1, False),
    ("Cuerda de viento", "Izaje", "Genérico", "Nylon 8mm", "UN", 12990, False, None, 1, False),
    ("Lienza", "Izaje", "Genérico", "Nylon", "UN", 3990, False, None, 1, False),

    # --- Herramientas ---
    ("Martillo", "Herramienta", "Stanley", "Carpintero", "UN", 9990, False, None, 1, False),
    ("Alicate", "Herramienta", "Stanley", "Universal", "UN", 7990, False, None, 1, False),

    # --- Comunicación (préstamo: requiere devolución) ---
    ("Radio análoga portátil", "Comunicación", "Motorola", "EP150", "UN", 89990, True, None, 1, True),
    ("Cargador / base de carga para radio", "Comunicación", "Motorola", "Base EP150", "UN", 24990, True, None, 1, False),
    ("Batería de repuesto para radio", "Comunicación", "Motorola", "EP150 Battery", "UN", 18990, True, None, 1, False),

    # --- Ferretería ---
    ("Tornillos", "Ferretería", "Genérico", "Surtido", "CAJA", 6990, False, None, 1, False),

    # --- Consumibles y oficina ---
    ("Agua embotellada 500 ml", "Consumible", "Cachantún", "500ml", "UN", 350, False, None, 12, False),
    ("Lápiz pasta", "Oficina", "Bic", "Cristal", "UN", 190, False, None, 1, False),
    ("Plumón permanente", "Oficina", "Artel", "Punta Fina", "UN", 890, False, None, 1, False),
]

# Productos de alta rotación (salen a diario): van sobre todo en Central.
NOMBRES_ALTA_ROTACION = {
    "Guantes anticorte", "Guantes cabritilla", "Guantes de nitrilo",
    "Mascarilla KN95", "Lentes de seguridad claros", "Lentes de seguridad oscuros",
    "Agua embotellada 500 ml", "Protector auditivo tipo tapón",
}

# Productos de renovación periódica por trabajador (cada varios meses).
NOMBRES_RENOVACION = {
    "Casco de seguridad", "Zapato de seguridad", "Buzo de papel desechable",
    "Chaleco reflectante", "Respirador media cara 3M",
}


class Command(BaseCommand):
    help = "Siembra datos reales de RentaMaq: 2 bodegas, ~10 usuarios, trabajadores, catálogo, 12 meses de historial y auditorías."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset", action="store_true",
            help="Borra los datos operativos existentes (trabajadores, inventario, entregas, movimientos, auditorías) antes de sembrar. NO borra usuarios ni roles.",
        )
        parser.add_argument(
            "--confirmo-respaldo", action="store_true",
            help="Confirma que ya respaldaste la base (pg_dump) antes de --reset. Obligatorio junto a --reset.",
        )
        parser.add_argument(
            "--trabajadores", type=int, default=120,
            help=f"Cantidad de trabajadores a generar ({MIN_TRABAJADORES}-{MAX_TRABAJADORES}). Default: 120.",
        )

    def handle(self, *args, **options):
        reset = options["reset"]
        confirmo_respaldo = options["confirmo_respaldo"]
        num_trabajadores = options["trabajadores"]

        if reset and not confirmo_respaldo:
            raise CommandError(
                "Falta --confirmo-respaldo. Antes de --reset debes respaldar la base:\n"
                "    pg_dump -U <usuario> -d <basedatos> -F c -f respaldo_antes_rentamaq.dump\n"
                "Vuelve a correr el comando agregando --confirmo-respaldo una vez respaldada."
            )

        if not (MIN_TRABAJADORES <= num_trabajadores <= MAX_TRABAJADORES):
            raise CommandError(f"--trabajadores debe estar entre {MIN_TRABAJADORES} y {MAX_TRABAJADORES}.")

        # Idempotencia real: generar 12 meses de historial es costoso y no
        # tiene una clave natural para hacer get_or_create movimiento por
        # movimiento. En vez de eso, el comando se niega a duplicar: si ya
        # hay datos operativos sembrados, exige --reset explícito para
        # repoblar en vez de crear una segunda copia por accidente.
        ya_sembrado = Bodega.objects.filter(codigo="BOD-CEN").exists() and Trabajador.objects.exists()
        if ya_sembrado and not reset:
            self.stdout.write(self.style.WARNING(
                "Ya existen datos de RentaMaq sembrados (Bodega Central + trabajadores). "
                "No se duplica nada. Usa --reset --confirmo-respaldo para repoblar desde cero."
            ))
            return

        with transaction.atomic():
            if reset:
                self._reset()

            bodegas = self._crear_bodegas()
            roles = self._crear_roles()
            usuarios = self._crear_usuarios(roles)
            trabajadores = self._crear_trabajadores(num_trabajadores)
            productos = self._crear_catalogo(bodegas)
            self._crear_historial(usuarios, bodegas, trabajadores, productos)
            self._crear_auditorias(usuarios, bodegas, productos)

        self.stdout.write(self.style.SUCCESS("Seed RentaMaq completado correctamente."))
        self.stdout.write(self.style.SUCCESS(f"Bodegas: {Bodega.objects.count()}"))
        self.stdout.write(self.style.SUCCESS(f"Usuarios: {Usuario.objects.count()}"))
        self.stdout.write(self.style.SUCCESS(f"Trabajadores: {Trabajador.objects.count()}"))
        self.stdout.write(self.style.SUCCESS(f"Inventario: {Inventario.objects.count()}"))
        self.stdout.write(self.style.SUCCESS(f"Unidades de activo (radios, etc.): {UnidadActivo.objects.count()}"))
        self.stdout.write(self.style.SUCCESS(f"Entregas EPP: {EntregaEPP.objects.count()}"))
        self.stdout.write(self.style.SUCCESS(f"Movimientos: {MovimientoInventario.objects.count()}"))
        self.stdout.write(self.style.SUCCESS(f"Auditorías: {AuditoriaInventario.objects.count()}"))

    # =================================================================
    # RESET — solo datos operativos/catálogo/trabajadores. Nunca borra
    # Usuario ni Rol (evita invalidar cuentas ya en uso).
    # =================================================================
    def _reset(self):
        self.stdout.write(self.style.WARNING("Borrando datos operativos existentes..."))

        DetalleAuditoriaInventario.objects.all().delete()
        AuditoriaInventario.objects.all().delete()
        MovimientoInventario.objects.all().delete()
        DetalleEntregaEPP.objects.all().delete()
        EntregaEPP.objects.all().delete()
        UnidadActivo.objects.all().delete()
        Inventario.objects.all().delete()
        Trabajador.objects.all().delete()
        Bodega.objects.exclude(codigo__in=["BOD-CEN", "BOD-RES"]).delete()

    # =================================================================
    # 1. BODEGAS
    # =================================================================
    def _crear_bodegas(self):
        # `nombre` es único desde antes de que existiera `codigo`: si ya hay
        # una "Bodega Central" del seed genérico, se reutiliza esa fila (se
        # le agrega código/tipo) en vez de intentar crear una segunda con el
        # mismo nombre, lo que violaría la unicidad de `nombre`.
        central, _ = Bodega.objects.update_or_create(
            nombre="Bodega Central",
            defaults={
                "codigo": "BOD-CEN",
                "tipo": "CENTRAL",
                "ubicacion": "Faena RentaMaq - Acceso principal",
                "responsable": "Encargado de Bodega",
                "descripcion": "Atiende al trabajador y realiza las entregas diarias.",
                "estado": True,
            },
        )
        reserva, _ = Bodega.objects.update_or_create(
            nombre="Bodega de Reserva",
            defaults={
                "codigo": "BOD-RES",
                "tipo": "RESERVA",
                "ubicacion": "Faena RentaMaq - Sector posterior a la Central",
                "responsable": "Encargado de Bodega",
                "descripcion": "Stock de respaldo y material de baja rotación.",
                "estado": True,
            },
        )
        return {"central": central, "reserva": reserva}

    # =================================================================
    # 2. ROLES Y USUARIOS (~10)
    # =================================================================
    def _crear_roles(self):
        nombres = ["Administrador", "Supervisor", "Bodeguero", "Encargado de Bodega"]
        return {nombre: Rol.objects.get_or_create(nombre=nombre)[0] for nombre in nombres}

    def _crear_usuarios(self, roles):
        contador_rut = ContadorRut(15000000)

        # 4 Bodeguero + 2 Encargado de Bodega + 3 Supervisor/Jefatura + 1 Administrador = 10
        definiciones = (
            [("bodeguero", i, "Bodeguero") for i in range(1, 5)]
            + [("encargado", i, "Encargado de Bodega") for i in range(1, 3)]
            + [("jefatura", i, "Supervisor") for i in range(1, 4)]
            + [("admin_rentamaq", 1, "Administrador")]
        )

        usuarios = {"Bodeguero": [], "Encargado de Bodega": [], "Supervisor": [], "Administrador": []}

        for prefijo, indice, nombre_rol in definiciones:
            username = f"{prefijo}{indice}" if prefijo != "admin_rentamaq" else prefijo
            nombre = fake.first_name()
            apellido = fake.last_name()

            usuario, creado = Usuario.objects.get_or_create(
                username=username,
                defaults={
                    "rut": contador_rut.nuevo(),
                    "first_name": nombre,
                    "last_name": apellido,
                    "email": f"{username}@rentamaq.cl",
                    "rol": roles[nombre_rol],
                    "is_staff": nombre_rol == "Administrador",
                    "is_superuser": nombre_rol == "Administrador",
                    "telefono": f"+569{random.randint(10000000, 99999999)}",
                },
            )

            if creado:
                usuario.set_password("rentamaq2024")
                usuario.save()

            usuarios[nombre_rol].append(usuario)

        return usuarios

    # =================================================================
    # 3. TRABAJADORES (50-200, no confundir con usuarios)
    # =================================================================
    def _crear_trabajadores(self, cantidad):
        contador_rut = ContadorRut(18000000)
        cargos = [c for c, _ in CARGOS_PESOS]
        pesos = [p for _, p in CARGOS_PESOS]

        hoy = date.today()
        trabajadores = []

        for _ in range(cantidad):
            cargo = random.choices(cargos, weights=pesos, k=1)[0]
            turno = random.choices(["dia", "noche"], weights=[55, 45], k=1)[0]
            # ~8% desvinculados: el sistema debe poder manejar historial de
            # entregas de gente que ya no está en la faena.
            activo = random.random() > 0.08
            dias_antiguedad = random.randint(15, 365 * 4)
            fecha_ingreso = hoy - timedelta(days=dias_antiguedad)

            trabajador = Trabajador.objects.create(
                rut=contador_rut.nuevo(),
                nombres=fake.first_name(),
                apellido_paterno=fake.last_name(),
                apellido_materno=fake.last_name(),
                cargo=cargo,
                turno=turno,
                telefono=f"+569{random.randint(10000000, 99999999)}",
                correo=None,
                activo=activo,
                fecha_ingreso=fecha_ingreso,
            )
            trabajadores.append(trabajador)

        return trabajadores

    # =================================================================
    # 4. CATÁLOGO (con variantes de talla como filas separadas)
    # =================================================================
    def _crear_catalogo(self, bodegas):
        productos = []  # lista de dicts: {"inventario": obj, "nombre_base": str}

        # Contador global simple: nada de prefijos derivados del nombre (un
        # producto de una sola palabra como "Alicate" da un prefijo de una
        # letra y colisiona fácil con otro). RM-0001, RM-0002... no colisiona
        # nunca y es trivial de verificar contra códigos ya existentes.
        siguiente_numero = [1]
        codigos_existentes = set(Inventario.objects.values_list("codigo", flat=True))

        def siguiente_codigo():
            while True:
                codigo = f"RM-{siguiente_numero[0]:04d}"
                siguiente_numero[0] += 1
                if codigo not in codigos_existentes:
                    codigos_existentes.add(codigo)
                    return codigo

        for (nombre, categoria, marca, modelo, unidad, precio, es_devolutivo,
             tallas, _unidades_por_pack, es_critico) in CATALOGO:

            variantes = tallas if tallas else [None]
            alta_rotacion = nombre in NOMBRES_ALTA_ROTACION
            renovacion = nombre in NOMBRES_RENOVACION

            for talla in variantes:
                for clave_bodega, bodega in bodegas.items():
                    # Alta rotación -> más stock en Central, poco respaldo en
                    # Reserva. Baja rotación / respaldo -> al revés.
                    if alta_rotacion:
                        stock_minimo = 20 if clave_bodega == "central" else 10
                        stock_maximo = 200 if clave_bodega == "central" else 60
                    elif renovacion:
                        stock_minimo = 8 if clave_bodega == "central" else 15
                        stock_maximo = 40 if clave_bodega == "central" else 80
                    else:
                        stock_minimo = 5 if clave_bodega == "central" else 10
                        stock_maximo = 30 if clave_bodega == "central" else 60

                    stock_actual = random.randint(stock_minimo, stock_maximo)

                    inventario = Inventario.objects.create(
                        bodega=bodega,
                        codigo=siguiente_codigo(),
                        nombre=nombre,
                        descripcion=f"{nombre} — {categoria}, uso operacional en faena.",
                        marca=marca,
                        modelo=modelo,
                        talla=talla,
                        unidad_medida=unidad,
                        stock_actual=stock_actual,
                        stock_minimo=stock_minimo,
                        stock_maximo=stock_maximo,
                        precio_unitario=Decimal(str(precio)),
                        ubicacion=f"Rack {categoria[:3].upper()}-{random.randint(1, 9)}",
                        estado=True,
                        es_devolutivo=es_devolutivo,
                        es_activo_critico=es_critico,
                        tiempo_reposicion_dias=14 if clave_bodega == "reserva" else 7,
                    )

                    productos.append({
                        "inventario": inventario,
                        "nombre_base": nombre,
                        "bodega_clave": clave_bodega,
                        "alta_rotacion": alta_rotacion,
                        "renovacion": renovacion,
                        "es_devolutivo": es_devolutivo,
                    })

        # Al menos 3 productos de alta rotación en Central quedan bajo el
        # mínimo, para que las alertas tengan algo que mostrar al abrir.
        candidatos_bajo_minimo = [
            p for p in productos
            if p["bodega_clave"] == "central" and p["alta_rotacion"]
        ]
        for p in random.sample(candidatos_bajo_minimo, min(4, len(candidatos_bajo_minimo))):
            inv = p["inventario"]
            inv.stock_actual = max(0, inv.stock_minimo - random.randint(1, 5))
            inv.save(update_fields=["stock_actual"])

        # Radios: unidades individuales serializadas (UnidadActivo), no solo
        # una cantidad agregada. [ESTIMADO ~30, confirmar con bodega].
        radio_central = next(
            p["inventario"] for p in productos
            if p["nombre_base"] == "Radio análoga portátil" and p["bodega_clave"] == "central"
        )
        radio_central.stock_actual = CANTIDAD_RADIOS
        radio_central.stock_minimo = 5
        radio_central.stock_maximo = CANTIDAD_RADIOS
        radio_central.save(update_fields=["stock_actual", "stock_minimo", "stock_maximo"])

        unidades_radio = [
            UnidadActivo.objects.create(inventario=radio_central, codigo=f"RADIO-{i:03d}")
            for i in range(1, CANTIDAD_RADIOS + 1)
        ]

        return {"lista": productos, "unidades_radio": unidades_radio}

    # =================================================================
    # 5. HISTORIAL DE 12 MESES
    # =================================================================
    def _elegir_anomalos_por_cargo(self, trabajadores):
        """2-3 trabajadores por cargo con consumo 3-4x su propio grupo,
        para que el reporte de turno y el K-Means (que compara solo dentro
        del mismo cargo) tengan casos reales que marcar para revisar."""
        por_cargo = {}
        for t in trabajadores:
            por_cargo.setdefault(t.cargo, []).append(t)

        anomalos = set()
        for cargo, grupo in por_cargo.items():
            if len(grupo) < 4:
                continue
            elegidos = random.sample(grupo, min(random.randint(2, 3), len(grupo)))
            anomalos.update(t.id for t in elegidos)

        return anomalos

    def _hora_para_turno(self, turno):
        if turno == "dia":
            return random.randint(8, 18)
        return random.choice(list(range(20, 24)) + list(range(0, 7)))

    @transaction.atomic
    def _crear_entrega(self, fecha_hora, trabajador, bodega, usuario, items):
        """items: lista de (inventario, cantidad, unidad_activo_o_None).
        Descuenta stock, crea EntregaEPP/DetalleEntregaEPP/MovimientoInventario
        y retro-fecha (auto_now_add ignora cualquier fecha pasada al crear).
        Si NINGÚN item tiene stock disponible, no crea nada (evita cabeceras
        de entrega "fantasma" sin ningún detalle)."""
        items_disponibles = [(inv, cant, ua) for inv, cant, ua in items if inv.stock_actual >= cant]
        if not items_disponibles:
            return None

        entrega = EntregaEPP.objects.create(
            trabajador=trabajador,
            usuario=usuario,
            bodega=bodega,
            observacion="",
            firma_base64="",
            estado="COMPLETADA",
        )

        turno = EntregaEPP.calcular_turno(fecha_hora)
        EntregaEPP.objects.filter(pk=entrega.pk).update(fecha_entrega=fecha_hora, turno=turno)

        for inventario, cantidad, unidad_activo in items_disponibles:
            stock_anterior = inventario.stock_actual
            inventario.stock_actual = stock_anterior - cantidad
            inventario.save(update_fields=["stock_actual"])

            fecha_vencimiento = None
            if inventario.vida_util_dias:
                fecha_vencimiento = fecha_hora.date() + timedelta(days=inventario.vida_util_dias)

            DetalleEntregaEPP.objects.create(
                entrega=entrega,
                inventario=inventario,
                cantidad=cantidad,
                talla=inventario.talla or "",
                precio_unitario=inventario.precio_unitario,
                fecha_vencimiento_vida_util=fecha_vencimiento,
                unidad_activo=unidad_activo,
            )

            if unidad_activo:
                unidad_activo.estado = "ENTREGADA"
                unidad_activo.save(update_fields=["estado"])

            movimiento = MovimientoInventario.objects.create(
                usuario=usuario,
                bodega=bodega,
                inventario=inventario,
                entrega=entrega,
                trabajador=trabajador,
                tipo_movimiento="SALIDA",
                cantidad=cantidad,
                stock_anterior=stock_anterior,
                stock_actual=inventario.stock_actual,
                observacion=f"Entrega pañol #{entrega.id}",
            )
            MovimientoInventario.objects.filter(pk=movimiento.pk).update(fecha=fecha_hora)

        return entrega

    def _crear_historial(self, usuarios, bodegas, trabajadores, productos):
        self.stdout.write("Generando 12 meses de historial (puede tardar unos minutos)...")

        bodeguer_usuarios = usuarios["Bodeguero"] + usuarios["Encargado de Bodega"]
        trabajadores_activos = [t for t in trabajadores if t.activo]
        if not trabajadores_activos:
            return

        anomalos = self._elegir_anomalos_por_cargo(trabajadores_activos)

        productos_central = [p for p in productos["lista"] if p["bodega_clave"] == "central"]
        alta_rotacion = [p for p in productos_central if p["alta_rotacion"] and not p["es_devolutivo"]]
        renovacion = [p for p in productos_central if p["renovacion"]]
        radios = [p for p in productos_central if p["nombre_base"] == "Radio análoga portátil"]
        catalogo_general = [p for p in productos_central if not p["es_devolutivo"]]

        unidades_radio_disponibles = list(productos["unidades_radio"])
        renovacion_reciente = {}  # (trabajador_id, nombre_producto) -> fecha última entrega

        hoy = timezone.localdate()
        inicio = hoy - timedelta(days=DIAS_HISTORIAL)
        fecha = inicio

        traspasos_generados = 0

        while fecha <= hoy:
            es_finde = fecha.weekday() == 6  # domingo: actividad mínima
            num_entregas_dia = random.randint(4, 10) if es_finde else random.randint(18, 38)

            for _ in range(num_entregas_dia):
                trabajador = random.choice(trabajadores_activos)

                # Los trabajadores desvinculados después de esta fecha no
                # pueden recibir entregas "futuras" respecto de su egreso.
                if trabajador.fecha_ingreso and trabajador.fecha_ingreso > fecha:
                    continue

                es_anomalo = trabajador.id in anomalos
                hora = self._hora_para_turno(trabajador.turno or "dia")
                fecha_hora = timezone.make_aware(
                    timezone.datetime.combine(fecha, timezone.datetime.min.time().replace(hour=hora))
                )

                items = []

                # Consumibles de alta rotación: a diario, más si es un caso
                # anómalo (retira muy por sobre el promedio de su cargo).
                num_consumibles = random.randint(1, 3)
                if es_anomalo:
                    num_consumibles *= random.randint(3, 4)

                for producto in random.sample(alta_rotacion, min(num_consumibles, len(alta_rotacion))):
                    cantidad = Decimal(random.randint(1, 2))
                    items.append((producto["inventario"], cantidad, None))

                # Estacionalidad: bloqueador/repelente en meses de verano.
                if fecha.month in MESES_VERANO and random.random() < 0.25:
                    estacionales = [
                        p for p in catalogo_general
                        if p["nombre_base"] in ("Bloqueador solar", "Repelente de insectos")
                    ]
                    if estacionales:
                        producto = random.choice(estacionales)
                        items.append((producto["inventario"], Decimal("1"), None))

                # EPP de renovación: cada varios meses por trabajador, no a diario.
                if renovacion and random.random() < 0.03:
                    producto = random.choice(renovacion)
                    clave = (trabajador.id, producto["nombre_base"])
                    ultima = renovacion_reciente.get(clave)
                    if not ultima or (fecha - ultima).days > 90:
                        items.append((producto["inventario"], Decimal("1"), None))
                        renovacion_reciente[clave] = fecha

                # Radios: se entregan al inicio de turno y deberían volver al
                # final. Se deja un % sin devolver a propósito.
                if radios and unidades_radio_disponibles and random.random() < 0.06:
                    unidad = unidades_radio_disponibles.pop()
                    producto = radios[0]
                    items.append((producto["inventario"], Decimal("1"), unidad))

                if not items:
                    continue

                usuario_atiende = random.choice(bodeguer_usuarios)
                entrega = self._crear_entrega(fecha_hora, trabajador, bodegas["central"], usuario_atiende, items)

                if entrega is None:
                    continue  # sin stock disponible ese día para ningún ítem elegido

                # Radios devueltos al final del mismo turno (~85% de las
                # veces); el resto queda pendiente para el reporte de
                # préstamos pendientes. Replica lo que hace
                # EntregaService.registrar_devolucion: sube el stock de
                # vuelta y deja un MovimientoInventario DEVOLUCION.
                for detalle in entrega.detalles.select_related("inventario").filter(unidad_activo__isnull=False):
                    if random.random() >= 0.85:
                        continue

                    fin_turno = fecha_hora + timedelta(hours=random.randint(8, 12))
                    estado_devolucion = "OPERATIVA" if random.random() < 0.95 else "DAÑADA"

                    detalle.devuelto = True
                    detalle.fecha_devolucion = fin_turno
                    detalle.estado_devolucion = estado_devolucion
                    detalle.save(update_fields=["devuelto", "fecha_devolucion", "estado_devolucion"])

                    detalle.unidad_activo.estado = "EN_MANTENCION" if estado_devolucion == "DAÑADA" else "DISPONIBLE"
                    detalle.unidad_activo.save(update_fields=["estado"])
                    if detalle.unidad_activo.estado == "DISPONIBLE":
                        unidades_radio_disponibles.append(detalle.unidad_activo)

                    producto_radio = detalle.inventario
                    stock_anterior = producto_radio.stock_actual
                    producto_radio.stock_actual = stock_anterior + detalle.cantidad
                    producto_radio.save(update_fields=["stock_actual"])
                    for p in radios:
                        if p["inventario"].pk == producto_radio.pk:
                            p["inventario"].stock_actual = producto_radio.stock_actual

                    mov_devolucion = MovimientoInventario.objects.create(
                        usuario=usuario_atiende,
                        bodega=bodegas["central"],
                        inventario=producto_radio,
                        entrega=entrega,
                        trabajador=trabajador,
                        tipo_movimiento="DEVOLUCION",
                        cantidad=detalle.cantidad,
                        stock_anterior=stock_anterior,
                        stock_actual=producto_radio.stock_actual,
                        observacion=f"Devolución activo diario ({estado_devolucion}) - Entrega #{entrega.id}",
                    )
                    MovimientoInventario.objects.filter(pk=mov_devolucion.pk).update(fecha=fin_turno)

            # Traspaso ocasional Reserva -> Central (~2 veces por mes).
            if fecha.day in (5, 20) and productos["lista"]:
                self._generar_traspaso(fecha, bodegas, usuarios, productos)
                traspasos_generados += 1

            # Reposición semanal: simula las compras normales del pañol.
            # Sin esto, los consumibles de alta rotación se agotan a los
            # pocos meses y el resto del año queda sin historial real.
            if fecha.weekday() == 0:
                self._reponer_stock_bajo(fecha, bodeguer_usuarios, productos_central)

            fecha += timedelta(days=1)

        self.stdout.write(f"  Traspasos generados: {traspasos_generados}")

    def _reponer_stock_bajo(self, fecha, usuarios_bodega, productos_central):
        """Simula la compra/reposición normal del pañol: todo producto de
        Central bajo su stock mínimo se repone a su stock máximo, vía un
        INGRESO real (no un traspaso). Sin esto, los consumibles de alta
        rotación se agotan a los pocos meses de simulación y el resto del
        historial anual queda vacío, lo que no refleja cómo opera un pañol
        real (siempre se resurte antes de quedar en cero)."""
        usuario = random.choice(usuarios_bodega)
        fecha_hora = timezone.make_aware(
            timezone.datetime.combine(fecha, timezone.datetime.min.time().replace(hour=9))
        )

        for p in productos_central:
            inventario = Inventario.objects.get(pk=p["inventario"].pk)
            if inventario.stock_actual >= inventario.stock_minimo:
                continue

            stock_anterior = inventario.stock_actual
            cantidad = inventario.stock_maximo - stock_anterior
            if cantidad <= 0:
                continue

            inventario.stock_actual = inventario.stock_maximo
            inventario.save(update_fields=["stock_actual"])
            p["inventario"].stock_actual = inventario.stock_actual  # mantiene el caché en memoria al día

            movimiento = MovimientoInventario.objects.create(
                usuario=usuario,
                bodega=inventario.bodega,
                inventario=inventario,
                tipo_movimiento="INGRESO",
                cantidad=cantidad,
                stock_anterior=stock_anterior,
                stock_actual=inventario.stock_actual,
                observacion="Reposición de stock (compra a proveedor).",
            )
            MovimientoInventario.objects.filter(pk=movimiento.pk).update(fecha=fecha_hora)

    def _generar_traspaso(self, fecha, bodegas, usuarios, productos):
        pares_por_nombre = {}
        for p in productos["lista"]:
            pares_por_nombre.setdefault(p["nombre_base"], {})[p["bodega_clave"]] = p["inventario"]

        candidatos = [
            par for par in pares_por_nombre.values()
            if "reserva" in par and "central" in par and par["reserva"].stock_actual > 5
        ]
        if not candidatos:
            return

        par = random.choice(candidatos)
        # OJO: origen/destino se recargan frescos desde la BD (no son el
        # mismo objeto Python que par["reserva"]/par["central"]), así que
        # hay que sincronizar el caché en memoria compartido al final o las
        # entregas futuras del bucle principal verían un stock desactualizado.
        origen = Inventario.objects.get(pk=par["reserva"].pk)
        destino = Inventario.objects.get(pk=par["central"].pk)
        cantidad = Decimal(min(int(origen.stock_actual) // 2, random.randint(5, 20)) or 1)

        if origen.stock_actual < cantidad:
            return

        stock_anterior_origen = origen.stock_actual
        stock_anterior_destino = destino.stock_actual
        origen.stock_actual -= cantidad
        destino.stock_actual += cantidad
        origen.save(update_fields=["stock_actual"])
        destino.save(update_fields=["stock_actual"])

        par["reserva"].stock_actual = origen.stock_actual
        par["central"].stock_actual = destino.stock_actual

        usuario = random.choice(usuarios["Encargado de Bodega"])
        fecha_hora = timezone.make_aware(timezone.datetime.combine(fecha, timezone.datetime.min.time().replace(hour=10)))

        movimiento = MovimientoInventario.objects.create(
            usuario=usuario,
            bodega=bodegas["reserva"],
            inventario=origen,
            tipo_movimiento="TRASPASO",
            cantidad=cantidad,
            stock_anterior=stock_anterior_origen,
            stock_actual=origen.stock_actual,
            bodega_destino=bodegas["central"],
            inventario_destino=destino,
            stock_anterior_destino=stock_anterior_destino,
            stock_actual_destino=destino.stock_actual,
            observacion=f"Traspaso {bodegas['reserva'].nombre} -> {bodegas['central'].nombre}",
        )
        MovimientoInventario.objects.filter(pk=movimiento.pk).update(fecha=fecha_hora)

    # =================================================================
    # 6. AUDITORÍAS (al menos 4: 2 por bodega, con diferencias reales)
    # =================================================================
    def _crear_auditorias(self, usuarios, bodegas, productos):
        encargado = usuarios["Encargado de Bodega"][0]

        for clave_bodega, bodega in bodegas.items():
            productos_bodega = [
                p["inventario"] for p in productos["lista"] if p["bodega_clave"] == clave_bodega
            ]
            if len(productos_bodega) < 5:
                continue

            # Auditoría 1: cerrada y ajustada, con diferencias reales.
            auditoria = AuditoriaInventarioService.crear_auditoria(
                bodega_id=bodega.id, usuario=encargado,
                observacion="Conteo cíclico mensual.",
            )

            muestra = random.sample(productos_bodega, min(10, len(productos_bodega)))
            for producto in muestra:
                sistema = producto.stock_actual
                # La mayoría cuadra; algunos tienen faltante real (nunca
                # sobrante artificial: son las diferencias que sustentan el
                # argumento de pérdida de insumos ante la mandante).
                if random.random() < 0.35:
                    diferencia = -Decimal(random.randint(1, max(1, int(sistema) // 5) or 1))
                else:
                    diferencia = Decimal("0")

                fisico = max(Decimal("0"), sistema + diferencia)
                motivo = "" if diferencia == 0 else random.choice([
                    "Posible extravío durante el turno.",
                    "Diferencia detectada en el conteo físico, sin explicación registrada.",
                    "Producto dañado y descartado sin registrar movimiento.",
                ])

                AuditoriaInventarioService.registrar_conteo(
                    auditoria_id=auditoria.id, inventario_id=producto.id,
                    stock_fisico=fisico, observacion=motivo,
                )

            AuditoriaInventarioService.cerrar_auditoria(auditoria.id)
            try:
                AuditoriaInventarioService.ajustar_stock(
                    auditoria_id=auditoria.id, usuario=encargado,
                    firma_autorizacion="firma_digital_seed_base64",
                )
            except ValidationError:
                pass  # si no había descuadre crítico, ajustar_stock igual corre sin firma

            # Auditoría 2: abierta (conteo cíclico en curso), para que no
            # todas las auditorías del historial estén ya cerradas.
            AuditoriaInventarioService.crear_auditoria(
                bodega_id=bodega.id, usuario=encargado,
                observacion="Conteo cíclico en curso.",
            )
