from django.conf import settings
from django.db import models
from django.core.validators import MaxValueValidator, MinValueValidator
from datetime import datetime, date
from django.contrib.auth.models import User
from django.utils import timezone
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.db.models import Q
from django.urls import reverse
import json


################################## Managers personalizados ##############################33
class BaseManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(eliminado=False)
    
    def activos(self):
        return self.get_queryset().filter(activo=True)
    
    def inactivos(self):
        return self.get_queryset().filter(activo=False)
    
    def eliminados(self):
        return super().get_queryset().filter(eliminado=True)

class AlumnoManager(BaseManager):
    def con_deuda(self):
        return self.get_queryset().filter(activo=True)

class ProfesorManager(BaseManager):
    pass

class PersonalManager(BaseManager):
    def por_tipo(self, tipo):
        return self.get_queryset().filter(tipo=tipo, activo=True)

class CursoManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(eliminado=False)
    
    def activos(self):
        return self.get_queryset().filter(activo=True)
    
    def inactivos(self):
        return self.get_queryset().filter(activo=False)
    
    def eliminados(self):
        return super().get_queryset().filter(eliminado=True)
    
    def del_profesor(self, profesor):
        return self.get_queryset().filter(profesor=profesor, activo=True)
    
    def with_eliminados(self):
        # Todos los cursos, incluyendo eliminados
        return super().get_queryset()

class PersonaManager(BaseManager):
    pass

class Persona(models.Model):
    nombre = models.CharField(max_length=100, verbose_name="Nombre")
    apellido = models.CharField(max_length=100, verbose_name="Apellido")
    dni = models.CharField(max_length=20, unique=True, verbose_name="DNI")
    fecha_nacimiento = models.DateField(verbose_name="Fecha de Nacimiento", null=True, blank=True)
    telefono = models.CharField(max_length=20, verbose_name="Teléfono", null=True, blank=True)
    mail = models.EmailField(verbose_name="Email", null=True, blank=True)
    direccion = models.TextField(verbose_name="Dirección", null=True, blank=True)
    sexo = models.CharField(max_length=10, choices=[('M', 'Masculino'), ('F', 'Femenino'), ('O', 'Otro')], verbose_name="Sexo", null=True, blank=True)
    telefono_contacto = models.CharField(max_length=20, verbose_name="Teléfono de Contacto", null=True, blank=True)
    foto = models.ImageField(upload_to='fotos/', verbose_name="Foto", null=True, blank=True)
    
    # Campos de soft delete
    activo = models.BooleanField(default=True, verbose_name="Activo")
    eliminado = models.BooleanField(default=False, verbose_name="Eliminado")
    eliminado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='%(class)s_eliminados')
    fecha_eliminacion = models.DateTimeField(null=True, blank=True, verbose_name="Fecha de Eliminación")
    
    # Campos de auditoría
    fecha_creacion = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Creación", null=True, blank=True) ##############mmodif)
    fecha_actualizacion = models.DateTimeField(auto_now=True, verbose_name="Fecha de Actualización")
    user = models.OneToOneField(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        verbose_name="Usuario del Sistema",
        related_name='%(class)s_relacionado',  # Para relaciones específicas
        help_text="Usuario de sistema asociado a esta persona"
    )
    
    # Campos para control de acceso
    puede_acceder_sistema = models.BooleanField(
        default=False,
        verbose_name="Puede acceder al sistema",
        help_text="Indica si esta persona puede iniciar sesión en el sistema"
    )
    # user = models.OneToOneField(
    #     User, 
    #     on_delete=models.SET_NULL, 
    #     null=True, 
    #     blank=True,
    #     verbose_name="Usuario del Sistema",
    #     related_name='%(class)s_relacionado',  # Para relaciones específicas
    #     help_text="Usuario de sistema asociado a esta persona"
    # )
    
    # Campos para control de acceso
    puede_acceder_sistema = models.BooleanField(
        default=False,
        verbose_name="Puede acceder al sistema",
        help_text="Indica si esta persona puede iniciar sesión en el sistema"
    )
    

    class Meta:
        abstract = True

    def nombre_completo(self):
        return f"{self.nombre} {self.apellido}"

    def __str__(self):
        return self.nombre_completo()
    
    # Método para obtener tipo de persona
    @property
    def tipo_persona(self):
        """Retorna el tipo de persona (Alumno, Profesor, Personal)"""
        return self.__class__.__name__.lower()
    
    # Método para crear usuario (base)
    def crear_usuario_sistema(self, request_user=None, forzar=False):
        """
        Crea un usuario del sistema para la persona
        Args:
            request_user: Usuario que realiza la acción (para historial)
            forzar: Si True, crea usuario incluso sin email
        """
        from django.contrib.auth.models import Group
        
        # Si ya tiene usuario, retornarlo
        if self.user and not forzar:
            return self.user
        
        try:
            # Validar que tenga email
            if not self.mail and not forzar:
                raise ValueError("La persona debe tener un email para crear usuario")
            
            # Generar username único
            username_base = f"{self.dni}" if self.dni else f"{self.nombre.lower()}.{self.apellido.lower()}"
            username = username_base
            counter = 1
            
            while User.objects.filter(username=username).exists():
                username = f"{username_base}{counter}"
                counter += 1
            
            # Crear contraseña temporal
            from django.utils.crypto import get_random_string
            password_temp = get_random_string(10)
            
            # Crear usuario
            user = User.objects.create_user(
                username=username,
                password=password_temp,
                first_name=self.nombre,
                last_name=self.apellido,
                email=self.mail if self.mail else f"{username}@institucion.edu",
                is_active=True
            )
            
            # Asignar grupo según tipo de persona
            grupo_nombre = self._obtener_nombre_grupo()
            grupo, created = Group.objects.get_or_create(name=grupo_nombre)
            user.groups.add(grupo)
            
            # Asignar usuario a la persona
            self.user = user
            self.puede_acceder_sistema = True
            self.save()
            
            # Registrar en historial
            if request_user:
                HistorialCambios.objects.create(
                    modelo=self.__class__.__name__,
                    objeto_id=self.id,
                    accion='EDITAR',
                    usuario=request_user,
                    descripcion=f"Usuario del sistema creado: {username} (Grupo: {grupo_nombre})"
                )
            
            # Guardar contraseña temporal para notificación
            user._password_temp = password_temp
            
            return user
            
        except Exception as e:
            print(f"❌ Error al crear usuario para {self.nombre_completo()}: {e}")
            raise
    
    def _obtener_nombre_grupo(self):
        """Método abstracto para obtener nombre de grupo (debe sobrescribirse)"""
        raise NotImplementedError("Cada tipo de persona debe implementar este método")
    
    # Método para desactivar usuario
    def desactivar_usuario_sistema(self, request_user=None):
        """Desactiva el usuario del sistema"""
        if self.user:
            self.user.is_active = False
            self.user.save()
            self.puede_acceder_sistema = False
            self.save()
            
            if request_user:
                HistorialCambios.objects.create(
                    modelo=self.__class__.__name__,
                    objeto_id=self.id,
                    accion='EDITAR',
                    usuario=request_user,
                    descripcion=f"Usuario del sistema desactivado: {self.user.username}"
                )
    
    # Método para reactivar usuario
    def reactivar_usuario_sistema(self, request_user=None):
        """Reactivar usuario del sistema"""
        if self.user:
            self.user.is_active = True
            self.user.save()
            self.puede_acceder_sistema = True
            self.save()
            
            if request_user:
                HistorialCambios.objects.create(
                    modelo=self.__class__.__name__,
                    objeto_id=self.id,
                    accion='EDITAR',
                    usuario=request_user,
                    descripcion=f"Usuario del sistema reactivado: {self.user.username}"
                )

#########################################  HISTORIAL DE CAMBIOS  ###########################3
class HistorialCambios(models.Model):
    TIPO_ACCION = [
        ('SELECCIONAR', 'Seleccionar'),
        ('CREAR', 'Crear'),
        ('EDITAR', 'Editar'),
        ('ELIMINAR', 'Eliminar'),
        ('RESTAURAR', 'Restaurar'),
    ]

    modelo = models.CharField(max_length=100, verbose_name="Modelo")
    objeto_id = models.IntegerField(verbose_name="ID del objeto")
    accion = models.CharField(max_length=20, choices=TIPO_ACCION, default='SELECCIONAR', verbose_name="Acción")
    usuario = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, verbose_name="Usuario")
    fecha = models.DateTimeField(auto_now_add=True, verbose_name="Fecha")
    datos_anteriores = models.JSONField(null=True, blank=True, verbose_name="Datos anteriores")
    datos_nuevos = models.JSONField(null=True, blank=True, verbose_name="Datos nuevos")
    descripcion = models.TextField(blank=True, verbose_name="Descripción")

    class Meta:
        verbose_name = "Historial de Cambios"
        verbose_name_plural = "Historial de Cambios"
        ordering = ['-fecha']

    def __str__(self):
        return f"{self.modelo} #{self.objeto_id} - {self.accion} - {self.usuario}"

################################### PROFESOR ###############################################333

