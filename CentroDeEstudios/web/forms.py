import os
from django import forms
from django.core.exceptions import ValidationError
from django.forms.utils import ErrorList, timezone
from .models import(
    ArchivoAlumno, Personal, Profesor, Alumno, Curso, Inscripcion,
    Asistencia, CuotaAlumno, Notificacion, TipoNotificacion, ArchivoCurso, User
)
from datetime import *
from django.forms import inlineformset_factory
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import get_user_model
from facturacion.models import Pago, DetallePago

################################## REGISTRO ##############################################

class AsignarUsuarioForm(forms.Form):
    """Formulario para asignar usuario a una persona"""
    
    crear_usuario = forms.BooleanField(
        required=False,
        initial=False,
        label="Crear usuario del sistema",
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    forzar_sin_email = forms.BooleanField(
        required=False,
        initial=False,
        label="Crear usuario sin email",
        help_text="Generará un email temporal",
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    enviar_credenciales = forms.BooleanField(
        required=False,
        initial=True,
        label="Enviar credenciales por email",
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    def __init__(self, *args, **kwargs):
        self.persona = kwargs.pop('persona', None)
        super().__init__(*args, **kwargs)
        
        if self.persona and self.persona.user:
            self.fields['crear_usuario'].initial = True
            self.fields['crear_usuario'].disabled = True
            self.fields['crear_usuario'].help_text = "Ya tiene usuario asignado"

class GestionUsuariosForm(forms.ModelForm):
    """Formulario para gestión masiva de usuarios"""
    
    class Meta:
        model = User
        fields = ['is_active', 'groups']
        widgets = {
            'groups': forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

class FiltroUsuariosForm(forms.Form):
    """Filtro para buscar usuarios"""
    
    TIPO_CHOICES = [
        ('', 'Todos'),
        ('ALUMNO', 'Alumnos'),
        ('PROFESOR', 'Profesores'),
        ('PERSONAL', 'Personal'),
        ('ADMIN', 'Administración'),
    ]
    
    tipo = forms.ChoiceField(
        choices=TIPO_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    activo = forms.ChoiceField(
        choices=[('', 'Todos'), ('SI', 'Activos'), ('NO', 'Inactivos')],
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Buscar por nombre, email, username...'
        })
    )


class RegistroUsuarioForm(UserCreationForm):
    email = forms.EmailField(required=True)
    first_name = forms.CharField(required=True, label='Nombre')
    last_name = forms.CharField(required=True, label='Apellido')

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'password1', 'password2']

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        if commit:
            user.save()
        return user


class EditarUsuarioForm(forms.ModelForm):
    """Formulario para editar usuarios - Solo coordinadores pueden cambiar username"""
    
    # Campo para verificar que solo coordinadores pueden editar username
    es_coordinador = forms.BooleanField(
        required=False,
        widget=forms.HiddenInput(),
        initial=False
    )
    
    class Meta:
        model = User
        fields = ['username', 'email', 'first_name', 'last_name', 'is_active']
        
    def __init__(self, *args, **kwargs):
        self.usuario_editor = kwargs.pop('usuario_editor', None)
        super().__init__(*args, **kwargs)
        
        # Verificar si el usuario editor es coordinador
        es_coord = self.es_coordinador_funcion(self.usuario_editor)
        
        # Si NO es coordinador, hacer el campo username de solo lectura
        if not es_coord:
            self.fields['username'].disabled = True
            self.fields['username'].help_text = "⚠️ Solo los coordinadores pueden modificar el nombre de usuario"
            self.fields['username'].widget.attrs['readonly'] = True
        
        # Establecer el valor oculto para coordinador
        self.fields['es_coordinador'].initial = es_coord
        
    def es_coordinador_funcion(self, user):
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
    
    def clean_username(self):
        """Validación adicional para username"""
        username = self.cleaned_data.get('username')
        es_coordinador = self.cleaned_data.get('es_coordinador')
        
        # Si no es coordinador y está intentando cambiar el username
        if not es_coordinador and self.instance.username != username:
            raise forms.ValidationError(
                "Solo los coordinadores pueden modificar el nombre de usuario"
            )
        
        # Verificar que el username no exista (excepto para este mismo usuario)
        if User.objects.filter(username=username).exclude(id=self.instance.id).exists():
            raise forms.ValidationError("Este nombre de usuario ya está en uso")
        
        return username
################################## ALUMNOS ##############################################
class AltaAlumnoForm(forms.ModelForm):
    class Meta:
        model = Alumno
        fields = '__all__'
        exclude = [
            'edad', 
            'fecha_creacion', 
            'fecha_eliminacion', 
            'eliminado_por',
            'eliminado'
        ]
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ingrese el nombre'}),
            'apellido': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ingrese el apellido'}),
            'dni': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ingrese el DNI'}),
            'fecha_nacimiento': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'sexo': forms.Select(attrs={'class': 'form-control'}),
            'direccion': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Ingrese la dirección'}),
            'telefono': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ingrese el teléfono'}),
            'telefono_contacto': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Teléfono de contacto'}),
            'mail': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'ejemplo@correo.com'}),
            'foto': forms.FileInput(attrs={'class': 'form-control'}),
            'activo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['foto'].required = False
    
    def clean(self):
        cleaned_data = super().clean()
        nombre = cleaned_data.get('nombre')
        apellido = cleaned_data.get('apellido')
        dni = cleaned_data.get('dni')
        
        # Solo validar si tenemos todos los datos necesarios
        if nombre and apellido and dni:
            try:
                # Usar exists() directamente sin mantener el queryset abierto
                if self.instance and self.instance.pk:
                    existe = Alumno.objects.filter(
                        nombre=nombre,
                        apellido=apellido,
                        dni=dni
                    ).exclude(pk=self.instance.pk).exists()
                else:
                    existe = Alumno.objects.filter(
                        nombre=nombre,
                        apellido=apellido,
                        dni=dni
                    ).exists()
                
                if existe:
                    raise forms.ValidationError(
                        "❌ Ya existe un alumno con el mismo nombre, apellido y DNI. "
                        "Por favor, verifica los datos ingresados."
                    )
            except Exception as e:
                # En caso de error de base de datos, no bloquear el formulario
                print(f"Error en validación de alumno: {e}")
        
        return cleaned_data

