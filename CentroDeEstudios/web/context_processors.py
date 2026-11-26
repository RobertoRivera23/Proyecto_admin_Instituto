# web/context_processors.py
from django.db.models import Q
from web.models import Notificacion, CuotaAlumno, Alumno, Inscripcion
from django.contrib.auth.models import Group
from django.utils import timezone
from datetime import timedelta


def notificaciones_context(request):
    """Context processor para notificaciones"""
    context = {}
    
    if request.user.is_authenticated:
        try:
            # Contador de notificaciones pendientes
            notificaciones_count = Notificacion.objects.filter(
                usuario_destino=request.user,
                eliminada=False,
                estado='PENDIENTE'
            ).count()
            
            context['notificaciones_count'] = notificaciones_count
            
            # También pasar algunas notificaciones para el dropdown (sin AJAX)
            notificaciones_dropdown = Notificacion.objects.filter(
                usuario_destino=request.user,
                eliminada=False,
                estado='PENDIENTE'
            ).select_related('tipo', 'usuario_origen').order_by('-fecha_creacion')[:5]
            
            context['notificaciones_dropdown'] = notificaciones_dropdown
            
        except Exception as e:
            # En caso de error, establecer valores por defecto
            print(f"❌ Error en context processor: {e}")
            context['notificaciones_count'] = 0
            context['notificaciones_dropdown'] = []
    
    else:
        context['notificaciones_count'] = 0
        context['notificaciones_dropdown'] = []
        
    return context

# web/context_processors.py
def personal_info(request):
    """
    Context processor que agrega información de permisos del personal
    a todos los templates
    """
    context = {
        'puede_asignar_tareas': False,
        'es_coordinador': False,
        'es_personal': False
    }
    
    if request.user.is_authenticated:
        # Verificar si el usuario tiene perfil de personal activo
        if hasattr(request.user, 'personal') and request.user.personal.activo:
            context['es_personal'] = True
            context['puede_asignar_tareas'] = True
            
            # Verificar si es coordinador
            if request.user.is_superuser or request.user.personal.tipo == 'COORDINADOR':
                context['es_coordinador'] = True
    
    return context



def moras_context(request):
    """Agregar contador de moras al contexto global - VERSIÓN CORREGIDA"""
    context = {
        'moras_count': 0,
        'notificaciones_pendientes_count': 0,
        'puede_asignar_tareas': False,
    }
    
    if request.user.is_authenticated:
        try:
            # Verificar si es coordinador o superusuario
            es_coord = False
            if hasattr(request.user, 'personal'):
                es_coord = request.user.personal.tipo == 'COORDINADOR'
            
            if es_coord or request.user.is_superuser:
                hoy = timezone.now().date()
                fecha_limite = hoy - timedelta(days=5)
                
                # CORRECCIÓN: Contar cuotas vencidas y no pagadas USANDO EL MODELO CORRECTO
                # El modelo Alumno NO tiene campo 'cuotas'. Usamos CuotaAlumno directamente
                moras_count = CuotaAlumno.objects.filter(
                    pagada=False,  # Cambiado: usar pagada=False en lugar de cuotas__pagada
                    fecha_vencimiento__lt=fecha_limite
                ).count()
                
                # Contar notificaciones pendientes del usuario
                notificaciones_pendientes_count = Notificacion.objects.filter(
                    usuario_destino=request.user,
                    estado='PENDIENTE',
                    eliminada=False
                ).count()
                
                context.update({
                    'moras_count': moras_count,
                    'notificaciones_pendientes_count': notificaciones_pendientes_count,
                    'puede_asignar_tareas': hasattr(request.user, 'personal') and request.user.personal.activo,
                })
                
        except Exception as e:
            # En caso de error, devolver valores por defecto
            print(f"✅ Error en context processor moras_context: {e}")
    
    return context



