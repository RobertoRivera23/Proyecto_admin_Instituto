# # web/decorators.py
# from functools import wraps
# from django.core.exceptions import PermissionDenied
# from django.contrib.auth.decorators import login_required
# from django.contrib.auth.models import Permission
# from django.shortcuts import redirect
# from django.contrib import messages
# from .models import Personal

# # -------------------------------------------------------------------
# # DECORADORES BASE CON REDIRECCIÓN
# # -------------------------------------------------------------------

# def rol_requerido(roles_permitidos):
#     """
#     Decorador para verificar que el usuario tenga un rol específico
#     CON REDIRECCIÓN A PÁGINA AMIGABLE
#     """
#     def decorator(view_func):
#         @wraps(view_func)
#         def _wrapped_view(request, *args, **kwargs):
#             # Permitir superusuarios
#             if request.user.is_superuser:
#                 return view_func(request, *args, **kwargs)
            
#             try:
#                 # Obtener personal usando el nombre correcto de relación
#                 if hasattr(request.user, 'personal_relacionado'):
#                     personal = request.user.personal_relacionado
#                 elif hasattr(request.user, 'personal'):
#                     personal = request.user.personal
#                 else:
#                     personal = Personal.objects.get(user=request.user)
                
#                 # Verificar rol
#                 if personal.tipo not in roles_permitidos:
#                     print(f"🚨 ROL DENEGADO - {personal.tipo} no está en {roles_permitidos}")
#                     messages.error(request, f"Rol '{personal.tipo}' no permitido. Se requiere: {', '.join(roles_permitidos)}")
#                     return redirect('sin_permiso_personal')
                    
#             except (AttributeError, Personal.DoesNotExist):
#                 print(f"🚨 USUARIO SIN PERSONAL: {request.user.username}")
#                 messages.error(request, "No tienes perfil de personal asociado")
#                 return redirect('sin_permiso_personal')
                
#             return view_func(request, *args, **kwargs)
#         return _wrapped_view
#     return decorator

# def permiso_requerido(permiso_codename):
#     """
#     Decorador para verificar permisos específicos de Django
#     CON REDIRECCIÓN A PÁGINA AMIGABLE
#     """
#     def decorator(view_func):
#         @wraps(view_func)
#         def _wrapped_view(request, *args, **kwargs):
#             # Permitir superusuarios automáticamente
#             if request.user.is_superuser:
#                 return view_func(request, *args, **kwargs)
            
#             if not request.user.has_perm(permiso_codename):
#                 print(f"🚨 PERMISO DENEGADO - {request.user.username} necesita {permiso_codename}")
                
#                 # Mensaje informativo basado en el rol del usuario
#                 try:
#                     if hasattr(request.user, 'personal_relacionado'):
#                         personal = request.user.personal_relacionado
#                         mensaje = f"Tu rol '{personal.tipo}' no tiene el permiso '{permiso_codename}'"
#                     else:
#                         mensaje = f"No tienes el permiso '{permiso_codename}'"
#                 except:
#                     mensaje = f"Permiso requerido: {permiso_codename}"
                
#                 messages.error(request, mensaje)
#                 return redirect('sin_permiso_personal')
            
#             return view_func(request, *args, **kwargs)
#         return _wrapped_view
#     return decorator

# # -------------------------------------------------------------------
# # DECORADORES DE ROLES EXISTENTES (MEJORADOS)
# # -------------------------------------------------------------------

# def acceso_administrativo_requerido(view_func):
#     """
#     Decorador para acceso solo a personal administrativo y coordinadores
#     CON REDIRECCIÓN
#     """
#     @wraps(view_func)
#     @login_required
#     def _wrapped_view(request, *args, **kwargs):
#         # Permitir superusuarios
#         if request.user.is_superuser:
#             return view_func(request, *args, **kwargs)
        
#         try:
#             if hasattr(request.user, 'personal_relacionado'):
#                 personal = request.user.personal_relacionado
#             else:
#                 personal = request.user.personal
            
#             if personal.tipo not in ['ADMINISTRATIVO', 'COORDINADOR']:
#                 messages.error(request, f"Acceso restringido a ADMINISTRATIVO o COORDINADOR. Tu rol: {personal.tipo}")
#                 return redirect('sin_permiso_personal')
                
#         except (AttributeError, Personal.DoesNotExist):
#             messages.error(request, "No tienes perfil de personal asociado")
#             return redirect('sin_permiso_personal')
        
#         return view_func(request, *args, **kwargs)
#     return _wrapped_view

# def acceso_secretaria_requerido(view_func):
#     """
#     Decorador para acceso a secretaría y superiores
#     CON REDIRECCIÓN
#     """
#     @wraps(view_func)
#     @login_required
#     def _wrapped_view(request, *args, **kwargs):
#         # Permitir superusuarios
#         if request.user.is_superuser:
#             return view_func(request, *args, **kwargs)
        
#         try:
#             if hasattr(request.user, 'personal_relacionado'):
#                 personal = request.user.personal_relacionado
#             else:
#                 personal = request.user.personal
            
#             if personal.tipo not in ['ADMINISTRATIVO', 'COORDINADOR', 'SECRETARIA']:
#                 messages.error(request, f"Acceso restringido. Tu rol: {personal.tipo}")
#                 return redirect('sin_permiso_personal')
                
#         except (AttributeError, Personal.DoesNotExist):
#             messages.error(request, "No tienes perfil de personal asociado")
#             return redirect('sin_permiso_personal')
        
#         return view_func(request, *args, **kwargs)
#     return _wrapped_view

# # -------------------------------------------------------------------
# # DECORADORES COMBINADOS CON REDIRECCIÓN
# # -------------------------------------------------------------------

