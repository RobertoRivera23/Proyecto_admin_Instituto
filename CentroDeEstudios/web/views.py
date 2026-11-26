# views.py - VISTAS COMPLETAS Y ORGANIZADAS
from django.template import TemplateDoesNotExist
from django.urls import reverse
from django.shortcuts import render, redirect, get_object_or_404, reverse, redirect
from django.contrib import messages
from django.views.generic import View
from django.db.models import Q, Count, Avg, Case, When, Value, IntegerField,  BooleanField
from django.contrib.auth.decorators import login_required, permission_required
from django.views.generic import FormView
from django.urls import reverse_lazy
#from web.decorators import personal_required 
from django.utils import timezone
from datetime import datetime, date, timedelta
from django.http import HttpResponse, JsonResponse, HttpResponseForbidden
from django.db import IntegrityError, transaction
from django.core.exceptions import ValidationError
from django.contrib.auth import logout,login, get_user_model
from django.views.generic.list import ListView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.views import PasswordChangeView
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from openpyxl import Workbook
from facturacion.models import HistorialContactoMora
from .services.notificaciones_service import ServicioNotificaciones
import json
# from .decorators.permissions import gestion_usuarios_requerida
from django.contrib.auth.models import Group, User, Permission
from django.contrib.auth.views import LoginView, PasswordResetView
# Importación de modelos axes
from axes.models import AccessAttempt
from axes.handlers.proxy import AxesProxyHandler

from datetime import datetime, timedelta, date
from django.db import transaction

from django.db.models import Q, Avg, Count, Sum
from django.views.decorators.http import require_POST, require_GET


from .models import (
    Alumno, Profesor, Personal, Curso, Inscripcion, 
    Certificado, HistorialCambios, BackupGenerico, Asistencia, CuotaAlumno, Examen, 
    Notificacion, TipoNotificacion, HistorialNotificacion, PasswordChangeLog, ArchivoAlumno,
    CuotaAlumno, ObservacionAlumno
)
from facturacion.models import Pago
# Importación de formularios
from .forms import (
    AltaAlumnoForm, EditarAlumnoForm, AltaProfesorForm, AltaCursoForm,
    InscripcionForm, InscripcionForm, CambiarEstadoInscripcionForm, FiltroInscripcionesForm,
    AsistenciaForm, NotificacionRapidaForm, FiltroCursoForm,
    AltaPersonalForm, PersonalForm, PersonalEditForm, PersonalFilterForm,
    CuotaAlumnoForm, AsignarPermisosForm, CambiarPasswordForm, AsignarTareaCompaneroForm, 
    InscripcionCompletaForm, BuscarAlumnoForm, EditarAlumnoForm, ArchivoAlumnoForm, ArchivoCursoForm,
    AsistenciaForm, ExamenForm, ObservacionForm, EditarPerfilProfesorForm, EditarUsuarioForm, 
)

# Importación de utilidades
from .utils import (
    crear_backup_alumno, crear_backup_generico, listar_backups, 
    restaurar_desde_backup, obtener_estadisticas_backups,   
)

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
    solo_para_gestion_usuarios,
    puede_ver_vistas_profesor, 
    puede_ver_cursos_profesor,
    profesor_solo_lectura,
    es_administrador_o_coordinador,
    obtener_profesor_usuario
)

# Para generación de PDFs
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.units import cm
import io
from .decorators import *
from .security_matrix import *

##########################################
# REGISTRO
##########################################

from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import View
from django.contrib.auth.forms import UserCreationForm
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.models import Group
from .models import Personal

class RegistroView(LoginRequiredMixin, UserPassesTestMixin, View):
    """Vista de registro solo para administradores y coordinadores"""
    
    def test_func(self):
        """Verifica si el usuario tiene permisos para registrar nuevos usuarios"""
        if self.request.user.has_perm('cursos.can_manage_staff'):
            return True
        try:
            personal = self.request.user.personal
            return personal.tipo in ['ADMINISTRATIVO', 'COORDINADOR']
        except:
            return False
    
    def handle_no_permission(self):
        messages.error(self.request, "❌ No tienes permisos para registrar nuevos usuarios.")
        return redirect('dashboard_personalizado')
    
    def get(self, request):
        form = UserCreationForm()
        return render(request, 'usuarios/registro.html', {'form': form})

    def post(self, request):
        form = UserCreationForm(request.POST)
        if form.is_valid():
            try:
                # Crear el usuario
                user = form.save()
                
                # ✅ Asignar grupo por defecto (CONSULTA)
                grupo_consulta, created = Group.objects.get_or_create(name='CONSULTA')
                user.groups.add(grupo_consulta)
                
                # ✅ Mensaje de éxito con información útil
                messages.success(request, 
                    f"✅ Usuario <strong>{user.username}</strong> creado exitosamente. "
                    f"<br>📝 <strong>Contraseña:</strong> Establecida durante el registro "
                    f"<br>👤 <strong>Grupo por defecto:</strong> CONSULTA "
                    f"<br>🔧 <strong>Siguiente paso:</strong> Asocia este usuario a un Personal existente desde la gestión de usuarios."
                )
                
                return redirect('gestion_usuarios')
                
            except Exception as e:
                messages.error(request, f"❌ Error al crear el usuario: {str(e)}")
                return render(request, 'usuarios/registro.html', {'form': form})
        
        # Si hay errores en el formulario
        messages.error(request, 
            "❌ Error en el formulario. Por favor, corrige los errores mostrados abajo."
        )
        return render(request, 'usuarios/registro.html', {'form': form})
##########################################
# LOGIN
##########################################

from django.contrib.auth.views import LoginView
from django.contrib import messages
from django.shortcuts import redirect
from axes.handlers.proxy import AxesProxyHandler

class CustomLoginView(LoginView):
    template_name = 'usuarios/login_unificado.html'
    
    def form_valid(self, form):
        """Maneja login exitoso con redirección según tipo de usuario"""
        response = super().form_valid(form)
        user = form.get_user()
        
        # Buscar tipo de persona
        from .models import Alumno, Profesor, Personal
        persona = None
        
        for model in [Alumno, Profesor, Personal]:
            try:
                persona = model.objects.get(user=user, activo=True, eliminado=False)
                break
            except model.DoesNotExist:
                continue
        
        if persona:
            # Mensaje de bienvenida personalizado
            tipo = persona.tipo_persona.capitalize()
            messages.success(self.request, f"¡Bienvenido/a {tipo} {persona.nombre}!")
            
            # Redirigir según tipo
            if isinstance(persona, Alumno):
                return redirect('dashboard_alumno')
            elif isinstance(persona, Profesor):
                return redirect('dashboard_profesor')
            elif isinstance(persona, Personal):
                if persona.tipo in ['ADMINISTRATIVO', 'COORDINADOR']:
                    return redirect('dashboard_administracion')
                else:
                    return redirect('dashboard_personal')
        
        # Si no tiene persona asociada (usuario del sistema)
        messages.info(self.request, "Bienvenido al sistema")
        return redirect('dashboard')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Agregar información sobre tipos de acceso
        context['tipos_acceso'] = [
            {'nombre': 'Alumnos', 'descripcion': 'Acceso a cursos, notas y certificados'},
            {'nombre': 'Profesores', 'descripcion': 'Gestión de cursos y alumnos'},
            {'nombre': 'Personal', 'descripcion': 'Administración del sistema'},
        ]
        return context


class CustomPasswordResetView(PasswordResetView):
    template_name = 'usuarios/resetear_contrasena.html'
    email_template_name = 'usuarios/password_reset_email.html'
    subject_template_name = 'usuarios/password_reset_subject.txt'
    
    def post(self, request, *args, **kwargs):
        email = request.POST.get('email')
        
        # Verificar si el usuario existe y tiene permisos
        try:
            user = User.objects.get(email=email)
            # Verificar si es administrador o coordinador
            if hasattr(user, 'personal') and user.personal.tipo in ['ADMINISTRATIVO', 'COORDINADOR']:
                return super().post(request, *args, **kwargs)
            else:
                messages.info(request, 
                    "📧 Si el email existe en nuestro sistema, recibirás un enlace de recuperación. "
                    "Si no lo recibes, contacta al administrador del sistema.")
                return redirect('login')
        except User.DoesNotExist:
            # Por seguridad, no revelar si el email existe o no
            messages.info(request, 
                "📧 Si el email existe en nuestro sistema, recibirás un enlace de recuperación. "
                "Si no lo recibes, contacta al administrador del sistema.")
            return redirect('login')

##########################################
# VISTAS GENERALES Y AUTENTICACIÓN
##########################################

@login_required(login_url='login')
def index(request):
    """Página principal del sistema con estadísticas"""
    context = {
        'total_alumnos': 0,
        'total_profesores': 0,
        'total_cursos': 0,
        'total_inscripciones': 0,
        'user': request.user,
    }
    
    try:
        # Alumnos no eliminados
        context['total_alumnos'] = Alumno.objects.filter(eliminado=False).count()
        
        # Profesores no eliminados  
        context['total_profesores'] = Profesor.objects.filter(eliminado=False).count()
        
        # Cursos no eliminados
        context['total_cursos'] = Curso.objects.filter(eliminado=False).count()
        
        # Inscripciones activas (si existe el modelo)
        try:
            from .models import Inscripcion
            context['total_inscripciones'] = Inscripcion.objects.filter(activo=True).count()
        except:
            context['total_inscripciones'] = 0
            
    except Exception as e:
        print(f"Error al calcular estadísticas: {e}")
    
    print(f"🚨 DEBUG INDEX - Estadísticas: {context}")
    return render(request, 'web/index.html', context)

def user_logout(request):
    """Cerrar sesión de usuario"""
    logout(request)
    messages.success(request, 'Sesión cerrada')
    return redirect('login')

    
##########################################
# VISTAS PARA GESTIÓN DE USUARIOS                         
##########################################

@login_required
@solo_para_gestion_usuarios 
def gestion_usuarios(request):
    """Vista CRÍTICA: Solo para coordinadores con permiso específico"""       # LOG INMEDIATO para ver si llegamos aquí
   
    if hasattr(request.user, 'personal_relacionado'):
        personal = request.user.personal_relacionado
        print(f"🎌 Rol del usuario: {personal.tipo}")
    
    print("=" * 60)
    
    print(f"✅ VISTA EJECUTADA por {request.user.username} (COORDINADOR)")
    # Auditoría adicional
    from .models import AuditLog
    AuditLog.objects.create(
        user=request.user.username,
        view='gestion_usuarios',
        url=request.path,
        method=request.method,
        operation_type='USER_LIST_VIEW',
        ip_address=get_client_ip(request),
        status='SUCCESS',
        response_code=200
    )
    """Vista principal de gestión de usuarios del sistema"""
    print(f"✅ Acceso concedido a {request.user.username} (COORDINADOR)")
    # Usuarios con Personal asociado
    # Usuarios con Personal asociado
    usuarios_personal = Personal.objects.filter(
        user__isnull=False, 
        eliminado=False
    ).select_related('user')
    
    # ✅ NUEVO: Usuarios sin Personal asociado
    usuarios_con_user = User.objects.filter(
        personal__isnull=False
    ).values_list('id', flat=True)
    
    usuarios_sin_personal = User.objects.exclude(
        id__in=usuarios_con_user
    ).filter(
        is_superuser=False  # Excluir superusuarios
    ).order_by('-date_joined')
    
    # Estadísticas
    total_usuarios = usuarios_personal.count() + usuarios_sin_personal.count()
    usuarios_activos = usuarios_personal.filter(user__is_active=True).count()
    usuarios_inactivos = total_usuarios - usuarios_activos
    
    context = {
        'usuarios_personal': usuarios_personal,
        'usuarios_sin_personal': usuarios_sin_personal,  # ✅ NUEVO
        'total_usuarios': total_usuarios,
        'usuarios_activos': usuarios_activos,
        'usuarios_inactivos': usuarios_inactivos,
    }
    return render(request, 'usuarios/gestion_usuarios.html', context)

@login_required
@solo_para_gestion_usuarios
def editar_usuario(request, user_id):
    """
    Vista para editar usuarios - Solo coordinadores pueden modificar username
    """
    # Obtener el usuario a editar
    usuario_a_editar = get_object_or_404(User, id=user_id)
    
    # Verificar que el usuario tiene permiso para editar
    if not request.user.has_perm('auth.can_manage_user_accounts'):
        messages.error(request, "❌ No tienes permisos para editar usuarios")
        return redirect('gestion_usuarios')
    
    # Verificar si es coordinador
    es_coordinador = False
    if hasattr(request.user, 'personal_relacionado'):
        es_coordinador = request.user.personal_relacionado.tipo == 'COORDINADOR'
    
    if request.method == 'POST':
        form = EditarUsuarioForm(
            request.POST, 
            instance=usuario_a_editar,
            usuario_editor=request.user
        )
        
        if form.is_valid():
            form.save()
            
            # Registrar en historial
            from .models import HistorialCambios
            HistorialCambios.objects.create(
                modelo='User',
                objeto_id=usuario_a_editar.id,
                accion='EDITAR',
                usuario=request.user,
                descripcion=f"Usuario {usuario_a_editar.username} editado por {request.user.username}"
            )
            
            messages.success(request, f"✅ Usuario {usuario_a_editar.username} actualizado correctamente")
            return redirect('gestion_usuarios')
    else:
        form = EditarUsuarioForm(
            instance=usuario_a_editar,
            usuario_editor=request.user
        )
    
    # Verificar a qué tipo de persona pertenece este usuario
    tipo_persona = None
    persona_id = None
    
    # Buscar si es personal
    try:
        from .models import Personal
        personal = Personal.objects.get(user=usuario_a_editar)
        tipo_persona = 'Personal'
        persona_id = personal.id
    except Personal.DoesNotExist:
        pass
    
    # Buscar si es profesor
    if not tipo_persona:
        try:
            from .models import Profesor
            profesor = Profesor.objects.get(user=usuario_a_editar)
            tipo_persona = 'Profesor'
            persona_id = profesor.id
        except Profesor.DoesNotExist:
            pass
    
    context = {
        'form': form,
        'usuario': usuario_a_editar,
        'es_coordinador': es_coordinador,
        'tipo_persona': tipo_persona,
        'persona_id': persona_id,
    }
    
    return render(request, 'usuarios/editar_usuario.html', context)

@login_required
@solo_coordinador_estricto 
def asignar_grupo_usuario(user, nombre_grupo):
    """Asigna un grupo al usuario"""
    try:
        from django.contrib.auth.models import Group
        
        # Limpiar grupos existentes
        user.groups.clear()
        
        # Obtener o crear el grupo
        grupo, creado = Group.objects.get_or_create(name=nombre_grupo)
        user.groups.add(grupo)
        
        # Si es ADMINISTRADOR, hacer staff
        if nombre_grupo == 'ADMINISTRADOR':
            user.is_staff = True
            user.save()
        
        print(f"DEBUG - Grupo '{nombre_grupo}' asignado a {user.username}")
        return True
    except Exception as e:
        print(f"ERROR en asignar_grupo_usuario: {e}")
        import traceback
        traceback.print_exc()
        return False

@login_required
@solo_coordinador_estricto 
def asignar_permisos_especiales(user, permisos):
    """Asigna permisos especiales al usuario"""
    try:
        # Limpiar permisos existentes
        user.user_permissions.clear()
        
        # Agregar nuevos permisos
        if permisos:
            # Aquí necesitas convertir los nombres de permisos a objetos Permission
            from django.contrib.auth.models import Permission
            permisos_objs = Permission.objects.filter(codename__in=permisos)
            user.user_permissions.set(permisos_objs)
            print(f"DEBUG - {len(permisos)} permisos asignados a {user.username}")
        else:
            print(f"DEBUG - No se asignaron permisos especiales a {user.username}")
            
        return True
    except Exception as e:
        print(f"ERROR en asignar_permisos_especiales: {e}")
        import traceback
        traceback.print_exc()
        return False
    
@login_required
@solo_coordinador_estricto 
def asignar_permisos(request, personal_id):
    """Asignar permisos a un usuario del personal o a un usuario sin personal asociado"""
    
    # Inicializar form como None al principio
    form = None
    user_obj = None  # Cambié el nombre para evitar confusión
    personal_obj = None
    es_usuario_sin_personal = (personal_id == 0)
    
    # Si personal_id es 0, buscar el usuario por user_id en los parámetros GET
    if es_usuario_sin_personal:
        user_id = request.GET.get('user_id')
        if not user_id:
            messages.error(request, "❌ No se proporcionó un ID de usuario.")
            return redirect('gestion_usuarios')
        
        try:
            user_obj = User.objects.get(id=user_id)
            # Crear un objeto simple para usar en el template
            personal_obj = type('Obj', (object,), {
                'id': 0,
                'user': user_obj,  # Aquí guardamos el objeto user
                'nombre_completo': f"{user_obj.first_name} {user_obj.last_name}".strip() or user_obj.username,
                'legajo': 'N/A',
                'tipo': 'SIN_ASIGNAR',
                'get_tipo_display': lambda: 'Usuario Sin Personal'
            })()
            
        except User.DoesNotExist:
            messages.error(request, "❌ Usuario no encontrado.")
            return redirect('gestion_usuarios')
    else:
        # Lógica normal para personal_id válido
        personal_obj = get_object_or_404(Personal, pk=personal_id, eliminado=False)
        
        if not personal_obj.user:
            messages.error(request, "❌ Este personal no tiene usuario del sistema.")
            return redirect('gestion_usuarios')
        
        user_obj = personal_obj.user
    
    # Manejo de POST
    if request.method == 'POST':
        form = AsignarPermisosForm(request.POST)
        if form.is_valid():
            try:
                grupo_seleccionado = form.cleaned_data['grupo']
                permisos_especiales = form.cleaned_data.get('permisos_especiales', [])
                
                print(f"DEBUG - Grupo seleccionado: {grupo_seleccionado}")
                print(f"DEBUG - Permisos especiales: {permisos_especiales}")
                print(f"DEBUG - Usuario objetivo: {user_obj.username}")
                
                # Lógica para asignar grupos y permisos
                success_grupo = asignar_grupo_usuario(user_obj, grupo_seleccionado)
                success_permisos = asignar_permisos_especiales(user_obj, permisos_especiales)
                
                # Determinar el nombre para mostrar
                if es_usuario_sin_personal:
                    nombre_display = user_obj.username
                else:
                    nombre_display = personal_obj.nombre_completo()
                
                if success_grupo and success_permisos:
                    messages.success(request, f"✅ Permisos actualizados para {nombre_display}")
                else:
                    messages.warning(request, f"⚠️ Permisos actualizados con advertencias para {nombre_display}")
                
                # Redirigir según el tipo de usuario
                if es_usuario_sin_personal:
                    return redirect(f"{request.path}?user_id={user_obj.id}")
                else:
                    return redirect('asignar_permisos', personal_id=personal_obj.id)
                
            except Exception as e:
                messages.error(request, f"❌ Error al asignar permisos: {str(e)}")
                print(f"ERROR en asignar_permisos (POST): {e}")
                import traceback
                traceback.print_exc()
    
    # Manejo de GET o cuando form no está definida
    if form is None:
        try:
            # Inicializar el formulario con datos actuales del usuario
            initial_data = {}
            
            # Obtener el grupo actual del usuario
            if user_obj.groups.exists():
                grupo_actual = user_obj.groups.first().name
                # Verificar que el grupo actual esté en nuestras opciones
                grupos_disponibles = [choice[0] for choice in AsignarPermisosForm.GRUPOS_PERMISOS]
                if grupo_actual in grupos_disponibles:
                    initial_data['grupo'] = grupo_actual
            
            # Obtener permisos especiales actuales
            permisos_actuales = []
            for permiso in user_obj.user_permissions.all():
                if permiso.codename in ['can_manage_staff', 'can_manage_courses', 'can_manage_students', 'can_view_reports', 'can_manage_payments']:
                    permisos_actuales.append(permiso.codename)
            
            initial_data['permisos_especiales'] = permisos_actuales
            form = AsignarPermisosForm(initial=initial_data)
            
        except Exception as e:
            print(f"ERROR inicializando formulario: {e}")
            import traceback
            traceback.print_exc()
            # Si hay error, crear formulario vacío
            form = AsignarPermisosForm()
            messages.error(request, f"❌ Error al cargar los permisos actuales: {str(e)}")
    
    # Crear título adecuado
    try:
        if es_usuario_sin_personal:
            titulo = f'Asignar Permisos - Usuario {user_obj.username}'
        else:
            titulo = f'Asignar Permisos - {personal_obj.nombre_completo()}'
    except:
        titulo = f'Asignar Permisos - Usuario {user_obj.username}'
    
    context = {
        'personal': personal_obj,
        'form': form,
        'titulo': titulo
    }
    return render(request, 'usuarios/asignar_permisos.html', context)

@login_required
@solo_coordinador
def cambiar_password_usuario_por_personal(request, personal_id):
    """Redirección para cambiar contraseña por personal_id"""
    try:
        personal = get_object_or_404(Personal, pk=personal_id)
        if personal.user:
            return redirect('cambiar_password_usuario', user_id=personal.user.id)
        else:
            messages.error(request, "❌ Este personal no tiene usuario del sistema.")
            return redirect('gestion_usuarios')
    except Exception as e:
        messages.error(request, f"❌ Error: {str(e)}")
        return redirect('gestion_usuarios')
    


@login_required
@solo_coordinador
def cambiar_password_usuario(request, user_id):
    """Cambiar contraseña de usuario del sistema (para coordinadores)"""
    # Obtener el usuario directamente
    usuario = get_object_or_404(User, pk=user_id)
    
    # Verificar permisos del usuario actual
    if not request.user.has_perm('auth.change_user'):
        messages.error(request, "❌ No tienes permisos para cambiar contraseñas.")
        return redirect('gestion_usuarios')
    
    # Buscar información de la persona asociada
    tipo_persona = None
    persona_id = None
    persona_nombre = None
    persona_tipo_display = None
    
    try:
        # Buscar si es personal
        from .models import Personal
        personal = Personal.objects.get(user=usuario)
        tipo_persona = 'personal'
        persona_id = personal.id
        persona_nombre = personal.nombre_completo()
        persona_tipo_display = f"Personal ({personal.get_tipo_display()})"
    except Personal.DoesNotExist:
        try:
            # Buscar si es profesor
            from .models import Profesor
            profesor = Profesor.objects.get(user=usuario)
            tipo_persona = 'profesor'
            persona_id = profesor.id
            persona_nombre = profesor.nombre_completo()
            persona_tipo_display = "Profesor"
        except Profesor.DoesNotExist:
            try:
                # Buscar si es alumno (si tienes modelo Alumno)
                from .models import Alumno
                alumno = Alumno.objects.get(user=usuario)
                tipo_persona = 'alumno'
                persona_id = alumno.id
                persona_nombre = alumno.nombre_completo()
                persona_tipo_display = "Alumno"
            except:
                tipo_persona = 'usuario_simple'
                persona_nombre = usuario.username
                persona_tipo_display = "Usuario del Sistema"
    
    if request.method == 'POST':
        form = CambiarPasswordForm(request.POST)
        if form.is_valid():
            try:
                nueva_password = form.cleaned_data['nueva_password']
                usuario.set_password(nueva_password)
                usuario.save()
                
                # Registrar en historial
                HistorialCambios.objects.create(
                    modelo='Usuario',
                    objeto_id=usuario.id,
                    accion='EDITAR',
                    usuario=request.user,
                    descripcion=f"Contraseña cambiada por {request.user.username} para usuario {usuario.username}"
                )
                
                # Auditoría
                from .models import AuditLog
                AuditLog.objects.create(
                    user=request.user.username,
                    view='cambiar_password_usuario',
                    url=request.path,
                    method=request.method,
                    operation_type='PASSWORD_CHANGE',
                    ip_address=get_client_ip(request),
                    status='SUCCESS',
                    response_code=200,
                    details=f"Contraseña cambiada para usuario: {usuario.username}"
                )
                
                messages.success(request, f"✅ Contraseña actualizada para {usuario.username}")
                return redirect('gestion_usuarios')
                
            except Exception as e:
                messages.error(request, f"❌ Error al cambiar contraseña: {str(e)}")
    else:
        form = CambiarPasswordForm()
    
    # Verificar si el usuario actual es coordinador
    es_coordinador = False
    if hasattr(request.user, 'personal_relacionado'):
        es_coordinador = request.user.personal_relacionado.tipo == 'COORDINADOR'
    
    context = {
        'usuario': usuario,
        'form': form,
        'tipo_persona': tipo_persona,
        'persona_id': persona_id,
        'persona_nombre': persona_nombre,
        'persona_tipo_display': persona_tipo_display,
        'es_coordinador': es_coordinador,
        'titulo': f'Cambiar Contraseña - {usuario.username}'
    }
    
    return render(request, 'usuarios/cambiar_contrasena.html', context)


@login_required
@solo_coordinador
def toggle_activo_usuario(request, personal_id):
    """Activar/desactivar usuario del sistema"""
    personal = get_object_or_404(Personal, pk=personal_id, eliminado=False)
    
    if not personal.user:
        messages.error(request, "❌ Este personal no tiene usuario del sistema.")
        return redirect('gestion_usuarios')
    
    try:
        personal.user.is_active = not personal.user.is_active
        personal.user.save()
        
        estado = "activado" if personal.user.is_active else "desactivado"
        messages.success(request, f"✅ Usuario '{personal.user.username}' {estado} correctamente")
        
    except Exception as e:
        messages.error(request, f"❌ Error al cambiar estado: {str(e)}")
    
    return redirect('gestion_usuarios')

@login_required
@solo_coordinador
def eliminar_usuario(request, personal_id):
    """Eliminar usuario del sistema (mantiene el personal)"""
    personal = get_object_or_404(Personal, pk=personal_id, eliminado=False)
    
    if not personal.user:
        messages.error(request, "❌ Este personal no tiene usuario del sistema.")
        return redirect('gestion_usuarios')
    
    try:
        username = personal.user.username
        personal.user.delete()
        personal.user = None
        personal.save()
        
        messages.success(request, f"✅ Usuario '{username}' eliminado correctamente")
        
    except Exception as e:
        messages.error(request, f"❌ Error al eliminar usuario: {str(e)}")
    
    return redirect('gestion_usuarios')

@login_required
@solo_coordinador
def asociar_usuario_personal(request, user_id, personal_id):
    """Asocia un usuario existente a un Personal"""
    try:
        user = User.objects.get(id=user_id)
        personal = Personal.objects.get(id=personal_id, eliminado=False)
        
        # Verificar que el personal no tenga usuario
        if personal.user:
            messages.warning(request, 
                f"⚠️ Este personal ya tiene un usuario asociado: {personal.user.username}"
            )
            return redirect('detalle_personal', personal_id=personal.id)
        
        # Asociar usuario
        personal.user = user
        personal.save()
        
        messages.success(request, 
            f"✅ Usuario <strong>{user.username}</strong> asociado exitosamente a "
            f"<strong>{personal.nombre_completo()}</strong>"
        )
        
        return redirect('gestion_usuarios')
        
    except User.DoesNotExist:
        messages.error(request, "❌ Usuario no encontrado.")
        return redirect('gestion_usuarios')
    except Personal.DoesNotExist:
        messages.error(request, "❌ Personal no encontrado.")
        return redirect('gestion_usuarios')

# @login_required
# def perfil_usuario(request):
#     """Vista del perfil del usuario logueado"""
#     try:
#         personal = Personal.objects.get(user=request.user)
#     except Personal.DoesNotExist:
#         personal = None
    
#     context = {
#         'personal': personal,
#         'user': request.user
#     }
#     return render(request, 'usuarios/perfil_usuario.html', context)
def obtener_tipo_usuario_y_redirigir(request, redirigir=True):
    """
    Función auxiliar que determina el tipo de usuario y opcionalmente redirige
    Retorna: (tipo_usuario, objeto_usuario, nombre_dashboard)
    """
    from web.models import Personal, Alumno, Profesor
    
    # 1. Verificar Personal
    try:
        personal = Personal.objects.get(user=request.user, activo=True, eliminado=False)
        if personal.tipo in ['ADMINISTRATIVO', 'COORDINADOR']:
            return ('ADMINISTRADOR', personal, 'dashboard_administracion')
        else:
            return ('PERSONAL', personal, 'dashboard_personal')
    except Personal.DoesNotExist:
        pass
    
    # 2. Verificar Alumno
    try:
        alumno = Alumno.objects.get(user=request.user, activo=True, eliminado=False)
        return ('ALUMNO', alumno, 'dashboard_alumno')
    except Alumno.DoesNotExist:
        pass
    
    # 3. Verificar Profesor
    try:
        profesor = Profesor.objects.get(user=request.user, activo=True, eliminado=False)
        return ('PROFESOR', profesor, 'dashboard_profesor')
    except Profesor.DoesNotExist:
        pass
    
    return (None, None, None)

@login_required
def perfil_administrativo(request):
    """Perfil personal para administradores y coordinadores - Mismo diseño que dashboard_personal"""
    
    print("=" * 60)
    print(f"🎯 VISTA perfil_administrativo - Usuario: {request.user.username}")
    
    # Obtener información del personal
    from web.models import Personal
    try:
        personal = Personal.objects.get(user=request.user, activo=True, eliminado=False)
    except Personal.DoesNotExist:
        print("❌ No se encontró personal asociado")
        messages.error(request, "No tienes perfil de personal asociado")
        return redirect('dashboard')
    
    # Verificar que sea administrador o coordinador
    if personal.tipo not in ['ADMINISTRATIVO', 'COORDINADOR']:
        print(f"❌ Usuario no es administrador/coordinador, es: {personal.tipo}")
        return redirect('dashboard_personal')
    
    print(f"✅ Personal administrativo encontrado: {personal.nombre_completo()}, Tipo: {personal.tipo}")
    
    # **REUTILIZAMOS LA MISMA LÓGICA DE dashboard_personal**
    # Calcular estadísticas básicas (si es secretaria - aunque aquí no aplica, mantenemos estructura)
    estadisticas = {}
    if personal.tipo == 'SECRETARIA':  # Por si acaso
        try:
            from web.models import Alumno, Curso, Inscripcion
            estadisticas['total_alumnos'] = Alumno.objects.filter(activo=True, eliminado=False).count()
            estadisticas['total_cursos_sistema'] = Curso.objects.filter(activo=True, eliminado=False).count()
            estadisticas['total_inscripciones'] = Inscripcion.objects.filter(
                activo=True, eliminado=False
            ).count()
        except Exception as e:
            print(f"⚠️ Error calculando estadísticas: {e}")
    
    # Calcular antigüedad
    from datetime import date
    if personal.fecha_ingreso:
        hoy = date.today()
        antiguedad = hoy.year - personal.fecha_ingreso.year
        if hoy.month < personal.fecha_ingreso.month or (hoy.month == personal.fecha_ingreso.month and hoy.day < personal.fecha_ingreso.day):
            antiguedad -= 1
    else:
        antiguedad = 0
    
    # Obtener cursos donde este personal es auxiliar
    cursos_asignados = 0
    cursos_asignados_lista = []
    
    try:
        from web.models import Curso
        cursos_asignados_lista = Curso.objects.filter(
            auxiliar=personal,
            activo=True,
            eliminado=False
        ).select_related('profesor')
        
        cursos_asignados = cursos_asignados_lista.count()
        print(f"📚 Cursos asignados como auxiliar: {cursos_asignados}")
    except Exception as e:
        print(f"⚠️ Error contando cursos asignados: {e}")
    
    # Buscar profesor asociado
    profesor_asociado = None
    try:
        from web.models import Profesor
        if hasattr(personal, 'profesor'):
            profesor_asociado = personal.profesor
        else:
            profesor_asociado = Profesor.objects.filter(
                user=request.user,
                activo=True,
                eliminado=False
            ).first()
    except Exception as e:
        print(f"⚠️ Error en búsqueda de profesor asociado: {e}")
    
    # Determinar qué cursos mostrar
    if personal.tipo in ['SECRETARIA', 'ADMINISTRATIVO', 'COORDINADOR']:
        cursos_mostrar = cursos_asignados
    else:
        cursos_mostrar = 0
    
    context = {
        'titulo': f'Mi Perfil - {personal.get_tipo_display()}',
        'personal': personal,
        'personal_tipo': personal.tipo,
        'estadisticas': estadisticas,
        'es_personal': True,
        'es_secretaria': personal.tipo == 'SECRETARIA',
        'es_administrativo': personal.tipo in ['SECRETARIA', 'ADMINISTRATIVO', 'COORDINADOR'],
        'es_administrador_coordinador': personal.tipo in ['ADMINISTRATIVO', 'COORDINADOR'],
        'antiguedad': antiguedad,
        'cursos_asignados': cursos_mostrar,
        'cursos_asignados_lista': cursos_asignados_lista[:5],
        'total_cursos_asignados': cursos_asignados,
        'profesor_asociado': profesor_asociado,
        'es_perfil': True,  # Nueva variable para identificar que estamos en la vista de perfil
    }
    
    print(f"📁 Cargando perfil administrativo con template personal.html")
    print(f"📁 Cursos asignados: {cursos_asignados}")
    
    return render(request, 'web/dashboard/personal.html', context)

@login_required
def perfil_usuario(request):
    """Vista del perfil del usuario logueado - Redirige según tipo"""
    print(f"🎯 VISTA perfil_usuario - Usuario: {request.user.username}")
    
    try:
        # PRIMERO: Verificar si es Personal
        from web.models import Personal
        try:
            personal = Personal.objects.get(user=request.user, activo=True, eliminado=False)
            print(f"✅ Personal encontrado: {personal.nombre_completo()}, Tipo: {personal.tipo}")
            
            # **NUEVA LÓGICA:**
            # - Administradores/Coordinadores → perfil_administrativo (mismo diseño que personal)
            # - Otro personal → dashboard_personal (ya que su perfil ES su dashboard)
            if personal.tipo in ['ADMINISTRATIVO', 'COORDINADOR']:
                print(f"🔀 Redirigiendo administrador/coordinador a perfil_administrativo")
                return redirect('perfil_administrativo')
            else:
                print(f"🔀 Redirigiendo otro personal a dashboard_personal")
                return redirect('dashboard_personal')
                
        except Personal.DoesNotExist:
            print(f"❌ No es Personal")
        
        # SEGUNDO: Verificar si es Alumno
        from web.models import Alumno
        try:
            alumno = Alumno.objects.get(user=request.user, activo=True, eliminado=False)
            print(f"✅ Alumno encontrado: {alumno.nombre_completo()}")
            print(f"🔀 Redirigiendo a dashboard_alumno")
            return redirect('dashboard_alumno')
        except Alumno.DoesNotExist:
            print(f"❌ No es Alumno")
        
        # TERCERO: Verificar si es Profesor
        from web.models import Profesor
        try:
            profesor = Profesor.objects.get(user=request.user, activo=True, eliminado=False)
            print(f"✅ Profesor encontrado: {profesor.nombre_completo()}")
            print(f"🔀 Redirigiendo a dashboard_profesor")
            return redirect('dashboard_profesor')
        except Profesor.DoesNotExist:
            print(f"❌ No es Profesor")
        
        # CUARTO: Si no tiene ningún perfil asociado
        print(f"🚨 Usuario sin perfil asociado en el sistema")
        messages.warning(request, "No tienes un perfil activo en el sistema. Contacta con administración.")
        return redirect('index')
        
    except Exception as e:
        print(f"❌ Error en perfil_usuario: {e}")
        messages.error(request, f"Error al cargar tu perfil: {e}")
        return redirect('index')

@login_required
def dashboard_redirect(request):
    """Redirige al dashboard correspondiente - Usando función auxiliar"""
    print(f"[DEBUG-REDIRECT] 🔍 Usuario: {request.user.username}")
    
    tipo_usuario, objeto_usuario, nombre_dashboard = obtener_tipo_usuario_y_redirigir(request, redirigir=False)
    
    if nombre_dashboard:
        print(f"[DEBUG-REDIRECT] ✅ {tipo_usuario} - Redirigiendo a {nombre_dashboard}")
        return redirect(nombre_dashboard)
    else:
        print(f"[DEBUG-REDIRECT] 🚨 Usuario sin perfil asociado.")
        messages.error(request, "Tu usuario no tiene un perfil activo en el sistema.")
        return redirect('login')
    
# @login_required
# def perfil_usuario(request):
#     """Vista del perfil del usuario - Redirige al dashboard correspondiente"""
#     print(f"🎯 VISTA perfil_usuario - Usuario: {request.user.username}")
    
#     try:
#         # PRIMERO: Verificar si es Personal
#         try:
#             from web.models import Personal
#             personal = Personal.objects.get(user=request.user, activo=True, eliminado=False)
#             print(f"✅ Personal encontrado: {personal.nombre_completo()}, Tipo: {personal.tipo}")
            
#             # Redirigir según tipo de personal
#             if personal.tipo in ['ADMINISTRATIVO', 'COORDINADOR']:
#                 print(f"🔀 Redirigiendo a dashboard_administracion")
#                 return redirect('dashboard_administracion')
#             else:
#                 print(f"🔀 Redirigiendo a dashboard_personal")
#                 return redirect('dashboard_personal')
                
#         except Personal.DoesNotExist:
#             print(f"❌ No es Personal")
        
#         # SEGUNDO: Verificar si es Alumno
#         try:
#             from web.models import Alumno
#             alumno = Alumno.objects.get(user=request.user, activo=True, eliminado=False)
#             print(f"✅ Alumno encontrado: {alumno.nombre_completo()}")
#             print(f"🔀 Redirigiendo a dashboard_alumno")
#             return redirect('dashboard_alumno')
#         except Alumno.DoesNotExist:
#             print(f"❌ No es Alumno")
        
#         # TERCERO: Verificar si es Profesor
#         try:
#             from web.models import Profesor
#             profesor = Profesor.objects.get(user=request.user, activo=True, eliminado=False)
#             print(f"✅ Profesor encontrado: {profesor.nombre_completo()}")
#             print(f"🔀 Redirigiendo a dashboard_profesor")
#             return redirect('dashboard_profesor')
#         except Profesor.DoesNotExist:
#             print(f"❌ No es Profesor")
        
#         # CUARTO: Si no tiene ningún perfil asociado
#         print(f"🚨 Usuario sin perfil asociado en el sistema")
#         messages.warning(request, "No tienes un perfil activo en el sistema. Contacta con administración.")
#         return redirect('index')
        
#     except Exception as e:
#         print(f"❌ Error en perfil_usuario: {e}")
#         messages.error(request, f"Error al cargar tu perfil: {e}")
#         return redirect('index')

