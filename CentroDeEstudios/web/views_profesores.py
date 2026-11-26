import unicodedata

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.template import TemplateDoesNotExist
from django.utils import timezone
from django.db.models import Q, Avg, Count, Sum
from django.http import HttpResponse, JsonResponse
from django.core.paginator import Paginator
from django.views.decorators.http import require_POST, require_GET
import json
from datetime import datetime, date
import xlwt
from .decorators import tiene_acceso_vistas_profesor, es_administrador_o_coordinador
from .forms import AltaAlumnoForm as AltaAlumnoForm, AltaCursoForm as AltaCursoForm, AltaPersonalForm as AltaPersonalForm, AltaProfesorForm as AltaProfesorForm, Alumno as Alumno, ArchivoAlumno as ArchivoAlumno, ArchivoAlumnoForm as ArchivoAlumnoForm, ArchivoCurso as ArchivoCurso, ArchivoCursoForm as ArchivoCursoForm, AsignarPermisosForm as AsignarPermisosForm, AsignarTareaCompaneroForm as AsignarTareaCompaneroForm, AsignarUsuarioForm as AsignarUsuarioForm, Asistencia as Asistencia, AsistenciaForm as AsistenciaForm, BuscarAlumnoForm as BuscarAlumnoForm, CambiarEstadoInscripcionForm as CambiarEstadoInscripcionForm, CambiarPasswordForm as CambiarPasswordForm, CuotaAlumno as CuotaAlumno, CuotaAlumnoForm as CuotaAlumnoForm, Curso as Curso, DetallePago as DetallePago, EditarAlumnoForm as EditarAlumnoForm, EditarPerfilProfesorForm as EditarPerfilProfesorForm, EditarUsuarioForm as EditarUsuarioForm, ErrorList as ErrorList, Examen as Examen, ExamenForm as ExamenForm, FiltroCursoForm as FiltroCursoForm, FiltroInscripcionesForm as FiltroInscripcionesForm, FiltroUsuariosForm as FiltroUsuariosForm, GestionUsuariosForm as GestionUsuariosForm, Inscripcion as Inscripcion, InscripcionCompletaForm as InscripcionCompletaForm, InscripcionForm as InscripcionForm, MAXYEAR as MAXYEAR, MINYEAR as MINYEAR, Notificacion as Notificacion, NotificacionRapidaForm as NotificacionRapidaForm, ObservacionAlumno as ObservacionAlumno, ObservacionForm as ObservacionForm, Pago as Pago, Permission as Permission, Personal as Personal, PersonalEditForm as PersonalEditForm, PersonalFilterForm as PersonalFilterForm, PersonalForm as PersonalForm, Profesor as Profesor, Q as Q, RegistrarNotaForm as RegistrarNotaForm, RegistroUsuarioForm as RegistroUsuarioForm, TipoNotificacion as TipoNotificacion, UTC as UTC, User as User, UserCreationForm as UserCreationForm, ValidationError as ValidationError, date as date, datetime as datetime, forms as forms, get_user_model as get_user_model, inlineformset_factory as inlineformset_factory, os as os, time as time, timedelta as timedelta, timezone as timezone, tzinfo as tzinfo
from .forms_profesores import Asistencia as Asistencia, AsistenciaForm as AsistenciaForm, EditarPerfilProfesorForm as EditarPerfilProfesorForm, Examen as Examen, ExamenForm as ExamenForm, ObservacionAlumno as ObservacionAlumno, ObservacionForm as ObservacionForm, ValidationError as ValidationError, forms as forms, timezone as timezone
# Importar los NUEVOS decoradores
from .decorators import (
    puede_ver_vistas_profesor, 
    puede_ver_cursos_profesor,
    profesor_solo_lectura,
    es_administrador_o_coordinador,
    obtener_profesor_usuario,
    tiene_acceso_vistas_profesor,
    requiere_permiso_profesor,
    puede_tomar_asistencia,
)

from .models import (
    Personal, Profesor, Curso, Inscripcion, Alumno, 
    Asistencia, Examen, ObservacionAlumno,
    Notificacion, HistorialCambios, CuotaAlumno, TipoNotificacion,
)

# web/views_profesores.py - Agrega al inicio del archivo

def obtener_profesor_para_vista(request, profesor_id=None):
    """
    FunciÃ³n auxiliar para obtener el profesor correcto segÃºn el contexto:
    1. Si se pasa profesor_id: devuelve ese profesor (para admin viendo otros)
    2. Si no: devuelve el profesor del usuario actual (si es profesor)
    3. Si es admin sin profesor: devuelve None y un mensaje apropiado
    """
    
    es_admin = getattr(request, 'es_administrador', False)
    profesor_actual = getattr(request, 'profesor', None)
    
    # CASO 1: Se solicita un profesor especÃ­fico por ID
    if profesor_id:
        if not es_admin:
            return None, "No tienes permiso para ver informaciÃ³n de otros profesores"
        
        try:
            profesor = Profesor.objects.get(
                id=profesor_id,
                activo=True,
                eliminado=False
            )
            return profesor, None
        except Profesor.DoesNotExist:
            return None, "El profesor solicitado no existe o no estÃ¡ activo"
    
    # CASO 2: Usuario es profesor, devolver su perfil
    elif profesor_actual:
        return profesor_actual, None
    
    # CASO 3: Es admin sin profesor especÃ­fico
    elif es_admin:
        return None, "Selecciona un profesor para ver su informaciÃ³n"
    
    # CASO 4: No es admin ni tiene perfil
    else:
        return None, "No tienes un perfil de profesor activo"

# ============================================
# DASHBOARD Y PERFIL (ACCESO AMPLIADO)
# ============================================
from django.utils import timezone
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .models import Curso, Notificacion, Asistencia

@login_required
@requiere_permiso_profesor
def dashboard_profesor(request):
    """Dashboard principal - Acceso para profesores y administradores"""
    
    # Determinar quÃ© mostrar segÃºn el tipo de usuario
    es_admin = getattr(request, 'es_administrador', False)
    profesor = getattr(request, 'profesor_actual', None)  # Usar profesor_actual segÃºn logs
    
    if es_admin and not profesor:
        # Administrador sin perfil de profesor - redirigir a dashboard admin
        return redirect('dashboard_admin_general')
    
    # Si llega aquÃ­, es un profesor (o admin con perfil de profesor)
    hoy = timezone.now().date()
    
    if profesor:
        # Obtener cursos asignados
        cursos_asignados = profesor.cursos_asignados.filter(activo=True, eliminado=False)
        total_cursos = cursos_asignados.count()
        
        # Calcular total de alumnos en todos los cursos
        total_alumnos = 0
        for curso in cursos_asignados:
            total_alumnos += curso.total_alumnos  # Usa la propiedad total_alumnos del modelo Curso
        
        # Cursos prÃ³ximos (con fecha de inicio mayor o igual a hoy)
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
            print(f"âš ï¸ Error calculando asistencias pendientes: {e}")
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
        'total_alumnos': total_alumnos,  # Â¡AÃ±adido!
        'proximas_clases': proximas_clases,  # Â¡AÃ±adido! (no cursos_proximos)
        'asistencias_pendientes': asistencias_pendientes,  # Â¡AÃ±adido!
        'notificaciones': notificaciones,
        'hoy': hoy,
        'es_administrador': es_admin,
        'es_profesor': True,
        'modo_vista': 'profesor',  # Â¡AÃ±adido! (necesario para el template)
    }
    
    return render(request, 'web/profesores/dashboard.html', context)


def perfil_profesor(request, profesor_id=None):
    """Perfil de profesor - VersiÃ³n unificada"""
    
    profesor, error_msg = obtener_profesor_para_vista(request, profesor_id)
    
    if error_msg:
        messages.info(request, error_msg)
        # Si es admin, redirigir a lista para seleccionar profesor
        if getattr(request, 'es_administrador', False):
            return redirect('listar_profesores')
        else:
            return redirect('dashboard_profesor')
    
    # Obtener informaciÃ³n adicional del profesor
    cursos = profesor.cursos_asignados.filter(activo=True, eliminado=False)
    
    context = {
        'profesor': profesor,
        'cursos': cursos,
        'total_cursos': cursos.count(),
        'es_administrador': getattr(request, 'es_administrador', False),
        'es_mi_perfil': (getattr(request, 'profesor', None) and 
                        getattr(request, 'profesor').id == profesor.id),
    }
    
    return render(request, 'web/profesores/perfil.html', context)

# ============================================
# CURSOS (DIFERENCIADO POR ROL)
# ============================================