# def gestion_completa_requerida(view_func):
#     """
#     Requiere rol administrativo/coordinador Y permiso de gestión completa
#     CON REDIRECCIÓN A PÁGINA AMIGABLE
#     """
#     @wraps(view_func)
#     @login_required
#     def _wrapped_view(request, *args, **kwargs):
#         # Permitir superusuarios automáticamente
#         if request.user.is_superuser:
#             return view_func(request, *args, **kwargs)
        
#         # Verificar permiso primero
#         if not request.user.has_perm('web.can_manage_staff'):
#             print(f"🚨 PERMISO DENEGADO - {request.user.username} necesita 'web.can_manage_staff'")
#             messages.error(request, "No tienes permiso para gestión completa de personal")
#             return redirect('sin_permiso_personal')
        
#         # Luego verificar rol
#         try:
#             if hasattr(request.user, 'personal_relacionado'):
#                 personal = request.user.personal_relacionado
#             else:
#                 personal = request.user.personal
            
#             if personal.tipo not in ['ADMINISTRATIVO', 'COORDINADOR']:
#                 print(f"🚨 ROL DENEGADO - {personal.tipo} no es ADMINISTRATIVO/COORDINADOR")
#                 messages.error(request, f"Rol '{personal.tipo}' no puede realizar gestión completa. Se requiere ADMINISTRATIVO o COORDINADOR.")
#                 return redirect('sin_permiso_personal')
        
#         except (AttributeError, Personal.DoesNotExist):
#             print(f"🚨 USUARIO SIN PERSONAL: {request.user.username}")
#             messages.error(request, "No tienes perfil de personal asociado")
#             return redirect('sin_permiso_personal')
        
#         return view_func(request, *args, **kwargs)
#     return _wrapped_view

# # -------------------------------------------------------------------
# # DECORADOR PERSONAL_REQUIRED (YA TIENE REDIRECCIÓN)
# # -------------------------------------------------------------------

# def personal_required(view_func):
#     """
#     Decorador que verifica que el usuario tenga un perfil Personal activo
#     YA TIENE REDIRECCIÓN
#     """
#     @wraps(view_func)
#     def _wrapped_view(request, *args, **kwargs):
#         if not request.user.is_authenticated:
#             return redirect('login')
        
#         personal = None
        
#         if hasattr(request.user, 'personal_relacionado'):
#             personal = request.user.personal_relacionado
#         elif hasattr(request.user, 'personal'):
#             personal = request.user.personal
#         else:
#             try:
#                 personal = Personal.objects.get(user=request.user)
#             except Personal.DoesNotExist:
#                 personal = None
        
#         if not personal:
#             messages.error(request, "Tu usuario no está asociado a ningún personal")
#             return redirect('sin_permiso_personal')
        
#         if not personal.activo:
#             messages.error(request, "Tu cuenta de personal no está activa")
#             return redirect('sin_permiso_personal')
        
#         request.personal = personal
#         return view_func(request, *args, **kwargs)
    
#     return _wrapped_view

# # -------------------------------------------------------------------
# # FUNCIÓN AUXILIAR ES_COORDINADOR
# # -------------------------------------------------------------------

# def es_coordinador(user):
#     """
#     Función auxiliar que devuelve True si el usuario es coordinador.
#     """
#     if user.is_superuser:
#         return True
    
#     try:
#         if hasattr(user, 'personal_relacionado'):
#             personal = user.personal_relacionado
#         elif hasattr(user, 'personal'):
#             personal = user.personal
#         else:
#             personal = Personal.objects.get(user=user)
        
#         return personal.tipo == 'COORDINADOR'
    
#     except (Personal.DoesNotExist, AttributeError):
#         return False

# # -------------------------------------------------------------------
# # DECORADOR TEMPORAL COORDINADOR_O_SUPERUSUARIO
# # -------------------------------------------------------------------

# def coordinador_o_superusuario(view_func):
#     """
#     Decorador temporal que permite acceso a coordinadores y superusuarios
#     CON REDIRECCIÓN AMIGABLE
#     """
#     @wraps(view_func)
#     def _wrapped_view(request, *args, **kwargs):
#         if not request.user.is_authenticated:
#             return redirect('login')
        
#         # Permitir superusuarios
#         if request.user.is_superuser:
#             return view_func(request, *args, **kwargs)
        
#         # Verificar si es coordinador
#         if es_coordinador(request.user):
#             return view_func(request, *args, **kwargs)
        
#         # Si no es coordinador ni superusuario
#         messages.error(request, "Acceso restringido a coordinadores y administradores")
#         return redirect('sin_permiso_personal')
    
#     return _wrapped_view


# # -------------------------------------------------------------------
# # DECORADORES FALTANTES (QUE SE IMPORTAN EN VIEWS.PY)
# # -------------------------------------------------------------------

# def gestion_usuarios_requerida(view_func):
#     """
#     Requiere rol administrativo Y permisos de gestión de usuarios
#     CON REDIRECCIÓN AMIGABLE
#     """
#     @wraps(view_func)
#     @login_required
#     def _wrapped_view(request, *args, **kwargs):
#         # Permitir superusuarios automáticamente
#         if request.user.is_superuser:
#             return view_func(request, *args, **kwargs)
        
#         # Verificar permiso primero
#         if not request.user.has_perm('auth.can_manage_user_accounts'):
#             print(f"🚨 PERMISO DENEGADO - {request.user.username} necesita 'auth.can_manage_user_accounts'")
#             messages.error(request, "No tienes permiso para gestión de usuarios")
#             return redirect('sin_permiso_personal')
        
