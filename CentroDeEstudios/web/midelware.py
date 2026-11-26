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