@login_required
@requiere_permiso_profesor
def mis_cursos(request):
    """Lista de cursos - Diferente para profesores y administradores"""
    from django.db.models import Q
    from django.core.paginator import Paginator
    from django.utils import timezone
    from django.contrib import messages
    from .models import Profesor, Curso, Alumno

    print("=== INICIO mis_cursos ===")

    # OBTENER PROFESOR DE FORMA SEGURA Y COMPLETA
    profesor = None
    if hasattr(request, 'profesor') and request.profesor:
        # Si viene del decorador, puede tener datos incompletos, así que recargamos
        profesor = Profesor.objects.get(id=request.profesor.id)
        print(f"✅ Profesor recargado desde request.profesor: {profesor}")
    elif hasattr(request, 'profesor_obj') and request.profesor_obj:
        profesor = Profesor.objects.get(id=request.profesor_obj.id)
        print(f"✅ Profesor recargado desde request.profesor_obj: {profesor}")
    else:
        try:
            profesor = Profesor.objects.get(user=request.user)
            print(f"✅ Profesor obtenido de base de datos: {profesor}")
        except Profesor.DoesNotExist:
            profesor = None
            print(f"⚠️ No se encontró profesor para el usuario: {request.user.username}")

    # DETERMINAR SI ES ADMINISTRADOR
    es_admin = False
    if hasattr(request, 'es_administrador'):
        es_admin = request.es_administrador
    else:
        es_admin = request.user.is_superuser or request.user.groups.filter(
            name__in=['Administrativo', 'Coordinador']
        ).exists()
    print(f"🔍 Es administrador: {es_admin}")

    # FECHA ACTUAL
    hoy = timezone.now().date()
    print(f"📅 Fecha actual: {hoy}")

    # FILTROS DE LA SOLICITUD
    estado = request.GET.get('estado', 'no_finalizados')  # Por defecto: activos + próximos
    busqueda = request.GET.get('buscar', '')

    # CONSTRUIR QUERY BASE SEGÚN ROL
    if es_admin:
        base_qs = Curso.objects.filter(eliminado=False)
        titulo = "Todos los Cursos"
        mostrar_profesor = False   # No hay un profesor específico en admin
        profesor_context = None
    else:
        if not profesor:
            messages.error(request, "No tienes permisos para acceder a esta sección.")
            return redirect('home')
        base_qs = profesor.cursos_asignados.filter(eliminado=False)
        titulo = "Mis Cursos"
        mostrar_profesor = True
        profesor_context = profesor  # Profesor completo

    # APLICAR FILTRO POR ESTADO
    if estado == 'activos':
        cursos_qs = base_qs.filter(
            activo=True,
            fecha_inicio__lte=hoy,
            fecha_fin__gte=hoy
        )
    elif estado == 'proximos':
        cursos_qs = base_qs.filter(
            activo=True,
            fecha_inicio__gt=hoy
        )
    elif estado == 'finalizados':
        cursos_qs = base_qs.filter(
            activo=True,
            fecha_fin__lt=hoy
        )
    elif estado == 'inactivos':
        cursos_qs = base_qs.filter(activo=False)
    elif estado == 'no_finalizados':
        cursos_qs = base_qs.filter(
            activo=True,
            fecha_fin__gte=hoy   # Incluye activos y próximos
        )
    else:  # 'todos'
        cursos_qs = base_qs

    # BÚSQUEDA
    if busqueda:
        if es_admin:
            cursos_qs = cursos_qs.filter(
                Q(nombre__icontains=busqueda) |
                Q(dias__icontains=busqueda) |
                Q(horario__icontains=busqueda) |
                Q(profesor__nombre__icontains=busqueda) |
                Q(profesor__apellido__icontains=busqueda)
            )
        else:
            cursos_qs = cursos_qs.filter(
                Q(nombre__icontains=busqueda) |
                Q(dias__icontains=busqueda) |
                Q(horario__icontains=busqueda)
            )

    cursos_qs = cursos_qs.order_by('-fecha_inicio')

    # PAGINACIÓN
    paginator = Paginator(cursos_qs, 10)
    page = request.GET.get('page', 1)
    try:
        cursos_paginados = paginator.page(page)
    except:
        cursos_paginados = paginator.page(1)

    # ===== ESTADÍSTICAS PARA TARJETAS =====
    total_cursos = base_qs.count()
    cursos_activos_count = base_qs.filter(
        activo=True,
        fecha_inicio__lte=hoy,
        fecha_fin__gte=hoy
    ).count()
    cursos_proximos_count = base_qs.filter(
        activo=True,
        fecha_inicio__gt=hoy
    ).count()
    cursos_finalizados_count = base_qs.filter(
        activo=True,
        fecha_fin__lt=hoy
    ).count()
    cursos_inactivos_count = base_qs.filter(activo=False).count()

    # TOTAL ALUMNOS (ajusta según tu relación)
    total_alumnos = Alumno.objects.filter(
        cursos_inscritos__in=base_qs,
        activo=True
    ).distinct().count()

    # ===== DEPURACIÓN: MOSTRAR DATOS DEL PROFESOR =====
    if profesor_context:
        print("📌 DATOS DEL PROFESOR:")
        print(f"   - Nombre completo: {profesor_context.nombre_completo()}")
        print(f"   - Mail: {getattr(profesor_context, 'mail', 'NO EXISTE')}")
        print(f"   - CUIT: {getattr(profesor_context, 'cuit', 'NO EXISTE')}")
        print(f"   - Teléfono: {getattr(profesor_context, 'telefono', 'NO EXISTE')}")
        print(f"   - Foto: {profesor_context.foto.url if profesor_context.foto else 'Sin foto'}")

    # CONTEXTO
    context = {
        'titulo': titulo,
        'cursos': cursos_paginados,
        'profesor': profesor_context,
        'es_administrador': es_admin,
        'mostrar_profesor': mostrar_profesor,
        'hoy': hoy,
        'cursos_activos_count': cursos_activos_count,
        'cursos_proximos_count': cursos_proximos_count,
        'cursos_finalizados_count': cursos_finalizados_count,
        'total_cursos': total_cursos,
        'total_alumnos': total_alumnos,
        # Para compatibilidad con otros templates
        'cursos_activos': cursos_activos_count,
        'cursos_finalizados': cursos_finalizados_count,
        'cursos_inactivos': cursos_inactivos_count,
        'estado_filtro': estado,
        'busqueda_actual': busqueda,
        'tipo_acceso': getattr(request, 'tipo_acceso', 'profesor'),
    }

    print("=== FIN mis_cursos ===")
    return render(request, 'web/profesores/mis_cursos.html', context)

@login_required
@requiere_permiso_profesor
def detalle_curso_profesor(request, curso_id):
    """Vista de solo lectura - Muestra detalles del curso"""
    # LÃ³gica de solo lectura
    curso = get_object_or_404(Curso, id=curso_id)
    inscripciones = Inscripcion.objects.filter(curso=curso, activo=True)
    
    context = {
        'curso': curso,
        'inscripciones': inscripciones,
        'modo_vista': 'detalle',
        'permisos': {
            'puede_editar': False,  # En detalle no se puede editar
            'puede_gestionar': request.user.has_perm('web.change_curso'),
        }
    }
    return render(request, 'web/profesores/detalle_curso.html', context)

@login_required
@requiere_permiso_profesor
def gestionar_curso(request, curso_id):
    """Vista de gestiÃ³n - Permite acciones administrativas"""
    curso = get_object_or_404(Curso, id=curso_id)
    
    # Formularios de gestiÃ³n
    form_curso = AltaCursoForm(instance=curso) if request.user.has_perm('web.change_curso') else None
    form_alumno = AltaAlumnoForm(curso=curso)
    
    if request.method == 'POST':
        if 'actualizar_curso' in request.POST and form_curso:
            # LÃ³gica para actualizar curso
            pass
        elif 'agregar_alumno' in request.POST:
            # LÃ³gica para agregar alumno
            pass
    
    context = {
        'curso': curso,
        'form_curso': form_curso,
        'form_alumno': form_alumno,
        'modo_vista': 'gestion',
        'permisos': {
            'puede_editar': request.user.has_perm('web.change_curso'),
            'puede_eliminar': request.user.has_perm('web.delete_curso'),
        }
    }
    return render(request, 'web/profesores/gestionar_curso.html', context)

# ============================================
# ASISTENCIA (DIFERENCIADO POR ROL)
# ============================================

def debug_view_info():
    """FunciÃ³n para debug que muestra quÃ© vista se estÃ¡ ejecutando"""
    print("=" * 60)
    print(f"ðŸ” EJECUTANDO VISTA: {sys._getframe(1).f_code.co_name}")
    print(f"ðŸ“‚ MÃ“DULO: {__name__}")
    print("=" * 60)



import json
from datetime import datetime, timedelta
from django.utils import timezone
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.db import transaction
from django.contrib.auth.decorators import login_required
from .models import Curso, Inscripcion, Asistencia, Profesor, Personal, Notificacion, TipoNotificacion, HistorialCambios
from .utils import crear_notificacion_ausencia_curso, generar_fechas_clase

import unicodedata
import unicodedata

def dias_curso_a_lista_numeros(curso):
    """
    Convierte el campo `dias` del curso en lista de números (0=lunes, 6=domingo).
    Soporta plurales, mayúsculas, acentos y abreviaturas.
    """
    if not curso or not curso.dias:
        return []
    
    # Normalizar: minúsculas, sin acentos, sin espacios extras
    def normalizar(texto):
        texto = texto.lower().strip()
        texto = unicodedata.normalize('NFKD', texto).encode('ASCII', 'ignore').decode('utf-8')
        return texto

    # Separar por comas
    partes = [normalizar(p) for p in curso.dias.split(',')]
    
    # Mapeo amplio (incluye plurales y abreviaturas)
    dias_map = {
        'lunes': 0, 'lun': 0,
        'martes': 1, 'mar': 1,
        'miercoles': 2, 'mie': 2,
        'jueves': 3, 'jue': 3,
        'viernes': 4, 'vie': 4,
        'sabado': 5, 'sab': 5,
        'domingo': 6, 'dom': 6,
    }
    
    resultado = []
    for p in partes:
        # Buscar directamente
        if p in dias_map:
            resultado.append(dias_map[p])
        else:
            # Si termina en 's', quitar la 's' y probar (para plurales como 'sabados')
            if p.endswith('s'):
                p_sin_s = p[:-1]
                if p_sin_s in dias_map:
                    resultado.append(dias_map[p_sin_s])
                else:
                    print(f"⚠️ Día no reconocido (con 's'): '{p}'")
            else:
                print(f"⚠️ Día no reconocido: '{p}'")
    
    # Eliminar duplicados
    return list(set(resultado))

