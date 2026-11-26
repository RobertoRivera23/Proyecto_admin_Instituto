from django.utils.deprecation import MiddlewareMixin
from .models import Personal, Profesor
from django.shortcuts import redirect
from django.contrib import messages
from django.urls import reverse

class ControlAccesoMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Verificar si el usuario necesita cambiar su contraseña temporal
        if (request.user.is_authenticated and 
            hasattr(request.user, 'personal') and
            request.user.check_password('temp123') and
            not request.path.startswith('/cambiar_contrasena') and
            request.path != reverse('logout')):
            
            messages.warning(
                request, 
                'Debes cambiar tu contraseña temporal para continuar usando el sistema.'
            )
            return redirect('cambiar_contrasena')
        
        response = self.get_response(request)
        return response
    


class UserInfoMiddleware(MiddlewareMixin):
    """Middleware simplificado solo para inicializar atributos"""
    
    def process_request(self, request):
        # Inicializar siempre
        request.es_administrador = False
        request.es_profesor = False
        request.profesor = None
        request.tipo_acceso = None
        
        if request.user.is_authenticated:
            # Solo inicializar atributos básicos
            if request.user.is_superuser:
                request.es_administrador = True
                request.tipo_acceso = 'SUPERUSUARIO'
            
            # Verificar si tiene personal
            elif hasattr(request.user, 'personal_relacionado'):
                personal = request.user.personal_relacionado
                request.es_administrador = personal.tipo in ['ADMINISTRATIVO', 'COORDINADOR']
                request.tipo_acceso = personal.tipo
            
            # Verificar si es profesor
            if hasattr(request.user, 'profesor_relacionado'):
                profesor = request.user.profesor_relacionado
                request.profesor = profesor
                request.es_profesor = profesor.activo and not profesor.eliminado
                if not request.tipo_acceso:
                    request.tipo_acceso = 'PROFESOR'
            elif hasattr(request.user, 'profesor'):
                profesor = request.user.profesor
                request.profesor = profesor
                request.es_profesor = profesor.activo and not profesor.eliminado
                if not request.tipo_acceso:
                    request.tipo_acceso = 'PROFESOR'
        
        return None
    
    
# web/middleware.py
class DebugRoutingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        print("=" * 60)
        print(f"🛣️  MIDDLEWARE ROUTING - Path: {request.path}")
        print(f"🛣️  View Resolved: {request.resolver_match}")
        
        if request.resolver_match:
            print(f"🛣️  View Function: {request.resolver_match.func.__name__}")
            print(f"🛣️  View Module: {request.resolver_match.func.__module__}")
        
        response = self.get_response(request)
        return response

# En settings.py
MIDDLEWARE = [
    # ... otros middlewares ...
    'web.middleware.DebugRoutingMiddleware',
]