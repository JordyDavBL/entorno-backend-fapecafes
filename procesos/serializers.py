from rest_framework import serializers
from .models import Organizacion, Lote, Muestra
import json

class OrganizacionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organizacion
        fields = '__all__'

class LoteSerializer(serializers.ModelSerializer):
    organizacion_nombre = serializers.CharField(source='organizacion.nombre', read_only=True)
    propietarios_json = serializers.SerializerMethodField()
    usuario_creador = serializers.HiddenField(default=serializers.CurrentUserDefault())
    
    class Meta:
        model = Lote
        fields = '__all__'
    
    def get_propietarios_json(self, obj):
        try:
            return json.loads(obj.propietarios) if obj.propietarios else []
        except:
            return []
    
    def create(self, validated_data):
        # El usuario_creador se establece automáticamente desde el contexto
        return super().create(validated_data)

class MuestraSerializer(serializers.ModelSerializer):
    lote_codigo = serializers.CharField(source='lote.codigo', read_only=True)
    
    class Meta:
        model = Muestra
        fields = '__all__'