@login_required
def tomar_asistencia_unificada(request, curso_id):
    """
    Vista unificada para tomar asistencia - Acceso para:
    - Profesor del curso
    - Auxiliar asignado al curso  
    - Personal ADMINISTRATIVO
    - Personal COORDINADOR
    - Personal SECRETARIA
    - Superusuarios
    
    CON NOTIFICACIONES AUTOMÁTICAS:
    1. Ausencia masiva (>30% o >3 ausentes) → Notifica al auxiliar usando función de utils
    2. Ausencias consecutivas (2 faltas seguidas) → Notifica al auxiliar
    """
    print("=" * 60)
    print(f"🎯 VISTA tomar_asistencia_unificada - Usuario: {request.user.username}")
    
    # Obtener el curso
    curso = get_object_or_404(Curso, id=curso_id, activo=True, eliminado=False)
    print(f"🎯 Curso: {curso.nombre}")
    print(f"🎯 Profesor asignado: {curso.profesor}")
    print(f"🎯 Auxiliar asignado: {curso.auxiliar}")
    
    # Determinar roles del usuario
    es_profesor_del_curso = False
    es_auxiliar_del_curso = False
    es_personal_autorizado = False
    es_superusuario = request.user.is_superuser
    
    # Verificar si es profesor del curso
    try:
        profesor_usuario = Profesor.objects.get(user=request.user, activo=True, eliminado=False)
        if curso.profesor == profesor_usuario:
            es_profesor_del_curso = True
    except Profesor.DoesNotExist:
        pass
    
    # Verificación del auxiliar
    try:
        if curso.auxiliar and curso.auxiliar.user and curso.auxiliar.user.id == request.user.id:
            es_auxiliar_del_curso = True
    except Exception:
        pass
    
    # Verificar si es personal autorizado
    try:
        personal = Personal.objects.get(user=request.user, activo=True, eliminado=False)
        if curso.auxiliar and curso.auxiliar.id == personal.id:
            es_auxiliar_del_curso = True
        if personal.tipo in ['ADMINISTRATIVO', 'COORDINADOR', 'SECRETARIA']:
            es_personal_autorizado = True
    except Personal.DoesNotExist:
        pass
    
    # Verificación adicional por email/legajo
    if not es_auxiliar_del_curso and curso.auxiliar:
        if curso.auxiliar.mail and curso.auxiliar.mail == request.user.email:
            es_auxiliar_del_curso = True
        if curso.auxiliar.legajo and curso.auxiliar.legajo == request.user.username:
            es_auxiliar_del_curso = True
    
    # Verificación de permisos de acceso
    roles_autorizados = [es_profesor_del_curso, es_auxiliar_del_curso, es_personal_autorizado, es_superusuario]
    if not any(roles_autorizados):
        messages.error(request, "No tienes permiso para acceder a esta página.")
        # Redirigir según perfil
        try:
            Profesor.objects.get(user=request.user)
            return redirect('mis_cursos_profesor')
        except:
            try:
                Personal.objects.get(user=request.user)
                return redirect('dashboard_personal')
            except:
                return redirect('dashboard')
    
    # Determinar si puede editar
    puede_editar = False
    if es_profesor_del_curso or es_auxiliar_del_curso or es_superusuario:
        puede_editar = True
    elif es_personal_autorizado:
        puede_editar = request.GET.get('editar') == '1'
    
    hoy = timezone.now().date()
    
    # Obtener inscripciones
    inscripciones = Inscripcion.objects.filter(
        curso=curso,
        activo=True,
        estado__in=['INSCRIPTO', 'CURSANDO']
    ).select_related('alumno').order_by('alumno__apellido', 'alumno__nombre')
    total_alumnos = inscripciones.count()
    
    # Obtener fecha (GET o POST)
    fecha_str = request.GET.get('fecha') or request.POST.get('fecha') or hoy.isoformat()
    try:
        fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date()
    except:
        fecha = hoy

    # ==============================================
    # VALIDACIÓN DE DÍAS DE CLASE (CORREGIDA)
    # ==============================================
    dias_validos = dias_curso_a_lista_numeros(curso)  # pasamos el objeto curso
    fecha_valida = not dias_validos or (fecha.weekday() in dias_validos)

    # Variable combinada para habilitar edición en template
    puede_guardar = puede_editar and fecha_valida and fecha <= hoy

    # Mensaje informativo si no es día de clase
    if not fecha_valida:
        messages.warning(request, f"La fecha {fecha.strftime('%d/%m/%Y')} no es un día de clase ({curso.dias}). No puedes modificar la asistencia.")

    # ==============================================
    # MANEJAR POST (GUARDAR ASISTENCIA)
    # ==============================================
    if request.method == 'POST' and puede_editar:
        try:
            fecha_str = request.POST.get('fecha', hoy.isoformat())
            fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date()
            
            # Validar fecha futura
            if fecha > hoy:
                messages.error(request, 'No puedes tomar asistencia para fechas futuras')
                return redirect('tomar_asistencia_profesor', curso_id=curso.id)
            
            # Validar día de clase (usando la misma función)
            dias_validos_post = dias_curso_a_lista_numeros(curso)
            if dias_validos_post and fecha.weekday() not in dias_validos_post:
                messages.error(request, f"La fecha {fecha.strftime('%d/%m/%Y')} no es un día de clase ({curso.dias}).")
                return redirect('tomar_asistencia_profesor', curso_id=curso.id)
            
            # Variables para estadísticas
            ausentes_count = 0
            presentes_count = 0
            alumnos_ausentes_lista = []
            alumnos_con_ausencias_consecutivas = []
            
            with transaction.atomic():
                for inscripcion in inscripciones:
                    alumno_id = str(inscripcion.alumno.id)
                    presente = request.POST.get(f'presente_{alumno_id}') == 'on'
                    observaciones = request.POST.get(f'observaciones_{alumno_id}', '').strip()
                    
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
                    
                    # Verificar ausencias consecutivas (si está ausente)
                    if not presente:
                        try:
                            fechas_clase = generar_fechas_clase(
                                curso.fecha_inicio,
                                fecha,
                                curso.dias
                            )
                            if fecha in fechas_clase:
                                indice_actual = fechas_clase.index(fecha)
                                if indice_actual > 0:
                                    fecha_anterior = fechas_clase[indice_actual - 1]
                                    try:
                                        asist_ant = Asistencia.objects.get(
                                            inscripcion=inscripcion,
                                            fecha=fecha_anterior
                                        )
                                        if not asist_ant.presente:
                                            dias_diff = (fecha - fecha_anterior).days
                                            if dias_diff <= 14:
                                                alumnos_con_ausencias_consecutivas.append({
                                                    'alumno': inscripcion.alumno,
                                                    'fecha_actual': fecha,
                                                    'fecha_anterior': fecha_anterior,
                                                    'dias_diferencia': dias_diff,
                                                    'curso': curso.nombre
                                                })
                                    except Asistencia.DoesNotExist:
                                        pass
                        except Exception as e:
                            print(f"Error verificando ausencias consecutivas: {e}")
            
       # ==============================================
            # NOTIFICACIONES
            # ==============================================
            
            porcentaje_ausencia = (ausentes_count / total_alumnos * 100) if total_alumnos > 0 else 0
            print(f"📊 Estadísticas - Presentes: {presentes_count}, Ausentes: {ausentes_count}, Porcentaje: {porcentaje_ausencia:.1f}%")
            print(f"📋 Alumnos con ausencias consecutivas: {len(alumnos_con_ausencias_consecutivas)}")
            
            # A. NOTIFICACIÓN DE AUSENCIA MASIVA (usando función de utils)
            if ausentes_count >= 3 or porcentaje_ausencia > 30:
                print("🎯 LLAMANDO A FUNCIÓN crear_notificacion_ausencia_curso")
                notificacion_masiva = crear_notificacion_ausencia_curso(
                    curso=curso,
                    fecha=fecha,
                    ausentes_count=ausentes_count,
                    total_alumnos=total_alumnos,
                    usuario_origen=request.user
                )
                
                if notificacion_masiva:
                    print(f"✅ Notificación masiva creada: ID {notificacion_masiva.id}")
                    messages.info(request, 
                        f'Notificación de ausencia masiva enviada al auxiliar '
                        f'({ausentes_count} alumnos ausentes)'
                    )
                else:
                    print("❌ No se pudo crear notificación masiva")
            
            # B. NOTIFICACIONES DE AUSENCIAS CONSECUTIVAS
            if alumnos_con_ausencias_consecutivas:
                print(f"🎯 CREANDO NOTIFICACIONES DE AUSENCIAS CONSECUTIVAS")
                print(f"   Total alumnos con 2 faltas consecutivas: {len(alumnos_con_ausencias_consecutivas)}")
                
                # Mostrar lista de alumnos con ausencias consecutivas para depuración
                for i, registro in enumerate(alumnos_con_ausencias_consecutivas, 1):
                    print(f"   {i}. {registro['alumno'].nombre_completo()} - {registro['fecha_anterior']} a {registro['fecha_actual']}")
                
                try:
                    # Obtener o crear tipo de notificación para ausencias consecutivas
                    tipo_consecutiva, creado = TipoNotificacion.objects.get_or_create(
                        nombre='AUSENCIA_CONSECUTIVA',
                        defaults={
                            'icono': 'fa-user-times',
                            'color': 'warning',
                            'descripcion': 'Notificación por ausencias consecutivas de alumnos'
                        }
                    )
                    
                    notificaciones_creadas = 0
                    
                    for registro in alumnos_con_ausencias_consecutivas:
                        alumno = registro['alumno']
                        
                        print(f"   📋 Procesando notificación para: {alumno.nombre_completo()}")
                        
                        # Determinar destinatario - PRIORIDAD
                        destinatario = None
                        
                        # 1. PRIMERO: Auxiliar del curso (si existe y tiene usuario)
                        if curso.auxiliar and hasattr(curso.auxiliar, 'user') and curso.auxiliar.user:
                            destinatario = curso.auxiliar.user
                            print(f"   📞 Destinatario: AUXILIAR ({destinatario.username})")
                        
                        # 2. SEGUNDO: Profesor del curso (si existe y tiene usuario)
                        elif curso.profesor and hasattr(curso.profesor, 'user') and curso.profesor.user:
                            destinatario = curso.profesor.user
                            print(f"   📞 Destinatario: PROFESOR ({destinatario.username})")
                        
                        # 3. TERCERO: Buscar un administrativo (Claudia o cualquiera)
                        else:
                            try:
                                # Buscar usuario con "claudia" en username
                                from django.contrib.auth.models import User
                                claudia_user = User.objects.filter(
                                    username__icontains='claudia',
                                    is_active=True
                                ).first()
                                
                                if claudia_user:
                                    destinatario = claudia_user
                                    print(f"   📞 Destinatario: ADMINISTRATIVO CLAUDIA ({destinatario.username})")
                                else:
                                    # Buscar cualquier administrativo
                                    administrativo = Personal.objects.filter(
                                        tipo='ADMINISTRATIVO',
                                        activo=True,
                                        user__isnull=False
                                    ).first()
                                    
                                    if administrativo and administrativo.user:
                                        destinatario = administrativo.user
                                        print(f"   📞 Destinatario: ADMINISTRATIVO ({destinatario.username})")
                            except Exception as e:
                                print(f"   ⚠️ Error buscando destinatario administrativo: {e}")
                        
                        if not destinatario:
                            print(f"   ❌ No se encontró destinatario para {alumno.nombre_completo()}")
                            continue
                        
                        # Verificar si ya existe notificación similar reciente (últimos 3 días)
                        fecha_limite = timezone.now() - timedelta(days=3)
                        notificacion_existente = Notificacion.objects.filter(
                            usuario_destino=destinatario,
                            tipo=tipo_consecutiva,
                            titulo__icontains=alumno.nombre_completo(),
                            fecha_creacion__gte=fecha_limite,
                            mensaje__icontains=curso.nombre
                        ).exists()
                        
                        if notificacion_existente:
                            print(f"   ⏭️ Notificación ya existe para {alumno.nombre_completo()} en últimos 3 días")
                            continue
                        
                        # Crear mensaje detallado
                        mensaje_consecutiva = f"""ALUMNO: {alumno.nombre_completo()}

CURSO: {curso.nombre}
PROFESOR: {curso.profesor.nombre_completo() if curso.profesor else 'No asignado'}
AUXILIAR: {curso.auxiliar.nombre_completo() if curso.auxiliar else 'No asignado'}

FECHAS DE AUSENCIA CONSECUTIVA:
• {registro['fecha_anterior'].strftime('%d/%m/%Y')}
• {registro['fecha_actual'].strftime('%d/%m/%Y')}
({registro.get('dias_diferencia', '?')} días entre ausencias)

INFORMACIÓN DEL ALUMNO:
DNI: {alumno.dni}
Teléfono: {alumno.telefono or 'No disponible'}
Email: {alumno.email or 'No disponible'}

El alumno ha faltado a 2 clases consecutivas.
Por favor, contactar para verificar situación."""

                        # Crear notificación
                        Notificacion.objects.create(
                            titulo=f'⚠️ Ausencia consecutiva - {alumno.nombre_completo()}',
                            mensaje=mensaje_consecutiva,
                            usuario_destino=destinatario,
                            usuario_origen=request.user,
                            estado='PENDIENTE',
                            prioridad='ALTA',
                            tipo=tipo_consecutiva,
                            fecha_vencimiento=timezone.now() + timedelta(hours=72),
                            es_manual=False
                        )
                        
                        notificaciones_creadas += 1
                        print(f"   ✅ Notificación creada para {alumno.nombre_completo()}")
                    
                    if notificaciones_creadas > 0:
                        print(f"✅ {notificaciones_creadas} notificaciones de ausencia consecutiva creadas")
                        
                        # Informar al usuario
                        messages.info(request, 
                            f'Se han creado {notificaciones_creadas} notificación(es) '
                            f'por ausencias consecutivas.'
                        )
                    else:
                        print("ℹ️ No se crearon nuevas notificaciones (ya existían o no hay destinatario)")
                            
                except Exception as e:
                    print(f"❌ Error creando notificaciones por ausencia consecutiva: {e}")
                    import traceback
                    traceback.print_exc()
            
            # Mensaje de éxito general
            messages.success(request, 
                f'Asistencia del {fecha.strftime("%d/%m/%Y")} guardada correctamente. '
                f'Presentes: {presentes_count}, Ausentes: {ausentes_count}'
            )
            
            return redirect('tomar_asistencia_profesor', curso_id=curso.id)
            
        except Exception as e:
            print(f"❌ Error al guardar asistencia: {e}")
            import traceback
            traceback.print_exc()
            messages.error(request, f'Error al guardar asistencia: {str(e)}')
            return redirect('tomar_asistencia_profesor', curso_id=curso.id)
    
    # ==============================================
    # MÉTODO GET: MOSTRAR FORMULARIO
    # ==============================================
    # Obtener asistencias para la fecha
    asistencias_fecha = Asistencia.objects.filter(
        inscripcion__curso=curso,
        fecha=fecha
    ).select_related('inscripcion', 'inscripcion__alumno', 'registrado_por')
    
    asistencias_dict = {a.inscripcion.alumno.id: a for a in asistencias_fecha}
    
    # Calcular porcentaje de asistencia global
    try:
        total_asistencias = Asistencia.objects.filter(inscripcion__curso=curso).count()
        total_presentes = Asistencia.objects.filter(inscripcion__curso=curso, presente=True).count()
        porcentaje_asistencia = (total_presentes / total_asistencias * 100) if total_asistencias else 0
    except:
        porcentaje_asistencia = 0
    
    # Información del auxiliar
    auxiliar_info = None
    if curso.auxiliar:
        auxiliar_info = {
            'nombre': curso.auxiliar.nombre_completo(),
            'email': curso.auxiliar.mail,
            'telefono': curso.auxiliar.telefono,
            'tiene_usuario': bool(curso.auxiliar.user),
            'usuario': curso.auxiliar.user.username if curso.auxiliar.user else None,
        }
    
    # Pasar días válidos en JSON para JS
    dias_validos_json = json.dumps(dias_validos)
    
    context = {
        'curso': curso,
        'inscripciones': inscripciones,
        'es_profesor_del_curso': es_profesor_del_curso,
        'es_auxiliar_del_curso': es_auxiliar_del_curso,
        'es_personal_autorizado': es_personal_autorizado,
        'es_superusuario': es_superusuario,
        'puede_editar': puede_editar,
        'hoy': hoy,
        'fecha_seleccionada': fecha,
        'asistencias_dict': asistencias_dict,
        'porcentaje_asistencia': round(porcentaje_asistencia, 2),
        'total_alumnos': total_alumnos,
        'auxiliar_info': auxiliar_info,
        'puede_ver_reportes': True,
        'dias_validos_json': dias_validos_json,
        'fecha_valida': fecha_valida,
        'puede_guardar': puede_guardar,
    }
    
    print("=" * 60)
    print("="*40)
    print(f"curso.dias: '{curso.dias}'")
    print(f"dias_validos: {dias_validos}")
    print(f"fecha.weekday(): {fecha.weekday()}")
    print(f"fecha_valida: {fecha_valida}")
    print(f"puede_guardar: {puede_guardar}")
    print("="*40)
    return render(request, 'web/profesores/tomar_asistencia.html', context)


