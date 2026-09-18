"""
Helpers compartidos para armar datos mínimos de prueba (rol, usuario,
bodega, trabajador, inventario). Evita repetir el mismo boilerplate de
creación en cada archivo de test.
"""
from decimal import Decimal

from nexofaena.models.bodega import Bodega
from nexofaena.models.inventario import Inventario
from nexofaena.models.rol import Rol
from nexofaena.models.trabajador import Trabajador
from nexofaena.models.unidad_activo import UnidadActivo
from nexofaena.models.usuario import Usuario


def crear_rol(nombre="Bodeguero"):
    rol, _ = Rol.objects.get_or_create(nombre=nombre)
    return rol


_contador_rut = [10000000]


def _siguiente_rut():
    _contador_rut[0] += 1
    return f"{_contador_rut[0]}-9"


def crear_usuario(username="bodeguero_test", rol_nombre="Bodeguero", **extra):
    rol = crear_rol(rol_nombre)
    usuario = Usuario.objects.create_user(
        username=username,
        password="test-pass-123",
        rut=extra.pop("rut", _siguiente_rut()),
        rol=rol,
        **extra,
    )
    return usuario


def crear_bodega(nombre="Bodega Test"):
    return Bodega.objects.create(nombre=nombre)


def crear_trabajador(rut="11111111-1", nombres="Juan", apellido_paterno="Pérez", **extra):
    return Trabajador.objects.create(
        rut=rut,
        nombres=nombres,
        apellido_paterno=apellido_paterno,
        cargo=extra.pop("cargo", "Operador"),
        **extra,
    )


def crear_producto(bodega, nombre="Casco de seguridad", codigo=None, stock=Decimal("10"),
                    stock_minimo=Decimal("2"), es_devolutivo=False, **extra):
    return Inventario.objects.create(
        bodega=bodega,
        nombre=nombre,
        codigo=codigo or f"SKU-{nombre[:6].upper()}-{bodega.id}",
        stock_actual=stock,
        stock_minimo=stock_minimo,
        es_devolutivo=es_devolutivo,
        precio_unitario=Decimal("1000"),
        **extra,
    )


def crear_unidad_activo(producto, codigo, estado="DISPONIBLE"):
    return UnidadActivo.objects.create(inventario=producto, codigo=codigo, estado=estado)