#         # Luego verificar rol
#         try:
#             if hasattr(request.user, 'personal_relacionado'):
#                 personal = request.user.personal_relacionado
#             else:
#                 personal = request.user.personal
            
#             if personal.tipo not in ['ADMINISTRATIVO']:
#                 print(f"🚨 ROL DENEGADO - {personal.tipo} no es ADMINISTRATIVO")
#                 messages.error(request, f"Rol '{personal.tipo}' no puede gestionar usuarios. Se requiere ADMINISTRATIVO.")
#                 return redirect('sin_permiso_personal')
        
#         except (AttributeError, Personal.DoesNotExist):
#             print(f"🚨 USUARIO SIN PERSONAL: {request.user.username}")
#             messages.error(request, "No tienes perfil de personal asociado")
#             return redirect('sin_permiso_personal')
        
#         return view_func(request, *args, **kwargs)
#     return _wrapped_view

# def auditoria_requerida(view_func):
#     """
#     Solo para supervisores de seguridad - rol + permisos de auditoría
#     CON REDIRECCIÓN AMIGABLE
#     """
#     @wraps(view_func)
#     @login_required
#     def _wrapped_view(request, *args, **kwargs):
#         # Permitir superusuarios automáticamente
#         if request.user.is_superuser:
#             return view_func(request, *args, **kwargs)
        
#         # Verificar permiso primero
#         if not request.user.has_perm('web.can_view_audit_logs'):
#             print(f"🚨 PERMISO DENEGADO - {request.user.username} necesita 'web.can_view_audit_logs'")
#             messages.error(request, "No tienes permiso para ver auditoría")
#             return redirect('sin_permiso_personal')
        
#         # Luego verificar rol
#         try:
#             if hasattr(request.user, 'personal_relacionado'):
#                 personal = request.user.personal_relacionado
#             else:
#                 personal = request.user.personal
            
#             if personal.tipo not in ['ADMINISTRATIVO']:
#                 print(f"🚨 ROL DENEGADO - {personal.tipo} no es ADMINISTRATIVO")
#                 messages.error(request, f"Rol '{personal.tipo}' no puede ver auditoría. Se requiere ADMINISTRATIVO.")
#                 return redirect('sin_permiso_personal')
        
#         except (AttributeError, Personal.DoesNotExist):
#             print(f"🚨 USUARIO SIN PERSONAL: {request.user.username}")
#             messages.error(request, "No tienes perfil de personal asociado")
#             return redirect('sin_permiso_personal')
        
#         return view_func(request, *args, **kwargs)
#     return _wrapped_view


# web/decorators.py - VERSIÓN COMPLETA CORREGIDA
from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required as django_login_required
from .models import Personal

# -------------------------------------------------------------------
# FUNCIONES AUXILIARES
# -------------------------------------------------------------------

def obtener_personal(user):
    """Obtiene el objeto Personal de un usuario"""
    if hasattr(user, 'personal_relacionado'):
        return user.personal_relacionado
    elif hasattr(user, 'personal'):
        return user.personal
    try:
        return Personal.objects.get(user=user)
    except Personal.DoesNotExist:
        return None

# -------------------------------------------------------------------
# DECORADORES BASE
# -------------------------------------------------------------------

def login_required_custom(view_func):
    """Versión mejorada de login_required con mensajes"""
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.warning(request, "Debes iniciar sesión para acceder a esta página")
            return redirect('login')
        return view_func(request, *args, **kwargs)
    return _wrapped_view

def personal_required(view_func):
    """Verifica que el usuario tenga un Personal activo"""
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        
        personal = obtener_personal(request.user)
        
        if not personal:
            messages.error(request, "Tu usuario no tiene un perfil de Personal asociado")
            return redirect('sin_permiso_personal')
        
        if not personal.activo:
            messages.error(request, "Tu cuenta de Personal no está activa")
            return redirect('sin_permiso_personal')
        
        request.personal = personal
        return view_func(request, *args, **kwargs)
    
    return _wrapped_view

# -------------------------------------------------------------------
# DECORADORES POR ROL (ESTRICTOS)
# -------------------------------------------------------------------

# web/decorators.py - AGREGAR ESTA FUNCIÓN NUEVA

