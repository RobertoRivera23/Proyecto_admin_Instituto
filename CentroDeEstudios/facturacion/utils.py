from django.utils import timezone
from .models import Contribuyente, PuntoVenta, ConfiguracionFacturacion

def get_or_create_default_contribuyente():
    """Retorna el contribuyente por defecto (Instituto Argentino de Capacitación Laboral)."""
    datos_default = {
        'razon_social': 'Instituto Argentino de Capacitación Laboral',
        'nombre': 'Instituto Argentino de Capacitación Laboral',
        'cuit': '99999999999',
        'domicilio': 'Av. Rivadavia 2890, piso 12, CABA CP: 1203',
        'telefono': '011-1234-5678',
        'email': 'info@iacl.com.ar',
        'actividad': 'Educación y Capacitación Laboral',
        'tipo_responsabilidad': 'CF',
        'fecha_inicio_actividades': timezone.now().date(),
        'arca_habilitado': False,
        'activo': True,
    }
    
    contribuyente = Contribuyente.objects.filter(cuit=datos_default['cuit']).first()
    if not contribuyente:
        contribuyente = Contribuyente.objects.filter(
            razon_social=datos_default['razon_social']
        ).first()
    
    if not contribuyente:
        contribuyente = Contribuyente.objects.create(**datos_default)
    
    # Asegurar punto de venta activo
    PuntoVenta.objects.get_or_create(
        contribuyente=contribuyente,
        numero=1,
        defaults={
            'descripcion': 'Punto de Venta Principal',
            'activo': True
        }
    )
    
    # Asegurar configuración principal
    config, _ = ConfiguracionFacturacion.objects.get_or_create(id=1)
    config.contribuyente_principal = contribuyente
    config.save()
    
    return contribuyente