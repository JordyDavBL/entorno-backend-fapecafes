from rest_framework import serializers
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from .models import (Organizacion, LoteCafe, PropietarioCafe, MuestraCafe, ProcesoAnalisis, 
                    RegistroBitacora, UserProfile, RegistroDescarga, Insumo, RegistroUsoMaquinaria, PropietarioMaestro, TareaInsumo, Proceso, TareaProceso)

class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = '__all__'
        read_only_fields = ('user',)

class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True, validators=[validate_password])
    password2 = serializers.CharField(write_only=True, required=True)
    rol = serializers.ChoiceField(choices=UserProfile.ROLES_CHOICES, default='EMPLEADO')
    telefono = serializers.CharField(max_length=20, required=False, allow_blank=True)
    cedula = serializers.CharField(max_length=20, required=False, allow_blank=True)
    departamento = serializers.CharField(max_length=100, required=False, allow_blank=True)
    fecha_ingreso = serializers.DateField(required=False, allow_null=True)

    class Meta:
        model = User
        fields = ('username', 'password', 'password2', 'email', 'first_name', 'last_name', 
                 'rol', 'telefono', 'cedula', 'departamento', 'fecha_ingreso')
        extra_kwargs = {
            'first_name': {'required': True},
            'last_name': {'required': True},
            'email': {'required': True},
        }

    def validate(self, attrs):
        if attrs['password'] != attrs['password2']:
            raise serializers.ValidationError({"password": "Las contraseñas no coinciden."})
        return attrs

    def create(self, validated_data):
        # Extraer datos del perfil
        profile_data = {
            'rol': validated_data.pop('rol', 'EMPLEADO'),
            'telefono': validated_data.pop('telefono', ''),
            'cedula': validated_data.pop('cedula', ''),
            'departamento': validated_data.pop('departamento', ''),
            'fecha_ingreso': validated_data.pop('fecha_ingreso', None),
        }
        
        # Remover password2 antes de crear el usuario
        validated_data.pop('password2', None)
        
        # Crear el usuario
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            first_name=validated_data['first_name'],
            last_name=validated_data['last_name'],
            password=validated_data['password']
        )
        
        # Refrescar el usuario desde la base de datos para asegurar que tenga el perfil
        user.refresh_from_db()
        
        # Actualizar el perfil con los datos adicionales
        try:
            profile = user.profile
            for key, value in profile_data.items():
                if value is not None:  # Solo actualizar campos con valores válidos
                    setattr(profile, key, value)
            profile.save()
        except UserProfile.DoesNotExist:
            # Si por alguna razón no existe el perfil, crearlo
            UserProfile.objects.create(user=user, **profile_data)
        
        return user

class UserSerializer(serializers.ModelSerializer):
    profile = UserProfileSerializer(read_only=True)
    rol = serializers.CharField(source='profile.rol', read_only=True)
    rol_display = serializers.CharField(source='profile.get_rol_display', read_only=True)
    telefono = serializers.CharField(source='profile.telefono', read_only=True)
    cedula = serializers.CharField(source='profile.cedula', read_only=True)
    departamento = serializers.CharField(source='profile.departamento', read_only=True)
    fecha_ingreso = serializers.DateField(source='profile.fecha_ingreso', read_only=True)
    activo = serializers.BooleanField(source='profile.activo', read_only=True)
    nombre_completo = serializers.CharField(source='profile.nombre_completo', read_only=True)
    
    # Permisos basados en rol
    puede_crear_lotes = serializers.BooleanField(source='profile.puede_crear_lotes', read_only=True)
    puede_analizar_muestras = serializers.BooleanField(source='profile.puede_analizar_muestras', read_only=True)
    puede_generar_reportes = serializers.BooleanField(source='profile.puede_generar_reportes', read_only=True)
    puede_administrar_usuarios = serializers.BooleanField(source='profile.puede_administrar_usuarios', read_only=True)
    puede_ver_estadisticas_completas = serializers.BooleanField(source='profile.puede_ver_estadisticas_completas', read_only=True)
    
    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'first_name', 'last_name', 'profile', 'rol', 'rol_display',
                 'telefono', 'cedula', 'departamento', 'fecha_ingreso', 'activo', 'nombre_completo',
                 'puede_crear_lotes', 'puede_analizar_muestras', 'puede_generar_reportes',
                 'puede_administrar_usuarios', 'puede_ver_estadisticas_completas')