@login_required
def dashboard_personalizado(request):
    """Dashboard personalizado según el tipo de usuario"""
    try:
        personal = Personal.objects.get(user=request.user)
        tipo_usuario = personal.tipo
    except Personal.DoesNotExist:
        personal = None
        tipo_usuario = 'CONSULTA'

    # Verificar contraseña temporal
    contraseña_temporal = request.user.check_password('temp123')

    # Inicializar contexto
    context = {
        'personal': personal,
        'tipo_usuario': tipo_usuario,
        'contraseña_temporal': contraseña_temporal,
        'total_alumnos': 0,
        'total_cursos': 0,
        'total_profesores': 0,
        'total_personal': 0,
    }

    # Agregar estadísticas específicas según el rol
    try:
        if tipo_usuario in ['ADMINISTRATIVO', 'COORDINADOR']:
            from .models import Alumno, Curso, Profesor
            context.update({
                'total_alumnos': Alumno.objects.filter(eliminado=False, activo=True).count(),
                'total_cursos': Curso.objects.filter(eliminado=False, activo=True).count(),
                'total_profesores': Profesor.objects.filter(eliminado=False, activo=True).count(),
                'total_personal': Personal.objects.filter(eliminado=False, activo=True).count(),
            })
        elif tipo_usuario == 'PROFESOR':
            # Estadísticas para profesores
            from .models import Curso
            context['mis_cursos'] = Curso.objects.filter(profesor=personal, activo=True).count()
        elif tipo_usuario == 'SECRETARIA':
            # Estadísticas para secretaría
            pass
    except Exception as e:
        # Log del error pero no romper la vista
        print(f"Error cargando estadísticas: {e}")

    return render(request, 'usuarios/dashboard.html', context)

############################## RECUPERAR PASSWORD USUARIO ###################################

class CustomPasswordChangeView(PasswordChangeView):
    success_url = '/password-change-done/'  # Cambia por tu URL

    def form_valid(self, form):
        # Guarda el cambio de contraseña
        response = super().form_valid(form)
        # Registra el cambio
        PasswordChangeLog.objects.create(
            user=self.request.user,
            ip_address=self.get_client_ip(),
            user_agent=self.request.META.get('HTTP_USER_AGENT', '')
        )
        return response

    def get_client_ip(self):
        x_forwarded_for = self.request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = self.request.META.get('REMOTE_ADDR')
        return ip

##########################################
# VISTAS PARA GESTIÓN DE ALUMNOS
##########################################

@login_required(login_url='login')
def listar_alumno(request):
    """Listar todos los alumnos activos con funcionalidad de búsqueda"""
    busqueda = request.GET.get("buscar")
    alumnos = Alumno.objects.all()
    
    # Contar eliminados para mostrar en el botón
    total_eliminados = Alumno.all_objects.filter(eliminado=True).count()
    
    # Búsqueda
    if busqueda:
        alumnos = Alumno.objects.filter(
            Q(nombre__icontains=busqueda) | 
            Q(apellido__icontains=busqueda) |
            Q(dni__icontains=busqueda) |
            Q(telefono__icontains=busqueda) |
            Q(mail__icontains=busqueda)
        ).distinct()

    context = {
        'alumnos': alumnos,
        'total_eliminados': total_eliminados,
        'busqueda_actual': busqueda or ''
    }
    return render(request, 'web/alumnos/listar_alumno.html', context)


@login_required(login_url='login')
@acceso_secretaria_requerido
def alta_alumno(request):
    """Crear nuevo alumno respetando triple coincidencia"""
    if request.method == "POST":
        form = AltaAlumnoForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                alumno = form.save(commit=False)
                # Calcular edad automáticamente si hay fecha de nacimiento
                if alumno.fecha_nacimiento:
                    from datetime import date
                    today = date.today()
                    alumno.edad = today.year - alumno.fecha_nacimiento.year - (
                        (today.month, today.day) < 
                        (alumno.fecha_nacimiento.month, alumno.fecha_nacimiento.day)
                    )
                alumno.save()
                messages.success(request, f'✅ Alumno {alumno.nombre_completo()} creado exitosamente')
                return redirect('listar_alumno')
            except Exception as e:
                messages.error(request, f'❌ Error: {e}')
        else:
            # Mostrar errores específicos
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'❌ {field}: {error}')
    else:
        form = AltaAlumnoForm()
    
    return render(request, 'web/alumnos/alta_alumno.html', {
        'alta_alumno_form': form
    })

@login_required(login_url='login')
@acceso_secretaria_requerido
def edit_alumno(request, id):
    """Editar alumno existente con gestión de archivos adicionales"""
    alumno = get_object_or_404(Alumno, pk=id)
    archivos_adicionales = alumno.archivos_adicionales.all()
    form_archivo = ArchivoAlumnoForm()
    
    if request.method == "POST":
        # Determinar qué formulario se envió
        if 'subir_archivo' in request.POST:
            # Validar límite de archivos (máximo 10)
            if archivos_adicionales.count() >= 10:
                messages.error(request, '❌ Límite alcanzado: No se pueden subir más de 10 archivos por alumno')
            else:
                form_archivo = ArchivoAlumnoForm(request.POST, request.FILES)
                if form_archivo.is_valid():
                    try:
                        archivo = form_archivo.save(commit=False)
                        archivo.alumno = alumno
                        archivo.subido_por = request.user
                        archivo.save()
                        messages.success(request, '✅ Archivo subido exitosamente')
                        return redirect('edit_alumno', id=id)
                    except Exception as e:
                        messages.error(request, f'❌ Error al subir archivo: {str(e)}')
        
        elif 'guardar_alumno' in request.POST:
            form = EditarAlumnoForm(request.POST, request.FILES, instance=alumno)
            if form.is_valid():
                try:
                    alumno_actualizado = form.save()
                    crear_backup_alumno(
                        alumno_actualizado, 
                        "Edición del alumno",
                        request.user
                    )
                    messages.success(request, '✅ Alumno actualizado exitosamente')
                    return redirect('edit_alumno', id=id)
                except Exception as e:
                    messages.error(request, f'❌ Error al actualizar alumno: {str(e)}')
    else:
        form = EditarAlumnoForm(instance=alumno)

    context = {
        'form': form,
        'alumno': alumno,
        'archivos_adicionales': archivos_adicionales,
        'form_archivo': form_archivo,
    }
    return render(request, 'web/alumnos/edit_alumno.html', context)

@login_required(login_url='login')
@gestion_completa_requerida
def confirmar_eliminar_alumno(request, id):
    """Vista de confirmación para eliminar alumno (soft delete)"""
    alumno = get_object_or_404(Alumno, pk=id)
    
    # Obtener relaciones importantes
    inscripciones_activas = alumno.inscripcion_set.filter(
        activo=True, 
        estado__in=['INSCRIPTO', 'CURSANDO']
    ).select_related('curso')
    
    # Obtener cuotas pendientes
    cuotas_pendientes = CuotaAlumno.objects.filter(
        inscripcion__alumno=alumno,
        pagada=False,
        inscripcion__activo=True
    ).select_related('inscripcion__curso')
    
    # Obtener cursos activos
    cursos_activos = alumno.cursos_activos
    
    context = {
        'alumno': alumno,
        'inscripciones_activas': inscripciones_activas,
        'cuotas_pendientes': cuotas_pendientes,
        'cursos_activos': cursos_activos,
        'total_inscripciones': inscripciones_activas.count(),
        'total_cuotas_pendientes': cuotas_pendientes.count(),
        'total_cursos_activos': cursos_activos.count(),
    }
    
    return render(request, 'web/alumnos/confirmar_eliminar_alumno.html', context)

@login_required(login_url='login')
@gestion_completa_requerida
def eliminar_archivo_alumno(request, id, archivo_id):
    """Eliminar archivo adicional de alumno"""
    alumno = get_object_or_404(Alumno, pk=id)
    archivo = get_object_or_404(ArchivoAlumno, pk=archivo_id, alumno=alumno)
    
    if request.method == "POST":
        try:
            # Eliminar el archivo físico del sistema de archivos
            archivo.archivo.delete(save=False)
            archivo.delete()
            messages.success(request, '✅ Archivo eliminado exitosamente')
        except Exception as e:
            messages.error(request, f'❌ Error al eliminar archivo: {str(e)}')
        
        return redirect('edit_alumno', id=id)
    
    return redirect('edit_alumno', id=id)


@login_required(login_url='login')
def mostrar_alumno(request, id):
    """Mostrar detalles de un alumno (incluyendo eliminados)"""
    # Usar all_objects para incluir alumnos eliminados
    alumno = get_object_or_404(Alumno.all_objects, pk=id)
    archivos_adicionales = alumno.archivos_adicionales.all()
    
    context = {
        'alumno': alumno,
        'archivos_adicionales': archivos_adicionales,
    }
    return render(request, 'web/alumnos/mostrar_alumno.html', context)

@login_required(login_url='login')
@gestion_completa_requerida
def eliminar_alumno(request, id):
    """Eliminar alumno (soft delete) - ahora con motivo"""
    alumno = get_object_or_404(Alumno, pk=id)
    
    if request.method == "POST":
        try:
            motivo = request.POST.get('motivo_eliminacion', 'Sin motivo especificado')
            
            # Soft delete - el backup es AUTOMÁTICO y maneja las inscripciones
            alumno.soft_delete(usuario=request.user)
            
            # Registrar el motivo específico en el historial
            HistorialCambios.objects.create(
                modelo='Alumno',
                objeto_id=alumno.id,
                accion='ELIMINAR',
                usuario=request.user,
                descripcion=f"Alumno {alumno.nombre_completo()} eliminado. Motivo: {motivo}"
            )
            
            messages.success(
                request, 
                f'✅ Alumno {alumno.nombre_completo()} marcado como eliminado correctamente'
            )
            
        except Exception as e:
            messages.error(request, f'❌ Error al eliminar alumno: {e}')
        
        return redirect('listar_alumno')
    
    # Si no es POST, redirigir a la confirmación
    return redirect('confirmar_eliminar_alumno', id=id)

@login_required(login_url='login')
def alumnos_eliminados(request):
    """Mostrar alumnos eliminados (soft delete)"""
    busqueda = request.GET.get("buscar")
    alumnos = Alumno.all_objects.filter(eliminado=True).order_by('-fecha_eliminacion')
    
    # Aplicar búsqueda si existe
    if busqueda:
        alumnos = alumnos.filter(
            Q(nombre__icontains=busqueda) | 
            Q(apellido__icontains=busqueda) |
            Q(dni__icontains=busqueda) |
            Q(telefono__icontains=busqueda) |
            Q(mail__icontains=busqueda)
        ).distinct()
    
    # Estadísticas
    total_eliminados = alumnos.count()
    total_alumnos = Alumno.objects.count()
    
    context = {
        'alumnos': alumnos,
        'total_eliminados': total_eliminados,
        'total_alumnos': total_alumnos,
        'titulo': 'Alumnos Eliminados',
        'busqueda_actual': busqueda or ''
    }
    return render(request, 'web/alumnos/alumnos_eliminados.html', context)

@login_required(login_url='login')
def restaurar_alumno(request, id):
    """Restaurar alumno eliminado"""
    alumno = get_object_or_404(Alumno.all_objects, pk=id, eliminado=True)
    
    if request.method == "POST":
        try:
            nombre_completo = alumno.nombre_completo()
            
            # Restaurar el alumno
            alumno.restore()
            
            # Crear backup de la restauración
            crear_backup_generico(
                instancia=alumno,
                motivo=f"Restauración solicitada por {request.user.username}",
                usuario=request.user
            )
            
            messages.success(request, f'✅ Alumno {nombre_completo} restaurado exitosamente')
            return redirect('alumnos_eliminados')
            
        except Exception as e:
            messages.error(request, f'❌ Error al restaurar alumno: {e}')
            return redirect('alumnos_eliminados')
    
    # GET - Mostrar página de confirmación
    context = {
        'alumno': alumno,
        'dias_eliminado': (timezone.now() - alumno.fecha_eliminacion).days if alumno.fecha_eliminacion else 0
    }
    return render(request, 'web/alumnos/confirmar_restaurar.html', context)


@login_required(login_url='login')
def historial_completo_alumno(request, alumno_id):
    alumno = get_object_or_404(Alumno, id=alumno_id)
    
    # Obtener todas las inscripciones, incluyendo cursos eliminados
    inscripciones = Inscripcion.objects.filter(
        alumno=alumno
    ).select_related('curso', 'curso__profesor').order_by('-fecha_inscripcion')
    
    # Estadísticas detalladas
    total_cursos = inscripciones.count()
    cursos_aprobados = inscripciones.filter(estado='APROBADO').count()
    cursos_cursando = inscripciones.filter(estado='CURSANDO').count()
    cursos_inscriptos = inscripciones.filter(estado='INSCRIPTO').count()
    cursos_reprobados = inscripciones.filter(estado='REPROBADO').count()
    cursos_abandonados = inscripciones.filter(estado='ABANDONO').count()
    
    # Promedio de notas (solo de cursos aprobados)
    promedio_notas = inscripciones.filter(
        estado='APROBADO', 
        nota_final__isnull=False
    ).aggregate(promedio=Avg('nota_final'))['promedio']
    
    context = {
        'alumno': alumno,
        'inscripciones': inscripciones,
        'total_cursos': total_cursos,
        'cursos_aprobados': cursos_aprobados,
        'cursos_cursando': cursos_cursando,
        'cursos_inscriptos': cursos_inscriptos,
        'cursos_reprobados': cursos_reprobados,
        'cursos_abandonados': cursos_abandonados,
        'promedio_notas': promedio_notas,
    }
    return render(request, 'web/alumnos/historial_completo.html', context)


##########################################
# VISTAS PARA INSCRIPCIONES DE ALUMNOS
##########################################

@login_required(login_url='login')
def inscripciones_alumno(request, alumno_id):
    """Listar TODAS las inscripciones de un alumno específico"""
    print("=" * 60)
    print(f"🎯 VISTA inscripciones_alumno - Usuario: {request.user.username}")
    print(f"🎯 Alumno ID: {alumno_id}")
    
    # Obtener el alumno
    try:
        alumno = Alumno.objects.get(pk=alumno_id)
        print(f"🎯 Alumno: {alumno.nombre_completo()}")
        print(f"🎯 Alumno activo: {alumno.activo}")
        print(f"🎯 Alumno eliminado: {alumno.eliminado if hasattr(alumno, 'eliminado') else 'No tiene campo eliminado'}")
    except Alumno.DoesNotExist:
        messages.error(request, "El alumno no existe.")
        return redirect('listar_alumno')
    
    # Verificar permisos
    tiene_permiso = False
    es_superusuario = request.user.is_superuser
    
    # 1. El propio alumno puede ver sus inscripciones
    if alumno.user == request.user:
        tiene_permiso = True
        print("✅ Tiene permiso (es el alumno)")
    
    # 2. Profesores que enseñen al alumno
    try:
        profesor = Profesor.objects.get(user=request.user, activo=True, eliminado=False)
        # Verificar si el alumno está inscrito en algún curso del profesor
        cursos_del_profesor = Curso.objects.filter(profesor=profesor, activo=True)
        if hasattr(Curso, 'eliminado'):
            cursos_del_profesor = cursos_del_profesor.filter(eliminado=False)
            
        inscripciones_del_profesor = Inscripcion.objects.filter(
            alumno=alumno,
            curso__in=cursos_del_profesor
        ).exists()
        
        if inscripciones_del_profesor:
            tiene_permiso = True
            print("✅ Tiene permiso (es profesor del alumno en algún curso)")
    except Profesor.DoesNotExist:
        pass
    
    # 3. Personal autorizado
    try:
        personal = Personal.objects.get(user=request.user, activo=True, eliminado=False)
        if personal.tipo in ['ADMINISTRATIVO', 'COORDINADOR', 'SECRETARIA']:
            tiene_permiso = True
            print(f"✅ Tiene permiso (es {personal.tipo})")
    except Personal.DoesNotExist:
        pass
    
    # 4. Superusuarios
    if es_superusuario:
        tiene_permiso = True
        print("✅ Tiene permiso (es superusuario)")
    
    if not tiene_permiso:
        messages.error(request, "No tienes permiso para ver las inscripciones de este alumno.")
        return redirect('dashboard')
    
    # ==============================================
    # OBTENER TODAS LAS INSCRIPCIONES
    # ==============================================
    
    # Obtener TODAS las inscripciones del alumno, sin importar su estado
    todas_inscripciones = Inscripcion.objects.filter(alumno=alumno).select_related(
        'curso'
    ).order_by('-fecha_inscripcion')
    
    print(f"📊 Total inscripciones encontradas: {todas_inscripciones.count()}")
    
    # Separar por estado de actividad (SOLO usando el campo 'activo', no 'eliminado')
    inscripciones_activas = todas_inscripciones.filter(activo=True)
    inscripciones_inactivas = todas_inscripciones.filter(activo=False)
    
    print(f"📊 Activas: {inscripciones_activas.count()}")
    print(f"📊 Inactivas: {inscripciones_inactivas.count()}")
    
    # Mostrar detalles para depuración
    for i, insc in enumerate(todas_inscripciones, 1):
        print(f"  {i}. ID: {insc.id}, Curso: {insc.curso.nombre}, Estado: {insc.estado}, Activo: {insc.activo}")
    
    # Para la tabla principal, mostrar todas (activas + inactivas)
    inscripciones_a_mostrar = todas_inscripciones
    
    # Calcular estadísticas
    estadisticas = {
        'total': inscripciones_a_mostrar.count(),
        'cursando': inscripciones_a_mostrar.filter(estado='CURSANDO').count(),
        'finalizado': inscripciones_a_mostrar.filter(estado='APROBADO').count(),  # En tu modelo es APROBADO, no FINALIZADO
        'inscrito': inscripciones_a_mostrar.filter(estado='INSCRIPTO').count(),
        'abandono': inscripciones_a_mostrar.filter(estado='ABANDONO').count(),
        'cancelado': inscripciones_a_mostrar.filter(estado='CANCELADO').count(),
        'reprobado': inscripciones_a_mostrar.filter(estado='REPROBADO').count(),
        'activas': inscripciones_activas.count(),
        'inactivas': inscripciones_inactivas.count(),
    }
    
    # Calcular porcentaje de aprobación exitosa
    if estadisticas['total'] > 0:
        cursos_aprobados = inscripciones_a_mostrar.filter(estado='APROBADO').count()
        porcentaje_exito = (cursos_aprobados / estadisticas['total']) * 100
    else:
        porcentaje_exito = 0
    
    # Cursos disponibles para nueva inscripción (cursos activos donde el alumno no está inscrito)
    cursos_inscritos = inscripciones_a_mostrar.values_list('curso_id', flat=True)
    cursos_disponibles = Curso.objects.filter(
        activo=True,
    ).exclude(id__in=cursos_inscritos).order_by('nombre')
    
    context = {
        'alumno': alumno,
        'inscripciones': inscripciones_a_mostrar,
        'inscripciones_activas': inscripciones_activas,
        'inscripciones_inactivas': inscripciones_inactivas,
        'estadisticas': estadisticas,
        'porcentaje_exito': round(porcentaje_exito, 2),
        'cursos_disponibles': cursos_disponibles,
        'tiene_permiso': tiene_permiso,
        'puede_crear_nueva': tiene_permiso and cursos_disponibles.exists(),
        'puede_ver_inactivas': es_superusuario or (hasattr(request.user, 'personal') and 
                                                  request.user.personal.tipo in ['ADMINISTRATIVO', 'COORDINADOR']),
        'mostrar_filtros': True,
    }
    
    print(f"📊 Total a mostrar en tabla: {inscripciones_a_mostrar.count()}")
    print(f"📚 Cursos disponibles para nueva inscripción: {cursos_disponibles.count()}")
    print("=" * 60)
    
    return render(request, 'web/alumnos/inscripciones_alumno.html', context)

@login_required(login_url='login')
def nueva_inscripcion(request, alumno_id=None):
    """Crear nueva inscripción - con búsqueda de alumnos"""
    alumno = None
    form_busqueda = BuscarAlumnoForm()
    resultados = []
    
    if alumno_id:
        alumno = get_object_or_404(Alumno, pk=alumno_id, activo=True)
    
    # Procesar búsqueda si se envió el formulario de búsqueda
    if 'buscar' in request.GET:
        form_busqueda = BuscarAlumnoForm(request.GET)
        if form_busqueda.is_valid():
            busqueda = form_busqueda.cleaned_data['busqueda']
            if busqueda:
                # Búsqueda en DNI, nombre y apellido
                resultados = Alumno.objects.filter(
                    activo=True
                ).filter(
                    Q(dni__icontains=busqueda) |
                    Q(nombre__icontains=busqueda) |
                    Q(apellido__icontains=busqueda)
                )[:10]  # Limitar a 10 resultados
    
    # Procesar selección de alumno
    if 'seleccionar_alumno' in request.POST:
        alumno_id_seleccionado = request.POST.get('alumno_id')
        if alumno_id_seleccionado:
            return redirect('nueva_inscripcion_con_alumno', alumno_id=alumno_id_seleccionado)
    
    # Procesar formulario de inscripción
    if request.method == 'POST' and 'guardar_inscripcion' in request.POST:
        form = InscripcionForm(request.POST)
        if form.is_valid():
            try:
                inscripcion = form.save(commit=False)
                inscripcion.alumno = alumno
                inscripcion.creado_por = request.user
                inscripcion.save()
                
                # Registrar en historial
                HistorialCambios.objects.create(
                    modelo='Inscripcion',
                    objeto_id=inscripcion.id,
                    accion='CREAR',
                    usuario=request.user,
                    descripcion=f"Nueva inscripción: {inscripcion.alumno} en {inscripcion.curso}"
                )
                
                messages.success(request, f'✅ {inscripcion.alumno} inscrito en {inscripcion.curso} exitosamente')
                return redirect('inscripciones_alumno', alumno_id=alumno.id)
                    
            except IntegrityError:
                messages.error(request, '❌ El alumno ya está inscrito en este curso')
            except Exception as e:
                messages.error(request, f'❌ Error al crear inscripción: {e}')
    else:
        form = InscripcionForm()
    
    context = {
        'alumno': alumno,
        'form': form,
        'form_busqueda': form_busqueda,
        'resultados': resultados,
        'modo_busqueda': alumno_id is None,
    }
    return render(request, 'web/inscripciones/nueva_inscripcion.html', context)

@login_required(login_url='login')
def nueva_inscripcion_con_alumno(request, alumno_id):
    """Vista específica para crear inscripción con alumno ya seleccionado"""
    try:
        alumno = get_object_or_404(Alumno, pk=alumno_id, activo=True)
        print(f"Alumno encontrado: {alumno.nombre_completo()}")  # Para debug
        
        if request.method == 'POST':
            form = InscripcionForm(request.POST)
            if form.is_valid():
                try:
                    inscripcion = form.save(commit=False)
                    inscripcion.alumno = alumno
                    inscripcion.creado_por = request.user
                    inscripcion.save()
                    
                    messages.success(request, f'✅ {inscripcion.alumno} inscrito en {inscripcion.curso} exitosamente')
                    return redirect('inscripciones_alumno', alumno_id=alumno.id)
                        
                except IntegrityError:
                    messages.error(request, '❌ El alumno ya está inscrito en este curso')
                except Exception as e:
                    messages.error(request, f'❌ Error al crear inscripción: {e}')
        else:
            form = InscripcionForm()
        
        context = {
            'alumno': alumno,  # ← Asegúrate de que esta línea esté presente
            'form': form,
        }
        return render(request, 'web/inscripciones/nueva_inscripcion.html', context)
        
    except Exception as e:
        print(f"Error en nueva_inscripcion_con_alumno: {e}")
        messages.error(request, f'Error al cargar el alumno: {e}')
        return redirect('listar_inscripciones')  # Redirige a una página segura


@login_required(login_url='login')
def editar_inscripcion(request, inscripcion_id):
    """Editar una inscripción existente"""
    inscripcion = get_object_or_404(Inscripcion, pk=inscripcion_id, activo=True)
    
    if request.method == 'POST':
        form = InscripcionForm(request.POST, instance=inscripcion)
        if form.is_valid():
            try:
                form.save()
                
                # Registrar en historial
                HistorialCambios.objects.create(
                    modelo='Inscripcion',
                    objeto_id=inscripcion.id,
                    accion='EDITAR',
                    usuario=request.user,
                    descripcion=f"Inscripción actualizada: {inscripcion}"
                )
                
                messages.success(request, '✅ Inscripción actualizada exitosamente')
                return redirect('inscripciones_alumno', alumno_id=inscripcion.alumno.id)
                
            except Exception as e:
                messages.error(request, f'❌ Error al actualizar inscripción: {e}')
    else:
        form = InscripcionForm(instance=inscripcion)
    
    context = {
        'inscripcion': inscripcion,
        'form': form,
    }
    return render(request, 'web/alumnos/editar_inscripcion.html', context)


from django.db.models import Sum

@login_required(login_url='login')
def cambiar_estado_inscripcion(request, inscripcion_id):
    """Cambiar el estado de una inscripción - Solo para usuarios autorizados"""
    print("=" * 60)
    print(f"🎯 VISTA cambiar_estado_inscripcion - Usuario: {request.user.username}")
    print(f"🎯 Inscripción ID: {inscripcion_id}")
    
    try:
        # Obtener la inscripción sin ningún filtro inicial
        inscripcion = Inscripcion.objects.get(pk=inscripcion_id)
        print(f"✅ Inscripción encontrada: {inscripcion}")
        print(f"🎯 Activo: {inscripcion.activo}")
        print(f"🎯 Estado: {inscripcion.estado}")
        
    except Inscripcion.DoesNotExist:
        print(f"❌ Inscripción con ID {inscripcion_id} NO EXISTE en la base de datos")
        messages.error(request, 'La inscripción no existe.')
        
        # Redirigir según el tipo de usuario
        try:
            Profesor.objects.get(user=request.user, activo=True, eliminado=False)
            return redirect('mis_cursos_profesor')
        except Profesor.DoesNotExist:
            pass
        
        try:
            Personal.objects.get(user=request.user, activo=True, eliminado=False)
            return redirect('dashboard_personal')
        except Personal.DoesNotExist:
            pass
        
        return redirect('dashboard')
    
    # ==============================================
    # VERIFICACIÓN DE PERMISOS
    # ==============================================
    tiene_permiso = False
    es_superusuario = request.user.is_superuser
    
    # 1. Verificar si es profesor del curso
    try:
        profesor = Profesor.objects.get(user=request.user, activo=True, eliminado=False)
        if inscripcion.curso.profesor == profesor:
            tiene_permiso = True
            print("✅ Tiene permiso (es profesor del curso)")
    except Profesor.DoesNotExist:
        pass
    
    # 2. Verificar si es auxiliar del curso
    try:
        if inscripcion.curso.auxiliar and inscripcion.curso.auxiliar.user == request.user:
            tiene_permiso = True
            print("✅ Tiene permiso (es auxiliar del curso)")
    except:
        pass
    
    # 3. Verificar si es personal autorizado
    try:
        personal = Personal.objects.get(user=request.user, activo=True, eliminado=False)
        if personal.tipo in ['ADMINISTRATIVO', 'COORDINADOR', 'SECRETARIA']:
            tiene_permiso = True
            print(f"✅ Tiene permiso (es {personal.tipo})")
    except Personal.DoesNotExist:
        pass
    
    # 4. Superusuarios siempre tienen permiso
    if es_superusuario:
        tiene_permiso = True
        print("✅ Tiene permiso (es superusuario)")
    
    # Si no tiene permiso, redirigir
    if not tiene_permiso:
        print("❌ USUARIO NO AUTORIZADO para cambiar estado de inscripción")
        messages.error(
            request, 
            "No tienes permiso para cambiar el estado de esta inscripción."
        )
        return redirect('inscripciones_alumno', alumno_id=inscripcion.alumno.id)
    
    # ==============================================
    # LÓGICA DEL FORMULARIO
    # ==============================================
    
    # Si la inscripción está inactiva, mostrar advertencia
    if not inscripcion.activo:
        messages.warning(
            request, 
            'Esta inscripción está inactiva. Al cambiar el estado, se reactivará automáticamente.'
        )
    
    if request.method == 'POST':
        form = CambiarEstadoInscripcionForm(request.POST, instance=inscripcion)
        if form.is_valid():
            try:
                # Guardar el estado anterior
                estado_anterior = inscripcion.estado
                estado_nuevo = form.cleaned_data['estado']
                
                # Al cambiar estado, reactivar la inscripción automáticamente
                inscripcion.activo = True
                inscripcion.fecha_modificacion = timezone.now()
                inscripcion.modificado_por = request.user
                
                # Guardar los cambios
                inscripcion = form.save(commit=False)
                inscripcion.save()
                
                # Registrar en historial
                HistorialCambios.objects.create(
                    modelo='Inscripcion',
                    objeto_id=inscripcion.id,
                    accion='EDITAR',
                    usuario=request.user,
                    descripcion=f"Estado de inscripción cambiado: {estado_anterior} → {estado_nuevo}. Alumno: {inscripcion.alumno.nombre_completo()}, Curso: {inscripcion.curso.nombre}"
                )
                
                print(f"✅ Estado cambiado: {estado_anterior} → {estado_nuevo}")
                print(f"✅ Inscripción reactivada: {inscripcion.activo}")
                
                # Mensaje de éxito
                messages.success(request, f'✅ Estado actualizado a: {inscripcion.get_estado_display()}')
                
                # Redirigir a la página del alumno
                return redirect('inscripciones_alumno', alumno_id=inscripcion.alumno.id)
                
            except Exception as e:
                print(f"❌ Error al cambiar estado: {e}")
                messages.error(request, f'❌ Error al cambiar estado: {str(e)}')
        else:
            print(f"❌ Formulario inválido: {form.errors}")
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'Error en {field}: {error}')
    else:
        form = CambiarEstadoInscripcionForm(instance=inscripcion)
    
    context = {
        'inscripcion': inscripcion,
        'form': form,
        'alumno': inscripcion.alumno,
        'curso': inscripcion.curso,
        'puede_ver_detalles': True,
    }
    
    print("=" * 60)
    return render(request, 'web/alumnos/cambiar_estado_inscripcion.html', context)


@login_required(login_url='login')
def eliminar_inscripcion(request, inscripcion_id):
    """Eliminar (soft delete) una inscripción"""
    inscripcion = get_object_or_404(Inscripcion, pk=inscripcion_id, activo=True)
    alumno_id = inscripcion.alumno.id
    
    if request.method == 'POST':
        try:
            inscripcion.soft_delete(usuario=request.user)
            messages.success(request, '✅ Inscripción eliminada exitosamente')
        except Exception as e:
            messages.error(request, f'❌ Error al eliminar inscripción: {e}')
    
    return redirect('inscripciones_alumno', alumno_id=alumno_id)

@login_required(login_url='login')
def listar_inscripciones(request):
    """Lista general de todas las inscripciones (activas e inactivas)"""
    form_filtro = FiltroInscripcionesForm(request.GET or None)
    
    # Mostrar TODAS las inscripciones no eliminadas
    inscripciones = Inscripcion.objects.filter(eliminado=False)
    
    if form_filtro.is_valid():
        estado = form_filtro.cleaned_data.get('estado')
        curso = form_filtro.cleaned_data.get('curso')
        fecha_desde = form_filtro.cleaned_data.get('fecha_desde')
        fecha_hasta = form_filtro.cleaned_data.get('fecha_hasta')
        mostrar_inactivas = form_filtro.cleaned_data.get('mostrar_inactivas', False)
        
        if estado:
            inscripciones = inscripciones.filter(estado=estado)
        if curso:
            inscripciones = inscripciones.filter(curso=curso)
        if fecha_desde:
            inscripciones = inscripciones.filter(fecha_inscripcion__gte=fecha_desde)
        if fecha_hasta:
            inscripciones = inscripciones.filter(fecha_inscripcion__lte=fecha_hasta)
        
        # Filtrar por activas si no se selecciona mostrar inactivas
        if not mostrar_inactivas:
            inscripciones = inscripciones.filter(activo=True)
    
    # Separar activas e inactivas para estadísticas
    inscripciones_activas = inscripciones.filter(activo=True)
    inscripciones_inactivas = inscripciones.filter(activo=False)
    
    # Estadísticas generales
    total_inscripciones = inscripciones.count()
    total_activas = inscripciones_activas.count()
    total_inactivas = inscripciones_inactivas.count()
    
    # Estadísticas por estado (solo activas)
    aprobados = inscripciones_activas.filter(estado='FINALIZADO').count()
    cursando = inscripciones_activas.filter(estado='CURSANDO').count()
    inscriptos = inscripciones_activas.filter(estado='INSCRIPTO').count()
    abandonos = inscripciones_activas.filter(estado='ABANDONO').count()
    
    context = {
        'inscripciones': inscripciones.order_by('-fecha_inscripcion'),
        'form_filtro': form_filtro,
        'total_inscripciones': total_inscripciones,
        'total_activas': total_activas,
        'total_inactivas': total_inactivas,
        'aprobados': aprobados,
        'cursando': cursando,
        'inscriptos': inscriptos,
        'abandonos': abandonos,
    }
    return render(request, 'web/inscripciones/listar_inscripciones.html', context)

@login_required(login_url='login')
def inscripciones_alumno(request, alumno_id):
    """Listar TODAS las inscripciones de un alumno específico"""
    print("=" * 60)
    print(f"🎯 VISTA inscripciones_alumno - Usuario: {request.user.username}")
    print(f"🎯 Alumno ID: {alumno_id}")
    
    # Obtener el alumno (aunque esté inactivo o eliminado)
    try:
        alumno = Alumno.objects.get(pk=alumno_id)
        print(f"🎯 Alumno: {alumno.nombre_completo()}")
        print(f"🎯 Alumno activo: {alumno.activo}")
        print(f"🎯 Alumno eliminado: {alumno.eliminado}")
    except Alumno.DoesNotExist:
        messages.error(request, "El alumno no existe.")
        return redirect('listar_alumno')
    
    # Verificar permisos
    tiene_permiso = False
    es_superusuario = request.user.is_superuser
    
    # 1. El propio alumno puede ver sus inscripciones
    if alumno.user == request.user:
        tiene_permiso = True
        print("✅ Tiene permiso (es el alumno)")
    
    # 2. Profesores que enseñen al alumno
    try:
        profesor = Profesor.objects.get(user=request.user, activo=True, eliminado=False)
        # Verificar si el alumno está inscrito en algún curso del profesor
        cursos_del_profesor = Curso.objects.filter(profesor=profesor, activo=True, eliminado=False)
        inscripciones_del_profesor = Inscripcion.objects.filter(
            alumno=alumno,
            curso__in=cursos_del_profesor
        ).exists()
        
        if inscripciones_del_profesor:
            tiene_permiso = True
            print("✅ Tiene permiso (es profesor del alumno en algún curso)")
    except Profesor.DoesNotExist:
        pass
    
    # 3. Personal autorizado
    try:
        personal = Personal.objects.get(user=request.user, activo=True, eliminado=False)
        if personal.tipo in ['ADMINISTRATIVO', 'COORDINADOR', 'SECRETARIA']:
            tiene_permiso = True
            print(f"✅ Tiene permiso (es {personal.tipo})")
    except Personal.DoesNotExist:
        pass
    
    # 4. Superusuarios
    if es_superusuario:
        tiene_permiso = True
        print("✅ Tiene permiso (es superusuario)")
    
    if not tiene_permiso:
        messages.error(request, "No tienes permiso para ver las inscripciones de este alumno.")
        return redirect('dashboard')
    
    # ==============================================
    # OBTENER TODAS LAS INSCRIPCIONES
    # ==============================================
    
    # Obtener TODAS las inscripciones del alumno, sin importar su estado
    todas_inscripciones = Inscripcion.objects.filter(alumno=alumno).select_related(
        'curso'
    ).order_by('-fecha_inscripcion')
    
    print(f"📊 Total inscripciones encontradas: {todas_inscripciones.count()}")
    
    # Separar por estado de actividad
    inscripciones_activas = todas_inscripciones.filter(activo=True, eliminado=False)
    inscripciones_inactivas = todas_inscripciones.filter(activo=False, eliminado=False)
    inscripciones_eliminadas = todas_inscripciones.filter(eliminado=True)
    
    print(f"📊 Activas: {inscripciones_activas.count()}")
    print(f"📊 Inactivas: {inscripciones_inactivas.count()}")
    print(f"📊 Eliminadas: {inscripciones_eliminadas.count()}")
    
    # Para la tabla principal, mostrar activas + inactivas (pero no eliminadas)
    inscripciones_a_mostrar = todas_inscripciones.filter(eliminado=False)
    
    # Mostrar detalles para depuración
    for i, insc in enumerate(todas_inscripciones, 1):
        print(f"  {i}. ID: {insc.id}, Curso: {insc.curso.nombre}, Estado: {insc.estado}, Activo: {insc.activo}, Eliminado: {insc.eliminado}")
    
    # Calcular estadísticas
    estadisticas = {
        'total': inscripciones_a_mostrar.count(),
        'cursando': inscripciones_a_mostrar.filter(estado='CURSANDO').count(),
        'finalizado': inscripciones_a_mostrar.filter(estado='FINALIZADO').count(),
        'inscrito': inscripciones_a_mostrar.filter(estado='INSCRIPTO').count(),
        'abandono': inscripciones_a_mostrar.filter(estado='ABANDONO').count(),
        'inactivo': inscripciones_a_mostrar.filter(estado='INACTIVO').count(),
        'activas': inscripciones_activas.count(),
        'inactivas': inscripciones_inactivas.count(),
    }
    
    # Calcular porcentaje de finalización exitosa
    if estadisticas['total'] > 0:
        cursos_finalizados = inscripciones_a_mostrar.filter(estado='FINALIZADO').count()
        porcentaje_exito = (cursos_finalizados / estadisticas['total']) * 100
    else:
        porcentaje_exito = 0
    
    # Cursos disponibles para nueva inscripción (cursos activos donde el alumno no está inscrito)
    cursos_inscritos = inscripciones_a_mostrar.values_list('curso_id', flat=True)
    cursos_disponibles = Curso.objects.filter(
        activo=True,
        eliminado=False,
    ).exclude(id__in=cursos_inscritos).order_by('nombre')
    
    context = {
        'alumno': alumno,
        'inscripciones': inscripciones_a_mostrar,
        'inscripciones_activas': inscripciones_activas,
        'inscripciones_inactivas': inscripciones_inactivas,
        'inscripciones_eliminadas': inscripciones_eliminadas,
        'estadisticas': estadisticas,
        'porcentaje_exito': round(porcentaje_exito, 2),
        'cursos_disponibles': cursos_disponibles,
        'tiene_permiso': tiene_permiso,
        'puede_crear_nueva': tiene_permiso and cursos_disponibles.exists(),
        'puede_ver_eliminadas': es_superusuario or (hasattr(request.user, 'personal') and 
                                                    request.user.personal.tipo in ['ADMINISTRATIVO', 'COORDINADOR']),
        'mostrar_filtros': True,
    }
    
    print(f"📊 Total a mostrar en tabla: {inscripciones_a_mostrar.count()}")
    print(f"📚 Cursos disponibles para nueva inscripción: {cursos_disponibles.count()}")
    print("=" * 60)
    
    return render(request, 'web/alumnos/inscripciones_alumno.html', context)

