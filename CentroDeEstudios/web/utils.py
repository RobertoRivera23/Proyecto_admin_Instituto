from django.db import models

from .models import BackupAlumno
from .models import BackupGenerico
from django.apps import apps
import json
from django.core.serializers import serialize
from django.contrib.auth.models import User
from django.contrib.auth.decorators import user_passes_test
from functools import wraps
from django.http import HttpResponseForbidden
from django.utils import timezone
from datetime import timedelta
from django.db.models import Q

def crear_backup_alumno(alumno, motivo, usuario=None):
    """Crea un backup de los datos del alumno"""
    datos_backup = {
        'nombre': alumno.nombre,
        'apellido': alumno.apellido,
        'dni': alumno.dni,
        'fecha_nacimiento': alumno.fecha_nacimiento.isoformat() if alumno.fecha_nacimiento else None,
        'sexo': alumno.sexo,
        'direccion': alumno.direccion,
        'telefono': alumno.telefono,
        'telefono_contacto': alumno.telefono_contacto,
        'mail': alumno.mail,
        'edad': alumno.edad,
        'curso_id': alumno.cursoAlumno.id if alumno.cursoAlumno else None,
        'activo': alumno.activo,
        'foto': alumno.foto.name if alumno.foto else None,
    }
    
    backup = BackupAlumno.objects.create(
        alumno_original=alumno,
        datos_backup=datos_backup,
        motivo=motivo,
        usuario_backup=usuario
    )
    
    return backup


def crear_backup_generico(instancia, motivo="Backup automático", usuario=None):
    """
    Función genérica para crear backups de cualquier modelo
    """
    try:
        # Serializar la instancia
        datos = serialize('json', [instancia])
        datos_dict = json.loads(datos)[0]
        
        # Crear registro de backup (puedes guardarlo en un modelo de Backup si lo creas)
        backup_info = {
            'modelo': f"{instancia._meta.app_label}.{instancia._meta.model_name}",
            'id_original': instancia.pk,
            'datos': datos_dict,
            'motivo': motivo,
            'usuario': usuario.username if usuario else 'sistema',
            'fecha_backup': timezone.now().isoformat()
        }
        
        # Aquí puedes guardar el backup en un archivo, base de datos, etc.
        # Por ahora solo lo imprimimos
        print(f"📦 Backup creado: {backup_info}")
        
        return backup_info
        
    except Exception as e:
        print(f"❌ Error al crear backup: {e}")
        return None

######################## GENERICOS REUTILIZABLES

def crear_backup_alumno(alumno, motivo, usuario=None):
    return _crear_backup_instancia(alumno, motivo, usuario, 'Alumno')

def crear_backup_profesor(profesor, motivo, usuario=None):
    return _crear_backup_instancia(profesor, motivo, usuario, 'Profesor')

def crear_backup_curso(curso, motivo, usuario=None):
    return _crear_backup_instancia(curso, motivo, usuario, 'Curso')

def _crear_backup_instancia(instancia, motivo, usuario, tipo_modelo):
    """
    Función interna para crear backups de cualquier instancia
    """
    
    
    datos_backup = {}
    
    # Recopilar datos básicos
    campos_base = ['nombre', 'apellido', 'dni', 'direccion', 'telefono', 'mail', 'activo']
    
    for field_name in campos_base:
        if hasattr(instancia, field_name):
            field_value = getattr(instancia, field_name)
            if hasattr(field_value, 'isoformat'):  # Fechas
                datos_backup[field_name] = field_value.isoformat()
            else:
                datos_backup[field_name] = field_value
    
    # Campos específicos por modelo
    if tipo_modelo == 'Alumno':
        datos_backup.update({
            'edad': instancia.edad,
            'curso_id': instancia.cursoAlumno.id if instancia.cursoAlumno else None,
        })
    elif tipo_modelo == 'Profesor':
        # Agregar campos específicos de profesor si los tienes
        if hasattr(instancia, 'especialidad'):
            datos_backup['especialidad'] = instancia.especialidad
    elif tipo_modelo == 'Curso':
        datos_backup.update({
            'nombre_curso': instancia.nombre,
            'descripcion': getattr(instancia, 'descripcion', ''),
            'precio': getattr(instancia, 'precio', None),
        })
    
    # Agregar representación string
    datos_backup['_representacion'] = str(instancia)
    
    backup = BackupGenerico.objects.create(
        modelo=tipo_modelo,
        objeto_id=instancia.id,
        datos_backup=datos_backup,
        motivo=motivo,
        usuario_backup=usuario
    )
    
    return backup


################################# CREACION BACKUPS GENERICOS REUTILIZABLES