class ProfesorManager(models.Manager):
    """Manager personalizado para profesores"""
    
    def activos(self):
        """Devuelve solo profesores activos (no eliminados)"""
        return self.get_queryset().filter(eliminado=False, activo=True)
    
    def eliminados(self):
        """Devuelve solo profesores eliminados"""
        return self.get_queryset().filter(eliminado=True)
    
    def todos(self):
        """Devuelve todos los profesores, incluyendo eliminados"""
        return self.get_queryset()

class Profesor(Persona):  # Asumiendo que Profesor hereda de Persona
    cuit = models.BigIntegerField(
        verbose_name="CUIT", 
        unique=True, 
        null=True, 
        blank=True
    )
    entidad = models.CharField(
        max_length=50, 
        verbose_name="Banco", 
        default="Sin especificar"
    )
    cbu = models.BigIntegerField(
        verbose_name="CBU", 
        unique=True, 
        null=True, 
        blank=True
    )
    
    # Campos para soft delete
    eliminado = models.BooleanField(default=False)
    eliminado_por = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='profesores_eliminados'
    )
    fecha_eliminacion = models.DateTimeField(null=True, blank=True)
    
    # Manager personalizado
    objects = ProfesorManager()
    
    class Meta:
        verbose_name = "Profesor"
        verbose_name_plural = "Profesores"
        ordering = ['apellido', 'nombre']

    def __str__(self):
        return f"{self.nombre_completo()} | CUIT: {self.cuit}"
    
    def nombre_completo(self):
        """Devuelve el nombre completo del profesor"""
        return f"{self.nombre} {self.apellido}"
    
    def soft_delete(self, usuario=None):
        """Marca el profesor como eliminado y guarda backup de cursos asignados"""
        try:
            print(f"DEBUG SOFT DELETE: Iniciando eliminación del profesor {self.id}")
            
            # 1. Guardar IDs de cursos asignados antes de desasociar
            cursos_asignados_ids = list(self.cursos_asignados.values_list('id', flat=True))
            print(f"DEBUG SOFT DELETE: Cursos asignados: {cursos_asignados_ids}")
            
            # 2. Crear backup con las relaciones
            self._crear_backup_eliminacion(usuario, cursos_asignados_ids)
            
            # 3. Desasociar de los cursos (poner profesor a NULL)
            self._desasociar_de_cursos()
            
            # 4. Marcar como eliminado
            self.eliminado = True
            self.eliminado_por = usuario
            self.fecha_eliminacion = timezone.now()
            self.activo = False
            self.save(update_fields=['eliminado', 'eliminado_por', 'fecha_eliminacion', 'activo'])
            
            # 5. Registrar en historial
            self._registrar_historial('ELIMINAR', usuario)
            
            print(f"DEBUG SOFT DELETE: Profesor {self.id} eliminado correctamente")
            return True
            
        except Exception as e:
            print(f"❌ ERROR en soft_delete Profesor {self.id}: {str(e)}")
            import traceback
            print(traceback.format_exc())
            raise
    
    def restore(self, usuario=None):
        """Restaura un profesor eliminado y reassigna sus cursos"""
        try:
            print(f"DEBUG RESTORE: Restaurando profesor {self.id}")
            
            # 1. Restaurar los datos básicos
            self.eliminado = False
            self.eliminado_por = None
            self.fecha_eliminacion = None
            self.activo = True
            self.save(update_fields=['eliminado', 'eliminado_por', 'fecha_eliminacion', 'activo'])
            
            print(f"DEBUG RESTORE: Datos básicos restaurados")
            
            # 2. Reasignar cursos si es posible
            cursos_restaurados = self._reasignar_cursos(usuario)
            
            # 3. Crear backup de la restauración
            self._crear_backup_restauracion(usuario, cursos_restaurados)
            
            # 4. Registrar en historial
            self._registrar_historial('RESTAURAR', usuario, cursos_restaurados)
            
            print(f"DEBUG RESTORE: Profesor {self.id} restaurado exitosamente")
            return cursos_restaurados
            
        except Exception as e:
            print(f"❌ ERROR en restore Profesor {self.id}: {str(e)}")
            import traceback
            print(traceback.format_exc())
            raise
    
    # ========== MÉTODOS PRIVADOS PARA SOFT DELETE/RESTORE ==========
    
    def _crear_backup_eliminacion(self, usuario, cursos_asignados_ids):
        """Crea un backup de la eliminación con las relaciones"""
        try:
            from .utils import crear_backup_generico
            
            # Datos adicionales para el backup
            datos_extra = {
                'cursos_asignados': cursos_asignados_ids,
                'fecha_eliminacion': timezone.now().isoformat(),
                'eliminado_por': usuario.username if usuario else 'sistema',
                'relaciones_guardadas': True
            }
            
            crear_backup_generico(
                instancia=self,
                datos_extra=datos_extra,
                motivo=f"Soft delete del profesor {self.nombre_completo()}",
                usuario=usuario,
                tipo_backup='ELIMINACION_PROFESOR'
            )
            print(f"DEBUG: Backup de eliminación creado")
            
        except Exception as e:
            print(f"⚠️ Advertencia: No se pudo crear backup: {e}")
    
    def _desasociar_de_cursos(self):
        """Desasocia al profesor de todos sus cursos"""
        try:
            # Buscar todos los cursos activos que tienen este profesor
            from .models import Curso
            cursos = Curso.objects.filter(
                profesor=self,
                activo=True,
                eliminado=False
            )
            
            count = 0
            for curso in cursos:
                # Guardar relación en historial antes de desasociar
                HistorialCambios.objects.create(
                    modelo='CursoProfesor',
                    objeto_id=curso.id,
                    accion='DESASIGNAR',
                    usuario=self.eliminado_por,
                    descripcion=f"Desasignado profesor {self.nombre_completo()} del curso {curso.nombre}"
                )
                
                # Desasociar
                curso.profesor = None
                curso.save(update_fields=['profesor'])
                count += 1
            
            print(f"DEBUG: Desasociado de {count} cursos")
            return count
            
        except Exception as e:
            print(f"⚠️ Advertencia al desasociar cursos: {e}")
            return 0
    
    def _reasignar_cursos(self, usuario):
        """Reasigna los cursos que tenía el profesor antes de ser eliminado"""
        try:
            # Buscar el backup más reciente de eliminación
            from .models import BackupRegistro
            backup = BackupRegistro.objects.filter(
                modelo='Profesor',
                objeto_id=self.id,
                tipo_backup='ELIMINACION_PROFESOR'
            ).order_by('-fecha_backup').first()
            
            if not backup:
                print(f"DEBUG: No se encontró backup de eliminación")
                return []
            
            # Extraer IDs de cursos del backup
            datos_backup = json.loads(backup.contenido)
            cursos_asignados_ids = datos_backup.get('cursos_asignados', [])
            
            if not cursos_asignados_ids:
                print(f"DEBUG: No hay cursos para reasignar en el backup")
                return []
            
            # Reasignar cursos
            from .models import Curso
            cursos_restaurados = []
            
            for curso_id in cursos_asignados_ids:
                try:
                    curso = Curso.objects.get(
                        id=curso_id,
                        activo=True,
                        eliminado=False
                    )
                    
                    # Solo reasignar si el curso no tiene profesor actualmente
                    if curso.profesor is None:
                        curso.profesor = self
                        curso.save(update_fields=['profesor'])
                        
                        # Registrar en historial
                        HistorialCambios.objects.create(
                            modelo='CursoProfesor',
                            objeto_id=curso.id,
                            accion='REASIGNAR',
                            usuario=usuario,
                            descripcion=f"Reasignado profesor {self.nombre_completo()} al curso {curso.nombre}"
                        )
                        
                        cursos_restaurados.append(curso)
                        print(f"DEBUG: Curso {curso_id} reasignado")
                        
                except Curso.DoesNotExist:
                    print(f"DEBUG: Curso {curso_id} no existe o no está activo")
                except Exception as e:
                    print(f"DEBUG: Error al reasignar curso {curso_id}: {e}")
            
            print(f"DEBUG: Total cursos reasignados: {len(cursos_restaurados)}")
            return cursos_restaurados
            
        except Exception as e:
            print(f"⚠️ Advertencia al reasignar cursos: {e}")
            return []
    
    def _crear_backup_restauracion(self, usuario, cursos_restaurados):
        """Crea un backup de la restauración"""
        try:
            from .utils import crear_backup_generico
            
            # Datos adicionales para el backup
            cursos_restaurados_ids = [curso.id for curso in cursos_restaurados]
            datos_extra = {
                'cursos_restaurados': cursos_restaurados_ids,
                'fecha_restauracion': timezone.now().isoformat(),
                'restaurado_por': usuario.username if usuario else 'sistema'
            }
            
            crear_backup_generico(
                instancia=self,
                datos_extra=datos_extra,
                motivo=f"Restauración del profesor {self.nombre_completo()}",
                usuario=usuario,
                tipo_backup='RESTAURACION_PROFESOR'
            )
            print(f"DEBUG: Backup de restauración creado")
            
        except Exception as e:
            print(f"⚠️ Advertencia: No se pudo crear backup de restauración: {e}")
    
    def _registrar_historial(self, accion, usuario, datos_extra=None):
        """Registra una acción en el historial de cambios"""
        try:
            descripcion = f"Profesor {self.nombre_completo()} {accion.lower()}do"
            if datos_extra:
                cursos_count = len(datos_extra) if isinstance(datos_extra, list) else 0
                if cursos_count > 0:
                    descripcion += f" con {cursos_count} curso{'s' if cursos_count > 1 else ''} reasignado{'s' if cursos_count > 1 else ''}"
            
            HistorialCambios.objects.create(
                modelo='Profesor',
                objeto_id=self.id,
                accion=accion,
                usuario=usuario,
                descripcion=descripcion
            )
            print(f"DEBUG: Historial registrado - {accion}")
            
        except Exception as e:
            print(f"⚠️ Advertencia al registrar historial: {e}")
            
    def _obtener_nombre_grupo(self):
        """Sobrescribe el método para obtener nombre de grupo específico"""
        return "Profesores"
    
    def get_permisos_especificos(self):
        """Permisos específicos para profesores"""
        return [
            'web.view_profesor',
            'web.change_profesor', 
            'web.view_curso',
            'web.change_curso',
            'web.view_alumno',
            'web.view_inscripcion',
            'web.add_asistencia',
            'web.change_asistencia',
            'web.view_asistencia',
            # Agrega aquí otros permisos específicos de profesor
        ]
    
    def asignar_grupo_profesor(self, user):
        """Asigna al usuario al grupo de Profesores"""
        from django.contrib.auth.models import Group
        grupo_profesor, creado = Group.objects.get_or_create(name='Profesores')
        user.groups.add(grupo_profesor)
        
        # Asignar permisos específicos
        from django.contrib.auth.models import Permission
        from django.contrib.contenttypes.models import ContentType
        
        # Obtener todos los permisos del grupo
        for permiso in grupo_profesor.permissions.all():
            user.user_permissions.add(permiso)
        
        # Log de la operación
        print(f"✅ Usuario {user.username} asignado al grupo 'Profesores'")
    
    @property
    def tiene_usuario_activo(self):
        """Verifica si tiene usuario activo"""
        return bool(self.user and self.user.is_active)
    
    @property
    def info_usuario(self):
        """Devuelve información del usuario asociado"""
        if self.user:
            return {
                'username': self.user.username,
                'email': self.email,
                'is_active': self.user.is_active,
                'last_login': self.user.last_login,
                'date_joined': self.user.date_joined,
            }
        return None
    
    # ========== PROPIEDADES Y MÉTODOS ADICIONALES ==========
    
    @property
    def cursos_asignados(self):
        """Devuelve los cursos asignados al profesor"""
        from .models import Curso
        return Curso.objects.filter(
            profesor=self,
            activo=True,
            eliminado=False
        )
    
    @property
    def total_cursos(self):
        """Devuelve el total de cursos asignados"""
        return self.cursos_asignados.count()
    
    @property
    def estado_display(self):
        """Devuelve el estado en formato legible"""
        if self.eliminado:
            return "Eliminado"
        elif self.activo:
            return "Activo"
        else:
            return "Inactivo"
    
    def get_dias_eliminado(self):
        """Devuelve los días que lleva eliminado"""
        if self.fecha_eliminacion:
            delta = timezone.now() - self.fecha_eliminacion
            return delta.days
        return 0
    
    def get_absolute_url(self):
        """URL para ver el detalle del profesor"""
        return reverse('mostrar_profesor', args=[str(self.id)])
    
    def get_restore_url(self):
        """URL para restaurar el profesor"""
        return reverse('restaurar_profesor', args=[str(self.id)])
    
    def get_delete_url(self):
        """URL para eliminar el profesor"""
        return reverse('eliminar_profesor', args=[str(self.id)])
    
    # Métodos relacionados con permisos y usuarios
    def _obtener_nombre_grupo(self):
        return "Profesores"
    
    def get_dashboard_url(self):
        return reverse('dashboard_profesor')
    
    def get_permisos_especificos(self):
        """Permisos específicos para profesores"""
        return [
            'view_own_profile',
            'view_own_cursos',
            'manage_own_cursos',
            'take_attendance',
            'grade_students',
            'view_student_progress',
        ]
        