class OrganizacionSerializer(serializers.ModelSerializer):
    ubicacion_completa = serializers.ReadOnlyField()
    
    class Meta:
        model = Organizacion
        fields = '__all__'

class PropietarioMaestroSerializer(serializers.ModelSerializer):
    direccion_completa = serializers.ReadOnlyField()
    total_entregas = serializers.ReadOnlyField()
    total_quintales_historicos = serializers.ReadOnlyField()
    
    class Meta:
        model = PropietarioMaestro
        fields = '__all__'

class PropietarioCafeSerializer(serializers.ModelSerializer):
    direccion_completa = serializers.ReadOnlyField()
    propietario_maestro_nombre = serializers.CharField(source='propietario_maestro.nombre_completo', read_only=True)
    
    class Meta:
        model = PropietarioCafe
        fields = '__all__'

class MuestraCafeSerializer(serializers.ModelSerializer):
    propietario_nombre = serializers.CharField(source='propietario.nombre_completo', read_only=True)
    
    class Meta:
        model = MuestraCafe
        fields = '__all__'

class LoteCafeSerializer(serializers.ModelSerializer):
    organizacion_nombre = serializers.CharField(source='organizacion.nombre', read_only=True)
    propietarios = PropietarioCafeSerializer(many=True, read_only=True)
    muestras = MuestraCafeSerializer(many=True, read_only=True)
    total_muestras = serializers.SerializerMethodField()
    muestras_aprobadas = serializers.SerializerMethodField()
    muestras_contaminadas = serializers.SerializerMethodField()
    
    # Campos calculados de peso
    diferencia_peso = serializers.ReadOnlyField()
    porcentaje_perdida = serializers.ReadOnlyField()
    
    # Campos de limpieza formateados para mostrar en el frontend
    fecha_limpieza_formatted = serializers.SerializerMethodField()
    
    class Meta:
        model = LoteCafe
        fields = '__all__'
    
    def get_total_muestras(self, obj):
        return obj.muestras.count()
    
    def get_muestras_aprobadas(self, obj):
        return obj.muestras.filter(estado='APROBADA').count()
    
    def get_muestras_contaminadas(self, obj):
        return obj.muestras.filter(estado='CONTAMINADA').count()
    
    def get_fecha_limpieza_formatted(self, obj):
        """Formatear la fecha de limpieza para mostrar en el frontend"""
        if obj.fecha_limpieza:
            return obj.fecha_limpieza.strftime('%Y-%m-%d %H:%M')
        return None

    def validate_numero_lote(self, value):
        """Validar y generar número de lote único si es necesario"""
        if not value:
            raise serializers.ValidationError("El número de lote es requerido")
        
        # Verificar si el número de lote ya existe
        if LoteCafe.objects.filter(numero_lote=value).exists():
            # Generar un número único automáticamente
            base_numero = value
            contador = 1
            nuevo_numero = f"{base_numero}-{contador:02d}"
            
            while LoteCafe.objects.filter(numero_lote=nuevo_numero).exists():
                contador += 1
                nuevo_numero = f"{base_numero}-{contador:02d}"
            
            # Retornar el número único generado
            return nuevo_numero
        
        return value

class ProcesoAnalisisSerializer(serializers.ModelSerializer):
    lote_numero = serializers.CharField(source='lote.numero_lote', read_only=True)
    usuario_nombre = serializers.CharField(source='usuario_proceso.get_full_name', read_only=True)
    
    class Meta:
        model = ProcesoAnalisis
        fields = '__all__'

