from django.contrib.auth.models import Permission, Group
from django.contrib.contenttypes.models import ContentType
from django.db.models import Q

class PermisosSistema:
    """Clase para gestionar permisos del sistema - VERSIÓN MEJORADA"""
    
    @staticmethod
    def crear_grupos_y_permisos():
        """Crea todos los grupos y permisos necesarios para el nuevo sistema"""
        print("🔧 Creando grupos y permisos del sistema...")
        
        # 1. CREAR GRUPOS BASE
        grupos_base = ['Alumnos', 'Profesores', 'Personal', 'Administración']
        for nombre in grupos_base:
            Group.objects.get_or_create(name=nombre)
            print(f"✅ Grupo base creado: {nombre}")
        
        # 2. CREAR GRUPOS ESPECÍFICOS DE PERSONAL
        grupos_personal = ['Administrativo', 'Coordinador', 'Secretaría', 'Consulta']
        for nombre in grupos_personal:
            Group.objects.get_or_create(name=nombre)
            print(f"✅ Grupo específico creado: {nombre}")
        
        # 3. ASIGNAR PERMISOS A GRUPOS BASE
        
        # Grupo Alumnos: permisos limitados
        grupo_alumnos = Group.objects.get(name='Alumnos')
        permisos_alumno = Permission.objects.filter(
            codename__in=[
                'view_alumno',      # Ver su propio perfil
                'change_alumno',    # Modificar su propio perfil
                'view_curso',       # Ver cursos disponibles
                'view_inscripcion', # Ver sus inscripciones
            ]
        )
        grupo_alumnos.permissions.set(permisos_alumno)
        print("✅ Permisos asignados a: Alumnos")
        
        # Grupo Profesores: permisos de docente
        grupo_profesores = Group.objects.get(name='Profesores')
        permisos_profesor = Permission.objects.filter(
            codename__in=[
                'view_profesor',
                'change_profesor',
                'view_curso',
                'change_curso',
                'view_alumno',
                'view_inscripcion',
                'add_asistencia',
                'change_asistencia',
                'view_asistencia',
            ]
        )
        grupo_profesores.permissions.set(permisos_profesor)
        print("✅ Permisos asignados a: Profesores")
        
        # Grupo Personal: permisos básicos de visualización
        grupo_personal = Group.objects.get(name='Personal')
        permisos_personal = Permission.objects.filter(
            Q(codename__startswith='view_')
        )
        grupo_personal.permissions.set(permisos_personal)
        print("✅ Permisos asignados a: Personal")
        
        # 4. ASIGNAR PERMISOS A GRUPOS ESPECÍFICOS DE PERSONAL
        
        # Grupo Administración: permisos de gestión (compatibilidad)
        grupo_admin = Group.objects.get(name='Administración')
        permisos_admin = Permission.objects.filter(
            codename__in=[
                'can_manage_staff',     # Permisos personalizados
                'can_add_staff',
                'can_edit_staff',
                'can_delete_staff',
                'can_view_staff',
            ]
        )
        grupo_admin.permissions.set(permisos_admin)
        print("✅ Permisos asignados a: Administración (compatibilidad)")
        
        # Grupo Administrativo: permisos de gestión de personal
        grupo_administrativo = Group.objects.get(name='Administrativo')
        permisos_administrativo = Permission.objects.filter(
            codename__in=[
                'can_manage_staff',     # Gestión de personal
                'can_add_staff',
                'can_edit_staff',
                'can_delete_staff',
                'can_view_staff',
                'web.can_view_audit_logs',  # Puede ver auditoría
            ]
        )
        grupo_administrativo.permissions.set(permisos_administrativo)
        print("✅ Permisos asignados a: Administrativo")
        
        # Grupo Coordinador: permisos COMPLETOS incluyendo gestión de usuarios
        grupo_coordinador = Group.objects.get(name='Coordinador')
        permisos_coordinador = Permission.objects.filter(
            codename__in=[
                # Permisos de gestión de personal
                'can_manage_staff',
                'can_add_staff',
                'can_edit_staff',
                'can_delete_staff',
                'can_view_staff',
                
                # Permisos EXCLUSIVOS de gestión de usuarios
                'can_manage_user_accounts',
                'can_create_users',
                'can_disable_users',
                'can_reset_passwords',
                
                # Permisos de auditoría
                'can_view_audit_logs',
                'can_export_audit_logs',
                
                # Permisos de otros módulos
                'cursos.can_manage_courses',
                'cursos.can_manage_students',
                'finanzas.can_manage_payments',
                'finanzas.can_view_reports',
            ]
        )
        grupo_coordinador.permissions.set(permisos_coordinador)
        print("✅ Permisos asignados a: Coordinador (con privilegios exclusivos)")
        
        # Grupo Secretaría: permisos básicos
        grupo_secretaria = Group.objects.get(name='Secretaría')
        permisos_secretaria = Permission.objects.filter(
            codename__in=[
                'can_view_staff',
                'cursos.can_manage_students',
                'add_inscripcion',
                'change_inscripcion',
                'view_inscripcion',
            ]
        )
        grupo_secretaria.permissions.set(permisos_secretaria)
        print("✅ Permisos asignados a: Secretaría")
        
        # Grupo Consulta: solo visualización
        grupo_consulta = Group.objects.get(name='Consulta')
        permisos_consulta = Permission.objects.filter(
            codename__in=[
                'view_alumno',
                'view_profesor',
                'view_curso',
                'view_inscripcion',
            ]
        )
        grupo_consulta.permissions.set(permisos_consulta)
        print("✅ Permisos asignados a: Consulta")
        
        print("\n🎉 SISTEMA DE PERMISOS CONFIGURADO CORRECTAMENTE")
        print("="*60)
        
        # 5. MOSTRAR RESUMEN
        print("\n📊 RESUMEN DE PERMISOS POR GRUPO:")
        grupos = Group.objects.all().order_by('name')
        for grupo in grupos:
            print(f"\n  👥 {grupo.name}:")
            for perm in grupo.permissions.all()[:5]:  # Mostrar primeros 5
                print(f"    • {perm.codename}")
            if grupo.permissions.count() > 5:
                print(f"    ... y {grupo.permissions.count() - 5} más")