@login_required(login_url='login')
def inscripciones_eliminadas(request):
    """Lista de inscripciones eliminadas (soft delete)"""
    inscripciones = Inscripcion.objects.filter(activo=False)
    
    context = {
        'inscripciones': inscripciones,
    }
    return render(request, 'web/inscripciones/inscripciones_eliminadas.html', context)

@login_required(login_url='login')
def restaurar_inscripcion(request, inscripcion_id):
    """Restaurar una inscripción eliminada"""
    inscripcion = get_object_or_404(Inscripcion, pk=inscripcion_id, activo=False)
    
    if request.method == 'POST':
        try:
            inscripcion.activo = True
            inscripcion.save()
            
            # Registrar en historial
            HistorialCambios.objects.create(
                modelo='Inscripcion',
                objeto_id=inscripcion.id,
                accion='RESTAURAR',
                usuario=request.user,
                descripcion=f"Inscripción restaurada: {inscripcion}"
            )
            
            messages.success(request, '✅ Inscripción restaurada exitosamente')
        except Exception as e:
            messages.error(request, f'❌ Error al restaurar inscripción: {e}')
    
    return redirect('inscripciones_eliminadas')

@login_required(login_url='login')
def detalle_inscripcion(request, inscripcion_id):
    """Página de detalle completo de una inscripción"""
    try:
        inscripcion = get_object_or_404(Inscripcion, pk=inscripcion_id, activo=True)
        
        # Obtener historial de cambios
        historial = HistorialCambios.objects.filter(
            modelo='Inscripcion', 
            objeto_id=inscripcion_id
        ).order_by('-fecha')
        
        # Obtener exámenes
        examenes = Examen.objects.filter(inscripcion=inscripcion).order_by('fecha')
        
        # Calcular promedio
        promedio = None
        promedio_str = "N/A"
        if examenes.exists():
            resultado = examenes.aggregate(Avg('nota'))
            promedio = resultado['nota__avg']
            if promedio is not None:
                promedio_str = f"{promedio:.2f}"
        
        context = {
            'inscripcion': inscripcion,
            'historial': historial,
            'examenes': examenes,
            'promedio': promedio_str,
            'total_examenes': examenes.count(),
        }
        
        return render(request, 'web/inscripciones/detalle_inscripcion.html', context)
        
    except Exception as e:
        messages.error(request, f'Error al cargar los detalles: {str(e)}')
        # Redirigir a la página del alumno
        return redirect('inscripciones_alumno', alumno_id=inscripcion.alumno.id)
    

@login_required(login_url='login')
def buscar_alumnos_ajax(request):
    """Vista AJAX para buscar alumnos"""
    query = request.GET.get('q', '')
    alumnos = []
    
    if query:
        alumnos = Alumno.objects.filter(
            activo=True
        ).filter(
            Q(dni__icontains=query) |
            Q(nombre__icontains=query) |
            Q(apellido__icontains=query)
        )[:10]
    
    data = []
    for alumno in alumnos:
        data.append({
            'id': alumno.id,
            'nombre_completo': alumno.nombre_completo(),
            'dni': alumno.dni,
            'email': alumno.email or 'No especificado',
            'telefono': alumno.telefono or 'No especificado',
        })
    
    return JsonResponse({'alumnos': data})

@login_required(login_url='login')
def modal_detalle_alumno(request, alumno_id):
    """Vista segura para modal de alumno - sin enlaces problemáticos"""
    try:
        alumno = get_object_or_404(Alumno, pk=alumno_id, activo=True)
        
        # Importamos reverse para generar las URLs
        from django.urls import reverse
        
        # Generamos las URLs
        url_ficha_completa = reverse('mostrar_alumno', args=[alumno.id])
        url_nueva_inscripcion = reverse('nueva_inscripcion_con_alumno', args=[alumno.id])
        
        modal_html = f"""
        <div class="modal fade" id="modalAlumnoDetalle" tabindex="-1">
            <div class="modal-dialog modal-lg">
                <div class="modal-content">
                    <div class="modal-header bg-primary text-white">
                        <h5 class="modal-title">
                            <i class="fas fa-user me-2"></i>{alumno.nombre_completo()}
                        </h5>
                        <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body">
                        <div class="row">
                            <div class="col-md-4 text-center">
        """
        
        if alumno.foto:
            modal_html += f'<img src="{alumno.foto.url}" alt="{alumno.nombre_completo()}" class="img-fluid rounded-circle mb-3" style="max-width: 150px;">'
        else:
            modal_html += '''
                                <div class="bg-light rounded-circle d-flex align-items-center justify-content-center mx-auto mb-3" 
                                     style="width: 150px; height: 150px;">
                                    <i class="fas fa-user fa-3x text-muted"></i>
                                </div>
            '''
        
        modal_html += f"""
                            </div>
                            <div class="col-md-8">
                                <table class="table table-sm">
                                    <tr><th>DNI:</th><td>{alumno.dni}</td></tr>
                                    <tr><th>Email:</th><td>{alumno.mail or 'No especificado'}</td></tr>
                                    <tr><th>Teléfono:</th><td>{alumno.telefono or 'No especificado'}</td></tr>
                                    <tr><th>Teléfono Contacto:</th><td>{alumno.telefono_contacto or 'No especificado'}</td></tr>
                                    <tr><th>Dirección:</th><td>{alumno.direccion or 'No especificada'}</td></tr>
                                    <tr><th>Fecha Nacimiento:</th><td>{alumno.fecha_nacimiento.strftime('%d/%m/%Y') if alumno.fecha_nacimiento else 'No especificada'}</td></tr>
                                    <tr><th>Edad:</th><td>{alumno.edad or alumno.calcular_edad() or 'No especificada'} años</td></tr>
                                    <tr><th>Sexo:</th><td>{alumno.get_sexo_display() if alumno.sexo else 'No especificado'}</td></tr>
        """
        
        # Mostrar el curso asignado si existe
        if alumno.cursoAlumno:
            modal_html += f"""
                                    <tr><th>Curso Asignado:</th><td>{alumno.cursoAlumno.nombre}</td></tr>
            """
        
        modal_html += f"""
                                </table>
                            </div>
                        </div>
                        
                        <!-- Estadísticas de inscripciones -->
                        <div class="row mt-4">
                            <div class="col-12">
                                <h6><i class="fas fa-chart-bar me-2"></i>Estadísticas de Inscripciones</h6>
                                <div class="row text-center">
                                    <div class="col-md-3 mb-2">
                                        <div class="card bg-light">
                                            <div class="card-body py-2">
                                                <h6 class="card-title mb-0">Total</h6>
                                                <p class="card-text h4 mb-0">{alumno.total_inscripciones}</p>
                                            </div>
                                        </div>
                                    </div>
                                    <div class="col-md-3 mb-2">
                                        <div class="card bg-success text-white">
                                            <div class="card-body py-2">
                                                <h6 class="card-title mb-0">Aprobados</h6>
                                                <p class="card-text h4 mb-0">{alumno.inscripciones_aprobadas}</p>
                                            </div>
                                        </div>
                                    </div>
                                    <div class="col-md-3 mb-2">
                                        <div class="card bg-warning text-dark">
                                            <div class="card-body py-2">
                                                <h6 class="card-title mb-0">Cursando</h6>
                                                <p class="card-text h4 mb-0">{alumno.inscripciones_cursando}</p>
                                            </div>
                                        </div>
                                    </div>
                                    <div class="col-md-3 mb-2">
                                        <div class="card bg-danger text-white">
                                            <div class="card-body py-2">
                                                <h6 class="card-title mb-0">Reprobados</h6>
                                                <p class="card-text h4 mb-0">{alumno.inscripciones_reprobadas}</p>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
        """
        
        modal_html += f"""
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cerrar</button>
                        <a href="{url_ficha_completa}" class="btn btn-primary">Ver Ficha Completa</a>
                        <a href="{url_nueva_inscripcion}" class="btn btn-success">Inscribir en Curso</a>
                    </div>
                </div>
            </div>
        </div>
        """
        
        return HttpResponse(modal_html)
        
    except Exception as e:
        return HttpResponse(f"""
        <div class="modal fade" id="modalAlumnoDetalle" tabindex="-1">
            <div class="modal-dialog">
                <div class="modal-content">
                    <div class="modal-header bg-danger text-white">
                        <h5 class="modal-title">Error</h5>
                        <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body">
                        <p>Error al cargar información del alumno: {str(e)}</p>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cerrar</button>
                    </div>
                </div>
            </div>
        </div>
        """)
        

@login_required(login_url='login')
def obtener_fechas_curso(request, curso_id):
    """Obtener fechas de inicio y fin de un curso para AJAX"""
    try:
        print(f"🔍 Solicitando fechas para curso ID: {curso_id}")
        
        curso = get_object_or_404(Curso, pk=curso_id)
        print(f"📚 Curso encontrado: {curso.nombre}")
        
        # Verificar que el curso tenga los campos de fecha
        fecha_inicio = curso.fecha_inicio.strftime('%Y-%m-%d') if curso.fecha_inicio else ''
        fecha_fin = curso.fecha_fin.strftime('%Y-%m-%d') if curso.fecha_fin else ''
        
        print(f"📅 Fecha inicio: {fecha_inicio}, Fecha fin: {fecha_fin}")
        
        response_data = {
            'fecha_inicio': fecha_inicio,
            'fecha_fin': fecha_fin,
        }
        
        print(f"📤 Enviando respuesta: {response_data}")
        return JsonResponse(response_data)
        
    except Exception as e:
        print(f"❌ Error en obtener_fechas_curso: {e}")
        return JsonResponse({'error': str(e)}, status=500)
    
##########################################
# VISTAS PARA GESTIÓN DE PROFESORES
##########################################


@login_required(login_url='login')
@gestion_completa_requerida
def alta_profesor(request):
    """Crear nuevo profesor con manejo de archivos y usuario opcional"""
    if request.method == "POST":
        form = AltaProfesorForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                profesor = form.save()
                
                # Verificar si se creó usuario y mostrar la contraseña
                if hasattr(profesor.user, '_password_temp'):
                    password_temp = profesor.user._password_temp
                    messages.success(request, 
                        f'✅ Profesor {profesor.nombre_completo()} creado exitosamente.<br>'
                        f'✅ Usuario creado: <strong>{profesor.user.username}</strong><br>'
                        f'✅ Contraseña temporal: <strong>{password_temp}</strong><br>'
                        f'<small>Comparta esta información con el profesor de forma segura.</small>',
                        extra_tags='safe'
                    )
                else:
                    messages.success(request, 
                        f'✅ Profesor {profesor.nombre_completo()} creado exitosamente'
                    )
                
                return redirect('listar_profesores')
            except Exception as e:
                messages.error(request, f'❌ Error: {str(e)}')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'❌ {field}: {error}')
    else:
        form = AltaProfesorForm()
    
    return render(request, 'web/profesores/alta_profesor.html', {
        'alta_profesor_form': form,
        'titulo': 'Nuevo Profesor'
    })
    
    
@login_required(login_url='login')
def listar_profesores(request):
    """Listar profesores activos"""
    busqueda = request.GET.get('buscar', '')
    
    # Filtrar solo activos y no eliminados
    profesores = Profesor.objects.filter(eliminado=False, activo=True).order_by('apellido', 'nombre')
    
    if busqueda:
        profesores = profesores.filter(
            Q(nombre__icontains=busqueda) | 
            Q(apellido__icontains=busqueda) |
            Q(dni__icontains=busqueda) |
            Q(telefono__icontains=busqueda) |
            Q(mail__icontains=busqueda) |
            Q(cuit__icontains=busqueda)
        ).distinct()
    
    # Estadísticas
    total_activos = profesores.count()
    total_eliminados = Profesor.objects.filter(eliminado=True).count()
    
    context = {
        'profesores': profesores,
        'total_activos': total_activos,
        'total_eliminados': total_eliminados,
        'busqueda_actual': busqueda
    }
    return render(request, 'web/profesores/listar_profesores.html', context)


# views.py
@login_required(login_url='login')
def mostrar_profesor(request, id):
    """Mostrar detalles de un profesor"""
    profesor = get_object_or_404(Profesor, pk=id)
    
    # Verificar si viene desde la lista de eliminados
    from_eliminados = request.GET.get('from_eliminados', False)
    
    # Calcular edad si tiene fecha de nacimiento
    edad = None
    if profesor.fecha_nacimiento:
        hoy = date.today()
        edad = hoy.year - profesor.fecha_nacimiento.year - (
            (hoy.month, hoy.day) < (profesor.fecha_nacimiento.month, profesor.fecha_nacimiento.day)
        )
    
    context = {
        'profesor': profesor,
        'edad': edad,
        'from_eliminados': from_eliminados
    }
    return render(request, 'web/profesores/mostrar_profesor.html', context)


@login_required(login_url='login')
@gestion_completa_requerida
def editar_profesor(request, id):
    """Editar profesor existente con gestión de usuario"""
    profesor = get_object_or_404(Profesor, pk=id, eliminado=False)
    
    # Verificar si el usuario actual es coordinador
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
    
    if request.method == "POST":
        accion_usuario = request.POST.get('accion_usuario')
        
        # ==========================================
        # PROCESAR ACCIONES DE USUARIO (sin validar el formulario completo)
        # ==========================================
        if accion_usuario:
            if accion_usuario == 'desactivar' and profesor.user:
                profesor.user.is_active = False
                profesor.user.save()
                profesor.puede_acceder_sistema = False
                profesor.save()
                
                from .models import HistorialCambios
                HistorialCambios.objects.create(
                    modelo='Profesor',
                    objeto_id=profesor.id,
                    accion='EDITAR',
                    usuario=request.user,
                    descripcion=f"Usuario {profesor.user.username} desactivado para el profesor {profesor.nombre_completo()}"
                )
                
                messages.warning(request, f'⚠️ Usuario {profesor.user.username} desactivado')
                return redirect('editar_profesor', id=profesor.id)
                
            elif accion_usuario == 'reactivar' and profesor.user:
                profesor.user.is_active = True
                profesor.user.save()
                profesor.puede_acceder_sistema = True
                profesor.save()
                
                from .models import HistorialCambios
                HistorialCambios.objects.create(
                    modelo='Profesor',
                    objeto_id=profesor.id,
                    accion='EDITAR',
                    usuario=request.user,
                    descripcion=f"Usuario {profesor.user.username} reactivado para el profesor {profesor.nombre_completo()}"
                )
                
                messages.success(request, f'✅ Usuario {profesor.user.username} reactivado')
                return redirect('editar_profesor', id=profesor.id)
                
            elif accion_usuario == 'reset_password' and profesor.user:
                from django.utils.crypto import get_random_string
                nueva_password = get_random_string(12)
                profesor.user.set_password(nueva_password)
                profesor.user.save()
                
                from .models import HistorialCambios
                HistorialCambios.objects.create(
                    modelo='Profesor',
                    objeto_id=profesor.id,
                    accion='EDITAR',
                    usuario=request.user,
                    descripcion=f"Contraseña reseteada para el usuario {profesor.user.username}"
                )
                
                messages.info(request,
                    f'🔐 Contraseña restablecida para {profesor.user.username}<br>'
                    f'Nueva contraseña: <strong>{nueva_password}</strong>',
                    extra_tags='safe'
                )
                return redirect('editar_profesor', id=profesor.id)
                
            elif accion_usuario == 'desvincular' and profesor.user:
                usuario_desvinculado = profesor.user
                profesor.user = None
                profesor.puede_acceder_sistema = False
                profesor.save()
                
                from .models import HistorialCambios
                HistorialCambios.objects.create(
                    modelo='Profesor',
                    objeto_id=profesor.id,
                    accion='EDITAR',
                    usuario=request.user,
                    descripcion=f"Usuario {usuario_desvinculado.username} desvinculado del profesor {profesor.nombre_completo()}"
                )
                
                messages.warning(request, f'⚠️ Usuario {usuario_desvinculado.username} desvinculado')
                return redirect('editar_profesor', id=profesor.id)
        
        # ==========================================
        # SI NO HAY ACCIÓN DE USUARIO, PROCESAMOS EL FORMULARIO NORMAL
        # ==========================================
        form = AltaProfesorForm(request.POST, request.FILES, instance=profesor)
        if form.is_valid():
            try:
                profesor = form.save()
                
                from .models import HistorialCambios
                HistorialCambios.objects.create(
                    modelo='Profesor',
                    objeto_id=profesor.id,
                    accion='EDITAR',
                    usuario=request.user,
                    descripcion=f"Profesor {profesor.nombre_completo()} actualizado"
                )
                
                messages.success(request, f'✅ Profesor {profesor.nombre_completo()} actualizado exitosamente')
                return redirect('listar_profesores')
            except Exception as e:
                messages.error(request, f'❌ Error: {e}')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'❌ {field}: {error}')
    else:
        form = AltaProfesorForm(instance=profesor)
    
    # Verificar estado del usuario asociado
    estado_usuario = None
    if profesor.user:
        estado_usuario = {
            'username': profesor.user.username,
            'is_active': profesor.user.is_active,
            'last_login': profesor.user.last_login,
            'email': profesor.user.email,
            'puede_acceder_sistema': profesor.puede_acceder_sistema,
            'id': profesor.user.id,
        }
    
    return render(request, 'web/profesores/editar_profesor.html', {
        'form': form,
        'profesor': profesor,
        'estado_usuario': estado_usuario,
        'es_coordinador': es_coordinador,
        'titulo': f'Editar Profesor: {profesor.nombre_completo()}'
    })

@login_required(login_url='login')
@gestion_completa_requerida
def eliminar_profesor(request, id):
    """Eliminar profesor (soft delete)"""
    profesor = get_object_or_404(Profesor, pk=id, eliminado=False)
    
    if request.method == "POST":
        try:
            profesor.soft_delete(usuario=request.user)
            messages.success(request, f'✅ Profesor {profesor.nombre_completo()} eliminado correctamente')
            return redirect('listar_profesores')
        except Exception as e:
            messages.error(request, f'❌ Error: {e}')
    
    context = {'profesor': profesor}
    return render(request, 'web/profesores/eliminar_profesor.html', context)


@login_required(login_url='login')
@gestion_completa_requerida
def profesores_eliminados(request):
    """Listar profesores eliminados (soft delete)"""
    # Obtener parámetro de búsqueda
    busqueda = request.GET.get('busqueda', '')
    
    # Filtrar profesores eliminados - USAR objects SIN FILTRO
    profesores = Profesor.objects.filter(eliminado=True).order_by('-fecha_eliminacion')
    
    # Aplicar búsqueda si existe
    if busqueda:
        profesores = profesores.filter(
            Q(nombre__icontains=busqueda) | 
            Q(apellido__icontains=busqueda) |
            Q(dni__icontains=busqueda) |
            Q(telefono__icontains=busqueda) |
            Q(mail__icontains=busqueda) |
            Q(cuit__icontains=busqueda)
        ).distinct()
    
    # Estadísticas
    total_eliminados = profesores.count()
    total_activos = Profesor.objects.filter(eliminado=False, activo=True).count()
    total_en_sistema = Profesor.objects.count()
    
    # DEBUG: Ver en consola
    print(f"DEBUG - Vista profesores_eliminados:")
    print(f"Total eliminados encontrados: {total_eliminados}")
    print(f"Profesores: {list(profesores.values_list('id', 'nombre', 'apellido', 'eliminado'))}")
    
    context = {
        'profesores': profesores,
        'titulo': 'Profesores Eliminados',
        'total_eliminados': total_eliminados,
        'total_activos': total_activos,
        'total_en_sistema': total_en_sistema,
        'busqueda_actual': busqueda
    }
    return render(request, 'web/profesores/profesores_eliminados.html', context)


@login_required(login_url='login')
@gestion_completa_requerida
def restaurar_profesor(request, id):
    """Restaurar profesor eliminado"""
    profesor = get_object_or_404(Profesor, pk=id, eliminado=True)
    
    if request.method == 'POST':
        try:
            with transaction.atomic():
                print(f"DEBUG: Iniciando restauración del profesor ID={profesor.id}")
                
                # Guardar nombre antes de restaurar
                nombre_completo = profesor.nombre_completo()
                
                # Restaurar el profesor
                profesor.restore(usuario=request.user)
                
                # Crear backup de la restauración
                from .utils import crear_backup_generico
                crear_backup_generico(
                    instancia=profesor,
                    motivo=f"Restauración solicitada por {request.user.username}",
                    usuario=request.user
                )
                
                messages.success(request, f'✅ Profesor {nombre_completo} restaurado correctamente')
                return redirect('listar_profesores')
                
        except Exception as e:
            print(f"ERROR en restaurar_profesor: {str(e)}")
            messages.error(request, f'❌ Error al restaurar profesor: {str(e)}')
            return redirect('profesores_eliminados')
    
    # GET - Mostrar página de confirmación
    
    # Calcular días eliminado
    dias_eliminado = 0
    if profesor.fecha_eliminacion:
        dias_eliminado = (timezone.now() - profesor.fecha_eliminacion).days
    
    # Obtener cursos que tenía asignados (buscar en backups/historial)
    cursos_asignados = []
    
    # Intenta buscar en backups si tienes esa funcionalidad
    try:
        from .models import BackupRegistro
        # Buscar backup reciente de este profesor
        backup = BackupRegistro.objects.filter(
            contenido__contains=str(profesor.id),
            modelo='Profesor'
        ).order_by('-fecha_backup').first()
        
        if backup and 'cursos_asignados' in backup.contenido:
            # Extraer IDs de cursos del backup
            import json
            datos = json.loads(backup.contenido)
            if 'cursos_asignados' in datos:
                from .models import Curso
                curso_ids = datos['cursos_asignados']
                cursos_asignados = Curso.objects.filter(id__in=curso_ids, activo=True)
    except:
        pass  # Si no hay sistema de backup, continuar sin cursos
    
    context = {
        'profesor': profesor,
        'dias_eliminado': dias_eliminado,
        'cursos_asignados': cursos_asignados
    }
    
    # Asegúrate de usar la plantilla correcta
    return render(request, 'web/profesores/restaurar_profesor.html', context)



# ============================================
# DASHBOARD Y PERFIL
# ============================================
@login_required
@requiere_permiso_profesor
def dashboard_profesor(request):
    """Dashboard principal - Acceso para profesores y administradores"""
    
    # Determinar qué mostrar según el tipo de usuario
    es_admin = getattr(request, 'es_administrador', False)
    profesor = getattr(request, 'profesor_actual', None)  # Usar profesor_actual según logs
    
    if es_admin and not profesor:
        # Administrador sin perfil de profesor - redirigir a dashboard admin
        return redirect('dashboard_admin_general')
    
    # Si llega aquí, es un profesor (o admin con perfil de profesor)
    hoy = timezone.now().date()
    
    if profesor:
        # Obtener cursos asignados
        cursos_asignados = profesor.cursos_asignados.filter(activo=True, eliminado=False)
        total_cursos = cursos_asignados.count()
        
        # Calcular total de alumnos en todos los cursos
        total_alumnos = 0
        for curso in cursos_asignados:
            total_alumnos += curso.total_alumnos  # Usa la propiedad total_alumnos del modelo Curso
        
        # Cursos próximos (con fecha de inicio mayor o igual a hoy)
        proximas_clases = cursos_asignados.filter(
            fecha_inicio__gte=hoy
        ).order_by('fecha_inicio')[:3]
        
        # Calcular asistencias pendientes para hoy
        asistencias_pendientes = 0
        try:
            from .models import Asistencia
            # Contar cursos activos hoy que no tienen asistencia registrada
            cursos_hoy = cursos_asignados.filter(
                fecha_inicio__lte=hoy,
                fecha_fin__gte=hoy
            )
            for curso in cursos_hoy:
                if not Asistencia.objects.filter(
                    curso=curso,
                    fecha=hoy
                ).exists():
                    asistencias_pendientes += 1
        except Exception as e:
            print(f"⚠️ Error calculando asistencias pendientes: {e}")
            asistencias_pendientes = 0
        
    else:
        cursos_asignados = []
        total_cursos = 0
        total_alumnos = 0
        proximas_clases = []
        asistencias_pendientes = 0
    
    # Notificaciones
    notificaciones = Notificacion.objects.filter(
        usuario_destino=request.user,
        eliminada=False
    ).order_by('-fecha_creacion')[:5]
    
    context = {
        'titulo': 'Dashboard del Profesor',
        'profesor': profesor,
        'cursos_asignados': cursos_asignados,
        'total_cursos': total_cursos,
        'total_alumnos': total_alumnos,  # ¡Añadido!
        'proximas_clases': proximas_clases,  # ¡Añadido! (no cursos_proximos)
        'asistencias_pendientes': asistencias_pendientes,  # ¡Añadido!
        'notificaciones': notificaciones,
        'hoy': hoy,
        'es_administrador': es_admin,
        'es_profesor': True,
        'modo_vista': 'profesor',  # ¡Añadido! (necesario para el template)
    }
    
    return render(request, 'web/profesores/dashboard.html', context)



@login_required
@requiere_permiso_profesor
def perfil_profesor(request):
    """Perfil del profesor (solo lectura)"""
    profesor = request.profesor
    
    # Obtener cursos históricos (incluye eliminados para estadísticas)
    cursos_totales = profesor.cursos_asignados.count()
    
    # Estadísticas de asistencias tomadas
    asistencias_tomadas = Asistencia.objects.filter(
        inscripcion__curso__profesor=profesor,
        registrado_por=request.user
    ).count()
    
    # Observaciones creadas
    observaciones_creadas = ObservacionAlumno.objects.filter(
        creado_por=request.user,
        eliminado=False
    ).count()
    
    # Historial de actividad reciente
    historial_reciente = HistorialCambios.objects.filter(
        usuario=request.user
    ).order_by('-fecha')[:10]
    
    context = {
        'profesor': profesor,
        'cursos_totales': cursos_totales,
        'asistencias_tomadas': asistencias_tomadas,
        'observaciones_creadas': observaciones_creadas,
        'historial_reciente': historial_reciente,
    }
    
    return render(request, 'web/profesores/perfil.html', context)

@login_required
@requiere_permiso_profesor
def mis_cursos(request):
    """Lista de cursos asignados al profesor"""
    profesor = request.profesor
    
    cursos = profesor.cursos_asignados.filter(activo=True, eliminado=False)
    
    context = {
        'cursos': cursos,
    }
    
    return render(request, 'web/profesores/mis_cursos.html', context)

# @login_required
# @requiere_permiso_profesor
# def detalle_curso_profesor(request, curso_id):
#     """Detalle de un curso específico del profesor"""
#     profesor = request.profesor
#     curso = request.curso
    
#     # Obtener inscripciones activas
#     inscripciones = Inscripcion.objects.filter(
#         curso=curso,
#         activo=True,
#         estado__in=['INSCRIPTO', 'CURSANDO']
#     ).select_related('alumno')
    
#     context = {
#         'curso': curso,
#         'alumnos': inscripciones,
#     }
    
#     return render(request, 'web/profesores/detalle_curso.html', context)

# ============================================
# CURSOS DEL PROFESOR
# ============================================

@login_required
@requiere_permiso_profesor
def mis_cursos(request):
    """Lista de cursos asignados al profesor"""
    profesor = request.profesor
    
    # Filtros
    estado = request.GET.get('estado', 'activos')
    busqueda = request.GET.get('buscar', '')
    
    # Obtener cursos según filtro
    if estado == 'activos':
        cursos = profesor.cursos_asignados.filter(activo=True, eliminado=False)
    elif estado == 'finalizados':
        hoy = timezone.now().date()
        cursos = profesor.cursos_asignados.filter(
            fecha_fin__lt=hoy,
            activo=True,
            eliminado=False
        )
    else:  # todos
        cursos = profesor.cursos_asignados.filter(eliminado=False)
    
    # Búsqueda
    if busqueda:
        cursos = cursos.filter(
            Q(nombre__icontains=busqueda) |
            Q(dias__icontains=busqueda) |
            Q(horario__icontains=busqueda)
        )
    
    # Ordenar por fecha de inicio (más recientes primero)
    cursos = cursos.order_by('-fecha_inicio')
    
    # Estadísticas
    cursos_activos = cursos.filter(activo=True, eliminado=False).count()
    cursos_finalizados = cursos.filter(
        fecha_fin__lt=timezone.now().date(),
        activo=True,
        eliminado=False
    ).count()
    
    context = {
        'cursos': cursos,
        'cursos_activos': cursos_activos,
        'cursos_finalizados': cursos_finalizados,
        'estado_filtro': estado,
        'busqueda_actual': busqueda,
    }
    
    return render(request, 'web/profesores/mis_cursos.html', context)

@login_required
@requiere_permiso_profesor
def detalle_curso_profesor(request, curso_id):
    """Detalle de un curso específico del profesor"""
    profesor = request.profesor
    curso = request.curso
    
    # Obtener inscripciones activas
    inscripciones = Inscripcion.objects.filter(
        curso=curso,
        activo=True,
        estado__in=['INSCRIPTO', 'CURSANDO']
    ).select_related('alumno')
    
    # Preparar datos de alumnos con estadísticas
    alumnos_data = []
    hoy = timezone.now().date()
    
    for inscripcion in inscripciones:
        alumno = inscripcion.alumno
        
        # Asistencias del alumno en este curso
        asistencias = Asistencia.objects.filter(inscripcion=inscripcion)
        total_clases = asistencias.count()
        presentes = asistencias.filter(presente=True).count()
        porcentaje_asistencia = (presentes / total_clases * 100) if total_clases > 0 else 0
        
        # Exámenes del alumno
        examenes = Examen.objects.filter(inscripcion=inscripcion)
        promedio = examenes.aggregate(prom=Avg('nota'))['prom'] if examenes.exists() else None
        
        # Observaciones recientes del alumno (solo visibles para el profesor)
        observaciones = ObservacionAlumno.objects.filter(
            alumno=alumno,
            curso=curso,
            eliminado=False,
            visibilidad__in=['PROFESOR_CURSO', 'PROFESORES_CURSO', 'TODOS']
        ).order_by('-fecha_creacion')[:3]
        
        alumnos_data.append({
            'inscripcion': inscripcion,
            'alumno': alumno,
            'total_clases': total_clases,
            'presentes': presentes,
            'porcentaje_asistencia': round(porcentaje_asistencia, 1),
            'promedio': round(promedio, 2) if promedio else None,
            'observaciones_recientes': observaciones,
        })
    
    # Estadísticas del curso
    total_alumnos = inscripciones.count()
    promedio_general = None
    asistencia_general = None
    
    if alumnos_data:
        promedios = [a['promedio'] for a in alumnos_data if a['promedio']]
        if promedios:
            promedio_general = sum(promedios) / len(promedios)
        
        porcentajes = [a['porcentaje_asistencia'] for a in alumnos_data if a['total_clases'] > 0]
        if porcentajes:
            asistencia_general = sum(porcentajes) / len(porcentajes)
    
    context = {
        'curso': curso,
        'alumnos_data': alumnos_data,
        'total_alumnos': total_alumnos,
        'promedio_general': round(promedio_general, 2) if promedio_general else None,
        'asistencia_general': round(asistencia_general, 1) if asistencia_general else None,
        'hoy': hoy,
    }
    
    return render(request, 'web/profesores/detalle_curso.html', context)

# ============================================
# ASISTENCIA
# ============================================

@login_required
@requiere_permiso_profesor
def tomar_asistencia_profesor(request, curso_id):
    """Tomar asistencia para un curso específico"""
    profesor = request.profesor
    curso = request.curso
    
    # Verificar que el profesor tiene permiso para este curso
    if not request.es_administrador and curso.profesor != profesor:
        messages.error(request, "No tienes permiso para tomar asistencia en este curso")
        return redirect('mis_cursos_profesor')
    
    hoy = timezone.now().date()
    
    # Obtener inscripciones activas
    inscripciones = Inscripcion.objects.filter(
        curso=curso,
        activo=True,
        estado__in=['INSCRIPTO', 'CURSANDO']
    ).select_related('alumno')
    
    # Generar fechas de clase para el mes actual
    mes_actual = hoy.month
    año_actual = hoy.year
    
    # Obtener días de clase del curso
    dias_clase = curso.obtener_dias_lista() if hasattr(curso, 'obtener_dias_lista') else []
    
    if request.method == 'POST':
        try:
            fecha_str = request.POST.get('fecha', hoy.isoformat())
            fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date()
            
            # Verificar que la fecha no sea futura
            if fecha > hoy:
                messages.error(request, 'No puedes tomar asistencia para fechas futuras')
                return redirect('tomar_asistencia_profesor', curso_id=curso.id)
            
            # Contadores para estadísticas
            ausentes_count = 0
            presentes_count = 0
            alumnos_ausentes_lista = []
            
            # Procesar cada alumno
            for inscripcion in inscripciones:
                alumno_id = str(inscripcion.alumno.id)
                presente = request.POST.get(f'presente_{alumno_id}') == 'on'
                observaciones = request.POST.get(f'observaciones_{alumno_id}', '').strip()
                
                # Contar estadísticas
                if presente:
                    presentes_count += 1
                else:
                    ausentes_count += 1
                    alumnos_ausentes_lista.append(inscripcion.alumno.nombre_completo())
                
                # Crear o actualizar asistencia
                Asistencia.objects.update_or_create(
                    inscripcion=inscripcion,
                    fecha=fecha,
                    defaults={
                        'presente': presente,
                        'observaciones': observaciones,
                        'registrado_por': request.user,
                    }
                )
            
            total_alumnos = inscripciones.count()
            porcentaje_ausencia = (ausentes_count / total_alumnos * 100) if total_alumnos > 0 else 0
            
            messages.success(request, 
                f'Asistencia del {fecha.strftime("%d/%m/%Y")} guardada correctamente. '
                f'Presentes: {presentes_count}, Ausentes: {ausentes_count}'
            )
            
            # ============================================
            # CREAR NOTIFICACIÓN DE AUSENCIA (CORREGIDA)
            # ============================================
            print("=" * 60)
            print(f"📊 RESUMEN ASISTENCIA - Curso: {curso.nombre}")
            print(f"📅 Fecha: {fecha.strftime('%d/%m/%Y')}")
            print(f"👨‍🎓 Total alumnos: {total_alumnos}")
            print(f"✅ Presentes: {presentes_count}")
            print(f"❌ Ausentes: {ausentes_count} ({porcentaje_ausencia:.1f}%)")
            
            # Condición para crear notificación: más de 2 ausentes o más del 30%
            if ausentes_count >= 3 or porcentaje_ausencia > 30:
                print("⚠️ CONDICIÓN CUMPLIDA: Creando notificación de ausencia")
                
                # Determinar destinatario de la notificación
                destinatario = None
                
                # 1. Intentar obtener el auxiliar del curso
                auxiliar_curso = None
                
                # Verificar campo 'auxiliar' (relación con Personal)
                if hasattr(curso, 'auxiliar') and curso.auxiliar:
                    print(f"🔍 Buscando auxiliar en campo 'auxiliar': {curso.auxiliar.nombre_completo()}")
                    auxiliar_curso = curso.auxiliar
                
                # Verificar campo 'auxiliarCurso' (si existe)
                elif hasattr(curso, 'auxiliarCurso') and curso.auxiliarCurso:
                    print(f"🔍 Buscando auxiliar en campo 'auxiliarCurso': {curso.auxiliarCurso.nombre_completo()}")
                    auxiliar_curso = curso.auxiliarCurso
                
                # 2. Si hay auxiliar, verificar si tiene usuario
                if auxiliar_curso:
                    if hasattr(auxiliar_curso, 'user') and auxiliar_curso.user:
                        destinatario = auxiliar_curso.user
                        print(f"✅ DESTINATARIO ENCONTRADO: Auxiliar - {destinatario.get_full_name()}")
                    else:
                        print(f"⚠️ Auxiliar encontrado pero NO tiene usuario asociado: {auxiliar_curso.nombre_completo()}")
                
                # 3. Si no hay auxiliar, usar el profesor del curso
                if not destinatario and curso.profesor:
                    if hasattr(curso.profesor, 'user') and curso.profesor.user:
                        destinatario = curso.profesor.user
                        print(f"✅ DESTINATARIO ENCONTRADO: Profesor (fallback) - {destinatario.get_full_name()}")
                    else:
                        print(f"⚠️ Profesor encontrado pero NO tiene usuario asociado: {curso.profesor.nombre_completo()}")
                
                # 4. Si aún no hay destinatario, buscar a Claudia Alegre
                if not destinatario:
                    try:
                        # Buscar usuario específico "claudia.alegre"
                        destinatario = User.objects.filter(
                            username__icontains='claudia',
                            is_active=True
                        ).first()
                        
                        if destinatario:
                            print(f"✅ DESTINATARIO ENCONTRADO: Claudia Alegre - {destinatario.username}")
                        else:
                            # Buscar cualquier administrativo activo
                            from web.models import Personal
                            administrativo = Personal.objects.filter(
                                tipo='ADMINISTRATIVO',
                                activo=True,
                                user__isnull=False
                            ).first()
                            
                            if administrativo and administrativo.user:
                                destinatario = administrativo.user
                                print(f"✅ DESTINATARIO ENCONTRADO: Administrativo genérico - {destinatario.username}")
                    except Exception as e:
                        print(f"❌ Error buscando destinatario administrativo: {e}")
                
                # 5. Si no se encontró ningún destinatario, usar el usuario actual
                if not destinatario:
                    destinatario = request.user
                    print(f"⚠️ Usando usuario actual como fallback: {destinatario.username}")
                
                # 6. Crear la notificación
                if destinatario:
                    try:
                        # Obtener o crear tipo de notificación
                        tipo_notificacion, created = TipoNotificacion.objects.get_or_create(
                            nombre='AUSENCIA_MASIVA',
                            defaults={
                                'icono': 'fa-user-times',
                                'color': 'warning',
                                'descripcion': 'Notificación por alta ausencia en curso'
                            }
                        )
                        
                        # Crear mensaje detallado
                        mensaje = (
                            f"**Curso:** {curso.nombre}\n"
                            f"**Fecha:** {fecha.strftime('%d/%m/%Y')}\n"
                            f"**Profesor:** {curso.profesor.nombre_completo() if curso.profesor else 'No asignado'}\n"
                            f"**Total alumnos:** {total_alumnos}\n"
                            f"**Presentes:** {presentes_count}\n"
                            f"**Ausentes:** {ausentes_count} ({porcentaje_ausencia:.1f}%)\n\n"
                        )
                        
                        # Agregar lista de ausentes si no son muchos
                        if alumnos_ausentes_lista and len(alumnos_ausentes_lista) <= 10:
                            mensaje += "**Alumnos ausentes:**\n"
                            for alumno in alumnos_ausentes_lista:
                                mensaje += f"• {alumno}\n"
                        elif alumnos_ausentes_lista:
                            mensaje += f"**Hay {ausentes_count} alumnos ausentes**\n"
                        
                        # Determinar prioridad
                        if porcentaje_ausencia > 50 or ausentes_count >= 10:
                            prioridad = 'URGENTE'
                        elif porcentaje_ausencia > 30:
                            prioridad = 'ALTA'
                        else:
                            prioridad = 'MEDIA'
                        
                        # Crear notificación
                        notificacion = Notificacion.objects.create(
                            titulo=f'⚠️ Alta ausencia en {curso.nombre}',
                            mensaje=mensaje,
                            usuario_destino=destinatario,
                            usuario_origen=request.user,
                            estado='PENDIENTE',
                            prioridad=prioridad,
                            tipo=tipo_notificacion,
                            fecha_vencimiento=timezone.now() + timezone.timedelta(hours=24),
                            es_manual=False
                        )
                        
                        print(f"📨 NOTIFICACIÓN CREADA: ID {notificacion.id}")
                        print(f"   Destinatario: {destinatario.get_full_name()}")
                        print(f"   Prioridad: {prioridad}")
                        print(f"   Ausentes: {ausentes_count} ({porcentaje_ausencia:.1f}%)")
                        
                        # Mensaje informativo para el profesor
                        if destinatario != request.user:
                            messages.info(request, 
                                f'Notificación de ausencia enviada a {destinatario.get_full_name()} '
                                f'({ausentes_count} alumnos ausentes)'
                            )
                        
                    except Exception as e:
                        print(f"❌ ERROR creando notificación: {e}")
                        messages.warning(request, "No se pudo crear la notificación de ausencia")
                else:
                    print("❌ NO SE PUDO DETERMINAR DESTINATARIO")
                
                print("=" * 60)
            
            return redirect('tomar_asistencia_profesor', curso_id=curso.id)
            
        except Exception as e:
            print(f"❌ ERROR en tomar_asistencia_profesor: {e}")
            messages.error(request, f'Error al guardar asistencia: {str(e)}')
            return redirect('tomar_asistencia_profesor', curso_id=curso.id)
    
    # ============================================
    # MÉTODO GET: Mostrar formulario de asistencia
    # ============================================
    
    # Obtener asistencias del mes actual para referencia
    asistencias_mes = Asistencia.objects.filter(
        inscripcion__curso=curso,
        fecha__month=mes_actual,
        fecha__year=año_actual
    ).select_related('inscripcion', 'inscripcion__alumno')
    
    # Crear diccionario para fácil acceso
    asistencias_dict = {}
    for asistencia in asistencias_mes:
        key = f"{asistencia.inscripcion.alumno.id}_{asistencia.fecha.strftime('%Y-%m-%d')}"
        asistencias_dict[key] = asistencia
    
    # Obtener estadísticas del curso
    estadisticas_curso = {
        'total_alumnos': inscripciones.count(),
        'alumnos_presentes_hoy': Asistencia.objects.filter(
            inscripcion__curso=curso,
            fecha=hoy,
            presente=True
        ).count(),
        'alumnos_ausentes_hoy': Asistencia.objects.filter(
            inscripcion__curso=curso,
            fecha=hoy,
            presente=False
        ).count(),
    }
    
    # Información del auxiliar para mostrar en el template
    auxiliar_info = None
    if hasattr(curso, 'auxiliar') and curso.auxiliar:
        auxiliar_info = {
            'nombre': curso.auxiliar.nombre_completo(),
            'tipo': 'Auxiliar',
            'campo': 'auxiliar',
        }
    elif hasattr(curso, 'auxiliarCurso') and curso.auxiliarCurso:
        auxiliar_info = {
            'nombre': curso.auxiliarCurso.nombre_completo(),
            'tipo': 'Auxiliar Curso',
            'campo': 'auxiliarCurso',
        }
    
    context = {
        'curso': curso,
        'inscripciones': inscripciones,
        'hoy': hoy,
        'asistencias_dict': asistencias_dict,
        'dias_clase': dias_clase,
        'mes_actual': mes_actual,
        'año_actual': año_actual,
        'estadisticas_curso': estadisticas_curso,
        'auxiliar_info': auxiliar_info,
        'profesor_actual': profesor,
        'es_administrador': request.es_administrador,
    }
    
    return render(request, 'web/profesores/tomar_asistencia.html', context)