def crear_backup_generico(instancia, motivo, usuario=None):
    """
    Crea un backup genérico para CUALQUIER modelo de Django
    
    Args:
        instancia: La instancia del modelo a respaldar (ej: un objeto Alumno)
        motivo (str): Razón del backup (ej: "Eliminación", "Modificación")
        usuario: Usuario que realiza el backup (opcional)
    
    Returns:
        BackupGenerico: El objeto de backup creado
    """
    
    # 1. Obtener información del modelo
    nombre_modelo = instancia._meta.model_name  # Ej: 'alumno', 'profesor'
    nombre_app = instancia._meta.app_label      # Ej: 'web'
    id_objeto = instancia.id
    
    print(f"Creando backup para: {nombre_modelo} (ID: {id_objeto})")
    
    # 2. Recopilar TODOS los datos del objeto
    datos_backup = {}
    
    # Recorrer todos los campos del modelo
    for field in instancia._meta.fields:
        nombre_campo = field.name
        valor_campo = getattr(instancia, nombre_campo)
        
        print(f"Procesando campo: {nombre_campo} = {valor_campo}")
        
        # 3. Convertir tipos especiales a formato serializable (JSON)
        if valor_campo is None:
            # Si es None, lo guardamos como None
            datos_backup[nombre_campo] = None
            
        elif isinstance(valor_campo, (str, int, float, bool)):
            # Tipos básicos que JSON puede manejar directamente
            datos_backup[nombre_campo] = valor_campo
            
        elif hasattr(valor_campo, 'isoformat'):
            # Para campos de fecha/hora (DateField, DateTimeField)
            datos_backup[nombre_campo] = valor_campo.isoformat()
            
        elif hasattr(valor_campo, 'id'):
            # Para relaciones ForeignKey - guardamos solo el ID
            datos_backup[nombre_campo] = valor_campo.id
            datos_backup[f'{nombre_campo}_str'] = str(valor_campo)  # Y su representación string
            
        else:
            # Para cualquier otro tipo, convertimos a string
            datos_backup[nombre_campo] = str(valor_campo)
    
    # 4. Agregar información adicional útil
    datos_backup['_metadata'] = {
        'modelo_completo': f"{nombre_app}.{nombre_modelo}",
        'representacion_string': str(instancia),
        'tiene_foto': hasattr(instancia, 'foto') and bool(instancia.foto),
    }
    
    print(f"Datos recopilados: {len(datos_backup)} campos")
    
    # 5. Crear el registro de backup
    backup = BackupGenerico.objects.create(
        modelo=nombre_modelo.capitalize(),  # Ej: 'Alumno' en lugar de 'alumno'
        objeto_id=id_objeto,
        datos_backup=datos_backup,
        motivo=motivo,
        usuario_backup=usuario
    )
    
    print(f"✅ Backup creado exitosamente: {backup}")
    return backup