################################ Personal ###############################################
class Personal(Persona):
    TIPO_PERSONAL = [
        ('SELECCIONAR', 'Seleccionar'),
        ('ADMINISTRATIVO', 'Administrativo'),
        ('COORDINADOR', 'Coordinador'),
        ('SECRETARIA', 'Secretaría'),
        ('LIMPEZA', 'Limpieza'),
        ('SEGURIDAD', 'Seguridad'),
        ('OTRO', 'Otro'),
    ]
    
    tipo = models.CharField(max_length=20, choices=TIPO_PERSONAL, default='SELECCIONAR', verbose_name="Tipo de Personal")
    legajo = models.CharField(max_length=20, unique=True, verbose_name="Legajo", null=True, blank=True)
    fecha_ingreso = models.DateField(verbose_name="Fecha de Ingreso", default=timezone.now)
    fecha_egreso = models.DateField(null=True, blank=True, verbose_name="Fecha de Egreso")
    salario = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="Salario")
    observaciones = models.TextField(blank=True, verbose_name="Observaciones")
    
    objects = PersonalManager()
    
    class Meta:
        verbose_name = "Personal"
        verbose_name_plural = "Personal"
        ordering = ['tipo', 'apellido', 'nombre']
    
    def _obtener_nombre_grupo(self):
        # Grupo base
        grupo_base = "Personal"
        
        # Para administrativos y coordinadores, agregar grupo Administración
        if self.tipo in ['ADMINISTRATIVO', 'COORDINADOR']:
            return f"{grupo_base},Administración"
        
        return grupo_base
    
    def get_dashboard_url(self):
        if self.tipo in ['ADMINISTRATIVO', 'COORDINADOR']:
            return reverse('dashboard_administracion')
        return reverse('dashboard_personal')
    
    # Modificar métodos que usaban self.user_old
    def soft_delete(self, usuario=None):
        """Marca el personal como eliminado y crea backup"""
        try:
            # 1. Primero crear el backup
            from .utils import crear_backup_generico
            crear_backup_generico(
                instancia=self,
                motivo=f"Soft delete solicitado por {usuario.username if usuario else 'sistema'}",
                usuario=usuario
            )
            
            # 2. Luego marcar como eliminado
            self.eliminado = True
            self.eliminado_por = usuario
            self.fecha_eliminacion = timezone.now()
            self.activo = False
            
            # 3. Desactivar usuario asociado si existe (USANDO self.user de Persona)
            if self.user:
                self.desactivar_usuario_sistema(usuario)
            
            self.save()
            
            # 4. Registrar en historial
            HistorialCambios.objects.create(
                modelo='Personal',
                objeto_id=self.id,
                accion='ELIMINAR',
                usuario=usuario,
                descripcion=f"Personal {self.nombre_completo()} ({self.legajo}) marcado como eliminado (soft delete)"
            )
            
        except Exception as e:
            print(f"❌ Error en soft_delete Personal: {e}")
            raise
    
    def restore(self, usuario=None):
        """Restaura un personal eliminado"""
        try:
            self.eliminado = False
            self.eliminado_por = None
            self.fecha_eliminacion = None
            self.activo = True
            
            # Reactivar usuario asociado si existe (USANDO self.user de Persona)
            if self.user:
                self.reactivar_usuario_sistema(usuario)
            
            self.save()
            
            # Registrar en historial
            HistorialCambios.objects.create(
                modelo='Personal',
                objeto_id=self.id,
                accion='RESTAURAR',
                usuario=usuario,
                descripcion=f"Personal {self.nombre_completo()} ({self.legajo}) restaurado"
            )
            
        except Exception as e:
            print(f"❌ Error al restaurar Personal: {e}")
            raise

    def __str__(self):
        return f"{self.nombre_completo()} - {self.get_tipo_display()} ({self.legajo})"
    
    @property
    def antiguedad(self):
        """Calcula la antigüedad en años"""
        from datetime import date
        if self.fecha_ingreso:
            hoy = date.today()
            años = hoy.year - self.fecha_ingreso.year
            if (hoy.month, hoy.day) < (self.fecha_ingreso.month, self.fecha_ingreso.day):
                años -= 1
            return años
        return 0

    @property
    def esta_activo(self):
        """Verifica si el personal está activo"""
        return self.activo and not self.eliminado

    def crear_usuario_sistema(self, usuario=None):
        """Crea un usuario del sistema para el personal"""
        if not self.user:
            try:
                # Generar username único
                base_username = f"{self.nombre.lower()}.{self.apellido.lower()}"
                username = base_username
                counter = 1
                while User.objects.filter(username=username).exists():
                    username = f"{base_username}{counter}"
                    counter += 1
                
                # Crear usuario
                user = User.objects.create_user(
                    username=username,
                    password='temp123',  # Contraseña temporal
                    first_name=self.nombre,
                    last_name=self.apellido,
                    email=self.mail,  # Usando self.mail en lugar de self.email
                    is_active=True
                )
                
                # Asignar grupo según tipo de personal
                if self.tipo in ['ADMINISTRATIVO', 'COORDINADOR']:
                    grupo, created = Group.objects.get_or_create(name='Administración')
                    user.groups.add(grupo)
                
                self.user = user
                self.save()
                
                # Registrar en historial
                HistorialCambios.objects.create(
                    modelo='Personal',
                    objeto_id=self.id,
                    accion='EDITAR',
                    usuario=usuario,
                    descripcion=f"Usuario del sistema creado para {self.nombre_completo()}: {username}"
                )
                
                return user
            except Exception as e:
                print(f"❌ Error al crear usuario: {e}")
                return None
        return self.user  # ✅ Este return debe estar DENTRO del método
    
    
    
