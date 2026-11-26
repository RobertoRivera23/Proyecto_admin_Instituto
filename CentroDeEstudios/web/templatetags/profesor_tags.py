from django import template
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.contrib import messages

register = template.Library()

@register.filter
def tiene_acceso_profesor(user):
    """
    Filtro para verificar si un usuario tiene acceso a vistas de profesor
    Uso en template: {{ user|tiene_acceso_profesor }}
    """
    if not user.is_authenticated:
        return False
    
    try:
        from ..decorators import tiene_acceso_vistas_profesor
        tiene_acceso, _, _ = tiene_acceso_vistas_profesor(user)
        return tiene_acceso
    except Exception:
        return False

@register.filter
def es_administrador_o_coordinador(user):
    """
    Filtro para verificar si es administrador o coordinador
    Uso: {{ user|es_administrador_o_coordinador }}
    """
    if not user.is_authenticated:
        return False
    
    try:
        from ..decorators import es_administrador_o_coordinador as es_admin_coord
        return es_admin_coord(user)
    except Exception:
        return False

@register.simple_tag
def obtener_profesor_actual(user):
    """
    Obtiene el objeto Profesor del usuario
    Uso: {% obtener_profesor_actual user as profesor %}
    """
    if not user.is_authenticated:
        return None
    
    try:
        from ..decorators import obtener_profesor_usuario
        return obtener_profesor_usuario(user)
    except Exception:
        return None

@register.simple_tag
def modo_profesor_activo(request):
    """
    Verifica si el modo profesor está activo
    Uso: {% modo_profesor_activo request as modo_activo %}
    """
    return request.session.get('modo_profesor', 'admin') == 'profesor'