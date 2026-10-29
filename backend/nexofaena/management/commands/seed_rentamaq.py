"""
Seed realista del pañol de RentaMaq (faena), a partir de fotografías del
pañol y conversación directa con el stakeholder (Carlos Guerrero, RentaMaq).

Deja la base como se vería una faena real en operación, sin inflarla:
- 2 bodegas: Central (atiende al trabajador) y Reserva (respaldo).
- El catálogo real del pañol, con tallas y las radios Motorola como
  unidades individuales que se prestan y se devuelven.
- ~40 trabajadores con cargos y turnos realistas.
- 4 meses de entregas hasta HOY (kiosco y bodeguero), reposiciones,
  traspasos, devoluciones de radios y 2 auditorías por bodega.

Con eso los modelos del Panel Gerencial tienen datos reales que analizar:
unos pocos productos por agotarse (un pedido que no ha llegado), un par de
trabajadores con consumo fuera de lo normal, radios sin devolver recientes
y productos de baja rotación con más stock del necesario.

El historial se simula en memoria y se inserta en bloque (bulk_create): la
base de producción está en Neon (Oregon), y crear fila por fila desde Chile
tomaba horas.

IMPORTANTE — antes de correr con --reset:
    1. Respalda la base actual:
       pg_dump -U <usuario> -d <basedatos> -F c -f respaldo_antes_rentamaq.dump
    2. Recién entonces vuelve a correr con --reset --confirmo-respaldo.

--reset borra los datos operativos (trabajadores, inventario, entregas,
movimientos, auditorías y alertas) y deja solo las 2 bodegas del pañol.
Nunca borra usuarios ni roles: las cuentas con las que se inicia sesión
siguen funcionando.

Las cifras marcadas [ESTIMADO] vienen de fotos y no son datos oficiales.
"""

import heapq
import random
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from itertools import count

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.test.utils import override_settings
from django.utils import timezone
from faker import Faker

from nexofaena.models.alerta import Alerta
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
from nexofaena.services.dashboard_service import DashboardService

fake = Faker("es_CL")

MIN_TRABAJADORES = 20
MAX_TRABAJADORES = 200
TRABAJADORES_POR_DEFECTO = 40

# 4 meses: cubre las 12 semanas que miran los modelos de consumo y los 90
# días de la clasificación ABC, sin acumular un año de datos que nadie mira.
DIAS_HISTORIAL = 120

# Entregas por día en Central (40 trabajadores, no todos retiran a diario).
ENTREGAS_DIA_HABIL = (10, 18)
ENTREGAS_DOMINGO = (2, 5)

# Radios observadas en fotografías del rack de carga + estante secundario.
# [ESTIMADO] — confirmar con bodega antes de tomarlo como cifra oficial.
CANTIDAD_RADIOS = 30
PROBABILIDAD_RETIRA_RADIO = 0.25  # varias radios al día, como en el rack real

# Meses de verano austral: más bloqueador solar / repelente sale del pañol.
MESES_VERANO = {12, 1, 2}

# Productos cuyo pedido al proveedor "no ha llegado": no se reponen en los
# últimos días del historial, así que hoy aparecen por agotarse (es lo que
# el Panel Gerencial debe detectar y recomendar comprar).
PEDIDO_PENDIENTE = ("Guantes de nitrilo", "Mascarilla KN95", "Lentes de seguridad claros")
DIAS_SIN_REPOSICION = 16

# Cuánto más retira, por entrega, un trabajador con consumo inusual.
FACTOR_CONSUMO_INUSUAL = 4