######################### Cursos #####################################3
class Curso(models.Model):
    nombre = models.CharField(max_length=100, verbose_name="Nombre")
    dias = models.CharField(max_length=100, verbose_name="Días")
    horario = models.CharField(max_length=100, verbose_name="Horario", null=True, blank=True)
    precio = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    duracion = models.CharField(max_length=50, verbose_name="Duración")
    fecha_inicio = models.DateField(verbose_name="Fecha de Inicio")
    fecha_fin = models.DateField(verbose_name="Fecha de Fin")
    # Nuevos campos para modalidad virtual
    MODALIDAD_CHOICES = [
        ('PRESENCIAL', 'Presencial'),
        ('VIRTUAL', 'Virtual'),
        ('HIBRIDO', 'Híbrido'),
    ]
    
    modalidad = models.CharField(
        max_length=20,
        choices=MODALIDAD_CHOICES,
        default='PRESENCIAL',
        verbose_name="Modalidad"
    )
    
    # Campos específicos para virtual
    plataforma_virtual = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name="Plataforma Virtual"
    )
    
    enlace_clase = models.URLField(
        blank=True,
        null=True,
        verbose_name="Enlace de la Clase"
    )
    
    # Campos para horarios más estructurados
    hora_inicio = models.TimeField(
        blank=True,
        null=True,
        verbose_name="Hora de Inicio"
    )
    
    hora_fin = models.TimeField(
        blank=True,
        null=True,
        verbose_name="Hora de Fin"
    )
    
    # Método para obtener días como lista
    def obtener_dias_lista(self):
        """Convierte el string de días en una lista"""
        if not self.dias:
            return []
        return [dia.strip() for dia in self.dias.split(',')]
    
    # Propiedad para verificar si es virtual
    @property
    def es_virtual(self):
        return self.modalidad in ['VIRTUAL', 'HIBRIDO']
    
    # Método para formato de horario estructurado
    def horario_estructurado(self):
        if self.hora_inicio and self.hora_fin:
            return f"{self.hora_inicio.strftime('%H:%M')} - {self.hora_fin.strftime('%H:%M')}"
        return self.horario or "Horario no definido"
    
        # Relaciones
    profesor = models.ForeignKey(
        Profesor, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        verbose_name="Profesor Asignado",
        related_name='cursos_asignados'
    )
    auxiliar = models.ForeignKey(
        Personal, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        verbose_name="Auxiliar Asignado",
        related_name='cursos_asignados'
    )
    
    # Estado
    activo = models.BooleanField(verbose_name="Activo", default=True)
    
    # Campos para soft delete
    eliminado = models.BooleanField(default=False)
    eliminado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    fecha_eliminacion = models.DateTimeField(null=True, blank=True)
    
    # Campos de auditoría
    fecha_creacion = models.DateTimeField(auto_now_add=True,null=True, blank=True) ##############mmodif)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    objects = CursoManager()
    all_objects = models.Manager()  # Manager que incluye todos
    
    class Meta:
        verbose_name = "Curso"
        verbose_name_plural = "Cursos"
        permissions = [
            ("can_view_courses", "Puede ver cursos"),
            ("can_manage_courses", "Puede gestionar todos los cursos"),
            ("can_view_own_courses", "Puede ver solo sus cursos asignados"),
        ]

    def __str__(self):
        # Verificar si hay información de horario disponible
        if self.dias and self.horario_estructurado() and self.horario_estructurado() != "Horario no definido":
            return f"{self.nombre} - {self.dias} {self.horario_estructurado()}"
        elif self.dias and self.horario:
            return f"{self.nombre} - {self.dias} {self.horario}"
        else:
            return self.nombre
    
    # Método para formato de horario estructurado
    def horario_estructurado(self):
        if self.hora_inicio and self.hora_fin:
            return f"{self.hora_inicio.strftime('%H:%M')} - {self.hora_fin.strftime('%H:%M')}"
        return self.horario or "Horario no definido"
    
    # Método específico para mostrar en formularios (si prefieres mantener __str__ simple)
    def nombre_con_horario(self):
        """Método específico para mostrar nombre con horario en formularios"""
        if self.dias and self.horario_estructurado() and self.horario_estructurado() != "Horario no definido":
            return f"{self.nombre} - {self.dias} {self.horario_estructurado()}"
        elif self.dias and self.horario:
            return f"{self.nombre} - {self.dias} {self.horario}"
        else:
            return f"{self.nombre} - Horario no definido"

    def soft_delete(self, usuario=None):
        """Marca el curso como eliminado y crea backup"""
        try:
            # 1. Primero crear el backup
            from .utils import crear_backup_generico
            crear_backup_generico(
                instancia=self,
                motivo=f"Soft delete solicitado por {usuario.username if usuario else 'sistema'}",
                usuario=usuario
            )
            
            # 2. Luego marcar como eliminado
            self.eliminado = True
            self.eliminado_por = usuario
            self.fecha_eliminacion = timezone.now()
            self.activo = False
            self.save()
            
            # 3. Registrar en historial
            HistorialCambios.objects.create(
                modelo='Curso',
                objeto_id=self.id,
                accion='ELIMINAR',
                usuario=usuario,
                descripcion=f"Curso '{self.nombre}' marcado como eliminado (soft delete)"
            )
            
        except Exception as e:
            print(f"❌ Error en soft_delete Curso: {e}")
            raise

    def restore(self, usuario=None):
        """Restaura un curso eliminado"""
        try:
            self.eliminado = False
            self.eliminado_por = None
            self.fecha_eliminacion = None
            self.activo = True
            self.save()
            
            # Registrar en historial
            HistorialCambios.objects.create(
                modelo='Curso',
                objeto_id=self.id,
                accion='RESTAURAR',
                usuario=usuario,
                descripcion=f"Curso '{self.nombre}' restaurado"
            )
            
        except Exception as e:
            print(f"❌ Error al restaurar Curso: {e}")
            raise

    @property
    def alumnos_inscritos(self):
        """Alumnos actualmente inscritos en el curso"""
        from .models import Inscripcion
        return Alumno.objects.filter(
            inscripcion__curso=self,
            inscripcion__activo=True,
            inscripcion__estado__in=['INSCRIPTO', 'CURSANDO']
        ).distinct()

    @property
    def total_alumnos(self):
        """Total de alumnos inscritos"""
        return self.alumnos_inscritos.count()

    @property
    def esta_activo(self):
        """Verifica si el curso está actualmente activo"""
        from django.utils import timezone
        hoy = timezone.now().date()
        return self.fecha_inicio <= hoy <= self.fecha_fin
    
    