class CrearLoteConPropietariosSerializer(serializers.Serializer):
    organizacion = serializers.PrimaryKeyRelatedField(queryset=Organizacion.objects.all())
    numero_lote = serializers.CharField(max_length=50)
    fecha_entrega = serializers.DateTimeField()
    total_quintales = serializers.IntegerField()
    peso_total_inicial = serializers.DecimalField(max_digits=10, decimal_places=2, required=True)
    observaciones_peso = serializers.CharField(required=False, allow_blank=True)
    observaciones = serializers.CharField(required=False, allow_blank=True)
    propietarios = serializers.ListField(
        child=serializers.DictField()
    )
    
    def validate_numero_lote(self, value):
        """Validar y generar número de lote único si es necesario"""
        if not value:
            raise serializers.ValidationError("El número de lote es requerido")
        
        # Verificar si el número de lote ya existe
        if LoteCafe.objects.filter(numero_lote=value).exists():
            # Generar un número único automáticamente
            base_numero = value
            contador = 1
            nuevo_numero = f"{base_numero}-{contador:02d}"
            
            while LoteCafe.objects.filter(numero_lote=nuevo_numero).exists():
                contador += 1
                nuevo_numero = f"{base_numero}-{contador:02d}"
            
            # Retornar el número único generado
            return nuevo_numero
        
        return value

    def validate_propietarios(self, value):
        for propietario in value:
            # Validar campos requeridos
            if not propietario.get('quintales_entregados'):
                raise serializers.ValidationError("quintales_entregados es requerido para cada propietario")
            
            # Verificar si es propietario existente o nuevo
            propietario_maestro_id = propietario.get('propietario_maestro_id')
            
            if propietario_maestro_id:
                # Es un propietario existente, verificar que existe
                try:
                    PropietarioMaestro.objects.get(id=propietario_maestro_id, activo=True)
                except PropietarioMaestro.DoesNotExist:
                    raise serializers.ValidationError(f"Propietario maestro con ID {propietario_maestro_id} no encontrado")
            else:
                # Es un propietario nuevo, validar campos requeridos
                if not propietario.get('nombre_completo'):
                    raise serializers.ValidationError("nombre_completo es requerido para propietarios nuevos")
                if not propietario.get('cedula'):
                    raise serializers.ValidationError("cedula es requerido para propietarios nuevos")
            
            # Validar tipos de datos
            try:
                float(propietario['quintales_entregados'])
            except (ValueError, TypeError):
                raise serializers.ValidationError("quintales_entregados debe ser un número válido")
        
        return value
    
    def validate_peso_total_inicial(self, value):
        if value <= 0:
            raise serializers.ValidationError("El peso total inicial debe ser mayor a 0")
        return value
    
    def create(self, validated_data):
        propietarios_data = validated_data.pop('propietarios')
        validated_data['usuario_registro'] = self.context['request'].user
        lote = LoteCafe.objects.create(**validated_data)
        
        for propietario_data in propietarios_data:
            quintales_entregados = float(propietario_data['quintales_entregados'])
            propietario_maestro_id = propietario_data.get('propietario_maestro_id')
            
            if propietario_maestro_id:
                # Propietario existente
                propietario_maestro = PropietarioMaestro.objects.get(id=propietario_maestro_id)
                
                # Crear el registro de entrega con datos del propietario maestro
                PropietarioCafe.objects.create(
                    lote=lote,
                    propietario_maestro=propietario_maestro,
                    quintales_entregados=quintales_entregados,
                    nombre_completo=propietario_maestro.nombre_completo,
                    cedula=propietario_maestro.cedula,
                    telefono=propietario_maestro.telefono,
                    departamento=propietario_maestro.departamento,
                    municipio=propietario_maestro.municipio,
                    comunidad=propietario_maestro.comunidad,
                    calle=propietario_maestro.calle,
                    numero_casa=propietario_maestro.numero_casa,
                    referencias=propietario_maestro.referencias
                )
            else:
                # Propietario nuevo
                # Primero, verificar si ya existe un propietario maestro con esta cédula
                cedula = propietario_data['cedula']
                propietario_maestro, created = PropietarioMaestro.objects.get_or_create(
                    cedula=cedula,
                    defaults={
                        'nombre_completo': propietario_data['nombre_completo'],
                        'telefono': propietario_data.get('telefono', ''),
                        'departamento': propietario_data.get('departamento', ''),
                        'municipio': propietario_data.get('municipio', ''),
                        'comunidad': propietario_data.get('comunidad', ''),
                        'calle': propietario_data.get('calle', ''),
                        'numero_casa': propietario_data.get('numero_casa', ''),
                        'referencias': propietario_data.get('referencias', ''),
                        'activo': True
                    }
                )
                
                # Si no fue creado pero los datos han cambiado, actualizar el maestro
                if not created:
                    actualizado = False
                    if propietario_maestro.nombre_completo != propietario_data['nombre_completo']:
                        propietario_maestro.nombre_completo = propietario_data['nombre_completo']
                        actualizado = True
                    if propietario_maestro.telefono != propietario_data.get('telefono', ''):
                        propietario_maestro.telefono = propietario_data.get('telefono', '')
                        actualizado = True
                    
                    # Actualizar campos de dirección si son diferentes
                    campos_direccion = ['departamento', 'municipio', 'comunidad', 'calle', 'numero_casa', 'referencias']
                    for campo in campos_direccion:
                        nuevo_valor = propietario_data.get(campo, '')
                        if getattr(propietario_maestro, campo) != nuevo_valor:
                            setattr(propietario_maestro, campo, nuevo_valor)
                            actualizado = True
                    
                    if actualizado:
                        propietario_maestro.save()
                
                # Crear el registro de entrega
                PropietarioCafe.objects.create(
                    lote=lote,
                    propietario_maestro=propietario_maestro,
                    quintales_entregados=quintales_entregados,
                    # Copiar datos específicos para esta entrega
                    nombre_completo=propietario_data['nombre_completo'],
                    cedula=cedula,
                    telefono=propietario_data.get('telefono', ''),
                    departamento=propietario_data.get('departamento', ''),
                    municipio=propietario_data.get('municipio', ''),
                    comunidad=propietario_data.get('comunidad', ''),
                    calle=propietario_data.get('calle', ''),
                    numero_casa=propietario_data.get('numero_casa', ''),
                    referencias=propietario_data.get('referencias', ''),
                    direccion=propietario_data.get('direccion', '')
                )
        
        return lote