# # ============================================
# # NOTAS Y EXÁMENES
# # ============================================

# @login_required
# @requiere_permiso_profesor
# def gestionar_notas(request, curso_id):
#     # Obtener el curso
#     curso = get_object_or_404(Curso, id=curso_id, activo=True)
    
#     # Verificar que el profesor es el asignado o es administrador/coordinador
#     if not (getattr(request, 'es_administrador', False) or curso.profesor_id == request.profesor.id):
#         messages.error(request, "No tienes permiso para gestionar este curso.")
#         return redirect('dashboard_profesor')
    
#     # Obtener inscripciones activas
#     inscripciones = Inscripcion.objects.filter(
#         curso=curso,
#         activo=True,
#         estado__in=['INSCRIPTO', 'CURSANDO']
#     ).select_related('alumno')
    
#     if request.method == 'POST':
#         try:
#             for inscripcion in inscripciones:
#                 for tipo_examen in ['TEORICO_1', 'TEORICO_2', 'PRACTICO_1', 'PRACTICO_2']:
#                     nota_key = f"nota_{inscripcion.id}_{tipo_examen}"
#                     obs_key = f"obs_{inscripcion.id}_{tipo_examen}"
#                     if nota_key in request.POST and request.POST[nota_key]:
#                         try:
#                             nota = float(request.POST[nota_key])
#                             observaciones = request.POST.get(obs_key, '')
#                             Examen.objects.update_or_create(
#                                 inscripcion=inscripcion,
#                                 tipo=tipo_examen,
#                                 defaults={
#                                     'nota': nota,
#                                     'observaciones': observaciones,
#                                     'fecha': timezone.now().date(),
#                                 }
#                             )
#                         except ValueError:
#                             continue
#             messages.success(request, 'Notas guardadas correctamente')
#             return redirect('gestionar_notas', curso_id=curso.id)
#         except Exception as e:
#             messages.error(request, f'Error al guardar notas: {str(e)}')
    
#     # Cargar exámenes existentes
#     examenes = Examen.objects.filter(inscripcion__curso=curso).select_related('inscripcion', 'inscripcion__alumno')
#     examenes_dict = {}
#     for examen in examenes:
#         key = f"{examen.inscripcion.id}_{examen.tipo}"
#         examenes_dict[key] = examen
    
#     context = {
#         'curso': curso,
#         'inscripciones': inscripciones,
#         'examenes_dict': examenes_dict,
#     }
#     return render(request, 'web/profesores/gestionar_notas.html', context)

# @login_required
# @requiere_permiso_profesor
# def agregar_examen_individual(request, curso_id, alumno_id):
#     # Obtener curso y alumno
#     curso = get_object_or_404(Curso, id=curso_id, activo=True)
#     alumno = get_object_or_404(Alumno, id=alumno_id, eliminado=False)
    
#     # Verificar permisos
#     if not (getattr(request, 'es_administrador', False) or curso.profesor_id == request.profesor.id):
#         messages.error(request, "No tienes permiso.")
#         return redirect('dashboard_profesor')
    
#     # Obtener inscripción activa
#     inscripcion = get_object_or_404(Inscripcion, curso=curso, alumno=alumno, activo=True)
    
#     if request.method == 'POST':
#         form = ExamenForm(request.POST)
#         if form.is_valid():
#             examen = form.save(commit=False)
#             examen.inscripcion = inscripcion
#             examen.save()
#             messages.success(request, 'Examen agregado correctamente')
#             return redirect('detalle_curso_profesor', curso_id=curso.id)
#     else:
#         form = ExamenForm()
    
#     context = {
#         'curso': curso,
#         'alumno': alumno,
#         'form': form,
#     }
#     return render(request, 'web/profesores/agregar_examen.html', context)

# ============================================
# OBSERVACIONES
# ============================================

@login_required
@requiere_permiso_profesor
def listar_observaciones_curso(request, curso_id):
    """Listar observaciones de un curso"""
    profesor = request.profesor
    curso = request.curso
    
    # Obtener observaciones visibles para el profesor
    observaciones = ObservacionAlumno.objects.filter(
        curso=curso,
        eliminado=False,
        visibilidad__in=['PROFESOR_CURSO', 'PROFESORES_CURSO', 'TODOS']
    ).select_related('alumno', 'creado_por').order_by('-fecha_creacion')
    
    # Filtros
    tipo = request.GET.get('tipo', '')
    creador = request.GET.get('creador', '')
    estado = request.GET.get('estado', '')
    busqueda = request.GET.get('buscar', '')
    
    if tipo:
        observaciones = observaciones.filter(tipo=tipo)
    
    if creador == 'mi':
        observaciones = observaciones.filter(creado_por=request.user)
    elif creador == 'otros':
        observaciones = observaciones.exclude(creado_por=request.user)
    
    if estado == 'importantes':
        observaciones = observaciones.filter(es_importante=True)
    elif estado == 'resueltas':
        observaciones = observaciones.filter(resuelto=True)
    elif estado == 'pendientes':
        observaciones = observaciones.filter(resuelto=False)
    
    if busqueda:
        observaciones = observaciones.filter(
            Q(contenido__icontains=busqueda) |
            Q(alumno__nombre__icontains=busqueda) |
            Q(alumno__apellido__icontains=busqueda)
        )
    
    # Paginación
    page = request.GET.get('page', 1)
    paginator = Paginator(observaciones, 20)
    
    try:
        observaciones_paginadas = paginator.page(page)
    except:
        observaciones_paginadas = paginator.page(1)
    
    context = {
        'curso': curso,
        'observaciones': observaciones_paginadas,
        'tipos_observacion': ObservacionAlumno.TIPO_CHOICES,
        'filtro_tipo': tipo,
        'filtro_creador': creador,
        'filtro_estado': estado,
        'busqueda_actual': busqueda,
    }
    
    return render(request, 'web/profesores/listar_observaciones.html', context)

@login_required
@requiere_permiso_profesor
def agregar_observacion_alumno(request, curso_id, alumno_id):
    """Agregar observación a un alumno"""
    profesor = request.profesor
    curso = request.curso
    alumno = get_object_or_404(Alumno, id=alumno_id)
    
    if request.method == 'POST':
        form = ObservacionForm(request.POST)
        if form.is_valid():
            observacion = form.save(commit=False)
            observacion.alumno = alumno
            observacion.curso = curso
            observacion.creado_por = request.user
            observacion.save()
            
            # Crear notificación para administración/coordinación si es importante
            if observacion.es_importante:
                # Buscar coordinadores y administradores
                usuarios_admin = User.objects.filter(
                    Q(personal_relacionado__tipo='COORDINADOR') |
                    Q(personal_relacionado__tipo='ADMINISTRATIVO'),
                    is_active=True
                ).distinct()
                
                for usuario in usuarios_admin:
                    Notificacion.objects.create(
                        usuario_destino=usuario,
                        usuario_origen=request.user,
                        titulo=f'📌 Observación importante: {alumno.nombre_completo()}',
                        mensaje=f'{profesor.nombre_completo()} agregó una observación importante para {alumno.nombre_completo()} en {curso.nombre}',
                        estado='PENDIENTE',
                        prioridad='ALTA',
                        es_manual=False
                    )
            
            messages.success(request, 'Observación agregada correctamente')
            return redirect('detalle_alumno_profesor', curso_id=curso.id, alumno_id=alumno.id)
    else:
        form = ObservacionForm()
    
    context = {
        'curso': curso,
        'alumno': alumno,
        'form': form,
    }
    
    return render(request, 'web/profesores/agregar_observacion.html', context)

@login_required
@requiere_permiso_profesor
def detalle_alumno_profesor(request, curso_id, alumno_id):
    """Detalle de un alumno en un curso específico"""
    # Obtener curso y alumno desde los parámetros de la URL
    curso = get_object_or_404(Curso, id=curso_id, activo=True, eliminado=False)
    alumno = get_object_or_404(Alumno, id=alumno_id, activo=True)
    
    # Obtener la inscripción activa del alumno en este curso
    inscripcion = get_object_or_404(
        Inscripcion, 
        curso=curso, 
        alumno=alumno, 
        activo=True,
        estado__in=['INSCRIPTO', 'CURSANDO']  # Opcional, según tu lógica
    )
    
    # El profesor puede obtenerse del decorador o desde request.user si ya está configurado
    # Si usas @requiere_permiso_profesor, puede que ya tenga request.profesor
    profesor = getattr(request, 'profesor', None)
    # Obtener asistencias
    asistencias = Asistencia.objects.filter(
        inscripcion=inscripcion
    ).order_by('-fecha')
    
    # Obtener exámenes
    examenes = Examen.objects.filter(
        inscripcion=inscripcion
    ).order_by('tipo')
    
    # Obtener observaciones (solo visibles para el profesor)
    observaciones = ObservacionAlumno.objects.filter(
        alumno=alumno,
        curso=curso,
        eliminado=False,
        visibilidad__in=['PROFESOR_CURSO', 'PROFESORES_CURSO', 'TODOS']
    ).order_by('-fecha_creacion')
    
    # Estadísticas
    total_asistencias = asistencias.count()
    asistencias_presente = asistencias.filter(presente=True).count()
    porcentaje_asistencia = (asistencias_presente / total_asistencias * 100) if total_asistencias > 0 else 0
    
    promedio = examenes.aggregate(prom=Avg('nota'))['prom'] if examenes.exists() else None
    
    context = {
        'curso': curso,
        'alumno': alumno,
        'inscripcion': inscripcion,
        'asistencias': asistencias,
        'examenes': examenes,
        'observaciones': observaciones,
        'total_asistencias': total_asistencias,
        'asistencias_presente': asistencias_presente,
        'porcentaje_asistencia': round(porcentaje_asistencia, 1),
        'promedio': round(promedio, 2) if promedio else None,
    }
    
    return render(request, 'web/profesores/detalle_alumno.html', context)

# ============================================
# ACCIONES AJAX/RÁPIDAS
# ============================================

@login_required
@requiere_permiso_profesor
@require_POST
def marcar_observacion_resuelta(request, observacion_id):
    """Marcar observación como resuelta (AJAX)"""
    try:
        observacion = ObservacionAlumno.objects.get(
            id=observacion_id,
            creado_por=request.user,  # Solo el creador puede marcar como resuelta
            eliminado=False
        )
        
        observacion.resuelto = not observacion.resuelto  # Toggle
        if observacion.resuelto:
            observacion.fecha_resolucion = timezone.now()
        else:
            observacion.fecha_resolucion = None
        
        observacion.save()
        
        return JsonResponse({
            'success': True,
            'resuelto': observacion.resuelto,
            'fecha_resolucion': observacion.fecha_resolucion.strftime('%d/%m/%Y %H:%M') if observacion.fecha_resolucion else ''
        })
        
    except ObservacionAlumno.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Observación no encontrada'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