class Alumno(Persona):
    edad = models.IntegerField(
        verbose_name='Edad',
        blank=True,
        null=True,
        editable=False  # ← No aparece en formularios admin
    )
    cursoAlumno = models.ForeignKey(Curso, verbose_name="Curso Asignado", on_delete=models.SET_NULL, null=True, blank=True)
    ultimo_contacto_mora = models.DateTimeField(null=True, blank=True, verbose_name='Último contacto por mora')
    
    objects = AlumnoManager()
    all_objects = models.Manager()  # Manager que incluye todos (incluyendo eliminados)
    
    #calcula edad automaticamente
    def save(self, *args, **kwargs):
        """Calcular edad automáticamente al guardar"""
        if self.fecha_nacimiento:
            today = date.today()
            self.edad = today.year - self.fecha_nacimiento.year - (
                (today.month, today.day) < 
                (self.fecha_nacimiento.month, self.fecha_nacimiento.day)
            )
        else:
            self.edad = None
        super().save(*args, **kwargs)

    def calcular_edad(self):
        """Método para calcular edad en tiempo real (sin guardar)"""
        if self.fecha_nacimiento:
            today = date.today()
            return today.year - self.fecha_nacimiento.year - (
                (today.month, today.day) < 
                (self.fecha_nacimiento.month, self.fecha_nacimiento.day)
            )
        return None

    # Control de duplicacion de datos
    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['nombre', 'apellido', 'dni'],
                name='unique_alumno_nombre_apellido_dni'
            )
        ]
        verbose_name = "Alumno"
        verbose_name_plural = "Alumnos"
        ordering = ['apellido', 'nombre']

    def __str__(self):
        return f"{self.nombre_completo()} | DNI: {self.dni}"

    # PROPIEDADES PARA INSCRIPCIONES
    @property
    def total_inscripciones(self):
        """Total de inscripciones activas del alumno"""
        return self.inscripcion_set.filter(activo=True).count()
    
    @property
    def inscripciones_aprobadas(self):
        """Total de cursos aprobados"""
        return self.inscripcion_set.filter(estado='APROBADO', activo=True).count()
    
    @property
    def inscripciones_cursando(self):
        """Total de cursos en progreso"""
        return self.inscripcion_set.filter(estado='CURSANDO', activo=True).count()
    
    @property
    def inscripciones_inscripto(self):
        """Total de cursos inscritos (pendientes de comenzar)"""
        return self.inscripcion_set.filter(estado='INSCRIPTO', activo=True).count()
    
    @property
    def inscripciones_reprobadas(self):
        """Total de cursos reprobados"""
        return self.inscripcion_set.filter(estado='REPROBADO', activo=True).count()
    
    @property
    def puede_inscribirse(self):
        """Verifica si el alumno puede inscribirse en nuevos cursos"""
        return self.activo and not self.eliminado
    
    @property
    def ultima_inscripcion(self):
        """Última inscripción del alumno"""
        return self.inscripcion_set.filter(activo=True).order_by('-fecha_inscripcion').first()
    
    @property
    def cursos_activos(self):
        """Cursos en los que está actualmente inscrito (CURSANDO o INSCRIPTO)"""
        return Curso.objects.filter(
            inscripcion__alumno=self,
            inscripcion__estado__in=['CURSANDO', 'INSCRIPTO'],
            inscripcion__activo=True
        ).distinct()
        
    # @property
    def curso_actual(self):
    #     """
    #     Retorna el curso actual del alumno basado en su última inscripción activa.
    #     Si no tiene inscripciones activas, devuelve el curso asignado directamente
    #     en el campo 'cursoAlumno' (si existe).
    #     """
    #     # Buscar la última inscripción activa (ordenada por fecha)
        ultima_inscripcion = self.inscripcion_set.filter(activo=True).order_by('-fecha_inscripcion').first()
        if ultima_inscripcion:
            return ultima_inscripcion.curso
     # Fallback: si no hay inscripciones activas, usar cursoAlumno
        return self.cursoAlumno

    def soft_delete(self, usuario=None, motivo="Sin motivo especificado"):
        """Marca el alumno como eliminado y desactiva relaciones"""
        try:  # ← CORREGIDO: Esta línea estaba mal indentada
            # 1. Primero crear el backup - Importamos aquí para evitar circular import
            from .utils import crear_backup_generico
            crear_backup_generico(
                instancia=self,
                motivo=f"Soft delete - {motivo}",
                usuario=usuario
            )
            
            # 2. Desactivar todas las inscripciones activas
            inscripciones_activas = self.inscripcion_set.filter(activo=True)
            for inscripcion in inscripciones_activas:
                inscripcion.activo = False
                inscripcion.save()
                
                # Registrar el cambio en el historial
                HistorialCambios.objects.create(
                    modelo='Inscripcion',
                    objeto_id=inscripcion.id,
                    accion='ELIMINAR',
                    usuario=usuario,
                    descripcion=f"Inscripción desactivada por eliminación del alumno {self.nombre_completo()}"
                )
            
            # 3. Luego marcar como eliminado
            self.eliminado = True
            self.eliminado_por = usuario
            self.fecha_eliminacion = timezone.now()
            self.activo = False
            self.save()
            
            # 4. Registrar en historial
            HistorialCambios.objects.create(
                modelo='Alumno',
                objeto_id=self.id,
                accion='ELIMINAR',
                usuario=usuario,
                descripcion=f"Alumno {self.nombre_completo()} marcado como eliminado (soft delete). {inscripciones_activas.count()} inscripciones desactivadas."
            )
            
        except Exception as e:
            print(f"❌ Error en soft_delete Alumno: {e}")
            raise

    def restore(self, usuario=None):
        """Restaura un alumno eliminado"""
        try:
            self.eliminado = False
            self.eliminado_por = None
            self.fecha_eliminacion = None
            self.activo = True
            self.save()
            
            # Registrar en historial
            HistorialCambios.objects.create(
                modelo='Alumno',
                objeto_id=self.id,
                accion='RESTAURAR',
                usuario=usuario,
                descripcion=f"Alumno {self.nombre_completo()} restaurado"
            )
            
        except Exception as e:
            print(f"❌ Error al restaurar Alumno: {e}")
            raise
    
    def _obtener_nombre_grupo(self):
        return "Alumnos"
    
    # Métodos específicos para alumnos
    def get_dashboard_url(self):
        return reverse('dashboard_alumno')
    
    def get_permisos_especificos(self):
        """Permisos específicos para alumnos"""
        return [
            'view_own_profile',
            'view_own_inscripciones',
            'view_own_certificados',
            'view_own_notas',
        ]
        
class ArchivoCurso(models.Model):
    TIPO_ARCHIVO_CHOICES = [
        ('PROGRAMA', 'Programa de estudios'),
        ('MATERIAL', 'Material didáctico'),
        ('EVALUACION', 'Evaluación'),
        ('CERTIFICADO', 'Certificado'),
        ('OTRO', 'Otro archivo'),
    ]
    
    curso = models.ForeignKey(
        Curso, 
        on_delete=models.CASCADE, 
        related_name='archivos_curso',
        verbose_name="Curso"
    )
    archivo = models.FileField(
        upload_to='cursos/archivos/',
        verbose_name="Archivo"
    )
    tipo = models.CharField(
        max_length=20, 
        choices=TIPO_ARCHIVO_CHOICES,
        default='MATERIAL',
        verbose_name="Tipo de archivo"
    )
    nombre = models.CharField(
        max_length=255, 
        blank=True,
        verbose_name="Nombre del archivo"
    )
    descripcion = models.TextField(
        blank=True,
        verbose_name="Descripción"
    )
    fecha_subida = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha de subida"
    )
    subido_por = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True,
        verbose_name="Subido por"
    )
    
    class Meta:
        verbose_name = "Archivo de Curso"
        verbose_name_plural = "Archivos de Cursos"
        ordering = ['-fecha_subida']
    
    def __str__(self):
        return f"{self.nombre} - {self.curso.nombre}"
    
    def extension(self):
        import os
        return os.path.splitext(self.archivo.name)[1].lower()
    
    def es_imagen(self):
        return self.extension() in ['.jpg', '.jpeg', '.png', '.gif', '.bmp']
    
    def es_pdf(self):
        return self.extension() == '.pdf'
    
    def tamaño_archivo(self):
        try:
            size = self.archivo.size
            if size < 1024:
                return f"{size} B"
            elif size < 1024 * 1024:
                return f"{size / 1024:.1f} KB"
            else:
                return f"{size / (1024 * 1024):.1f} MB"
        except:
            return "Desconocido"
        
# Actualizar las relaciones después de definir Curso
Curso.add_to_class('profesorCurso', models.ForeignKey(Profesor, verbose_name="Profesor", on_delete=models.SET_NULL, null=True, blank=True, related_name='cursos_profesor'))
Curso.add_to_class('auxiliarCurso', models.ForeignKey(Personal, verbose_name="Auxiliar Asignada", on_delete=models.SET_NULL, null=True, blank=True, related_name='cursos_auxiliar'))

############################### MAS ALUMNO ######################################
# Agregar en models.py (en la sección de Alumno o al final del archivo)

class ArchivoAlumno(models.Model):
    TIPO_ARCHIVO_CHOICES = [
        ('FOTO', 'Foto adicional'),
        ('DOCUMENTO', 'Documento'),
        ('CERTIFICADO', 'Certificado'),
        ('OTRO', 'Otro archivo'),
    ]
    
    alumno = models.ForeignKey(
        'Alumno', 
        on_delete=models.CASCADE, 
        related_name='archivos_adicionales',
        verbose_name="Alumno"
    )
    archivo = models.FileField(
        upload_to='alumnos/archivos/',
        verbose_name="Archivo"
    )
    tipo = models.CharField(
        max_length=20, 
        choices=TIPO_ARCHIVO_CHOICES,
        default='DOCUMENTO',
        verbose_name="Tipo de archivo"
    )
    nombre = models.CharField(
        max_length=255, 
        blank=True,
        verbose_name="Nombre del archivo"
    )
    descripcion = models.TextField(
        blank=True,
        verbose_name="Descripción"
    )
    fecha_subida = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha de subida"
    )
    subido_por = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True,
        verbose_name="Subido por"
    )
    
    class Meta:
        verbose_name = "Archivo de Alumno"
        verbose_name_plural = "Archivos de Alumnos"
        ordering = ['-fecha_subida']
        constraints = [
            models.UniqueConstraint(
                fields=['alumno', 'nombre'],
                name='unique_archivo_alumno_nombre'
            )
        ]
    
    def __str__(self):
        return f"{self.nombre} - {self.alumno.nombre_completo()}"
    
    def extension(self):
        import os
        return os.path.splitext(self.archivo.name)[1].lower()
    
    def es_imagen(self):
        return self.extension() in ['.jpg', '.jpeg', '.png', '.gif', '.bmp']
    
    def es_pdf(self):
        return self.extension() == '.pdf'
    
    def nombre_archivo(self):
        import os
        return os.path.basename(self.archivo.name)
    
    def tamaño_archivo(self):
        try:
            size = self.archivo.size
            if size < 1024:
                return f"{size} B"
            elif size < 1024 * 1024:
                return f"{size / 1024:.1f} KB"
            else:
                return f"{size / (1024 * 1024):.1f} MB"
        except:
            return "Desconocido"
        


# class Pago(models.Model):
#     alumnoPago = models.ForeignKey(Alumno, on_delete=models.CASCADE, null=True, blank=True)
#     auxiliar = models.ForeignKey(Personal, on_delete=models.CASCADE, null=True, blank=True) 
#     fecha = models.DateField(verbose_name="Fecha", auto_now_add=True)
   
