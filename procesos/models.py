from django.db import models
from django.contrib.auth.models import User

class Organizacion(models.Model):
    nombre = models.CharField(max_length=200)
    tipo = models.CharField(max_length=100)
    direccion = models.TextField(blank=True)
    telefono = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.nombre

class Lote(models.Model):
    ESTADOS = [
        ('preparacion', 'En Preparación'),
        ('proceso', 'En Proceso'),
        ('analisis', 'En Análisis'),
        ('finalizado', 'Finalizado'),
    ]
    
    codigo = models.CharField(max_length=50, unique=True)
    organizacion = models.ForeignKey(Organizacion, on_delete=models.CASCADE)
    variedad_cafe = models.CharField(max_length=100, blank=True, null=True)
    cantidad_quintales = models.DecimalField(max_digits=10, decimal_places=2)
    fecha_cosecha = models.DateField()
    estado = models.CharField(max_length=20, choices=ESTADOS, default='preparacion')
    propietarios = models.TextField(help_text="JSON con información de propietarios")
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    usuario_creador = models.ForeignKey(User, on_delete=models.CASCADE)
    
    def __str__(self):
        return f"{self.codigo} - {self.organizacion.nombre}"

class Muestra(models.Model):
    ESTADOS = [
        ('pendiente', 'Pendiente'),
        ('en_analisis', 'En Análisis'),
        ('completada', 'Completada'),
    ]
    
    lote = models.ForeignKey(Lote, on_delete=models.CASCADE)
    codigo_muestra = models.CharField(max_length=50)
    peso_gramos = models.DecimalField(max_digits=8, decimal_places=2)
    estado = models.CharField(max_length=20, choices=ESTADOS, default='pendiente')
    fecha_seleccion = models.DateTimeField(auto_now_add=True)
    
    # Resultados del análisis
    humedad = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    defectos = models.IntegerField(null=True, blank=True)
    puntaje_taza = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    observaciones = models.TextField(blank=True)
    fecha_resultado = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return f"{self.codigo_muestra} - {self.lote.codigo}"
