# web/forms_profesores.py
from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone
from .models import Examen, ObservacionAlumno, Asistencia, Curso, Profesor

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
        
        
class ExamenForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        TIPO_CHOICES = kwargs.pop('TIPO_CHOICES', None)
        super().__init__(*args, **kwargs)
        
        if TIPO_CHOICES:
            self.fields['tipo'].choices = [('', 'Seleccionar tipo')] + list(TIPO_CHOICES)
    
    class Meta:
        model = Examen
        fields = ['tipo', 'fecha', 'nota', 'observaciones']
        widgets = {
            'tipo': forms.Select(attrs={'class': 'form-control'}),
            'fecha': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control',
                'max': timezone.now().date().isoformat()
            }),
            'nota': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.1',
                'min': '0',
                'max': '10',
                'placeholder': '0.00 - 10.00'
            }),
            'observaciones': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Observaciones sobre el examen...'
            }),
        }
        labels = {
            'tipo': 'Tipo de Examen',
            'fecha': 'Fecha del Examen',
            'nota': 'Nota (0-10)',
            'observaciones': 'Observaciones',
        }
    
    def clean_nota(self):
        nota = self.cleaned_data.get('nota')
        if nota is not None:
            if nota < 0 or nota > 10:
                raise ValidationError('La nota debe estar entre 0 y 10')
        return nota
    
    def clean_fecha(self):
        fecha = self.cleaned_data.get('fecha')
        if fecha and fecha > timezone.now().date():
            raise ValidationError('La fecha no puede ser futura')
        return fecha