from django.contrib import admin
from .models import *

@admin.register(Contribuyente)
class ContribuyenteAdmin(admin.ModelAdmin):
    list_display = ('razon_social', 'cuit', 'actividad', 'tipo_responsabilidad', 'activo')
    list_filter = ('activo', 'tipo_responsabilidad', 'arca_ambiente')  # Cambiado de 'arca_habilitado' a 'arca_ambiente'
    search_fields = ('razon_social', 'cuit', 'actividad')
    fieldsets = (
        ('Información General', {
            'fields': ('nombre', 'razon_social', 'cuit', 'actividad', 'activo')
        }),
        ('Datos Fiscales', {
            'fields': ('tipo_responsabilidad', 'nro_iibb', 'fecha_inicio_actividades')
        }),
        ('Datos de Contacto', {
            'fields': ('domicilio', 'telefono', 'email', 'logo')
        }),
        ('Configuración ARCA', {
            'fields': ('arca_usuario', 'arca_password', 
                      'arca_token', 'arca_endpoint', 'arca_ambiente'),
            'classes': ('collapse',)
        }),
    )

@admin.register(Comprobante)
class ComprobanteAdmin(admin.ModelAdmin):
    list_display = ('numero_completo', 'tipo', 'cliente_razon_social', 
                   'fecha_emision', 'total', 'estado')
    list_filter = ('tipo', 'estado', 'fecha_emision', 'contribuyente', 'enviar_arca')
    search_fields = ('numero', 'cliente_razon_social', 'cliente_numero_documento')
    readonly_fields = ('uuid', 'creado_en', 'modificado_en', 'numero_completo')
    fieldsets = (
        ('Identificación', {
            'fields': ('uuid', 'tipo', 'punto_venta', 'numero', 'estado', 'numero_completo')
        }),
        ('Fechas', {
            'fields': ('fecha_emision', 'fecha_vencimiento')
        }),
        ('Emisor', {
            'fields': ('contribuyente',)
        }),
        ('Receptor', {
            'fields': ('cliente_tipo_documento', 'cliente_numero_documento',
                      'cliente_razon_social', 'cliente_domicilio',
                      'cliente_email', 'cliente_condicion_iva',
                      'alumno', 'pago')
        }),
        ('Totales', {
            'fields': ('subtotal', 'descuento', 'iva', 'percepciones',
                      'retenciones', 'total', 'moneda', 'condicion_venta')
        }),
        ('ARCA', {
            'fields': ('enviar_arca', 'arca_envio_id', 'arca_cae',
                      'arca_fecha_vto_cae', 'arca_resultado',
                      'arca_observaciones', 'arca_respuesta_raw'),
            'classes': ('collapse',)
        }),
        ('Archivos', {
            'fields': ('pdf', 'xml'),
            'classes': ('collapse',)
        }),
        ('Observaciones', {
            'fields': ('observaciones',),
            'classes': ('collapse',)
        }),
        ('Auditoría', {
            'fields': ('creado_por', 'creado_en', 'modificado_por', 'modificado_en'),
            'classes': ('collapse',)
        }),
    )

@admin.register(ProductoServicio)
class ProductoServicioAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'nombre', 'tipo', 'precio', 'stock_actual', 'activo')
    list_filter = ('tipo', 'maneja_stock', 'activo')
    search_fields = ('codigo', 'nombre', 'codigo_barras')
    fieldsets = (
        ('Información General', {
            'fields': ('codigo', 'codigo_barras', 'nombre', 'descripcion', 'tipo', 'precio', 'activo')
        }),
        ('Stock', {
            'fields': ('maneja_stock', 'stock_actual', 'stock_minimo', 'stock_maximo')
        }),
        ('Datos Fiscales', {
            'fields': ('codigo_afip', 'unidad_medida', 'alicuota_iva')
        }),
    )

@admin.register(ItemComprobante)
class ItemComprobanteAdmin(admin.ModelAdmin):
    list_display = ('comprobante', 'descripcion', 'cantidad', 'precio_unitario', 'subtotal')
    list_filter = ('comprobante__tipo',)
    search_fields = ('descripcion', 'codigo', 'comprobante__numero')

@admin.register(MovimientoStock)
class MovimientoStockAdmin(admin.ModelAdmin):
    list_display = ('producto', 'tipo', 'cantidad', 'stock_anterior', 'stock_posterior', 'fecha')
    list_filter = ('tipo', 'fecha')
    search_fields = ('producto__nombre', 'producto__codigo')
    readonly_fields = ('fecha',)

@admin.register(Caja)
class CajaAdmin(admin.ModelAdmin):
    list_display = ('punto_venta', 'usuario', 'fecha_apertura', 'estado', 'saldo_inicial', 'saldo_final')
    list_filter = ('estado', 'punto_venta')
    readonly_fields = ('fecha_apertura', 'fecha_cierre')
    search_fields = ('usuario__username', 'punto_venta__numero')


admin.site.register(PuntoVenta)
admin.site.register(ConfiguracionFacturacion)