@requiere_permiso_profesor
@require_GET
def obtener_estadisticas_curso(request, curso_id):
    """Obtener estadísticas del curso (AJAX)"""
    try:
        profesor = request.profesor
        curso = get_object_or_404(Curso, id=curso_id, profesor=profesor, activo=True, eliminado=False)
        
        # Obtener inscripciones
        inscripciones = Inscripcion.objects.filter(
            curso=curso,
            activo=True,
            estado__in=['INSCRIPTO', 'CURSANDO']
        )
        
        # Calcular estadísticas
        total_alumnos = inscripciones.count()
        
        # Asistencia del mes actual
        hoy = timezone.now().date()
        asistencias_mes = Asistencia.objects.filter(
            inscripcion__curso=curso,
            fecha__month=hoy.month,
            fecha__year=hoy.year
        )
        total_clases_mes = asistencias_mes.values('fecha').distinct().count()
        promedio_asistencia_mes = (asistencias_mes.filter(presente=True).count() / (total_alumnos * total_clases_mes * 100)) if total_clases_mes > 0 else 0
        
        # Promedio de notas
        examenes = Examen.objects.filter(inscripcion__curso=curso)
        promedio_notas = examenes.aggregate(prom=Avg('nota'))['prom'] if examenes.exists() else None
        
        # Observaciones pendientes
        observaciones_pendientes = ObservacionAlumno.objects.filter(
            curso=curso,
            resuelto=False,
            eliminado=False,
            visibilidad__in=['PROFESOR_CURSO', 'PROFESORES_CURSO', 'TODOS']
        ).count()
        
        return JsonResponse({
            'success': True,
            'data': {
                'total_alumnos': total_alumnos,
                'promedio_asistencia_mes': round(promedio_asistencia_mes, 1),
                'promedio_notas': round(promedio_notas, 2) if promedio_notas else None,
                'observaciones_pendientes': observaciones_pendientes,
                'total_clases_mes': total_clases_mes,
            }
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

##########################################
# VISTAS PARA GESTIÓN DE CURSOS
##########################################

@login_required(login_url='login')
@gestion_completa_requerida
def alta_curso(request):
    """Crear nuevo curso"""
    if request.method == "POST":
        form = AltaCursoForm(request.POST)
        if form.is_valid():
            nuevo_curso = form.save()
            messages.success(request, '✅ El curso fue dado de alta con éxito')
            return redirect('listar_cursos')
        else:
            messages.error(request, '❌ Por favor, corrige los errores en el formulario.')
    else:
        form = AltaCursoForm()
    
    context = {
        'alta_curso_form': form,
    }
    return render(request, 'web/cursos/alta_curso.html', context)


@login_required(login_url='login')
def listar_cursos(request):
    """Listar todos los cursos"""
    busqueda = request.GET.get("buscar")
    cursos = Curso.objects.all()
    
    if request.GET.get("buscar"):
        cursos = Curso.objects.filter(
            Q(nombre__icontains=busqueda) | 
            Q(fecha_inicio__icontains=busqueda) |
            Q(fecha_fin__icontains=busqueda) |
            Q(precio__icontains=busqueda) 
        ).distinct()
    
    context = {
        'cursos': cursos
    }
    return render(request, 'web/cursos/listar_cursos.html', context)

@login_required(login_url='login')
def listar_alumnos_curso(request, curso_id):
    curso = get_object_or_404(Curso, id=curso_id)
    inscripciones = Inscripcion.objects.filter(
        curso=curso, 
        activo=True,
        estado__in=['INSCRIPTO', 'CURSANDO']
    ).select_related('alumno')
    
    hoy = timezone.now().date()
    mes_actual = hoy.month
    año_actual = hoy.year
    
    alumnos_inscripciones = []
    for inscripcion in inscripciones:
        # Determinar estado de pago
        estado_pago = 'AL_DIA'
        try:
            cuota = CuotaAlumno.objects.get(
                inscripcion=inscripcion,
                mes=mes_actual,
                año=año_actual
            )
            if not cuota.pagada:
                if hoy.day <= 10:
                    estado_pago = 'NARANJA'
                else:
                    estado_pago = 'ROJO'
        except CuotaAlumno.DoesNotExist:
            estado_pago = 'AL_DIA'
        
        # Obtener última asistencia
        ultima_asistencia = Asistencia.objects.filter(
            inscripcion=inscripcion
        ).order_by('-fecha').first()
        
        alumnos_inscripciones.append({
            'inscripcion': inscripcion,
            'alumno': inscripcion.alumno,
            'estado_pago': estado_pago,
            'ultima_asistencia': ultima_asistencia,
        })
    
    context = {
        'curso': curso,
        'alumnos': alumnos_inscripciones,
    }
    return render(request, 'web/cursos/listar_alumnos_curso.html', context)


# views.py - función tomar_asistencia
# @login_required
# #@secretaria_o_superior
# def tomar_asistencia_secretaria(request, curso_id):
#     curso = get_object_or_404(Curso, id=curso_id, activo=True)
    
#     # Verificar permisos
#     if not (request.user.is_staff or request.user.is_superuser or 
#             curso.profesor == request.user.profesor if hasattr(request.user, 'profesor') else False):
#         messages.error(request, "No tienes permiso para tomar asistencia en este curso")
#         return redirect('listar_cursos')
    
#     hoy = timezone.now().date()
    
#     if request.method == 'POST':
#         try:
#             # Obtener todas las inscripciones activas del curso
#             inscripciones = Inscripcion.objects.filter(
#                 curso=curso,
#                 activo=True,
#                 estado__in=['INSCRIPTO', 'CURSANDO']
#             ).select_related('alumno')
            
#             # Procesar datos del formulario
#             data = request.POST
            
#             # Verificar si es para agregar examen
#             if 'agregar_examen' in data:
#                 # Tu código actual para agregar examen...
#                 pass
            
#             # Verificar si es para eliminar examen
#             elif 'eliminar_examen' in data:
#                 # Tu código actual para eliminar examen...
#                 pass
            
#             else:
#                 # Procesar asistencias y notas
#                 alumnos_procesados = []
                
#                 for inscripcion in inscripciones:
#                     alumno = inscripcion.alumno
                    
#                     # Procesar asistencias por fecha
#                     for fecha_str in data.getlist('fechas[]', []):
#                         try:
#                             fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date()
#                             if fecha > hoy:  # No permitir futuras asistencias
#                                 continue
                            
#                             checkbox_name = f"asistencia_{inscripcion.id}_{fecha_str}"
#                             presente = checkbox_name in data
                            
#                             # Buscar o crear asistencia
#                             asistencia, created = Asistencia.objects.get_or_create(
#                                 inscripcion=inscripcion,
#                                 fecha=fecha,
#                                 defaults={
#                                     'presente': presente,
#                                     'registrado_por': request.user,
#                                     'observaciones': ''
#                                 }
#                             )
                            
#                             # Actualizar si ya existe
#                             if not created and (asistencia.presente != presente):
#                                 asistencia.presente = presente
#                                 asistencia.registrado_por = request.user
#                                 asistencia.save()
                            
#                         except ValueError:
#                             continue
                    
#                     # Procesar notas de exámenes
#                     # Tu código actual para procesar notas...
                
#                 # DESPUÉS DE GUARDAR TODAS LAS ASISTENCIAS, VERIFICAR INASISTENCIAS CONSECUTIVAS
#                 try:
#                     from .utils import verificar_inasistencias_consecutivas
#                     notificaciones_creadas = verificar_inasistencias_consecutivas(curso_id, hoy)
                    
#                     if notificaciones_creadas > 0:
#                         messages.info(
#                             request, 
#                             f'✅ Se generaron {notificaciones_creadas} notificaciones por inasistencias consecutivas'
#                         )
#                 except Exception as e:
#                     print(f"⚠️ Error al verificar inasistencias: {e}")
#                     # No mostrar error al usuario para no interrumpir el flujo
                
#                 messages.success(request, '✅ Asistencia y notas guardadas correctamente')
#                 return redirect('tomar_asistencia', curso_id=curso.id)
                
#         except Exception as e:
#             print(f"❌ Error al guardar asistencia: {e}")
#             messages.error(request, f'❌ Error al guardar: {str(e)}')
    
#     @register.filter
#     def get_item(dictionary, key):
#         return dictionary.get(key)

    
#     context = {
#         # Tu contexto actual...
#     }
    
#     return render(request, 'web/asistencia/tomar_asistencia.html', context)

@login_required
def guardar_asistencia_completa(request, curso, inscripciones, fechas_clase):
    hoy = timezone.now().date()
    permite_editar_pasado = request.user.is_staff
    
    # Diccionario para contar ausentes por fecha
    ausentes_por_fecha = {}
    
    try:
        with transaction.atomic():
            for inscripcion in inscripciones:
                # Procesar asistencias
                for fecha in fechas_clase:
                    if not permite_editar_pasado and fecha < hoy:
                        continue  # Saltar fechas pasadas si no tiene permiso
                    
                    key = f"asistencia_{inscripcion.id}_{fecha.strftime('%Y-%m-%d')}"
                    presente = request.POST.get(key) == 'on'
                    
                    observaciones_key = f"observaciones_{inscripcion.id}_{fecha.strftime('%Y-%m-%d')}"
                    observaciones = request.POST.get(observaciones_key, '')
                    
                    # Contar ausentes
                    if not presente:
                        if fecha not in ausentes_por_fecha:
                            ausentes_por_fecha[fecha] = 0
                        ausentes_por_fecha[fecha] += 1
                    
                    Asistencia.objects.update_or_create(
                        inscripcion=inscripcion,
                        fecha=fecha,
                        defaults={
                            'presente': presente,
                            'observaciones': observaciones,
                            'registrado_por': request.user,
                        }
                    )
        
        # Crear notificaciones para fechas con alta ausencia
        total_alumnos = inscripciones.count()
        
        for fecha, num_ausentes in ausentes_por_fecha.items():
            porcentaje_ausencia = (num_ausentes / total_alumnos * 100) if total_alumnos > 0 else 0
            
            # Crear notificación si hay más del 30% de ausentes o más de 3 ausentes
            if num_ausentes >= 3 or porcentaje_ausencia > 30:
                from web.utils import crear_notificacion_ausencia_curso
                
                notificacion = crear_notificacion_ausencia_curso(
                    curso=curso,
                    fecha=fecha,
                    ausentes_count=num_ausentes,
                    total_alumnos=total_alumnos,
                    usuario_origen=request.user
                )
                
                if notificacion:
                    print(f"✅ Notificación creada para {fecha.strftime('%d/%m/%Y')}: {num_ausentes} ausentes")
        
        messages.success(request, 'Asistencia guardada correctamente.')
    except Exception as e:
        messages.error(request, f'Error al guardar: {str(e)}')
    
    return redirect('tomar_asistencia', curso_id=curso.id)


# Agrega esta función para usar en el template con el filtro |get_item
from django.template.defaulttags import register

# @register.filter
# def get_item(dictionary, key):
#     return dictionary.get(key)


@login_required(login_url='login')
@gestion_completa_requerida
def eliminar_curso(request, id):
    """Eliminar curso (soft delete)"""
    curso = get_object_or_404(Curso, pk=id)
    
    if request.method == "POST":
        try:
            curso.soft_delete(usuario=request.user)
            messages.success(request, f'✅ Curso {curso.nombre} marcado como eliminado')
        except Exception as e:
            messages.error(request, f'❌ Error: {e}')
        
        return redirect('listar_cursos')
    
@login_required(login_url='login')
@gestion_completa_requerida    
def editar_curso(request, curso_id):
    curso = get_object_or_404(Curso, id=curso_id)
    
    if request.method == 'POST':
        form = AltaCursoForm(request.POST, instance=curso)
        if form.is_valid():
            curso_actualizado = form.save()
            messages.success(request, f'Curso "{curso_actualizado.nombre}" actualizado exitosamente.')
            return redirect('listar_cursos')
        else:
            messages.error(request, 'Por favor, corrige los errores en el formulario.')
    else:
        form = AltaCursoForm(instance=curso)
    
    context = {
        'form': form,
        'curso': curso,
    }
    return render(request, 'web/cursos/editar_curso.html', context)

@login_required(login_url='login')
@gestion_completa_requerida    
def eliminar_curso(request, curso_id):
    curso = get_object_or_404(Curso, id=curso_id)
    if request.method == 'POST':
        curso.soft_delete(request.user)
        messages.success(request, f'Curso "{curso.nombre}" eliminado exitosamente.')
        return redirect('listar_cursos')
    
    context = {
        'curso': curso,
    }
    return render(request, 'web/cursos/eliminar_curso.html', context)

@login_required(login_url='login')
def cursos_eliminados(request):
    # Obtener SOLO cursos eliminados (soft delete)
    cursos = Curso.all_objects.filter(eliminado=True).select_related('profesor', 'auxiliar', 'eliminado_por')
   
    # Aplicar filtros
    buscar = request.GET.get('buscar', '')
    tipo = request.GET.get('tipo', '')
    mes = request.GET.get('mes', '')
    
    if buscar:
        cursos = cursos.filter(
            Q(nombre__icontains=buscar) |
            Q(profesor__nombre__icontains=buscar) |
            Q(profesor__apellido__icontains=buscar) |
            Q(auxiliar__nombre__icontains=buscar) |
            Q(auxiliar__apellido__icontains=buscar)
        )
    
    if tipo == 'ELIMINADO':
        cursos = cursos.filter(eliminado=True)
    elif tipo == 'FINALIZADO':
        # Para cursos finalizados (no eliminados pero con fecha pasada)
        cursos = cursos.filter(eliminado=False, fecha_fin__lt=timezone.now().date())
    
    if mes:
        cursos = cursos.filter(fecha_eliminacion__month=mes)
    
    # Ordenar por fecha de eliminación (más recientes primero)
    cursos = cursos.order_by('-fecha_eliminacion')
    
    # Estadísticas - CORREGIDO
    total_cursos = cursos.count()
    hoy = timezone.now()
    
    # Cursos eliminados (todos los de la consulta son eliminados)
    cursos_eliminados = cursos.filter(eliminado=True).count()
    
    # Cursos finalizados (en este contexto, son los que no están eliminados pero tienen fecha pasada)
    cursos_finalizados = cursos.filter(eliminado=False, fecha_fin__lt=hoy.date()).count()
    
    # Cursos eliminados este mes
    cursos_este_mes = cursos.filter(
        fecha_eliminacion__month=hoy.month, 
        fecha_eliminacion__year=hoy.year
    ).count()
    
    # Calcular total de alumnos históricos
    total_alumnos_historicos = 0
    for curso in cursos:
        total_alumnos_historicos += curso.total_alumnos
    
    # Cursos que pueden ser restaurados (todos los eliminados son restaurables)
    cursos_restaurables = cursos.filter(eliminado=True).count()
    
    # Paginación
    page = request.GET.get('page', 1)
    paginator = Paginator(cursos, 15)
    
    try:
        cursos_paginados = paginator.page(page)
    except PageNotAnInteger:
        cursos_paginados = paginator.page(1)
    except EmptyPage:
        cursos_paginados = paginator.page(paginator.num_pages)
    
    context = {
        'cursos': cursos_paginados,
        'total_cursos': total_cursos,
        'cursos_eliminados': cursos_eliminados,  # Asegurar que esta variable esté definida
        'cursos_finalizados': cursos_finalizados,  # Asegurar que esta variable esté definida
        'cursos_este_mes': cursos_este_mes,
        'total_alumnos_historicos': total_alumnos_historicos,
        'cursos_restaurables': cursos_restaurables,
        'today': hoy.date(),
        'page_obj': cursos_paginados,
        'is_paginated': paginator.num_pages > 1,
    }
    
    return render(request, 'web/cursos/cursos_eliminados.html', context)


@login_required(login_url='login')
@gestion_completa_requerida   
def restaurar_curso(request, curso_id):
    """Restaurar un curso eliminado - con template personalizado"""
    try:
        # Buscar con all_objects (incluye eliminados)
        curso = Curso.all_objects.get(id=curso_id, eliminado=True)
    except Curso.DoesNotExist:
        messages.error(request, f'No se encontró el curso con ID {curso_id} o no está eliminado.')
        return redirect('cursos_eliminados')
    
    if request.method == 'POST':
        # Restaurar el curso
        curso.eliminado = False
        curso.activo = True
        curso.save()
        
        # Verificar que ahora se pueda encontrar con el manager normal
        try:
            curso_verificado = Curso.objects.get(id=curso_id)
            messages.success(request, f'Curso "{curso.nombre}" restaurado exitosamente.')
            return redirect('listar_cursos')
        except Curso.DoesNotExist:
            # Si aún no se encuentra, hay un problema con el manager
            messages.error(request, f'Curso restaurado pero no se pudo verificar.')
            return redirect('cursos_eliminados')
    
    # Para GET, renderizar tu template personalizado
    context = {'curso': curso}
    return render(request, 'web/cursos/confirmar_restaurar.html', context)


@login_required(login_url='login')
def curso_eliminado_listar_alumnos(request, curso_id):
    """Listar alumnos de un curso eliminado - versión optimizada"""
    curso = get_object_or_404(Curso.all_objects, id=curso_id)  
    busqueda = request.GET.get("buscar")
    
    # Obtener inscripciones con alumnos relacionados
    inscripciones = Inscripcion.objects.filter(
        curso=curso
    ).select_related('alumno')
    
    # Búsqueda
    if busqueda:
        inscripciones = inscripciones.filter(
            Q(alumno__nombre__icontains=busqueda) | 
            Q(alumno__apellido__icontains=busqueda) |
            Q(alumno__dni__icontains=busqueda) |
            Q(alumno__telefono__icontains=busqueda) |
            Q(alumno__mail__icontains=busqueda)
        )

    # Crear lista de alumnos desde las inscripciones
    alumnos_data = []
    for inscripcion in inscripciones:
        alumnos_data.append({
            'alumno': inscripcion.alumno,
            'inscripcion': inscripcion
        })

    context = {
        'curso': curso,
        'alumnos_data': alumnos_data,
        'total_alumnos': len(alumnos_data),
        'busqueda_actual': busqueda or ''
    }
    return render(request, 'web/cursos/curso_eliminado_listar_alumnos.html', context)


@login_required(login_url='login')
def listar_alumnos_curso_universal(request, curso_id):
    """Listar alumnos de cualquier curso (activo o eliminado) - VISTA UNIVERSAL"""
    curso = get_object_or_404(Curso.all_objects, id=curso_id)
    
    busqueda = request.GET.get("buscar")
    
    # Obtener inscripciones con alumnos relacionados
    inscripciones = Inscripcion.objects.filter(
        curso=curso, 
        activo=True,
        estado__in=['INSCRIPTO', 'CURSANDO']
    ).select_related('alumno')
    
    # Búsqueda
    if busqueda:
        inscripciones = inscripciones.filter(
            Q(alumno__nombre__icontains=busqueda) | 
            Q(alumno__apellido__icontains=busqueda) |
            Q(alumno__dni__icontains=busqueda) |
            Q(alumno__telefono__icontains=busqueda) |
            Q(alumno__mail__icontains=busqueda)
        )

    # Misma lógica que la vista original
    hoy = timezone.now().date()
    mes_actual = hoy.month
    año_actual = hoy.year
    
    alumnos_inscripciones = []
    for inscripcion in inscripciones:
        # Determinar estado de pago
        estado_pago = 'AL_DIA'
        try:
            cuota = CuotaAlumno.objects.get(
                inscripcion=inscripcion,
                mes=mes_actual,
                año=año_actual
            )
            if not cuota.pagada:
                if hoy.day <= 10:
                    estado_pago = 'NARANJA'
                else:
                    estado_pago = 'ROJO'
        except CuotaAlumno.DoesNotExist:
            estado_pago = 'AL_DIA'
        
        # Obtener última asistencia
        ultima_asistencia = Asistencia.objects.filter(
            inscripcion=inscripcion
        ).order_by('-fecha').first()
        
        alumnos_inscripciones.append({
            'inscripcion': inscripcion,
            'alumno': inscripcion.alumno,
            'estado_pago': estado_pago,
            'ultima_asistencia': ultima_asistencia,
        })
    
    context = {
        'curso': curso,
        'alumnos': alumnos_inscripciones,  # Mismo nombre que la vista original
        'busqueda_actual': busqueda or '',
        'es_curso_eliminado': curso.eliminado
    }
    
    # Elegir template según si el curso está eliminado o no
    if curso.eliminado:
        template = 'web/cursos/curso_eliminado_listar_alumnos.html'
    else:
        template = 'web/cursos/listar_alumnos_curso.html'
    
    return render(request, template, context)

@login_required(login_url='login')
def mostrar_curso(request, curso_id):
    """Mostrar detalles completos de un curso con alumnos, notas, asistencias y archivos"""
    curso = get_object_or_404(Curso.all_objects, id=curso_id)
    
    # Obtener inscripciones activas con alumnos relacionados
    inscripciones = Inscripcion.objects.filter(
        curso=curso, 
        activo=True
    ).select_related('alumno')
    
    # Preparar datos de alumnos con sus notas y asistencias
    alumnos_data = []
    for inscripcion in inscripciones:
        # Obtener exámenes del alumno
        examenes = Examen.objects.filter(inscripcion=inscripcion)
        examenes_dict = {examen.tipo: examen for examen in examenes}
        
        # Calcular promedio
        promedio = None
        if examenes.exists():
            total = sum(examen.nota for examen in examenes)
            promedio = total / examenes.count()
        
        # Obtener asistencias del alumno
        asistencias = Asistencia.objects.filter(inscripcion=inscripcion)
        total_asistencias = asistencias.count()
        asistencias_presente = asistencias.filter(presente=True).count()
        porcentaje_asistencia = (asistencias_presente / total_asistencias * 100) if total_asistencias > 0 else 0
        
        # Obtener cuotas del alumno
        cuotas = CuotaAlumno.objects.filter(inscripcion=inscripcion)
        cuotas_pagadas = cuotas.filter(pagada=True).count()
        cuotas_totales = cuotas.count()
        
        alumnos_data.append({
            'inscripcion': inscripcion,
            'alumno': inscripcion.alumno,
            'examenes': examenes_dict,
            'promedio': round(promedio, 2) if promedio else None,
            'total_asistencias': total_asistencias,
            'asistencias_presente': asistencias_presente,
            'porcentaje_asistencia': round(porcentaje_asistencia, 1),
            'cuotas_pagadas': cuotas_pagadas,
            'cuotas_totales': cuotas_totales,
            'estado_pago': 'AL_DIA' if cuotas_pagadas == cuotas_totales else 'PENDIENTE',
        })
    
    # Obtener archivos del curso
    archivos_curso = curso.archivos_curso.all()
    form_archivo = ArchivoCursoForm()
    
    # Estadísticas del curso
    total_alumnos = inscripciones.count()
    promedio_general = None
    porcentaje_asistencia_general = None
    
    if alumnos_data:
        promedios = [alumno['promedio'] for alumno in alumnos_data if alumno['promedio'] is not None]
        if promedios:
            promedio_general = sum(promedios) / len(promedios)
        
        porcentajes = [alumno['porcentaje_asistencia'] for alumno in alumnos_data if alumno['total_asistencias'] > 0]
        if porcentajes:
            porcentaje_asistencia_general = sum(porcentajes) / len(porcentajes)
    
    context = {
        'curso': curso,
        'alumnos_data': alumnos_data,
        'archivos_curso': archivos_curso,
        'form_archivo': form_archivo,
        'total_alumnos': total_alumnos,
        'promedio_general': round(promedio_general, 2) if promedio_general else None,
        'porcentaje_asistencia_general': round(porcentaje_asistencia_general, 1) if porcentaje_asistencia_general else None,
        'hoy': timezone.now().date(),
    }
    
    return render(request, 'web/cursos/mostrar_curso.html', context)

@login_required(login_url='login')
def eliminar_archivo_curso(request, curso_id, archivo_id):
    """Eliminar archivo de curso"""
    curso = get_object_or_404(Curso, pk=curso_id)
    archivo = get_object_or_404(ArchivoCurso, pk=archivo_id, curso=curso)
    
    if request.method == "POST":
        try:
            # Eliminar el archivo físico del sistema de archivos
            archivo.archivo.delete(save=False)
            archivo.delete()
            messages.success(request, '✅ Archivo eliminado exitosamente')
        except Exception as e:
            messages.error(request, f'❌ Error al eliminar archivo: {str(e)}')
        
        return redirect('mostrar_curso', curso_id=curso_id)
    
    return redirect('mostrar_curso', curso_id=curso_id)


##########################################
# VISTAS PARA GESTIÓN DE PERSONAL
##########################################

@login_required(login_url='login')
@gestion_personal_requerida 
def lista_personal(request):
    """Lista todo el personal con filtros"""
    # Obtener el queryset base (sin filtros)
    personal_base = Personal.objects.filter(eliminado=False)
    
    # Aplicar filtros
    form_filtro = PersonalFilterForm(request.GET or None)
    personal_filtrado = personal_base
    
    if form_filtro.is_valid():
        tipo = form_filtro.cleaned_data.get('tipo')
        estado = form_filtro.cleaned_data.get('estado')
        search = form_filtro.cleaned_data.get('search')
        
        if tipo:
            personal_filtrado = personal_filtrado.filter(tipo=tipo)
        
        if estado == 'ACTIVO':
            personal_filtrado = personal_filtrado.filter(activo=True)
        elif estado == 'INACTIVO':
            personal_filtrado = personal_filtrado.filter(activo=False)
        
        if search:
            personal_filtrado = personal_filtrado.filter(
                Q(nombre__icontains=search) |
                Q(apellido__icontains=search) |
                Q(legajo__icontains=search) |
                Q(dni__icontains=search)
            )
    
    # Ordenar el resultado final
    personal_list = personal_filtrado.order_by('tipo', 'apellido', 'nombre')
    
    # Calcular estadísticas de manera inteligente
    # Si hay filtro de estado aplicado, calculamos sobre el conjunto filtrado
    # Si no hay filtro de estado, mostramos estadísticas globales
    if form_filtro.is_valid() and form_filtro.cleaned_data.get('estado'):
        # Con filtro de estado: estadísticas del conjunto filtrado
        total_activos = personal_list.filter(activo=True).count()
        total_inactivos = personal_list.filter(activo=False).count()
    else:
        # Sin filtro de estado: estadísticas globales del base
        total_activos = personal_base.filter(activo=True).count()
        total_inactivos = personal_base.filter(activo=False).count()
    
    context = {
        'personal_list': personal_list,
        'form_filtro': form_filtro,
        'total_activos': total_activos,
        'total_inactivos': total_inactivos,
    }
    return render(request, 'web/personal/lista_personal.html', context)



@login_required(login_url='login')
@gestion_completa_requerida
def crear_personal(request):
    """Crear nuevo personal con asignación automática de grupo"""
    if request.method == 'POST':
        form = PersonalForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                with transaction.atomic():  # Para asegurar consistencia
                    personal = form.save(commit=False)
                    
                    # 1. Guardar primero el personal
                    personal.save()
                    
                    # 2. Crear usuario si se solicitó
                    if form.cleaned_data.get('crear_usuario'):
                        # Generar username automático
                        username = f"{personal.nombre.lower()}.{personal.apellido.lower()}"
                        username = username.replace(' ', '')[:30]
                        
                        # Verificar si el username ya existe
                        contador = 1
                        username_original = username
                        while User.objects.filter(username=username).exists():
                            username = f"{username_original}{contador}"
                            contador += 1
                        
                        # Crear usuario con contraseña temporal
                        password = User.objects.make_random_password(length=10)
                        user = User.objects.create_user(
                            username=username,
                            password=password,
                            first_name=personal.nombre,
                            last_name=personal.apellido,
                            email=personal.mail or '',
                            is_active=True
                        )
                        
                        # 3. ASIGNACIÓN AUTOMÁTICA DE GRUPO
                        # Mapeo entre tipo de personal y nombre de grupo
                        MAPEO_TIPO_A_GRUPO = {
                            'ADMINISTRATIVO': 'Administración',
                            'COORDINADOR': 'Coordinación',
                            'SECRETARIA': 'Secretaría',
                            'CONSULTA': 'Consulta',
                            # Agrega otros tipos según necesites
                        }
                        
                        # Obtener el nombre del grupo según el tipo de personal
                        nombre_grupo = MAPEO_TIPO_A_GRUPO.get(
                            personal.tipo, 
                            'Consulta'  # Grupo por defecto
                        )
                        
                        # Asignar el grupo al usuario
                        grupo, creado = Group.objects.get_or_create(name=nombre_grupo)
                        user.groups.clear()  # Limpiar grupos previos
                        user.groups.add(grupo)
                        
                        # 4. Asociar el usuario al personal
                        personal.user = user
                        personal.save()
                        
                        # 5. Asignar permisos específicos según el tipo
                        if personal.tipo in ['ADMINISTRATIVO', 'COORDINADOR']:
                            # Permisos para administradores y coordinadores
                            permisos_administracion = [
                                'can_manage_staff',
                                'can_manage_courses',
                                'can_manage_students',
                                'can_view_reports',
                                'can_manage_payments',
                            ]
                            
                            for permiso_codename in permisos_administracion:
                                try:
                                    permiso = Permission.objects.get(codename=permiso_codename)
                                    user.user_permissions.add(permiso)
                                except Permission.DoesNotExist:
                                    pass  # El permiso no existe, continuar
                        
                        # 6. Mensaje de éxito con información de credenciales
                        messages.success(request, 
                            f"✅ Personal '{personal.nombre_completo()}' creado correctamente<br>"
                            f"👤 <strong>Usuario:</strong> {username}<br>"
                            f"🔑 <strong>Contraseña temporal:</strong> {password}<br>"
                            f"👥 <strong>Grupo asignado:</strong> {nombre_grupo}"
                        )
                        
                        # 7. Registrar en historial
                        HistorialCambios.objects.create(
                            modelo='Personal',
                            objeto_id=personal.id,
                            accion='CREAR',
                            usuario=request.user,
                            descripcion=f"Personal creado con usuario {username} y grupo {nombre_grupo}"
                        )
                    else:
                        # Si no se crea usuario, solo guardar el personal
                        messages.success(request, 
                            f"✅ Personal '{personal.nombre_completo()}' creado correctamente<br>"
                            f"⚠️ <strong>Nota:</strong> No se creó usuario del sistema. "
                            f"Puedes asignar uno desde la gestión de usuarios."
                        )
                    
                    return redirect('lista_personal')
                    
            except IntegrityError as e:
                messages.error(request, f"❌ Error de integridad: {str(e)}")
            except Exception as e:
                messages.error(request, f"❌ Error al crear personal: {str(e)}")
                import traceback
                print(f"Error detallado: {traceback.format_exc()}")
        else:
            messages.error(request, "❌ Por favor corrige los errores en el formulario.")
    else:
        form = PersonalForm()
    
    context = {
        'form': form,
        'titulo': 'Agregar Personal',
        'boton_texto': 'Crear Personal',
    }
    return render(request, 'web/personal/form_personal.html', context)


@login_required(login_url='login')
@acceso_administrativo_requerido
@permiso_requerido('web.can_edit_staff') 
def editar_personal(request, personal_id):
    """Editar personal existente"""
    personal = get_object_or_404(Personal, pk=personal_id, eliminado=False)
    
    if request.method == 'POST':
        form = PersonalEditForm(request.POST, request.FILES, instance=personal)
        if form.is_valid():
            try:
                personal = form.save(commit=False)
                
                # Crear usuario si se solicitó y no tiene
                if form.cleaned_data.get('crear_usuario') and not personal.user:
                    usuario_creado = personal.crear_usuario_sistema()
                    if usuario_creado:
                        messages.success(request, f"✅ Usuario creado: {usuario_creado.username}")
                
                personal.save()
                
                messages.success(request, f"✅ Personal '{personal.nombre_completo()}' actualizado correctamente")
                return redirect('lista_personal')
                
            except Exception as e:
                messages.error(request, f"❌ Error al actualizar personal: {str(e)}")
        else:
            messages.error(request, "❌ Por favor corrige los errores en el formulario.")
    else:
        form = PersonalEditForm(instance=personal)
        # Si ya tiene usuario, deshabilitar el checkbox
        if personal.user:
            form.fields['crear_usuario'].initial = False
            form.fields['crear_usuario'].disabled = True
            form.fields['crear_usuario'].help_text = "Ya tiene usuario del sistema"
    
    context = {
        'form': form,
        'personal': personal,
        'titulo': f'Editar Personal: {personal.nombre_completo()}',
        'boton_texto': 'Actualizar Personal',
    }
    return render(request, 'web/personal/form_personal.html', context)


@login_required(login_url='login')
@permission_required('web.can_view_staff', raise_exception=True)
def detalle_personal(request, personal_id):
    """Ver detalle del personal"""
    personal = get_object_or_404(Personal, id=personal_id, eliminado=False)
    
    context = {
        'personal': personal,
        'today': timezone.now().date(),
    }
    return render(request, 'web/personal/detalle_personal.html', context)



@login_required(login_url='login')
@rol_requerido(['ADMINISTRATIVO'])
@permiso_requerido('web.can_delete_staff')
def eliminar_personal(request, personal_id):
    """Eliminar personal (soft delete)"""
    personal = get_object_or_404(Personal, pk=personal_id, eliminado=False)
    
    if request.method == 'POST':
        try:
            nombre_completo = personal.nombre_completo()
            personal.soft_delete(request.user)
            messages.success(request, f"✅ Personal '{nombre_completo}' eliminado correctamente")
            return redirect('lista_personal')
        except Exception as e:
            messages.error(request, f"❌ Error al eliminar personal: {str(e)}")
            return redirect('lista_personal')
    
    context = {
        'personal': personal,
    }
    return render(request, 'web/personal/confirmar_eliminar.html', context)

@login_required(login_url='login')
#@permission_required('cursos.can_manage_staff', raise_exception=True)
@permission_required('web.can_manage_staff', raise_exception=True)
def toggle_activo_personal(request, personal_id):
    """Activar/desactivar personal"""
    personal = get_object_or_404(Personal, pk=personal_id, eliminado=False)
    
    try:
        personal.activo = not personal.activo
        personal.save()
        
        estado = "activado" if personal.activo else "desactivado"
        messages.success(request, f"✅ Personal '{personal.nombre_completo()}' {estado} correctamente")
        
    except Exception as e:
        messages.error(request, f"❌ Error al cambiar estado: {str(e)}")
    
    return redirect('lista_personal')

@login_required(login_url='login')
#eit@permission_required('cursos.can_manage_staff', raise_exception=True)
@permission_required('web.can_manage_staff', raise_exception=True)
def restaurar_personal(request, personal_id):
    """Restaurar personal eliminado"""
    personal = get_object_or_404(Personal, pk=personal_id, eliminado=True)
    
    if request.method == 'POST':
        try:
            personal.restore(request.user)
            messages.success(request, f"✅ Personal '{personal.nombre_completo()}' restaurado correctamente")
            return redirect('lista_personal')
        except Exception as e:
            messages.error(request, f"❌ Error al restaurar personal: {str(e)}")
    
    context = {
        'personal': personal,
        'titulo': 'Restaurar Personal'
    }
    return render(request, 'web/personal/confirmar_restaurar.html', context)

##########################################
# VISTAS PARA SISTEMA DE PROFESORES
##########################################

@login_required(login_url='login')
def cursos_profesor(request):
    """Vista para que los profesores vean sus cursos asignados"""
    # Verificar si el usuario es profesor
    es_profesor = request.user.groups.filter(name='Profesores').exists()
    es_administracion = request.user.groups.filter(name='Administración').exists()
    
    # Filtrar cursos según permisos
    if es_profesor:
        # Profesores ven solo sus cursos asignados
        cursos = Curso.objects.filter(profesor__user=request.user, activo=True, eliminado=False)
    elif es_administracion:
        # Administración ve todos los cursos activos
        cursos = Curso.objects.filter(activo=True, eliminado=False)
    else:
        # Usuarios sin permisos específicos
        cursos = Curso.objects.none()
        messages.warning(request, 'No tienes permisos para ver cursos')
    
    # Aplicar filtros
    form_filtro = FiltroCursoForm(request.GET or None)
    if form_filtro.is_valid():
        estado = form_filtro.cleaned_data.get('estado')
        mes = form_filtro.cleaned_data.get('mes')
        
        if estado == 'ACTIVO':
            cursos = cursos.filter(fecha_inicio__lte=timezone.now().date(), fecha_fin__gte=timezone.now().date())
        elif estado == 'FINALIZADO':
            cursos = cursos.filter(fecha_fin__lt=timezone.now().date())
        elif estado == 'FUTURO':
            cursos = cursos.filter(fecha_inicio__gt=timezone.now().date())
        
        if mes:
            cursos = cursos.filter(fecha_inicio__month=mes)
    
    context = {
        'cursos': cursos.order_by('fecha_inicio'),
        'form_filtro': form_filtro,
        'es_profesor': es_profesor,
        'es_administracion': es_administracion,
        'hoy': timezone.now().date(),
    }
    return render(request, 'web/profesores/cursos_profesor.html', context)

@login_required(login_url='login')
def gestionar_curso(request, curso_id):
    """Vista para gestionar un curso específico (tomar lista, poner notas)"""
    curso = get_object_or_404(Curso, pk=curso_id, activo=True, eliminado=False)
    
    # Verificar permisos
    es_profesor_curso = curso.profesor and curso.profesor.user == request.user
    es_administracion = request.user.groups.filter(name='Administración').exists()
    
    if not (es_profesor_curso or es_administracion):
        messages.error(request, 'No tienes permisos para gestionar este curso')
        return redirect('cursos_profesor')
    
    # Obtener inscripciones activas
    inscripciones = Inscripcion.objects.filter(
        curso=curso,
        activo=True,
        estado__in=['INSCRIPTO', 'CURSANDO']
    ).select_related('alumno')
    
    total_inscriptos = inscripciones.count()

    # Asistencias totales y presentes
    asistencias_totales = Asistencia.objects.filter(inscripcion__curso=curso).count()
    asistencias_presentes = Asistencia.objects.filter(inscripcion__curso=curso, presente=True).count()
    porcentaje_asistencia = (asistencias_presentes / asistencias_totales * 100) if asistencias_totales > 0 else 0

    # Próximas clases
    hoy = date.today()
    if curso.fecha_inicio and curso.fecha_fin:
    # Usar función existente o implementar lógica
        from web.utils import generar_fechas_clase
        todas_fechas = generar_fechas_clase(curso.fecha_inicio, curso.fecha_fin, curso.dias)
        proximas_clases = [f for f in todas_fechas if f >= hoy][:5]
    else:
        proximas_clases = []
    # Obtener cuotas del mes actual para cada alumno
    mes_actual = timezone.now().month
    año_actual = timezone.now().year
    for inscripcion in inscripciones:
        # Verificar si tiene cuota pagada este mes
        cuota_pagada = CuotaAlumno.objects.filter(
            inscripcion=inscripcion,
            mes=mes_actual,
            año=año_actual,
            pagada=True
        ).exists()
        inscripcion.cuota_pagada = cuota_pagada
        
        # Obtener asistencia de hoy
        hoy = timezone.now().date()
        asistencia_hoy = Asistencia.objects.filter(
            inscripcion=inscripcion,
            fecha=hoy
        ).first()
        inscripcion.asistencia_hoy = asistencia_hoy
    
    # Procesar toma de lista
    if request.method == 'POST' and 'tomar_lista' in request.POST:
        fecha_lista = request.POST.get('fecha_lista', timezone.now().date())
        
        for inscripcion in inscripciones:
            campo_presente = f'presente_{inscripcion.id}'
            campo_observaciones = f'observaciones_{inscripcion.id}'
            
            presente = request.POST.get(campo_presente) == 'on'
            observaciones = request.POST.get(campo_observaciones, '')
            
            # Crear o actualizar registro de asistencia
            asistencia, created = Asistencia.objects.get_or_create(
                inscripcion=inscripcion,
                fecha=fecha_lista,
                defaults={
                    'presente': presente,
                    'observaciones': observaciones,
                    'registrado_por': request.user
                }
            )
            
            if not created:
                asistencia.presente = presente
                asistencia.observaciones = observaciones
                asistencia.save()
        
        messages.success(request, f'✅ Lista tomada para la fecha {fecha_lista}')
        return redirect('gestionar_curso', curso_id=curso_id)
    
    # Procesar notas
    if request.method == 'POST' and 'guardar_nota' in request.POST:
        inscripcion_id = request.POST.get('inscripcion_id')
        nota_final = request.POST.get('nota_final')
        observaciones = request.POST.get('observaciones', '')
        
        if inscripcion_id and nota_final:
            try:
                inscripcion = Inscripcion.objects.get(pk=inscripcion_id, curso=curso)
                inscripcion.nota_final = nota_final
                if float(nota_final) >= 6:  # Aprobar con 6 o más
                    inscripcion.estado = 'APROBADO'
                else:
                    inscripcion.estado = 'REPROBADO'
                inscripcion.observaciones = observaciones
                inscripcion.save()
                
                messages.success(request, f'✅ Nota guardada para {inscripcion.alumno.nombre_completo()}')
            except (Inscripcion.DoesNotExist, ValueError) as e:
                messages.error(request, f'❌ Error al guardar nota: {e}')
        
        return redirect('gestionar_curso', curso_id=curso_id)
    
    context = {
    'curso': curso,
    'inscripciones': inscripciones,
    'hoy': hoy,
    'mes_actual': mes_actual,
    'año_actual': año_actual,
    'es_profesor_curso': es_profesor_curso,
    'total_inscriptos': total_inscriptos,
    'asistencias_totales': asistencias_totales,
    'asistencias_presentes': asistencias_presentes,
    'porcentaje_asistencia': round(porcentaje_asistencia, 1),
    'proximas_clases': proximas_clases,
    }
    return render(request, 'web/profesores/gestionar_curso.html', context)

@login_required(login_url='login')
def reporte_asistencias(request, curso_id):
    curso = get_object_or_404(Curso, pk=curso_id, activo=True, eliminado=False)
    
    # Verificar permisos
    es_profesor_curso = curso.profesor and curso.profesor.user == request.user
    es_administracion = request.user.groups.filter(name='Administración').exists()
    if not (es_profesor_curso or es_administracion):
        messages.error(request, 'No tienes permisos para ver este reporte')
        return redirect('cursos_profesor')
    
    # Obtener fechas del filtro GET o usar las del curso
    fecha_inicio = request.GET.get('fecha_inicio', curso.fecha_inicio)
    fecha_fin = request.GET.get('fecha_fin', curso.fecha_fin)
    
    # Obtener asistencias en el rango de fechas
    asistencias_qs = Asistencia.objects.filter(
        inscripcion__curso=curso,
        fecha__range=[fecha_inicio, fecha_fin]
    ).select_related('inscripcion__alumno')
    
    # --- Estadísticas generales ---
    total_registros = asistencias_qs.count()
    presentes = asistencias_qs.filter(presente=True).count()
    ausentes = total_registros - presentes
    porcentaje_asistencia = (presentes / total_registros * 100) if total_registros > 0 else 0
    
    # --- Fechas únicas ordenadas (para el detalle) ---
    fechas_unicas = asistencias_qs.values_list('fecha', flat=True).distinct().order_by('fecha')
    
    # --- Inscripciones activas y con estado válido (para el reporte) ---
    inscripciones_activas = Inscripcion.objects.filter(
        curso=curso,
        activo=True,
        estado__in=['INSCRIPTO', 'CURSANDO']      # Ajusta los valores según tu elección
    ).select_related('alumno').order_by(
        'alumno__apellido', 'alumno__nombre'      # Orden alfabético por apellido y nombre
    )
    
    # --- Diccionario de asistencias para acceso rápido en template ---
    asistencias_dict = {}
    for a in asistencias_qs:
        if a.inscripcion_id not in asistencias_dict:
            asistencias_dict[a.inscripcion_id] = {}
        asistencias_dict[a.inscripcion_id][a.fecha] = a
    
    # --- Estadísticas por alumno (ya existente) ---
    alumnos_stats = {}
    for inscripcion in inscripciones_activas:
        asistencias_alumno = asistencias_qs.filter(inscripcion=inscripcion)
        total_clases = asistencias_alumno.count()
        presentes_alumno = asistencias_alumno.filter(presente=True).count()
        
        alumnos_stats[inscripcion.id] = {
            'alumno': inscripcion.alumno,
            'total_clases': total_clases,
            'presentes': presentes_alumno,
            'ausentes': total_clases - presentes_alumno,
            'porcentaje_asistencia': (presentes_alumno / total_clases * 100) if total_clases > 0 else 0
        }
    
    context = {
        'curso': curso,
        'asistencias': asistencias_dict,          # Diccionario anidado para el filtro dict_key
        'alumnos_stats': alumnos_stats,
        'fecha_inicio': fecha_inicio,
        'fecha_fin': fecha_fin,
        'total_registros': total_registros,       # Para la tarjeta "Total Registros"
        'asistencias_presentes': presentes,
        'asistencias_ausentes': ausentes,
        'porcentaje_asistencia': porcentaje_asistencia,
        'fechas_unicas': fechas_unicas,
        'hoy': date.today(),                       # Para el nombre del archivo Excel
    }
    return render(request, 'web/profesores/reporte_asistencias.html', context)


def calcular_estado_pago(inscripcion, hoy):
    """Calcula el estado de pago del alumno"""
    estado_pago = 'AL_DIA'
    try:
        cuota = CuotaAlumno.objects.get(
            inscripcion=inscripcion,
            mes=hoy.month,
            año=hoy.year
        )
        if not cuota.pagada:
            if hoy.day <= 10:
                estado_pago = 'NARANJA'
            else:
                estado_pago = 'ROJO'
    except CuotaAlumno.DoesNotExist:
        estado_pago = 'AL_DIA'
    
    return estado_pago



##########################################
# VISTAS PARA SISTEMA DE PAGOS
##########################################

# @login_required(login_url='login')
# def pago_create(request):
#     """Crear nuevo pago con detalles"""
#     if request.method == 'POST':
#         pago_form = PagoForm(request.POST)
#         detalle_pago_formset = DetallePagoFormSet(request.POST)

#         flagPagoObligatorio1 = False

#         if pago_form.is_valid() and detalle_pago_formset.is_valid():

#             if detalle_pago_formset.is_valid():
#                 for form in detalle_pago_formset:
#                     if form.cleaned_data.get('curso') is not None and form.cleaned_data.get('precio') is not None and form.cleaned_data.get('cantidad') is not None:
#                         pago = pago_form.save()
#                         detalle_pago = form.save(commit=False)
#                         detalle_pago.pago = pago
#                         detalle_pago.precio_total = detalle_pago.cantidad * detalle_pago.precio
#                         detalle_pago.save()
#                         flagPagoObligatorio1 = True
#                     else:
#                         if form.cleaned_data.get('curso') is None and flagPagoObligatorio1 == False:
#                             error_message = "Error en el formulario de detalle de pago. Por favor, revise los campos."
#                             context = {'pago_form': pago_form, 'detalle_pago_formset': detalle_pago_formset, 'error_message': error_message}                            
#                             return render(request, 'web/pagos/pago_alta.html', context)
#                         else:
#                             return redirect('pago_mensaje', pago_id=pago.pk)
#             else:
#                 error_message = "Error en el formulario de detalle de pago. Por favor, revise los campos."
#                 context = {'pago_form': pago_form, 'detalle_pago_formset': detalle_pago_formset, 'error_message': error_message}
#         else:
#             error_message = "Error, Detalle de Pago. Si selecciona un curso, complete el resto de los campos"
#             context = {'pago_form': pago_form, 'detalle_pago_formset': detalle_pago_formset, 'error_message': error_message}
#             return render(request, 'web/pagos/pago_alta.html', context)
#     else:
#         pago_form = PagoForm()
#         detalle_pago_formset = DetallePagoFormSet()

#     return render(request, 'web/pagos/pago_alta.html', {
#         'pago_form': pago_form,
#         'detalle_pago_formset': detalle_pago_formset,
#     })

def pago_create(request):
    """Redirige a la nueva vista de facturación"""
    from django.shortcuts import redirect
    return redirect('facturacion:registrar_pago')

@login_required(login_url='login')
def get_precio_curso(request):
    """Obtener precio de curso para AJAX"""
    curso_id = request.GET.get('curso_id')
    try:
        curso = Curso.objects.get(id=curso_id)
        return JsonResponse({'precio': float(curso.precio)})
    except Curso.DoesNotExist:
        return JsonResponse({'precio': 0.0})
    except Exception as e:
        print(f"Error en get_precio_curso: {e}")
        return JsonResponse({'precio': 0.0})

@login_required(login_url='login')
def pago_update(request, pk):
    """Actualizar pago existente"""
    pago = get_object_or_404(Pago, pk=pk)
    if request.method == "POST":
        form = PagoForm(request.POST, instance=pago)
        if form.is_valid():
            form.save()
            messages.success(request, '✅ Pago actualizado exitosamente')
            return redirect('listar_pagos')
    else:
        form = PagoForm(instance=pago)
    return render(request, 'web/pagos/pago_form.html', {'form': form})

@login_required(login_url='login')
def pago_delete(request, pk):
    """Eliminar pago"""
    pago = get_object_or_404(Pago, pk=pk)
    if request.method == "POST":
        pago.delete()
        messages.success(request, '✅ Pago eliminado exitosamente')
        return redirect('listar_pagos')
    return render(request, 'web/pagos/pago_confirm_delete.html', {'pago': pago})

##########################################
# VISTAS PARA CERTIFICADOS
##########################################

@login_required(login_url='login')
def generar_certificado_pdf(request, inscripcion_id):
    """Genera un certificado PDF para una inscripción aprobada"""
    inscripcion = get_object_or_404(
        Inscripcion, 
        pk=inscripcion_id, 
        activo=True,
        estado='APROBADO'
    )
    
    # Verificar si ya existe un certificado
    certificado_existente = Certificado.objects.filter(inscripcion=inscripcion).first()
    
    if not certificado_existente:
        # Crear nuevo certificado
        certificado = Certificado.objects.create(
            inscripcion=inscripcion,
            emitido_por=request.user
        )
    else:
        certificado = certificado_existente
    
    # Crear el PDF
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, 
        pagesize=A4,
        rightMargin=2*cm,
        leftMargin=2*cm,
        topMargin=2*cm,
        bottomMargin=2*cm
    )
    
    # Estilos
    styles = getSampleStyleSheet()
    estilo_titulo = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        spaceAfter=30,
        alignment=1,
        textColor=colors.HexColor('#2C3E50')
    )
    
    estilo_subtitulo = ParagraphStyle(
        'CustomSubtitle',
        parent=styles['Heading2'],
        fontSize=14,
        spaceAfter=20,
        alignment=1,
        textColor=colors.HexColor('#34495E')
    )
    
    estilo_cuerpo = ParagraphStyle(
        'CustomBody',
        parent=styles['Normal'],
        fontSize=12,
        spaceAfter=12,
        alignment=4,
        textColor=colors.HexColor('#2C3E50')
    )
    
    estilo_destacado = ParagraphStyle(
        'CustomHighlight',
        parent=styles['Normal'],
        fontSize=13,
        spaceAfter=15,
        alignment=1,
        textColor=colors.HexColor('#E74C3C'),
        backColor=colors.HexColor('#FDF2E9'),
        borderPadding=10,
        borderColor=colors.HexColor('#F5B7B1'),
        borderWidth=1
    )
    
    # Contenido del PDF
    story = []
    
    # Encabezado
    story.append(Paragraph("INSTITUTO ACADÉMICO DE CAPACITACIÓN LABORAL", estilo_titulo))
    story.append(Spacer(1, 20))
    
    # Línea decorativa
    story.append(Paragraph("<hr/>", styles['Normal']))
    story.append(Spacer(1, 30))
    
    # Título del certificado
    story.append(Paragraph("CERTIFICADO DE APROBACIÓN", estilo_subtitulo))
    story.append(Spacer(1, 40))
    
    # Cuerpo del certificado
    texto_certificado = f"""
    El Instituto Académico de Capacitación Laboral certifica que
    <b>{inscripcion.alumno.nombre_completo().upper()}</b>
    con DNI <b>{inscripcion.alumno.dni}</b> ha aprobado satisfactoriamente el curso de
    """
    story.append(Paragraph(texto_certificado, estilo_cuerpo))
    story.append(Spacer(1, 20))
    
    # Nombre del curso destacado
    story.append(Paragraph(f"«{inscripcion.curso.nombre.upper()}»", estilo_destacado))
    story.append(Spacer(1, 20))
    
    # Detalles del curso
    detalles_curso = f"""
    Con una duración de <b>{inscripcion.curso.duracion}</b>, 
    impartido los días <b>{inscripcion.curso.dias}</b> en el horario de <b>{inscripcion.curso.horario}</b>,
    durante el período comprendido entre <b>{inscripcion.fecha_inicio.strftime('%d/%m/%Y')}</b> 
    y <b>{inscripcion.fecha_fin.strftime('%d/%m/%Y')}</b>.
    """
    story.append(Paragraph(detalles_curso, estilo_cuerpo))
    story.append(Spacer(1, 20))
    
    # Nota final si existe
    if inscripcion.nota_final:
        story.append(Paragraph(
            f"Obteniendo una calificación final de <b>{inscripcion.nota_final}</b> puntos.", 
            estilo_cuerpo
        ))
        story.append(Spacer(1, 20))
    
    # Fecha de emisión
    fecha_emision = timezone.now().strftime("%d de %B de %Y")
    story.append(Paragraph(
        f"Se expide el presente certificado en la ciudad de Buenos Aires, a los {fecha_emision}.",
        estilo_cuerpo
    ))
    story.append(Spacer(1, 50))
    
    # Firmas
    datos_firmas = [
        ['', ''],
        ['_________________________', '_________________________'],
        ['Director Académico', 'Coordinador del Curso'],
    ]
    
    tabla_firmas = Table(datos_firmas, colWidths=[8*cm, 8*cm])
    tabla_firmas.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('TOPPADDING', (0, 0), (-1, -1), 10),
    ]))
    
    story.append(tabla_firmas)
    story.append(Spacer(1, 30))
    
    # Código de verificación
    story.append(Paragraph(
        f"<i>Código de verificación: {certificado.codigo_certificado}</i>",
        ParagraphStyle(
            'CustomCode',
            parent=styles['Normal'],
            fontSize=9,
            alignment=1,
            textColor=colors.grey
        )
    ))
    
    # Generar PDF
    doc.build(story)
    
    # Guardar el PDF en el modelo
    from django.core.files.base import ContentFile
    pdf_content = ContentFile(buffer.getvalue())
    certificado.archivo_pdf.save(f'certificado_{certificado.codigo_certificado}.pdf', pdf_content)
    
    # Preparar respuesta para descarga
    buffer.seek(0)
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="certificado_{certificado.codigo_certificado}.pdf"'
    
    # Registrar en historial
    HistorialCambios.objects.create(
        modelo='Certificado',
        objeto_id=certificado.id,
        accion='CREAR',
        usuario=request.user,
        descripcion=f"Certificado generado: {certificado.codigo_certificado}"
    )
    
    return response

@login_required(login_url='login')
def ver_certificado(request, codigo):
    """Ver información de un certificado"""
    certificado = get_object_or_404(Certificado, codigo_certificado=codigo)
    
    context = {
        'certificado': certificado,
    }
    return render(request, 'web/certificados/ver_certificado.html', context)

@login_required(login_url='login')
def descargar_certificado(request, codigo):
    """Descargar el archivo PDF del certificado"""
    certificado = get_object_or_404(Certificado, codigo_certificado=codigo)
    
    if certificado.archivo_pdf:
        response = HttpResponse(certificado.archivo_pdf, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{certificado.archivo_pdf.name}"'
        return response
    else:
        messages.error(request, 'El archivo PDF no está disponible')
        return redirect('ver_certificado', codigo=codigo)

def verificar_certificado(request):
    """Página pública para verificar certificados"""
    codigo = request.GET.get('codigo', '')
    certificado = None
    
    if codigo:
        try:
            certificado = Certificado.objects.get(codigo_certificado=codigo)
        except Certificado.DoesNotExist:
            messages.error(request, 'Certificado no encontrado')
    
    context = {
        'certificado': certificado,
        'codigo_buscado': codigo,
    }
    return render(request, 'web/certificados/verificar_certificado.html', context)

##########################################
# VISTAS PARA BACKUPS
##########################################

@login_required(login_url='login')
def listar_backups_view(request):
    """Vista para listar todos los backups"""
    modelo_filtro = request.GET.get('modelo', '')
    estado_filtro = request.GET.get('estado', '')
    
    backups = listar_backups(
        modelo=modelo_filtro if modelo_filtro else None,
        estado=estado_filtro if estado_filtro else None
    )
    
    estadisticas = obtener_estadisticas_backups()
    
    context = {
        'backups': backups,
        'estadisticas': estadisticas,
        'modelos': ['Alumno', 'Profesor', 'Curso'],
        'estados': ['ACTIVO', 'RESTAURADO', 'ELIMINADO'],
        'filtro_actual': {
            'modelo': modelo_filtro,
            'estado': estado_filtro,
        }
    }
    
    return render(request, 'web/backups/listar_backups.html', context)

@login_required(login_url='login')
def restaurar_backup_view(request, backup_id):
    """Vista para restaurar un backup"""
    backup = get_object_or_404(BackupGenerico, id=backup_id)
    
    if request.method == "POST":
        try:
            nueva_instancia, mensaje = restaurar_desde_backup(
                backup_id=backup_id,
                usuario=request.user
            )
            
            if nueva_instancia:
                messages.success(request, mensaje)
                
                # Redirigir según el tipo de modelo
                if backup.modelo == 'Alumno':
                    return redirect('mostrar_alumno', id=nueva_instancia.id)
                elif backup.modelo == 'Profesor':
                    return redirect('mostrar_profesor', id=nueva_instancia.id)
                elif backup.modelo == 'Curso':
                    return redirect('listar_cursos')
                else:
                    return redirect('listar_backups')
            else:
                messages.error(request, mensaje)
                
        except Exception as e:
            messages.error(request, f'❌ Error al restaurar: {e}')
        
        return redirect('listar_backups')
    
    # GET - Mostrar confirmación
    context = {
        'backup': backup,
        'info_objeto': backup.get_info_objeto()
    }
    return render(request, 'web/backups/confirmar_restauracion.html', context)

@login_required(login_url='login') 
def eliminar_backup_view(request, backup_id):
    """Elimina permanentemente un backup (no el objeto original)"""
    backup = get_object_or_404(BackupGenerico, id=backup_id)
    
    if request.method == "POST":
        try:
            backup.delete()
            messages.success(request, '✅ Backup eliminado permanentemente')
        except Exception as e:
            messages.error(request, f'❌ Error al eliminar backup: {e}')
        
        return redirect('listar_backups')
    
    context = {
        'backup': backup,
        'info_objeto': backup.get_info_objeto()
    }
    return render(request, 'web/backups/confirmar_eliminar_backup.html', context)

##########################################
# VISTAS OBSOLETAS O POR IMPLEMENTAR
##########################################

@login_required(login_url='login')
def alta_inscripcion(request, id):
    """Vista antigua - mantener por compatibilidad"""
    alumno = get_object_or_404(Alumno, pk=id)
    context = {}
    
    if request.method == "GET":
        form = AltaInscripcionForm(instance=alumno)
    else:
        form = AltaInscripcionForm(request.POST, request.FILES, instance=alumno)
        if form.is_valid():
            try:
                form.save()
                messages.success(request, '✅ El alumno fue inscrito con éxito')
                return redirect('listar_alumno')
            except Exception as e:
                messages.error(request, f'❌ Error al inscribir alumno: {e}')
    
    context = {
        'form': form,
    }
    return render(request, 'web/alta_inscripcion.html', context)

##########################################
# BUSCADOR GLOBAL
##########################################


@login_required
def buscar_global(request):
    query = request.GET.get('q', '')
    resultados = {}
    
    if query:
        from .models import Alumno, Profesor, Curso  # Ajusta según tus modelos
        
        # Búsqueda en alumnos
        resultados['alumnos'] = Alumno.objects.filter(
            Q(nombre__icontains=query) | 
            Q(apellido__icontains=query) |
            Q(dni__icontains=query)
        )[:5]
        
        # Búsqueda en profesores
        resultados['profesores'] = Profesor.objects.filter(
            Q(nombre__icontains=query) | 
            Q(apellido__icontains=query)
        )[:5]
        
        # Búsqueda en cursos
        resultados['cursos'] = Curso.objects.filter(
            Q(nombre__icontains=query) |
            Q(descripcion__icontains=query)
        )[:5]
    
    return render(request, 'web/buscar_global.html', {
        'query': query,
        'resultados': resultados
    })
    
##########################################
# PERMISOS GENERALES DEL SISTEMA
##########################################
    
# Añade esto al final de models.py, antes de las funciones
class PermisosSistema:
    """
    Clase centralizada para gestionar todos los permisos personalizados del sistema
    Sigue el principio de mínimo privilegio
    """
    
    # GESTIÓN DE PERSONAL (Niveles de acceso)
    CAN_VIEW_STAFF = 'web.can_view_staff'           # Ver personal
    CAN_ADD_STAFF = 'web.can_add_staff'             # Agregar personal  
    CAN_EDIT_STAFF = 'web.can_edit_staff'           # Editar personal
    CAN_DELETE_STAFF = 'web.can_delete_staff'       # Eliminar personal (soft delete)
    CAN_MANAGE_STAFF = 'web.can_manage_staff'       # Gestión completa (existente)
    
    # GESTIÓN DE USUARIOS Y PERMISOS
    CAN_VIEW_USERS = 'auth.can_view_users'          # Ver usuarios del sistema
    CAN_EDIT_USERS = 'auth.can_edit_users'          # Editar usuarios
    CAN_MANAGE_USER_ACCOUNTS = 'auth.can_manage_user_accounts'  # Crear/eliminar usuarios
    CAN_MANAGE_PERMISSIONS = 'auth.can_manage_permissions'      # Asignar permisos
    
    # GESTIÓN ACADÉMICA
    CAN_VIEW_COURSES = 'web.can_view_courses'       # Ver cursos
    CAN_MANAGE_COURSES = 'web.can_manage_courses'   # Gestionar cursos (existente)
    CAN_VIEW_OWN_COURSES = 'web.can_view_own_courses' # Ver cursos propios
    
    # GESTIÓN DE ALUMNOS
    CAN_VIEW_STUDENTS = 'web.can_view_students'     # Ver alumnos
    CAN_MANAGE_STUDENTS = 'web.can_manage_students' # Gestionar alumnos
    
    # AUDITORÍA Y SEGURIDAD
    CAN_VIEW_AUDIT_LOGS = 'web.can_view_audit_logs' # Ver logs del sistema
    CAN_VIEW_SECURITY_LOGS = 'web.can_view_security_logs' # Ver logs de seguridad
    
    # REPORTES
    CAN_VIEW_REPORTS = 'web.can_view_reports'       # Ver reportes
    CAN_GENERATE_REPORTS = 'web.can_generate_reports' # Generar reportes
    
    # SISTEMA
    CAN_MANAGE_SYSTEM = 'web.can_manage_system'     # Configuración del sistema

    @classmethod
    def get_all_permissions(cls):
        """Retorna todos los permisos definidos"""
        return [value for key, value in cls.__dict__.items() 
                if not key.startswith('_') and isinstance(value, str)]
        
        
##########################################
# AUDITORIAS
##########################################

@login_required
@permission_required('web.can_view_audit_logs', raise_exception=True)
def ver_logs_auditoria(request):
    """Vista para ver logs de auditoría del sistema"""
    from .models import HistorialCambios
    
    # Filtros
    fecha_desde = request.GET.get('fecha_desde')
    fecha_hasta = request.GET.get('fecha_hasta')
    modelo_filter = request.GET.get('modelo')
    accion_filter = request.GET.get('accion')
    usuario_filter = request.GET.get('usuario')
    
    logs = HistorialCambios.objects.all().select_related('usuario').order_by('-fecha')
    
    # Aplicar filtros
    if fecha_desde:
        logs = logs.filter(fecha__date__gte=fecha_desde)
    if fecha_hasta:
        logs = logs.filter(fecha__date__lte=fecha_hasta)
    if modelo_filter and modelo_filter != 'TODOS':
        logs = logs.filter(modelo=modelo_filter)
    if accion_filter and accion_filter != 'TODOS':
        logs = logs.filter(accion=accion_filter)
    if usuario_filter:
        logs = logs.filter(usuario__username__icontains=usuario_filter)
    
    # Estadísticas
    total_logs = logs.count()
    modelos_disponibles = HistorialCambios.objects.values_list('modelo', flat=True).distinct()
    
    # Paginación
    paginator = Paginator(logs, 50)  # 50 logs por página
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'total_logs': total_logs,
        'modelos_disponibles': modelos_disponibles,
        'fecha_desde': fecha_desde,
        'fecha_hasta': fecha_hasta,
        'modelo_filter': modelo_filter,
        'accion_filter': accion_filter,
        'usuario_filter': usuario_filter,
    }
    
    return render(request, 'web/auditoria/logs_auditoria.html', context)