class EditarAlumnoForm(forms.ModelForm):
    # Mantener el campo foto pero hacerlo opcional
    foto = forms.ImageField(
        required=False,
        widget=forms.FileInput(attrs={'class': 'form-control'}),
        label="Cambiar imagen"
    )
    
    class Meta:
        model = Alumno
        fields = ['nombre', 'apellido', 'dni', 'fecha_nacimiento', 'sexo', 
                 'direccion', 'telefono', 'telefono_contacto', 'mail', 'foto', 'activo']
        widgets = {
            'fecha_nacimiento': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Hacer que todos los campos sean opcionales excepto los esenciales
        self.fields['foto'].required = False

    def save(self, commit=True):
        instance = super().save(commit=False)
    
    #Solo actualizar la foto si se proporcionó una nueva y es diferente de la actual
        nueva_foto = self.cleaned_data.get('foto')
    
    # Verificar si es un nuevo archivo (no la instancia actual)
        if nueva_foto and hasattr(nueva_foto, 'name') and nueva_foto != instance.foto:
            # Eliminar la imagen anterior si no es la por defecto
            if instance.foto and instance.foto.name != 'imagenes_bd/foto_por_defecto.png':
                instance.foto.delete(save=False)
            instance.foto = nueva_foto
    
        if commit:
            instance.save()
    
        return instance
    


class ArchivoAlumnoForm(forms.ModelForm):
    class Meta:
        model = ArchivoAlumno
        fields = ['archivo', 'tipo', 'nombre', 'descripcion']
        widgets = {
            'archivo': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': '.jpg,.jpeg,.png,.gif,.pdf,.doc,.docx'
            }),
            'tipo': forms.Select(attrs={'class': 'form-control'}),
            'nombre': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nombre descriptivo del archivo'
            }),
            'descripcion': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Descripción opcional del archivo'
            }),
        }
        labels = {
            'archivo': 'Seleccionar archivo',
            'tipo': 'Tipo de archivo',
            'nombre': 'Nombre para mostrar',
            'descripcion': 'Descripción'
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['nombre'].required = False
    
    def clean_archivo(self):
        archivo = self.cleaned_data.get('archivo')
        if archivo:
            # Validar tamaño máximo (10MB)
            max_size = 10 * 1024 * 1024
            if archivo.size > max_size:
                raise forms.ValidationError("El archivo no puede ser mayor a 10MB")
            
            # Validar extensiones
            extensiones_permitidas = ['.jpg', '.jpeg', '.png', '.gif', '.pdf', '.doc', '.docx']
            import os
            ext = os.path.splitext(archivo.name)[1].lower()
            if ext not in extensiones_permitidas:
                raise forms.ValidationError(
                    f"Solo se permiten archivos: {', '.join(extensiones_permitidas)}"
                )
        
        return archivo
    
    def clean(self):
        cleaned_data = super().clean()
        archivo = cleaned_data.get('archivo')
        nombre = cleaned_data.get('nombre')
        
        # Si no se proporciona nombre, usar el nombre del archivo
        if archivo and not nombre:
            cleaned_data['nombre'] = archivo.name
        
        return cleaned_data


################################## PROFESORES ##############################################

class AltaProfesorForm(forms.ModelForm):
    # Campos para gestión de usuario
    crear_usuario_sistema = forms.BooleanField(
        required=False,
        initial=False,
        label='Crear usuario del sistema',
        help_text='Crear un usuario para que pueda acceder al sistema como profesor'
    )
    
    username_personalizado = forms.CharField(
        required=False,
        max_length=150,
        label='Nombre de usuario personalizado',
        help_text='Dejar en blanco para usar DNI como nombre de usuario'
    )
    
    generar_password_aleatoria = forms.BooleanField(
        required=False,
        initial=True,
        label='Generar contraseña aleatoria',
        help_text='Se generará una contraseña aleatoria segura'
    )
    
    password_personalizada = forms.CharField(
        required=False,
        widget=forms.PasswordInput(render_value=True),
        label='Contraseña personalizada',
        help_text='Si no se especifica, se generará una aleatoria',
        min_length=8
    )
    
    class Meta:
        model = Profesor
        fields = '__all__'
        exclude = [
            'fecha_creacion', 
            'fecha_eliminacion', 
            'eliminado_por',
            'eliminado',
            'user',                # Excluimos el campo user del formulario base
            'puede_acceder_sistema'
        ]
        widgets = {
            'fecha_nacimiento': forms.DateInput(attrs={'type': 'date'}),
            'direccion': forms.Textarea(attrs={'rows': 2}),
            'observaciones': forms.Textarea(attrs={'rows': 3}),
        }
        labels = {
            'nombre': 'Nombre *',
            'apellido': 'Apellido *',
            'dni': 'DNI *',
            'mail': 'Correo electrónico',
            'telefono': 'Teléfono principal',
            'telefono_contacto': 'Teléfono de contacto (alternativo)',
            'cuit': 'CUIT/CUIL',
            'cbu': 'CBU',
            'entidad': 'Entidad bancaria',
            'activo': 'Profesor activo',
            'foto': 'Foto de perfil',
        }
        help_texts = {
            'dni': 'Sin puntos ni espacios',
            'cuit': 'Formato: 20-12345678-9',
            'cbu': '22 dígitos',
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Si estamos editando y el profesor ya tiene usuario asociado
        if self.instance and self.instance.pk and self.instance.user:
            # Deshabilitamos y ocultamos los campos de creación de usuario
            self.fields['crear_usuario_sistema'].initial = True
            self.fields['crear_usuario_sistema'].label = 'Usuario existente asociado'
            self.fields['crear_usuario_sistema'].help_text = f'Usuario actual: {self.instance.user.username}'
            self.fields['crear_usuario_sistema'].disabled = True
            self.fields['crear_usuario_sistema'].widget = forms.HiddenInput()
            
            # Ocultamos completamente los campos de creación
            self.fields['username_personalizado'].widget = forms.HiddenInput()
            self.fields['generar_password_aleatoria'].widget = forms.HiddenInput()
            self.fields['password_personalizada'].widget = forms.HiddenInput()
        else:
            # En creación, marcamos por defecto la generación de contraseña aleatoria
            self.fields['generar_password_aleatoria'].initial = True
    
    def clean(self):
        cleaned_data = super().clean()
        
        # Solo validar si se está intentando crear un usuario
        crear_usuario = cleaned_data.get('crear_usuario_sistema')
        
        # Si el profesor ya tiene usuario, no validamos nada de usuario
        if self.instance and self.instance.pk and self.instance.user:
            return cleaned_data
        
        # Validaciones para creación de usuario
        if crear_usuario:
            password_personalizada = cleaned_data.get('password_personalizada')
            generar_aleatoria = cleaned_data.get('generar_password_aleatoria', False)
            
            # Si no se genera aleatoria y no se proporciona contraseña personalizada -> error
            if not generar_aleatoria and not password_personalizada:
                raise forms.ValidationError(
                    "Debe especificar una contraseña personalizada o marcar 'Generar contraseña aleatoria'"
                )
            
            # Validar longitud de contraseña personalizada
            if password_personalizada and len(password_personalizada) < 8:
                raise forms.ValidationError(
                    "La contraseña personalizada debe tener al menos 8 caracteres"
                )
        
        return cleaned_data
    
    def save(self, commit=True):
        # Guardar primero el profesor (sin usuario aún)
        profesor = super().save(commit=False)
        
        # Procesar creación de usuario si corresponde
        crear_usuario = self.cleaned_data.get('crear_usuario_sistema')
        
        # Si ya tiene usuario, solo actualizamos email si cambió
        if profesor.pk and profesor.user:
            if profesor.mail and profesor.user.email != profesor.mail:
                profesor.user.email = profesor.mail
                profesor.user.save()
            if commit:
                profesor.save()
            return profesor
        
        # Si no tiene usuario y se pide crear
        if crear_usuario:
            # Determinar username
            username = self.cleaned_data.get('username_personalizado')
            if not username:
                username = profesor.dni  # Usar DNI como base
            
            # Asegurar username único
            original_username = username
            counter = 1
            while User.objects.filter(username=username).exists():
                username = f"{original_username}{counter}"
                counter += 1
            
            # Determinar contraseña
            password_personalizada = self.cleaned_data.get('password_personalizada')
            generar_aleatoria = self.cleaned_data.get('generar_password_aleatoria', True)
            
            if password_personalizada:
                password = password_personalizada
            elif generar_aleatoria:
                password = get_random_string(12)
            else:
                # Por defecto, aleatoria
                password = get_random_string(12)
            
            # Crear usuario
            user = User.objects.create_user(
                username=username,
                password=password,
                email=profesor.mail or '',
                first_name=profesor.nombre,
                last_name=profesor.apellido,
                is_active=True
            )
            
            # Asignar al grupo Profesores (debe existir el grupo)
            grupo_profesor, _ = Group.objects.get_or_create(name='Profesores')
            user.groups.add(grupo_profesor)
            
            # Asociar al profesor
            profesor.user = user
            profesor.puede_acceder_sistema = True
            
            # Guardar la contraseña temporal en el objeto para mostrarla en la vista
            user._password_temp = password
        
        if commit:
            profesor.save()
        
        return profesor
    
from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone
from .models import Examen, ObservacionAlumno, Asistencia

class ExamenForm(forms.ModelForm):
    class Meta:
        model = Examen
        fields = ['tipo', 'nota', 'observaciones']
        widgets = {
            'tipo': forms.Select(attrs={'class': 'form-control'}),
            'nota': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.1',
                'min': '0',
                'max': '10'
            }),
            'observaciones': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3
            }),
        }
    
    def clean_nota(self):
        nota = self.cleaned_data.get('nota')
        if nota is not None and (nota < 0 or nota > 10):
            raise ValidationError('La nota debe estar entre 0 y 10')
        return nota