class SeleccionarMuestrasSerializer(serializers.Serializer):
    lote_id = serializers.IntegerField()
    propietarios_seleccionados = serializers.ListField(
        child=serializers.IntegerField()
    )
    
    def validate(self, data):
        if len(data['propietarios_seleccionados']) < 1:
            raise serializers.ValidationError("Debe seleccionar al menos 1 propietario para las muestras")
        return data

class RegistroBitacoraSerializer(serializers.ModelSerializer):
    usuario_nombre = serializers.CharField(source='usuario.username', read_only=True)
    usuario_email = serializers.CharField(source='usuario.email', read_only=True)
    lote_numero = serializers.CharField(source='lote.numero_lote', read_only=True)
    muestra_numero = serializers.CharField(source='muestra.numero_muestra', read_only=True)
    organizacion_nombre = serializers.CharField(source='organizacion.nombre', read_only=True)
    
    class Meta:
        model = RegistroBitacora
        fields = '__all__'
        
    def create(self, validated_data):
        # Agregar automáticamente el usuario del request
        request = self.context.get('request')
        if request and hasattr(request, 'user'):
            validated_data['usuario'] = request.user
        return super().create(validated_data)

class RegistroDescargaSerializer(serializers.ModelSerializer):
    empleado_nombre = serializers.CharField(source='empleado.get_full_name', read_only=True)
    empleado_username = serializers.CharField(source='empleado.username', read_only=True)
    lote_numero = serializers.CharField(source='lote.numero_lote', read_only=True)
    insumo_nombre = serializers.CharField(source='insumo.nombre', read_only=True)
    insumo_codigo = serializers.CharField(source='insumo.codigo', read_only=True)
    insumo_tipo = serializers.CharField(source='insumo.get_tipo_display', read_only=True)
    
    class Meta:
        model = RegistroDescarga
        fields = '__all__'
        read_only_fields = ('empleado', 'tiempo_descarga_minutos', 'fecha_registro')
    
    def create(self, validated_data):
        # Asignar automáticamente el empleado del request
        request = self.context.get('request')
        if request and hasattr(request, 'user'):
            validated_data['empleado'] = request.user
        return super().create(validated_data)
    
    def validate(self, data):
        # Validar que la hora de fin sea posterior a la de inicio
        if data.get('hora_inicio') and data.get('hora_fin'):
            if data['hora_fin'] <= data['hora_inicio']:
                raise serializers.ValidationError("La hora de fin debe ser posterior a la hora de inicio")
        
        # Validar cantidad de insumo si se proporciona
        if data.get('insumo') and data.get('cantidad_insumo_usado'):
            insumo = data['insumo']
            cantidad_usada = data['cantidad_insumo_usado']
            
            # Validar que la cantidad sea positiva
            if cantidad_usada <= 0:
                raise serializers.ValidationError("La cantidad de insumo usado debe ser mayor a 0")
            
            # Verificar si el tipo de insumo requiere descuento de stock
            tipos_que_restan = ['CONTENEDOR', 'EQUIPO_MEDICION', 'OTRO']
            if insumo.tipo in tipos_que_restan:
                # Verificar que hay suficiente stock
                if cantidad_usada > insumo.cantidad_disponible:
                    raise serializers.ValidationError(
                        f"No hay suficiente stock del insumo '{insumo.nombre}'. "
                        f"Stock disponible: {insumo.cantidad_disponible} {insumo.get_unidad_medida_display()}, "
                        f"cantidad solicitada: {cantidad_usada} {insumo.get_unidad_medida_display()}"
                    )
        
        return data