@login_required
@permission_required('web.can_view_security_logs', raise_exception=True)
def ver_logs_seguridad(request):
    """Vista para ver logs de seguridad (cambios de contraseña, etc.)"""
    from django.contrib.auth.models import User
    from .models import PasswordChangeLog
    
    logs = PasswordChangeLog.objects.all().select_related('user', 'changed_by').order_by('-changed_at')
    
    # Filtros
    usuario_filter = request.GET.get('usuario')
    fecha_desde = request.GET.get('fecha_desde')
    fecha_hasta = request.GET.get('fecha_hasta')
    
    if usuario_filter:
        logs = logs.filter(user__username__icontains=usuario_filter)
    if fecha_desde:
        logs = logs.filter(changed_at__date__gte=fecha_desde)
    if fecha_hasta:
        logs = logs.filter(changed_at__date__lte=fecha_hasta)
    
    # Paginación
    paginator = Paginator(logs, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'total_logs': logs.count(),
    }
    
    return render(request, 'web/auditoria/logs_seguridad.html', context)


@login_required(login_url='login')
def debug_cursos_eliminados(request):
    """Vista temporal para diagnosticar cursos eliminados"""
    from django.http import JsonResponse
    
    cursos_all = Curso.all_objects.filter(eliminado=True)
    
    data = {
        'total_eliminados_all_objects': cursos_all.count(),
        'cursos_eliminados': [
            {
                'id': curso.id,
                'nombre': curso.nombre,
                'eliminado': curso.eliminado,
                'activo': curso.activo,
            }
            for curso in cursos_all
        ]
    }
    
    return JsonResponse(data)

##########################################
# NOTIFICACIONES
##########################################

@login_required
def notificaciones_dropdown(request):
    """Vista para cargar las notificaciones en el dropdown del navbar"""
    # Obtener notificaciones pendientes y no eliminadas del usuario
    notificaciones = Notificacion.objects.filter(
        usuario_destino=request.user,
        estado='PENDIENTE',
        eliminada=False
    ).order_by('-fecha_creacion')[:10]  # Últimas 10 notificaciones

    # Serializar las notificaciones para el dropdown
    notificaciones_data = []
    for notificacion in notificaciones:
        notificaciones_data.append({
            'id': notificacion.id,
            'titulo': notificacion.titulo,
            'mensaje': notificacion.mensaje,
            'fecha_creacion': notificacion.fecha_creacion.strftime("%d/%m/%Y %H:%M"),
            'prioridad': notificacion.prioridad,
            'tipo_icono': notificacion.tipo.icono,
            'tipo_color': notificacion.tipo.color,
            'origen': notificacion.usuario_origen.get_full_name() if notificacion.usuario_origen else 'Sistema'
        })

    # Contar notificaciones pendientes para el badge
    pendientes_count = Notificacion.objects.filter(
        usuario_destino=request.user,
        estado='PENDIENTE',
        eliminada=False
    ).count()

    return JsonResponse({
        'notificaciones': notificaciones_data,
        'pendientes_count': pendientes_count
    })
    
    
# En web/views.py

@login_required
@personal_required
def marcar_leida(request, id):
    """Toggle para marcar como leída/no leída"""
    notificacion = get_object_or_404(Notificacion, id=id)
    
    # Verificar que el usuario es el destinatario o coordinador
    if notificacion.usuario_destino == request.user or es_coordinador(request.user):
        if notificacion.estado == 'LEIDA':
            # Si ya está leída, volver a pendiente
            notificacion.estado = 'PENDIENTE'
            notificacion.fecha_leida = None
            mensaje = "Notificación marcada como no leída"
        else:
            # Marcar como leída (desde pendiente o realizada)
            notificacion.estado = 'LEIDA'
            notificacion.fecha_leida = timezone.now()
            mensaje = "Notificación marcada como leída"
        
        notificacion.save()
        messages.success(request, mensaje)
    else:
        messages.error(request, "No tienes permiso para modificar esta notificación")
    
    return redirect('listar_notificaciones')

@login_required
@personal_required
def marcar_realizada(request, id):
    """Toggle para marcar como realizada/no realizada"""
    notificacion = get_object_or_404(Notificacion, id=id)
    
    # Verificar que el usuario es el destinatario o coordinador
    if notificacion.usuario_destino == request.user or es_coordinador(request.user):
        if notificacion.estado == 'REALIZADA':
            # Si ya está realizada, volver a leída
            notificacion.estado = 'LEIDA'
            notificacion.fecha_realizado = None
            mensaje = "Notificación marcada como no realizada"
        else:
            # Marcar como realizada (desde pendiente o leída)
            notificacion.estado = 'REALIZADA'
            notificacion.fecha_realizado = timezone.now()
            
            # Si estaba pendiente, también marcarla como leída
            if notificacion.estado == 'PENDIENTE':
                notificacion.fecha_leida = timezone.now()
            
            mensaje = "Notificación marcada como realizada"
        
        notificacion.save()
        messages.success(request, mensaje)
    else:
        messages.error(request, "No tienes permiso para modificar esta notificación")
    
    return redirect('listar_notificaciones')


@login_required
@personal_required
def cambiar_estado_notificacion(request, id):
    """Cambiar estado de notificación de forma más flexible"""
    notificacion = get_object_or_404(Notificacion, id=id)
    nuevo_estado = request.GET.get('estado')
    
    # Estados válidos
    estados_validos = ['PENDIENTE', 'LEIDA', 'REALIZADA']
    
    if nuevo_estado in estados_validos:
        # Verificar permisos
        if notificacion.usuario_destino == request.user or es_coordinador(request.user):
            estado_anterior = notificacion.estado
            notificacion.estado = nuevo_estado
            
            # Actualizar fechas según el estado
            if nuevo_estado == 'LEIDA' and estado_anterior != 'LEIDA':
                notificacion.fecha_leida = timezone.now()
            elif nuevo_estado == 'REALIZADA':
                notificacion.fecha_realizado = timezone.now()
                if estado_anterior == 'PENDIENTE':
                    notificacion.fecha_leida = timezone.now()
            elif nuevo_estado == 'PENDIENTE':
                # Resetear fechas si vuelve a pendiente
                notificacion.fecha_leida = None
                notificacion.fecha_realizado = None
            
            notificacion.save()
            messages.success(request, f"Estado cambiado a {nuevo_estado}")
        else:
            messages.error(request, "No tienes permiso para modificar esta notificación")
    else:
        messages.error(request, "Estado no válido")
    
    return redirect('listar_notificaciones')

class CrearNotificacionRapidaView(LoginRequiredMixin, FormView):
    template_name = 'web/notificaciones/crear_rapida.html'
    form_class = NotificacionRapidaForm
    success_url = reverse_lazy('listar_notificaciones')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        # Crear la notificación usando el modelo Notificacion
        notificacion = Notificacion.objects.create(
            titulo=form.cleaned_data['titulo'],
            mensaje=form.cleaned_data['mensaje'],
            usuario_destino=form.cleaned_data['usuario_destino'],
            fecha_vencimiento=form.cleaned_data['fecha_vencimiento'],
            prioridad=form.cleaned_data['prioridad'],
            creado_por=self.request.user,
            origen=self.request.user.get_full_name() or self.request.user.username,
            tipo='TAREA',  # Ajusta según tus necesidades
        )
        
        messages.success(self.request, 'Recordatorio creado exitosamente.')
        
        # Si se presionó el botón "Guardar y Crear Otro", redirigir a la misma página
        if 'guardar_y_crear' in self.request.POST:
            self.success_url = reverse_lazy('crear_notificacion_rapida')
        
        return super().form_valid(form)
    
    
@login_required
@personal_required
def papelera_notificaciones(request):
    """Papelera de notificaciones - Personal ve las suyas y las que asignó"""
    # Obtener parámetros de filtro
    estado = request.GET.get('estado', '')
    prioridad = request.GET.get('prioridad', '')
    tipo_id = request.GET.get('tipo', '')
    search = request.GET.get('search', '')
    fecha_eliminacion_desde = request.GET.get('fecha_eliminacion_desde', '')
    fecha_eliminacion_hasta = request.GET.get('fecha_eliminacion_hasta', '')
    
    # Determinar si es coordinador
    es_coord = es_coordinador(request.user)
    
    # Filtro base según permisos
    if es_coord:
        notificaciones = Notificacion.todas.filter(eliminada=True)
        total_eliminadas = Notificacion.todas.filter(eliminada=True).count()
    else:
        notificaciones = Notificacion.todas.filter(
            Q(usuario_destino=request.user) | 
            Q(usuario_origen=request.user),
            eliminada=True
        )
        total_eliminadas = Notificacion.todas.filter(
            Q(usuario_destino=request.user) | 
            Q(usuario_origen=request.user),
            eliminada=True
        ).count()
        
    # Aplicar filtros
    if estado:
        notificaciones = notificaciones.filter(estado=estado)
    if prioridad:
        notificaciones = notificaciones.filter(prioridad=prioridad)
    if tipo_id:
        notificaciones = notificaciones.filter(tipo_id=tipo_id)
    
    if search:
        notificaciones = notificaciones.filter(
            Q(titulo__icontains=search) |
            Q(mensaje__icontains=search) |
            Q(tipo__nombre__icontains=search) |
            Q(usuario_destino__first_name__icontains=search) |
            Q(usuario_destino__last_name__icontains=search)
        )
    
    if fecha_eliminacion_desde:
        try:
            fecha_desde_obj = datetime.strptime(fecha_eliminacion_desde, '%Y-%m-%d')
            notificaciones = notificaciones.filter(fecha_eliminacion__date__gte=fecha_desde_obj)
        except ValueError:
            pass
    
    if fecha_eliminacion_hasta:
        try:
            fecha_hasta_obj = datetime.strptime(fecha_eliminacion_hasta, '%Y-%m-%d')
            notificaciones = notificaciones.filter(fecha_eliminacion__date__lte=fecha_hasta_obj)
        except ValueError:
            pass
    
    # Ordenar por fecha de eliminación (más reciente primero)
    notificaciones = notificaciones.order_by('-fecha_eliminacion')
    
    tipos_notificacion = TipoNotificacion.objects.all()
    
    context = {
        'notificaciones': notificaciones,
        'total_eliminadas': total_eliminadas,
        'tipos_notificacion': tipos_notificacion,
        'now': timezone.now(),
        'search_query': search,
        'fecha_eliminacion_desde': fecha_eliminacion_desde,
        'fecha_eliminacion_hasta': fecha_eliminacion_hasta,
        'es_coordinador': es_coord,
    }
    
    return render(request, 'web/notificaciones/papelera.html', context)


@login_required
@personal_required
def listar_notificaciones(request):
    """Listar notificaciones - Personal ve las suyas y las que asignó a otros"""
    # Obtener parámetros de filtro
    estado = request.GET.get('estado', '')
    prioridad = request.GET.get('prioridad', '')
    tipo_id = request.GET.get('tipo', '')
    search = request.GET.get('search', '')
    fecha_desde = request.GET.get('fecha_desde', '')
    fecha_hasta = request.GET.get('fecha_hasta', '')
    orden = request.GET.get('orden', 'estado_prioridad')
    usuario_destino_id = request.GET.get('usuario_destino', '')
    
    # CORRECCIÓN: Determinar si es coordinador - SIN .first() porque es objeto directo
    es_coord = False
    if hasattr(request.user, 'personal_relacionado'):
        # Acceder directamente al objeto (NO usar .first())
        personal_usuario = request.user.personal_relacionado  # ¡SIN .first()!
        if personal_usuario and personal_usuario.tipo == 'COORDINADOR':
            es_coord = True
    elif request.user.is_superuser:
        es_coord = True
    
    # Filtro base según permisos
    if es_coord:
        # Coordinador ve todas las notificaciones
        notificaciones = Notificacion.objects.all()
        base_query = Notificacion.objects.all()
    else:
        # Personal normal ve:
        # 1. Sus propias notificaciones (usuario_destino=request.user)
        # 2. Las notificaciones que asignó a otros (usuario_origen=request.user)
        notificaciones = Notificacion.objects.filter(
            Q(usuario_destino=request.user) | 
            Q(usuario_origen=request.user)
        )
        base_query = Notificacion.objects.filter(
            Q(usuario_destino=request.user) | 
            Q(usuario_origen=request.user)
        )
    
    # Aplicar filtros básicos
    if estado:
        notificaciones = notificaciones.filter(estado=estado)
    if prioridad:
        notificaciones = notificaciones.filter(prioridad=prioridad)
    if tipo_id:
        notificaciones = notificaciones.filter(tipo_id=tipo_id)
    
    # Aplicar filtro por usuario destinatario (solo para coordinadores)
    if es_coord and usuario_destino_id:
        try:
            usuario_destino = User.objects.get(id=usuario_destino_id)
            notificaciones = notificaciones.filter(usuario_destino=usuario_destino)
        except User.DoesNotExist:
            pass
    
    # Búsqueda por texto
    if search:
        notificaciones = notificaciones.filter(
            Q(titulo__icontains=search) |
            Q(mensaje__icontains=search) |
            Q(tipo__nombre__icontains=search) |
            Q(usuario_destino__first_name__icontains=search) |
            Q(usuario_destino__last_name__icontains=search) |
            Q(usuario_origen__first_name__icontains=search) |
            Q(usuario_origen__last_name__icontains=search)
        )
    
    # Filtro por fechas
    if fecha_desde:
        try:
            fecha_desde_obj = datetime.strptime(fecha_desde, '%Y-%m-%d')
            notificaciones = notificaciones.filter(fecha_creacion__date__gte=fecha_desde_obj)
        except ValueError:
            pass
    
    if fecha_hasta:
        try:
            fecha_hasta_obj = datetime.strptime(fecha_hasta, '%Y-%m-%d')
            notificaciones = notificaciones.filter(fecha_creacion__date__lte=fecha_hasta_obj)
        except ValueError:
            pass

    # Definir orden de prioridad
    priority_order = Case(
        When(prioridad='URGENTE', then=Value(4)),
        When(prioridad='ALTA', then=Value(3)),
        When(prioridad='MEDIA', then=Value(2)),
        When(prioridad='BAJA', then=Value(1)),
        default=Value(0),
        output_field=IntegerField(),
    )
    
    # Definir orden de estado (PENDIENTE > LEIDA > REALIZADA)
    estado_order = Case(
        When(estado='PENDIENTE', then=Value(3)),
        When(estado='LEIDA', then=Value(2)),
        When(estado='REALIZADA', then=Value(1)),
        default=Value(0),
        output_field=IntegerField(),
    )
    
    # Anotar con orden de prioridad y estado
    now = timezone.now()
    notificaciones = notificaciones.annotate(
        priority_value=priority_order,
        estado_value=estado_order,
        is_overdue=Case(
            When(fecha_vencimiento__lt=now, then=Value(1)),
            default=Value(0),
            output_field=IntegerField(),
        ),
        # Anotar si la notificación fue asignada por el usuario actual
        es_asignada_por_mi=Case(
            When(usuario_origen=request.user, then=Value(True)),
            default=Value(False),
            output_field=BooleanField(),
        )
    )
    
    # Aplicar ordenamiento según parámetro
    if orden == 'fecha_creacion':
        notificaciones = notificaciones.order_by('-fecha_creacion')
    elif orden == 'fecha_vencimiento':
        notificaciones = notificaciones.order_by('fecha_vencimiento', '-priority_value')
    elif orden == 'prioridad':
        notificaciones = notificaciones.order_by('-priority_value', '-estado_value', 'fecha_vencimiento')
    else:  # orden por defecto: estado_prioridad
        notificaciones = notificaciones.order_by(
            '-estado_value',      # Estado descendente (PENDIENTE primero)
            '-priority_value',    # Prioridad descendente (URGENTE primero)
            'is_overdue',         # Vencidas primero
            'fecha_vencimiento',  # Fecha vencimiento ascendente
            '-fecha_creacion'     # Fecha creación descendente
        )
    
    # Estadísticas según permisos
    if es_coord:
        total_notificaciones = Notificacion.objects.count()
        pendientes = Notificacion.objects.filter(estado='PENDIENTE').count()
        realizadas = Notificacion.objects.filter(estado='REALIZADA').count()
        leidas = Notificacion.objects.filter(estado='LEIDA').count()
        urgentes = Notificacion.objects.filter(prioridad='URGENTE').count()
        altas = Notificacion.objects.filter(prioridad='ALTA').count()
        medias = Notificacion.objects.filter(prioridad='MEDIA').count()
        bajas = Notificacion.objects.filter(prioridad='BAJA').count()
        eliminadas_count = Notificacion.todas.filter(eliminada=True).count()
        
        # Estadísticas adicionales para coordinador
        tareas_asignadas_por_mi = Notificacion.objects.filter(usuario_origen=request.user).count()
        tareas_asignadas_por_mi_pendientes = Notificacion.objects.filter(
            usuario_origen=request.user, 
            estado='PENDIENTE'
        ).count()
    else:
        # Usar base_query para estadísticas
        total_notificaciones = base_query.count()
        pendientes = base_query.filter(estado='PENDIENTE').count()
        realizadas = base_query.filter(estado='REALIZADA').count()
        leidas = base_query.filter(estado='LEIDA').count()
        urgentes = base_query.filter(prioridad='URGENTE').count()
        altas = base_query.filter(prioridad='ALTA').count()
        medias = base_query.filter(prioridad='MEDIA').count()
        bajas = base_query.filter(prioridad='BAJA').count()
        eliminadas_count = Notificacion.todas.filter(
            Q(usuario_destino=request.user) | 
            Q(usuario_origen=request.user),
            eliminada=True
        ).count()
        
        # Estadísticas adicionales para usuario normal
        tareas_asignadas_por_mi = Notificacion.objects.filter(usuario_origen=request.user).count()
        tareas_asignadas_por_mi_pendientes = Notificacion.objects.filter(
            usuario_origen=request.user, 
            estado='PENDIENTE'
        ).count()
    
    # Paginación
    paginator = Paginator(notificaciones, 50)  # 50 por página
    page = request.GET.get('page')
    notificaciones_paginadas = paginator.get_page(page)
    
    # Tipos de notificación para el filtro
    tipos_notificacion = TipoNotificacion.objects.all()
    
    # Obtener usuarios para el modal y filtro
    usuarios_personal = User.objects.filter(
        is_active=True,
        personal_relacionado__isnull=False,
        personal_relacionado__activo=True,
        personal_relacionado__eliminado=False
    ).order_by('first_name', 'last_name')
    
    # Para coordinadores: también obtener usuarios para el filtro de vista
    usuarios_filtro = usuarios_personal if es_coord else None
    
    # Obtener información del usuario filtrado (si aplica)
    usuario_filtrado_info = None
    if es_coord and usuario_destino_id:
        try:
            usuario_filtrado = User.objects.get(id=usuario_destino_id)
            # CORREGIR: Acceder directamente al objeto (SIN .first())
            if hasattr(usuario_filtrado, 'personal_relacionado'):
                personal = usuario_filtrado.personal_relacionado  # SIN .first()
                tipo_display = personal.get_tipo_display() if personal else ''
            else:
                tipo_display = ''
            
            usuario_filtrado_info = {
                'nombre': usuario_filtrado.get_full_name() or usuario_filtrado.username,
                'tipo': tipo_display,
            }
        except User.DoesNotExist:
            usuario_destino_id = ''  # Limpiar si el usuario no existe
    
    context = {
        'notificaciones': notificaciones_paginadas,
        'total_notificaciones': total_notificaciones,
        'pendientes': pendientes,
        'realizadas': realizadas,
        'leidas': leidas,
        'urgentes': urgentes,
        'altas': altas,
        'medias': medias,
        'bajas': bajas,
        'eliminadas_count': eliminadas_count,
        'tipos_notificacion': tipos_notificacion,
        'now': now,
        'search_query': search,
        'fecha_desde': fecha_desde,
        'fecha_hasta': fecha_hasta,
        'orden_actual': orden,
        'tareas_asignadas_por_mi': tareas_asignadas_por_mi,
        'tareas_asignadas_por_mi_pendientes': tareas_asignadas_por_mi_pendientes,
        'es_coordinador': es_coord,
        'usuarios_personal': usuarios_personal,  # Para el modal (todos)
        'usuarios_filtro': usuarios_filtro,      # Para filtro de vista (solo coordinadores)
        'usuario_destino_id': usuario_destino_id,
        'usuario_filtrado_info': usuario_filtrado_info,  # Info del usuario filtrado
    }
    
    return render(request, 'web/notificaciones/listar.html', context)

@login_required
@personal_required
def dashboard_coordinador(request):
    """Dashboard de reportes para coordinador"""
    try:
        if not (request.user.is_superuser or es_coordinador(request.user)):
            messages.error(request, "No tienes permisos para acceder a esta página.")
            return redirect('index')
        
        # Obtener período
        periodo = request.GET.get('periodo', 'semana')
        hoy = timezone.now()
        
        if periodo == 'hoy':
            fecha_inicio = hoy.replace(hour=0, minute=0, second=0, microsecond=0)
        elif periodo == 'semana':
            fecha_inicio = hoy - timedelta(days=7)
        elif periodo == 'mes':
            fecha_inicio = hoy - timedelta(days=30)
        elif periodo == 'trimestre':
            fecha_inicio = hoy - timedelta(days=90)
        else:  # año
            fecha_inicio = hoy - timedelta(days=365)
        
        # Estadísticas de moras
        total_deuda = CuotaAlumno.objects.filter(
            pagada=False,
            fecha_vencimiento__lt=hoy.date()
        ).aggregate(total=Sum('monto'))['total'] or Decimal('0')
        
        # CORREGIDO: Acceso a través de inscripcion
        total_alumnos_mora = Alumno.objects.filter(
            inscripcion__cuotaalumno__pagada=False,
            inscripcion__cuotaalumno__fecha_vencimiento__lt=hoy.date(),
            activo=True
        ).distinct().count()
        
        # Tiempo promedio de mora
        from django.db.models import F, ExpressionWrapper, DurationField
        from django.db.models.functions import Coalesce
        
        cuotas_vencidas = CuotaAlumno.objects.filter(
            pagada=False,
            fecha_vencimiento__lt=hoy.date()
        ).annotate(
            dias_mora=ExpressionWrapper(
                hoy.date() - F('fecha_vencimiento'),
                output_field=DurationField()
            )
        )
        
        if cuotas_vencidas.exists():
            promedio_dias = cuotas_vencidas.aggregate(
                promedio=Avg('dias_mora')
            )['promedio']
            promedio_dias = promedio_dias.days if promedio_dias else 0
        else:
            promedio_dias = 0
        
        # Notificaciones enviadas en el período
        notificaciones_enviadas = Notificacion.objects.filter(
            fecha_creacion__gte=fecha_inicio,
            tipo__codigo='MORA_PAGOS'
        ).count()
        
        # Monto recuperado en el período
        try:
            recuperado_mes = Pago.objects.filter(
                fecha_pago__gte=fecha_inicio.date()
            ).aggregate(total=Sum('monto'))['total'] or Decimal('0')
        except:
            recuperado_mes = Decimal('0')
        
        # Porcentaje de alumnos en mora
        total_alumnos_activos = Alumno.objects.filter(activo=True).count()
        porcentaje_mora = (total_alumnos_mora / total_alumnos_activos * 100) if total_alumnos_activos > 0 else 0
        
        # Top 10 deudores - CORREGIDO
        top_deudores = Alumno.objects.filter(
            inscripcion__cuotaalumno__pagada=False,
            inscripcion__cuotaalumno__fecha_vencimiento__lt=hoy.date(),
            activo=True
        ).annotate(
            deuda=Sum('inscripcion__cuotaalumno__monto',
                filter=Q(inscripcion__cuotaalumno__pagada=False) & 
                Q(inscripcion__cuotaalumno__fecha_vencimiento__lt=hoy.date())
            )
        ).filter(deuda__gt=0).order_by('-deuda')[:10]
        
        # Calcular días de mora para cada deudor - CORREGIDO
        for alumno in top_deudores:
            primera_cuota = CuotaAlumno.objects.filter(
                inscripcion__alumno=alumno,  # Acceso correcto
                pagada=False,
                fecha_vencimiento__lt=hoy.date()
            ).order_by('fecha_vencimiento').first()
            
            if primera_cuota:
                alumno.dias_mora = (hoy.date() - primera_cuota.fecha_vencimiento).days
            else:
                alumno.dias_mora = 0
        
        # Actividad reciente
        actividad_reciente = Notificacion.objects.filter(
            tipo__codigo__in=['MORA_PAGOS', 'RECORDATORIO_PAGO', 'PAGO_REGISTRADO']
        ).select_related('usuario_origen', 'tipo').order_by('-fecha_creacion')[:10]
        
        # Distribución por nivel de deuda - CORREGIDO
        alumnos_alta = Alumno.objects.filter(
            inscripcion__cuotaalumno__pagada=False,
            inscripcion__cuotaalumno__fecha_vencimiento__lt=hoy.date(),
            activo=True
        ).annotate(
            deuda=Sum('inscripcion__cuotaalumno__monto',
                filter=Q(inscripcion__cuotaalumno__pagada=False) & 
                Q(inscripcion__cuotaalumno__fecha_vencimiento__lt=hoy.date())
            )
        ).filter(deuda__gt=1000).count()
        
        alumnos_media = Alumno.objects.filter(
            inscripcion__cuotaalumno__pagada=False,
            inscripcion__cuotaalumno__fecha_vencimiento__lt=hoy.date(),
            activo=True
        ).annotate(
            deuda=Sum('inscripcion__cuotaalumno__monto',
                filter=Q(inscripcion__cuotaalumno__pagada=False) & 
                Q(inscripcion__cuotaalumno__fecha_vencimiento__lt=hoy.date())
            )
        ).filter(deuda__gt=500, deuda__lte=1000).count()
        
        alumnos_baja = Alumno.objects.filter(
            inscripcion__cuotaalumno__pagada=False,
            inscripcion__cuotaalumno__fecha_vencimiento__lt=hoy.date(),
            activo=True
        ).annotate(
            deuda=Sum('inscripcion__cuotaalumno__monto',
                filter=Q(inscripcion__cuotaalumno__pagada=False) & 
                Q(inscripcion__cuotaalumno__fecha_vencimiento__lt=hoy.date())
            )
        ).filter(deuda__gt=0, deuda__lte=500).count()
        
        # Estadísticas de notificaciones por tipo
        notificaciones_stats = Notificacion.objects.filter(
            fecha_creacion__gte=fecha_inicio
        ).values('tipo__nombre', 'tipo__icono', 'tipo__color').annotate(
            total=Count('id'),
            pendientes=Count('id', filter=Q(estado='PENDIENTE')),
            realizadas=Count('id', filter=Q(estado='REALIZADA'))
        ).order_by('-total')
        
        # Tiempo promedio de respuesta para notificaciones realizadas
        tiempo_promedio = 0
        notificaciones_realizadas = Notificacion.objects.filter(
            estado='REALIZADA',
            fecha_realizado__isnull=False,
            fecha_creacion__gte=fecha_inicio
        )
        
        if notificaciones_realizadas.exists():
            total_segundos = 0
            for notif in notificaciones_realizadas:
                if notif.fecha_realizado and notif.fecha_creacion:
                    diferencia = notif.fecha_realizado - notif.fecha_creacion
                    total_segundos += diferencia.total_seconds()
            
            tiempo_promedio = total_segundos / notificaciones_realizadas.count() / 86400  # Convertir a días
        
        context = {
            'total_deuda': total_deuda,
            'total_alumnos_mora': total_alumnos_mora,
            'tiempo_promedio': round(promedio_dias, 1),
            'notificaciones_realizadas': notificaciones_enviadas,
            'recuperado_mes': recuperado_mes,
            'porcentaje_mora': round(porcentaje_mora, 1),
            'top_deudores': top_deudores,
            'actividad_reciente': actividad_reciente,
            'alumnos_alta': alumnos_alta,
            'alumnos_media': alumnos_media,
            'alumnos_baja': alumnos_baja,
            'notificaciones_stats': notificaciones_stats,
            'tiempo_promedio_respuesta': round(tiempo_promedio, 2),
            'periodo': periodo,
            'total_notificaciones': Notificacion.objects.count(),
        }
        
        return render(request, 'web/notificaciones/dashboard_coordinador.html', context)
        
    except Exception as e:
        messages.error(request, f'Error cargando dashboard: {str(e)}')
        import traceback
        traceback.print_exc()
        return redirect('index')
    
@login_required
@personal_required
def crear_notificacion_rapida(request):
    """Crear notificación rápida - TODOS pueden asignar a TODOS"""
    if request.method == 'POST':
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        
        if is_ajax:
            try:
                # Obtener datos del formulario
                titulo = request.POST.get('titulo', '').strip()
                mensaje = request.POST.get('mensaje', '').strip()
                usuario_destino_id = request.POST.get('usuario_destino')
                fecha_vencimiento_str = request.POST.get('fecha_vencimiento')
                prioridad = request.POST.get('prioridad', 'MEDIA')
                
                # Validaciones básicas
                if not titulo or not mensaje:
                    return JsonResponse({
                        'success': False,
                        'error': 'Título y mensaje son requeridos'
                    })
                
                # Obtener usuario destino - CORRECCIÓN SINTÁCTICA
                usuario_destino = None
                try:
                    usuario_destino_id = int(usuario_destino_id)
                    usuario_destino = User.objects.filter(
                        id=usuario_destino_id,
                        personal_relacionado__isnull=False,
                        personal_relacionado__activo=True,
                        personal_relacionado__eliminado=False
                    ).first()
                except (ValueError, TypeError):
                    return JsonResponse({
                        'success': False,
                        'error': 'ID de usuario destino no válido'
                    })
                
                if not usuario_destino:
                    return JsonResponse({
                        'success': False,
                        'error': 'Usuario destino no válido o no tiene personal asociado'
                    })
                
                # IMPORTANTE: NO hay restricciones de permisos
                # TODOS pueden asignar a TODOS
                
                # Obtener o crear tipo de notificación manual
                tipo_manual, created = TipoNotificacion.objects.get_or_create(
                    codigo='MANUAL',
                    defaults={
                        'nombre': 'Notificación Manual',
                        'codigo': 'MANUAL',
                        'descripcion': 'Notificación creada manualmente por el usuario',
                        'prioridad': 'MEDIA',
                        'color': 'info',
                        'icono': 'fa-sticky-note',
                        'ES_MANUAL': True
                    }
                )
                
                # Crear notificación
                notificacion = Notificacion.objects.create(
                    usuario_origen=request.user,
                    usuario_destino=usuario_destino,
                    tipo=tipo_manual,
                    titulo=titulo,
                    mensaje=mensaje,
                    estado='PENDIENTE',
                    prioridad=prioridad,
                    es_manual=True,
                    fecha_creacion=timezone.now()
                )
                
                # Procesar fecha de vencimiento si existe
                if fecha_vencimiento_str:
                    try:
                        from django.utils.dateparse import parse_datetime
                        fecha_vencimiento = parse_datetime(fecha_vencimiento_str)
                        if fecha_vencimiento:
                            notificacion.fecha_vencimiento = fecha_vencimiento
                            notificacion.save()
                    except Exception as e:
                        print(f"Error al parsear fecha: {e}")
                
                # Preparar mensaje de éxito
                if usuario_destino == request.user:
                    mensaje_exito = f'✅ Recordatorio "{titulo}" creado exitosamente para ti'
                else:
                    mensaje_exito = f'✅ Recordatorio "{titulo}" creado exitosamente para {usuario_destino.get_full_name()}'
                
                return JsonResponse({
                    'success': True,
                    'message': mensaje_exito,
                    'notificacion_id': notificacion.id,
                    'destinatario': usuario_destino.get_full_name()
                })
                
            except Exception as e:
                import traceback
                print(f"Error en crear_notificacion_rapida (AJAX): {str(e)}")
                print(traceback.format_exc())
                
                return JsonResponse({
                    'success': False,
                    'error': f'Error del servidor: {str(e)}'
                }, status=500)
        
        else:
            # Manejar formulario tradicional (no AJAX)
            form = NotificacionRapidaForm(request.POST, user=request.user)
            
            if form.is_valid():
                usuario_destino = form.cleaned_data['usuario_destino']
                
                # IMPORTANTE: NO hay restricciones de permisos
                # TODOS pueden asignar a TODOS
                
                # Obtener o crear tipo de notificación manual
                tipo_manual, created = TipoNotificacion.objects.get_or_create(
                    codigo='MANUAL',
                    defaults={
                        'nombre': 'Notificación Manual',
                        'codigo': 'MANUAL',
                        'descripcion': 'Notificación creada manualmente por el usuario',
                        'prioridad': 'MEDIA',
                        'color': 'info',
                        'icono': 'fa-sticky-note',
                        'ES_MANUAL': True
                    }
                )
                
                # Crear notificación
                notificacion = Notificacion.objects.create(
                    usuario_origen=request.user,
                    usuario_destino=usuario_destino,
                    tipo=tipo_manual,
                    titulo=form.cleaned_data['titulo'],
                    mensaje=form.cleaned_data['mensaje'],
                    fecha_vencimiento=form.cleaned_data['fecha_vencimiento'],
                    estado='PENDIENTE',
                    prioridad=form.cleaned_data['prioridad'],
                    es_manual=True,
                    fecha_creacion=timezone.now()
                )
                
                if usuario_destino == request.user:
                    messages.success(request, f'✅ Recordatorio creado exitosamente para ti')
                else:
                    messages.success(request, f'✅ Recordatorio creado exitosamente para {usuario_destino.get_full_name()}')
                
                return redirect('listar_notificaciones')
            else:
                messages.error(request, '❌ Error al crear el recordatorio')
                return render(request, 'web/notificaciones/crear_rapida.html', {'form': form})
    
    else:
        # GET request
        form = NotificacionRapidaForm(user=request.user)
        return render(request, 'web/notificaciones/crear_rapida.html', {'form': form})

User = get_user_model()


@login_required
@personal_required  
def asignar_tarea_companero(request):
    """Asignar tarea a compañero - Todo el personal puede usar esta función"""
    if request.method == 'POST':
        form = AsignarTareaCompaneroForm(request.POST, user=request.user)
        if form.is_valid():
            try:
                # Obtener datos del formulario
                usuario_destino = form.cleaned_data['usuario_destino']
                titulo = form.cleaned_data['titulo']
                mensaje = form.cleaned_data['mensaje']
                fecha_vencimiento = form.cleaned_data['fecha_vencimiento']
                prioridad = form.cleaned_data['prioridad']
                
                # Obtener o crear tipo de notificación manual
                tipo_manual, created = TipoNotificacion.objects.get_or_create(
                    codigo='MANUAL',
                    defaults={
                        'nombre': 'Notificación Manual',
                        'descripcion': 'Notificación creada manualmente por el usuario',
                        'prioridad': 'MEDIA',
                        'color': 'info',
                        'icono': 'fa-sticky-note',
                        'ES_MANUAL': True  # Agregado este campo
                    }
                )
                
                # Crear la notificación
                notificacion = Notificacion.objects.create(
                    usuario_destino=usuario_destino,
                    usuario_origen=request.user,
                    tipo=tipo_manual,
                    titulo=titulo,
                    mensaje=mensaje,
                    fecha_vencimiento=fecha_vencimiento,
                    prioridad=prioridad,
                    es_manual=True,
                    estado='PENDIENTE',
                    fecha_creacion=timezone.now()  # Agregado para consistencia
                )
                
                # Obtener nombres para el mensaje de éxito
                nombre_origen = request.user.get_full_name() or request.user.username
                nombre_destino = usuario_destino.get_full_name() or usuario_destino.username
                
                messages.success(request, f'✅ Tarea asignada correctamente: {nombre_origen} → {nombre_destino}')
                return redirect('listar_notificaciones')
                
            except Exception as e:
                messages.error(request, f'❌ Error al crear la notificación: {str(e)}')
        else:
            messages.error(request, '❌ Error en el formulario. Verifica los datos.')
    else:
        form = AsignarTareaCompaneroForm(user=request.user)
    
    return render(request, 'web/notificaciones/asignar_tarea.html', {'form': form})

@login_required
def eliminar_notificacion(request, notificacion_id):
    """Eliminar una notificación"""
    notificacion = get_object_or_404(Notificacion, id=notificacion_id)
    
    # Verificar que el usuario tiene permiso para eliminar
    # Solo puede eliminar sus propias notificaciones o ser coordinador
    if notificacion.usuario_destino != request.user and not request.user.has_perm('web.can_view_all_notifications'):
        messages.error(request, '❌ No tienes permiso para eliminar esta notificación')
        return redirect('listar_notificaciones')
    
    if request.method == 'POST':
        titulo = notificacion.titulo
        notificacion.delete()
        messages.success(request, f'✅ Notificación "{titulo}" eliminada correctamente')
        return redirect('listar_notificaciones')
    
    # Si es GET, mostrar confirmación
    return render(request, 'web/notificaciones/confirmar_eliminacion.html', {'notificacion': notificacion})

