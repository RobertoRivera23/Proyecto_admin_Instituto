from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission
from web.models import Personal, Alumno, Profesor

class Command(BaseCommand):
    help = 'Configura permisos del sistema manteniendo estructura existente'
    
    def handle(self, *args, **options):
        self.stdout.write('🔧 Configurando sistema de permisos...')
        
        # 1. CREAR GRUPOS BASE (si no existen)
        grupos_base = ['Personal', 'Administración', 'Alumnos', 'Profesores']
        for nombre in grupos_base:
            Group.objects.get_or_create(name=nombre)
        
        # 2. CREAR GRUPOS ESPECÍFICOS
        grupos_especificos = ['Administrativo', 'Coordinador', 'Secretaría', 'Consulta']
        for nombre in grupos_especificos:
            Group.objects.get_or_create(name=nombre)
        
        # 3. PERMISOS para TODOS en 'Administración' (compatibilidad)
        permisos_administracion = [
            'can_manage_staff',      # Gestión de personal
            'can_add_staff',
            'can_edit_staff', 
            'can_delete_staff',
            'can_view_staff',
        ]
        
        grupo_admin = Group.objects.get(name='Administración')
        for perm_codename in permisos_administracion:
            try:
                perm = Permission.objects.get(codename=perm_codename)
                grupo_admin.permissions.add(perm)
            except:
                pass
        
        # 4. PERMISOS EXCLUSIVOS para COORDINADORES
        permisos_coordinador_exclusivos = [
            'can_manage_user_accounts',  # Solo coordinadores
            'can_create_users',
            'can_disable_users',
            'can_reset_passwords',
            'can_view_audit_logs',
        ]
        
        grupo_coord = Group.objects.get(name='Coordinador')
        for perm_codename in permisos_coordinador_exclusivos:
            try:
                perm = Permission.objects.get(codename=perm_codename)
                grupo_coord.permissions.add(perm)
                self.stdout.write(f'   🎯 Permiso exclusivo a Coordinador: {perm_codename}')
            except:
                pass
        
        # 5. ACTUALIZAR USUARIOS EXISTENTES
        self.stdout.write('👥 Actualizando usuarios...')
        
        # Personal
        for personal in Personal.objects.filter(user__isnull=False):
            try:
                user = personal.user
                
                # Mantener grupos de Alumno/Profesor si los tiene
                grupos_actuales = list(user.groups.all())
                
                # Aplicar nueva configuración
                if personal.tipo == 'ADMINISTRATIVO':
                    user.groups.add(Group.objects.get(name='Administrativo'))
                    user.groups.add(Group.objects.get(name='Administración'))
                    user.groups.add(Group.objects.get(name='Personal'))
                    self.stdout.write(f'   👔 {personal.nombre_completo()} -> Administrativo')
                    
                elif personal.tipo == 'COORDINADOR':
                    user.groups.add(Group.objects.get(name='Coordinador'))
                    user.groups.add(Group.objects.get(name='Administración'))
                    user.groups.add(Group.objects.get(name='Personal'))
                    self.stdout.write(f'   🎯 {personal.nombre_completo()} -> Coordinador (con privilegios)')
                    
                elif personal.tipo == 'SECRETARIA':
                    user.groups.add(Group.objects.get(name='Secretaría'))
                    user.groups.add(Group.objects.get(name='Personal'))
                    self.stdout.write(f'   📁 {personal.nombre_completo()} -> Secretaría')
                    
                else:
                    user.groups.add(Group.objects.get(name='Consulta'))
                    user.groups.add(Group.objects.get(name='Personal'))
                    self.stdout.write(f'   👁️ {personal.nombre_completo()} -> Consulta')
                
                user.is_staff = personal.tipo in ['ADMINISTRATIVO', 'COORDINADOR', 'SECRETARIA']
                user.save()
                
            except Exception as e:
                self.stdout.write(f'   ❌ Error con {personal.nombre_completo()}: {e}')
        
        # 6. MANTENER Alumnos y Profesores
        self.stdout.write('👨‍🎓 Manteniendo alumnos y profesores...')
        
        # Alumnos (ya deberían tener su grupo por la señal)
        for alumno in Alumno.objects.filter(user__isnull=False, puede_acceder_sistema=True):
            if alumno.user:
                grupo_alumno = Group.objects.get(name='Alumnos')
                alumno.user.groups.add(grupo_alumno)
                alumno.user.is_staff = False
                alumno.user.save()
        
        # Profesores
        for profesor in Profesor.objects.filter(user__isnull=False, puede_acceder_sistema=True):
            if profesor.user:
                grupo_profesor = Group.objects.get(name='Profesores')
                profesor.user.groups.add(grupo_profesor)
                profesor.user.is_staff = True  # Profesores pueden acceder al admin
                profesor.user.save()
        
        self.stdout.write('')
        self.stdout.write('✅ SISTEMA CONFIGURADO')
        self.stdout.write('')
        self.stdout.write('📊 ESTRUCTURA DE PERMISOS:')
        self.stdout.write('   🎯 COORDINADOR: Gestión de personal + Gestión de usuarios (exclusivo)')
        self.stdout.write('   👔 ADMINISTRATIVO: Gestión de personal')
        self.stdout.write('   📁 SECRETARÍA: Acceso básico')
        self.stdout.write('   👨‍🎓 ALUMNOS: Grupo Alumnos (sin cambios)')
        self.stdout.write('   👨‍🏫 PROFESORES: Grupo Profesores (sin cambios)')