#     def __str__(self):
#         return f"Pago - {self.fecha}"

# Actualizar Alumno con pagos
#Alumno.add_to_class('pagosAlumno', models.ForeignKey(Pago, on_delete=models.SET_NULL, null=True, blank=True, related_name='alumnos_pago'))

class Examen(models.Model):
    TIPO_CHOICES = [
        ('TEORICO_1', 'Teórico 1'),
        ('TEORICO_2', 'Teórico 2'), 
        ('PRACTICO_1', 'Práctico 1'),
        ('PRACTICO_2', 'Práctico 2'),
        ('RECUPERATORIO_1', 'Recuperatorio 1'),
        ('RECUPERATORIO_2', 'Recuperatorio 2'),
        ('TERCER_EXAMEN', 'Tercer Examen'),
        ('CUARTO_EXAMEN', 'Cuarto Examen'),
    ]
    
    inscripcion = models.ForeignKey('Inscripcion', on_delete=models.CASCADE, related_name='examenes')
    fecha = models.DateField()
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
    nota = models.DecimalField(max_digits=4, decimal_places=2, validators=[MinValueValidator(0), MaxValueValidator(10)])
    observaciones = models.TextField(blank=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_modificacion = models.DateTimeField(auto_now=True)
    incluir_en_promedio: models.BooleanField[bool] = models.BooleanField(default=True, verbose_name="Incluir en promedio")
    
    class Meta:
        unique_together = ['inscripcion', 'tipo']
        verbose_name_plural = "Exámenes"
    
    def __str__(self):
        return f"{self.inscripcion.alumno} - {self.get_tipo_display()} - {self.nota}"
    
######################################3 Inscripcion  ###########################################3
class Inscripcion(models.Model):
    ESTADOS_INSCRIPCION = [
        ('INSCRIPTO', 'Inscripto'),
        ('CURSANDO', 'Cursando'),
        ('APROBADO', 'Aprobado'),
        ('REPROBADO', 'Reprobado'),
        ('ABANDONO', 'Abandonó'),
        ('CANCELADO', 'Cancelado'),
    ]
    
    alumno = models.ForeignKey(Alumno, on_delete=models.CASCADE, verbose_name="Alumno")
    curso = models.ForeignKey(Curso, on_delete=models.CASCADE, verbose_name="Curso")
    fecha_inscripcion = models.DateField(auto_now_add=True, verbose_name="Fecha de Inscripción")
    fecha_inicio = models.DateField(verbose_name="Fecha de Inicio", null=True, blank=True)
    fecha_fin = models.DateField(verbose_name="Fecha de Fin", null=True, blank=True)
    estado = models.CharField(
        max_length=20, 
        choices=ESTADOS_INSCRIPCION, 
        default='INSCRIPTO',
        verbose_name="Estado"
    )
    nota_final = models.DecimalField(
        max_digits=4, 
        decimal_places=2, 
        null=True, 
        blank=True,
        verbose_name="Nota Final"
    )
    costo_inscripcion = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        null=True, 
        blank=True,
        verbose_name="Costo de Inscripción"
    )
    abono_inscripcion = models.BooleanField(
        verbose_name="Abonó Inscripción", 
        default=False
    )
    observaciones = models.TextField(blank=True, verbose_name="Observaciones")
    activo = models.BooleanField(verbose_name="Activo", default=True)
    
    # Campos para auditoría
    creado_por = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name='inscripciones_creadas'
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)
    
    # Campos para soft delete (AGREGAR ESTOS)
    eliminado = models.BooleanField(default=False, verbose_name="Eliminado")
    eliminado_por = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='inscripciones_eliminadas',
        verbose_name="Eliminado por"
    )
    fecha_eliminacion = models.DateTimeField(null=True, blank=True, verbose_name="Fecha de eliminación")

    class Meta:
        verbose_name = "Inscripción"
        verbose_name_plural = "Inscripciones"
        unique_together = ['alumno', 'curso']  # Evitar inscripciones duplicadas
        ordering = ['-fecha_inscripcion']

    def __str__(self):
        return f"{self.alumno} - {self.curso} ({self.estado})"

    def puede_emitir_certificado(self):
        """Verifica si se puede emitir certificado para esta inscripción"""
        return self.estado == 'APROBADO' and self.fecha_fin is not None

    def duracion_curso(self):
        """Calcula la duración del curso en días"""
        if self.fecha_inicio and self.fecha_fin:
            return (self.fecha_fin - self.fecha_inicio).days
        return None

    def soft_delete(self, usuario=None):
        """Soft delete para inscripción"""
        self.activo = False
        self.eliminado = True
        self.eliminado_por = usuario
        self.fecha_eliminacion = timezone.now()
        self.save()
        
        # Registrar en historial de inscripciones
        HistorialCambios.objects.create(
            modelo='Inscripcion',
            objeto_id=self.id,
            accion='ELIMINAR',
            usuario=usuario,
            descripcion=f"Inscripción {self} marcada como eliminada"
        )
        
    def restore(self, usuario=None):
        """Restaurar una inscripción eliminada"""
        self.activo = True
        self.eliminado = False
        self.eliminado_por = None
        self.fecha_eliminacion = None
        self.save()
        
        HistorialCambios.objects.create(
            modelo='Inscripcion',
            objeto_id=self.id,
            accion='RESTAURAR',
            usuario=usuario,
            descripcion=f"Inscripción {self} restaurada"
        )
        
    def promedio(self):
        examenes = Examen.objects.filter(inscripcion=self)
        if examenes.exists():
            return examenes.aggregate(Avg('nota'))['nota__avg']
        return None
    
    def estado_academico(self):
        promedio = self.promedio()
        if promedio is None:
            return 'SIN NOTAS'
        return 'APROBADO' if promedio >= 7 else 'DESAPROBADO'
    
    
# Relación ManyToMany para Curso y Alumno a través de Inscripcion
Curso.add_to_class('alumnoCurso', models.ManyToManyField(Alumno, through=Inscripcion, blank=True, related_name='cursos_inscritos'))

# class DetallePago(models.Model):
#     pagoDetalle = models.ForeignKey(Pago, on_delete=models.CASCADE)
#     cursoDetalle = models.ForeignKey(Curso, on_delete=models.CASCADE)
#     cantidad = models.IntegerField(default=1, validators=[MinValueValidator(1), MaxValueValidator(99)])
#     precio = models.DecimalField(max_digits=10, decimal_places=2)
#     observaciones = models.CharField(max_length=100, verbose_name="Observaciones", null=True, blank=True)
#     precio_total = models.DecimalField(max_digits=10, decimal_places=2, default=0)

#     def save(self, *args, **kwargs):
#         if self.cantidad and self.precio:
#             self.precio_total = self.cantidad * self.precio
#         super().save(*args, **kwargs)

#     def __str__(self):
#         return f"Detalle - {self.cursoDetalle.nombre}"


#############################################3 Cuotas Listado alumnos ####################################
class CuotaAlumno(models.Model):
    MESES = [
        (1, 'Enero'), (2, 'Febrero'), (3, 'Marzo'), (4, 'Abril'),
        (5, 'Mayo'), (6, 'Junio'), (7, 'Julio'), (8, 'Agosto'),
        (9, 'Septiembre'), (10, 'Octubre'), (11, 'Noviembre'), (12, 'Diciembre')
    ]
    
    inscripcion = models.ForeignKey(Inscripcion, on_delete=models.CASCADE, verbose_name="Inscripción")
    mes = models.IntegerField(choices=MESES, verbose_name="Mes")
    año = models.IntegerField(verbose_name="Año")
    monto = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Monto")
    pagada = models.BooleanField(default=False, verbose_name="Pagada")
    fecha_vencimiento = models.DateField(verbose_name="Fecha de Vencimiento")
    fecha_pago = models.DateField(null=True, blank=True, verbose_name="Fecha de Pago")
    observaciones = models.TextField(blank=True, verbose_name="Observaciones")
    
    class Meta:
        verbose_name = "Cuota de Alumno"
        verbose_name_plural = "Cuotas de Alumnos"
        unique_together = ['inscripcion', 'mes', 'año']
        ordering = ['-año', '-mes']

    def __str__(self):
        return f"Cuota {self.get_mes_display()}/{self.año} - {self.inscripcion.alumno}"

    @property
    def esta_vencida(self):
        """Verifica si la cuota está vencida"""
        from django.utils import timezone
        return not self.pagada and self.fecha_vencimiento < timezone.now().date()

class Asistencia(models.Model):
    inscripcion = models.ForeignKey(Inscripcion, on_delete=models.CASCADE, verbose_name="Inscripción")
    fecha = models.DateField(verbose_name="Fecha")
    presente = models.BooleanField(default=True, verbose_name="Presente")
    observaciones = models.TextField(blank=True, verbose_name="Observaciones")
    registrado_por = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Registrado por")
    fecha_registro = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Registro")
    
    class Meta:
        verbose_name = "Asistencia"
        verbose_name_plural = "Asistencias"
        unique_together = ['inscripcion', 'fecha']
        ordering = ['-fecha']

    def __str__(self):
        estado = "Presente" if self.presente else "Ausente"
        return f"Asistencia {self.fecha} - {self.inscripcion.alumno} ({estado})"

