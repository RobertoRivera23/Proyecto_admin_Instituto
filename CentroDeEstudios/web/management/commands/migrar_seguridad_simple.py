# web/management/commands/migrar_seguridad_simple.py
from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission
from django.db import transaction
from django.contrib.contenttypes.models import ContentType

class Command(BaseCommand):
    help = 'Migración simplificada al sistema de seguridad'
    
    def handle(self, *args, **options):
        self.stdout.write("🚀 INICIANDO MIGRACIÓN SIMPLIFICADA DE SEGURIDAD...")
        
        with transaction.atomic():
            self.crear_permisos_faltantes()
            self.crear_grupos_basicos()
            self.asignar_usuarios_a_grupos()
        
        self.stdout.write("✅ MIGRACIÓN SIMPLIFICADA COMPLETADA")
    
    def crear_permisos_faltantes(self):
        """Crea los permisos personalizados que puedan faltar"""
        try:
            from web.models import Personal, Curso
            content_type_personal = ContentType.objects.get_for_model(Personal)
            content_type_curso = ContentType.objects.get_for_model(Curso)
            
            permisos_a_crear = [
                # Permisos para Personal
                ('can_view_staff', 'Puede ver personal', content_type_personal),
                ('can_add_staff', 'Puede agregar personal', content_type_personal),
                ('can_edit_staff', 'Puede editar personal', content_type_personal),
                ('can_delete_staff', 'Puede eliminar personal', content_type_personal),
                
                # Permisos para Curso
                ('can_view_courses', 'Puede ver cursos', content_type_curso),
                
                # Permisos para sistema
                ('can_view_reports', 'Puede ver reportes', content_type_personal),
                ('can_generate_reports', 'Puede generar reportes', content_type_personal),
                ('can_view_audit_logs', 'Puede ver logs de auditoría', content_type_personal),
            ]
            
            for codename, name, content_type in permisos_a_crear:
                perm, created = Permission.objects.get_or_create(
                    codename=codename,
                    content_type=content_type,
                    defaults={'name': name}
                )
                if created:
                    self.stdout.write(self.style.SUCCESS(f'✅ Creado permiso: {codename}'))
                    
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ Error creando permisos: {e}'))
    
    def crear_grupos_basicos(self):
        """Crea grupos básicos con permisos esenciales"""
        
        grupos_config = {
            'LECTURA': [
                'web.can_view_staff',
                'web.can_view_courses',
                'web.can_view_students',
            ],
            
            'SECRETARIA': [
                'web.can_view_staff',
                'web.can_view_courses', 
                'web.can_view_students',
                'web.can_edit_staff',
                'web.can_manage_students',
                'auth.can_view_users',
            ],
            
            'COORDINADOR': [
                'web.can_view_staff',
                'web.can_edit_staff',
                'web.can_manage_courses',
                'web.can_manage_students',
                'auth.can_view_users',
                'auth.can_edit_users',
                'web.can_view_reports',
            ],
            
            'ADMINISTRADOR': [
                'web.can_manage_staff',
                'web.can_manage_courses',
                'web.can_manage_students',
                'auth.can_view_users',
                'auth.can_edit_users',
                'auth.can_manage_user_accounts',
                'web.can_view_reports',
                'web.can_generate_reports',
                'web.can_view_audit_logs',
            ]
        }
        
        for nombre_grupo, permisos in grupos_config.items():
            grupo, created = Group.objects.get_or_create(name=nombre_grupo)
            grupo.permissions.clear()
            
            permisos_asignados = 0
            for perm_codename in permisos:
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
                self.style.SUCCESS(f'✅ {nombre_grupo}: {permisos_asignados} permisos')
            )
    
    def asignar_usuarios_a_grupos(self):
        """Asigna usuarios a grupos según su rol de personal"""
        try:
            from web.models import Personal
            
            # Mapeo simple de roles a grupos
            mapeo_roles = {
                'SECRETARIA': 'SECRETARIA',
                'COORDINADOR': 'COORDINADOR', 
                'ADMINISTRATIVO': 'ADMINISTRADOR',
                'LIMPEZA': 'LECTURA',
                'SEGURIDAD': 'LECTURA',
                'OTRO': 'LECTURA',
            }
            
            for personal in Personal.objects.filter(eliminado=False, activo=True):
                if personal.user and personal.tipo in mapeo_roles:
                    grupo_nombre = mapeo_roles[personal.tipo]
                    try:
                        grupo = Group.objects.get(name=grupo_nombre)
                        personal.user.groups.clear()
                        personal.user.groups.add(grupo)
                        
                        self.stdout.write(
                            f'✅ {personal.nombre_completo()} ({personal.tipo}) -> {grupo_nombre}'
                        )
                    except Group.DoesNotExist:
                        self.stdout.write(
                            self.style.ERROR(f'❌ Grupo no encontrado: {grupo_nombre}')
                        )
                elif personal.user:
                    self.stdout.write(
                        self.style.WARNING(f'⚠️ {personal.nombre_completo()} ({personal.tipo}): Rol sin mapeo')
                    )
                    
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ Error asignando usuarios: {e}'))