@login_required
def eliminar_notificacion(request, notificacion_id):
    """Eliminar una notificación (soft delete)"""
    notificacion = get_object_or_404(Notificacion, id=notificacion_id)
    
    # Verificar que el usuario tiene permiso para eliminar
    if notificacion.usuario_destino != request.user and not request.user.has_perm('web.can_view_all_notifications'):
        messages.error(request, '❌ No tienes permiso para eliminar esta notificación')
        return redirect('listar_notificaciones')
    
    if request.method == 'POST':
        titulo = notificacion.titulo
        notificacion.soft_delete(usuario=request.user)
        messages.success(request, f'✅ Notificación "{titulo}" movida a la papelera')
        return redirect('listar_notificaciones')
    
    # Si es GET, mostrar confirmación
    return render(request, 'web/notificaciones/confirmar_eliminacion.html', {'notificacion': notificacion})

@login_required
def restaurar_notificacion(request, notificacion_id):
    """Restaurar una notificación desde la papelera"""
    notificacion = get_object_or_404(
        Notificacion.todas, 
        id=notificacion_id, 
        usuario_destino=request.user,
        eliminada=True
    )
    
    if request.method == 'POST':
        titulo = notificacion.titulo
        notificacion.restaurar()
        messages.success(request, f'✅ Notificación "{titulo}" restaurada correctamente')
        return redirect('papelera_notificaciones')
    
    # Si es GET, mostrar confirmación
    return render(request, 'web/notificaciones/confirmar_restauracion.html', {'notificacion': notificacion})

@login_required
def eliminar_permanentemente_notificacion(request, notificacion_id):
    """Eliminar permanentemente una notificación de la papelera"""
    notificacion = get_object_or_404(
        Notificacion.todas, 
        id=notificacion_id, 
        usuario_destino=request.user,
        eliminada=True
    )
    
    if request.method == 'POST':
        titulo = notificacion.titulo
        notificacion.hard_delete()
        messages.success(request, f'🗑️ Notificación "{titulo}" eliminada permanentemente')
        return redirect('papelera_notificaciones')
    
    # Si es GET, mostrar confirmación
    return render(request, 'web/notificaciones/confirmar_eliminacion_permanente.html', {'notificacion': notificacion})

@login_required
def vaciar_papelera(request):
    """Eliminar permanentemente todas las notificaciones de la papelera"""
    if request.method == 'POST':
        notificaciones_eliminadas = Notificacion.todas.filter(
            usuario_destino=request.user,
            eliminada=True
        )
        count = notificaciones_eliminadas.count()
        
        # Eliminar permanentemente
        notificaciones_eliminadas.delete()
        
        messages.success(request, f'🗑️ Se eliminaron permanentemente {count} notificaciones')
        return redirect('papelera_notificaciones')
    
    # Si es GET, mostrar confirmación
    notificaciones_count = Notificacion.todas.filter(
        usuario_destino=request.user,
        eliminada=True
    ).count()
    
    return render(request, 'web/notificaciones/confirmar_vaciar_papelera.html', {
        'notificaciones_count': notificaciones_count
    })

@login_required
def dashboard_notificaciones(request):
    """
    Vista router para dashboard de notificaciones.
    Redirige coordinadores a dashboard_coordinador y otros a listar_notificaciones.
    """
    try:
        # Verificar si es coordinador o superusuario
        if request.user.is_superuser or es_coordinador(request.user):
            return redirect('dashboard_coordinador')
        else:
            return redirect('listar_notificaciones')
    
    except Exception as e:
        messages.error(request, f'Error al cargar el dashboard: {str(e)}')
        return redirect('index')
    
    
 # web/views.py - Agrega esta vista
@login_required
def debug_notificaciones(request):
    """Vista de diagnóstico para notificaciones"""
    from django.db.models import Q
    
    data = {
        'usuario_autenticado': request.user.is_authenticated,
        'username': request.user.username if request.user.is_authenticated else 'No autenticado',
    }
    
    if request.user.is_authenticated:
        # Notificaciones pendientes
        notificaciones_pendientes = Notificacion.objects.filter(
            usuario_destino=request.user,
            eliminada=False,
            estado='PENDIENTE'
        )
        
        data.update({
            'total_pendientes': notificaciones_pendientes.count(),
            'notificaciones': list(notificaciones_pendientes.values('id', 'titulo', 'estado', 'prioridad')[:10]),
            'context_processor_count': request.notificaciones_count if hasattr(request, 'notificaciones_count') else 'No disponible'
        })
    
    from django.http import JsonResponse
    return JsonResponse(data)   

# Vista temporal para debugging - elimínala después
@login_required(login_url='login')
def debug_todos_cursos(request):
    """Ver todos los cursos disponibles"""
    cursos = Curso.objects.all()
    result = []
    for curso in cursos:
        result.append({
            'id': curso.id,
            'nombre': curso.nombre,
            'fecha_inicio': str(curso.fecha_inicio) if curso.fecha_inicio else None,
            'fecha_fin': str(curso.fecha_fin) if curso.fecha_fin else None,
        })
    return JsonResponse({'cursos': result})

# Agrega estas importaciones al inicio del archivo views.py
from datetime import datetime, timedelta
from django.db import transaction
from django.db.models import Avg, Q
from django.core.exceptions import ValidationError
from dateutil.rrule import rrule, WEEKLY, MO, TU, WE, TH, FR, SA, SU

# Y usa esta versión simple:
from datetime import datetime, timedelta

def generar_fechas_clase_simple(fecha_inicio, fecha_fin, dias_curso):
    """
    Versión simple sin dateutil
    """
    dias_map = {
        'LUNES': 0,
        'MARTES': 1,
        'MIERCOLES': 2,
        'JUEVES': 3,
        'VIERNES': 4,
        'SABADO': 5,
        'DOMINGO': 6
    }
    
    dias_numeros = []
    if dias_curso:
        for dia in dias_curso.split(','):
            dia_limpio = dia.strip().upper()
            if dia_limpio in dias_map:
                dias_numeros.append(dias_map[dia_limpio])
    
    if not dias_numeros:
        return []
    
    fechas = []
    fecha_actual = fecha_inicio
    
    while fecha_actual <= fecha_fin:
        if fecha_actual.weekday() in dias_numeros:
            fechas.append(fecha_actual)
        fecha_actual += timedelta(days=1)
    
    return fechas

def generar_fechas_clase(fecha_inicio, fecha_fin, dias_curso):
    """
    Genera las fechas de clase basado en los días configurados
    """
    # Mapeo de días en español a constantes de dateutil
    dias_map = {
        'LUNES': MO,
        'MARTES': TU,
        'MIERCOLES': WE,
        'JUEVES': TH,
        'VIERNES': FR,
        'SABADO': SA,
        'DOMINGO': SU
    }
    
    dias_rrule = []
    if dias_curso:
        for dia in dias_curso.split(','):
            dia_limpio = dia.strip().upper()
            if dia_limpio in dias_map:
                dias_rrule.append(dias_map[dia_limpio])
    
    if not dias_rrule:
        return []
    
    # Convertir a objetos datetime si son date
    if isinstance(fecha_inicio, datetime):
        start_dt = fecha_inicio
    else:
        start_dt = datetime.combine(fecha_inicio, time.min)
    
    if isinstance(fecha_fin, datetime):
        end_dt = fecha_fin
    else:
        end_dt = datetime.combine(fecha_fin, time.min)
    
    # Generar fechas usando rrule (sin el doble rrule.rrule)
    fechas = list(rrule(
        freq=WEEKLY,
        dtstart=start_dt,
        until=end_dt,
        byweekday=dias_rrule
    ))
    
    return [fecha.date() for fecha in fechas]

# FILTRO PARA TEMPLATES
from django.template.defaulttags import register

# @register.filter
# def get_item(dictionary, key):
#     return dictionary.get(key)


# web/views.py
@login_required
@personal_required
def seguimiento_moras(request):
    """Vista especializada para seguimiento de moras de pagos"""
    # Verificar si es coordinador o tiene permisos
    if not es_coordinador(request.user):
        messages.error(request, 'Solo coordinadores pueden acceder a esta vista')
        return redirect('index')
    
    # Filtros
    dias_mora = request.GET.get('dias_mora', 5)
    mostrar_solo_activos = request.GET.get('activos', 'true') == 'true'
    
    hoy = timezone.now().date()
    fecha_limite = hoy - timedelta(days=int(dias_mora))
    
    # Consulta de alumnos en mora
    alumnos_mora = Alumno.objects.filter(
        cuotaalumno__pagada=False,
        cuotaalumno__fecha_vencimiento__lt=fecha_limite,
        activo=mostrar_solo_activos
    ).annotate(
        total_deuda=Sum('cuotaalumno__monto',
            filter=Q(cuotaalumno__pagada=False) & 
            Q(cuotaalumno__fecha_vencimiento__lt=hoy)
        ),
        cuotas_vencidas=Count('cuotaalumno',
            filter=Q(cuotaalumno__pagada=False) & 
            Q(cuotaalumno__fecha_vencimiento__lt=hoy)
        ),
        primera_cuota_vencida=Min('cuotaalumno__fecha_vencimiento',
            filter=Q(cuotaalumno__pagada=False) & 
            Q(cuotaalumno__fecha_vencimiento__lt=hoy)
        )
    ).filter(total_deuda__gt=0).distinct().order_by('-total_deuda')
    
    # Estadísticas
    total_deuda = sum(alumno.total_deuda or 0 for alumno in alumnos_mora)
    total_alumnos = alumnos_mora.count()
    
    context = {
        'alumnos_mora': alumnos_mora,
        'total_deuda': total_deuda,
        'total_alumnos': total_alumnos,
        'dias_mora': dias_mora,
        'hoy': hoy,
        'fecha_limite': fecha_limite,
    }
    
    return render(request, 'web/facturacion/seguimiento_moras.html', context)


from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views.generic import View
from django.db.models import Q, Sum, Count, Avg, Max, Min
from django.utils import timezone
from datetime import timedelta
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.core.paginator import Paginator
import json
from decimal import Decimal

@login_required
@personal_required
def seguimiento_moras(request):
    """Vista para seguimiento de alumnos con pagos en mora"""
    try:
        # Verificar permisos (solo coordinadores y administradores)
        if not (request.user.is_superuser or es_coordinador(request.user)):
            messages.error(request, "No tienes permisos para acceder a esta página.")
            return redirect('index')
        
        # Obtener parámetros de filtro
        dias_mora = request.GET.get('dias_mora', 5)
        try:
            dias_mora = int(dias_mora)
        except ValueError:
            dias_mora = 5
        
        estado_alumno = request.GET.get('estado_alumno', 'activos')
        search = request.GET.get('search', '')
        curso_id = request.GET.get('curso', '')
        orden = request.GET.get('orden', '-total_deuda')
        
        hoy = timezone.now().date()
        fecha_limite = hoy - timedelta(days=dias_mora)
        
        # Consulta base: alumnos con cuotas vencidas
        alumnos_query = Alumno.objects.filter(
            cuotaalumno__pagada=False,
            cuotaalumno__fecha_vencimiento__lt=fecha_limite
        ).distinct()
        
        # Aplicar filtro de estado
        if estado_alumno == 'activos':
            alumnos_query = alumnos_query.filter(activo=True)
        elif estado_alumno == 'inactivos':
            alumnos_query = alumnos_query.filter(activo=False)
        # 'todos' no aplica filtro adicional
        
        # Aplicar filtro de búsqueda
        if search:
            alumnos_query = alumnos_query.filter(
                Q(nombre__icontains=search) |
                Q(apellido__icontains=search) |
                Q(matricula__icontains=search) |
                Q(telefono__icontains=search) |
                Q(email__icontains=search) |
                Q(dni__icontains=search)
            )
        
        # Aplicar filtro por curso
        if curso_id:
            alumnos_query = alumnos_query.filter(
                inscripcion__curso_id=curso_id,
                inscripcion__activa=True
            ).distinct()
        
        # Anotar con estadísticas de mora
        alumnos_mora = alumnos_query.annotate(
            total_deuda=Sum('cuotaalumno__monto', 
                filter=Q(cuotaalumno__pagada=False) & 
                Q(cuotaalumno__fecha_vencimiento__lt=hoy)
            ),
            cuotas_vencidas=Count('cuotaalumno',
                filter=Q(cuotaalumno__pagada=False) & 
                Q(cuotaalumno__fecha_vencimiento__lt=hoy)
            ),
            primera_cuota_vencida=Min('cuotaalumno__fecha_vencimiento',
                filter=Q(cuotaalumno__pagada=False) & 
                Q(cuotaalumno__fecha_vencimiento__lt=hoy)
            ),
            ultima_cuota_vencida=Max('cuotaalumno__fecha_vencimiento',
                filter=Q(cuotaalumno__pagada=False) & 
                Q(cuotaalumno__fecha_vencimiento__lt=hoy)
            )
        ).filter(total_deuda__gt=0)
        
        # Calcular días de mora para cada alumno
        for alumno in alumnos_mora:
            if alumno.primera_cuota_vencida:
                alumno.dias_mora = (hoy - alumno.primera_cuota_vencida).days
            else:
                alumno.dias_mora = 0
        
        # Aplicar ordenamiento
        if orden == 'nombre':
            alumnos_mora = alumnos_mora.order_by('nombre', 'apellido')
        elif orden == 'dias_mora':
            alumnos_mora = alumnos_mora.order_by('-dias_mora')
        elif orden == 'cuotas':
            alumnos_mora = alumnos_mora.order_by('-cuotas_vencidas')
        else:  # orden por defecto: total_deuda descendente
            alumnos_mora = alumnos_mora.order_by('-total_deuda')
        
        # Calcular estadísticas generales
        total_deuda = alumnos_mora.aggregate(Sum('total_deuda'))['total_deuda__sum'] or Decimal('0')
        total_alumnos = alumnos_mora.count()
        
        if total_alumnos > 0:
            total_cuotas_vencidas = alumnos_mora.aggregate(Sum('cuotas_vencidas'))['cuotas_vencidas__sum'] or 0
            promedio_cuotas = total_cuotas_vencidas / total_alumnos
            promedio_dias_mora = alumnos_mora.aggregate(Avg('dias_mora'))['dias_mora__avg'] or 0
            max_dias_mora = alumnos_mora.aggregate(Max('dias_mora'))['dias_mora__max'] or 0
        else:
            total_cuotas_vencidas = 0
            promedio_cuotas = 0
            promedio_dias_mora = 0
            max_dias_mora = 0
        
        # Calcular distribución por nivel de deuda
        deuda_alta = alumnos_mora.filter(total_deuda__gt=1000).aggregate(
            Sum('total_deuda')
        )['total_deuda__sum'] or Decimal('0')
        
        deuda_media = alumnos_mora.filter(
            total_deuda__gt=500, 
            total_deuda__lte=1000
        ).aggregate(Sum('total_deuda'))['total_deuda__sum'] or Decimal('0')
        
        deuda_baja = alumnos_mora.filter(
            total_deuda__gt=0, 
            total_deuda__lte=500
        ).aggregate(Sum('total_deuda'))['total_deuda__sum'] or Decimal('0')
        
        # Obtener cursos para filtro
        cursos = Curso.objects.filter(activo=True).order_by('nombre')
        
        # Alertas y recomendaciones
        alertas_urgentes = []
        alertas_normales = []
        recomendaciones = []
        
        if total_deuda > Decimal('10000'):
            alertas_urgentes.append(f"La deuda total (${total_deuda:.2f}) supera los $10,000. Se requiere atención inmediata.")
        
        if max_dias_mora > 60:
            alertas_urgentes.append(f"Existen alumnos con más de 60 días de mora (máximo: {max_dias_mora} días).")
        
        if total_alumnos > 20:
            alertas_normales.append(f"El número de alumnos en mora ({total_alumnos}) es elevado. Considere implementar un plan de cobranza más agresivo.")
        
        if promedio_dias_mora > 30:
            alertas_normales.append(f"El promedio de días de mora ({promedio_dias_mora:.0f} días) es alto. Revise los procesos de recordatorios.")
        
        # Recomendaciones
        if alertas_urgentes:
            recomendaciones.append("Contactar urgentemente a los 5 mayores deudores por teléfono.")
            recomendaciones.append("Considerar la suspensión de servicios para alumnos con más de 90 días de mora.")
        
        if deuda_alta > 0:
            recomendaciones.append("Establecer planes de pago personalizados para deudas superiores a $1000.")
        
        if total_cuotas_vencidas > 50:
            recomendaciones.append("Implementar un sistema de recordatorios automáticos más frecuente (cada 3 días).")
        
        # Estadísticas para gráficos
        variacion_mensual = 0  # En una implementación real, calcularías esto
        alumnos_alta = alumnos_mora.filter(total_deuda__gt=1000).count()
        alumnos_media = alumnos_mora.filter(total_deuda__gt=500, total_deuda__lte=1000).count()
        alumnos_baja = alumnos_mora.filter(total_deuda__gt=0, total_deuda__lte=500).count()
        
        context = {
            'alumnos_mora': alumnos_mora,
            'total_deuda': total_deuda,
            'total_alumnos': total_alumnos,
            'total_cuotas_vencidas': total_cuotas_vencidas,
            'promedio_cuotas': promedio_cuotas,
            'promedio_dias_mora': promedio_dias_mora,
            'max_dias_mora': max_dias_mora,
            'deuda_alta': deuda_alta,
            'deuda_media': deuda_media,
            'deuda_baja': deuda_baja,
            'alertas_urgentes': alertas_urgentes,
            'alertas_normales': alertas_normales,
            'recomendaciones': recomendaciones,
            'dias_mora': dias_mora,
            'estado_alumno': estado_alumno,
            'search': search,
            'curso_id': curso_id,
            'orden': orden,
            'cursos': cursos,
            'hoy': hoy,
            'fecha_limite': fecha_limite,
            'variacion_mensual': variacion_mensual,
            'alumnos_alta': alumnos_alta,
            'alumnos_media': alumnos_media,
            'alumnos_baja': alumnos_baja,
        }
        
        return render(request, 'web/facturacion/seguimiento_moras.html', context)
        
    except Exception as e:
        messages.error(request, f'Error al cargar el seguimiento de moras: {str(e)}')
        import traceback
        traceback.print_exc()
        return redirect('index')


@login_required
@personal_required
def obtener_detalle_alumno(request, alumno_id):
    """Obtener detalles de un alumno para el modal"""
    try:
        alumno = get_object_or_404(Alumno, id=alumno_id)
        
        # Obtener cuotas vencidas
        cuotas_vencidas = CuotaAlumno.objects.filter(
            alumno=alumno,
            pagada=False,
            fecha_vencimiento__lt=timezone.now().date()
        ).order_by('fecha_vencimiento')
        
        # Calcular totales
        total_deuda = cuotas_vencidas.aggregate(total=Sum('monto'))['total'] or Decimal('0')
        dias_mora = 0
        if cuotas_vencidas.exists():
            primera_cuota = cuotas_vencidas.first()
            dias_mora = (timezone.now().date() - primera_cuota.fecha_vencimiento).days
        
        # Obtener inscripciones activas
        inscripciones = Inscripcion.objects.filter(
            alumno=alumno,
            activa=True
        ).select_related('curso')
        
        # Obtener historial de pagos recientes
        pagos_recientes = Pago.objects.filter(
            alumno=alumno
        ).order_by('-fecha_pago')[:5]
        
        # Obtener notificaciones recientes
        notificaciones_recientes = Notificacion.objects.filter(
            relacion_alumno=alumno,
            tipo__codigo__in=['MORA_PAGOS', 'RECORDATORIO_PAGO']
        ).order_by('-fecha_creacion')[:5]
        
        data = {
            'id': alumno.id,
            'nombre_completo': alumno.nombre_completo(),
            'matricula': alumno.matricula,
            'dni': alumno.dni,
            'telefono': alumno.telefono,
            'email': alumno.email,
            'direccion': alumno.direccion,
            'contacto_emergencia_nombre': alumno.contacto_emergencia_nombre,
            'contacto_emergencia_telefono': alumno.contacto_emergencia_telefono,
            'activo': alumno.activo,
            'fecha_inscripcion': alumno.fecha_inscripcion.strftime('%d/%m/%Y') if alumno.fecha_inscripcion else '',
            'total_deuda': float(total_deuda),
            'dias_mora': dias_mora,
            'cuotas_vencidas_count': cuotas_vencidas.count(),
            'cuotas_vencidas': [
                {
                    'id': cuota.id,
                    'mes': cuota.mes,
                    'año': cuota.año,
                    'monto': float(cuota.monto),
                    'fecha_vencimiento': cuota.fecha_vencimiento.strftime('%d/%m/%Y'),
                    'dias_vencida': (timezone.now().date() - cuota.fecha_vencimiento).days,
                    'descripcion': cuota.descripcion or ''
                }
                for cuota in cuotas_vencidas
            ],
            'inscripciones': [
                {
                    'curso_nombre': insc.curso.nombre,
                    'fecha_inscripcion': insc.fecha_inscripcion.strftime('%d/%m/%Y'),
                    'estado': 'Activa' if insc.activa else 'Inactiva'
                }
                for insc in inscripciones
            ],
            'pagos_recientes': [
                {
                    'fecha': pago.fecha_pago.strftime('%d/%m/%Y'),
                    'monto': float(pago.monto),
                    'metodo_pago': pago.get_metodo_pago_display(),
                    'descripcion': pago.descripcion or ''
                }
                for pago in pagos_recientes
            ],
            'notificaciones_recientes': [
                {
                    'fecha': notif.fecha_creacion.strftime('%d/%m/%Y %H:%M'),
                    'titulo': notif.titulo,
                    'estado': notif.get_estado_display(),
                    'prioridad': notif.get_prioridad_display()
                }
                for notif in notificaciones_recientes
            ]
        }
        
        return JsonResponse({'success': True, 'data': data})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@personal_required
def obtener_cuotas_alumno(request, alumno_id):
    """Obtener todas las cuotas de un alumno"""
    try:
        alumno = get_object_or_404(Alumno, id=alumno_id)
        hoy = timezone.now().date()
        
        # Obtener todas las cuotas (vencidas y no vencidas)
        cuotas = CuotaAlumno.objects.filter(
            alumno=alumno
        ).order_by('-año', '-mes')
        
        cuotas_data = []
        for cuota in cuotas:
            estado = 'PAGADA' if cuota.pagada else 'PENDIENTE'
            dias_vencida = 0
            if not cuota.pagada and cuota.fecha_vencimiento < hoy:
                estado = 'VENCIDA'
                dias_vencida = (hoy - cuota.fecha_vencimiento).days
            
            cuotas_data.append({
                'id': cuota.id,
                'mes': cuota.mes,
                'año': cuota.año,
                'monto': float(cuota.monto),
                'fecha_vencimiento': cuota.fecha_vencimiento.strftime('%d/%m/%Y'),
                'pagada': cuota.pagada,
                'estado': estado,
                'dias_vencida': dias_vencida,
                'fecha_pago': cuota.fecha_pago.strftime('%d/%m/%Y') if cuota.fecha_pago else None,
                'descripcion': cuota.descripcion or '',
                'metodo_pago': cuota.metodo_pago or '',
                'referencia': cuota.referencia_pago or ''
            })
        
        # Calcular totales
        total_deuda = sum(c['monto'] for c in cuotas_data if not c['pagada'])
        total_pagado = sum(c['monto'] for c in cuotas_data if c['pagada'])
        cuotas_vencidas = [c for c in cuotas_data if c['estado'] == 'VENCIDA']
        
        data = {
            'alumno': {
                'id': alumno.id,
                'nombre_completo': alumno.nombre_completo(),
                'matricula': alumno.matricula
            },
            'cuotas': cuotas_data,
            'totales': {
                'total_deuda': total_deuda,
                'total_pagado': total_pagado,
                'cuotas_vencidas_count': len(cuotas_vencidas),
                'deuda_vencida': sum(c['monto'] for c in cuotas_vencidas)
            }
        }
        
        return JsonResponse({'success': True, 'data': data})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@personal_required
def marcar_cuota_pagada(request, cuota_id):
    """Marcar una cuota como pagada"""
    if request.method == 'POST':
        try:
            cuota = get_object_or_404(CuotaAlumno, id=cuota_id)
            
            # Actualizar cuota
            cuota.pagada = True
            cuota.fecha_pago = timezone.now().date()
            cuota.metodo_pago = request.POST.get('metodo_pago', 'EFECTIVO')
            cuota.referencia_pago = request.POST.get('referencia_pago', '')
            cuota.descripcion = request.POST.get('descripcion', 'Pago registrado desde seguimiento de moras')
            cuota.save()
            
            # Crear registro de pago
            Pago.objects.create(
                alumno=cuota.alumno,
                monto=cuota.monto,
                fecha_pago=cuota.fecha_pago,
                metodo_pago=cuota.metodo_pago,
                referencia=cuota.referencia_pago,
                descripcion=f"Pago de cuota {cuota.mes}/{cuota.año}",
                usuario_registro=request.user
            )
            
            # Crear notificación de pago registrado
            tipo_notif, _ = TipoNotificacion.objects.get_or_create(
                codigo='PAGO_REGISTRADO',
                defaults={
                    'nombre': 'Pago Registrado',
                    'descripcion': 'Notificación de pago registrado',
                    'prioridad': 'BAJA',
                    'color': 'success',
                    'icono': 'fa-check-circle',
                    'ES_MANUAL': False
                }
            )
            
            # Notificar al coordinador
            coordinadores = User.objects.filter(
                personal__tipo='COORDINADOR',
                personal__activo=True,
                is_active=True
            )
            
            for coordinador in coordinadores:
                Notificacion.objects.create(
                    usuario_destino=coordinador,
                    usuario_origen=request.user,
                    tipo=tipo_notif,
                    titulo=f'✅ Pago registrado: {cuota.alumno.nombre_completo()}',
                    mensaje=f'Se registró el pago de ${cuota.monto:.2f} para la cuota {cuota.mes}/{cuota.año} del alumno {cuota.alumno.nombre_completo()}.',
                    estado='PENDIENTE',
                    prioridad='BAJA',
                    es_manual=False,
                    relacion_alumno=cuota.alumno,
                    relacion_cuota=cuota
                )
            
            return JsonResponse({
                'success': True,
                'message': f'Cuota marcada como pagada. Se registró el pago de ${cuota.monto:.2f}.'
            })
            
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Método no permitido'})


@login_required
@personal_required
def contactar_alumno_mora(request, alumno_id):
    """Registrar contacto con alumno en mora"""
    if request.method == 'POST':
        try:
            alumno = get_object_or_404(Alumno, id=alumno_id)
            
            tipo_contacto = request.POST.get('tipo_contacto', 'TELEFONICO')
            resultado = request.POST.get('resultado', '')
            observaciones = request.POST.get('observaciones', '')
            proximo_contacto = request.POST.get('proximo_contacto', '')
            
            # Crear registro de contacto
            HistorialContactoMora.objects.create(
                alumno=alumno,
                usuario=request.user,
                tipo_contacto=tipo_contacto,
                resultado=resultado,
                observaciones=observaciones,
                proximo_contacto=proximo_contacto if proximo_contacto else None
            )
            
            # Actualizar fecha de último contacto en el alumno
            alumno.ultimo_contacto_mora = timezone.now()
            alumno.save()
            
            # Crear notificación del contacto
            tipo_notif, _ = TipoNotificacion.objects.get_or_create(
                codigo='CONTACTO_MORA',
                defaults={
                    'nombre': 'Contacto por Mora',
                    'descripcion': 'Registro de contacto con alumno en mora',
                    'prioridad': 'MEDIA',
                    'color': 'info',
                    'icono': 'fa-phone',
                    'ES_MANUAL': False
                }
            )
            
            Notificacion.objects.create(
                usuario_destino=request.user,
                usuario_origen=request.user,
                tipo=tipo_notif,
                titulo=f'📞 Contacto con {alumno.nombre_completo()}',
                mensaje=f'Contacto {tipo_contacto.lower()} registrado. Resultado: {resultado}',
                estado='PENDIENTE',
                prioridad='MEDIA',
                es_manual=True,
                relacion_alumno=alumno
            )
            
            return JsonResponse({
                'success': True,
                'message': 'Contacto registrado exitosamente'
            })
            
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Método no permitido'})


@login_required
@personal_required
def generar_notificaciones_mora_manual(request):
    """Generar notificaciones de mora manualmente"""
    if request.method == 'POST':
        try:
            # Verificar permisos
            if not (request.user.is_superuser or es_coordinador(request.user)):
                return JsonResponse({
                    'success': False, 
                    'error': 'No tienes permisos para realizar esta acción'
                }, status=403)
            
            # Obtener tipo de notificación de mora
            tipo_mora, created = TipoNotificacion.objects.get_or_create(
                codigo='MORA_PAGOS',
                defaults={
                    'nombre': 'Mora de Pagos',
                    'descripcion': 'Notificaciones automáticas de alumnos con pagos en mora',
                    'prioridad': 'ALTA',
                    'color': 'danger',
                    'icono': 'fa-exclamation-triangle',
                    'ES_MANUAL': False
                }
            )
            
            # Obtener alumnos con pagos en mora (más de 5 días)
            hoy = timezone.now().date()
            fecha_limite = hoy - timedelta(days=5)
            
            # Obtener cuotas vencidas
            cuotas_vencidas = CuotaAlumno.objects.filter(
                pagada=False,
                fecha_vencimiento__lt=fecha_limite
            ).select_related('inscripcion__alumno', 'inscripcion__curso')
            
            # Obtener coordinadores para notificar
            coordinadores = User.objects.filter(
                personal__tipo__in=['COORDINADOR', 'ADMINISTRADOR'],
                is_active=True
            ).distinct()
            
            notificaciones_creadas = 0
            
            for cuota in cuotas_vencidas:
                for coordinador in coordinadores:
                    # Verificar si ya existe notificación similar reciente
                    existe = Notificacion.objects.filter(
                        usuario_destino=coordinador,
                        tipo=tipo_mora,
                        titulo__icontains=cuota.inscripcion.alumno.nombre_completo(),
                        fecha_creacion__gte=hoy - timedelta(days=7)
                    ).exists()
                    
                    if not existe:
                        dias_mora = (hoy - cuota.fecha_vencimiento).days
                        Notificacion.objects.create(
                            usuario_destino=coordinador,
                            usuario_origen=None,  # Sistema
                            tipo=tipo_mora,
                            titulo=f'Mora de pago: {cuota.inscripcion.alumno.nombre_completo()}',
                            mensaje=f'El alumno {cuota.inscripcion.alumno.nombre_completo()} (DNI: {cuota.inscripcion.alumno.dni}) tiene una cuota vencida desde {cuota.fecha_vencimiento}. Monto: ${cuota.monto}. Días de mora: {dias_mora}. Curso: {cuota.inscripcion.curso.nombre}.',
                            estado='PENDIENTE',
                            prioridad='ALTA',
                            es_manual=False
                        )
                        notificaciones_creadas += 1
            
            return JsonResponse({
                'success': True, 
                'message': f'Se generaron {notificaciones_creadas} notificaciones de mora para {cuotas_vencidas.count()} cuotas vencidas',
                'notificaciones_creadas': notificaciones_creadas,
                'cuotas_vencidas': cuotas_vencidas.count()
            })
            
        except Exception as e:
            import traceback
            return JsonResponse({
                'success': False, 
                'error': str(e),
                'traceback': traceback.format_exc()
            }, status=500)
    
    return JsonResponse({
        'success': False, 
        'error': 'Método no permitido'
    }, status=405)

# web/views.py - Verifica que esta vista exista
@login_required
@personal_required
def exportar_moras_excel(request):
    """Exportar reporte de moras a Excel"""
    try:
        # Verificar permisos
        if not es_coordinador(request.user):
            messages.error(request, 'No tienes permisos para acceder a esta función.')
            return redirect('index')
        
        # Obtener parámetros
        dias_mora = int(request.GET.get('dias_mora', 5))
        estado_alumno = request.GET.get('estado_alumno', 'activos')
        action = request.GET.get('action', '')
        
        hoy = timezone.now().date()
        fecha_limite = hoy - timedelta(days=dias_mora)
        
        # Consulta de alumnos en mora
        alumnos_mora = Alumno.objects.filter(
            cuotaalumno__pagada=False,
            cuotaalumno__fecha_vencimiento__lt=fecha_limite
        ).distinct()
        
        # Filtrar por estado
        if estado_alumno == 'activos':
            alumnos_mora = alumnos_mora.filter(activo=True)
        elif estado_alumno == 'inactivos':
            alumnos_mora = alumnos_mora.filter(activo=False)
        
        # Anotar con datos de mora
        alumnos_mora = alumnos_mora.annotate(
            total_deuda=Sum('cuotaalumno__monto',
                filter=Q(cuotaalumno__pagada=False) & 
                Q(cuotaalumno__fecha_vencimiento__lt=hoy)
            ),
            cuotas_vencidas=Count('cuotaalumno',
                filter=Q(cuotaalumno__pagada=False) & 
                Q(cuotaalumno__fecha_vencimiento__lt=hoy)
            ),
            primera_cuota_vencida=Min('cuotaalumno__fecha_vencimiento',
                filter=Q(cuotaalumno__pagada=False) & 
                Q(cuotaalumno__fecha_vencimiento__lt=hoy)
            )
        ).filter(total_deuda__gt=0).order_by('-total_deuda')
        
        # Crear libro de Excel
        wb = Workbook()
        ws = wb.active
        ws.title = f"Reporte Moras {hoy}"
        
        # Encabezados
        headers = ['Alumno', 'DNI', 'Teléfono', 'Email', 'Curso Actual', 
                   'Deuda Total', 'Cuotas Vencidas', 'Días de Mora', 
                   'Primera Cuota Vencida', 'Estado']
        ws.append(headers)
        
        # Datos
        for alumno in alumnos_mora:
            if alumno.primera_cuota_vencida:
                dias_mora_alumno = (hoy - alumno.primera_cuota_vencida).days
            else:
                dias_mora_alumno = 0
            
            # Obtener curso actual
            curso_actual = alumno.inscripcion_set.filter(
                estado='ACTIVA'
            ).order_by('-fecha_inscripcion').first()
            
            ws.append([
                alumno.nombre_completo(),
                alumno.dni,
                alumno.telefono or '',
                alumno.email or '',
                curso_actual.curso.nombre if curso_actual else '',
                float(alumno.total_deuda or 0),
                alumno.cuotas_vencidas or 0,
                dias_mora_alumno,
                alumno.primera_cuota_vencida.strftime('%d/%m/%Y') if alumno.primera_cuota_vencida else '',
                'ACTIVO' if alumno.activo else 'INACTIVO'
            ])
        
        # Estilos
        for col in range(1, len(headers) + 1):
            ws.column_dimensions[get_column_letter(col)].width = 20
        
        # Preparar respuesta
        response = HttpResponse(
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        
        if action == 'reporte_semanal':
            filename = f'reporte_semanal_moras_{hoy}.xlsx'
        else:
            filename = f'reporte_moras_{hoy}.xlsx'
        
        response['Content-Disposition'] = f'attachment; filename={filename}'
        wb.save(response)
        
        return response
        
    except Exception as e:
        # Si hay error, devolver JSON en lugar de HTML
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)
        else:
            messages.error(request, f'Error generando reporte: {str(e)}')
            return redirect('seguimiento_moras')
    