#########################################  BACKUP GENERICOS REUTILIZABLES ###########################3
class BackupGenerico(models.Model):
    ESTADOS = [
        ('ACTIVO', 'Activo'),
        ('RESTAURADO', 'Restaurado'),
        ('ELIMINADO', 'Eliminado'),
    ]
    
    modelo = models.CharField(max_length=100, verbose_name="Modelo")
    objeto_id = models.IntegerField(verbose_name="ID del objeto original")
    datos_backup = models.JSONField(verbose_name="Datos de backup")
    fecha_backup = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de backup")
    motivo = models.CharField(max_length=200, verbose_name="Motivo del backup")
    usuario_backup = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        verbose_name="Usuario que realizó el backup"
    )
    estado = models.CharField(
        max_length=20, 
        choices=ESTADOS, 
        default='ACTIVO',
        verbose_name="Estado del backup"
    )
    fecha_restauracion = models.DateTimeField(null=True, blank=True, verbose_name="Fecha de restauración")
    usuario_restauracion = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL,  # ✅ CORREGIDO
        null=True, 
        blank=True,
        related_name='backups_restaurados',
        verbose_name="Usuario que restauró"
    )
    nuevo_objeto_id = models.IntegerField(null=True, blank=True, verbose_name="ID del nuevo objeto restaurado")

    class Meta:
        verbose_name = "Backup Genérico"
        verbose_name_plural = "Backups Genéricos"
        ordering = ['-fecha_backup']

    def __str__(self):
        estado_icon = {
            'ACTIVO': '💾',
            'RESTAURADO': '🔄', 
            'ELIMINADO': '🗑️'
        }
        return f"{estado_icon.get(self.estado, '📁')} Backup {self.modelo} #{self.objeto_id}"

    def get_info_objeto(self):
        """Obtiene información legible del objeto respaldado"""
        return self.datos_backup.get('_metadata', {}).get('representacion_string', 'Objeto desconocido')

class BackupAlumno(models.Model):
    alumno_original = models.ForeignKey(Alumno, on_delete=models.CASCADE, verbose_name="Alumno original")
    datos_backup = models.JSONField(verbose_name="Datos de backup")
    fecha_backup = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de backup")
    motivo = models.CharField(max_length=200, verbose_name="Motivo del backup")
    usuario_backup = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, verbose_name="Usuario")

    class Meta:
        verbose_name = "Backup de Alumno"
        verbose_name_plural = "Backups de Alumnos"
        ordering = ['-fecha_backup']

    def __str__(self):
        return f"Backup de {self.alumno_original.nombre_completo()} - {self.fecha_backup}"
    
##################################################### modelo Certificados ############################################
class Certificado(models.Model):
    inscripcion = models.OneToOneField(
        Inscripcion, 
        on_delete=models.CASCADE,
        verbose_name="Inscripción"
    )
    codigo_certificado = models.CharField(
        max_length=50, 
        unique=True,
        verbose_name="Código de Certificado"
    )
    fecha_emision = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha de Emisión"
    )
    emitido_por = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True,
        verbose_name="Emitido por"
    )
    archivo_pdf = models.FileField(
        upload_to='certificados/%Y/%m/%d/',
        null=True, 
        blank=True,
        verbose_name="Archivo PDF"
    )
    hash_verificacion = models.CharField(
        max_length=64,
        blank=True,
        verbose_name="Hash de Verificación"
    )
    
    class Meta:
        verbose_name = "Certificado"
        verbose_name_plural = "Certificados"
        ordering = ['-fecha_emision']

    def __str__(self):
        return f"Certificado {self.codigo_certificado}"

    def save(self, *args, **kwargs):
        if not self.codigo_certificado:
            # Generar código único: CERT-YYYYMMDD-XXXXX
            from django.utils import timezone
            fecha = timezone.now().strftime('%Y%m%d')
            ultimo_certificado = Certificado.objects.filter(
                codigo_certificado__startswith=f'CERT-{fecha}'
            ).count()
            self.codigo_certificado = f'CERT-{fecha}-{ultimo_certificado + 1:05d}'
        
        if not self.hash_verificacion:
            import hashlib
            texto = f"{self.codigo_certificado}{self.inscripcion_id}{self.fecha_emision}"
            self.hash_verificacion = hashlib.sha256(texto.encode()).hexdigest()
        
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('ver_certificado', kwargs={'codigo': self.codigo_certificado})

    def verificar_autenticidad(self, codigo_verificacion):
        """Verifica la autenticidad del certificado"""
        return self.hash_verificacion == codigo_verificacion

################################### PERMISOS ###############################################333
def crear_grupos_y_permisos():
    """Función para crear grupos y permisos iniciales"""
    
    # Grupo para Profesores
    grupo_profesores, created = Group.objects.get_or_create(name='Profesores')
    
    # Grupo para Administración
    grupo_administracion, created = Group.objects.get_or_create(name='Administración')
    
    # Permisos para Curso
    content_type = ContentType.objects.get_for_model(Curso)
    
    # Profesores pueden ver solo sus cursos
    permiso_ver_propios = Permission.objects.create(
        codename='can_view_own_courses',
        name='Puede ver solo sus cursos asignados',
        content_type=content_type,
    )
    
    # Administración puede gestionar todos los cursos
    permiso_gestionar = Permission.objects.create(
        codename='can_manage_courses',
        name='Puede gestionar todos los cursos',
        content_type=content_type,
    )
    
    grupo_profesores.permissions.add(permiso_ver_propios)
    grupo_administracion.permissions.add(permiso_gestionar)
    
    
########################### GESTOR DE PASSWORD ######################################################


class PasswordChangeLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Usuario")
    changed_at = models.DateTimeField(default=timezone.now, verbose_name="Fecha de cambio")
    changed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, 
                                   related_name='password_changes_made', verbose_name="Cambiado por")
    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name="Dirección IP")
    user_agent = models.TextField(blank=True, verbose_name="User Agent")
    
    class Meta:
        verbose_name = "Registro de cambio de contraseña"
        verbose_name_plural = "Registros de cambios de contraseña"
        ordering = ['-changed_at']
        permissions = [
            ("can_view_password_logs", "Puede ver registros de cambios de contraseña"),
        ]
    
    def __str__(self):
        return f"Cambio de contraseña - {self.user.username} - {self.changed_at.strftime('%d/%m/%Y %H:%M')}"
    


######################################## NOTIFICACIONES  ###############################################

class TipoNotificacion(models.Model):
    nombre = models.CharField(max_length=100)
    codigo = models.CharField(max_length=50, unique=True)
    descripcion = models.TextField()
    prioridad = models.CharField(max_length=20, choices=[
        ('BAJA', 'Baja'),
        ('MEDIA', 'Media'), 
        ('ALTA', 'Alta'),
        ('URGENTE', 'Urgente')
    ])
    color = models.CharField(max_length=20, default='primary')
    icono = models.CharField(max_length=50, default='fa-bell')
    ES_MANUAL = models.BooleanField(default=False, verbose_name="Es Manual")
    PUEDE_ASIGNAR = models.ManyToManyField(
        'Personal', 
        blank=True,
        verbose_name="Pueden Asignar",
        help_text="Tipos de personal que pueden asignar este tipo de notificación"
    )
    
    def __str__(self):
        return f"{self.nombre} {'🔔' if self.ES_MANUAL else '⚙️'}"
    
    class Meta:
        verbose_name_plural = "Tipos de Notificación"
    
    
class NotificacionManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(eliminada=False)
    
    def eliminadas(self):
        """Retorna solo las notificaciones eliminadas"""
        return super().get_queryset().filter(eliminada=True)
    
    def todas(self):
        """Retorna todas las notificaciones (incluyendo eliminadas)"""
        return super().get_queryset()
    

class Notificacion(models.Model):
    # CONSTANTES PARA CHOICES
    PRIORIDAD_CHOICES = (
        ('URGENTE', 'Urgente'),
        ('ALTA', 'Alta'),
        ('MEDIA', 'Media'),
        ('BAJA', 'Baja'),
    )
    
    ESTADO_CHOICES = (
        ('PENDIENTE', 'Pendiente'),
        ('LEIDA', 'Leída'),
        ('REALIZADA', 'Realizada'),
    )
    
    # Campos del modelo...
    usuario_destino = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notificaciones_recibidas'
    )
    
    usuario_origen = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='notificaciones_enviadas'
    )
    
    tipo = models.ForeignKey('TipoNotificacion', on_delete=models.PROTECT)
    titulo = models.CharField(max_length=200)
    mensaje = models.TextField()
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='PENDIENTE')
    prioridad = models.CharField(max_length=20, choices=PRIORIDAD_CHOICES, default='MEDIA')
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_vencimiento = models.DateTimeField(null=True, blank=True)
    fecha_leida = models.DateTimeField(null=True, blank=True)
    fecha_realizado = models.DateTimeField(null=True, blank=True)
    es_manual = models.BooleanField(default=True)  # Nota: solo necesitas un campo es_manual
    
    # Campos para soft delete
    eliminada = models.BooleanField(default=False)
    fecha_eliminacion = models.DateTimeField(null=True, blank=True)
    eliminada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='notificaciones_eliminadas'
    )
    
    # MANAGERS
    objects = NotificacionManager()
    todas = models.Manager()
    
    class Meta:
        verbose_name = 'Notificación'
        verbose_name_plural = 'Notificaciones'
        ordering = ['-fecha_creacion']
    
    def __str__(self):
        origen = self.usuario_origen.get_full_name() if self.usuario_origen else "Sistema"
        destino = self.usuario_destino.get_full_name()
        return f"{self.titulo} ({origen} → {destino})"
    
    def soft_delete(self, usuario=None):
        """Marca la notificación como eliminada (soft delete)"""
        self.eliminada = True
        self.fecha_eliminacion = timezone.now()
        self.eliminada_por = usuario
        self.save()
    
    def restaurar(self):
        """Restaura una notificación eliminada"""
        self.eliminada = False
        self.fecha_eliminacion = None
        self.eliminada_por = None
        self.save()
    
    def delete(self, *args, **kwargs):
        """Override del delete para hacer soft delete por defecto"""
        self.soft_delete(usuario=getattr(self, '_current_user', None))
    
    def hard_delete(self):
        """Eliminación física permanente"""
        super().delete()
        