class InsumoSerializer(serializers.ModelSerializer):
    tipo_display = serializers.CharField(source='get_tipo_display', read_only=True)
    unidad_medida_display = serializers.CharField(source='get_unidad_medida_display', read_only=True)
    estado_inventario = serializers.CharField(read_only=True)
    necesita_reposicion = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = Insumo
        fields = '__all__'
    
    def validate_codigo(self, value):
        """Validar que el código sea único"""
        if not value:
            raise serializers.ValidationError("El código es requerido")
        
        # Verificar unicidad solo si es una creación o si el código ha cambiado
        instance = self.instance
        if instance is None:  # Creación
            if Insumo.objects.filter(codigo=value).exists():
                raise serializers.ValidationError("Ya existe un insumo con este código")
        else:  # Actualización
            if instance.codigo != value and Insumo.objects.filter(codigo=value).exists():
                raise serializers.ValidationError("Ya existe un insumo con este código")
        
        return value
    
    def validate_nombre(self, value):
        """Validar que el nombre no esté vacío"""
        if not value or not value.strip():
            raise serializers.ValidationError("El nombre del insumo es requerido")
        return value.strip()
    
    def validate_tipo(self, value):
        """Validar que el tipo sea válido"""
        if not value:
            raise serializers.ValidationError("El tipo de insumo es requerido")
        
        tipos_validos = [choice[0] for choice in Insumo.TIPOS_INSUMO]
        if value not in tipos_validos:
            raise serializers.ValidationError(f"Tipo de insumo inválido. Opciones válidas: {', '.join(tipos_validos)}")
        
        return value
    
    def validate_unidad_medida(self, value):
        """Validar que la unidad de medida sea válida"""
        if not value:
            raise serializers.ValidationError("La unidad de medida es requerida")
        
        unidades_validas = [choice[0] for choice in Insumo.UNIDADES_MEDIDA]
        if value not in unidades_validas:
            raise serializers.ValidationError(f"Unidad de medida inválida. Opciones válidas: {', '.join(unidades_validas)}")
        
        return value
    
    def validate_cantidad_disponible(self, value):
        """Validar que la cantidad disponible sea no negativa"""
        if value < 0:
            raise serializers.ValidationError("La cantidad disponible no puede ser negativa")
        return value
    
    def validate_cantidad_minima(self, value):
        """Validar que la cantidad mínima sea no negativa"""
        if value < 0:
            raise serializers.ValidationError("La cantidad mínima no puede ser negativa")
        return value
    
    def validate_capacidad_maxima(self, value):
        """Validar que la capacidad máxima sea positiva si se proporciona"""
        if value is not None and value <= 0:
            raise serializers.ValidationError("La capacidad máxima debe ser mayor a 0")
        return value

