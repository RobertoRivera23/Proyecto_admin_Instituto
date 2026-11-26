# web/management/commands/migrar_seguridad_hibrida.py
from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission
from django.db import transaction

class Command(BaseCommand):
    help = 'Migración al sistema de seguridad híbrido (Roles + Permisos)'
    
    def handle(self, *args, **options):
        self.stdout.write("🚀 INICIANDO MIGRACIÓN SEGURIDAD HÍBRIDA...")
        
        with transaction.atomic():
            self.crear_permisos_faltantes()
            self.crear_grupos_hibridos()
            self.asignar_permisos_por_rol()
            self.verificar_configuracion()
        
        self.stdout.write("✅ MIGRACIÓN HÍBRIDA COMPLETADA")
    
    def crear_permisos_faltantes(self):
        """Crea los permisos personalizados que puedan faltar"""
        from django.contrib.contenttypes.models import ContentType
        from web.models import Personal, Curso
        
        content_type_personal = ContentType.objects.get_for_model(Personal)
        content_type_curso = ContentType.objects.get_for_model(Curso)
        content_type_user = ContentType.objects.get_for_model(Permission)  # Para permisos de auth
        
        permisos_a_crear = [
            # Permisos para Personal
            ('can_view_staff', 'Puede ver personal', content_type_personal),
            ('can_add_staff', 'Puede agregar personal', content_type_personal),
            ('can_edit_staff', 'Puede editar personal', content_type_personal),
            ('can_delete_staff', 'Puede eliminar personal', content_type_personal),
            
            # Permisos para Curso
            ('can_view_courses', 'Puede ver cursos', content_type_curso),
            
            # Permisos para sistema (usaremos content_type_personal para permisos genéricos)
            ('can_view_reports', 'Puede ver reportes', content_type_personal),
            ('can_generate_reports', 'Puede generar reportes', content_type_personal),
            ('can_view_audit_logs', 'Puede ver logs de auditoría', content_type_personal),
            ('can_view_security_logs', 'Puede ver logs de seguridad', content_type_personal),
            ('can_manage_system', 'Puede gestionar sistema', content_type_personal),
        ]
        
        for codename, name, content_type in permisos_a_crear:
            perm, created = Permission.objects.get_or_create(
                codename=codename,
                content_type=content_type,
                defaults={'name': name}
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'✅ Creado permiso: {codename}'))
    
    def crear_grupos_hibridos(self):
        """Crea grupos basados en la matriz de seguridad"""
        from web.security_matrix import MATRIZ_SEGURIDAD
        
        for nivel, config in MATRIZ_SEGURIDAD.items():
            # Crear grupo principal
            grupo, created = Group.objects.get_or_create(name=nivel)
            grupo.permissions.clear()
            
            # Asignar permisos del nivel
            permisos_asignados = 0
            for perm_codename in config['permisos']:
                try:
                    app_label, codename = perm_codename.split('.', 1)
                    perm = Permission.objects.get(
                        content_type__app_label=app_label,
                        codename=codename
                    )
                    grupo.permissions.add(perm)
                    permisos_asignados += 1
                except Permission.DoesNotExist:
                    self.stdout.write(
                        self.style.WARNING(f'⚠️ Permiso no encontrado: {perm_codename}')
                    )
            
            self.stdout.write(
                self.style.SUCCESS(f'✅ {nivel}: {len(config["roles"])} roles, {permisos_asignados} permisos')
            )
    
    def asignar_permisos_por_rol(self):
        """Asigna usuarios a grupos según su rol de personal"""
        from web.models import Personal
        
        for personal in Personal.objects.filter(eliminado=False, activo=True):
            if personal.user:
                # Encontrar grupo basado en rol
                grupo_encontrado = None
                for nivel, config in MATRIZ_SEGURIDAD.items():
                    if personal.tipo in config['roles']:
                        grupo_encontrado = nivel
                        break
                
                if grupo_encontrado:
                    try:
                        grupo = Group.objects.get(name=grupo_encontrado)
                        personal.user.groups.clear()
                        personal.user.groups.add(grupo)
                        
                        self.stdout.write(
                            f'✅ {personal.nombre_completo()} ({personal.tipo}) -> {grupo_encontrado}'
                        )
                    except Group.DoesNotExist:
                        self.stdout.write(
                            self.style.ERROR(f'❌ Grupo no encontrado: {grupo_encontrado}')
                        )
                else:
                    self.stdout.write(
                        self.style.WARNING(f'⚠️ {personal.nombre_completo()} ({personal.tipo}): Rol sin grupo asignado')
                    )
    
    def verificar_configuracion(self):
        """Verifica la consistencia del sistema de seguridad"""
        self.stdout.write("\n🔍 VERIFICACIÓN DE CONFIGURACIÓN:")
        
        from web.models import Personal
        from django.contrib.auth.models import User
        
        for user in User.objects.filter(is_active=True):
            try:
                personal = user.personal
                grupos = [g.name for g in user.groups.all()]
                
                self.stdout.write(f"\n👤 {user.username} ({personal.tipo}):")
                self.stdout.write(f"   Grupos: {grupos}")
                
                # Verificar que el grupo coincida con el rol
                grupo_esperado = None
                for nivel, config in MATRIZ_SEGURIDAD.items():
                    if personal.tipo in config['roles']:
                        grupo_esperado = nivel
                        break
                
                if grupo_esperado and grupo_esperado in grupos:
                    self.stdout.write(self.style.SUCCESS(f"   ✅ Grupo correcto"))
                else:
                    self.stdout.write(self.style.ERROR(f"   ❌ Grupo incorrecto. Esperado: {grupo_esperado}"))
                    
            except Personal.DoesNotExist:
                self.stdout.write(f"\n👤 {user.username}: ❌ Sin perfil de personal")