class HistorialNotificacion(models.Model):
    notificacion = models.ForeignKey(Notificacion, on_delete=models.CASCADE)
    usuario = models.ForeignKey(User, on_delete=models.CASCADE)
    accion = models.CharField(max_length=50)
    fecha_accion = models.DateTimeField(auto_now_add=True)
    observaciones = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-fecha_accion']

class ConfiguracionNotificacion(models.Model):
    usuario = models.ForeignKey(User, on_delete=models.CASCADE)
    tipo_notificacion = models.ForeignKey(TipoNotificacion, on_delete=models.CASCADE)
    activo = models.BooleanField(default=True)
    push = models.BooleanField(default=True)
    email = models.BooleanField(default=False)
    
    class Meta:
        unique_together = ['usuario', 'tipo_notificacion']
        
        
# En models.py (después del modelo Notificacion)

class ObservacionAlumno(models.Model):
    """Observaciones sobre alumnos (profesores, administración, coordinación)"""
    
    TIPO_CHOICES = [
        ('PROFESOR', 'Observación del profesor'),
        ('ADMINISTRACION', 'Observación administrativa'),
        ('COORDINACION', 'Observación del coordinador'),
        ('ASISTENCIA', 'Observación por asistencia'),
        ('ACADEMICO', 'Observación académica'),
        ('COMPORTAMIENTO', 'Observación de comportamiento'),
        ('OTRO', 'Otro tipo'),
    ]
    
    VISIBILIDAD_CHOICES = [
        ('PROFESOR_CURSO', 'Solo profesor del curso'),
        ('PROFESORES_CURSO', 'Todos los profesores del curso'),
        ('ADMINISTRACION', 'Administración y coordinación'),
        ('TODOS', 'Todos los involucrados'),
        ('FUTURO_ALUMNO', 'Futuro: visible para alumno'),
    ]
    
    alumno = models.ForeignKey('Alumno', on_delete=models.CASCADE, verbose_name="Alumno")
    curso = models.ForeignKey('Curso', on_delete=models.CASCADE, verbose_name="Curso", null=True, blank=True)
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, verbose_name="Tipo de observación")
    contenido = models.TextField(verbose_name="Contenido")
    visibilidad = models.CharField(max_length=20, choices=VISIBILIDAD_CHOICES, default='PROFESOR_CURSO')
    
    # Campos de control
    creado_por = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Creado por")
    fecha_creacion = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de creación")
    fecha_modificacion = models.DateTimeField(auto_now=True, verbose_name="Fecha de modificación")
    es_importante = models.BooleanField(default=False, verbose_name="¡Importante!")
    resuelto = models.BooleanField(default=False, verbose_name="Resuelto")
    fecha_resolucion = models.DateTimeField(null=True, blank=True, verbose_name="Fecha de resolución")
    
    # Campos para futura funcionalidad (visible para alumno)
    visible_para_alumno = models.BooleanField(
        default=False, 
        verbose_name="Visible para el alumno",
        help_text="Futuro: el alumno podrá ver esta observación"
    )
    
    # Campos para soft delete
    eliminado = models.BooleanField(default=False)
    eliminado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='observaciones_eliminadas')
    fecha_eliminacion = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        verbose_name = "Observación de Alumno"
        verbose_name_plural = "Observaciones de Alumnos"
        ordering = ['-fecha_creacion']
        permissions = [
            ("view_observaciones_propias", "Puede ver observaciones propias"),
            ("view_observaciones_curso", "Puede ver observaciones de su curso"),
            ("view_all_observaciones", "Puede ver todas las observaciones"),
        ]
    
    def __str__(self):
        return f"Obs: {self.alumno.nombre_completo()} - {self.get_tipo_display()}"
    
    def soft_delete(self, usuario=None):
        """Marca la observación como eliminada"""
        self.eliminado = True
        self.eliminado_por = usuario
        self.fecha_eliminacion = timezone.now()
        self.save()
        
        HistorialCambios.objects.create(
            modelo='ObservacionAlumno',
            objeto_id=self.id,
            accion='ELIMINAR',
            usuario=usuario,
            descripcion=f"Observación eliminada para {self.alumno.nombre_completo()}"
        )
    
    def restaurar(self, usuario=None):
        """Restaura una observación eliminada"""
        self.eliminado = False
        self.eliminado_por = None
        self.fecha_eliminacion = None
        self.save()
        
        HistorialCambios.objects.create(
            modelo='ObservacionAlumno',
            objeto_id=self.id,
            accion='RESTAURAR',
            usuario=usuario,
            descripcion=f"Observación restaurada para {self.alumno.nombre_completo()}"
        )
    
    @property
    def puede_ver_profesor(self, profesor):
        """Verifica si un profesor puede ver esta observación"""
        if self.visibilidad in ['PROFESOR_CURSO', 'PROFESORES_CURSO', 'TODOS']:
            # Profesor del curso puede verla
            return self.curso and self.curso.profesor == profesor
        return False
    
    @property
    def puede_ver_administracion(self, usuario):
        """Verifica si administración/coordinación puede ver"""
        try:
            if hasattr(usuario, 'personal_relacionado'):
                personal = usuario.personal_relacionado
                return personal.tipo in ['ADMINISTRATIVO', 'COORDINADOR']
        except:
            pass
        return False
        


def crear_tipos_notificacion_pagos():
    """Crea los tipos de notificación relacionados con pagos"""
    
    # Tipo para notificaciones automáticas de mora
    tipo_mora, created = TipoNotificacion.objects.get_or_create(
        codigo='MORA_PAGOS',
        defaults={
            'nombre': 'Mora de Pagos',
            'descripcion': 'Notificaciones automáticas de alumnos con pagos en mora',
            'prioridad': 'ALTA',
            'color': 'danger',
            'icono': 'fa-exclamation-triangle',
            'ES_MANUAL': False  # Es automática
        }
    )
    
    # Si se creó, asignar quiénes pueden recibir estas notificaciones
    if created:
        # Asignar a coordinadores y administradores
        coordinadores = Personal.objects.filter(
            tipo__in=['COORDINADOR', 'ADMINISTRADOR'],
            activo=True,
            eliminado=False
        )
        tipo_mora.PUEDE_ASIGNAR.set(coordinadores)
    
    # Tipo para recordatorios de pago
    tipo_recordatorio, _ = TipoNotificacion.objects.get_or_create(
        codigo='RECORDATORIO_PAGO',
        defaults={
            'nombre': 'Recordatorio de Pago',
            'descripcion': 'Recordatorios de pagos próximos a vencer',
            'prioridad': 'MEDIA',
            'color': 'warning',
            'icono': 'fa-calendar-check',
            'ES_MANUAL': False  # Es automática
        }
    )
    
    return tipo_mora, tipo_recordatorio


##############################  AUDITORIA PERMISOS  #######################################


class AuditLog(models.Model):
    """Registro de auditoría para todos los accesos al sistema"""
    
    ACTION_CHOICES = [
        ('ACCESS', 'Acceso a vista'),
        ('CREATE', 'Creación'),
        ('UPDATE', 'Actualización'),
        ('DELETE', 'Eliminación'),
        ('LOGIN', 'Inicio de sesión'),
        ('LOGOUT', 'Cierre de sesión'),
        ('PERMISSION_CHECK', 'Verificación de permiso'),
        ('ROLE_CHECK', 'Verificación de rol'),
    ]
    
    STATUS_CHOICES = [
        ('SUCCESS', 'Éxito'),
        ('FAILURE', 'Fallo'),
        ('WARNING', 'Advertencia'),
    ]
    
    timestamp = models.DateTimeField(auto_now_add=True)
    user = models.CharField(max_length=150)  # Username, puede ser 'anonymous'
    view = models.CharField(max_length=200)  # Nombre de la vista/función
    url = models.CharField(max_length=500)
    method = models.CharField(max_length=10)
    operation_type = models.CharField(max_length=50, choices=ACTION_CHOICES)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    response_code = models.IntegerField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)  # Datos adicionales
    
    class Meta:
        indexes = [
            models.Index(fields=['timestamp']),
            models.Index(fields=['user']),
            models.Index(fields=['status']),
            models.Index(fields=['operation_type']),
        ]
        ordering = ['-timestamp']
    
    def __str__(self):
        return f"{self.timestamp} - {self.user} - {self.view} - {self.status}"