def solo_coordinador_estricto(view_func):
    """
    Decorador 100% autónomo que SOLO permite COORDINADORES
    Con logs de DEBUG visibles
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        # 1. Verificar autenticación
        if not request.user.is_authenticated:
            from django.contrib import messages
            messages.error(request, "Debes iniciar sesión")
            from django.shortcuts import redirect
            return redirect('login')
        
        # 2. Obtener el personal (DEBUG: imprimir para diagnóstico)
        print("=" * 60)
        print(f"🎯 DECORADOR solo_coordinador_estricto EJECUTADO")
        print(f"🎯 Usuario intentando acceder: {request.user.username}")
        
        personal = None
        
        # Intentar todas las formas posibles
        if hasattr(request.user, 'personal_relacionado'):
            personal = request.user.personal_relacionado
            print(f"🎯 Personal obtenido por: personal_relacionado")
        elif hasattr(request.user, 'personal'):
            personal = request.user.personal
            print(f"🎯 Personal obtenido por: personal")
        else:
            try:
                from .models import Personal
                personal = Personal.objects.get(user=request.user)
                print(f"🎯 Personal obtenido por: búsqueda directa")
            except Exception as e:
                print(f"🎯 ERROR obteniendo personal: {e}")
                personal = None
        
        # 3. Si no tiene personal, DENEGAR
        if not personal:
            print(f"🚨 BLOQUEO: Usuario sin personal")
            from django.contrib import messages
            messages.error(request, "No tienes perfil de Personal")
            from django.shortcuts import redirect
            return redirect('sin_permiso_personal')
        
        # 4. VERIFICACIÓN PRINCIPAL: ¿Es COORDINADOR?
        print(f"🎯 Rol del usuario: {personal.tipo}")
        
        if personal.tipo != 'COORDINADOR':
            print(f"🚨 BLOQUEO: {personal.tipo} no es COORDINADOR")
            print(f"🚨 Usuario {request.user.username} BLOQUEADO")
            from django.contrib import messages
            messages.error(request, 
                f"ACCESO EXCLUSIVO para COORDINADORES. Tu rol: {personal.tipo}"
            )
            from django.shortcuts import redirect
            return redirect('sin_permiso_personal')
        
        # 5. Verificar que esté activo
        if not personal.activo:
            print(f"🚨 BLOQUEO: Personal inactivo")
            from django.contrib import messages
            messages.error(request, "Tu cuenta no está activa")
            from django.shortcuts import redirect
            return redirect('sin_permiso_personal')
        
        print(f"✅ PERMITIDO: {request.user.username} es COORDINADOR")
        print("=" * 60)
        
        # 6. Pasar el personal al request para uso interno
        request.personal = personal
        
        return view_func(request, *args, **kwargs)
    
    return _wrapped_view

def solo_para_gestion_usuarios(view_func):
    """
    Decorador EXCLUSIVO para coordinadores que pueden gestionar usuarios
    Verifica:
    1. Está autenticado
    2. Tiene permiso Django 'can_manage_user_accounts' (solo coordinadores)
    3. Opcional: También verifica el rol
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        print("=" * 60)
        print(f"🔐 VERIFICACIÓN GESTIÓN USUARIOS - Usuario: {request.user.username}")
        
        # 1. Autenticación
        if not request.user.is_authenticated:
            return redirect('login')
        
        # 2. Verificar permiso Django ESPECÍFICO
        permiso_requerido = 'auth.can_manage_user_accounts'
        
        if not request.user.has_perm(permiso_requerido):
            # Mostrar información de diagnóstico
            print(f"🚨 FALTA PERMISO: {permiso_requerido}")
            
            # Ver qué permisos tiene
            todos_permisos = list(request.user.get_all_permissions())
            print(f"📋 Permisos actuales: {todos_permisos}")
            
            # Ver qué grupos tiene
            grupos = [g.name for g in request.user.groups.all()]
            print(f"👥 Grupos actuales: {grupos}")
            
            messages.error(request, 
                "❌ ACCESO DENEGADO\n"
                "Esta función requiere permiso especial para gestión de usuarios.\n"
                "Solo los coordinadores pueden acceder."
            )
            return redirect('sin_permiso_personal')
        
        # 3. Verificación adicional por rol (opcional pero recomendado)
        try:
            # Obtener rol del personal
            if hasattr(request.user, 'personal_relacionado'):
                personal = request.user.personal_relacionado
                rol = personal.tipo
            else:
                from .models import Personal
                personal = Personal.objects.get(user=request.user)
                rol = personal.tipo
            
            print(f"✅ USUARIO AUTORIZADO: {request.user.username}")
            print(f"   Rol: {rol}")
            print(f"   Permiso 'can_manage_user_accounts': ✅")
            print("=" * 60)
            
            # Pasar personal al request para uso en la vista
            request.personal = personal
            
        except Exception as e:
            print(f"⚠️ Advertencia: No se pudo obtener información del personal: {e}")
            # Continuar de todos modos porque el permiso Django ya está verificado
        
        return view_func(request, *args, **kwargs)
    
    return _wrapped_view


def gestion_personal_requerida(view_func):
    """
    Decorador EXCLUSIVO para administradores y coordinadores
    NO permite secretarías
    """
    @wraps(view_func)
    @login_required_custom
    @personal_required
    def _wrapped_view(request, *args, **kwargs):
        personal = request.personal
        
        # Solo administradores y coordinadores
        if personal.tipo not in ['ADMINISTRATIVO', 'COORDINADOR']:
            messages.error(request, 
                f"Acceso restringido a ADMINISTRATIVO y COORDINADOR. Tu rol: {personal.tipo}"
            )
            return redirect('sin_permiso_personal')
        
        return view_func(request, *args, **kwargs)
    
    return _wrapped_view