class ObservacionForm(forms.ModelForm):
    class Meta:
        model = ObservacionAlumno
        fields = ['tipo', 'contenido', 'es_importante', 'visibilidad']
        widgets = {
            'tipo': forms.Select(attrs={'class': 'form-control'}),
            'contenido': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Describe la observación detalladamente...'
            }),
            'es_importante': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'visibilidad': forms.Select(attrs={'class': 'form-control'}),
        }
        labels = {
            'es_importante': '¡Marcar como importante!',
            'visibilidad': 'Quién puede ver esta observación',
        }

class AsistenciaForm(forms.ModelForm):
    fecha = forms.DateField(
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control',
            'max': timezone.now().date().isoformat()
        }),
        initial=timezone.now().date
    )
    
    class Meta:
        model = Asistencia
        fields = ['presente', 'observaciones']
        widgets = {
            'presente': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'observaciones': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Observaciones sobre la asistencia...'
            }),
        }

class EditarPerfilProfesorForm(forms.ModelForm):
    """Formulario para que el profesor edite solo ciertos campos"""
    class Meta:
        model = Profesor  # Asegúrate de importar el modelo
        fields = ['telefono', 'mail', 'direccion', 'foto']
        widgets = {
            'telefono': forms.TextInput(attrs={'class': 'form-control'}),
            'mail': forms.EmailInput(attrs={'class': 'form-control'}),
            'direccion': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'foto': forms.FileInput(attrs={'class': 'form-control'}),
        }
        
        
