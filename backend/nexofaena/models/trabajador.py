from django.db import models

class Trabajador(models.Model):
    TURNOS = (
        ('dia', 'Día'),
        ('noche', 'Noche'),
    )

    id = models.BigAutoField(primary_key=True)
    rut = models.CharField(max_length=12, unique=True, verbose_name="RUT Trabajador")
    nombres = models.CharField(max_length=100, verbose_name="Nombres")
    apellido_paterno = models.CharField(max_length=100, verbose_name="Apellido Paterno")
    apellido_materno = models.CharField(max_length=100, blank=True, null=True, verbose_name="Apellido Materno")
    cargo = models.CharField(max_length=100, verbose_name="Cargo / Especialidad")
    turno = models.CharField(
        max_length=10, choices=TURNOS, blank=True, null=True, verbose_name="Turno Asignado",
        help_text="Turno habitual del trabajador (día/noche). Distinto del turno calculado por hora en cada entrega.",
    )

    telefono = models.CharField(max_length=20, blank=True, null=True, verbose_name="Teléfono")
    correo = models.EmailField(blank=True, null=True, verbose_name="Correo Electrónico")
    
    activo = models.BooleanField(default=True, verbose_name="¿Activo en Faena?")
    fecha_ingreso = models.DateField(blank=True, null=True, verbose_name="Fecha de Ingreso")
    
    fecha_creacion = models.DateTimeField(auto_now_add=True, verbose_name="Fecha Registro")
    fecha_actualizacion = models.DateTimeField(auto_now=True, verbose_name="Última Actualización")

    # Kiosco de autoservicio (reconocimiento facial): descriptor de 128
    # floats que entrega face-api.js, NO una foto. El matching contra la
    # cámara se hace en el dispositivo (distancia euclidiana contra los
    # descriptores cacheados offline), así que este campo viaja igual que
    # el resto de la ficha por /trabajadores/ y se cachea en Dexie.
    face_descriptor = models.JSONField(
        blank=True, null=True, verbose_name="Descriptor facial",
        help_text="Vector de 128 números generado por face-api.js al enrolar el rostro en el kiosco. No es una imagen.",
    )
    face_enrolado_en = models.DateTimeField(
        blank=True, null=True, verbose_name="Rostro enrolado en",
    )

    class Meta:
        db_table = "trabajadores"
        verbose_name = "Trabajador"
        verbose_name_plural = "Trabajadores"
        # Índices para búsquedas rápidas (Autocompletado)
        indexes = [
            models.Index(fields=['rut']),
            models.Index(fields=['apellido_paterno', 'nombres']),
        ]

    def __str__(self):
        return f"{self.rut} | {self.nombres} {self.apellido_paterno}"

    @property
    def nombre_completo(self):
        return f"{self.nombres} {self.apellido_paterno} {self.apellido_materno or ''}".strip()