def solo_coordinador(view_func):
    """
    Decorador para verificar que el usuario es coordinador
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        print(f"🔐 VERIFICACIÓN COORDINADOR - Usuario: {request.user.username}")
        
        # Verificar autenticación
        if not request.user.is_authenticated:
            return redirect('login')
        
        # Verificar si es coordinador
        es_coordinador = False
        if hasattr(request.user, 'personal_relacionado'):
            es_coordinador = request.user.personal_relacionado.tipo == 'COORDINADOR'
        else:
            try:
                from .models import Personal
                personal = Personal.objects.get(user=request.user)
                es_coordinador = personal.tipo == 'COORDINADOR'
            except:
                pass
        
        if not es_coordinador:
            messages.error(request, 
                "❌ ACCESO DENEGADO\n"
                "Esta función solo está disponible para coordinadores."
            )
            return redirect('sin_permiso_personal')
        
        print(f"✅ COORDINADOR AUTORIZADO: {request.user.username}")
        return view_func(request, *args, **kwargs)
    
    return _wrapped_view

def solo_administrativo(view_func):
    """Solo para ADMINISTRATIVOS (estricto)"""
    @wraps(view_func)
    @login_required_custom
    @personal_required
    def _wrapped_view(request, *args, **kwargs):
        personal = request.personal
        
        if personal.tipo != 'ADMINISTRATIVO':
            messages.error(request, 
                f"Acceso exclusivo para ADMINISTRATIVOS. Tu rol: {personal.tipo}"
            )
            return redirect('sin_permiso_personal')
        
        return view_func(request, *args, **kwargs)
    
    return _wrapped_view

# -------------------------------------------------------------------
# DECORADORES POR ROL (JERÁRQUICOS)
# -------------------------------------------------------------------

def coordinador_o_superior(view_func):
    """COORDINADORES y ADMINISTRATIVOS (roles superiores)"""
    @wraps(view_func)
    @login_required_custom
    @personal_required
    def _wrapped_view(request, *args, **kwargs):
        personal = request.personal
        roles_permitidos = ['COORDINADOR', 'ADMINISTRATIVO']
        
        if personal.tipo not in roles_permitidos:
            messages.error(request, 
                f"Acceso para {', '.join(roles_permitidos)}. Tu rol: {personal.tipo}"
            )
            return redirect('sin_permiso_personal')
        
        return view_func(request, *args, **kwargs)
    
    return _wrapped_view

def secretaria_o_superior(view_func):
    """SECRETARIAS, COORDINADORES y ADMINISTRATIVOS"""
    @wraps(view_func)
    @login_required_custom
    @personal_required
    def _wrapped_view(request, *args, **kwargs):
        personal = request.personal
        roles_permitidos = ['SECRETARIA', 'COORDINADOR', 'ADMINISTRATIVO']
        
        if personal.tipo not in roles_permitidos:
            messages.error(request, 
                f"Acceso para {', '.join(roles_permitidos)}. Tu rol: {personal.tipo}"
            )
            return redirect('sin_permiso_personal')
        
        return view_func(request, *args, **kwargs)
    
    return _wrapped_view

# -------------------------------------------------------------------
# DECORADORES COMBINADOS (ROL + PERMISO)
# -------------------------------------------------------------------

def gestion_completa_requerida(view_func):
    """
    Para ADMINISTRATIVOS y COORDINADORES
    que tengan permiso 'web.can_manage_staff'
    """
    @wraps(view_func)
    @login_required_custom
    @personal_required
    def _wrapped_view(request, *args, **kwargs):
        personal = request.personal
        
        # 1. Verificar rol
        if personal.tipo not in ['ADMINISTRATIVO', 'COORDINADOR']:
            messages.error(request, 
                f"Se requiere ADMINISTRATIVO o COORDINADOR. Tu rol: {personal.tipo}"
            )
            return redirect('sin_permiso_personal')
        
        # 2. Verificar permiso
        if not request.user.has_perm('web.can_manage_staff'):
            messages.error(request, 
                "No tienes permiso para gestión completa de personal"
            )
            return redirect('sin_permiso_personal')
        
        return view_func(request, *args, **kwargs)
    
    return _wrapped_view

def gestion_usuarios_requerida(view_func):
    """
    EXCLUSIVO para COORDINADORES
    que tengan permiso 'auth.can_manage_user_accounts'
    """
    @wraps(view_func)
    @login_required_custom
    @personal_required
    def _wrapped_view(request, *args, **kwargs):
        personal = request.personal
        
        # 1. Verificar rol (EXCLUSIVO para coordinadores)
        if personal.tipo != 'COORDINADOR':
            messages.error(request, 
                f"Vista exclusiva para COORDINADORES. Tu rol: {personal.tipo}"
            )
            return redirect('sin_permiso_personal')
        
        # 2. Verificar permiso
        if not request.user.has_perm('auth.can_manage_user_accounts'):
            messages.error(request, 
                "No tienes permiso para gestión de usuarios"
            )
            return redirect('sin_permiso_personal')
        
        return view_func(request, *args, **kwargs)
    
    return _wrapped_view

# -------------------------------------------------------------------
# DECORADORES COMPATIBLES
# -------------------------------------------------------------------

# Alias para compatibilidad
acceso_administrativo_requerido = coordinador_o_superior
acceso_secretaria_requerido = secretaria_o_superior

# Función auxiliar (no decorador)
def es_coordinador(user):
    """Función que devuelve True si el usuario es coordinador"""
    personal = obtener_personal(user)
    if not personal:
        return False
    return personal.tipo == 'COORDINADOR'

def rol_requerido(roles_permitidos):
    """Decorador que verifica que el usuario tenga uno de los roles especificados"""
    def decorator(view_func):
        @wraps(view_func)
        @login_required_custom
        @personal_required
        def _wrapped_view(request, *args, **kwargs):
            personal = request.personal
            
            if personal.tipo not in roles_permitidos:
                messages.error(request, 
                    f"Se requiere: {', '.join(roles_permitidos)}. Tu rol: {personal.tipo}"
                )
                return redirect('sin_permiso_personal')
            
            return view_func(request, *args, **kwargs)
        
        return _wrapped_view
    return decorator

def permiso_requerido(permiso_codename):
    """Decorador que verifica un permiso específico"""
    def decorator(view_func):
        @wraps(view_func)
        @login_required_custom
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.has_perm(permiso_codename):
                messages.error(request, 
                    f"Falta permiso: {permiso_codename}"
                )
                return redirect('sin_permiso_personal')
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator

# -------------------------------------------------------------------
# DECORADOR SOLO_PARA_GESTION_USUARIOS (para compatibilidad con views.py)
# -------------------------------------------------------------------

def solo_para_gestion_usuarios(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        # Verificación básica - ajustar después
        if not request.user.groups.filter(name='Coordinador').exists():
            messages.error(request, "Solo coordinadores pueden acceder")
            return redirect('dashboard')
        return view_func(request, *args, **kwargs)
    return _wrapped_view

# Importa los otros decoradores que sí existen
from .decorators import (
    login_required_custom,
    personal_required,
    solo_coordinador,
    solo_coordinador_estricto,
    solo_administrativo,
    coordinador_o_superior,
    secretaria_o_superior,
    gestion_completa_requerida,
    gestion_usuarios_requerida,
    acceso_administrativo_requerido,
    acceso_secretaria_requerido,
    es_coordinador,
    rol_requerido,
    permiso_requerido,
)

solo_para_gestion_usuarios = gestion_usuarios_requerida



# ============================================
# FUNCIONES AUXILIARES PARA PROFESORES/ADMINISTRADORES
# ============================================

def obtener_profesor_usuario(user):
    """Obtiene el objeto Profesor de un usuario (si existe)"""
    profesor = None
    
    # Intentar todas las formas posibles
    if hasattr(user, 'profesor_relacionado'):
        profesor = user.profesor_relacionado
    elif hasattr(user, 'profesor'):
        profesor = user.profesor
    else:
        try:
            from .models import Profesor
            profesor = Profesor.objects.get(user=user)
        except:
            profesor = None
    
    return profesor

def obtener_personal_usuario(user):
    """Obtiene el objeto Personal de un usuario (si existe)"""
    personal = None
    
    if hasattr(user, 'personal_relacionado'):
        personal = user.personal_relacionado
    elif hasattr(user, 'personal'):
        personal = user.personal
    else:
        try:
            from .models import Personal
            personal = Personal.objects.get(user=user)
        except:
            personal = None
    
    return personal

def es_administrador_o_coordinador(user):
    """Verifica si el usuario es administrador o coordinador activo"""
    if user.is_superuser:
        return True
    
    personal = obtener_personal_usuario(user)
    if personal:
        return (personal.activo and not personal.eliminado and 
                personal.tipo in ['ADMINISTRATIVO', 'COORDINADOR'])
    
    return False

def es_profesor_activo(user):
    """Verifica si el usuario es un profesor activo"""
    profesor = obtener_profesor_usuario(user)
    if profesor:
        return profesor.activo and not profesor.eliminado
    return False

def tiene_acceso_vistas_profesor(user):
    """
    Verifica si el usuario puede acceder a vistas de profesor
    Return: (bool, tipo_usuario, objeto)
    """
    if not user.is_authenticated:
        return False, None, None
    
    # 1. Superusuarios siempre pueden
    if user.is_superuser:
        # Intentar obtener perfil de profesor si existe
        profesor = obtener_profesor_usuario(user)
        return True, 'SUPERUSUARIO', profesor
    
    # 2. Administradores/Coordinadores pueden
    if es_administrador_o_coordinador(user):
        # Intentar obtener perfil de profesor si existe
        profesor = obtener_profesor_usuario(user)
        personal = obtener_personal_usuario(user)
        return True, personal.tipo if personal else 'ADMINISTRADOR', profesor
    
    # 3. Profesores activos pueden
    if es_profesor_activo(user):
        profesor = obtener_profesor_usuario(user)
        return True, 'PROFESOR', profesor
    
    return False, None, None

# ============================================
# DECORADORES NUEVOS PARA ACCESO AMPLIADO
# ============================================

def puede_ver_vistas_profesor(view_func):
    """
    Decorador que permite acceso a:
    - Profesores activos
    - Administradores
    - Coordinadores
    - Superusuarios
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        print("=" * 60)
        print(f"🔐 ACCESO VISTAS PROFESOR - Usuario: {request.user.username}")
        
        # Verificar acceso
        acceso_permitido, tipo_usuario, profesor = tiene_acceso_vistas_profesor(request.user)
        
        if not acceso_permitido:
            print(f"🚨 BLOQUEO: Usuario no tiene acceso a vistas de profesor")
            messages.error(request, "Acceso restringido. Se requiere ser profesor, administrador o coordinador.")
            return redirect('sin_permiso_personal')
        
        print(f"✅ PERMITIDO: {request.user.username} - Tipo: {tipo_usuario}")
        
        # Guardar información en el request
        request.tipo_acceso = tipo_usuario
        request.es_administrador = tipo_usuario in ['ADMINISTRATIVO', 'COORDINADOR', 'SUPERUSUARIO']
        request.es_profesor = tipo_usuario == 'PROFESOR'
        
        # Si tiene perfil de profesor, guardarlo
        if profesor:
            request.profesor = profesor
            print(f"   Perfil profesor: {profesor.nombre_completo()}")
        else:
            request.profesor = None
        
        print("=" * 60)
        return view_func(request, *args, **kwargs)
    
    return _wrapped_view