SEMILLA = 2024  # mismos datos en cada corrida (reproducible)


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
    help = (
        "Siembra datos realistas de RentaMaq: 2 bodegas, catálogo real del pañol con radios, "
        "~40 trabajadores, 4 meses de historial hasta hoy y auditorías."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset", action="store_true",
            help=(
                "Borra los datos operativos existentes (trabajadores, inventario, entregas, movimientos, "
                "auditorías, alertas y bodegas extra) antes de sembrar. NO borra usuarios ni roles."
            ),
        )
        parser.add_argument(
            "--confirmo-respaldo", action="store_true",
            help="Confirma que ya respaldaste la base (pg_dump) antes de --reset. Obligatorio junto a --reset.",
        )
        parser.add_argument(
            "--trabajadores", type=int, default=TRABAJADORES_POR_DEFECTO,
            help=f"Cantidad de trabajadores ({MIN_TRABAJADORES}-{MAX_TRABAJADORES}). Default: {TRABAJADORES_POR_DEFECTO}.",
        )

    def handle(self, *args, **options):
        reset = options["reset"]
        num_trabajadores = options["trabajadores"]

        if reset and not options["confirmo_respaldo"]:
            raise CommandError(
                "Falta --confirmo-respaldo. Antes de --reset debes respaldar la base:\n"
                "    pg_dump -U <usuario> -d <basedatos> -F c -f respaldo_antes_rentamaq.dump\n"
                "Vuelve a correr el comando agregando --confirmo-respaldo una vez respaldada."
            )

        if not (MIN_TRABAJADORES <= num_trabajadores <= MAX_TRABAJADORES):
            raise CommandError(f"--trabajadores debe estar entre {MIN_TRABAJADORES} y {MAX_TRABAJADORES}.")

        # Idempotencia: el comando se niega a duplicar. Si ya hay datos
        # sembrados, exige --reset explícito para repoblar.
        ya_sembrado = Bodega.objects.filter(codigo="BOD-CEN").exists() and Trabajador.objects.exists()
        if ya_sembrado and not reset:
            self.stdout.write(self.style.WARNING(
                "Ya existen datos de RentaMaq sembrados (Bodega Central + trabajadores). "
                "No se duplica nada. Usa --reset --confirmo-respaldo para repoblar desde cero."
            ))
            return

        random.seed(SEMILLA)
        Faker.seed(SEMILLA)

        # Las diferencias de las auditorías generan alertas que normalmente
        # se envían al grupo de Telegram: al sembrar no tiene sentido avisar.
        with override_settings(TELEGRAM_NOTIFICACIONES_ACTIVAS=False), transaction.atomic():
            if reset:
                self._reset()

            bodegas = self._crear_bodegas()
            roles = self._crear_roles()
            usuarios = self._crear_usuarios(roles)
            trabajadores = self._crear_trabajadores(num_trabajadores)
            productos = self._crear_catalogo(bodegas)
            self._crear_historial(usuarios, bodegas, trabajadores, productos)
            self._crear_auditorias(usuarios, bodegas, productos)

        DashboardService.invalidar_cache()

        self.stdout.write(self.style.SUCCESS("Seed RentaMaq completado correctamente."))
        self.stdout.write(self.style.SUCCESS(f"Bodegas: {Bodega.objects.count()}"))
        self.stdout.write(self.style.SUCCESS(f"Trabajadores: {Trabajador.objects.count()}"))
        self.stdout.write(self.style.SUCCESS(f"Productos (con tallas y bodega): {Inventario.objects.count()}"))
        self.stdout.write(self.style.SUCCESS(f"Radios: {UnidadActivo.objects.count()}"))
        self.stdout.write(self.style.SUCCESS(f"Entregas EPP: {EntregaEPP.objects.count()}"))
        self.stdout.write(self.style.SUCCESS(f"Movimientos: {MovimientoInventario.objects.count()}"))
        self.stdout.write(self.style.SUCCESS(f"Auditorías: {AuditoriaInventario.objects.count()}"))

    # =================================================================
    # RESET — datos operativos. Nunca borra Usuario ni Rol (evita
    # invalidar cuentas en uso).
    # =================================================================
    def _reset(self):
        self.stdout.write(self.style.WARNING("Borrando datos operativos existentes..."))

        Alerta.objects.all().delete()
        DetalleAuditoriaInventario.objects.all().delete()
        AuditoriaInventario.objects.all().delete()
        MovimientoInventario.objects.all().delete()
        DetalleEntregaEPP.objects.all().delete()
        EntregaEPP.objects.all().delete()
        UnidadActivo.objects.all().delete()
        Inventario.objects.all().delete()
        Trabajador.objects.all().delete()
        Bodega.objects.exclude(codigo__in=["BOD-CEN", "BOD-RES"]).delete()
        # Responsable inactivo que creaba el antiguo comando generar_demo_dashboard.
        Usuario.objects.filter(username="demo.bodeguero").delete()

    # =================================================================
    # 1. BODEGAS (solo 2)
    # =================================================================
    def _crear_bodegas(self):
        # `nombre` es único desde antes de que existiera `codigo`: si ya hay
        # una "Bodega Central" del seed genérico, se reutiliza esa fila.
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
    # 2. ROLES Y PERSONAL DE BODEGA
    # =================================================================
    def _crear_roles(self):
        nombres = ["Administrador", "Supervisor", "Bodeguero", "Encargado de Bodega"]
        return {nombre: Rol.objects.get_or_create(nombre=nombre)[0] for nombre in nombres}

    def _crear_usuarios(self, roles):
        """
        Personal de bodega que figura como responsable de las entregas del
        historial. Se crea INACTIVO y sin contraseña usable: la app está
        publicada en internet, y antes estas cuentas nacían con una
        contraseña conocida (una de ellas como superusuario). Si alguna ya
        existía, no se toca, para no cortarle el acceso a nadie.
        """
        contador_rut = ContadorRut(15000000)
        existentes = set(Usuario.objects.values_list("rut", flat=True))

        definiciones = (
            [("bodeguero", i, "Bodeguero") for i in range(1, 4)]
            + [("encargado", i, "Encargado de Bodega") for i in range(1, 3)]
        )

        usuarios = {"Bodeguero": [], "Encargado de Bodega": []}
        for prefijo, indice, nombre_rol in definiciones:
            username = f"{prefijo}{indice}"
            rut = contador_rut.nuevo()
            while rut in existentes:
                rut = contador_rut.nuevo()

            usuario = Usuario.objects.filter(username=username).first()
            if usuario is None:
                usuario = Usuario(
                    username=username,
                    rut=rut,
                    first_name=fake.first_name(),
                    last_name=fake.last_name(),
                    email=f"{username}@rentamaq.cl",
                    rol=roles[nombre_rol],
                    is_active=False,
                )
                usuario.set_unusable_password()
                usuario.save()

            usuarios[nombre_rol].append(usuario)

        return usuarios

    # =================================================================
    # 3. TRABAJADORES
    # =================================================================
    def _crear_trabajadores(self, cantidad):
        contador_rut = ContadorRut(18000000)
        cargos = [c for c, _ in CARGOS_PESOS]
        pesos = [p for _, p in CARGOS_PESOS]
        hoy = date.today()

        trabajadores = []
        for _ in range(cantidad):
            # ~8% desvinculados: el sistema debe manejar el historial de
            # gente que ya no está en la faena.
            trabajadores.append(Trabajador(
                rut=contador_rut.nuevo(),
                nombres=fake.first_name(),
                apellido_paterno=fake.last_name(),
                apellido_materno=fake.last_name(),
                cargo=random.choices(cargos, weights=pesos, k=1)[0],
                turno=random.choices(["dia", "noche"], weights=[55, 45], k=1)[0],
                telefono=f"+569{random.randint(10000000, 99999999)}",
                activo=random.random() > 0.08,
                fecha_ingreso=hoy - timedelta(days=random.randint(15, 365 * 4)),
            ))

        return Trabajador.objects.bulk_create(trabajadores)

    # =================================================================
    # 4. CATÁLOGO — una ficha por producto; la talla se anota en cada
    #    entrega (como en el pañol real), no es un producto aparte. Antes
    #    eran 18 "Zapato de seguridad" (9 tallas x 2 bodegas).
    # =================================================================
    def _crear_catalogo(self, bodegas):
        # RM-0001, RM-0002...: nunca colisiona y es fácil de verificar.
        codigos_existentes = set(Inventario.objects.values_list("codigo", flat=True))
        numero = count(1)

        def siguiente_codigo():
            while True:
                codigo = f"RM-{next(numero):04d}"
                if codigo not in codigos_existentes:
                    codigos_existentes.add(codigo)
                    return codigo

        productos = []
        objetos = []
        for (nombre, categoria, marca, modelo, unidad, precio, es_devolutivo,
             tallas, _unidades_por_pack, es_critico) in CATALOGO:
            alta_rotacion = nombre in NOMBRES_ALTA_ROTACION
            renovacion = nombre in NOMBRES_RENOVACION

            # La Reserva solo guarda respaldo de lo que más rota; herramientas,
            # oficina, izaje y radios viven solo en Central.
            bodegas_del_producto = (
                bodegas.items() if (alta_rotacion or renovacion) else [("central", bodegas["central"])]
            )

            for clave_bodega, bodega in bodegas_del_producto:
                # Alta rotación -> más stock en Central, poco respaldo en
                # Reserva. Baja rotación / respaldo -> al revés.
                if alta_rotacion:
                    minimo, maximo = (20, 200) if clave_bodega == "central" else (10, 60)
                elif renovacion:
                    minimo, maximo = (8, 40) if clave_bodega == "central" else (15, 80)
                else:
                    minimo, maximo = (5, 30) if clave_bodega == "central" else (10, 60)

                if nombre in PEDIDO_PENDIENTE and clave_bodega == "central":
                    # Se piden de a poco (máximo bajo): sin la reposición
                    # que no ha llegado, se agotan en días.
                    maximo = 45

                inventario = Inventario(
                    bodega=bodega,
                    codigo=siguiente_codigo(),
                    nombre=nombre,
                    descripcion=f"{nombre} — {categoria}, uso operacional en faena.",
                    marca=marca,
                    modelo=modelo,
                    talla=None,
                    unidad_medida=unidad,
                    stock_actual=random.randint((minimo + maximo) // 2, maximo),
                    stock_minimo=minimo,
                    stock_maximo=maximo,
                    precio_unitario=Decimal(str(precio)),
                    ubicacion=f"Rack {categoria[:3].upper()}-{random.randint(1, 9)}",
                    estado=True,
                    es_devolutivo=es_devolutivo,
                    es_activo_critico=es_critico,
                    tiempo_reposicion_dias=14 if clave_bodega == "reserva" else 7,
                )
                objetos.append(inventario)
                productos.append({
                    "inventario": inventario,
                    "nombre_base": nombre,
                    "bodega_clave": clave_bodega,
                    "alta_rotacion": alta_rotacion,
                    "renovacion": renovacion,
                    "es_devolutivo": es_devolutivo,
                    "tallas": tallas,
                })

        Inventario.objects.bulk_create(objetos, batch_size=200)

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

        unidades_radio = UnidadActivo.objects.bulk_create([
            UnidadActivo(inventario=radio_central, codigo=f"RADIO-{i:03d}")
            for i in range(1, CANTIDAD_RADIOS + 1)
        ])

        return {"lista": productos, "unidades_radio": unidades_radio}

    # =================================================================
    # 5. HISTORIAL (simulado en memoria, insertado en bloque)
    # =================================================================
    def _elegir_inusuales(self, trabajadores):
        """Un trabajador con consumo inusual en cada uno de los 2 cargos más
        numerosos: son los grupos donde el K-Means (que compara solo dentro
        del mismo cargo) tiene pares suficientes para detectarlo."""
        por_cargo = {}
        for t in trabajadores:
            por_cargo.setdefault(t.cargo, []).append(t)

        grupos = sorted(por_cargo.values(), key=len, reverse=True)[:2]
        return {random.choice(grupo).id for grupo in grupos if len(grupo) >= 6}

    @staticmethod
    def _momento(dia, hora, minuto=0):
        return timezone.make_aware(datetime.combine(dia, time(hour=hora, minute=minuto)))

    def _hora_para_turno(self, turno):
        if turno == "noche":
            return random.choice(list(range(20, 24)) + list(range(0, 7)))
        return random.randint(8, 18)

    def _crear_historial(self, usuarios, bodegas, trabajadores, productos):
        self.stdout.write(f"Simulando {DIAS_HISTORIAL} días de operación del pañol...")

        bodegueros = usuarios["Bodeguero"] + usuarios["Encargado de Bodega"]
        encargados = usuarios["Encargado de Bodega"]
        activos = [t for t in trabajadores if t.activo]
        inusuales = self._elegir_inusuales(activos)

        central = [p for p in productos["lista"] if p["bodega_clave"] == "central"]
        alta_rotacion = [p["inventario"] for p in central if p["alta_rotacion"] and not p["es_devolutivo"]]
        renovacion = [p for p in central if p["renovacion"]]
        estacionales = [p["inventario"] for p in central if p["nombre_base"] in ("Bloqueador solar", "Repelente de insectos")]
        baja_rotacion = [
            p["inventario"] for p in central
            if not (p["alta_rotacion"] or p["renovacion"] or p["es_devolutivo"]) and p["inventario"] not in estacionales
        ]
        radio = next(p["inventario"] for p in central if p["nombre_base"] == "Radio análoga portátil")
        reponibles = [p["inventario"] for p in productos["lista"] if not p["es_devolutivo"]]
        pares_traspaso = self._pares_traspaso(productos["lista"])

        ahora = timezone.localtime()
        hoy = ahora.date()
        inicio = hoy - timedelta(days=DIAS_HISTORIAL)
        inicio_sin_reposicion = hoy - timedelta(days=DIAS_SIN_REPOSICION)

        stock = {p["inventario"].id: Decimal(p["inventario"].stock_actual) for p in productos["lista"]}
        tallas = {p["inventario"].id: p["tallas"] for p in productos["lista"] if p["tallas"]}
        radios_disponibles = list(productos["unidades_radio"])
        ultima_renovacion = {}

        entregas, detalles, movimientos = [], [], []
        eventos = []
        secuencia = count()

        def programar(momento, tipo, datos=None):
            heapq.heappush(eventos, (momento, next(secuencia), tipo, datos))

        def mover(inventario, tipo, cantidad, momento, usuario, detalle_texto, trabajador=None, entrega=None):
            antes = stock[inventario.id]
            despues = antes - cantidad if tipo == "SALIDA" else antes + cantidad
            stock[inventario.id] = despues
            movimiento = MovimientoInventario(
                usuario=usuario, bodega=inventario.bodega, inventario=inventario,
                trabajador=trabajador, entrega=entrega, tipo_movimiento=tipo,
                cantidad=cantidad, stock_anterior=antes, stock_actual=despues,
                observacion=detalle_texto,
            )
            movimiento._fecha = momento
            movimientos.append(movimiento)

        def registrar_entrega(trabajador, momento):
            inusual = trabajador.id in inusuales
            pedidos = []

            # Consumibles de alta rotación (más cantidad y variedad si el
            # trabajador tiene consumo inusual).
            for inventario in random.sample(alta_rotacion, random.randint(3, 4) if inusual else random.randint(1, 2)):
                pedidos.append((inventario, Decimal(random.randint(1, 2) * (2 if inusual else 1)), None))

            if momento.month in MESES_VERANO and estacionales and random.random() < 0.25:
                pedidos.append((random.choice(estacionales), Decimal("1"), None))

            # Herramientas, izaje, oficina: salen de vez en cuando.
            if baja_rotacion and random.random() < 0.12:
                pedidos.append((random.choice(baja_rotacion), Decimal("1"), None))

            # EPP de renovación: cada varios meses por trabajador, no a diario.
            if renovacion and random.random() < 0.03:
                elegido = random.choice(renovacion)
                clave = (trabajador.id, elegido["nombre_base"])
                ultima = ultima_renovacion.get(clave)
                if not ultima or (momento.date() - ultima).days > 90:
                    pedidos.append((elegido["inventario"], Decimal("1"), None))
                    ultima_renovacion[clave] = momento.date()

            # Radio: se presta al inicio del turno y debería volver al final.
            if radios_disponibles and random.random() < PROBABILIDAD_RETIRA_RADIO:
                pedidos.append((radio, Decimal("1"), radios_disponibles.pop()))

            # Sin stock no hay entrega de ese ítem (quiebre real).
            pedidos = [(inv, cant, unidad) for inv, cant, unidad in pedidos if stock[inv.id] >= cant]
            if not pedidos:
                return

            usuario = random.choice(bodegueros)
            canal = "KIOSCO" if random.random() < 0.6 else "BODEGA"
            entrega = EntregaEPP(
                trabajador=trabajador, usuario=usuario, bodega=bodegas["central"],
                observacion="", firma_base64="", estado="COMPLETADA", canal=canal,
                turno=EntregaEPP.calcular_turno(momento),
            )
            entrega._fecha = momento
            entregas.append(entrega)

            for inventario, cantidad, unidad in pedidos:
                vencimiento = None
                if inventario.vida_util_dias:
                    vencimiento = momento.date() + timedelta(days=inventario.vida_util_dias)

                detalle = DetalleEntregaEPP(
                    entrega=entrega, inventario=inventario, cantidad=cantidad,
                    talla=random.choice(tallas[inventario.id]) if inventario.id in tallas else "",
                    precio_unitario=inventario.precio_unitario,
                    fecha_vencimiento_vida_util=vencimiento, unidad_activo=unidad,
                )
                detalles.append(detalle)
                mover(
                    inventario, "SALIDA", cantidad, momento, usuario,
                    f"Entrega de EPP ({'kiosco' if canal == 'KIOSCO' else 'bodeguero'})",
                    trabajador=trabajador, entrega=entrega,
                )

                if unidad:
                    unidad.estado = "ENTREGADA"
                    sorteo = random.random()
                    if sorteo < 0.80:
                        devolucion = momento + timedelta(hours=random.randint(8, 12))
                    elif sorteo < 0.90 or momento.date() < hoy - timedelta(days=10):
                        # Devuelta con atraso (las antiguas siempre terminan volviendo).
                        devolucion = momento + timedelta(days=random.randint(1, 5), hours=random.randint(0, 8))
                    else:
                        devolucion = None  # sigue pendiente: aparece en "Equipos sin devolver"
                    if devolucion:
                        programar(devolucion, "devolucion", (detalle, unidad, usuario, trabajador, entrega))

        def registrar_devolucion(datos, momento):
            detalle, unidad, usuario, trabajador, entrega = datos
            estado = "OPERATIVA" if random.random() < 0.95 else "DAÑADA"
            detalle.devuelto = True
            detalle.fecha_devolucion = momento
            detalle.estado_devolucion = estado
            mover(radio, "DEVOLUCION", detalle.cantidad, momento, usuario,
                  f"Devolución de {unidad.codigo} ({estado})", trabajador=trabajador, entrega=entrega)
            if estado == "DAÑADA":
                unidad.estado = "EN_MANTENCION"
                programar(momento + timedelta(days=7), "fin_mantencion", unidad)
            else:
                unidad.estado = "DISPONIBLE"
                radios_disponibles.append(unidad)

        def reponer(momento):
            usuario = random.choice(bodegueros)
            for inventario in reponibles:
                if stock[inventario.id] >= inventario.stock_minimo:
                    continue
                if inventario.nombre in PEDIDO_PENDIENTE and momento.date() >= inicio_sin_reposicion:
                    continue  # el pedido al proveedor todavía no llega
                cantidad = Decimal(inventario.stock_maximo) - stock[inventario.id]
                if cantidad > 0:
                    mover(inventario, "INGRESO", cantidad, momento, usuario, "Reposición de stock (compra a proveedor)")

        def traspasar(momento):
            candidatos = [(o, d) for o, d in pares_traspaso if stock[o.id] > 5]
            if not candidatos:
                return
            origen, destino = random.choice(candidatos)
            cantidad = Decimal(min(int(stock[origen.id]) // 2, random.randint(5, 20)) or 1)

            antes_origen, antes_destino = stock[origen.id], stock[destino.id]
            stock[origen.id] -= cantidad
            stock[destino.id] += cantidad
            movimiento = MovimientoInventario(
                usuario=random.choice(encargados), bodega=bodegas["reserva"], inventario=origen,
                tipo_movimiento="TRASPASO", cantidad=cantidad,
                stock_anterior=antes_origen, stock_actual=stock[origen.id],
                bodega_destino=bodegas["central"], inventario_destino=destino,
                stock_anterior_destino=antes_destino, stock_actual_destino=stock[destino.id],
                observacion=f"Traspaso {bodegas['reserva'].nombre} -> {bodegas['central'].nombre}",
            )
            movimiento._fecha = momento
            movimientos.append(movimiento)

        dia = inicio
        while dia <= hoy:
            if dia.weekday() == 0:
                programar(self._momento(dia, 9), "reposicion")
            if dia.day in (5, 20):
                programar(self._momento(dia, 10), "traspaso")

            rango = ENTREGAS_DOMINGO if dia.weekday() == 6 else ENTREGAS_DIA_HABIL
            for _ in range(random.randint(*rango)):
                trabajador = random.choice(activos)
                if trabajador.fecha_ingreso and trabajador.fecha_ingreso > dia:
                    continue
                momento = self._momento(dia, self._hora_para_turno(trabajador.turno), random.randint(0, 59))
                programar(momento, "entrega", trabajador)

            # Se procesa todo lo del día en orden cronológico; lo que cae
            # después de "ahora" no ocurrió todavía (ej. una radio que se
            # devuelve al final del turno de hoy sigue pendiente).
            fin_dia = self._momento(dia + timedelta(days=1), 0)
            while eventos and eventos[0][0] < fin_dia:
                momento, _, tipo, datos = heapq.heappop(eventos)
                if momento > ahora:
                    continue
                if tipo == "entrega":
                    registrar_entrega(datos, momento)
                elif tipo == "devolucion":
                    registrar_devolucion(datos, momento)
                elif tipo == "fin_mantencion":
                    datos.estado = "DISPONIBLE"
                    radios_disponibles.append(datos)
                elif tipo == "reposicion":
                    reponer(momento)
                elif tipo == "traspaso":
                    traspasar(momento)

            dia += timedelta(days=1)

        self._guardar_historial(entregas, detalles, movimientos, productos, stock)

    @staticmethod
    def _pares_traspaso(lista):
        por_clave = {}
        for p in lista:
            if p["es_devolutivo"]:
                continue
            inventario = p["inventario"]
            por_clave.setdefault((p["nombre_base"], inventario.talla), {})[p["bodega_clave"]] = inventario
        return [(par["reserva"], par["central"]) for par in por_clave.values() if "reserva" in par and "central" in par]

    def _guardar_historial(self, entregas, detalles, movimientos, productos, stock):
        """Inserta todo en bloque. fecha_entrega y fecha son auto_now_add
        (bulk_create las pisa con la hora actual), así que se restauran con
        bulk_update, que no pasa por pre_save."""
        EntregaEPP.objects.bulk_create(entregas, batch_size=500)
        for entrega in entregas:
            entrega.fecha_entrega = entrega._fecha
        EntregaEPP.objects.bulk_update(entregas, ["fecha_entrega"], batch_size=500)

        DetalleEntregaEPP.objects.bulk_create(detalles, batch_size=500)

        MovimientoInventario.objects.bulk_create(movimientos, batch_size=500)
        for movimiento in movimientos:
            movimiento.fecha = movimiento._fecha
        MovimientoInventario.objects.bulk_update(movimientos, ["fecha"], batch_size=500)

        UnidadActivo.objects.bulk_update(productos["unidades_radio"], ["estado"])

        inventarios = [p["inventario"] for p in productos["lista"]]
        for inventario in inventarios:
            inventario.stock_actual = stock[inventario.id]
        Inventario.objects.bulk_update(inventarios, ["stock_actual"], batch_size=200)

        self.stdout.write(f"  {len(entregas)} entregas, {len(movimientos)} movimientos.")

    # =================================================================
    # 6. AUDITORÍAS (2 por bodega: una cerrada con diferencias reales y
    #    otra en curso)
    # =================================================================
    def _crear_auditorias(self, usuarios, bodegas, productos):
        encargado = usuarios["Encargado de Bodega"][0]

        for clave_bodega, bodega in bodegas.items():
            productos_bodega = [
                p["inventario"] for p in productos["lista"]
                if p["bodega_clave"] == clave_bodega and not p["es_devolutivo"]
            ]
            if len(productos_bodega) < 5:
                continue

            auditoria = AuditoriaInventarioService.crear_auditoria(
                bodega_id=bodega.id, usuario=encargado,
                observacion="Conteo cíclico mensual.",
            )

            for producto in random.sample(productos_bodega, min(10, len(productos_bodega))):
                sistema = producto.stock_actual
                # La mayoría cuadra; algunos tienen faltante real (nunca
                # sobrante artificial: son las diferencias que sustentan el
                # argumento de pérdida de insumos ante la mandante).
                if random.random() < 0.35 and sistema > 0:
                    diferencia = -Decimal(random.randint(1, max(1, int(sistema) // 5)))
                else:
                    diferencia = Decimal("0")

                motivo = "" if diferencia == 0 else random.choice([
                    "Posible extravío durante el turno.",
                    "Diferencia detectada en el conteo físico, sin explicación registrada.",
                    "Producto dañado y descartado sin registrar movimiento.",
                ])

                AuditoriaInventarioService.registrar_conteo(
                    auditoria_id=auditoria.id, inventario_id=producto.id,
                    stock_fisico=max(Decimal("0"), sistema + diferencia), observacion=motivo,
                )

            AuditoriaInventarioService.cerrar_auditoria(auditoria.id)
            try:
                AuditoriaInventarioService.ajustar_stock(
                    auditoria_id=auditoria.id, usuario=encargado,
                    firma_autorizacion="firma_digital_seed_base64",
                )
            except ValidationError:
                pass  # sin descuadre crítico no hace falta ajustar

            AuditoriaInventarioService.crear_auditoria(
                bodega_id=bodega.id, usuario=encargado,
                observacion="Conteo cíclico en curso.",
            )