def restaurar_desde_backup(backup_id, usuario=None):
    """
    Restaura un objeto desde un backup
    
    Args:
        backup_id (int): ID del backup a restaurar
        usuario: Usuario que realiza la restauración
    
    Returns:
        tuple: (nueva_instancia, mensaje)
    """
    try:
        # 1. Obtener el backup
        backup = BackupGenerico.objects.get(id=backup_id, estado='ACTIVO')
        
        print(f"🔄 Iniciando restauración del backup: {backup}")
        
        # 2. Obtener el modelo correcto
        nombre_modelo = backup.modelo.lower()  # Ej: 'Alumno' → 'alumno'
        datos = backup.datos_backup
        
        # 3. Determinar qué modelo estamos restaurando
        if nombre_modelo == 'alumno':
            from .models import Alumno
            Modelo = Alumno
        elif nombre_modelo == 'profesor':
            from .models import Profesor  
            Modelo = Profesor
        elif nombre_modelo == 'curso':
            from .models import Curso
            Modelo = Curso
        else:
            return None, f"❌ Modelo '{nombre_modelo}' no soportado para restauración"
        
        # 4. Verificar si el objeto original aún existe
        objeto_original_existe = Modelo.all_objects.filter(id=backup.objeto_id).exists()
        
        if objeto_original_existe:
            # 5A. Si existe, preguntar si sobreescribir o crear nuevo (aquí creamos nuevo)
            nueva_instancia = Modelo()
            es_nuevo = True
            accion = "creado nuevo"
        else:
            # 5B. Si no existe, restaurar en el mismo ID
            nueva_instancia = Modelo(id=backup.objeto_id)
            es_nuevo = False
            accion = "restaurado"
        
        # 6. Restaurar los datos campo por campo
        campos_restaurados = 0
        
        for field_name, field_value in datos.items():
            # Saltar campos de metadata
            if field_name.startswith('_'):
                continue
                
            # Saltar campos de relaciones (los manejamos después)
            if field_name.endswith('_str'):
                continue
                
            try:
                # 7. Convertir valores de vuelta a sus tipos originales
                field = Modelo._meta.get_field(field_name)
                
                if field_value is None:
                    setattr(nueva_instancia, field_name, None)
                    
                elif isinstance(field, (models.CharField, models.TextField)):
                    setattr(nueva_instancia, field_name, str(field_value) if field_value else '')
                    
                elif isinstance(field, (models.IntegerField, models.AutoField)):
                    setattr(nueva_instancia, field_name, int(field_value) if field_value else 0)
                    
                elif isinstance(field, (models.BooleanField)):
                    setattr(nueva_instancia, field_name, bool(field_value))
                    
                elif isinstance(field, (models.DateField, models.DateTimeField)) and field_value:
                    from django.utils.dateparse import parse_datetime, parse_date
                    if isinstance(field, models.DateTimeField):
                        parsed_date = parse_datetime(field_value)
                    else:
                        parsed_date = parse_date(field_value)
                    setattr(nueva_instancia, field_name, parsed_date)
                    
                elif isinstance(field, models.ForeignKey) and field_value:
                    # Para ForeignKeys, asignar el objeto relacionado
                    related_model = field.related_model
                    try:
                        related_obj = related_model.objects.get(id=field_value)
                        setattr(nueva_instancia, field_name, related_obj)
                    except related_model.DoesNotExist:
                        print(f"⚠️ Objeto relacionado {field_name} #{field_value} no existe")
                        
                campos_restaurados += 1
                
            except Exception as e:
                print(f"⚠️ Error restaurando campo {field_name}: {e}")
                continue
        
        # 8. Guardar la nueva instancia
        nueva_instancia.save()
        
        # 9. Actualizar el estado del backup
        backup.estado = 'RESTAURADO'
        backup.fecha_restauracion = timezone.now()
        backup.usuario_restauracion = usuario
        backup.nuevo_objeto_id = nueva_instancia.id
        backup.save()
        
        mensaje = f"✅ {backup.modelo} {accion} exitosamente desde backup. {campos_restaurados} campos restaurados."
        
        print(f"✅ Restauración completada: {mensaje}")
        return nueva_instancia, mensaje
        
    except BackupGenerico.DoesNotExist:
        return None, "❌ Backup no encontrado o ya fue restaurado"
    except Exception as e:
        return None, f"❌ Error durante la restauración: {str(e)}"
    
# web/utils.py
def listar_backups(modelo=None, estado=None, usuario=None):
    """
    Lista backups con filtros opcionales
    
    Args:
        modelo (str): Filtrar por modelo ('Alumno', 'Profesor', etc.)
        estado (str): Filtrar por estado ('ACTIVO', 'RESTAURADO')
        usuario: Filtrar por usuario
    
    Returns:
        QuerySet: Backups filtrados
    """
    backups = BackupGenerico.objects.all()
    
    if modelo:
        backups = backups.filter(modelo__iexact=modelo)
    
    if estado:
        backups = backups.filter(estado=estado)
        
    if usuario:
        backups = backups.filter(usuario_backup=usuario)
    
    return backups.order_by('-fecha_backup')

def obtener_estadisticas_backups():
    """
    Obtiene estadísticas de los backups
    """
    total = BackupGenerico.objects.count()
    por_modelo = BackupGenerico.objects.values('modelo').annotate(
        total=models.Count('id'),
        activos=models.Count('id', filter=models.Q(estado='ACTIVO')),
        restaurados=models.Count('id', filter=models.Q(estado='RESTAURADO'))
    )
    
    return {
        'total': total,
        'por_modelo': list(por_modelo),
        'activos': BackupGenerico.objects.filter(estado='ACTIVO').count(),
        'restaurados': BackupGenerico.objects.filter(estado='RESTAURADO').count(),
    }



def asignar_grupo_usuario(user, grupo):
    """Asigna un grupo de permisos a un usuario"""
    user.groups.clear()
    
    grupo_obj, created = Group.objects.get_or_create(name=grupo)
    user.groups.add(grupo_obj)
    
    # Asignar permisos básicos según grupo
    if grupo == 'ADMINISTRADOR':
        user.is_staff = True
        user.is_superuser = True
    elif grupo == 'COORDINADOR':
        user.is_staff = True
        user.is_superuser = False
    else:
        user.is_staff = False
        user.is_superuser = False
    
    user.save()

def asignar_permisos_especiales(user, permisos):
    """Asigna permisos especiales individuales"""
    from django.contrib.auth.models import Permission
    from django.contrib.contenttypes.models import ContentType
    
    # Limpiar permisos actuales
    user.user_permissions.clear()
    
    # Asignar nuevos permisos
    for perm_codename in permisos:
        try:
            perm = Permission.objects.get(codename=perm_codename)
            user.user_permissions.add(perm)
        except Permission.DoesNotExist:
            continue
    
    user.save()
    

    
####################################### NOTIFICACIONES ##################################
# def es_coordinador(user):
#     """
#     Verifica si un usuario es coordinador.
#     """
#     if user.is_superuser:
#         return True
    