# web/forms_profesores.py
from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone
from .models import Examen, ObservacionAlumno, Asistencia

class ExamenForm(forms.ModelForm):
    class Meta:
        model = Examen
        fields = ['tipo', 'nota', 'observaciones']
        widgets = {
            'tipo': forms.Select(attrs={'class': 'form-control'}),
            'nota': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.1',
                'min': '0',
                'max': '10'
            }),
            'observaciones': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3
            }),
        }
    
    def clean_nota(self):
        nota = self.cleaned_data.get('nota')
        if nota is not None and (nota < 0 or nota > 10):
            raise ValidationError('La nota debe estar entre 0 y 10')
        return nota

class ObservacionForm(forms.ModelForm):
    class Meta:
        model = ObservacionAlumno
        fields = ['tipo', 'contenido', 'es_importante', 'visibilidad']
        widgets = {
            'tipo': forms.Select(attrs={'class': 'form-control'}),
            'contenido': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Describe la observación detalladamente...'
            }),
            'es_importante': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'visibilidad': forms.Select(attrs={'class': 'form-control'}),
        }
        labels = {
            'es_importante': '¡Marcar como importante!',
            'visibilidad': 'Quién puede ver esta observación',
        }

class AsistenciaForm(forms.ModelForm):
    fecha = forms.DateField(
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control',
            'max': timezone.now().date().isoformat()
        }),
        initial=timezone.now().date
    )
    
    class Meta:
        model = Asistencia
        fields = ['presente', 'observaciones']
        widgets = {
            'presente': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'observaciones': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Observaciones sobre la asistencia...'
            }),
        }

class EditarPerfilProfesorForm(forms.ModelForm):
    """Formulario para que el profesor edite solo ciertos campos"""
    class Meta:
        model = Profesor  # Asegúrate de importar el modelo
        fields = ['telefono', 'mail', 'direccion', 'foto']
        widgets = {
            'telefono': forms.TextInput(attrs={'class': 'form-control'}),
            'mail': forms.EmailInput(attrs={'class': 'form-control'}),
            'direccion': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'foto': forms.FileInput(attrs={'class': 'form-control'}),
        }

################################## CURSOS ##############################################