def puede_ver_cursos_profesor(view_func):
    """
    Decorador para vistas específicas de curso:
    - Profesores: solo sus cursos asignados
    - Administradores/Coordinadores: todos los cursos
    """
    @wraps(view_func)
    @login_required_custom
    @puede_ver_vistas_profesor
    def _wrapped_view(request, *args, **kwargs):
        curso_id = kwargs.get('curso_id')
        
        print("=" * 60)
        print(f"🔐 VERIFICANDO ACCESO A CURSO - Usuario: {request.user.username}, Curso ID: {curso_id}")
        
        try:
            from .models import Curso
            curso = Curso.objects.get(id=curso_id, activo=True, eliminado=False)
            
            # Si es administrador/coordinador, permitir acceso a cualquier curso
            if request.es_administrador:
                print(f"✅ ACCESO ADMINISTRATIVO: Puede ver cualquier curso")
                request.curso = curso
                return view_func(request, *args, **kwargs)
            
            # Si es profesor, verificar que sea su curso
            if request.es_profesor:
                if curso.profesor == request.profesor:
                    print(f"✅ ACCESO PROFESOR: Es el profesor asignado al curso")
                    request.curso = curso
                    return view_func(request, *args, **kwargs)
                else:
                    print(f"🚨 BLOQUEO: No es el profesor asignado")
                    messages.error(request, 
                        f"No tienes permiso para acceder a este curso. "
                        f"Está asignado a: {curso.profesor.nombre_completo() if curso.profesor else 'ningún profesor'}"
                    )
                    return redirect('mis_cursos_profesor')
            
            # Caso no contemplado
            messages.error(request, "Error de permisos")
            return redirect('dashboard_profesor')
            
        except Curso.DoesNotExist:
            print(f"🚨 ERROR: Curso no encontrado")
            messages.error(request, "El curso no existe o no está activo")
            return redirect('mis_cursos_profesor')
        except Exception as e:
            print(f"🚨 ERROR: {str(e)}")
            messages.error(request, f"Error al verificar permisos: {str(e)}")
            return redirect('dashboard_profesor')
    
    return _wrapped_view