#     # Usar el related_name correcto
#     if hasattr(user, 'personal_relacionado'):
#         personal = user.personal_relacionado.first()
#         if personal and personal.tipo == 'COORDINADOR':
#             return True
    
#     return False

# def es_coordinador(user):
#     """Verifica si el usuario es coordinador"""
#     return hasattr(user, 'personal') and user.personal.tipo == 'COORDINADOR'

# def es_personal(user):
#     """Verifica si el usuario es personal (cualquier tipo)"""
#     return hasattr(user, 'personal') and user.personal.activo

# def coordinador_required(view_func):
#     """Decorator para vistas que requieren ser coordinador"""
#     @wraps(view_func)
#     def _wrapped_view(request, *args, **kwargs):
#         if es_coordinador(request.user):
#             return view_func(request, *args, **kwargs)
#         return HttpResponseForbidden("No tienes permisos de coordinador")
#     return _wrapped_view

# def personal_required(view_func):
#     """Decorator para vistas que requieren ser personal"""
#     @wraps(view_func)
#     def _wrapped_view(request, *args, **kwargs):
#         if es_personal(request.user):
#             return view_func(request, *args, **kwargs)
#         return HttpResponseForbidden("No eres miembro del personal")
#     return _wrapped_view





# utils.py - Función corregida
from django.utils import timezone
from datetime import timedelta
from django.db.models import Q