class RegistroUsoMaquinariaSerializer(serializers.ModelSerializer):
    empleado_nombre = serializers.CharField(source='empleado.get_full_name', read_only=True)
    empleado_username = serializers.CharField(source='empleado.username', read_only=True)
    insumo_nombre = serializers.CharField(source='maquinaria.nombre', read_only=True)
    insumo_codigo = serializers.CharField(source='maquinaria.codigo', read_only=True)
    tipo_maquinaria_display = serializers.SerializerMethodField()
    lote_numero = serializers.CharField(source='lote.numero_lote', read_only=True)
    trabajador_nombre = serializers.CharField(write_only=True, required=True)
    
    class Meta:
        model = RegistroUsoMaquinaria
        fields = '__all__'
        read_only_fields = ('empleado', 'tiempo_uso_minutos')
    
    def get_tipo_maquinaria_display(self, obj):
        """Obtener el nombre legible del tipo de maquinaria"""
        return obj.get_tipo_maquinaria_display()
    
    def create(self, validated_data):
        # Asignar automáticamente el empleado del request
        request = self.context.get('request')
        if request and hasattr(request, 'user'):
            validated_data['empleado'] = request.user
        
        # Remover el campo trabajador_nombre ya que no existe en el modelo
        validated_data.pop('trabajador_nombre', None)
        
        return super().create(validated_data)
    
    def validate(self, data):
        # Validar que la hora de fin sea posterior a la de inicio
        if data.get('hora_inicio') and data.get('hora_fin'):
            if data['hora_fin'] <= data['hora_inicio']:
                raise serializers.ValidationError("La hora de fin debe ser posterior a la hora de inicio")
        
        # Validar que se proporcione al menos el tipo de maquinaria o un insumo específico
        if not data.get('tipo_maquinaria') and not data.get('maquinaria'):
            raise serializers.ValidationError("Debe especificar el tipo de maquinaria o seleccionar un insumo específico")
        
        # Validar que el peso no exceda la capacidad del insumo (si se especifica un insumo específico)
        if (data.get('maquinaria') and 
            data.get('peso_total_descargado') and 
            data['maquinaria'].capacidad_maxima):
            if data['peso_total_descargado'] > data['maquinaria'].capacidad_maxima:
                raise serializers.ValidationError(
                    f"El peso descargado ({data['peso_total_descargado']} kg) excede la capacidad máxima "
                    f"del insumo ({data['maquinaria'].capacidad_maxima} kg)"
                )
        
        return data

class TareaInsumoSerializer(serializers.ModelSerializer):
    """Serializer para el modelo TareaInsumo"""
    empleado_nombre = serializers.CharField(source='empleado.get_full_name', read_only=True)
    empleado_username = serializers.CharField(source='empleado.username', read_only=True)
    insumo_nombre = serializers.CharField(source='insumo.nombre', read_only=True)
    insumo_codigo = serializers.CharField(source='insumo.codigo', read_only=True)
    insumo_tipo = serializers.CharField(source='insumo.get_tipo_display', read_only=True)
    muestra_numero = serializers.CharField(source='muestra.numero_muestra', read_only=True)
    lote_numero = serializers.CharField(source='lote.numero_lote', read_only=True)
    
    class Meta:
        model = TareaInsumo
        fields = '__all__'
        read_only_fields = ('empleado', 'fecha_creacion')
    
    def create(self, validated_data):
        # Asignar automáticamente el empleado del request
        request = self.context.get('request')
        if request and hasattr(request, 'user'):
            validated_data['empleado'] = request.user
        return super().create(validated_data)
    
    def validate(self, data):
        # Validar que se proporcione al menos una muestra o un lote
        if not data.get('muestra') and not data.get('lote'):
            raise serializers.ValidationError("Debe especificar al menos una muestra o un lote")
        
        # Validar que la hora de fin sea posterior a la de inicio si ambas se proporcionan
        if data.get('hora_inicio') and data.get('hora_fin'):
            if data['hora_fin'] <= data['hora_inicio']:
                raise serializers.ValidationError("La hora de fin debe ser posterior a la hora de inicio")
        
        # Validar que la cantidad sea positiva si se proporciona
        if data.get('cantidad') and data['cantidad'] <= 0:
            raise serializers.ValidationError("La cantidad debe ser mayor a 0")
        
        # Validar que el peso usado sea positivo si se proporciona
        if data.get('peso_usado') and data['peso_usado'] <= 0:
            raise serializers.ValidationError("El peso usado debe ser mayor a 0")
        
        # Validar que el tiempo de uso sea positivo si se proporciona
        if data.get('tiempo_uso') and data['tiempo_uso'] <= 0:
            raise serializers.ValidationError("El tiempo de uso debe ser mayor a 0")
        
        # Validar descripción no vacía
        if not data.get('descripcion') or not data['descripcion'].strip():
            raise serializers.ValidationError("La descripción de la tarea es requerida")
        
        return data

