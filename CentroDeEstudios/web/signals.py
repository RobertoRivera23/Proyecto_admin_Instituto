from django.dispatch import receiver
from django.contrib.auth import get_user_model
from django.contrib.auth.models import User, Group
from .models import Alumno, Personal, Profesor, Curso, HistorialCambios, PasswordChangeLog
from .utils import crear_backup_generico
import logging
from django.db.models.signals import post_save, pre_delete, post_delete
from django.contrib.auth.signals import password_changed

# Configurar logging
logger = logging.getLogger(__name__)
UserModel = get_user_model()

# =============================================================================
# FUNCIONES AUXILIARES
# =============================================================================

def _obtener_usuario_actual():
    """Intenta obtener el usuario actual"""
    try:
        from django.contrib.auth import get_user
        from django.contrib.auth.models import AnonymousUser
        from django.db import connection
        
        user = get_user(connection.cursor().db.connection.threadlocal)
        if user and not isinstance(user, AnonymousUser):
            return user
    except:
        pass
    return None

def _serializar_instancia(instancia):
    """Serializa una instancia para el historial"""
    datos = {}
    for field in instancia._meta.fields:
        field_name = field.name
        field_value = getattr(instancia, field_name)
        
        if hasattr(field_value, 'id'):
            datos[field_name] = field_value.id
        elif hasattr(field_value, 'isoformat'):
            datos[field_name] = field_value.isoformat()
        else:
            datos[field_name] = str(field_value)
    
    return datos