def verificar_inasistencias_consecutivas(curso_id, fecha_actual=None):
    """
    Verifica inasistencias consecutivas para todos los alumnos de un curso
    y genera notificaciones automáticas al personal correspondiente.
    
    Prioridad de destinatarios:
    1. AUXILIAR (si existe)
    2. COORDINADOR
    3. ADMINISTRATIVO
    4. SECRETARIA
    """
    from .models import (
        Curso, Inscripcion, Asistencia, 
        Notificacion, TipoNotificacion, Personal
    )
    
    try:
        if fecha_actual is None:
            fecha_actual = timezone.now().date()
        
        # Obtener el curso
        curso = Curso.objects.select_related('auxiliar').get(
            id=curso_id, 
            activo=True
        )
        
        # ==============================================
        # 1. DETERMINAR QUIÉN RECIBE LA NOTIFICACIÓN
        # ==============================================
        usuario_destino = None
        rol_destinatario = None
        
        # Opción A: Si el curso ya tiene auxiliar asignado
        if curso.auxiliar and hasattr(curso.auxiliar, 'user') and curso.auxiliar.user:
            usuario_destino = curso.auxiliar.user
            rol_destinatario = curso.auxiliar.tipo
            print(f"✅ Usando auxiliar asignado: {curso.auxiliar.nombre_completo()}")
        
        # Opción B: Si no tiene auxiliar, buscar COORDINADOR
        elif not usuario_destino:
            coordinador = Personal.objects.filter(
                tipo='COORDINADOR',
                activo=True,
                user__isnull=False
            ).first()
            
            if coordinador and coordinador.user:
                usuario_destino = coordinador.user
                rol_destinatario = 'COORDINADOR'
                print(f"✅ Usando coordinador: {coordinador.nombre_completo()}")
        
        # Opción C: Si no hay coordinador, buscar ADMINISTRATIVO
        elif not usuario_destino:
            administrativo = Personal.objects.filter(
                tipo='ADMINISTRATIVO',
                activo=True,
                user__isnull=False
            ).first()
            
            if administrativo and administrativo.user:
                usuario_destino = administrativo.user
                rol_destinatario = 'ADMINISTRATIVO'
                print(f"✅ Usando administrativo: {administrativo.nombre_completo()}")
        
        # Opción D: Si no hay administrativo, buscar SECRETARIA
        elif not usuario_destino:
            secretaria = Personal.objects.filter(
                tipo='SECRETARIA',
                activo=True,
                user__isnull=False
            ).first()
            
            if secretaria and secretaria.user:
                usuario_destino = secretaria.user
                rol_destinatario = 'SECRETARIA'
                print(f"✅ Usando secretaria: {secretaria.nombre_completo()}")
        
        # Si no encontramos a nadie, salir
        if not usuario_destino:
            print(f"❌ Curso {curso.nombre}: No hay personal disponible para notificar")
            return 0
        
        # ==============================================
        # 2. CREAR/OBTENER TIPO DE NOTIFICACIÓN
        # ==============================================
        tipo_notif, created = TipoNotificacion.objects.get_or_create(
            codigo='INASISTENCIA_CONSECUTIVA',
            defaults={
                'nombre': 'Inasistencias Consecutivas',
                'descripcion': 'Notificación automática cuando un alumno tiene 2 inasistencias consecutivas',
                'prioridad': 'ALTA',
                'color': 'danger',
                'icono': 'fa-user-times',
                'ES_MANUAL': False
            }
        )
        
        # Si se acaba de crear, asignar a los roles relevantes
        if created:
            # Asignar a todos los roles que pueden recibir estas notificaciones
            personal_relevante = Personal.objects.filter(
                tipo__in=['AUXILIAR', 'COORDINADOR', 'ADMINISTRATIVO', 'SECRETARIA'],
                activo=True,
                user__isnull=False
            )
            
            if hasattr(tipo_notif, 'PUEDE_ASIGNAR'):
                tipo_notif.PUEDE_ASIGNAR.set(personal_relevante)
                print(f"✅ Tipo de notificación creado y asignado a {personal_relevante.count()} personas")
        
        # ==============================================
        # 3. VERIFICAR INASISTENCIAS CONSECUTIVAS
        # ==============================================
        inscripciones = Inscripcion.objects.filter(
            curso=curso,
            activo=True,
            estado__in=['INSCRIPTO', 'CURSANDO']
        ).select_related('alumno')
        
        notificaciones_creadas = 0
        
        for inscripcion in inscripciones:
            alumno = inscripcion.alumno
            
            # Obtener las últimas 2 asistencias
            ultimas_asistencias = Asistencia.objects.filter(
                inscripcion=inscripcion,
                fecha__lte=fecha_actual
            ).order_by('-fecha')[:2]
            
            if len(ultimas_asistencias) == 2:
                ultima = ultimas_asistencias[0]
                penultima = ultimas_asistencias[1]
                
                # Verificar si ambas son inasistencias
                if not ultima.presente and not penultima.presente:
                    # Verificar si ya existe notificación similar reciente
                    notificacion_existente = Notificacion.objects.filter(
                        Q(titulo__contains=alumno.nombre_completo()) |
                        Q(mensaje__contains=alumno.nombre_completo()),
                        tipo=tipo_notif,
                        usuario_destino=usuario_destino,
                        estado='PENDIENTE',
                        fecha_creacion__gte=timezone.now() - timedelta(days=3)
                    ).exists()
                    
                    if not notificacion_existente:
                        # Crear notificación
                        notificacion = Notificacion.objects.create(
                            usuario_destino=usuario_destino,
                            usuario_origen=None,
                            tipo=tipo_notif,
                            titulo=f'⚠️ Inasistencias consecutivas - {alumno.nombre_completo()}',
                            mensaje=(
                                f"📋 **Curso:** {curso.nombre}\n"
                                f"👤 **Alumno:** {alumno.nombre_completo()} (DNI: {alumno.dni})\n"
                                f"📅 **Fechas de inasistencia:**\n"
                                f"   • {penultima.fecha.strftime('%d/%m/%Y')} ({penultima.fecha|date:'l'})\n"
                                f"   • {ultima.fecha.strftime('%d/%m/%Y')} ({ultima.fecha|date:'l'})\n\n"
                                f"📍 **Destinatario:** {rol_destinatario}\n\n"
                                f"⚠️ **Acción requerida:**\n"
                                f"El alumno ha faltado a las últimas 2 clases consecutivas.\n"
                                f"Por favor, contactar al alumno para verificar la situación."
                            ),
                            estado='PENDIENTE',
                            prioridad='ALTA',
                            es_manual=False,
                            fecha_vencimiento=timezone.now() + timedelta(days=2)
                        )
                        
                        notificaciones_creadas += 1
                        print(f"   ✅ Notificación creada para {alumno.nombre_completo()}")
        
        if notificaciones_creadas > 0:
            print(f"📊 Curso {curso.nombre}: {notificaciones_creadas} notificaciones creadas (enviadas a {rol_destinatario})")
        else:
            print(f"📊 Curso {curso.nombre}: 0 notificaciones creadas")
        
        return notificaciones_creadas
        
    except Curso.DoesNotExist:
        print(f"❌ Curso con ID {curso_id} no encontrado o inactivo")
        return 0
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 0
    
    
# utils.py - Función auxiliar corregida
def obtener_personal_usuario(usuario):
    """
    Obtiene el objeto Personal relacionado con un usuario.
    """
    if hasattr(usuario, 'personal_relacionado'):
        return usuario.personal_relacionado  # Sin .first()
    return None

def es_coordinador(user):
    """
    Verifica si un usuario es coordinador.
    """
    if user.is_superuser:
        return True
    
    personal = obtener_personal_usuario(user)
    if personal and personal.tipo == 'COORDINADOR':
        return True
    
    return False

def es_coordinador(user):
    """
    Verifica si un usuario es coordinador.
    """
    if user.is_superuser:
        return True
    
    # Acceder directamente (sin .first())
    if hasattr(user, 'personal_relacionado'):
        personal = user.personal_relacionado  # SIN .first()
        if personal and personal.tipo == 'COORDINADOR':
            return True
    
    return False