def contexto_global(request):
    """
    Contexto que se agrega automáticamente a todas las templates
    """
    context = {}
    
    if request.user.is_authenticated:
        # Información del usuario
        user = request.user
        
        # Determinar tipo de acceso
        es_admin_coord = False
        es_profesor = False
        tipo_acceso = None
        
        try:
            # Verificar si es superusuario
            if user.is_superuser:
                es_admin_coord = True
                tipo_acceso = 'SUPERUSUARIO'
            
            # Verificar si tiene personal asociado
            elif hasattr(user, 'personal') and user.personal:
                personal = user.personal
                es_admin_coord = personal.tipo in ['ADMINISTRATIVO', 'COORDINADOR']
                tipo_acceso = personal.tipo
            
            # Verificar si es profesor
            elif hasattr(user, 'profesor') and user.profesor:
                es_profesor = user.profesor.activo and not user.profesor.eliminado
                tipo_acceso = 'PROFESOR'
        
        except Exception as e:
            print(f"✅ Error en contexto_global al determinar tipo acceso: {e}")
            pass
        
        # Agregar al contexto
        context.update({
            'es_administrador_coordinador': es_admin_coord,
            'es_administrador': es_admin_coord,
            'es_profesor': es_profesor,
            'tipo_acceso': tipo_acceso,
        })
        
        # Notificaciones pendientes
        try:
            notificaciones_pendientes = Notificacion.objects.filter(
                usuario_destino=user,
                estado='PENDIENTE',  # Usar estado en lugar de leida
                eliminada=False
            ).count()
            context['notificaciones_pendientes_count'] = notificaciones_pendientes
            print(f"✅ Notificaciones pendientes calculadas: {notificaciones_pendientes}")
        except Exception as e:
            print(f"✅ Error en contexto_global al contar notificaciones: {e}")
            context['notificaciones_pendientes_count'] = 0
        
        # Moras pendientes (solo para coordinadores) - CORRECCIÓN
        if es_admin_coord:
            try:
                hoy = timezone.now().date()
                # CORRECCIÓN: Usar CuotaAlumno directamente con pagada=False
                moras_count = CuotaAlumno.objects.filter(
                    pagada=False,  # Cambiado de estado='PENDIENTE' a pagada=False
                    fecha_vencimiento__lt=hoy
                ).count()
                context['moras_count'] = moras_count
                print(f"✅ Moras calculadas: {moras_count}")
            except Exception as e:
                print(f"✅ Error en contexto_global al calcular moras: {e}")
                context['moras_count'] = 0
        else:
            context['moras_count'] = 0  # Para usuarios que no son admin/coord
    
    # Modo profesor activo
    context['modo_profesor_activo'] = request.session.get('modo_profesor', 'admin') == 'profesor'
    
    # Agregar atributos directos del request si existen
    if hasattr(request, 'es_administrador'):
        context['es_administrador'] = request.es_administrador
    
    return context

from .models import Personal, Profesor, Alumno

def usuario_context(request):
    """Context processor para agregar información del usuario a todos los templates"""
    context = {}
    
    if request.user.is_authenticated:
        try:
            # Intentar obtener el personal
            personal = Personal.objects.filter(
                user=request.user,
                activo=True,
                eliminado=False
            ).first()
            
            if personal:
                context['usuario_personal'] = personal
                context['es_personal'] = True
                context['es_secretaria'] = personal.tipo == 'SECRETARIA'
                context['es_administrativo'] = personal.tipo in ['SECRETARIA', 'ADMINISTRATIVO', 'COORDINADOR']
                context['es_administrador_coordinador'] = personal.tipo in ['ADMINISTRATIVO', 'COORDINADOR']
                context['tipo_personal'] = personal.tipo
            else:
                context['es_personal'] = False
                
            # Intentar obtener el profesor
            profesor = Profesor.objects.filter(
                user=request.user,
                activo=True,
                eliminado=False
            ).first()
            
            if profesor:
                context['usuario_profesor'] = profesor
                context['es_profesor'] = True
            else:
                context['es_profesor'] = False
                
            # Intentar obtener el alumno
            alumno = Alumno.objects.filter(
                user=request.user,
                activo=True,
                eliminado=False
            ).first()
            
            if alumno:
                context['usuario_alumno'] = alumno
                context['es_alumno'] = True
            else:
                context['es_alumno'] = False
                
        except Exception as e:
            print(f"⚠️ Error en context processor: {e}")
    
    return context

from django.contrib.auth.models import User
from web.models import Personal, Profesor, Alumno

def user_profile_info(request):
    """
    Context processor que obtiene la información del perfil del usuario
    independientemente de si es Personal, Profesor o Alumno.
    """
    context = {}
    
    if request.user.is_authenticated:
        user = request.user
        
        # Inicializar variables
        context['user_profile'] = None
        context['user_profile_type'] = None
        context['user_photo_url'] = None
        context['user_full_name'] = user.get_full_name() or user.username
        
        # Intentar obtener el perfil en este orden:
        # 1. Personal
        try:
            profile = Personal.objects.get(user=user)
            context['user_profile'] = profile
            context['user_profile_type'] = 'PERSONAL'
            if profile.foto:
                context['user_photo_url'] = profile.foto.url
        except Personal.DoesNotExist:
            pass
        
        # 2. Profesor (solo si no se encontró Personal)
        if not context['user_profile']:
            try:
                profile = Profesor.objects.get(user=user)
                context['user_profile'] = profile
                context['user_profile_type'] = 'PROFESOR'
                if profile.foto:
                    context['user_photo_url'] = profile.foto.url
            except Profesor.DoesNotExist:
                pass
        
        # 3. Alumno (solo si no se encontró Personal ni Profesor)
        if not context['user_profile']:
            try:
                profile = Alumno.objects.get(user=user)
                context['user_profile'] = profile
                context['user_profile_type'] = 'ALUMNO'
                if profile.foto:
                    context['user_photo_url'] = profile.foto.url
            except Alumno.DoesNotExist:
                pass
        
        # 4. Si aún no hay foto, usar una por defecto
        if not context['user_photo_url']:
            context['user_photo_url'] = None  # Lo manejaremos en el template
    
    return context