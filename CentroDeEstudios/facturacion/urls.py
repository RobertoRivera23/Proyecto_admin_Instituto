from django.urls import path
from . import views

app_name = 'facturacion'

urlpatterns = [
    # Dashboard principal
    path('', views.dashboard_facturacion, name='dashboard'),
    
    # Pagos
    path('pagos/', views.listar_pagos, name='listar_pagos'),
    path('pagos/registrar/', views.registrar_pago, name='registrar_pago'),
    path('pagos/editar/<int:pago_id>/', views.editar_pago, name='editar_pago'),
    #path('pagos/detalle/<int:pago_id>/', views.detalle_pago, name='detalle_pago'),
    path('pagos/confirmar/<int:pago_id>/', views.confirmar_pago, name='confirmar_pago'),
    path('pagos/anular/<int:pago_id>/', views.anular_pago, name='anular_pago'),
    path('pagos/reporte/', views.reporte_pagos, name='reporte_pagos'),
    path('pagos/exportar/', views.exportar_pagos, name='exportar_pagos'),
    
    # APIs para pagos
    path('alumno/<int:alumno_id>/detalle/', views.obtener_detalle_alumno, name='obtener_detalle_alumno'),
    path('alumno/<int:alumno_id>/cuotas/', views.obtener_cuotas_alumno, name='obtener_cuotas_alumno'),
    path('cuota/<int:cuota_id>/pagar/', views.marcar_cuota_pagada, name='marcar_cuota_pagada'),
    
    # Comprobantes (mantener tus vistas actuales)
    path('comprobantes/', views.ListaComprobantesView.as_view(), name='listar_comprobantes'),
    path('comprobantes/crear/', views.crear_comprobante, name='crear_comprobante'),
    path('comprobantes/<uuid:uuid>/preview/', views.preview_comprobante, name='preview_comprobante'),
    path('comprobantes/<uuid:uuid>/detalle/', views.detalle_comprobante, name='detalle_comprobante'),
    path('comprobantes/<uuid:uuid>/imprimir/', views.imprimir_comprobante, name='imprimir_comprobante'),
    
    # Seguimiento de moras (mantener compatibilidad)
    path('seguimiento-moras/', views.seguimiento_moras, name='seguimiento_moras'),
    path('reporte-moras-pdf/', views.reporte_moras_pdf, name='reporte_moras_pdf'),
    path('alumno/<int:alumno_id>/contactar/', views.contactar_alumno_mora, name='contactar_alumno_mora'),
    path('generar-notificaciones/', views.generar_notificaciones_mora_manual, name='generar_notificaciones_mora_manual'),
    path('exportar-moras-excel/', views.exportar_moras_excel, name='exportar_moras_excel'),
    
    # URLs temporales para mantener compatibilidad
    path('contribuyentes/', views.dashboard_facturacion, name='listar_contribuyentes'),
    path('productos/', views.dashboard_facturacion, name='listar_productos'),
    path('debug/', views.dashboard_debug, name='dashboard_debug'),
    path('test-herencia/', views.test_herencia, name='test_herencia'),
    
    # APIs generales
    path('api/buscar-cliente/', views.api_buscar_cliente, name='api_buscar_cliente'),
    path('api/buscar-producto/', views.api_buscar_producto, name='api_buscar_producto'),
    path('reportes/generar/', views.generar_reporte, name='generar_reporte'),
    path('api/buscar-curso/', views.api_buscar_curso, name='api_buscar_curso'),
    path('api/buscar-alumnos/', views.api_buscar_alumnos, name='api_buscar_alumnos'),
    path('api/cuotas-alumno/<int:alumno_id>/', views.obtener_cuotas_alumno, name='obtener_cuotas_alumno'),
    path('api/datos-alumno/<int:alumno_id>/', views.api_datos_alumno, name='api_datos_alumno'),


    
    path('pagos/', views.listar_pagos, name='listar_pagos'),
    path('pagos/registrar/', views.registrar_pago, name='registrar_pago'),
    path('pagos/editar/<int:pago_id>/', views.editar_pago, name='editar_pago'),
    path('pagos/detalle/<int:pago_id>/', views.detalle_pago, name='detalle_pago'),
    path('pagos/confirmar/<int:pago_id>/', views.confirmar_pago, name='confirmar_pago'),
    path('pagos/anular/<int:pago_id>/', views.anular_pago, name='anular_pago'),
    path('pagos/reporte/', views.reporte_pagos, name='reporte_pagos'),
    path('pagos/exportar/', views.exportar_pagos, name='exportar_pagos'),
    path('pagos/generar-recibo/<int:pago_id>/', views.generar_recibo, name='generar_recibo'),
    path('pagos/emitir-factura/<int:pago_id>/', views.emitir_factura_arca, name='emitir_factura_arca'),
]