from web.models import Curso, Notificacion, TipoNotificacion
from django.contrib.auth.models import User
from django.utils import timezone

def crear_notificacion_ausencia_curso(curso, fecha, ausentes_count, total_alumnos, usuario_origen):
    """
    Crea notificación de ausencia para el curso
    Prioridad de destinatario:
    1. Auxiliar asignado al curso (si tiene usuario)
    2. Profesor del curso (si tiene usuario)
    3. Administrativo por defecto (Claudia Alegre o similar)
    """
    print(f"📨 Creando notificación de ausencia para curso: {curso.nombre}")
    
    # 1. Intentar obtener el auxiliar asignado
    destinatario = None
    
    # Primero: buscar auxiliar en curso.auxiliar (relación con Personal)
    if curso.auxiliar and hasattr(curso.auxiliar, 'user') and curso.auxiliar.user:
        destinatario = curso.auxiliar.user
        print(f"   📞 Notificación para auxiliar: {destinatario.get_full_name()}")
    
    # Segundo: buscar en curso.auxiliarCurso (si existe)
    elif hasattr(curso, 'auxiliarCurso') and curso.auxiliarCurso:
        if hasattr(curso.auxiliarCurso, 'user') and curso.auxiliarCurso.user:
            destinatario = curso.auxiliarCurso.user
            print(f"   📞 Notificación para auxiliarCurso: {destinatario.get_full_name()}")
    
    # Tercero: si no hay auxiliar, usar el profesor
    elif curso.profesor and hasattr(curso.profesor, 'user') and curso.profesor.user:
        destinatario = curso.profesor.user
        print(f"   📞 Notificación para profesor (fallback): {destinatario.get_full_name()}")
    
    # Cuarto: buscar Claudia Alegre (usuario específico)
    else:
        try:
            # Buscar usuario por nombre "claudia.alegre" o similar
            claudia_user = User.objects.filter(
                username__icontains='claudia',
                is_active=True
            ).first()
            
            if claudia_user:
                destinatario = claudia_user
                print(f"   📞 Notificación para administrativo por defecto: {destinatario.username}")
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
                    print(f"   📞 Notificación para administrativo genérico: {destinatario.username}")
        except Exception as e:
            print(f"   ⚠️ Error buscando destinatario: {e}")
    
    # Si no se encontró destinatario, no crear notificación
    if not destinatario:
        print("   ⚠️ No se encontró destinatario para notificación de ausencia")
        return None
    
    # Calcular porcentaje de ausencia
    porcentaje = (ausentes_count / total_alumnos * 100) if total_alumnos > 0 else 0
    
    # Crear o obtener tipo de notificación
    tipo_notificacion, created = TipoNotificacion.objects.get_or_create(
        nombre='AUSENCIA_MASIVA',
        defaults={
            'icono': 'fa-user-times',
            'color': 'warning',
            'descripcion': 'Notificación por alta ausencia en curso'
        }
    )
    
    # Crear la notificación
    notificacion = Notificacion.objects.create(
        titulo=f'⚠️ Alta ausencia en {curso.nombre}',
        mensaje=(
            f'Fecha: {fecha.strftime("%d/%m/%Y")}\n'
            f'Ausentes: {ausentes_count} de {total_alumnos} alumnos ({porcentaje:.1f}%)\n'
            f'Curso: {curso.nombre}\n'
            f'Profesor: {curso.profesor.nombre_completo() if curso.profesor else "No asignado"}'
        ),
        usuario_destino=destinatario,
        usuario_origen=usuario_origen,
        estado='PENDIENTE',
        prioridad='ALTA' if porcentaje > 30 else 'MEDIA',
        tipo=tipo_notificacion,
        fecha_vencimiento=timezone.now() + timezone.timedelta(hours=24),  # Vence en 24 horas
        es_manual=False
    )
    
    print(f"   ✅ Notificación creada: ID {notificacion.id} para {destinatario.username}")
    return notificacion