class AltaCursoForm(forms.ModelForm):
    class Meta:
        model = Curso
        fields = [
            'nombre', 
            'dias', 
            'horario',
            'precio', 
            'duracion', 
            'fecha_inicio', 
            'fecha_fin', 
            'profesor', 
            'auxiliar', 
            'activo'
        ]
        widgets = {
            'fecha_inicio': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'fecha_fin': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombre del curso'}),
            'dias': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Lunes, Miércoles, Viernes'}),
            'horario': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: 18:00 - 20:00'}),
            'precio': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'duracion': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: 3 meses'}),
            'profesor': forms.Select(attrs={'class': 'form-control'}),
            'auxiliar': forms.Select(attrs={'class': 'form-control'}),
            'activo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        help_texts = {
            'dias': 'Ingrese los días separados por comas. Ej: Lunes, Miércoles, Viernes',
            'horario': 'Formato: HH:MM - HH:MM. Ej: 18:00 - 20:00',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Filtrar solo profesores activos
        self.fields['profesor'].queryset = Profesor.objects.filter(activo=True, eliminado=False)
        
        # Filtrar solo personal administrativo/secretaría activo
        self.fields['auxiliar'].queryset = Personal.objects.filter(
            activo=True, 
            eliminado=False,
            tipo__in=['ADMINISTRATIVO', 'SECRETARIA', 'COORDINADOR']
        )

    def clean(self):
        cleaned_data = super().clean()
        profesor = cleaned_data.get('profesor')
        dias = cleaned_data.get('dias')
        horario = cleaned_data.get('horario')
        fecha_inicio = cleaned_data.get('fecha_inicio')
        fecha_fin = cleaned_data.get('fecha_fin')
        
        # Si estamos editando un curso existente, obtenemos la instancia
        instance = getattr(self, 'instance', None)
        
        # Validar que fecha_fin sea mayor o igual a fecha_inicio
        if fecha_inicio and fecha_fin and fecha_fin < fecha_inicio:
            self.add_error('fecha_fin', '❌ La fecha de fin no puede ser anterior a la fecha de inicio.')
        
        # Validar superposición de horarios Y fechas
        if profesor and dias and horario and fecha_inicio and fecha_fin:
            try:
                self.validar_disponibilidad_profesor(
                    profesor, dias, horario, fecha_inicio, fecha_fin, instance
                )
            except ValidationError as e:
                self.add_error('profesor', e)
        
        return cleaned_data

    def validar_disponibilidad_profesor(self, profesor, dias_nuevo, horario_nuevo, 
                                       fecha_inicio_nuevo, fecha_fin_nuevo, curso_actual=None):
        """
        Valida que el profesor no tenga otro curso que se superponga en:
        1. Rango de fechas (fecha_inicio - fecha_fin)
        2. Días de la semana
        3. Horario
        """
        # Obtener cursos activos del profesor (excluyendo el curso actual si estamos editando)
        cursos_profesor = Curso.objects.filter(
            profesor=profesor,
            activo=True,
            eliminado=False
        )
        
        # Si estamos editando, excluir el curso actual
        if curso_actual and curso_actual.pk:
            cursos_profesor = cursos_profesor.exclude(pk=curso_actual.pk)
        
        # Normalizar datos para comparación
        dias_nuevo_normalizados = self.normalizar_dias(dias_nuevo)
        horario_nuevo_normalizado = self.normalizar_horario(horario_nuevo)
        
        for curso_existente in cursos_profesor:
            # 1. Primero verificar superposición de fechas
            if self.fechas_se_superponen(
                fecha_inicio_nuevo, fecha_fin_nuevo,
                curso_existente.fecha_inicio, curso_existente.fecha_fin
            ):
                # 2. Si hay superposición de fechas, verificar superposición de días
                dias_existente_normalizados = self.normalizar_dias(curso_existente.dias)
                dias_comunes = dias_nuevo_normalizados.intersection(dias_existente_normalizados)
                
                if dias_comunes:
                    # 3. Si hay superposición de días, verificar superposición de horarios
                    horario_existente_normalizado = self.normalizar_horario(curso_existente.horario)
                    
                    if self.horarios_se_superponen(horario_nuevo_normalizado, horario_existente_normalizado):
                        raise ValidationError(
                            f"❌ El profesor {profesor.nombre_completo()} ya tiene asignado el curso "
                            f"'{curso_existente.nombre}' que se superpone en:\n"
                            f"• Fechas: {curso_existente.fecha_inicio} al {curso_existente.fecha_fin}\n"
                            f"• Días: {curso_existente.dias}\n"
                            f"• Horario: {curso_existente.horario}\n\n"
                            f"Por favor, seleccione otro horario, días o rango de fechas diferentes."
                        )
    
    def fechas_se_superponen(self, fecha_inicio1, fecha_fin1, fecha_inicio2, fecha_fin2):
        """
        Verifica si dos rangos de fechas se superponen.
        Dos rangos se superponen si:
        - fecha_inicio1 <= fecha_fin2 Y fecha_inicio2 <= fecha_fin1
        """
        return (fecha_inicio1 <= fecha_fin2) and (fecha_inicio2 <= fecha_fin1)
    
    def normalizar_dias(self, dias_str):
        """
        Normaliza los días a un conjunto estandarizado para comparación
        """
        if not dias_str:
            return set()
        
        # Mapeo de variaciones comunes de días
        mapeo_dias = {
            'lun': 'lunes', 'lunes': 'lunes',
            'mar': 'martes', 'martes': 'martes', 
            'mier': 'miércoles', 'miercoles': 'miércoles', 'miércoles': 'miércoles',
            'jue': 'jueves', 'jueves': 'jueves',
            'vie': 'viernes', 'viernes': 'viernes',
            'sab': 'sábado', 'sabado': 'sábado', 'sábado': 'sábado',
            'dom': 'domingo', 'domingo': 'domingo'
        }
        
        dias = dias_str.lower().replace(',', ' ').replace(';', ' ').replace('y', ' ').split()
        dias_normalizados = set()
        
        for dia in dias:
            dia_limpio = dia.strip()
            # Buscar coincidencia en el mapeo
            for clave, valor in mapeo_dias.items():
                if clave in dia_limpio:
                    dias_normalizados.add(valor)
                    break
            else:
                # Si no encuentra en el mapeo, usar el día original
                dias_normalizados.add(dia_limpio)
        
        return dias_normalizados

    def normalizar_horario(self, horario_str):
        """
        Normaliza el horario para comparación
        Retorna una tupla (hora_inicio, hora_fin) en formato datetime.time
        """
        if not horario_str:
            return (None, None)
        
        try:
            # Patrones comunes de horarios
            if ' - ' in horario_str:
                partes = horario_str.split(' - ')
            elif ' a ' in horario_str:
                partes = horario_str.split(' a ')
            elif '-' in horario_str:
                partes = horario_str.split('-')
            else:
                partes = [horario_str.strip()]
            
            if len(partes) >= 2:
                hora_inicio_str = partes[0].strip()
                hora_fin_str = partes[1].strip()
                
                # Convertir a objetos time
                from datetime import datetime
                
                # Manejar formatos con y sin minutos
                formatos = ['%H:%M', '%H:%M:%S', '%H']
                hora_inicio = None
                hora_fin = None
                
                for formato in formatos:
                    try:
                        hora_inicio = datetime.strptime(hora_inicio_str, formato).time()
                        break
                    except ValueError:
                        continue
                
                for formato in formatos:
                    try:
                        hora_fin = datetime.strptime(hora_fin_str, formato).time()
                        break
                    except ValueError:
                        continue
                
                if hora_inicio and hora_fin:
                    return (hora_inicio, hora_fin)
        
        except (ValueError, IndexError):
            pass
        
        return (None, None)

    def horarios_se_superponen(self, horario1, horario2):
        """
        Verifica si dos horarios se superponen
        """
        hora_inicio1, hora_fin1 = horario1
        hora_inicio2, hora_fin2 = horario2
        
        # Si no se pueden determinar los horarios, asumir que no hay superposición
        if None in [hora_inicio1, hora_fin1, hora_inicio2, hora_fin2]:
            return False
        
        # Dos horarios se superponen si:
        # hora_inicio1 < hora_fin2 Y hora_inicio2 < hora_fin1
        return (hora_inicio1 < hora_fin2 and hora_inicio2 < hora_fin1) 
    
   
class ArchivoCursoForm(forms.ModelForm):
    class Meta:
        model = ArchivoCurso
        fields = ['archivo', 'tipo', 'nombre', 'descripcion']
        widgets = {
            'archivo': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': '.jpg,.jpeg,.png,.gif,.pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx'
            }),
            'tipo': forms.Select(attrs={'class': 'form-control'}),
            'nombre': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nombre descriptivo del archivo'
            }),
            'descripcion': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Descripción opcional del archivo'
            }),
        }
        labels = {
            'archivo': 'Seleccionar archivo',
            'tipo': 'Tipo de archivo',
            'nombre': 'Nombre para mostrar',
            'descripcion': 'Descripción'
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['nombre'].required = False
    
    def clean_archivo(self):
        archivo = self.cleaned_data.get('archivo')
        if archivo:
            # Validar tamaño máximo (10MB)
            max_size = 10 * 1024 * 1024
            if archivo.size > max_size:
                raise forms.ValidationError("El archivo no puede ser mayor a 10MB")
            
            # Validar extensiones
            extensiones_permitidas = ['.jpg', '.jpeg', '.png', '.gif', '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx']
            import os
            ext = os.path.splitext(archivo.name)[1].lower()
            if ext not in extensiones_permitidas:
                raise forms.ValidationError(
                    f"Solo se permiten archivos: {', '.join(extensiones_permitidas)}"
                )
        
        return archivo
    
    def clean(self):
        cleaned_data = super().clean()
        archivo = cleaned_data.get('archivo')
        nombre = cleaned_data.get('nombre')
        
        # Si no se proporciona nombre, usar el nombre del archivo
        if archivo and not nombre:
            cleaned_data['nombre'] = archivo.name
        
        return cleaned_data
    
    
################################## PERSONAL ##############################################
class AltaPersonalForm(forms.ModelForm):
    """Form para crear nuevo personal - versión simplificada"""
    class Meta:
        model = Personal
        fields = '__all__'
        widgets = {
            'tipo': forms.Select(attrs={'class': 'form-control'}),
            'legajo': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: ADM-001'}),
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ingrese el nombre'}),
            'apellido': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ingrese el apellido'}),
            'dni': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ingrese el DNI'}),
            'fecha_nacimiento': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'telefono': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ingrese el teléfono'}),
            'mail': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'ejemplo@correo.com'}),
            'direccion': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Ingrese la dirección'}),
            'fecha_ingreso': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'fecha_egreso': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'salario': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': '0.00'}),
            'observaciones': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Observaciones adicionales'}),
            'activo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