# ============================================
# NOTAS Y EXÃMENES
# ============================================

@login_required
@requiere_permiso_profesor
def gestionar_notas(request, curso_id):
    curso = get_object_or_404(Curso, id=curso_id, activo=True)
    
    if not (getattr(request, 'es_administrador', False) or curso.profesor_id == request.profesor.id):
        messages.error(request, "No tienes permiso para gestionar este curso.")
        return redirect('dashboard_profesor')
    
    inscripciones = Inscripcion.objects.filter(
        curso=curso,
        activo=True,
        estado__in=['INSCRIPTO', 'CURSANDO']
    ).select_related('alumno').order_by('alumno__apellido', 'alumno__nombre')
    
    # Tipos básicos + los que ya tienen exámenes
    tipos_basicos = [
        ('TEORICO_1', 'Teórico 1'),
        ('TEORICO_2', 'Teórico 2'),
        ('PRACTICO_1', 'Práctico 1'),
        ('PRACTICO_2', 'Práctico 2'),
    ]
    tipos_existentes = Examen.objects.filter(
        inscripcion__curso=curso
    ).values_list('tipo', flat=True).distinct()
    
    tipo_choices_dict = dict(Examen.TIPO_CHOICES)
    tipos_adicionales = [
        (t, tipo_choices_dict.get(t, t)) for t in tipos_existentes
        if t not in [bt[0] for bt in tipos_basicos]
    ]
    tipos_a_mostrar = tipos_basicos + tipos_adicionales
    
    if request.method == 'POST':
        if 'eliminar_examen' in request.POST:
            examen_id = request.POST.get('eliminar_examen')
            try:
                Examen.objects.get(id=examen_id).delete()
                messages.success(request, "Examen eliminado.")
            except Examen.DoesNotExist:
                messages.error(request, "El examen no existe.")
            return redirect('gestionar_notas', curso_id=curso.id)
        
        try:
            for inscripcion in inscripciones:
                for tipo, _ in tipos_a_mostrar:
                    nota_key = f"nota_{inscripcion.id}_{tipo}"
                    incluir_key = f"incluir_{inscripcion.id}_{tipo}"
                    fecha_key = f"fecha_{inscripcion.id}_{tipo}"
                    if nota_key in request.POST and request.POST[nota_key]:
                        try:
                            nota = float(request.POST[nota_key])
                            incluir = incluir_key in request.POST
                            fecha_str = request.POST.get(fecha_key, '')
                            if fecha_str:
                                from datetime import datetime
                                fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date()
                            else:
                                fecha = timezone.now().date()
                            Examen.objects.update_or_create(
                                inscripcion=inscripcion,
                                tipo=tipo,
                                defaults={
                                    'nota': nota,
                                    'incluir_en_promedio': incluir,
                                    'fecha': fecha,
                                }
                            )
                        except ValueError:
                            continue
            # Actualizar promedio en inscripción
            for inscripcion in inscripciones:
                promedio = Examen.objects.filter(
                    inscripcion=inscripcion, incluir_en_promedio=True
                ).aggregate(Avg('nota'))['nota__avg']
                inscripcion.nota_final = promedio
                inscripcion.save()
            messages.success(request, 'Notas guardadas.')
            return redirect('gestionar_notas', curso_id=curso.id)
        except Exception as e:
            messages.error(request, f'Error: {str(e)}')
    
    # Preparar datos para el template
    examenes = Examen.objects.filter(inscripcion__curso=curso).select_related('inscripcion')
    examenes_dict = {}
    for examen in examenes:
        key = (examen.inscripcion.id, examen.tipo)
        examenes_dict[key] = examen
    
    inscripciones_con_datos = []
    for insc in inscripciones:
        notas = {}
        for tipo, _ in tipos_a_mostrar:
            examen = examenes_dict.get((insc.id, tipo))
            notas[tipo] = {
                'nota': examen.nota if examen else '',
                'incluir': examen.incluir_en_promedio if examen else False,
                'id': examen.id if examen else None,
                'fecha': examen.fecha if examen else None,
            }
        inscripciones_con_datos.append({
            'inscripcion': insc,
            'notas': notas,
        })
    print("tipos_a_mostrar:", tipos_a_mostrar)
    if inscripciones_con_datos:
        print("Primer inscripción - notas.keys():", list(inscripciones_con_datos[0]['notas'].keys()))
    context = {
        'curso': curso,
        'inscripciones_con_datos': inscripciones_con_datos,
        'tipos_a_mostrar': tipos_a_mostrar,
    }
    return render(request, 'web/profesores/gestionar_notas.html', context)

@login_required
@requiere_permiso_profesor
def agregar_examen_personalizado(request, curso_id, alumno_id):
    curso = get_object_or_404(Curso, id=curso_id)
    alumno = get_object_or_404(Alumno, id=alumno_id)
    inscripcion = get_object_or_404(Inscripcion, curso=curso, alumno=alumno, activo=True)
    
    if request.method == 'POST':
        tipo = request.POST.get('tipo_personalizado', '').strip()
        nota = request.POST.get('nota', '').strip()
        incluir = request.POST.get('incluir', False) == 'on'
        
        if not tipo or not nota:
            messages.error(request, "Debe completar tipo y nota.")
        else:
            try:
                nota = float(nota)
                if nota < 0 or nota > 10:
                    raise ValueError("Nota fuera de rango")
                Examen.objects.create(
                    inscripcion=inscripcion,
                    tipo=tipo,
                    nota=nota,
                    incluir_en_promedio=incluir,
                    fecha=timezone.now().date()
                )
                messages.success(request, f"Examen '{tipo}' agregado correctamente.")
                return redirect('gestionar_notas', curso_id=curso.id)
            except ValueError:
                messages.error(request, "La nota debe ser un número entre 0 y 10.")
    
    return render(request, 'web/profesores/agregar_examen_personalizado.html', {
        'curso': curso,
        'alumno': alumno,
        'inscripcion': inscripcion
    })
