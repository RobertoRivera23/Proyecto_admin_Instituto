# web/management/commands/gestionar_permisos.py
from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType

class Command(BaseCommand):
    help = 'Sistema completo de gestión de permisos'
    
    def add_arguments(self, parser):
        parser.add_argument('--accion', type=str, help='Acción: listar, crear, asignar, quitar, diagnosticar')
        parser.add_argument('--tipo', type=str, help='Tipo: grupo, usuario, permiso')
        parser.add_argument('--nombre', type=str, help='Nombre del grupo/usuario/permiso')
        parser.add_argument('--permisos', type=str, help='Lista de permisos separados por coma')
        parser.add_argument('--grupo', type=str, help='Grupo destino para asignar permisos')
    
    def handle(self, *args, **options):
        accion = options['accion']
        
        if accion == 'listar':
            self.listar_todo()
        elif accion == 'crear_permiso':
            self.crear_permiso_personalizado(options['nombre'])
        elif accion == 'asignar_grupo':
            self.asignar_permisos_grupo(options['grupo'], options['permisos'])
        elif accion == 'asignar_usuario':
            self.asignar_permisos_usuario(options['nombre'], options['permisos'])
        elif accion == 'diagnosticar':
            self.diagnosticar_sistema()
        else:
            self.stdout.write("❌ Acción no válida. Usa: listar, crear, asignar, quitar, diagnosticar")
    
    def listar_todo(self):
        """Lista grupos, usuarios y permisos"""
        self.stdout.write("\n📋 GRUPOS DEL SISTEMA:")
        for grupo in Group.objects.all().order_by('name'):
            self.stdout.write(f"  👥 {grupo.name} ({grupo.permissions.count()} permisos, {grupo.user_set.count()} usuarios)")
            for perm in grupo.permissions.filter(codename__startswith='can_'):
                self.stdout.write(f"    • {perm.codename}")
        
        self.stdout.write("\n🔑 PERMISOS PERSONALIZADOS DISPONIBLES:")
        for perm in Permission.objects.filter(codename__startswith='can_').order_by('codename'):
            self.stdout.write(f"  • {perm.codename} ({perm.content_type.app_label})")
    
    def crear_permiso_personalizado(self, nombre_permiso):
        """Crea un nuevo permiso personalizado"""
        # Determinar content_type según el nombre
        if 'user' in nombre_permiso or 'account' in nombre_permiso:
            ct, _ = ContentType.objects.get_or_create(app_label='auth', model='user')
        else:
            ct, _ = ContentType.objects.get_or_create(app_label='web', model='personal')
        
        # Crear nombre amigable
        nombre_amigable = nombre_permiso.replace('_', ' ').title().replace('Can ', 'Can ')
        
        perm, creado = Permission.objects.get_or_create(
            codename=nombre_permiso,
            content_type=ct,
            defaults={'name': nombre_amigable}
        )
        
        if creado:
            self.stdout.write(f"✅ Permiso creado: {nombre_permiso} en {ct.app_label}")
        else:
            self.stdout.write(f"ℹ️  El permiso {nombre_permiso} ya existe")
    
    def asignar_permisos_grupo(self, nombre_grupo, permisos_str):
        """Asigna permisos a un grupo"""
        try:
            grupo = Group.objects.get(name=nombre_grupo)
            permisos_lista = permisos_str.split(',')
            
            permisos_objs = []
            for codename in permisos_lista:
                try:
                    perm = Permission.objects.get(codename=codename.strip())
                    permisos_objs.append(perm)
                except Permission.DoesNotExist:
                    self.stdout.write(f"⚠️  Permiso no encontrado: {codename}")
            
            grupo.permissions.add(*permisos_objs)
            self.stdout.write(f"✅ {len(permisos_objs)} permisos asignados a {nombre_grupo}")
            
        except Group.DoesNotExist:
            self.stdout.write(f"❌ Grupo no encontrado: {nombre_grupo}")
    
    def asignar_permisos_usuario(self, username, permisos_str):
        """Asigna permisos directamente a un usuario"""
        try:
            user = User.objects.get(username=username)
            permisos_lista = permisos_str.split(',')
            
            permisos_objs = []
            for codename in permisos_lista:
                try:
                    perm = Permission.objects.get(codename=codename.strip())
                    permisos_objs.append(perm)
                except Permission.DoesNotExist:
                    self.stdout.write(f"⚠️  Permiso no encontrado: {codename}")
            
            user.user_permissions.add(*permisos_objs)
            self.stdout.write(f"✅ {len(permisos_objs)} permisos asignados a {username}")
            
        except User.DoesNotExist:
            self.stdout.write(f"❌ Usuario no encontrado: {username}")
    
    def diagnosticar_sistema(self):
        """Diagnóstico completo del sistema de permisos"""
        self.stdout.write("\n" + "="*60)
        self.stdout.write("🔍 DIAGNÓSTICO DEL SISTEMA DE PERMISOS")
        self.stdout.write("="*60)
        
        # 1. Grupos base
        self.stdout.write("\n👥 GRUPOS BASE REQUERIDOS:")
        grupos_requeridos = ['Personal', 'Administración', 'Alumnos', 'Profesores']
        for nombre in grupos_requeridos:
            try:
                grupo = Group.objects.get(name=nombre)
                self.stdout.write(f"  ✅ {nombre}: {grupo.permissions.count()} permisos, {grupo.user_set.count()} usuarios")
            except Group.DoesNotExist:
                self.stdout.write(f"  ❌ {nombre}: NO EXISTE")
        
        # 2. Grupos específicos
        self.stdout.write("\n🎯 GRUPOS ESPECÍFICOS DE PERSONAL:")
        grupos_personal = ['Coordinador', 'Administrativo', 'Secretaría', 'Consulta']
        for nombre in grupos_personal:
            try:
                grupo = Group.objects.get(name=nombre)
                self.stdout.write(f"  👤 {nombre}:")
                self.stdout.write(f"    Permisos: {grupo.permissions.count()}")
                self.stdout.write(f"    Usuarios: {[u.username for u in grupo.user_set.all()]}")
            except Group.DoesNotExist:
                self.stdout.write(f"  ❌ {nombre}: NO EXISTE")
                
                
# En una migración de datos o management command
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from web.models import Curso, ObservacionAlumno

def crear_grupo_profesores():
    grupo, creado = Group.objects.get_or_create(name='Profesores')
    
    # Permisos para cursos (solo ver propios)
    content_type = ContentType.objects.get_for_model(Curso)
    permiso_ver_propios, _ = Permission.objects.get_or_create(
        codename='can_view_own_courses',
        name='Puede ver solo sus cursos asignados',
        content_type=content_type,
    )
    
    # Permisos para observaciones
    content_type_obs = ContentType.objects.get_for_model(ObservacionAlumno)
    permiso_ver_obs_curso, _ = Permission.objects.get_or_create(
        codename='view_observaciones_curso',
        name='Puede ver observaciones de su curso',
        content_type=content_type_obs,
    )
    
    permiso_add_obs, _ = Permission.objects.get_or_create(
        codename='add_observacionalumno',
        name='Puede agregar observaciones',
        content_type=content_type_obs,
    )
    
    # Asignar permisos al grupo
    grupo.permissions.add(permiso_ver_propios, permiso_ver_obs_curso, permiso_add_obs)
    
    return grupo