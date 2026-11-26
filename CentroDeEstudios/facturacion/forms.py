from django import forms
from django.forms import inlineformset_factory
from .models import Comprobante, ItemComprobante, Pago, DetallePago
from web.models import Alumno  



class ComprobanteForm(forms.ModelForm):
    # Campo para elegir entre alumno o tercero
    es_alumno = forms.BooleanField(
        required=False,
        initial=True,
        label="El comprobante corresponde a un alumno registrado",
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )

    class Meta:
        model = Comprobante
        fields = [
            'tipo', 'punto_venta', 'fecha_emision', 'contribuyente',
            'alumno',  # opcional
            'cliente_tipo_documento', 'cliente_numero_documento',
            'cliente_razon_social', 'cliente_domicilio', 'cliente_email',
            'cliente_condicion_iva', 'condicion_venta', 'moneda',
            'observaciones',
        ]
        widgets = {
            'fecha_emision': forms.DateInput(attrs={'type': 'date'}),
            'cliente_razon_social': forms.TextInput(attrs={'class': 'form-control'}),
            'cliente_domicilio': forms.TextInput(attrs={'class': 'form-control'}),
            'cliente_email': forms.EmailInput(attrs={'class': 'form-control'}),
            'observaciones': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            # Puedes agregar más widgets según necesites
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Hacer que alumno sea opcional (porque puede no seleccionarse)
        self.fields['alumno'].required = False
        # Los campos manuales del cliente no son requeridos por defecto,
        # la vista validará según corresponda
        self.fields['cliente_numero_documento'].required = False
        self.fields['cliente_razon_social'].required = False
        # También puedes añadir placeholders o clases CSS
        self.fields['cliente_tipo_documento'].widget.attrs['class'] = 'form-select'
        self.fields['cliente_condicion_iva'].widget.attrs['class'] = 'form-select'
        self.fields['condicion_venta'].widget.attrs['class'] = 'form-select'
        self.fields['moneda'].widget.attrs['class'] = 'form-select'
        self.fields['tipo'].widget.attrs['class'] = 'form-select'
        self.fields['punto_venta'].widget.attrs['class'] = 'form-select'
        self.fields['contribuyente'].widget.attrs['class'] = 'form-select'
        # Para que el campo alumno sea un select2 si lo deseas, puedes agregar atributos data
        # pero eso lo manejas en el template con JavaScript


class ItemComprobanteForm(forms.ModelForm):
    class Meta:
        model = ItemComprobante
        fields = [
            'producto', 'curso', 'codigo', 'descripcion',
            'cantidad', 'precio_unitario', 'iva_porcentaje',
            'descuento', 'orden'
        ]
        widgets = {
            'descripcion': forms.TextInput(attrs={'class': 'form-control'}),
            'cantidad': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'precio_unitario': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'iva_porcentaje': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'value': 21.0}),
            'descuento': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'value': 0}),
            'codigo': forms.TextInput(attrs={'class': 'form-control'}),
            'orden': forms.NumberInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Hacer opcionales los campos que pueden no usarse
        self.fields['producto'].required = False
        self.fields['curso'].required = False
        self.fields['codigo'].required = False
        # Opcionalmente, si quieres que el usuario no pueda modificar el iva,
        # puedes hacerlo readonly o con un valor fijo
        self.fields['iva_porcentaje'].initial = 21.0
        self.fields['descuento'].initial = 0.0
        self.fields['orden'].initial = 1


# Crear el formset para los items
ItemComprobanteFormSet = inlineformset_factory(
    Comprobante,                 # Modelo padre
    ItemComprobante,             # Modelo hijo
    form=ItemComprobanteForm,    # Formulario para cada item
    extra=1,                     # Número de formularios vacíos a mostrar
    can_delete=True,             # Permitir eliminar items
    fields=['producto', 'curso', 'codigo', 'descripcion', 'cantidad',
            'precio_unitario', 'iva_porcentaje', 'descuento', 'orden'],
)



class PagoForm(forms.ModelForm):
    """Formulario para edición de pagos (solo datos generales)"""
    fecha_pago = forms.DateTimeField(
        input_formats=['%Y-%m-%dT%H:%M', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d'],
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}, format='%Y-%m-%dT%H:%M')
    )

    class Meta:
        model = Pago
        fields = [
            'fecha_pago', 'monto', 'metodo_pago', 'referencia',
            'descripcion', 'confirmado', 'observaciones'
        ]
        widgets = {
            'metodo_pago': forms.Select(attrs={'class': 'form-select'}),
            'referencia': forms.TextInput(attrs={'class': 'form-control'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'observaciones': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'confirmado': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['monto'].widget.attrs.update({'class': 'form-control', 'step': '0.01', 'min': '0'})
        self.fields['metodo_pago'].choices = Pago.METODOS_PAGO  # Asegurar las opciones


class AnularPagoForm(forms.Form):
    """Formulario para anular un pago con motivo"""
    motivo_anulacion = forms.CharField(
        label='Motivo de anulación',
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Ej: Pago duplicado, error en el monto...'}),
        required=True
    )
    confirmar = forms.BooleanField(
        label='Comprendo las consecuencias de esta acción',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        required=True
    )


# Formulario auxiliar para búsqueda de alumnos (API)
class BusquedaAlumnoForm(forms.Form):
    term = forms.CharField(max_length=100, required=False)