class ProcesoSerializer(serializers.ModelSerializer):
    """Serializer para el modelo Proceso"""
    lotes_info = LoteCafeSerializer(source='lotes', many=True, read_only=True)
    responsable_nombre = serializers.CharField(source='responsable.get_full_name', read_only=True)
    usuario_creacion_nombre = serializers.CharField(source='usuario_creacion.get_full_name', read_only=True)
    
    # Campos calculados
    total_lotes = serializers.ReadOnlyField()
    porcentaje_progreso = serializers.ReadOnlyField()
    duracion_dias = serializers.ReadOnlyField()
    
    # Campos para mostrar información de estado
    estado_display = serializers.CharField(source='get_estado_display', read_only=True)
    fase_actual_display = serializers.CharField(source='get_fase_actual_display', read_only=True)
    
    class Meta:
        model = Proceso
        fields = '__all__'
        read_only_fields = ('numero', 'fecha_inicio', 'fecha_actualizacion', 'usuario_creacion')
    
    def create(self, validated_data):
        """Crear un nuevo proceso con validaciones y generación automática de número"""
        # Asignar automáticamente el usuario que está creando el proceso
        request = self.context.get('request')
        if request and hasattr(request, 'user'):
            validated_data['usuario_creacion'] = request.user
        
        # Generar número único de proceso si no se proporciona
        if not validated_data.get('numero'):
            # Buscar el último proceso para generar número secuencial
            ultimo_proceso = Proceso.objects.order_by('-id').first()
            if ultimo_proceso and ultimo_proceso.numero:
                try:
                    # Extraer número del formato "Proceso001"
                    numero_actual = int(ultimo_proceso.numero.replace('Proceso', ''))
                    siguiente_numero = numero_actual + 1
                except (ValueError, AttributeError):
                    siguiente_numero = 1
            else:
                siguiente_numero = 1
            
            validated_data['numero'] = f"Proceso{siguiente_numero:03d}"
        
        # Verificar que el número sea único
        contador = 1
        numero_base = validated_data['numero']
        while Proceso.objects.filter(numero=validated_data['numero']).exists():
            validated_data['numero'] = f"{numero_base}-{contador:02d}"
            contador += 1
        
        # Crear el proceso
        proceso = super().create(validated_data)
        
        return proceso
    
    def validate_numero(self, value):
        """Validar que el número de proceso sea único"""
        if value:
            # Solo validar unicidad si se está actualizando y el número cambió
            instance = self.instance
            if instance is None:  # Creación
                if Proceso.objects.filter(numero=value).exists():
                    raise serializers.ValidationError("Ya existe un proceso con este número")
            else:  # Actualización
                if instance.numero != value and Proceso.objects.filter(numero=value).exists():
                    raise serializers.ValidationError("Ya existe un proceso con este número")
        
        return value
    
    def validate_lotes(self, value):
        """Validar que los lotes estén en estados válidos para procesos"""
        if value:
            estados_validos = ['APROBADO', 'SEPARACION_APLICADA']
            lotes_invalidos = []
            
            for lote in value:
                if lote.estado not in estados_validos:
                    lotes_invalidos.append(f"{lote.numero_lote} (estado: {lote.estado})")
            
            if lotes_invalidos:
                raise serializers.ValidationError(
                    f"Los siguientes lotes no están en estados válidos para procesos: {', '.join(lotes_invalidos)}. "
                    f"Estados válidos: {', '.join(estados_validos)}"
                )
        
        return value

class TareaProcesoSerializer(serializers.ModelSerializer):
    """Serializer para el modelo TareaProceso"""
    proceso_numero = serializers.CharField(source='proceso.numero', read_only=True)
    empleado_nombre = serializers.CharField(source='empleado.get_full_name', read_only=True)
    tipo_tarea_display = serializers.CharField(source='get_tipo_tarea_display', read_only=True)
    fase_display = serializers.CharField(source='get_fase_display', read_only=True)
    
    class Meta:
        model = TareaProceso
        fields = '__all__'
        read_only_fields = ('empleado', 'fecha_registro', 'duracion_minutos')
    
    def create(self, validated_data):
        validated_data['empleado'] = self.context['request'].user
        return super().create(validated_data)
    
    def validate(self, data):
        # Validar que la hora de fin sea posterior a la de inicio
        if data.get('hora_inicio') and data.get('hora_fin'):
            if data['hora_fin'] <= data['hora_inicio']:
                raise serializers.ValidationError("La hora de fin debe ser posterior a la hora de inicio")
        
        return data