def obtener_destinatario_notificacion_ausencia(curso):
    """
    Obtiene el destinatario correcto para notificaciones de ausencia.
    Prioridad:
    1. Auxiliar del curso (campo 'auxiliar')
    2. Auxiliar del curso (campo 'auxiliarCurso')
    3. Profesor del curso
    4. Administrativo por defecto (Claudia Alegre)
    5. Fallback: usuario que genera la notificación
    
    Retorna: User object o None
    """
    from django.contrib.auth.models import User
    from web.models import Personal
    
    print(f"🔍 Buscando destinatario para curso: {curso.nombre}")
    
    # 1. Verificar campo 'auxiliar'
    if hasattr(curso, 'auxiliar') and curso.auxiliar:
        print(f"   📞 Auxiliar encontrado (campo auxiliar): {curso.auxiliar.nombre_completo()}")
        if hasattr(curso.auxiliar, 'user') and curso.auxiliar.user:
            print(f"   ✅ Usuario del auxiliar: {curso.auxiliar.user.username}")
            return curso.auxiliar.user
    
    # 2. Verificar campo 'auxiliarCurso'
    if hasattr(curso, 'auxiliarCurso') and curso.auxiliarCurso:
        print(f"   📞 Auxiliar encontrado (campo auxiliarCurso): {curso.auxiliarCurso.nombre_completo()}")
        if hasattr(curso.auxiliarCurso, 'user') and curso.auxiliarCurso.user:
            print(f"   ✅ Usuario del auxiliarCurso: {curso.auxiliarCurso.user.username}")
            return curso.auxiliarCurso.user
    
    # 3. Profesor del curso
    if curso.profesor:
        print(f"   👨‍🏫 Profesor encontrado: {curso.profesor.nombre_completo()}")
        if hasattr(curso.profesor, 'user') and curso.profesor.user:
            print(f"   ✅ Usuario del profesor: {curso.profesor.user.username}")
            return curso.profesor.user
    
    # 4. Buscar Claudia Alegre específicamente
    try:
        claudia = User.objects.filter(
            username__icontains='claudia',
            is_active=True
        ).first()
        
        if claudia:
            print(f"   👩‍💼 Claudia Alegre encontrada: {claudia.username}")
            return claudia
    except:
        pass
    
    # 5. Buscar cualquier administrativo activo
    try:
        administrativo = Personal.objects.filter(
            tipo='ADMINISTRATIVO',
            activo=True,
            user__isnull=False
        ).first()
        
        if administrativo and administrativo.user:
            print(f"   👔 Administrativo encontrado: {administrativo.user.username}")
            return administrativo.user
    except Exception as e:
        print(f"   ❌ Error buscando administrativo: {e}")
    
    print("   ⚠️ No se encontró destinatario")
    return None


def crear_notificacion_ausencia_curso(curso, fecha, ausentes_count, total_alumnos, usuario_origen):
    """
    Crea una notificación de ausencia para el curso.
    
    Args:
        curso: Objeto Curso
        fecha: datetime.date de la asistencia
        ausentes_count: Número de ausentes
        total_alumnos: Total de alumnos en el curso
        usuario_origen: User que crea la notificación
    
    Returns:
        Notificacion object o None
    """
    from web.models import TipoNotificacion, Notificacion
    from django.utils import timezone
    
    # Determinar destinatario
    destinatario = obtener_destinatario_notificacion_ausencia(curso)
    
    if not destinatario:
        print("⚠️ No se pudo determinar destinatario, no se crea notificación")
        return None
    
    # Calcular porcentaje
    porcentaje = (ausentes_count / total_alumnos * 100) if total_alumnos > 0 else 0
    
    # Obtener o crear tipo de notificación
    tipo_notificacion, created = TipoNotificacion.objects.get_or_create(
        nombre='AUSENCIA_MASIVA',
        defaults={
            'icono': 'fa-user-times',
            'color': 'warning',
            'descripcion': 'Notificación por alta ausencia en curso'
        }
    )
    
    # Determinar prioridad
    if porcentaje > 50 or ausentes_count >= 10:
        prioridad = 'URGENTE'
    elif porcentaje > 30:
        prioridad = 'ALTA'
    else:
        prioridad = 'MEDIA'
    
    # Crear mensaje
    mensaje = (
        f"**Curso:** {curso.nombre}\n"
        f"**Fecha:** {fecha.strftime('%d/%m/%Y')}\n"
        f"**Profesor:** {curso.profesor.nombre_completo() if curso.profesor else 'No asignado'}\n"
        f"**Total alumnos:** {total_alumnos}\n"
        f"**Ausentes:** {ausentes_count} ({porcentaje:.1f}%)\n"
        f"**Prioridad:** {prioridad}"
    )
    
    # Crear notificación
    notificacion = Notificacion.objects.create(
        titulo=f'⚠️ Alta ausencia en {curso.nombre}',
        mensaje=mensaje,
        usuario_destino=destinatario,
        usuario_origen=usuario_origen,
        estado='PENDIENTE',
        prioridad=prioridad,
        tipo=tipo_notificacion,
        fecha_vencimiento=timezone.now() + timezone.timedelta(hours=24),
        es_manual=False
    )
    
    print(f"✅ Notificación creada: ID {notificacion.id}")
    print(f"   Destinatario: {destinatario.get_full_name()}")
    print(f"   Ausentes: {ausentes_count}/{total_alumnos} ({porcentaje:.1f}%)")
    
    return notificacion


import traceback
from django.utils import timezone
from django.contrib.auth.models import User
from web.models import Notificacion, TipoNotificacion, Personal