# ============================================
# VISTAS ESPECIALES PARA ADMINISTRADORES
# ============================================

@login_required
def switch_modo_profesor(request):
    """
    Cambia entre modo 'admin' y modo 'profesor'
    Solo para administradores/coordinadores que tambiÃ©n son profesores
    """
    modo = request.GET.get('modo', 'profesor')
    
    # Verificar que es administrador
    if not getattr(request, 'es_administrador', False):
        messages.error(request, "Solo administradores pueden cambiar de modo")
        return redirect('dashboard_profesor')
    
    # Verificar que tiene perfil de profesor
    profesor = getattr(request, 'profesor', None)
    if not profesor and modo == 'profesor':
        messages.error(request, "No tienes perfil de profesor para activar este modo")
        return redirect('dashboard_admin_general')  # Redirigir al dashboard admin
    
    # Cambiar modo
    request.session['modo_profesor'] = modo
    
    if modo == 'profesor':
        messages.success(request, f"Modo profesor activado. Viendo como: {profesor.nombre_completo()}")
        return redirect('dashboard_profesor')
    else:
        messages.success(request, "Modo administrador activado")
        return redirect('dashboard_admin_general')  # Redirigir al dashboard admin
    
# ============================================
# AJAX/RÃPIDAS
# ============================================

@login_required
@requiere_permiso_profesor
@require_GET
def obtener_estadisticas_curso(request, curso_id):
    """Obtener estadÃ­sticas del curso (AJAX)"""
    try:
        from django.db.models import Avg, Count
        
        es_admin = request.es_administrador
        profesor = request.profesor
        
        # Obtener curso con permisos
        from .models import Curso
        if es_admin:
            curso = Curso.objects.get(id=curso_id, activo=True, eliminado=False)
        else:
            curso = Curso.objects.get(id=curso_id, profesor=profesor, activo=True, eliminado=False)
        
        # EstadÃ­sticas
        inscripciones = Inscripcion.objects.filter(
            curso=curso,
            activo=True,
            estado__in=['INSCRIPTO', 'CURSANDO']
        )
        
        total_alumnos = inscripciones.count()
        
        # Asistencia del mes
        hoy = timezone.now().date()
        asistencias_mes = Asistencia.objects.filter(
            inscripcion__curso=curso,
            fecha__month=hoy.month,
            fecha__year=hoy.year
        )
        total_asistencias = asistencias_mes.count()
        presentes = asistencias_mes.filter(presente=True).count()
        porcentaje_asistencia = (presentes / total_asistencias * 100) if total_asistencias > 0 else 0
        
        # Notas
        examenes = Examen.objects.filter(inscripcion__curso=curso)
        promedio_notas = examenes.aggregate(prom=Avg('nota'))['prom'] if examenes.exists() else None
        
        # Alumnos con bajo rendimiento (< 6)
        alumnos_bajo_rendimiento = 0
        for inscripcion in inscripciones:
            examenes_alumno = Examen.objects.filter(inscripcion=inscripcion)
            if examenes_alumno.exists():
                promedio = examenes_alumno.aggregate(prom=Avg('nota'))['prom']
                if promedio and promedio < 6:
                    alumnos_bajo_rendimiento += 1
        
        return JsonResponse({
            'success': True,
            'data': {
                'total_alumnos': total_alumnos,
                'porcentaje_asistencia': round(porcentaje_asistencia, 1),
                'promedio_notas': round(promedio_notas, 2) if promedio_notas else None,
                'alumnos_bajo_rendimiento': alumnos_bajo_rendimiento,
                'presentes_mes': presentes,
                'total_clases_mes': total_asistencias // total_alumnos if total_alumnos > 0 else 0,
            }
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})
    
    
# ============================================
# VISTAS PARA EXÃMENES INDIVIDUALES
# ============================================

@login_required
@requiere_permiso_profesor
def agregar_examen_individual(request, inscripcion_id):
    """
    Vista para agregar un examen individual a un alumno inscrito en un curso.
    Accesible para profesores y administradores.
    """
    # Obtener la inscripciÃ³n
    inscripcion = get_object_or_404(Inscripcion, id=inscripcion_id, activo=True)
    alumno = inscripcion.alumno
    curso = inscripcion.curso
    
    # Verificar permisos especÃ­ficos
    es_admin = request.es_administrador
    profesor = request.profesor
    
    if not es_admin and curso.profesor != profesor:
        messages.error(request, "Solo el profesor asignado puede agregar exÃ¡menes en este curso")
        return redirect('detalle_curso_profesor', curso_id=curso.id)
    
    # Obtener exÃ¡menes existentes para este alumno en el curso
    examenes_existentes = Examen.objects.filter(inscripcion=inscripcion)
    tipos_existentes = [examen.tipo for examen in examenes_existentes]
    
    # Filtrar tipos disponibles (excluir los ya existentes)
    TIPO_CHOICES_FILTRADOS = [
        choice for choice in Examen.TIPO_CHOICES 
        if choice[0] not in tipos_existentes
    ]
    
    if request.method == 'POST':
        # Crear formulario con datos POST
        form = ExamenForm(request.POST, TIPO_CHOICES=TIPO_CHOICES_FILTRADOS)
        
        if form.is_valid():
            try:
                examen = form.save(commit=False)
                examen.inscripcion = inscripcion
                
                # Verificar que no exista ya un examen del mismo tipo
                if Examen.objects.filter(inscripcion=inscripcion, tipo=examen.tipo).exists():
                    messages.error(request, f"Ya existe un examen de tipo {examen.get_tipo_display()} para este alumno")
                else:
                    examen.save()
                    
                    # Registrar en historial
                    HistorialCambios.objects.create(
                        usuario=request.user,
                        modelo_afectado='EXAMEN',
                        objeto_id=examen.id,
                        accion='CREACION',
                        detalles=f"Examen agregado: {examen.get_tipo_display()} - Nota: {examen.nota}",
                        ip_address=request.META.get('REMOTE_ADDR')
                    )
                    
                    messages.success(request, f"Examen {examen.get_tipo_display()} agregado exitosamente")
                    
                    # Redirigir segÃºn parÃ¡metro
                    redireccion = request.GET.get('redirect_to', 'detalle_alumno_curso')
                    if redireccion == 'detalle_curso':
                        return redirect('detalle_curso_profesor', curso_id=curso.id)
                    else:
                        return redirect('detalle_alumno_curso', curso_id=curso.id, alumno_id=alumno.id)
                        
            except Exception as e:
                messages.error(request, f"Error al guardar el examen: {str(e)}")
        else:
            messages.error(request, "Por favor, corrige los errores en el formulario")
    else:
        # Formulario inicial con fecha actual
        form = ExamenForm(TIPO_CHOICES=TIPO_CHOICES_FILTRADOS, initial={
            'fecha': timezone.now().date()
        })
    
    # Calcular estadÃ­sticas del alumno
    promedio_examenes = examenes_existentes.aggregate(Avg('nota'))['nota__avg']
    mejor_examen = examenes_existentes.order_by('-nota').first()
    peor_examen = examenes_existentes.order_by('nota').first()
    
    context = {
        'titulo': f'Agregar Examen - {alumno.nombre_completo()}',
        'form': form,
        'alumno': alumno,
        'curso': curso,
        'inscripcion': inscripcion,
        'es_administrador': es_admin,
        'examenes_existentes': examenes_existentes,
        'tipos_disponibles': TIPO_CHOICES_FILTRADOS,
        'promedio_actual': round(promedio_examenes, 2) if promedio_examenes else None,
        'mejor_examen': mejor_examen,
        'peor_examen': peor_examen,
        'tipo_acceso': request.tipo_acceso,
    }
    
    return render(request, 'web/profesores/agregar_examen_individual.html', context)


@login_required
@requiere_permiso_profesor
def editar_examen(request, examen_id):
    """
    Vista para editar un examen existente
    """
    examen = get_object_or_404(Examen, id=examen_id)
    inscripcion = examen.inscripcion
    alumno = inscripcion.alumno
    curso = inscripcion.curso
    
    # Verificar permisos
    es_admin = request.es_administrador
    profesor = request.profesor
    
    if not es_admin and curso.profesor != profesor:
        messages.error(request, "No tienes permiso para editar este examen")
        return redirect('detalle_curso_profesor', curso_id=curso.id)
    
    if request.method == 'POST':
        form = ExamenForm(request.POST, instance=examen)
        if form.is_valid():
            examen_original = Examen.objects.get(id=examen_id)
            nota_original = examen_original.nota
            tipo_original = examen_original.get_tipo_display()
            
            examen_editado = form.save()
            
            # Registrar en historial
            HistorialCambios.objects.create(
                usuario=request.user,
                modelo_afectado='EXAMEN',
                objeto_id=examen.id,
                accion='MODIFICACION',
                detalles=f"Examen modificado: {tipo_original} - Nota: {nota_original} â†’ {examen_editado.nota}",
                ip_address=request.META.get('REMOTE_ADDR')
            )
            
            messages.success(request, "Examen actualizado correctamente")
            
            redireccion = request.GET.get('redirect_to', 'detalle_alumno_curso')
            if redireccion == 'detalle_curso':
                return redirect('detalle_curso_profesor', curso_id=curso.id)
            else:
                return redirect('detalle_alumno_curso', curso_id=curso.id, alumno_id=alumno.id)
    else:
        form = ExamenForm(instance=examen)
    
    context = {
        'titulo': f'Editar Examen - {alumno.nombre_completo()}',
        'form': form,
        'examen': examen,
        'alumno': alumno,
        'curso': curso,
        'es_administrador': es_admin,
        'tipo_acceso': request.tipo_acceso,
    }
    
    return render(request, 'web/profesores/editar_examen.html', context)