# JERARQUÍA DE ROLES (de mayor a menor privilegio)
ROLE_HIERARCHY = {
    'SUPERUSUARIO': 100,
    'COORDINADOR': 90,      # ← ¡Coordinador es el más alto en Personal!
    'ADMINISTRATIVO': 80,
    'SECRETARIA': 70,
    'DOCENTE': 60,
    'CONSULTA': 50,
    'INACTIVO': 0
}

# PERMISOS DEL SISTEMA (codename: descripción)
SYSTEM_PERMISSIONS = {
    # Gestión de Personal
    'can_manage_staff': 'Gestión completa de personal',
    'can_add_staff': 'Agregar nuevo personal',
    'can_edit_staff': 'Editar personal existente',
    'can_delete_staff': 'Eliminar personal',
    'can_view_staff': 'Ver información de personal',
    
    # Gestión de Usuarios
    'can_manage_user_accounts': 'Gestión de cuentas de usuario',
    'can_create_users': 'Crear usuarios del sistema',
    'can_disable_users': 'Deshabilitar usuarios',
    'can_reset_passwords': 'Restablecer contraseñas',
    
    # Auditoría
    'can_view_audit_logs': 'Ver registros de auditoría',
    'can_export_audit_logs': 'Exportar registros de auditoría',
    
    # Otros módulos
    'cursos.can_manage_courses': 'Gestión de cursos',
    'cursos.can_manage_students': 'Gestión de estudiantes',
    'finanzas.can_manage_payments': 'Gestión de pagos',
    'finanzas.can_view_reports': 'Ver reportes financieros',
}

# ACCESOS POR DEFECTO SEGÚN ROL (actualizado)
ROLE_DEFAULT_PERMISSIONS = {
    'COORDINADOR': [  # ← Coordinador tiene todo
        'can_manage_staff',
        'can_manage_user_accounts',
        'can_view_audit_logs',
        'cursos.can_manage_courses',
        'finanzas.can_manage_payments',
    ],
    'ADMINISTRATIVO': [
        'can_manage_staff',
        'can_view_staff',
        'cursos.can_manage_courses',
        'finanzas.can_manage_payments',
    ],
    'SECRETARIA': [
        'can_view_staff',
        'cursos.can_manage_students',
    ],
    'DOCENTE': [],
    'CONSULTA': [],
}

# POLÍTICAS DE SEGURIDAD
SECURITY_POLICIES = {
    'allow_superuser_override': False,
    'require_2fa_for_admin': True,
    'log_all_access_attempts': True,
    'max_login_attempts': 5,
    'session_timeout': 3600,
}

# Función para verificar permisos de un usuario
def usuario_tiene_permiso(user, permiso_codename):
    """
    Verifica si un usuario tiene un permiso específico
    """
    # Superusuarios tienen todos los permisos
    if user.is_superuser:
        return True
    
    # Verificar permiso directamente
    if user.has_perm(permiso_codename):
        return True
    
    # Verificar por grupos
    for grupo in user.groups.all():
        if grupo.permissions.filter(codename=permiso_codename).exists():
            return True
    
    return False

# Función para obtener permisos de un usuario
def obtener_permisos_usuario(user):
    """
    Retorna todos los permisos de un usuario (directos y por grupos)
    """
    permisos = set()
    
    # Permisos directos
    for perm in user.user_permissions.all():
        permisos.add(perm.codename)
    
    # Permisos por grupos
    for grupo in user.groups.all():
        for perm in grupo.permissions.all():
            permisos.add(perm.codename)
    
    return list(permisos)