def crear_notificacion_ausencia_simple(curso, fecha, ausentes_count, total_alumnos, usuario_origen):
    """
    Función simple para crear notificaciones de ausencia
    """
    try:
        print("=" * 60)
        print(f"🎯 FUNCIÓN crear_notificacion_ausencia_simple")
        print(f"   Curso: {curso.nombre}")
        print(f"   Fecha: {fecha}")
        print(f"   Ausentes: {ausentes_count}/{total_alumnos}")
        
        # Determinar destinatario
        destinatario = None
        
        # 1. Buscar auxiliar
        if curso.auxiliar and hasattr(curso.auxiliar, 'user') and curso.auxiliar.user:
            destinatario = curso.auxiliar.user
            print(f"   ✅ Destinatario: Auxiliar - {destinatario.get_full_name()}")
        
        # 2. Buscar profesor
        elif curso.profesor and hasattr(curso.profesor, 'user') and curso.profesor.user:
            destinatario = curso.profesor.user
            print(f"   ✅ Destinatario: Profesor - {destinatario.get_full_name()}")
        
        # 3. Buscar Claudia Alegre
        else:
            claudia = User.objects.filter(username__icontains='claudia', is_active=True).first()
            if claudia:
                destinatario = claudia
                print(f"   ✅ Destinatario: Claudia Alegre - {claudia.username}")
            else:
                # Buscar cualquier administrativo
                admin = Personal.objects.filter(
                    tipo='ADMINISTRATIVO',
                    activo=True,
                    user__isnull=False
                ).first()
                if admin and admin.user:
                    destinatario = admin.user
                    print(f"   ✅ Destinatario: Administrativo - {destinatario.username}")
        
        if not destinatario:
            print("   ❌ No se encontró destinatario")
            return None
        
        # Crear tipo de notificación
        tipo, created = TipoNotificacion.objects.get_or_create(
            nombre='AUSENCIA_MASIVA',
            defaults={
                'icono': 'fa-user-times',
                'color': 'warning',
                'descripcion': 'Notificación por alta ausencia en curso'
            }
        )
        
        # Calcular porcentaje
        porcentaje = (ausentes_count / total_alumnos * 100) if total_alumnos > 0 else 0
        
        # Determinar prioridad
        if porcentaje > 50 or ausentes_count >= 10:
            prioridad = 'URGENTE'
        elif porcentaje > 30:
            prioridad = 'ALTA'
        else:
            prioridad = 'MEDIA'
        
        # Crear mensaje
        mensaje = f"""Curso: {curso.nombre}
Fecha: {fecha.strftime('%d/%m/%Y')}
Profesor: {curso.profesor.nombre_completo() if curso.profesor else 'No asignado'}
Total alumnos: {total_alumnos}
Ausentes: {ausentes_count} ({porcentaje:.1f}%)
Prioridad: {prioridad}"""
        
        # Crear notificación
        notificacion = Notificacion.objects.create(
            titulo=f'⚠️ Alta ausencia en {curso.nombre}',
            mensaje=mensaje,
            usuario_destino=destinatario,
            usuario_origen=usuario_origen,
            estado='PENDIENTE',
            prioridad=prioridad,
            tipo=tipo,
            fecha_vencimiento=timezone.now() + timezone.timedelta(hours=24),
            es_manual=False
        )
        
        print(f"   📨 Notificación creada: ID {notificacion.id}")
        print(f"   📤 Para: {destinatario.get_full_name()}")
        print("=" * 60)
        
        return notificacion
        
    except Exception as e:
        print(f"❌ ERROR en crear_notificacion_ausencia_simple: {e}")
        print(f"   Traceback: {traceback.format_exc()}")
        return None
    
def es_coordinador(user):
    """Verifica si el usuario es coordinador"""
    try:
        if hasattr(user, 'personal_relacionado'):
            return user.personal_relacionado.tipo == 'COORDINADOR'
        else:
            # Buscar el personal relacionado
            from .models import Personal
            personal = Personal.objects.get(user=user)
            return personal.tipo == 'COORDINADOR'
    except:
        return False
    
def get_client_ip(request):
    """Obtiene la dirección IP del cliente"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

def generar_fechas_clase(fecha_inicio, fecha_fin, dias_curso):
    """
    Genera las fechas de clase basado en los días configurados
    Versión simple y confiable sin dateutil
    """
    from datetime import timedelta
    
    # Mapeo de días en español a números de weekday (0=Lunes, 6=Domingo)
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
    
    fechas_clase = []
    fecha_actual = fecha_inicio
    
    # Generar todas las fechas entre inicio y fin
    while fecha_actual <= fecha_fin:
        # weekday() devuelve: 0=Lunes, 1=Martes, ..., 6=Domingo
        if fecha_actual.weekday() in dias_numeros:
            fechas_clase.append(fecha_actual)
        fecha_actual += timedelta(days=1)
    
    return fechas_clase