@login_required
@requiere_permiso_profesor
@require_POST
def eliminar_examen(request, examen_id):
    """
    Eliminar un examen (solo administradores)
    """
    examen = get_object_or_404(Examen, id=examen_id)
    inscripcion = examen.inscripcion
    curso = inscripcion.curso
    
    # Solo administradores pueden eliminar
    if not request.es_administrador:
        return JsonResponse({
            'success': False,
            'error': 'Solo administradores pueden eliminar exÃ¡menes'
        })
    
    try:
        # Registrar antes de eliminar
        HistorialCambios.objects.create(
            usuario=request.user,
            modelo_afectado='EXAMEN',
            objeto_id=examen.id,
            accion='ELIMINACION',
            detalles=f"Examen eliminado: {examen.get_tipo_display()} - Nota: {examen.nota}",
            ip_address=request.META.get('REMOTE_ADDR')
        )
        
        examen.delete()
        
        return JsonResponse({
            'success': True,
            'message': 'Examen eliminado correctamente'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })
        
# web/views_profesores.py

# @login_required
# @requiere_permiso_profesor  # Este decorador ya permite acceso a ambos
# def dashboard_profesor(request, profesor_id=None):
#     """
#     Dashboard unificado que funciona para:
#     1. Profesores (ven su propio dashboard)
#     2. Administradores viendo un profesor especÃ­fico
#     3. Administradores en modo gestiÃ³n general
#     """
    
#     # Obtener informaciÃ³n del usuario actual
#     es_admin = getattr(request, 'es_administrador', False)
#     profesor_actual = getattr(request, 'profesor', None)
#     modo_admin = request.session.get('modo_profesor', 'admin')
    
#     print(f"ðŸŽ¯ DASHBOARD PROFESOR - es_admin: {es_admin}, profesor_actual: {profesor_actual}, profesor_id: {profesor_id}")
    
#     # ===== DETERMINAR MODO DE OPERACIÃ“N =====
#     profesor_a_mostrar = None
#     modo_vista = None
    
#     # CASO A: Se pasÃ³ un profesor_id explÃ­cito (admin viendo otro profesor)
#     if profesor_id:
#         if not es_admin:
#             messages.error(request, "No tienes permiso para ver el dashboard de otros profesores.")
#             return redirect('dashboard_profesor')
        
#         try:
#             profesor_a_mostrar = Profesor.objects.get(
#                 id=profesor_id,
#                 activo=True,
#                 eliminado=False
#             )
#             modo_vista = 'admin_viendo_profesor'
#             print(f"âœ… Admin viendo profesor especÃ­fico: {profesor_a_mostrar.nombre_completo()}")
#         except Profesor.DoesNotExist:
#             messages.error(request, "El profesor solicitado no existe o no estÃ¡ activo.")
#             return redirect('listar_profesores')
    
#     # CASO B: Usuario es profesor y quiere ver su dashboard
#     elif profesor_actual and modo_admin == 'profesor':
#         profesor_a_mostrar = profesor_actual
#         modo_vista = 'profesor'
#         print(f"âœ… Profesor viendo SU propio dashboard: {profesor_a_mostrar.nombre_completo()}")
    
#     # CASO C: Admin en modo gestiÃ³n (sin profesor especÃ­fico)
#     elif es_admin:
#         # Redirigir o mostrar dashboard administrativo general
#         return dashboard_admin_general(request)
    
#     # CASO D: No es admin ni tiene perfil de profesor
#     else:
#         messages.error(request, "No tienes un perfil de profesor activo.")
#         return redirect('inicio')
    
#     # ===== OBTENER DATOS PARA EL DASHBOARD =====
#     # AquÃ­ obtenemos todos los datos especÃ­ficos del profesor
#     cursos_asignados = profesor_a_mostrar.curso_set.filter(
#         activo=True, 
#         eliminado=False
#     ).select_related('modalidad').prefetch_related('inscripcion_set')
    
#     # Calcular estadÃ­sticas
#     total_cursos = cursos_asignados.count()
    
#     # Total de alumnos en todos los cursos del profesor
#     total_alumnos = 0
#     for curso in cursos_asignados:
#         total_alumnos += curso.inscripcion_set.filter(
#             activo=True, 
#             estado__in=['INSCRIPTO', 'CURSANDO']
#         ).count()
    
#     # PrÃ³ximas clases (simplificado: cursos que empiezan hoy o en el futuro)
#     hoy = timezone.now().date()
#     proximas_clases = cursos_asignados.filter(
#         fecha_inicio__gte=hoy
#     ).order_by('fecha_inicio')[:5]
    
#     # Obtener asistencias pendientes (si tienes modelo Asistencia)
#     asistencias_pendientes = 0
#     try:
#         from .models import Asistencia
#         for curso in cursos_asignados:
#             asistencias_pendientes += Asistencia.objects.filter(
#                 curso=curso,
#                 fecha=hoy,
#                 tomada=False
#             ).count()
#     except:
#         pass
    
#     # ===== PREPARAR CONTEXTO =====
#     context = {
#         'profesor': profesor_a_mostrar,
#         'cursos_asignados': cursos_asignados,
#         'total_cursos': total_cursos,
#         'total_alumnos': total_alumnos,
#         'proximas_clases': proximas_clases,
#         'asistencias_pendientes': asistencias_pendientes,
        
#         # Variables de control
#         'es_administrador': es_admin,
#         'es_profesor': not es_admin,
#         'modo_vista': modo_vista,
#         'es_mi_dashboard': (profesor_actual and 
#                           profesor_actual.id == profesor_a_mostrar.id),
        
#         # Para el template especÃ­fico
#         'tiene_foto': profesor_a_mostrar.foto and os.path.exists(profesor_a_mostrar.foto.path),
#     }
    
#     return render(request, 'web/profesores/dashboard.html', context)



@login_required
def dashboard_admin_general(request):
    """Dashboard administrativo general - VersiÃ³n simplificada"""
    
    # Verificar que es administrador
    if not getattr(request, 'es_administrador', False):
        messages.error(request, "No tienes permisos administrativos")
        return redirect('dashboard_profesor')
    
    try:
        # EstadÃ­sticas generales
        total_cursos = Curso.objects.filter(activo=True, eliminado=False).count()
        total_profesores = Profesor.objects.filter(activo=True, eliminado=False).count()
        total_alumnos = Alumno.objects.filter(activo=True, eliminado=False).count()
        
        # Cursos recientes
        cursos_recientes = Curso.objects.filter(
            activo=True,
            eliminado=False
        ).order_by('-fecha_creacion')[:5]
        
        # Profesores recientes
        profesores_recientes = Profesor.objects.filter(
            activo=True,
            eliminado=False
        ).order_by('-fecha_creacion')[:5]
        
        # Notificaciones pendientes - VERSIÃ“N SIMPLIFICADA
        notificaciones_pendientes = 0
        try:
            # Intenta con el campo correcto
            notificaciones_pendientes = Notificacion.objects.filter(
                usuario_destino=request.user,
                eliminada=False
            ).filter(fecha_leida__isnull=True).count()
        except Exception as e:
            # Si falla, muestra 0 pero registra el error
            print(f"âš ï¸ Error al contar notificaciones: {e}")
            notificaciones_pendientes = 0
        
        context = {
            'titulo': 'Dashboard Administrativo',
            'es_administrador': True,
            'modo_vista': 'admin_general',
            
            # EstadÃ­sticas
            'total_cursos': total_cursos,
            'total_profesores': total_profesores,
            'total_alumnos': total_alumnos,
            'notificaciones_pendientes': notificaciones_pendientes,
            
            # Listas para acciones rÃ¡pidas
            'profesores_recientes': profesores_recientes,
            'cursos_recientes': cursos_recientes,
        }
        
        return render(request, 'web/profesores/dashboard_admin.html', context)
        
    except Exception as e:
        messages.error(request, f"Error al cargar el dashboard: {str(e)}")
        return redirect('listar_profesores')

# ============================================
# VISTAS CON PARÃMETROS PARA ADMINISTRADORES
# ============================================

@login_required
@requiere_permiso_profesor
def perfil_profesor_detalle(request, profesor_id):
    """Perfil de profesor especÃ­fico (para administradores)"""
    return perfil_profesor(request, profesor_id)

@login_required
@requiere_permiso_profesor
def mis_cursos_detalle(request, profesor_id):
    """Cursos de un profesor específico (para administradores)"""

    print("=== INICIO mis_cursos_detalle ===")
    print(f"profesor_id recibido: {profesor_id}")

    profesor = get_object_or_404(Profesor, id=profesor_id, activo=True, eliminado=False)
    print(f"👤 Profesor: {profesor.nombre_completo()}")

    # Verificar permisos: solo admin puede ver otros profesores
    es_admin = getattr(request, 'es_administrador', False)
    print(f"🔍 es_administrador: {es_admin}")
    if not es_admin:
        # Si no es admin, debe ser el propio profesor
        if hasattr(request, 'profesor') and request.profesor.id != profesor.id:
            messages.error(request, "No tienes permiso para ver los cursos de otros profesores")
            return redirect('mis_cursos_profesor')

    # Obtener cursos del profesor (activos y no eliminados)
    cursos = profesor.cursos_asignados.filter(activo=True, eliminado=False).order_by('-fecha_inicio')
    print(f"📚 Cursos encontrados: {cursos.count()}")

    hoy = timezone.now().date()
    print(f"📅 Fecha actual: {hoy}")

    # Estadísticas detalladas
    total_cursos = cursos.count()
    cursos_activos = cursos.filter(
        fecha_inicio__lte=hoy,
        fecha_fin__gte=hoy
    ).count()
    cursos_finalizados = cursos.filter(
        fecha_fin__lt=hoy
    ).count()
    cursos_proximos = cursos.filter(
        fecha_inicio__gt=hoy
    ).count()

    # Total alumnos - misma lógica que en mis_cursos
    # Opción 1: ManyToManyField 'cursos_inscritos'
    total_alumnos = Alumno.objects.filter(
        cursos_inscritos__in=cursos,
        activo=True
    ).distinct().count()
    # Opción 2: modelo intermedio CursoAlumno
    # total_alumnos = Alumno.objects.filter(cursoalumno__curso__in=cursos, activo=True).distinct().count()
    # Opción 3: suma de campo numérico
    # total_alumnos = cursos.aggregate(total=Sum('alumnos'))['total'] or 0

    print(f"📊 Estadísticas: activos={cursos_activos}, próximos={cursos_proximos}, "
          f"finalizados={cursos_finalizados}, alumnos={total_alumnos}")

    context = {
        'titulo': f'Cursos de {profesor.nombre_completo()}',
        'cursos': cursos,  # Puedes paginar si lo deseas
        'profesor': profesor,
        'es_administrador': True,
        'mostrar_profesor': False,
        'hoy': hoy,
        'total_cursos': total_cursos,
        'cursos_activos_count': cursos_activos,
        'cursos_proximos_count': cursos_proximos,
        'cursos_finalizados_count': cursos_finalizados,
        'total_alumnos': total_alumnos,
        'es_otro_profesor': True,
        'tipo_acceso': getattr(request, 'tipo_acceso', 'profesor'),
    }

    print("=== FIN mis_cursos_detalle ===")
    return render(request, 'web/profesores/mis_cursos.html', context)