@login_required
@personal_required
def reporte_moras_pdf(request):
    """Generar reporte de moras en PDF"""
    try:
        # Obtener parámetros de filtro
        dias_mora = int(request.GET.get('dias_mora', 5))
        estado_alumno = request.GET.get('estado_alumno', 'activos')
        
        hoy = timezone.now().date()
        fecha_limite = hoy - timedelta(days=dias_mora)
        
        # Consulta de alumnos en mora
        alumnos_mora = Alumno.objects.filter(
            cuotaalumno__pagada=False,
            cuotaalumno__fecha_vencimiento__lt=fecha_limite
        )
        
        if estado_alumno == 'activos':
            alumnos_mora = alumnos_mora.filter(activo=True)
        elif estado_alumno == 'inactivos':
            alumnos_mora = alumnos_mora.filter(activo=False)
        
        # Anotar con datos de mora
        alumnos_mora = alumnos_mora.annotate(
            total_deuda=Sum('cuotaalumno__monto', 
                filter=Q(cuotaalumno__pagada=False) & 
                Q(cuotaalumno__fecha_vencimiento__lt=hoy)
            ),
            cuotas_vencidas=Count('cuotaalumno',
                filter=Q(cuotaalumno__pagada=False) & 
                Q(cuotaalumno__fecha_vencimiento__lt=hoy)
            ),
            primera_cuota_vencida=Min('cuotaalumno__fecha_vencimiento',
                filter=Q(cuotaalumno__pagada=False) & 
                Q(cuotaalumno__fecha_vencimiento__lt=hoy)
            )
        ).filter(total_deuda__gt=0).distinct().order_by('-total_deuda')
        
        # Preparar datos para PDF
        data = []
        total_general = 0
        
        for alumno in alumnos_mora:
            dias_mora_alumno = 0
            if alumno.primera_cuota_vencida:
                dias_mora_alumno = (hoy - alumno.primera_cuota_vencida).days
            
            alumno_data = {
                'alumno': alumno,
                'dias_mora': dias_mora_alumno,
                'total_deuda': alumno.total_deuda or 0,
                'cuotas_vencidas': alumno.cuotas_vencidas or 0,
                'curso_actual': alumno.curso_actual(),
                'ultimo_contacto': alumno.ultimo_contacto_mora,
                'contacto_emergencia_nombre': alumno.contacto_emergencia_nombre,
                'contacto_emergencia_telefono': alumno.contacto_emergencia_telefono
            }
            
            data.append(alumno_data)
            total_general += alumno_data['total_deuda']
        
        # Crear contexto para el template
        context = {
            'alumnos_mora': data,
            'hoy': hoy,
            'dias_mora_param': dias_mora,
            'estado_alumno': estado_alumno,
            'total_registros': len(data),
            'total_general': total_general,
            'fecha_generacion': timezone.now()
        }
        
        # Renderizar HTML a partir del template
        html_string = render_to_string('facturacion/reporte_moras_pdf.html', context)
        
        # Crear PDF
        html = HTML(string=html_string)
        pdf_file = html.write_pdf()
        
        # Crear respuesta HTTP
        response = HttpResponse(pdf_file, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="reporte_moras_{hoy.strftime("%Y%m%d")}.pdf"'
        
        return response
        
    except Exception as e:
        messages.error(request, f'Error al generar reporte PDF: {str(e)}')
        return redirect('seguimiento_moras')
    
@login_required
@personal_required
def generar_recordatorios_pago(request):
    """Generar recordatorios de pago manualmente"""
    if request.method == 'POST':
        try:
            # Verificar permisos
            if not (request.user.is_superuser or es_coordinador(request.user)):
                return JsonResponse({
                    'success': False, 
                    'error': 'No tienes permisos para realizar esta acción'
                }, status=403)
            
            # Obtener o crear tipo de notificación de recordatorio
            try:
                tipo_recordatorio = TipoNotificacion.objects.get(codigo='RECORDATORIO_PAGO')
            except TipoNotificacion.DoesNotExist:
                # Si no existe, crearlo
                tipo_recordatorio = TipoNotificacion.objects.create(
                    codigo='RECORDATORIO_PAGO',
                    nombre='Recordatorio de Pago',
                    descripcion='Recordatorio de pago próximo a vencer',
                    prioridad='MEDIA',
                    color='warning',
                    icono='fa-clock',
                    ES_MANUAL=False
                )
            
            # Obtener alumnos con pagos próximos a vencer (en los próximos 3 días)
            hoy = timezone.now().date()
            fecha_limite = hoy + timedelta(days=3)
            
            # DEBUG: Mostrar fechas
            print(f"DEBUG - Hoy: {hoy}, Fecha límite: {fecha_limite}")
            
            # Obtener cuotas que vencen en los próximos 3 días
            cuotas_proximas = CuotaAlumno.objects.filter(
                pagada=False,
                fecha_vencimiento__gte=hoy,
                fecha_vencimiento__lte=fecha_limite,
                inscripcion__alumno__activo=True
            ).select_related('inscripcion__alumno', 'inscripcion__curso')
            
            print(f"DEBUG: Encontradas {cuotas_proximas.count()} cuotas próximas a vencer")
            
            # Obtener coordinadores para notificar
            coordinadores = User.objects.filter(
                personal__tipo__in=['COORDINADOR', 'ADMINISTRADOR'],
                is_active=True
            ).distinct()
            
            print(f"DEBUG: {coordinadores.count()} coordinadores encontrados")
            
            notificaciones_creadas = 0
            alumnos_procesados = set()
            
            for cuota in cuotas_proximas:
                if cuota.inscripcion.alumno_id in alumnos_procesados:
                    continue
                    
                alumnos_procesados.add(cuota.inscripcion.alumno_id)
                
                for coordinador in coordinadores:
                    # Verificar si ya existe notificación similar reciente (hoy)
                    existe_notif = Notificacion.objects.filter(
                        usuario_destino=coordinador,
                        tipo=tipo_recordatorio,
                        titulo__icontains=cuota.inscripcion.alumno.nombre_completo(),
                        fecha_creacion__date=hoy
                    ).exists()
                    
                    if not existe_notif:
                        dias_para_vencer = (cuota.fecha_vencimiento - hoy).days
                        Notificacion.objects.create(
                            usuario_destino=coordinador,
                            usuario_origen=None,  # Sistema
                            tipo=tipo_recordatorio,
                            titulo=f'Recordatorio de pago: {cuota.inscripcion.alumno.nombre_completo()}',
                            mensaje=f'El alumno {cuota.inscripcion.alumno.nombre_completo()} (DNI: {cuota.inscripcion.alumno.dni}) tiene una cuota que vence en {dias_para_vencer} día(s) ({cuota.fecha_vencimiento}). Monto: ${cuota.monto}. Curso: {cuota.inscripcion.curso.nombre}.',
                            estado='PENDIENTE',
                            prioridad='MEDIA',
                            es_manual=False
                        )
                        notificaciones_creadas += 1
                        print(f"DEBUG: Creada notificación para {cuota.inscripcion.alumno.nombre_completo()}")
            
            return JsonResponse({
                'success': True, 
                'message': f'Se generaron {notificaciones_creadas} recordatorios de pago para {len(alumnos_procesados)} alumnos con cuotas próximas a vencer',
                'notificaciones_creadas': notificaciones_creadas,
                'alumnos_procesados': len(alumnos_procesados),
                'cuotas_proximas': cuotas_proximas.count()
            })
            
        except Exception as e:
            import traceback
            print(f"ERROR en generar_recordatorios_pago: {str(e)}")
            print(f"Traceback: {traceback.format_exc()}")
            
            return JsonResponse({
                'success': False, 
                'error': f"Error: {str(e)}"
            }, status=500)
    
    return JsonResponse({
        'success': False, 
        'error': 'Método no permitido. Usa POST.'
    }, status=405)
    
    
@login_required
def debug_notificaciones_tareas(request):
    """Debug de las tareas de notificaciones"""
    context = {
        'urls': {
            'generar_mora': reverse('generar_notificaciones_mora_manual'),
            'recordatorios_pago': reverse('generar_recordatorios_pago'),
            'exportar_excel': reverse('exportar_moras_excel'),
            'seguimiento_moras': reverse('seguimiento_moras'),
        }
    }
    return render(request, 'web/debug/notificaciones_tareas.html', context)

@login_required
def debug_tareas_rapidas(request):
    """Debug de las tareas rápidas"""
    context = {
        'urls': {
            'generar_mora': '/web/notificaciones/generar-mora/',
            'recordatorios_pago': '/web/notificaciones/recordatorios-pago/',
            'exportar_excel': '/web/notificaciones/exportar-excel/',
        },
        'user': request.user,
        'es_coordinador': es_coordinador(request.user),
    }
    return render(request, 'web/debug/tareas_rapidas.html', context)


from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.contrib.auth.models import User, Group
from django.db.models import Count, Q
from django.utils import timezone
from datetime import date, timedelta

# =============================================================================
# DASHBOARDS ESPECÍFICOS
# =============================================================================

@login_required
def dashboard_administracion(request):
    print(f"[DEBUG-ADMIN] 🔍 Entrando en dashboard_administracion. Usuario: {request.user.username}")
    
    # VERIFICA si hay algún filtro de permisos/grupos al INICIO de esta vista:
    if not request.user.groups.filter(name='Administración').exists():
        print(f"[DEBUG-ADMIN] ⚠️  Usuario NO está en grupo 'Administración'. Esto causa un bucle si lo rediriges a 'dashboard'.")
        # COMENTA temporalmente cualquier redirección aquí para probar:
        # return redirect('dashboard')  # <-- COMENTA o ELIMINA esta línea para probar
        pass
    """Dashboard para administradores y coordinadores"""
    try:
        # Verificar que el usuario tenga permisos de administración
        if not request.user.groups.filter(name='Administración').exists():
            messages.error(request, "No tienes permisos para acceder a esta sección")
            #return redirect('dashboard')
        
        # Estadísticas generales
        from .models import Alumno, Profesor, Personal, Curso, Inscripcion
        
        hoy = date.today()
        
        context = {
            'total_alumnos': Alumno.objects.filter(activo=True, eliminado=False).count(),
            'total_profesores': Profesor.objects.filter(activo=True, eliminado=False).count(),
            'total_cursos': Curso.objects.filter(activo=True, eliminado=False).count(),
            'total_personal': Personal.objects.filter(activo=True, eliminado=False).count(),
            
            'alumnos_nuevos_hoy': Alumno.objects.filter(
                fecha_creacion__date=hoy,
                activo=True,
                eliminado=False
            ).count(),
            
            'cursos_proximos': Curso.objects.filter(
                fecha_inicio__gte=hoy,
                activo=True,
                eliminado=False
            ).order_by('fecha_inicio')[:5],
            
            'inscripciones_recientes': Inscripcion.objects.filter(
                activo=True
            ).select_related('alumno', 'curso').order_by('-fecha_inscripcion')[:10],
            
            'alumnos_con_deuda': 0,  # Puedes implementar esta lógica después
            'cursos_sin_profesor': Curso.objects.filter(
                profesor__isnull=True,
                activo=True,
                eliminado=False
            ).count(),
        }
        
        return render(request, 'web/dashboard/administracion.html', context)
        
    except Exception as e:
        print(f"❌ Error en dashboard_administracion: {e}")
        messages.error(request, f"Error al cargar el dashboard: {e}")
        #return redirect('dashboard')
    print(f"[DEBUG-ADMIN] ✅ Vista cargada correctamente.")
    return render(request, 'web/dashboard/administracion.html', context)


@login_required
def dashboard_personal(request):
    """Dashboard para personal no docente (secretarias, limpieza, seguridad, etc.)"""
    
    print("=" * 60)
    print(f"🎯 VISTA dashboard_personal - Usuario: {request.user.username}")
    
    # Obtener información del personal
    personal = obtener_personal_usuario(request.user)
    
    if not personal:
        print("❌ No se encontró personal asociado")
        messages.error(request, "No tienes perfil de personal asociado")
        return redirect('sin_permiso_personal')
    
    print(f"✅ Personal encontrado: {personal.nombre_completo()}, Tipo: {personal.tipo}")
    
    # Calcular estadísticas básicas (si es secretaria)
    estadisticas = {}
    if personal.tipo == 'SECRETARIA':
        try:
            from web.models import Alumno, Curso, Inscripcion
            estadisticas['total_alumnos'] = Alumno.objects.filter(activo=True, eliminado=False).count()
            estadisticas['total_cursos_sistema'] = Curso.objects.filter(activo=True, eliminado=False).count()
            estadisticas['total_inscripciones'] = Inscripcion.objects.filter(
                activo=True, eliminado=False
            ).count()
            print(f"📊 Estadísticas generales para secretaria: {estadisticas}")
        except Exception as e:
            print(f"⚠️ Error calculando estadísticas: {e}")
            estadisticas = {}
    
    # Calcular antigüedad
    from datetime import date
    if personal.fecha_ingreso:
        hoy = date.today()
        antiguedad = hoy.year - personal.fecha_ingreso.year
        if hoy.month < personal.fecha_ingreso.month or (hoy.month == personal.fecha_ingreso.month and hoy.day < personal.fecha_ingreso.day):
            antiguedad -= 1
    else:
        antiguedad = 0
    
    # **CORRECCIÓN PRINCIPAL: Obtener cursos donde este personal es auxiliar**
    cursos_asignados = 0
    cursos_asignados_lista = []
    
    try:
        from web.models import Curso
        # Obtener cursos donde este personal está asignado como auxiliar
        cursos_asignados_lista = Curso.objects.filter(
            auxiliar=personal,  # ¡Aquí está la clave!
            activo=True,
            eliminado=False
        ).select_related('profesor')  # Optimizar consultas
        
        cursos_asignados = cursos_asignados_lista.count()
        print(f"📚 Cursos asignados como auxiliar: {cursos_asignados}")
        
        # Imprimir primeros 3 cursos para debug
        for curso in cursos_asignados_lista[:3]:
            print(f"   - {curso.nombre} (Profesor: {curso.profesor})")
            
    except Exception as e:
        print(f"⚠️ Error contando cursos asignados: {e}")
    
    # **MANTENER BÚSQUEDA DE PROFESOR (para debug o futuros usos)**
    profesor_asociado = None
    try:
        from web.models import Profesor
        # Buscar si este personal tiene un perfil de profesor asociado
        if hasattr(personal, 'profesor'):
            profesor_asociado = personal.profesor
            print(f"🔍 Profesor asociado encontrado: {profesor_asociado}")
        else:
            # Intentar buscar por usuario
            profesor_asociado = Profesor.objects.filter(
                user=request.user,
                activo=True,
                eliminado=False
            ).first()
            if profesor_asociado:
                print(f"🔍 Profesor encontrado por usuario: {profesor_asociado.nombre_completo()}")
    except Exception as e:
        print(f"⚠️ Error en búsqueda de profesor asociado: {e}")
    
    # Determinar qué cursos mostrar en el dashboard
    # Para personal administrativo (secretaria, auxiliar, coordinador, administrativo) mostrar cursos donde son auxiliares
    # Para otro personal mostrar 0
    if personal.tipo in ['SECRETARIA', 'ADMINISTRATIVO', 'COORDINADOR']:
        cursos_mostrar = cursos_asignados  # Cursos donde es auxiliar
    else:
        cursos_mostrar = 0  # Limpieza, seguridad, etc.
    
    context = {
        'titulo': 'Mi Panel de Personal',
        'personal': personal,
        'personal_tipo': personal.tipo,
        'estadisticas': estadisticas,
        'es_personal': True,
        'es_secretaria': personal.tipo == 'SECRETARIA',
        'es_administrativo': personal.tipo in ['SECRETARIA', 'ADMINISTRATIVO', 'COORDINADOR'],
        'antiguedad': antiguedad,
        'cursos_asignados': cursos_mostrar,  # Para la tarjeta de estadísticas
        'cursos_asignados_lista': cursos_asignados_lista[:5],  # Primeros 5 para mostrar en tabla
        'total_cursos_asignados': cursos_asignados,  # Total real de cursos asignados
        'profesor_asociado': profesor_asociado,  # Para debug/información adicional
    }
    
    print(f"📁 Intentando cargar: web/dashboard/personal.html")
    print(f"📁 Cursos a mostrar en tarjeta: {cursos_mostrar}")
    print(f"📁 Total cursos asignados (como auxiliar): {cursos_asignados}")
    if personal.tipo == 'SECRETARIA':
        print(f"📊 Total cursos sistema: {estadisticas.get('total_cursos_sistema', 0)}")
    
    try:
        return render(request, 'web/dashboard/personal.html', context)
    except Exception as e:
        print(f"❌ Error cargando plantilla web/dashboard/personal.html: {e}")
        return render(request, 'web/base.html', context)


@login_required
def dashboard_redirect(request):
    """Redirige al dashboard correspondiente - VERSIÓN MEJORADA"""
    print(f"[DEBUG-REDIRECT] 🔍 Usuario: {request.user.username}")
    
    # Verificar si ya estamos en un bucle
    if hasattr(request, 'redirect_count'):
        request.redirect_count += 1
    else:
        request.redirect_count = 1
    
    if request.redirect_count > 3:
        print(f"[DEBUG-REDIRECT] 🚨 POSIBLE BUCLE DETECTADO. Redirigiendo a página segura.")
        messages.error(request, "Error de redirección. Contacte al administrador.")
        return redirect('index')  # Página segura, sin lógica de redirección
    
    try:
        # PRIMERO: Verificar Personal
        from .models import Personal
        try:
            personal = Personal.objects.get(user=request.user, activo=True, eliminado=False)
            print(f"[DEBUG-REDIRECT] ✅ Personal: {personal.nombre_completo}, Tipo: {personal.tipo}")
            
            if personal.tipo in ['ADMINISTRATIVO', 'COORDINADOR']:
                return redirect('dashboard_administracion')
            else:
                return redirect('dashboard_personal')
                
        except Personal.DoesNotExist:
            print(f"[DEBUG-REDIRECT] ❌ No es Personal")
        
        # SEGUNDO: Verificar Alumno
        from .models import Alumno
        try:
            alumno = Alumno.objects.get(user=request.user, activo=True, eliminado=False)
            print(f"[DEBUG-REDIRECT] ✅ Es Alumno")
            return redirect('dashboard_alumno')
        except Alumno.DoesNotExist:
            print(f"[DEBUG-REDIRECT] ❌ No es Alumno")
        
        # TERCERO: Verificar Profesor
        from .models import Profesor
        try:
            profesor = Profesor.objects.get(user=request.user, activo=True, eliminado=False)
            print(f"[DEBUG-REDIRect] ✅ Es Profesor")
            return redirect('dashboard_profesor')
        except Profesor.DoesNotExist:
            print(f"[DEBUG-REDIRECT] ❌ No es Profesor")
        
        # SI LLEGA AQUÍ: Usuario sin perfil asociado
        print(f"[DEBUG-REDIRECT] 🚨 Usuario sin perfil asociado.")
        messages.error(request, "Tu usuario no tiene un perfil activo en el sistema.")
        return redirect('login')
        
    except Exception as e:
        print(f"[DEBUG-REDIRECT] ❌ Error: {str(e)}")
        messages.error(request, f"Error al determinar tu perfil: {str(e)}")
        return redirect('index')

@login_required
def dashboard_alumno(request):
    """Dashboard específico para alumnos"""
    try:
        from .models import Alumno
        
        alumno = Alumno.objects.get(user=request.user, activo=True, eliminado=False)
        
        context = {
            'alumno': alumno,
            'inscripciones_activas': alumno.inscripcion_set.filter(
                activo=True, 
                estado__in=['INSCRIPTO', 'CURSANDO']
            ),
            'cursos_activos': alumno.cursos_activos,
            'certificados': alumno.inscripcion_set.filter(
                estado='APROBADO',
                certificado__isnull=False
            ).select_related('certificado'),
        }
        return render(request, 'web/dashboard/alumno.html', context)
        
    except Alumno.DoesNotExist:
        messages.error(request, "No tienes un perfil de alumno activo")
        return redirect('login')
    except Exception as e:
        print(f"❌ Error en dashboard_alumno: {e}")
        messages.error(request, f"Error al cargar el dashboard: {e}")
        return redirect('dashboard')

@login_required
@requiere_permiso_profesor
def dashboard_profesor(request):
    """Dashboard específico para profesores"""
    try:
        # El decorador @requiere_permiso_profesor ya configuró esto
        profesor = request.profesor
        
        if not profesor:
            messages.error(request, "No tienes un perfil de profesor activo")
            return redirect('login')
        
        # Obtener cursos asignados
        cursos_asignados = Curso.objects.filter(
            profesor=profesor,
            activo=True,
            eliminado=False
        )
        
        hoy = date.today()
        
        # Calcular total de alumnos (asegurándonos de que cada curso tenga el método total_alumnos)
        total_alumnos = 0
        for curso in cursos_asignados:
            total_alumnos += curso.total_alumnos
        
        context = {
            'profesor': profesor,
            'cursos_asignados': cursos_asignados,
            'total_alumnos': total_alumnos,
            'proximas_clases': cursos_asignados.filter(
                fecha_inicio__gte=hoy
            ).order_by('fecha_inicio')[:5],
        }
        return render(request, 'web/profesores/dashboard.html', context)  # Cambia el template path
        
    except Exception as e:
        print(f"❌ Error en dashboard_profesor: {e}")
        import traceback
        print(traceback.format_exc())
        messages.error(request, f"Error al cargar el dashboard: {e}")
        return redirect('dashboard') 
    

# =============================================================================
# FUNCIONES AUXILIARES PARA DASHBOARDS
# =============================================================================

def es_administrador(user):
    """Verifica si el usuario pertenece al grupo Administración"""
    return user.groups.filter(name='Administración').exists()

def es_profesor(user):
    """Verifica si el usuario pertenece al grupo Profesores"""
    return user.groups.filter(name='Profesores').exists()

def es_alumno(user):
    """Verifica si el usuario pertenece al grupo Alumnos"""
    return user.groups.filter(name='Alumnos').exists()

def es_personal(user):
    """Verifica si el usuario pertenece al grupo Personal"""
    return user.groups.filter(name='Personal').exists()

# =============================================================================
# GESTIÓN DE USUARIOS - VISTAS NUEVAS
# =============================================================================

@login_required
@permission_required('auth.view_user', raise_exception=True)
def gestion_usuarios(request):
    """Vista principal de gestión de usuarios del sistema"""
    
    # 1. Usuarios con Personal asociado NO ELIMINADO
    usuarios_personal = Personal.objects.filter(
        user__isnull=False, 
        eliminado=False
    ).select_related('user')
    
    # 2. IDs de usuarios que tienen Personal NO ELIMINADO
    ids_usuarios_con_personal_valido = usuarios_personal.values_list('user__id', flat=True)
    
    # 3. Todos los usuarios que NO están en la lista anterior y NO son superusuarios
    usuarios_sin_personal = User.objects.exclude(
        id__in=ids_usuarios_con_personal_valido
    ).exclude(
        is_superuser=True
    ).order_by('-date_joined')
    
    # 4. Estadísticas CORREGIDAS
    total_usuarios = User.objects.exclude(is_superuser=True).count()  # Todos excepto superusuarios
    usuarios_activos = User.objects.filter(is_active=True, is_superuser=False).count()
    usuarios_inactivos = total_usuarios - usuarios_activos
    
    # DEBUG - para ver qué está pasando
    print(f"DEBUG - Total usuarios (sin superusers): {total_usuarios}")
    print(f"DEBUG - Usuarios con personal válido: {usuarios_personal.count()}")
    print(f"DEBUG - Usuarios sin personal: {usuarios_sin_personal.count()}")
    
    context = {
        'usuarios_personal': usuarios_personal,
        'usuarios_sin_personal': usuarios_sin_personal,
        'total_usuarios': total_usuarios,
        'usuarios_activos': usuarios_activos,
        'usuarios_inactivos': usuarios_inactivos,
    }
    return render(request, 'usuarios/gestion_usuarios.html', context)

@login_required
@user_passes_test(es_administrador)
def asignar_usuario_persona(request, persona_id):
    """Asigna o crea usuario para una persona"""
    try:
        from .models import Alumno, Profesor, Personal
        from django.shortcuts import get_object_or_404
        
        # Determinar el tipo de persona
        persona = None
        tipo = None
        
        for model, tipo_str in [(Alumno, 'alumno'), (Profesor, 'profesor'), (Personal, 'personal')]:
            try:
                persona = model.objects.get(id=persona_id, activo=True, eliminado=False)
                tipo = tipo_str
                break
            except model.DoesNotExist:
                continue
        
        if not persona:
            messages.error(request, "Persona no encontrada")
            return redirect('gestion_usuarios')
        
        if request.method == 'POST':
            if persona.user:
                messages.info(request, f"{persona.nombre_completo()} ya tiene usuario asignado")
                return redirect('gestion_usuarios')
            
            # Crear usuario
            usuario_creado = persona.crear_usuario_sistema(request.user)
            
            if usuario_creado:
                messages.success(request, f"Usuario creado exitosamente: {usuario_creado.username}")
                
                # Si se solicitó enviar credenciales por email
                if request.POST.get('enviar_credenciales'):
                    # Aquí puedes implementar el envío de email
                    messages.info(request, f"Credenciales enviadas a: {persona.mail}")
            else:
                messages.error(request, "Error al crear el usuario")
            
            return redirect('gestion_usuarios')
        
        context = {
            'persona': persona,
            'tipo': tipo.capitalize(),
        }
        
        return render(request, 'usuarios/asignar_usuario.html', context)
        
    except Exception as e:
        print(f"❌ Error en asignar_usuario_persona: {e}")
        messages.error(request, f"Error al asignar usuario: {e}")
        return redirect('gestion_usuarios')

@login_required
@user_passes_test(es_administrador)
def desactivar_usuario(request, user_id):
    """Desactiva un usuario del sistema"""
    try:
        user = get_object_or_404(User, id=user_id)
        
        if user == request.user:
            messages.error(request, "No puedes desactivar tu propio usuario")
            return redirect('gestion_usuarios')
        
        user.is_active = False
        user.save()
        
        # Actualizar la persona asociada
        from .models import Alumno, Profesor, Personal
        
        for model in [Alumno, Profesor, Personal]:
            try:
                persona = model.objects.get(user=user)
                persona.puede_acceder_sistema = False
                persona.save()
                break
            except model.DoesNotExist:
                continue
        
        messages.success(request, f"Usuario {user.username} desactivado exitosamente")
        
    except Exception as e:
        print(f"❌ Error en desactivar_usuario: {e}")
        messages.error(request, f"Error al desactivar usuario: {e}")
    
    return redirect('gestion_usuarios')

@login_required
@user_passes_test(es_administrador)
def reactivar_usuario(request, user_id):
    """Reactivar un usuario del sistema"""
    try:
        user = get_object_or_404(User, id=user_id)
        
        user.is_active = True
        user.save()
        
        # Actualizar la persona asociada
        from .models import Alumno, Profesor, Personal
        
        for model in [Alumno, Profesor, Personal]:
            try:
                persona = model.objects.get(user=user)
                persona.puede_acceder_sistema = True
                persona.save()
                break
            except model.DoesNotExist:
                continue
        
        messages.success(request, f"Usuario {user.username} reactivado exitosamente")
        
    except Exception as e:
        print(f"❌ Error en reactivar_usuario: {e}")
        messages.error(request, f"Error al reactivar usuario: {e}")
    
    return redirect('gestion_usuarios')

@login_required
@user_passes_test(es_administrador)
def reset_password_usuario(request, user_id):
    """Resetear contraseña de un usuario"""
    try:
        user = get_object_or_404(User, id=user_id)
        
        if request.method == 'POST':
            from django.contrib.auth.hashers import make_password
            from django.utils.crypto import get_random_string
            
            nueva_password = get_random_string(10)
            user.password = make_password(nueva_password)
            user.save()
            
            messages.success(request, f"Contraseña reseteada para {user.username}")
            messages.info(request, f"Nueva contraseña: {nueva_password}")
            
            return redirect('gestion_usuarios')
        
        context = {
            'usuario': user,
        }
        
        return render(request, 'usuarios/reset_password.html', context)
        
    except Exception as e:
        print(f"❌ Error en reset_password_usuario: {e}")
        messages.error(request, f"Error al resetear contraseña: {e}")
        return redirect('gestion_usuarios')
    
#########################################################################
#                  ERRORES FALTA DE PERMISOS                            #
######################################################################### 
    

@login_required(login_url='login')
def sin_permiso_personal(request):
    """
    Vista que muestra una página amigable cuando no tienes permisos
    Se puede acceder desde múltiples decoradores
    """
    # Obtener el último mensaje (si hay)
    from django.contrib import messages
    mensajes = messages.get_messages(request)
    mensaje_permiso = ""
    
    for mensaje in mensajes:
        if "No tienes" in str(mensaje) or "permiso" in str(mensaje).lower():
            mensaje_permiso = str(mensaje)
    
    # Determinar tipo de error basado en el usuario
    contexto = {
        'user': request.user,
        'mensaje_especifico': mensaje_permiso,
    }
    
    # Verificar si es porque no tiene personal
    if not hasattr(request.user, 'personal_relacionado'):
        contexto['tipo_error'] = 'sin_personal'
        contexto['titulo'] = '❌ Usuario sin perfil de Personal'
    else:
        personal = request.user.personal_relacionado
        contexto['tipo_error'] = 'sin_permiso'
        contexto['titulo'] = '🔒 Permiso Denegado'
        contexto['tu_rol'] = personal.tipo
    
    return render(request, 'web/errors/sin_permiso.html', contexto, status=403)

from django.contrib.auth.decorators import login_required
from django.shortcuts import render

@login_required(login_url='login')
def sin_permiso_personal(request):
    """
    Vista que muestra página amigable cuando no hay permisos
    """
    # Recopilar mensajes de error
    from django.contrib import messages
    mensajes = list(messages.get_messages(request))
    
    contexto = {
        'user': request.user,
        'mensajes': mensajes,
    }
    
    # Intentar obtener información del personal para contexto
    try:
        if hasattr(request.user, 'personal_relacionado'):
            personal = request.user.personal_relacionado
            contexto['personal'] = personal
            contexto['tipo_error'] = 'sin_permiso'
        else:
            contexto['tipo_error'] = 'sin_personal'
    except:
        contexto['tipo_error'] = 'generico'
    
    return render(request, 'web/errors/sin_permiso.html', contexto, status=403)



# En views.py
def depurar_vista_curso(request, curso_id):
    import sys
    print("=" * 50)
    print("¡VISTA DE DEPURACIÓN EJECUTADA!")
    print(f"Request path: {request.path}")
    print(f"Curso ID: {curso_id}")
    print(f"User: {request.user}")
    print("=" * 50)
    
    from django.http import HttpResponse
    return HttpResponse(f"<h1>Depuración exitosa</h1><p>Curso ID: {curso_id}</p>")

# @login_required
# def dashboard_permisos(request):
#     """
#     Vista para el dashboard de gestión de permisos.
#     Solo accesible para coordinadores y superusuarios.
#     """
    
#     # 1. VERIFICACIÓN DE PERMISOS
#     # Verifica que el usuario tenga acceso (coordinador o superuser)
#     if not request.user.is_authenticated:
#         return redirect('login')
    
#     # Ajusta esta verificación según tu modelo de usuario
#     tiene_acceso = False
    
#     # Opción 1: Si usas un modelo Personal relacionado
#     if hasattr(request.user, 'personal'):
#         if request.user.personal.tipo == 'COORDINADOR' or request.user.is_superuser:
#             tiene_acceso = True
    
#     # Opción 2: Si usas grupos de Django
#     # elif request.user.groups.filter(name='Coordinadores').exists() or request.user.is_superuser:
#     #     tiene_acceso = True
    
#     # Opción 3: Permisos específicos
#     # elif request.user.has_perm('web.gestion_permisos') or request.user.is_superuser:
#     #     tiene_acceso = True
    
#     if not tiene_acceso:
#         messages.error(request, "No tienes permisos para acceder a esta sección.")
#         return redirect('index')  # Cambia por tu URL de inicio
    
#     # 2. OBTENER DATOS PARA EL DASHBOARD
#     # Aquí obtienes los datos que necesitas mostrar en el dashboard
    
#     # Ejemplo 1: Lista de usuarios con sus permisos
#     from django.contrib.auth.models import User
#     from django.contrib.auth.models import Permission, Group
    
#     # Obtener todos los usuarios (o filtrar por algún criterio)
#     usuarios = User.objects.filter(is_active=True).select_related('personal')
    
#     # Obtener todos los grupos disponibles
#     grupos = Group.objects.all()
    
#     # Obtener todos los permisos disponibles
#     permisos = Permission.objects.all()
    
#     # Ejemplo 2: Si tienes un modelo Personal
#     try:
#         from .models import Personal
#         personal_activo = Personal.objects.filter(activo=True)
#     except:
#         personal_activo = []
    
#     # 3. PROCESAR FILTROS Y BÚSQUEDAS (si aplica)
#     filtro_usuario = request.GET.get('usuario', '')
#     filtro_grupo = request.GET.get('grupo', '')
    
#     if filtro_usuario:
#         usuarios = usuarios.filter(
#             Q(username__icontains=filtro_usuario) |
#             Q(first_name__icontains=filtro_usuario) |
#             Q(last_name__icontains=filtro_usuario) |
#             Q(email__icontains=filtro_usuario)
#         )
    
#     if filtro_grupo:
#         usuarios = usuarios.filter(groups__name__icontains=filtro_grupo)
    
#     # 4. PAGINACIÓN
#     paginator = Paginator(usuarios, 20)  # 20 usuarios por página
#     page_number = request.GET.get('page')
#     page_obj = paginator.get_page(page_number)
    
#     # 5. CONTEXTO PARA LA PLANTILLA
#     context = {
#         'titulo': 'Gestión de Permisos',
#         'subtitulo': 'Dashboard de Administración de Permisos',
        
#         # Datos
#         'page_obj': page_obj,
#         'grupos': grupos,
#         'permisos': permisos,
#         'personal_activo': personal_activo,
        
#         # Filtros actuales (para mantener en la UI)
#         'filtro_usuario': filtro_usuario,
#         'filtro_grupo': filtro_grupo,
        
#         # Estadísticas (ejemplo)
#         'total_usuarios': usuarios.count(),
#         'total_grupos': grupos.count(),
#         'total_permisos': permisos.count(),
        
#         # Información del usuario actual
#         'usuario_actual': request.user,
#     }
    
#     # 6. RENDERIZAR LA PLANTILLA
#     return render(request, 'permisos/dashboard.html', context)

# web/views.py
def dashboard_permisos(request):
    """Vista básica para el dashboard de permisos"""
    context = {
        'titulo': 'Dashboard de Permisos',
        'mensaje': 'Gestión de permisos de usuarios'
    }
    return render(request, 'permisos/dashboard.html', context)

# web/views.py - AGREGAR DESPUÉS DE dashboard_permisos

from django.contrib.auth.models import Group, Permission
from django.contrib.auth.decorators import permission_required


def listar_grupos_permisos(request):
    """Lista todos los grupos y permisos disponibles"""
    grupos = Group.objects.all().prefetch_related('permissions').order_by('id')  # Ordenar por ID
    permisos = Permission.objects.all()
    
    # Lista de grupos protegidos que no se pueden eliminar
    grupos_protegidos = [
        'Coordinador', 'Administrativo', 'Secretaría', 'Consulta',
        'Personal', 'Administración', 'Alumnos', 'Profesores'
    ]
    
    # DEBUG: Verificar que todos los grupos tienen ID
    for grupo in grupos:
        print(f"Grupo: {grupo.name}, ID: {grupo.id}")
    
    context = {
        'titulo': 'Grupos y Permisos',
        'grupos': grupos,
        'permisos': permisos,
        'grupos_protegidos': grupos_protegidos,
    }
    return render(request, 'permisos/listar_grupos_permisos.html', context)


@permission_required('auth.add_group', raise_exception=True)
def crear_nuevo_grupo(request):
    """Crea un nuevo grupo de usuarios"""
    if request.method == 'POST':
        nombre = request.POST.get('nombre')
        descripcion = request.POST.get('descripcion', '')
        permisos_ids = request.POST.getlist('permisos')
        
        if nombre:
            grupo = Group.objects.create(name=nombre)
            # Si necesitas almacenar descripción, puedes usar un campo personalizado
            # o agregar metadata
            
            if permisos_ids:
                permisos = Permission.objects.filter(id__in=permisos_ids)
                grupo.permissions.set(permisos)
            
            messages.success(request, f'Grupo "{nombre}" creado exitosamente')
            return redirect('listar_grupos_permisos')
    
    permisos = Permission.objects.all()
    context = {
        'titulo': 'Crear Nuevo Grupo',
        'permisos': permisos,
    }
    return render(request, 'permisos/crear_grupo.html', context)

@permission_required('auth.add_permission', raise_exception=True)
def crear_nuevo_permiso(request):
    """Vista para crear permisos personalizados (si es necesario)"""
    # Nota: En Django, los permisos generalmente se crean automáticamente
    # con los modelos. Esta vista podría ser para explicar cómo funcionan.
    
    context = {
        'titulo': 'Crear Nuevo Permiso',
        'mensaje': 'En Django, los permisos se crean automáticamente con los modelos.',
        'info': 'Para agregar un permiso, primero debes definir un modelo en models.py',
    }
    return render(request, 'permisos/crear_permiso.html', context)

@permission_required('auth.change_user', raise_exception=True)
def asignar_permisos_usuario(request, user_id=None):
    """Asigna permisos y grupos a un usuario específico."""
    
    if user_id:
        # Modo de asignación a un usuario específico
        usuario = get_object_or_404(User, id=user_id)
        
        if request.method == 'POST':
            # Procesar asignación de permisos
            permisos_ids = request.POST.getlist('permisos')
            grupos_ids = request.POST.getlist('grupos')
            
            # Asignar permisos directos
            usuario.user_permissions.clear()
            if permisos_ids:
                permisos = Permission.objects.filter(id__in=permisos_ids)
                usuario.user_permissions.set(permisos)
            
            # Asignar grupos
            usuario.groups.clear()
            if grupos_ids:
                grupos = Group.objects.filter(id__in=grupos_ids)
                usuario.groups.set(grupos)
            
            messages.success(request, f'Permisos actualizados para {usuario.username}')
            return redirect('asignar_permisos_usuario', user_id=user_id)
        
        # Obtener datos actuales
        grupos = Group.objects.all()
        permisos = Permission.objects.all()
        grupos_usuario = usuario.groups.all()
        permisos_usuario = usuario.user_permissions.all()
        
        context = {
            'titulo': f'Asignar Permisos a {usuario.username}',
            'usuario': usuario,
            'grupos': grupos,
            'permisos': permisos,
            'grupos_usuario': grupos_usuario,
            'permisos_usuario': permisos_usuario,
        }
        return render(request, 'permisos/asignar_permisos_usuario.html', context)
    else:
        # Modo de selección de usuario (lista de usuarios)
        usuarios = User.objects.filter(is_active=True).order_by('username')
        
        context = {
            'titulo': 'Seleccionar Usuario',
            'usuarios': usuarios,
        }
        return render(request, 'permisos/seleccionar_usuario.html', context)
    

@permission_required('auth.change_group', raise_exception=True)
def editar_permisos_grupo(request, grupo_id):
    """Vista para editar los permisos de un grupo existente."""
    grupo = get_object_or_404(Group, id=grupo_id)
    
    if request.method == 'POST':
        # Obtener los permisos seleccionados
        permisos_ids = request.POST.getlist('permisos')
        
        # Actualizar los permisos del grupo
        permisos = Permission.objects.filter(id__in=permisos_ids)
        grupo.permissions.set(permisos)
        
        messages.success(request, f'Permisos del grupo "{grupo.name}" actualizados correctamente.')
        return redirect('listar_grupos_permisos')
    
    # Obtener todos los permisos y los permisos actuales del grupo
    todos_permisos = Permission.objects.all()
    permisos_grupo = grupo.permissions.all()
    
    context = {
        'titulo': f'Editar Permisos del Grupo: {grupo.name}',
        'grupo': grupo,
        'todos_permisos': todos_permisos,
        'permisos_grupo': permisos_grupo,
    }
    return render(request, 'permisos/editar_permisos_grupo.html', context)

@permission_required('auth.delete_group', raise_exception=True)
def eliminar_grupo(request, grupo_id):
    """Vista para eliminar un grupo de usuarios."""
    grupo = get_object_or_404(Group, id=grupo_id)
    
    # Lista de grupos protegidos que no se pueden eliminar
    grupos_protegidos = [
        'Coordinador', 'Administrativo', 'Secretaría', 'Consulta',
        'Personal', 'Administración', 'Alumnos', 'Profesores'
    ]
    
    if grupo.name in grupos_protegidos:
        messages.error(request, f'No se puede eliminar el grupo "{grupo.name}" porque es un grupo protegido.')
        return redirect('listar_grupos_permisos')
    
    if request.method == 'POST':
        nombre_grupo = grupo.name
        grupo.delete()
        messages.success(request, f'Grupo "{nombre_grupo}" eliminado correctamente.')
        return redirect('listar_grupos_permisos')
    
    # Si es GET, mostrar confirmación
    context = {
        'titulo': f'Eliminar Grupo: {grupo.name}',
        'grupo': grupo,
    }
    return render(request, 'permisos/confirmar_eliminar_grupo.html', context)

def test_fechas_clase(request):
    """Vista de prueba para generar_fechas_clase"""
    from datetime import date
    from web.utils import generar_fechas_clase
    
    # Datos de prueba
    fecha_inicio = date(2026, 1, 1)
    fecha_fin = date(2026, 1, 31)
    dias_curso = "LUNES,MIERCOLES,VIERNES"
    
    try:
        fechas = generar_fechas_clase(fecha_inicio, fecha_fin, dias_curso)
        print(f"✅ Fechas generadas: {len(fechas)}")
        for f in fechas:
            print(f"  - {f}")
    except Exception as e:
        print(f"❌ Error: {e}")
    
    return HttpResponse("Revisa la consola para los resultados")