"""
URL configuration for backend project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.http import JsonResponse

def api_root(request):
    return JsonResponse({
        'mensaje': 'Bienvenido a la API del proyecto',
        'endpoints_disponibles': {
            'admin': '/admin/',
            'registro': '/api/users/register/',
            'inicio_de_sesión': '/api/users/login/',
            'refrescar_token': '/api/users/login/refresh/',
            'perfil_usuario': '/api/users/me/',
            'organizaciones': '/api/users/organizaciones/',
            'lotes': '/api/users/lotes/',
            'muestras': '/api/users/muestras/',
            'estadisticas': '/api/users/estadisticas/'
        }
    })

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/users/', include('users.urls')),
    path('api/procesos/', include('procesos.urls')),
    path('', api_root, name='api_root'),  # Ruta raíz
]