@login_required
@requiere_permiso_profesor
def dashboard_profesor_detalle(request, profesor_id):
    """Dashboard de un profesor específico (SOLO para administradores, coordinadores y superusuarios)"""
    
    # 1. Verificar que NO sea profesor (profesores solo ven su propio dashboard)
    if hasattr(request, 'es_profesor') and request.es_profesor:
        messages.error(request, 
            "Los profesores solo pueden ver su propio dashboard. "
            "Ve a tu panel de control personal."
        )
        return redirect('dashboard_profesor')
    
    # 2. Verificar que sea administrador/coordinador/superusuario
    if not hasattr(request, 'es_administrador') or not request.es_administrador:
        messages.error(request, "No tienes permisos para ver dashboards de otros profesores")
        
        # Redirigir según el tipo de usuario
        if hasattr(request, 'personal'):
            if request.personal.tipo == 'SECRETARIA':
                return redirect('dashboard_personal')
            else:
                return redirect('sin_permiso_personal')
        else:
            return redirect('dashboard')
    
    # 3. Obtener el profesor
    profesor = get_object_or_404(Profesor,
        id=profesor_id,
        activo=True,
        eliminado=False
    )
    
    # 4. Datos para el dashboard
    # Intentar obtener cursos usando diferentes relaciones
    try:
        # Relación más común en Django
        cursos_asignados = Curso.objects.filter(
            profesor=profesor,
            activo=True,
            eliminado=False
        )
    except:
        cursos_asignados = Curso.objects.none()
    
    total_cursos = cursos_asignados.count()
    hoy = timezone.now().date()
    
    # Cursos próximos (próximos 7 días)
    fecha_limite = hoy + timezone.timedelta(days=7)
    cursos_proximos = cursos_asignados.filter(
        fecha_inicio__gte=hoy,
        fecha_inicio__lte=fecha_limite
    ).order_by('fecha_inicio')[:5]
    
    context = {
        'titulo': f'Dashboard de {profesor.nombre_completo()}',
        'profesor': profesor,
        'cursos_asignados': cursos_asignados,
        'total_cursos': total_cursos,
        'cursos_proximos': cursos_proximos,
        'es_administrador': True,
        'es_profesor': False,
        'es_otro_profesor': True,
        'hoy': hoy,
        'tipo_acceso': request.tipo_acceso if hasattr(request, 'tipo_acceso') else None,
        'modo_vista': 'admin_viendo_profesor',
    }
    
    # 5. Usar plantilla CORRECTA (no dashboard/base_personal.html)
    # Verificar si existe la plantilla especial para admin, sino usar la normal
    try:
        # Intenta cargar plantilla específica para admin viendo profesor
        return render(request, 'web/profesores/dashboard_admin_view.html', context)
    except TemplateDoesNotExist:
        # Si no existe, usa la plantilla normal
        return render(request, 'web/profesores/dashboard.html', context)
    
    
# ============================================
# VISTAS ADMINISTRATIVAS
# ============================================


@login_required
def dashboard_admin_general(request):
    """Dashboard administrativo general - VERSIÃ“N CORREGIDA"""
    
    # Verificar que es administrador
    if not getattr(request, 'es_administrador', False):
        messages.error(request, "No tienes permisos administrativos")
        return redirect('dashboard_profesor')
    
    try:
        # Importar los modelos necesarios
        from .models import Curso, Profesor, Alumno, Notificacion
        
        # EstadÃ­sticas generales
        total_cursos = Curso.objects.filter(activo=True, eliminado=False).count()
        total_profesores = Profesor.objects.filter(activo=True, eliminado=False).count()
        total_alumnos = Alumno.objects.filter(activo=True, eliminado=False).count()
        
        # Cursos recientes
        cursos_recientes = Curso.objects.filter(
            activo=True,
            eliminado=False
        ).order_by('-fecha_creacion')[:5]
        
        # Profesores recientes
        profesores_recientes = Profesor.objects.filter(
            activo=True,
            eliminado=False
        ).order_by('-fecha_creacion')[:5]
        
        # Notificaciones pendientes - SOLUCIÃ“N DEFINITIVA
        # Usa solo campos que SÃ existen segÃºn el error
        notificaciones_pendientes = Notificacion.objects.filter(
            usuario_destino=request.user,
            eliminada=False
        ).filter(
            fecha_leida__isnull=True  # Notificaciones no leÃ­das
        ).count()
        
        context = {
            'titulo': 'Dashboard Administrativo',
            'es_administrador': True,
            'modo_vista': 'admin_general',
            
            # EstadÃ­sticas
            'total_cursos': total_cursos,
            'total_profesores': total_profesores,
            'total_alumnos': total_alumnos,
            'notificaciones_pendientes': notificaciones_pendientes,
            
            # Listas para acciones rÃ¡pidas
            'profesores_recientes': profesores_recientes,
            'cursos_recientes': cursos_recientes,
            
            # Datos para grÃ¡ficos
            'tipo_acceso': request.tipo_acceso,
        }
        
        return render(request, 'web/profesores/dashboard_admin.html', context)
        
    except Exception as e:
        # Manejo de errores
        print(f"âŒ ERROR en dashboard_admin_general: {str(e)}")
        messages.error(request, f"Error al cargar el dashboard: {str(e)}")
        return redirect('listar_profesores')
    
    
    
    
    
    # Agrega esto al final de views_profesores.py

from django.http import JsonResponse
from django.shortcuts import render
from django.contrib.auth.decorators import login_required

@login_required
def test_permisos(request):
    """Vista temporal para debug de permisos"""
    user = request.user
    
    data = {
        'username': user.username,
        'is_authenticated': user.is_authenticated,
        'is_superuser': user.is_superuser,
        'groups': [g.name for g in user.groups.all()],
        'permissions': list(user.get_all_permissions()),
    }
    
    # Verificar si tiene perfil de profesor
    try:
        profesor = Profesor.objects.get(user=user)
        data['profesor'] = {
            'nombre': profesor.nombre_completo(),
            'activo': profesor.activo,
            'eliminado': profesor.eliminado,
        }
    except Profesor.DoesNotExist:
        data['profesor'] = None
    
    # Verificar si tiene perfil de personal
    try:
        personal = Personal.objects.get(user=user)
        data['personal'] = {
            'tipo': personal.tipo,
            'activo': personal.activo,
            'eliminado': personal.eliminado,
        }
    except Personal.DoesNotExist:
        data['personal'] = None
    
    # Retornar JSON en lugar de template (mÃ¡s simple)
    return JsonResponse(data)

# En views_profesores.py - VERSIÃ“N CORREGIDA

@login_required
def reporte_asistencia_curso(request, curso_id):
    """
    Reporte completo de asistencia para un curso
    - Permitir a profesores ver reportes de SUS cursos
    - Permitir a administradores ver reportes de TODOS los cursos
    """
    print("=" * 60)
    print(f"ðŸ“Š EJECUTANDO reporte_asistencia_curso - Curso ID: {curso_id}")
    print(f"ðŸ“Š Usuario: {request.user.username}")
    
    # Obtener el curso
    curso = get_object_or_404(Curso, id=curso_id, activo=True, eliminado=False)
    print(f"ðŸ“Š Curso: {curso.nombre}")
    print(f"ðŸ“Š Profesor asignado: {curso.profesor}")
    
    # Determinar permisos
    es_profesor_del_curso = False
    es_administrador = False
    
    # Verificar si es profesor del curso
    try:
        profesor = Profesor.objects.get(user=request.user, activo=True, eliminado=False)
        print(f"ðŸ“Š Profesor usuario: {profesor}")
        
        if curso.profesor == profesor:
            es_profesor_del_curso = True
            print("âœ… ES EL PROFESOR ASIGNADO - PERMITIR ACCESO")
        else:
            print("âš ï¸ NO ES EL PROFESOR ASIGNADO")
    except Profesor.DoesNotExist:
        print("âš ï¸ Usuario no tiene perfil de profesor")
    
    # Verificar si es administrador/coordinador
    if not es_profesor_del_curso:
        if request.user.is_superuser:
            es_administrador = True
            print("âœ… Es superusuario - PERMITIR ACCESO")
        else:
            try:
                personal = Personal.objects.get(user=request.user, activo=True, eliminado=False)
                if personal.tipo in ['ADMINISTRATIVO', 'COORDINADOR']:
                    es_administrador = True
                    print(f"âœ… Es {personal.tipo} - PERMITIR ACCESO")
            except Personal.DoesNotExist:
                pass
    
    # Verificar permisos
    if not (es_profesor_del_curso or es_administrador):
        print("âŒ NO TIENE PERMISOS - REDIRIGIR")
        messages.error(request, 
            "No tienes permiso para ver este reporte. "
            "Solo el profesor asignado o administradores pueden acceder."
        )
        # Redirigir a la vista de tomar asistencia (que ya verifica permisos)
        return redirect('tomar_asistencia', curso_id=curso_id)
    
    print("âœ… TIENE PERMISOS - GENERANDO REPORTE")
    
    # Obtener inscripciones activas y con estado válido
    inscripciones = Inscripcion.objects.filter(
        curso=curso,
        activo=True,
        estado__in=['INSCRIPTO', 'CURSANDO']
        
    ).select_related('alumno').order_by(
        'alumno__apellido', 'alumno__nombre'
    )
    print("estado es: ", inscripciones.estado_in)
    
    # Obtener todas las fechas de asistencia del curso (ordenadas)
    fechas_asistencia = Asistencia.objects.filter(
        inscripcion__curso=curso
    ).values_list('fecha', flat=True).distinct().order_by('fecha')

    # Construir estructuras de datos para la plantilla
    alumnos_stats = {}                # {inscripcion_id: stats}
    asistencias_dict = {}             # {inscripcion_id: {fecha: asistencia}}
    total_presentes_curso = 0
    total_registros_curso = 0

    for inscripcion in inscripciones:
        # Obtener asistencias de esta inscripción
        asistencias_qs = Asistencia.objects.filter(inscripcion=inscripcion).order_by('fecha')
        total_clases = asistencias_qs.count()
        presentes = asistencias_qs.filter(presente=True).count()
        ausentes = total_clases - presentes
        porcentaje = (presentes / total_clases * 100) if total_clases > 0 else 0

        # Guardar estadísticas del alumno
        alumnos_stats[inscripcion.id] = {
            'alumno': inscripcion.alumno,
            'total_clases': total_clases,
            'presentes': presentes,
            'ausentes': ausentes,
            'porcentaje_asistencia': round(porcentaje, 2),
        }

        # Diccionario de asistencias por fecha para este alumno
        asistencias_por_fecha = {}
        for a in asistencias_qs:
            asistencias_por_fecha[a.fecha] = a
        asistencias_dict[inscripcion.id] = asistencias_por_fecha

        # Acumuladores para estadísticas generales
        total_registros_curso += total_clases
        total_presentes_curso += presentes

    # Estadísticas generales
    total_alumnos = len(inscripciones)
    porcentaje_curso = (total_presentes_curso / total_registros_curso * 100) if total_registros_curso > 0 else 0

    # Convertir fechas a lista
    fechas_unicas = list(fechas_asistencia)

    context = {
        'curso': curso,
        'alumnos_stats': alumnos_stats,           # Para tabla de estadísticas y detalle
        'asistencias': asistencias_dict,          # Para acceso rápido en detalle
        'fechas_unicas': fechas_unicas,           # Lista de fechas para columnas
        'total_alumnos': total_alumnos,
        'total_registros': total_registros_curso,
        'asistencias_presentes': total_presentes_curso,
        'asistencias_ausentes': total_registros_curso - total_presentes_curso,
        'porcentaje_asistencia': round(porcentaje_curso, 2),
        'fecha_inicio': request.GET.get('fecha_inicio'),
        'fecha_fin': request.GET.get('fecha_fin'),
        'hoy': timezone.now(),
        # ... resto de variables de permisos si las necesitas ...
    }

    return render(request, 'web/profesores/reporte_asistencias.html', context)