class PersonalForm(forms.ModelForm):
    """Form completo para Personal con creación de usuario"""
    crear_usuario = forms.BooleanField(
        required=False,
        initial=False,
        label="Crear usuario del sistema",
        help_text="Si se marca, se creará un usuario para que acceda al sistema",
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    class Meta:
        model = Personal
        fields = [
            'tipo', 'legajo', 'nombre', 'apellido', 'dni', 
            'fecha_nacimiento', 'telefono', 'mail', 'direccion',
            'fecha_ingreso', 'salario', 'observaciones', 'foto', 'crear_usuario'
        ]
        widgets = {
            'tipo': forms.Select(attrs={'class': 'form-control'}),
            'legajo': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: ADM-001'}),
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ingrese el nombre'}),
            'apellido': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ingrese el apellido'}),
            'dni': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ingrese el DNI'}),
            'fecha_nacimiento': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'telefono': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ingrese el teléfono'}),
            'mail': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'ejemplo@correo.com'}),
            'direccion': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Ingrese la dirección'}),
            'fecha_ingreso': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'salario': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': '0.00'}),
            'observaciones': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Observaciones adicionales'}),
            'foto': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*'
            }),
        }
        labels = {
            'dni': 'DNI',
            'fecha_nacimiento': 'Fecha de Nacimiento',
            'fecha_ingreso': 'Fecha de Ingreso',
            'mail': 'Email',
            'foto': 'Foto de Perfil',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Hacer el campo foto opcional y agregar help text
        self.fields['foto'].required = False
        self.fields['foto'].help_text = 'Formatos soportados: JPG, PNG, GIF. Tamaño máximo: 5MB'
        
        # Si estamos editando y ya tiene foto, mostrar preview
        if self.instance and self.instance.pk and self.instance.foto:
            self.fields['foto'].help_text += '<br><small class="text-muted">Selecciona una nueva imagen para reemplazar la actual.</small>'

    def clean_legajo(self):
        legajo = self.cleaned_data.get('legajo')
        if Personal.objects.filter(legajo=legajo).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("❌ Este legajo ya está en uso.")
        return legajo

    def clean_dni(self):
        dni = self.cleaned_data.get('dni')
        if Personal.objects.filter(dni=dni).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("❌ Este DNI ya está registrado.")
        return dni

    def clean_foto(self):
        foto = self.cleaned_data.get('foto')
        if foto:
            # Validar tamaño del archivo (5MB máximo)
            if foto.size > 5 * 1024 * 1024:  # 5MB
                raise forms.ValidationError("❌ La imagen no puede superar los 5MB.")
            
            # Validar tipo de archivo
            valid_extensions = ['.jpg', '.jpeg', '.png', '.gif']
            ext = os.path.splitext(foto.name)[1].lower()
            if ext not in valid_extensions:
                raise forms.ValidationError("❌ Formato no soportado. Use JPG, PNG o GIF.")
        
        return foto

class PersonalEditForm(PersonalForm):
    """Form para edición que incluye campo de activo"""
    class Meta(PersonalForm.Meta):
        fields = PersonalForm.Meta.fields + ['activo']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['crear_usuario'].help_text = "Si se marca y no tiene usuario, se creará uno"

class PersonalFilterForm(forms.Form):
    TIPO_FILTER = [('', 'Todos los tipos')] + Personal.TIPO_PERSONAL
    ESTADO_FILTER = [
        ('', 'Todos los estados'),
        ('ACTIVO', 'Activos'),
        ('INACTIVO', 'Inactivos'),
    ]
    
    tipo = forms.ChoiceField(
        choices=TIPO_FILTER,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    estado = forms.ChoiceField(
        choices=ESTADO_FILTER,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Buscar por nombre, apellido, legajo...'
        })
    )
################################## GESTION DE PERMISOS  ##############################################
from django import forms
from django.contrib.auth.models import Permission
from django.db.models import Q

class AsignarPermisosForm(forms.Form):
    """Form para asignar permisos a usuarios del personal"""
    
    GRUPOS_PERMISOS = [
        ('ADMINISTRADOR', 'Administrador - Acceso completo al sistema'),
        ('COORDINADOR', 'Coordinador - Gestión académica y reportes'),
        ('SECRETARIA', 'Secretaría - Gestión de alumnos y cursos'),
        ('PROFESOR', 'Profesor - Gestión de sus cursos y alumnos'),
        ('CONSULTA', 'Solo consulta - Ver información sin modificar'),
    ]
    
    grupo = forms.ChoiceField(
        choices=GRUPOS_PERMISOS,
        required=True,
        widget=forms.Select(attrs={'class': 'form-control'}),
        label="Nivel de Acceso"
    )
    
    permisos_especiales = forms.ModelMultipleChoiceField(
        queryset=Permission.objects.filter(
            Q(codename__startswith='add_') | 
            Q(codename__startswith='change_') | 
            Q(codename__startswith='delete_') |
            Q(codename__startswith='view_')
        ).exclude(
            content_type__app_label__in=['auth', 'contenttypes', 'sessions', 'admin']
        ),
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}),
        label="Permisos Especiales Adicionales"
    )

