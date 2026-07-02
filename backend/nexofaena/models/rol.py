from django.db import models

class Rol(models.Model):
    id = models.BigAutoField(primary_key=True)
    nombre = models.CharField(max_length=50, unique=True, verbose_name="Nombre del Rol")
    descripcion = models.TextField(blank=True, null=True, verbose_name="Descripción")
    activo = models.BooleanField(default=True, verbose_name="¿Activo?")
    
    fecha_creacion = models.DateTimeField(auto_now_add=True, verbose_name="Fecha Creación")
    fecha_actualizacion = models.DateTimeField(auto_now=True, verbose_name="Última Actualización")

    class Meta:
        db_table = "roles"
        verbose_name = "Rol"
        verbose_name_plural = "Roles"
        ordering = ['nombre']

    def __str__(self):
        return self.nombre