def get_client_ip(request):
    """Obtiene la IP del cliente"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

# =============================================================================
# SEÑALES PARA BACKUP AUTOMÁTICO (MANTENER)
# =============================================================================

@receiver(pre_delete, sender=Alumno)
def backup_automatico_alumno(sender, instance, **kwargs):
    """Backup automático para Alumno"""
    try:
        logger.info(f"🔄 Backup automático para Alumno ID: {instance.id}")
        if hasattr(instance, 'eliminado') and instance.eliminado:
            motivo = "Eliminación definitiva después de soft delete"
        else:
            motivo = "Eliminación directa del objeto"
        
        crear_backup_generico(
            instancia=instance,
            motivo=f"Backup automático - {motivo}",
            usuario=_obtener_usuario_actual()
        )
        logger.info(f"✅ Backup creado para Alumno: {instance.nombre_completo()}")
    except Exception as e:
        logger.error(f"❌ Error en backup de Alumno {instance.id}: {e}")

@receiver(pre_delete, sender=Profesor)
def backup_automatico_profesor(sender, instance, **kwargs):
    """Backup automático para Profesor"""
    try:
        logger.info(f"🔄 Backup automático para Profesor ID: {instance.id}")
        if hasattr(instance, 'eliminado') and instance.eliminado:
            motivo = "Eliminación definitiva después de soft delete"
        else:
            motivo = "Eliminación directa del objeto"
        
        crear_backup_generico(
            instancia=instance,
            motivo=f"Backup automático - {motivo}",
            usuario=_obtener_usuario_actual()
        )
        logger.info(f"✅ Backup creado para Profesor: {instance.nombre_completo()}")
    except Exception as e:
        logger.error(f"❌ Error en backup de Profesor {instance.id}: {e}")

@receiver(pre_delete, sender=Curso)
def backup_automatico_curso(sender, instance, **kwargs):
    """Backup automático para Curso"""
    try:
        logger.info(f"🔄 Backup automático para Curso ID: {instance.id}")
        if hasattr(instance, 'eliminado') and instance.eliminado:
            motivo = "Eliminación definitiva después de soft delete"
        else:
            motivo = "Eliminación directa del objeto"
        
        crear_backup_generico(
            instancia=instance,
            motivo=f"Backup automático - {motivo}",
            usuario=_obtener_usuario_actual()
        )
        logger.info(f"✅ Backup creado para Curso: {instance.nombre}")
    except Exception as e:
        logger.error(f"❌ Error en backup de Curso {instance.id}: {e}")

# =============================================================================
# SEÑALES PARA HISTORIAL (MANTENER)
# =============================================================================

@receiver(post_save, sender=Alumno)
def historial_automatico_alumno(sender, instance, created, **kwargs):
    """Registra en historial cuando se crea/modifica un alumno"""
    try:
        if created:
            accion = 'CREAR'
            descripcion = f"Alumno {instance.nombre_completo()} creado"
            datos_nuevos = _serializar_instancia(instance)
            
            HistorialCambios.objects.create(
                modelo='Alumno',
                objeto_id=instance.id,
                accion=accion,
                usuario=_obtener_usuario_actual(),
                datos_nuevos=datos_nuevos,
                descripcion=descripcion
            )
            logger.info(f"📝 Historial: {descripcion}")
        else:
            accion = 'EDITAR'
            descripcion = f"Alumno {instance.nombre_completo()} modificado"
            
            HistorialCambios.objects.create(
                modelo='Alumno',
                objeto_id=instance.id,
                accion=accion,
                usuario=_obtener_usuario_actual(),
                descripcion=descripcion
            )
            logger.info(f"📝 Historial: {descripcion}")
    except Exception as e:
        logger.error(f"❌ Error en historial de Alumno {instance.id}: {e}")

# =============================================================================
# SEÑALES PARA CONTRASEÑAS (MANTENER)
# =============================================================================

@receiver(password_changed)
def log_password_change(sender, request, user, **kwargs):
    """Registra cambio de contraseña"""
    PasswordChangeLog.objects.create(
        user=user,
        changed_by=user if user.is_authenticated else None,
        ip_address=get_client_ip(request),
        user_agent=request.META.get('HTTP_USER_AGENT', '')
    )

# =============================================================================
# SEÑALES PARA SINCRONIZACIÓN (MANTENER)
# =============================================================================

@receiver(post_save, sender=UserModel)
def sincronizar_usuario_con_persona(sender, instance, created, **kwargs):
    """Sincroniza User con Persona asociada"""
    try:
        persona = None
        for model in [Alumno, Profesor, Personal]:
            try:
                persona = model.objects.get(user=instance)
                break
            except model.DoesNotExist:
                continue
        
        if persona:
            cambios = []
            if instance.first_name != persona.nombre:
                persona.nombre = instance.first_name
                cambios.append(f"Nombre: {persona.nombre}")
            
            if instance.last_name != persona.apellido:
                persona.apellido = instance.last_name
                cambios.append(f"Apellido: {persona.apellido}")
            
            if instance.email and instance.email != persona.mail:
                persona.mail = instance.email
                cambios.append(f"Email: {persona.mail}")
            
            if cambios:
                persona.save()
                logger.info(f"Sincronizado {persona}: {', '.join(cambios)}")
    except Exception as e:
        logger.error(f"Error sincronizando usuario {instance.username}: {e}")

@receiver(post_save, sender=Alumno)
@receiver(post_save, sender=Profesor)
@receiver(post_save, sender=Personal)
def sincronizar_persona_con_usuario(sender, instance, created, **kwargs):
    """Sincroniza Persona con User asociado"""
    try:
        if instance.user:
            cambios = []
            
            if instance.nombre and instance.nombre != instance.user.first_name:
                instance.user.first_name = instance.nombre
                cambios.append(f"Nombre: {instance.nombre}")
            
            if instance.apellido and instance.apellido != instance.user.last_name:
                instance.user.last_name = instance.apellido
                cambios.append(f"Apellido: {instance.apellido}")
            
            if instance.mail and instance.mail != instance.user.email:
                instance.user.email = instance.mail
                cambios.append(f"Email: {instance.mail}")
            
            if instance.activo != instance.user.is_active:
                instance.user.is_active = instance.activo and not instance.eliminado
                cambios.append(f"Activo: {instance.user.is_active}")
            
            if cambios:
                instance.user.save()
                logger.info(f"Sincronizado usuario {instance.user.username}: {', '.join(cambios)}")
    except Exception as e:
        logger.error(f"Error sincronizando persona {instance.nombre_completo()}: {e}")

# =============================================================================
# SEÑALES PARA ASIGNACIÓN DE GRUPOS - VERSIÓN ÚNICA Y CORREGIDA
# =============================================================================

@receiver(post_save, sender=Alumno)
def asignar_grupo_alumno(sender, instance, created, **kwargs):
    """Asigna grupo Alumnos"""
    if instance.user and instance.puede_acceder_sistema:
        try:
            grupo, _ = Group.objects.get_or_create(name='Alumnos')
            instance.user.groups.add(grupo)
            instance.user.is_staff = False
            instance.user.save()
            logger.info(f"✅ Alumno {instance.nombre_completo()} asignado a grupo Alumnos")
        except Exception as e:
            logger.error(f"Error asignando grupo a alumno {instance}: {e}")

@receiver(post_save, sender=Profesor)
def asignar_grupo_profesor(sender, instance, created, **kwargs):
    """Asigna grupo Profesores"""
    if instance.user and instance.puede_acceder_sistema:
        try:
            grupo, _ = Group.objects.get_or_create(name='Profesores')
            instance.user.groups.add(grupo)
            instance.user.is_staff = True
            instance.user.save()
            logger.info(f"✅ Profesor {instance.nombre_completo()} asignado a grupo Profesores")
        except Exception as e:
            logger.error(f"Error asignando grupo a profesor {instance}: {e}")

@receiver(post_save, sender=Personal)
def asignar_grupos_personal_final(sender, instance, created, **kwargs):
    """
    ÚNICA señal para asignar grupos a Personal - VERSIÓN DEFINITIVA
    """
    if not instance.user:
        return
    
    try:
        print(f"\n{'='*60}")
        print(f"[SEÑAL PERSONAL] 🔄 Procesando: {instance.nombre_completo()}")
        print(f"[SEÑAL PERSONAL] 🎯 Rol: {instance.tipo}")
        
        # 1. Obtener grupos base
        grupo_personal, _ = Group.objects.get_or_create(name='Personal')
        
        # 2. Limpiar SOLO grupos de personal (no tocar Alumnos/Profesores)
        grupos_a_remover = [
            'ADMINISTRADOR',  # ¡NO debe existir!
            'Administración',
            'Administrativo', 
            'Coordinador',
            'Secretaría',
            'Consulta'
        ]
        
        for grupo_nombre in grupos_a_remover:
            try:
                grupo = Group.objects.get(name=grupo_nombre)
                instance.user.groups.remove(grupo)
                print(f"[SEÑAL PERSONAL] 🧹 Removido grupo: {grupo_nombre}")
            except Group.DoesNotExist:
                pass
        
        # 3. Agregar grupo base 'Personal' a TODOS
        instance.user.groups.add(grupo_personal)
        
        # 4. Lógica específica por tipo
        if instance.tipo == 'ADMINISTRATIVO':
            grupo_admin, _ = Group.objects.get_or_create(name='Administración')
            grupo_especifico, _ = Group.objects.get_or_create(name='Administrativo')
            
            instance.user.groups.add(grupo_admin)
            instance.user.groups.add(grupo_especifico)
            
            instance.user.is_staff = True
            print(f"[SEÑAL PERSONAL] ✅ Configurado como: Administrativo")
            print(f"[SEÑAL PERSONAL]   Grupos: Personal, Administración, Administrativo")
            
        elif instance.tipo == 'COORDINADOR':
            grupo_admin, _ = Group.objects.get_or_create(name='Administración')
            grupo_especifico, _ = Group.objects.get_or_create(name='Coordinador')
            
            instance.user.groups.add(grupo_admin)
            instance.user.groups.add(grupo_especifico)
            
            instance.user.is_staff = True
            print(f"[SEÑAL PERSONAL] ✅ Configurado como: Coordinador (con privilegios)")
            print(f"[SEÑAL PERSONAL]   Grupos: Personal, Administración, Coordinador")
            
        elif instance.tipo == 'SECRETARIA':
            grupo_especifico, _ = Group.objects.get_or_create(name='Secretaría')
            
            instance.user.groups.add(grupo_especifico)
            
            instance.user.is_staff = True
            print(f"[SEÑAL PERSONAL] ✅ Configurado como: Secretaría")
            print(f"[SEÑAL PERSONAL]   Grupos: Personal, Secretaría")
            
        else:  # CONSULTA u otros
            grupo_especifico, _ = Group.objects.get_or_create(name='Consulta')
            
            instance.user.groups.add(grupo_especifico)
            
            instance.user.is_staff = False
            print(f"[SEÑAL PERSONAL] ✅ Configurado como: Consulta")
            print(f"[SEÑAL PERSONAL]   Grupos: Personal, Consulta")
        
        # 5. Asegurar acceso al sistema
        if not instance.puede_acceder_sistema:
            instance.puede_acceder_sistema = True
            instance.save(update_fields=['puede_acceder_sistema'])
            print(f"[SEÑAL PERSONAL] 🔧 Actualizado puede_acceder_sistema a True")
        
        # 6. Guardar usuario
        instance.user.save()
        print(f"[SEÑAL PERSONAL] 💾 Usuario {instance.user.username} actualizado")
        print(f"{'='*60}\n")
        
    except Exception as e:
        print(f"[SEÑAL PERSONAL] ❌ ERROR: {e}")
        logger.error(f"Error en señal asignar_grupos_personal_final: {e}")

# =============================================================================
# SEÑALES PARA CREACIÓN INICIAL (MODIFICADA)
# =============================================================================

@receiver(post_save, sender=UserModel)
def crear_grupos_iniciales(sender, instance, created, **kwargs):
    """Crea grupos iniciales si no existen"""
    if created and UserModel.objects.count() == 1:  # Primer usuario (superusuario)
        try:
            from .permissions import PermisosSistema
            PermisosSistema.crear_grupos_y_permisos()
            logger.info("✅ Grupos y permisos iniciales creados exitosamente")
        except Exception as e:
            logger.error(f"❌ Error creando grupos iniciales: {e}")