@login_required
def exportar_asistencia(request, curso_id):
    """
    Exportar asistencia a Excel
    """
    print("=" * 60)
    print(f"ðŸ“ˆ EJECUTANDO exportar_asistencia - Curso ID: {curso_id}")
    print(f"ðŸ“ˆ Usuario: {request.user.username}")
    
    # Obtener el curso
    curso = get_object_or_404(Curso, id=curso_id, activo=True, eliminado=False)
    
    # Determinar permisos (misma logica que reporte_asistencia_curso)
    es_profesor_del_curso = False
    es_administrador = False
    
    # Verificar si es profesor del curso
    try:
        profesor = Profesor.objects.get(user=request.user, activo=True, eliminado=False)
        if curso.profesor == profesor:
            es_profesor_del_curso = True
            print("âœ… ES EL PROFESOR ASIGNADO - PERMITIR EXPORTACIÃ“N")
    except Profesor.DoesNotExist:
        pass
    
    # Verificar si es administrador/coordinador
    if not es_profesor_del_curso:
        if request.user.is_superuser:
            es_administrador = True
            print("âœ… Es superusuario - PERMITIR EXPORTACIÃ“N")
        else:
            try:
                personal = Personal.objects.get(user=request.user, activo=True, eliminado=False)
                if personal.tipo in ['ADMINISTRATIVO', 'COORDINADOR']:
                    es_administrador = True
                    print(f"âœ… Es {personal.tipo} - PERMITIR EXPORTACIÃ“N")
            except Personal.DoesNotExist:
                pass
    
    # Verificar permisos
    if not (es_profesor_del_curso or es_administrador):
        print("âŒ NO TIENE PERMISOS - REDIRIGIR")
        messages.error(request, 
            "No tienes permiso para exportar este reporte. "
            "Solo el profesor asignado o administradores pueden acceder."
        )
        return redirect('tomar_asistencia', curso_id=curso_id)
    """
    Exportar asistencia a Excel
    """
    curso = get_object_or_404(Curso, id=curso_id, activo=True, eliminado=False)
    
    # Verificar permisos
    if not (request.user.is_superuser or 
            curso.profesor == request.user.profesor if hasattr(request.user, 'profesor') else False):
        messages.error(request, "No tienes permiso para exportar este reporte")
        return redirect('mis_cursos')
    
    # Obtener datos
    inscripciones = Inscripcion.objects.filter(
        curso=curso,
        activo=True
    ).select_related('alumno')
    
    fechas_asistencia = Asistencia.objects.filter(
        inscripcion__curso=curso
    ).values_list('fecha', flat=True).distinct().order_by('fecha')
    
    # Crear respuesta Excel
    response = HttpResponse(content_type='application/ms-excel')
    response['Content-Disposition'] = f'attachment; filename="asistencia_{curso.nombre}_{timezone.now().date()}.xls"'
    
    wb = xlwt.Workbook(encoding='utf-8')
    ws = wb.add_sheet('Asistencia')
    
    # Estilos
    style_header = xlwt.easyxf('font: bold on; align: horiz center')
    style_date = xlwt.easyxf(num_format_str='DD/MM/YYYY')
    style_percent = xlwt.easyxf(num_format_str='0.00%')
    
    # Escribir encabezados
    headers = ['ID', 'Apellido', 'Nombre', 'DNI', 'Email', 'TelÃ©fono']
    for fecha in fechas_asistencia:
        headers.append(fecha.strftime('%d/%m'))
    headers.extend(['Total Clases', 'Presentes', 'Ausentes', '% Asistencia'])
    
    for col, header in enumerate(headers):
        ws.write(0, col, header, style_header)
    
    # Escribir datos de alumnos
    for row, inscripcion in enumerate(inscripciones, 1):
        alumno = inscripcion.alumno
        ws.write(row, 0, alumno.id)
        ws.write(row, 1, alumno.apellido)
        ws.write(row, 2, alumno.nombre)
        ws.write(row, 3, alumno.dni or '')
        ws.write(row, 4, alumno.email or '')
        ws.write(row, 5, alumno.telefono or '')
        
        # Asistencias por fecha
        total_presentes = 0
        for col, fecha in enumerate(fechas_asistencia, 6):
            try:
                asistencia = Asistencia.objects.get(
                    inscripcion=inscripcion,
                    fecha=fecha
                )
                ws.write(row, col, 'P' if asistencia.presente else 'A')
                if asistencia.presente:
                    total_presentes += 1
            except Asistencia.DoesNotExist:
                ws.write(row, col, '-')
        
        # EstadÃ­sticas
        total_clases = len(fechas_asistencia)
        total_ausentes = total_clases - total_presentes
        porcentaje = total_presentes / total_clases if total_clases > 0 else 0
        
        ws.write(row, 6 + len(fechas_asistencia), total_clases)
        ws.write(row, 7 + len(fechas_asistencia), total_presentes)
        ws.write(row, 8 + len(fechas_asistencia), total_ausentes)
        ws.write(row, 9 + len(fechas_asistencia), porcentaje, style_percent)
    
    # Ajustar anchos de columna
    for i in range(len(headers)):
        ws.col(i).width = 256 * 15  # 15 caracteres
    
    wb.save(response)
    return response

@login_required
def exportar_asistencia_csv(request, curso_id):
    """
    Exportar asistencia a CSV (alternativa mÃ¡s simple)
    """
    curso = get_object_or_404(Curso, id=curso_id, activo=True, eliminado=False)
    
    # Verificar permisos
    if not (request.user.is_superuser or 
            curso.profesor == request.user.profesor if hasattr(request.user, 'profesor') else False):
        messages.error(request, "No tienes permiso para exportar este reporte")
        return redirect('mis_cursos')
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="asistencia_{curso.nombre}_{timezone.now().date()}.csv"'
    
    writer = csv.writer(response)
    
    # Encabezados
    writer.writerow(['Reporte de Asistencia', curso.nombre, f'Generado: {timezone.now().strftime("%d/%m/%Y %H:%M")}'])
    writer.writerow([])
    
    # Datos del curso
    writer.writerow(['Curso:', curso.nombre])
    writer.writerow(['Profesor:', curso.profesor.nombre_completo() if curso.profesor else 'No asignado'])
    writer.writerow(['Fecha inicio:', curso.fecha_inicio.strftime('%d/%m/%Y')])
    writer.writerow(['Fecha fin:', curso.fecha_fin.strftime('%d/%m/%Y')])
    writer.writerow([])
    
    # Encabezados de tabla
    writer.writerow(['ID', 'Apellido', 'Nombre', 'DNI', 'Total Clases', 'Presentes', 'Ausentes', '% Asistencia'])
    
    # Datos de alumnos
    inscripciones = Inscripcion.objects.filter(
        curso=curso,
        activo=True
    ).select_related('alumno').order_by('alumno__apellido', 'alumno__nombre')
    
    for inscripcion in inscripciones:
        alumno = inscripcion.alumno
        asistencias = Asistencia.objects.filter(inscripcion=inscripcion)
        total_clases = asistencias.count()
        total_presentes = asistencias.filter(presente=True).count()
        total_ausentes = total_clases - total_presentes
        porcentaje = (total_presentes / total_clases * 100) if total_clases > 0 else 0
        
        writer.writerow([
            alumno.id,
            alumno.apellido,
            alumno.nombre,
            alumno.dni or '',
            total_clases,
            total_presentes,
            total_ausentes,
            f'{porcentaje:.2f}%'
        ])
    
    return response

# En utils.py o en tu views_profesores.py
def verificar_ausencias_consecutivas_alumno(inscripcion, fecha_actual):
    """
    Verifica si un alumno tiene 2 ausencias consecutivas.
    Retorna True si es asÃ­.
    """
    try:
        # Obtener las Ãºltimas 4 asistencias para verificar patrones
        asistencias_recientes = Asistencia.objects.filter(
            inscripcion=inscripcion,
            fecha__lte=fecha_actual  # Solo fechas anteriores o iguales a hoy
        ).order_by('-fecha')[:4]  # Ãšltimas 4 clases
        
        if len(asistencias_recientes) < 2:
            return False
        
        # Verificar si las Ãºltimas 2 son ausencias
        ultimas_dos = list(asistencias_recientes[:2])
        
        # Ambas deben ser ausencias (presente=False)
        if not ultimas_dos[0].presente and not ultimas_dos[1].presente:
            # Verificar que sean clases consecutivas (misma semana o sin clases intermedias)
            # Esto depende de cÃ³mo tengas organizadas las clases
            return True
        
        return False
        
    except Exception as e:
        print(f"âš ï¸ Error al verificar ausencias consecutivas: {e}")
        return False