def profesor_solo_lectura(view_func):
    """
    Decorador especial para vistas donde:
    - Administradores/Coordinadores pueden EDITAR
    - Profesores solo pueden VER (lectura)
    """
    @wraps(view_func)
    @puede_ver_vistas_profesor
    def _wrapped_view(request, *args, **kwargs):
        # Marcar si es solo lectura
        request.solo_lectura = request.es_profesor  # True si es profesor, False si es admin
        return view_func(request, *args, **kwargs)
    
    return _wrapped_view

from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages

def requiere_permiso_profesor(view_func):
    """
    Decorador que protege vistas para profesores, administradores, coordinadores y superusuarios
    CORREGIDO para manejar correctamente SECRETARIA y otros roles
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        print(f"🔐 DECORADOR requiere_permiso_profesor - Usuario: {request.user.username}")
        
        # 1. Verificar autenticación
        if not request.user.is_authenticated:
            return redirect('login')
        
        # 2. Obtener información del usuario
        personal = obtener_personal_usuario(request.user)
        
        # 3. Verificar si es superusuario
        if request.user.is_superuser:
            print(f"✅ SUPERUSUARIO - Acceso permitido")
            # Configurar atributos del request
            request.es_administrador = True
            request.es_profesor = False
            request.tipo_acceso = 'SUPERUSUARIO'
            return view_func(request, *args, **kwargs)
        
        # 4. Verificar si es administrador/coordinador
        if personal and personal.tipo in ['ADMINISTRATIVO', 'COORDINADOR']:
            print(f"✅ {personal.tipo} - Acceso permitido")
            request.es_administrador = True
            request.es_profesor = False
            request.tipo_acceso = personal.tipo
            request.personal = personal
            return view_func(request, *args, **kwargs)
        
        # 5. Verificar si es profesor activo
        profesor = obtener_profesor_usuario(request.user)
        if profesor and profesor.activo and not profesor.eliminado:
            print(f"✅ PROFESOR - Acceso permitido")
            request.es_administrador = False
            request.es_profesor = True
            request.tipo_acceso = 'PROFESOR'
            request.profesor = profesor
            return view_func(request, *args, **kwargs)
        
        # 6. Si es SECRETARIA u otro rol, DENEGAR acceso
        print(f"🚨 ACCESO DENEGADO - Rol: {personal.tipo if personal else 'Sin rol'}")
        
        # Mensaje específico para secretaría
        if personal and personal.tipo == 'SECRETARIA':
            messages.error(request, 
                "❌ Acceso restringido\n\n"
                "Los secretarios no tienen acceso a vistas de profesor.\n\n"
                "✅ Usa la lista de profesores para ver información básica."
            )
            # Redirigir al dashboard personal de secretaría
            return redirect('dashboard_personal')
        
        # Para otros roles
        messages.error(request, "Acceso restringido. Se requieren permisos de profesor, administrador o coordinador.")
        return redirect('dashboard_personal')
    
    return wrapper

def puede_acceder_profesor(user):
    """
    Verifica si un usuario puede acceder a las vistas de profesor
    Permite: Profesores, Administrativos, Coordinadores, Superusuarios
    """
    if not user.is_authenticated:
        return False
    
    if user.is_superuser:
        return True
    
    # Verificar si es administrativo o coordinador
    try:
        if hasattr(user, 'personal_relacionado'):
            personal = user.personal_relacionado
            if personal.tipo in ['ADMINISTRATIVO', 'COORDINADOR']:
                return True
    except:
        pass
    
    # Verificar si es profesor activo
    try:
        if hasattr(user, 'profesor_relacionado'):
            profesor = user.profesor_relacionado
            return profesor.activo and not profesor.eliminado
    except:
        pass
    
    return False

# Luego modifica el decorador `puede_ver_vistas_profesor`:
def puede_ver_vistas_profesor(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not puede_acceder_profesor(request.user):
            messages.error(request, "Acceso restringido a profesores, administrativos y coordinadores")
            return redirect('sin_permiso_personal')
        
        # Establecer atributos del request
        request.es_administrador = es_administrador_o_coordinador(request.user)
        request.es_profesor = es_profesor_activo(request.user)
        
        return view_func(request, *args, **kwargs)
    
    return _wrapped_view


# Agrega al final de web/decorators.py

# ============================================
# DECORADORES ESPECÍFICOS PARA PROFESORES
# ============================================

def requiere_ser_profesor_del_curso(view_func):
    """
    Decorador que verifica que el usuario sea el profesor asignado al curso
    o un administrador/coordinador.
    """
    @wraps(view_func)
    def _wrapped_view(request, curso_id, *args, **kwargs):
        print("=" * 60)
        print(f"🎯 VERIFICACIÓN PROFESOR DEL CURSO - Usuario: {request.user.username}")
        print(f"🎯 Curso ID: {curso_id}")
        
        # 1. Verificar autenticación
        if not request.user.is_authenticated:
            return redirect('login')
        
        # 2. Obtener el curso
        from django.shortcuts import get_object_or_404
        from .models import Curso
        
        try:
            curso = Curso.objects.get(id=curso_id, activo=True, eliminado=False)
        except Curso.DoesNotExist:
            from django.contrib import messages
            messages.error(request, "El curso no existe o no está activo")
            return redirect('mis_cursos')
        
        # 3. Determinar si es administrador/coordinador
        es_admin = False
        if request.user.is_superuser:
            es_admin = True
            print(f"🎯 Usuario es superusuario")
        else:
            # Verificar si tiene personal relacionado con rol administrativo
            try:
                from .models import Personal
                personal = Personal.objects.get(user=request.user, activo=True, eliminado=False)
                if personal.tipo in ['ADMINISTRATIVO', 'COORDINADOR']:
                    es_admin = True
                    print(f"🎯 Usuario es {personal.tipo}")
            except:
                pass
        
        # 4. Si es administrador, permitir acceso directo
        if es_admin:
            print(f"✅ PERMITIDO: Acceso administrativo al curso {curso.nombre}")
            request.curso = curso
            request.es_administrador = True
            return view_func(request, curso_id, *args, **kwargs)
        
        # 5. Si NO es administrador, debe ser profesor del curso
        try:
            from .models import Profesor
            profesor = Profesor.objects.get(user=request.user, activo=True, eliminado=False)
            print(f"🎯 Profesor encontrado: {profesor.nombre_completo()}")
            
            # Verificar si es el profesor asignado al curso
            if curso.profesor == profesor:
                print(f"✅ PERMITIDO: Es el profesor asignado al curso {curso.nombre}")
                request.curso = curso
                request.profesor = profesor
                request.es_administrador = False
                return view_func(request, curso_id, *args, **kwargs)
            else:
                print(f"🚨 DENEGADO: No es el profesor asignado")
                print(f"   Curso asignado a: {curso.profesor.nombre_completo() if curso.profesor else 'Ninguno'}")
                from django.contrib import messages
                messages.error(
                    request, 
                    f"No eres el profesor asignado a este curso. "
                    f"El curso está asignado a: {curso.profesor.nombre_completo() if curso.profesor else 'ningún profesor'}"
                )
                return redirect('mis_cursos')
                
        except Profesor.DoesNotExist:
            print(f"🚨 DENEGADO: Usuario no es profesor")
            from django.contrib import messages
            messages.error(request, "No tienes perfil de profesor activo")
            return redirect('dashboard')
    
    return _wrapped_view


def puede_tomar_asistencia(view_func):
    """
    Decorador específico para tomar asistencia
    Permite:
    - Profesor asignado al curso
    - Administradores/Coordinadores en modo edición especial
    """
    @wraps(view_func)
    def _wrapped_view(request, curso_id, *args, **kwargs):
        print("=" * 60)
        print(f"📋 VERIFICACIÓN TOMAR ASISTENCIA - Usuario: {request.user.username}")
        
        # 1. Verificar autenticación
        if not request.user.is_authenticated:
            return redirect('login')
        
        # 2. Obtener el curso
        from django.shortcuts import get_object_or_404
        from .models import Curso
        from django.contrib import messages
        
        curso = get_object_or_404(Curso, id=curso_id, activo=True, eliminado=False)
        
        # 3. Verificar si es administrador
        es_admin = False
        if request.user.is_superuser:
            es_admin = True
            print(f"✅ Superusuario - Acceso permitido")
        else:
            # Verificar roles administrativos
            try:
                from .models import Personal
                personal = Personal.objects.get(user=request.user, activo=True, eliminado=False)
                if personal.tipo in ['ADMINISTRATIVO', 'COORDINADOR']:
                    es_admin = True
                    print(f"✅ {personal.tipo} - Acceso permitido (modo administrador)")
            except:
                pass
        
        # 4. Si es administrador, verificar si quiere editar
        if es_admin:
            puede_editar = request.GET.get('editar') == '1'
            if puede_editar:
                print(f"⚠️ Administrador en MODO EDICIÓN (editar=1)")
            else:
                print(f"ℹ️ Administrador en MODO VISTA")
            
            request.curso = curso
            request.es_administrador = True
            request.puede_editar = puede_editar
            return view_func(request, curso_id, *args, **kwargs)
        
        # 5. Si NO es administrador, debe ser profesor del curso
        try:
            from .models import Profesor
            profesor = Profesor.objects.get(user=request.user, activo=True, eliminado=False)
            
            if curso.profesor == profesor:
                print(f"✅ Profesor asignado - Acceso permitido para tomar asistencia")
                request.curso = curso
                request.profesor = profesor
                request.es_administrador = False
                request.puede_editar = True  # Profesor siempre puede editar
                return view_func(request, curso_id, *args, **kwargs)
            else:
                print(f"🚨 DENEGADO: No es el profesor asignado")
                messages.error(
                    request,
                    f"No eres el profesor asignado a este curso. "
                    f"Contacta al administrador si necesitas acceso."
                )
                return redirect('mis_cursos')
                
        except Profesor.DoesNotExist:
            print(f"🚨 DENEGADO: No tiene perfil de profesor")
            messages.error(request, "No tienes perfil de profesor activo")
            return redirect('dashboard')
    
    return _wrapped_view