class CambiarPasswordForm(forms.Form):
    """Form para cambiar contraseña de usuarios del sistema"""
    nueva_password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        min_length=8,
        label="Nueva Contraseña"
    )
    confirmar_password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        label="Confirmar Contraseña"
    )
    
    def clean(self):
        cleaned_data = super().clean()
        nueva_password = cleaned_data.get('nueva_password')
        confirmar_password = cleaned_data.get('confirmar_password')
        
        if nueva_password and confirmar_password:
            if nueva_password != confirmar_password:
                raise forms.ValidationError("❌ Las contraseñas no coinciden.")
            
            # Validaciones de seguridad adicionales
            if len(nueva_password) < 8:
                raise forms.ValidationError("❌ La contraseña debe tener al menos 8 caracteres.")
            
            if nueva_password.isnumeric():
                raise forms.ValidationError("❌ La contraseña no puede ser solo números.")
        return cleaned_data

################################## INSCRIPCIONES ##############################################

class InscripcionForm(forms.ModelForm):
    class Meta:
        model = Inscripcion
        fields = ['curso', 'fecha_inicio', 'fecha_fin', 'estado', 'nota_final', 
                 'costo_inscripcion', 'abono_inscripcion', 'observaciones']
        widgets = {
            'fecha_inicio': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'fecha_fin': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'curso': forms.Select(attrs={'class': 'form-control'}),
            'estado': forms.Select(attrs={'class': 'form-control'}),
            'nota_final': forms.NumberInput(attrs={
                'class': 'form-control', 
                'step': '0.01', 
                'min': '0', 
                'max': '10',
                'placeholder': '0.00 - 10.00'
            }),
            'costo_inscripcion': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'placeholder': '0.00'
            }),
            'abono_inscripcion': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'observaciones': forms.Textarea(attrs={
                'class': 'form-control', 
                'rows': 3,
                'placeholder': 'Observaciones adicionales...'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filtrar solo cursos activos
        self.fields['curso'].queryset = Curso.objects.filter(activo=True)
        # Personalizar cómo se muestran las opciones
        self.fields['curso'].label_from_instance = lambda obj: obj.nombre_con_horario()

from django import forms
from .models import Inscripcion

class CambiarEstadoInscripcionForm(forms.ModelForm):
    class Meta:
        model = Inscripcion
        fields = ['estado', 'observaciones']
        widgets = {
            'estado': forms.Select(attrs={
                'class': 'form-control',
                'required': True
            }),
            'observaciones': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Observaciones adicionales...'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Personalizar etiquetas o agregar ayuda
        self.fields['observaciones'].help_text = "Agrega cualquier observación relevante sobre este cambio de estado"
        
        
class FiltroInscripcionesForm(forms.Form):
    ESTADOS = [
        ('', 'Todos los estados'),
        ('INSCRIPTO', 'Inscripto'),
        ('CURSANDO', 'Cursando'),
        ('FINALIZADO', 'Finalizado'),
        ('ABANDONO', 'Abandono'),
        ('INACTIVO', 'Inactivo'),
    ]
    
    estado = forms.ChoiceField(
        choices=ESTADOS,
        required=False,
        label='Estado'
    )
    
    curso = forms.ModelChoiceField(
        queryset=Curso.objects.filter(activo=True, eliminado=False),
        required=False,
        empty_label='Todos los cursos',
        label='Curso'
    )
    
    fecha_desde = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date'}),
        label='Desde'
    )
    
    fecha_hasta = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date'}),
        label='Hasta'
    )
    
    mostrar_inactivas = forms.BooleanField(
        required=False,
        label='Mostrar inscripciones inactivas',
        initial=False
    )
    
# En forms.py - AGREGAR ESTE FORMULARIO
class InscripcionCompletaForm(forms.ModelForm):
    alumno = forms.ModelChoiceField(
        queryset=Alumno.objects.filter(activo=True),
        required=True,
        widget=forms.Select(attrs={'class': 'form-control'}),
        label="Alumno *"
    )
    
    class Meta:
        model = Inscripcion
        fields = ['alumno', 'curso', 'fecha_inicio', 'fecha_fin', 'estado', 'nota_final', 
                 'costo_inscripcion', 'abono_inscripcion', 'observaciones']
        widgets = {
            'fecha_inicio': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'fecha_fin': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'curso': forms.Select(attrs={'class': 'form-control'}),
            'estado': forms.Select(attrs={'class': 'form-control'}),
            'nota_final': forms.NumberInput(attrs={
                'class': 'form-control', 
                'step': '0.01', 
                'min': '0', 
                'max': '10',
                'placeholder': '0.00 - 10.00'
            }),
            'costo_inscripcion': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'placeholder': '0.00'
            }),
            'abono_inscripcion': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'observaciones': forms.Textarea(attrs={
                'class': 'form-control', 
                'rows': 3,
                'placeholder': 'Observaciones adicionales...'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filtrar solo cursos activos
        self.fields['curso'].queryset = Curso.objects.filter(activo=True)
        # Personalizar cómo se muestran las opciones
        self.fields['curso'].label_from_instance = lambda obj: obj.nombre_con_horario()


class BuscarAlumnoForm(forms.Form):
    busqueda = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Buscar por DNI, nombre o apellido...',
            'id': 'busqueda-alumno'
        }),
        label=''
    )
################################## PAGOS ##############################################
# class PagoForm(forms.ModelForm):
#     class Meta:
#         model = Pago
#         fields = '__all__'
#         widgets = {
#             'fecha': forms.DateInput(attrs={'type': 'date'}),
#         }

# class DetallePagoForm(forms.ModelForm):
#     class Meta:
#         model = DetallePago
#         fields = '__all__'

# DetallePagoFormSet = forms.inlineformset_factory(
#     Pago, 
#     DetallePago, 
#     form=DetallePagoForm, 
#     extra=1,
#     can_delete=True
# )

################################## ASISTENCIA Y NOTAS ##############################################
class AsistenciaForm(forms.ModelForm):
    class Meta:
        model = Asistencia
        fields = ['presente', 'observaciones']
        widgets = {
            'presente': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'observaciones': forms.Textarea(attrs={'rows': 2, 'class': 'form-control', 'placeholder': 'Observaciones sobre la asistencia...'}),
        }

class RegistrarNotaForm(forms.Form):
    nota_final = forms.DecimalField(
        max_digits=4,
        decimal_places=2,
        min_value=0,
        max_value=10,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01',
            'min': '0',
            'max': '10'
        })
    )
    observaciones = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'rows': 3,
            'class': 'form-control',
            'placeholder': 'Observaciones sobre el desempeño del alumno...'
        })
    )

class FiltroCursoForm(forms.Form):
    ESTADO_CHOICES = [
        ('', 'Todos los estados'),
        ('ACTIVO', 'Activos'),
        ('FINALIZADO', 'Finalizados'),
        ('FUTURO', 'Próximos'),
    ]
    
    estado = forms.ChoiceField(
        choices=ESTADO_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    mes = forms.IntegerField(
        required=False,
        min_value=1,
        max_value=12,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Mes (1-12)',
            'min': '1',
            'max': '12'
        })
    )

################################## CUOTAS ##############################################
class CuotaAlumnoForm(forms.ModelForm):
    class Meta:
        model = CuotaAlumno
        fields = ['inscripcion', 'mes', 'año', 'monto', 'fecha_vencimiento', 'observaciones']
        widgets = {
            'fecha_vencimiento': forms.DateInput(attrs={'type': 'date'}),
        }
        
        
        

# ################################# NOTIFICACIONES ##############################################

class NotificacionRapidaForm(forms.Form):
    """Formulario para crear notificaciones rápidas - TODOS pueden asignar a TODOS"""
    titulo = forms.CharField(
        max_length=200,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Ej: Seguimiento con alumno...'
        }),
        label="Título",
        help_text="Un título claro y descriptivo"
    )
    
    mensaje = forms.CharField(
        required=True,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 4,
            'placeholder': 'Descripción detallada de la tarea...'
        }),
        label="Mensaje",
        help_text="Describe claramente lo que se debe hacer"
    )
    
    usuario_destino = forms.ModelChoiceField(
        queryset=User.objects.none(),
        required=True,
        widget=forms.Select(attrs={
            'class': 'form-select',
            'placeholder': 'Selecciona un destinatario'
        }),
        label="Destinatario",
        help_text="Persona responsable de esta tarea"
    )
    
    fecha_vencimiento = forms.DateTimeField(
        required=False,
        widget=forms.DateTimeInput(attrs={
            'type': 'datetime-local',
            'class': 'form-control',
            'placeholder': 'YYYY-MM-DD HH:MM'
        }),
        label="Fecha de Vencimiento (opcional)",
        help_text="Fecha límite para completar la tarea"
    )
    
    prioridad = forms.ChoiceField(
        choices=Notificacion.PRIORIDAD_CHOICES,
        initial='MEDIA',
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="Prioridad",
        help_text="Nivel de urgencia de la tarea"
    )
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        if user:
            # CORRECCIÓN: Cambiar personal__ por personal_relacionado__
            # TODOS pueden asignar a CUALQUIER usuario activo del personal
            # Ordenamos por nombre para facilitar la búsqueda
            self.fields['usuario_destino'].queryset = User.objects.filter(
                is_active=True,
                personal_relacionado__isnull=False,  # ¡Corregido!
                personal_relacionado__activo=True,
                personal_relacionado__eliminado=False  # También agregué este filtro
            ).order_by('first_name', 'last_name')
            
            # Agregar opción "Seleccionar..." al inicio
            self.fields['usuario_destino'].empty_label = "Selecciona un destinatario"

User = get_user_model()

class AsignarTareaCompaneroForm(forms.Form):
    usuario_destino = forms.ModelChoiceField(
        queryset=User.objects.none(),
        label="Asignar a",
        help_text="Seleccione un compañero",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    titulo = forms.CharField(
        max_length=200,
        label="Título",
        widget=forms.TextInput(attrs={
            'class': 'form-control', 
            'placeholder': 'Ej: Tarea para...'
        })
    )
    mensaje = forms.CharField(
        label="Mensaje",
        widget=forms.Textarea(attrs={
            'class': 'form-control', 
            'rows': 3, 
            'placeholder': 'Descripción de la tarea...'
        })
    )
    fecha_vencimiento = forms.DateTimeField(
        required=False,
        label="Fecha de Vencimiento (opcional)",
        widget=forms.DateTimeInput(attrs={
            'type': 'datetime-local', 
            'class': 'form-control'
        })
    )
    prioridad = forms.ChoiceField(
        choices=Notificacion._meta.get_field('prioridad').choices,
        label="Prioridad",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        if user:
            # CORRECCIÓN: Cambiar personal__ por personal_relacionado__
            # Todo el personal puede asignar tareas a cualquier otro personal activo
            self.fields['usuario_destino'].queryset = User.objects.filter(
                is_active=True,
                personal_relacionado__isnull=False,  # ¡Corregido!
                personal_relacionado__activo=True,
                personal_relacionado__eliminado=False  # Agregado para consistencia
            ).exclude(id=user.id).distinct().order_by('first_name', 'last_name')