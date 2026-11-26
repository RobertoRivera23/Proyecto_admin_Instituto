from django.db import models
from django.conf import settings
from decimal import Decimal
import uuid
from django.core.validators import MinValueValidator, MaxValueValidator
from django.shortcuts import redirect, render
from django.utils import timezone
from django.contrib.auth.models import User

from web.models import Curso

# ========== MODELOS DE FACTURACIÓN ==========

class Contribuyente(models.Model):
    """Modelo para múltiples emisores de comprobantes"""
    TIPO_RESPONSABILIDAD = [
        ('RI', 'Responsable Inscripto'),
        ('RNI', 'Responsable No Inscripto'),
        ('EX', 'Exento'),
        ('CF', 'Consumidor Final'),
        ('MT', 'Monotributo'),
        ('MTI', 'Monotributo Trabajador Independiente Promovido'),
        ('MTS', 'Monotributista Social'),
    ]
    
    nombre = models.CharField(max_length=200, verbose_name="Nombre/Razón Social")
    razon_social = models.CharField(max_length=200, verbose_name="Razón Social")
    cuit = models.CharField(max_length=13, unique=True, verbose_name="CUIT")
    domicilio = models.CharField(max_length=200, verbose_name="Domicilio")
    telefono = models.CharField(max_length=50, blank=True, verbose_name="Teléfono")
    email = models.EmailField(blank=True, verbose_name="Email")
    actividad = models.CharField(max_length=100, verbose_name="Actividad Principal")
    tipo_responsabilidad = models.CharField(max_length=3, choices=TIPO_RESPONSABILIDAD, verbose_name="Condición Tributaria")
    nro_iibb = models.CharField(max_length=50, blank=True, verbose_name="N° IIBB")
    fecha_inicio_actividades = models.DateField(verbose_name="Fecha Inicio Actividades")
    logo = models.ImageField(upload_to='contribuyentes/logos/', blank=True, null=True, verbose_name="Logo")
    activo = models.BooleanField(default=True, verbose_name="Activo")
    
    # Campos específicos para ARCA
    arca_habilitado = models.BooleanField(default=False, verbose_name="Habilitado para ARCA")  # AGREGADO
    arca_usuario = models.CharField(max_length=100, blank=True, verbose_name="Usuario ARCA")
    arca_password = models.CharField(max_length=500, blank=True, verbose_name="Password ARCA")
    arca_token = models.CharField(max_length=500, blank=True, verbose_name="Token ARCA")
    arca_endpoint = models.URLField(blank=True, verbose_name="Endpoint ARCA")
    arca_ambiente = models.CharField(max_length=10, choices=[('TEST', 'Testing'), ('PROD', 'Producción')], default='TEST', verbose_name="Ambiente ARCA")
    
    class Meta:
        verbose_name = "Contribuyente"
        verbose_name_plural = "Contribuyentes"
        ordering = ['razon_social']
    
    def __str__(self):
        return f"{self.razon_social} - {self.cuit}"

class PuntoVenta(models.Model):
    """Puntos de venta por contribuyente"""
    contribuyente = models.ForeignKey(Contribuyente, on_delete=models.CASCADE, related_name='puntos_venta')
    numero = models.IntegerField(verbose_name="Número de Punto de Venta")
    descripcion = models.CharField(max_length=100, verbose_name="Descripción")
    activo = models.BooleanField(default=True, verbose_name="Activo")
    
    class Meta:
        verbose_name = "Punto de Venta"
        verbose_name_plural = "Puntos de Venta"
        unique_together = ['contribuyente', 'numero']
    
    def __str__(self):
        return f"PV {self.numero:04d} - {self.contribuyente.razon_social}"

class ProductoServicio(models.Model):
    """Catálogo de productos y servicios para facturación"""
    TIPO_CHOICES = [
        ('CURSO', 'Curso'),
        ('KIOSCO', 'Kiosco'),
        ('PROVEEDURIA', 'Proveeduría'),
        ('SERVICIO_JURIDICO', 'Servicio Jurídico'),
        ('OTROS', 'Otros'),
    ]
    
    codigo = models.CharField(max_length=50, unique=True, verbose_name="Código")
    codigo_barras = models.CharField(max_length=100, blank=True, verbose_name="Código de Barras")
    nombre = models.CharField(max_length=200, verbose_name="Nombre")
    descripcion = models.TextField(blank=True, verbose_name="Descripción")
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, verbose_name="Tipo")
    precio = models.DecimalField(max_digits=15, decimal_places=2, verbose_name="Precio Unitario")
    
    # Para productos físicos
    maneja_stock = models.BooleanField(default=False, verbose_name="Maneja Stock")
    stock_actual = models.IntegerField(default=0, verbose_name="Stock Actual")
    stock_minimo = models.IntegerField(default=5, verbose_name="Stock Mínimo")
    stock_maximo = models.IntegerField(default=100, verbose_name="Stock Máximo")
    
    # Campos AFIP
    codigo_afip = models.CharField(max_length=50, blank=True, verbose_name="Código AFIP")
    unidad_medida = models.CharField(max_length=20, default='UNIDAD', verbose_name="Unidad de Medida")
    alicuota_iva = models.DecimalField(max_digits=5, decimal_places=2, default=21.00, verbose_name="Alicuota IVA %")
    
    activo = models.BooleanField(default=True, verbose_name="Activo")
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Producto/Servicio"
        verbose_name_plural = "Productos/Servicios"
        ordering = ['tipo', 'nombre']
    
    def __str__(self):
        return f"{self.codigo} - {self.nombre}"
    
    @property
    def necesita_reponer(self):
        return self.maneja_stock and self.stock_actual <= self.stock_minimo


# ========== MODELO DE PAGO INTEGRADO ==========

class Pago(models.Model):
    """
    Modelo principal de pagos que integra cuotas, comprobantes y alumnos
    """
    METODOS_PAGO = [
        ('EFECTIVO', 'Efectivo'),
        ('TRANSFERENCIA', 'Transferencia Bancaria'),
        ('TARJETA_CREDITO', 'Tarjeta de Crédito'),
        ('TARJETA_DEBITO', 'Tarjeta de Débito'),
        ('MERCADO_PAGO', 'Mercado Pago'),
        ('OTRO', 'Otro'),
    ]
    
    ESTADOS_PAGO = [
        ('PENDIENTE', 'Pendiente'),
        ('CONFIRMADO', 'Confirmado'),
        ('ANULADO', 'Anulado'),
        ('RECHAZADO', 'Rechazado'),
        ('EN_PROCESO', 'En Proceso'),
    ]
    
    # Relaciones principales
    alumno = models.ForeignKey(
        'web.Alumno',  # ← CADENA
        on_delete=models.PROTECT,
        related_name='pagos_facturacion',
        verbose_name="Alumno",
        null=True,               
        blank=True,              
    )
    cuota = models.ForeignKey(
        'web.CuotaAlumno', 
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='pagos',
        verbose_name="Cuota asociada"
    )
    
    comprobante = models.ForeignKey(
        'Comprobante',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='pagos_relacionados',  # ← CAMBIADO a ForeignKey
        verbose_name="Comprobante asociado"
    )
    
    # Datos del pago
    monto = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        verbose_name="Monto"
    )
    
    metodo_pago = models.CharField(
        max_length=20,
        choices=METODOS_PAGO,
        default='EFECTIVO',
        verbose_name="Método de pago"
    )
    
    fecha_pago = models.DateTimeField(
        default=timezone.now,
        verbose_name="Fecha de pago"
    )
    
    fecha_registro = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha de registro"
    )
    
    # Estado y confirmación
    confirmado = models.BooleanField(
        default=False,
        verbose_name="Confirmado"
    )
    
    estado = models.CharField(
        max_length=20,
        choices=ESTADOS_PAGO,
        default='PENDIENTE',
        verbose_name="Estado"
    )
    
    # Información adicional
    referencia = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Número de referencia/comprobante"
    )
    
    descripcion = models.TextField(
        blank=True,
        verbose_name="Descripción"
    )
    
    observaciones = models.TextField(
        null=True,
        blank=True,
        verbose_name="Observaciones"
    )
    
    # Para pagos parciales o anticipos
    es_parcial = models.BooleanField(
        default=False,
        verbose_name="Es pago parcial"
    )
    
    saldo_pendiente = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name="Saldo pendiente"
    )
    
    # Auditoría
    usuario_registro = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='pagos_registrados',
        verbose_name="Registrado por"
    )
    
    usuario_confirmacion = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='pagos_confirmados',
        verbose_name="Confirmado por"
    )
    
    fecha_confirmacion = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Fecha de confirmación"
    )
    
    # Para anulaciones
    anulado = models.BooleanField(
        default=False,
        verbose_name="Anulado"
    )
    
    motivo_anulacion = models.TextField(
        blank=True,
        verbose_name="Motivo de anulación"
    )
    
    fecha_anulacion = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Fecha de anulación"
    )
    
    usuario_anulacion = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='pagos_anulados',
        verbose_name="Anulado por"
    )
    
    # campos para tercero:
    tercero_nombre = models.CharField(max_length=100, blank=True, verbose_name="Nombre")
    tercero_apellido = models.CharField(max_length=100, blank=True, verbose_name="Apellido")
    tercero_dni = models.CharField(max_length=20, blank=True, verbose_name="DNI")
    tercero_cuil = models.CharField(max_length=20, blank=True, verbose_name="CUIL")
    tercero_domicilio = models.CharField(max_length=200, blank=True, verbose_name="Domicilio")
    
    class Meta:
        verbose_name = "Pago"
        verbose_name_plural = "Pagos"
        ordering = ['-fecha_pago', '-id']
        indexes = [
            models.Index(fields=['alumno', 'fecha_pago']),
            models.Index(fields=['confirmado', 'fecha_pago']),
            models.Index(fields=['cuota', 'estado']),
        ]
        permissions = [
            ("can_confirm_payment", "Puede confirmar pagos"),
            ("can_annul_payment", "Puede anular pagos"),
            ("can_view_all_payments", "Puede ver todos los pagos"),
        ]
    
    def __str__(self):
        if self.alumno:
            return f"Pago #{self.id} - {self.alumno.nombre_completo()} - ${self.monto}"
        else:
            nombre = f"{self.tercero_nombre} {self.tercero_apellido}".strip()
            return f"Pago #{self.id} - {nombre or 'Tercero'} - ${self.monto}"
    
    def save(self, *args, **kwargs):
           # Sincronizar estado con confirmado y anulado
        if self.anulado:
            self.estado = 'ANULADO'
            self.confirmado = False
        elif self.confirmado:
            self.estado = 'CONFIRMADO'
        else:
            self.estado = 'PENDIENTE'

        # Calcular saldo pendiente si es pago parcial
        if self.cuota and self.es_parcial:
            self.saldo_pendiente = self.cuota.monto - self.monto
        else:
            self.saldo_pendiente = Decimal('0.00')
        
        # Si el pago se confirma y tiene cuota asociada, marcar cuota como pagada
        if self.confirmado and self.cuota and not self.cuota.pagada:
            self.cuota.pagada = True
            self.cuota.fecha_pago = self.fecha_pago
            self.cuota.save()
            
        # Si se anula el pago y tiene cuota, revertir el pago de la cuota
        if self.anulado and self.cuota and self.cuota.pagada:
            self.cuota.pagada = False
            self.cuota.fecha_pago = None
            self.cuota.save()
            
        super().save(*args, **kwargs)
    
    @property
    def numero_completo(self):
        """Formato legible del pago"""
        return f"PAY-{self.id:06d}"
    
    @property
    def esta_vencido(self):
        """Verifica si el pago está vencido (si tiene cuota asociada)"""
        if self.cuota:
            return not self.confirmado and self.cuota.fecha_vencimiento < timezone.now().date()
        return False
    
    @property
    def puede_anular(self):
        """Verifica si el pago puede ser anulado"""
        return self.confirmado and not self.anulado
    
    @property
    def color_estado(self):
        """Color para mostrar en interfaces"""
        colores = {
            'PENDIENTE': 'warning',
            'CONFIRMADO': 'success',
            'ANULADO': 'danger',
            'RECHAZADO': 'secondary',
            'EN_PROCESO': 'info',
        }
        return colores.get(self.estado, 'secondary')
    
    def generar_comprobante(self, usuario=None):
        """Genera un comprobante asociado a este pago"""
        if self.comprobante:
            return self.comprobante
        
        try:
            # Buscar contribuyente principal
            config = ConfiguracionFacturacion.objects.first()
            if not config or not config.contribuyente_principal:
                return None
            
            # Crear comprobante
            from django.utils import timezone
            comprobante = Comprobante.objects.create(
                tipo='RECIBO',  # O el tipo que corresponda
                punto_venta=config.contribuyente_principal.puntos_venta.first(),
                fecha_emision=timezone.now().date(),
                contribuyente=config.contribuyente_principal,
                cliente_numero_documento=self.alumno.dni or '',
                cliente_razon_social=self.alumno.nombre_completo(),
                cliente_domicilio=self.alumno.direccion or '',
                cliente_email=self.alumno.mail or '',
                condicion_venta='CONTADO',
                subtotal=self.monto,
                iva=Decimal('0.00'),
                total=self.monto,
                estado='ACEPTADO_ARCA' if self.confirmado else 'BORRADOR',
                alumno=self.alumno,
                creado_por=usuario or self.usuario_registro,
            )
            
            # Crear item del comprobante
            descripcion = f"Pago de cuota - {self.cuota.get_mes_display()}/{self.cuota.año}" if self.cuota else "Pago general"
            
            ItemComprobante.objects.create(
                comprobante=comprobante,
                descripcion=descripcion,
                cantidad=1,
                precio_unitario=self.monto,
                iva_porcentaje=0,
                subtotal=self.monto,
            )
            
            self.comprobante = comprobante
            self.save()
            
            return comprobante
            
        except Exception as e:
            print(f"Error generando comprobante: {e}")
            return None
        

class HistorialPago(models.Model):
    ACCIONES = [
        ('CREAR', 'Creación'),
        ('EDITAR', 'Edición'),
        ('CONFIRMAR', 'Confirmación'),
        ('ANULAR', 'Anulación'),
        ('OTRO', 'Otro'),
    ]

    pago = models.ForeignKey(Pago, on_delete=models.CASCADE, related_name='historial')
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    accion = models.CharField(max_length=20, choices=ACCIONES)
    descripcion = models.TextField(blank=True)
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Historial de Pago"
        verbose_name_plural = "Historiales de Pago"
        ordering = ['-fecha']
        
        

class Comprobante(models.Model):
    """Modelo principal para todos los tipos de comprobantes"""
    TIPO_COMPROBANTE = [
        ('FACTURA_A', 'Factura A'),
        ('FACTURA_B', 'Factura B'),
        ('FACTURA_C', 'Factura C'),
        ('PRESUPUESTO', 'Presupuesto'),
        ('REMITO', 'Remito'),
        ('RECIBO', 'Recibo'),
        ('NOTA_CREDITO_A', 'Nota de Crédito A'),
        ('NOTA_CREDITO_B', 'Nota de Crédito B'),
        ('NOTA_CREDITO_C', 'Nota de Crédito C'),
        ('NOTA_DEBITO_A', 'Nota de Débito A'),
        ('NOTA_DEBITO_B', 'Nota de Débito B'),
        ('NOTA_DEBITO_C', 'Nota de Débito C'),
    ]
    
    CONDICION_VENTA = [
        ('CONTADO', 'Contado'),
        ('CREDITO', 'Crédito'),
        ('CTA_CTE', 'Cuenta Corriente'),
    ]
    
    MONEDA = [
        ('ARS', 'Pesos Argentinos (ARS)'),
        ('USD', 'Dólares Estadounidenses (USD)'),
    ]
    
    ESTADO_COMPROBANTE = [
        ('BORRADOR', 'Borrador'),
        ('PENDIENTE', 'Pendiente de Envío'),
        ('ENVIADO_ARCA', 'Enviado a ARCA'),
        ('ACEPTADO_ARCA', 'Aceptado por ARCA'),
        ('RECHAZADO_ARCA', 'Rechazado por ARCA'),
        ('IMPRESO', 'Impreso'),
        ('ANULADO', 'Anulado'),
    ]
    
    # Identificación única
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    
    # Datos del comprobante
    tipo = models.CharField(max_length=20, choices=TIPO_COMPROBANTE, verbose_name="Tipo de Comprobante")
    punto_venta = models.ForeignKey(PuntoVenta, on_delete=models.PROTECT, verbose_name="Punto de Venta")
    numero = models.IntegerField(verbose_name="Número")
    fecha_emision = models.DateField(default=timezone.now, verbose_name="Fecha de Emisión")
    fecha_vencimiento = models.DateField(null=True, blank=True, verbose_name="Fecha de Vencimiento")
    
    # Contribuyente emisor
    contribuyente = models.ForeignKey(Contribuyente, on_delete=models.PROTECT, verbose_name="Emisor")
    
    # Cliente (puede ser Alumno u otro)
    cliente_tipo_documento = models.CharField(max_length=10, choices=[
        ('DNI', 'DNI'),
        ('CUIT', 'CUIT'),
        ('CUIL', 'CUIL'),
        ('PASAPORTE', 'Pasaporte'),
    ], default='DNI', verbose_name="Tipo Documento Cliente")
    
    cliente_numero_documento = models.CharField(max_length=20, verbose_name="N° Documento Cliente")
    cliente_razon_social = models.CharField(max_length=200, verbose_name="Nombre/Razón Social")
    cliente_domicilio = models.CharField(max_length=200, blank=True, verbose_name="Domicilio Cliente")
    cliente_email = models.EmailField(blank=True, verbose_name="Email Cliente")
    cliente_condicion_iva = models.CharField(max_length=3, choices=[
        ('CF', 'Consumidor Final'),
        ('RI', 'Responsable Inscripto'),
        ('RNI', 'Responsable No Inscripto'),
        ('EX', 'Exento'),
        ('MT', 'Monotributo'),
    ], default='CF', verbose_name="Condición IVA Cliente")
    
    # Relaciones
    alumno = models.ForeignKey(
        'web.Alumno',  # ← CADENA
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        verbose_name="Alumno Relacionado"
    )
    #pago = models.ForeignKey('facturacion.Pago', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Pago Relacionado")
    
    # Condiciones comerciales
    condicion_venta = models.CharField(max_length=10, choices=CONDICION_VENTA, default='CONTADO', verbose_name="Condición de Venta")
    moneda = models.CharField(max_length=3, choices=MONEDA, default='ARS', verbose_name="Moneda")
    
    # Totales
    subtotal = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name="Subtotal")
    descuento = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name="Descuento")
    iva = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name="IVA")
    percepciones = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name="Percepciones")
    retenciones = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name="Retenciones")
    total = models.DecimalField(max_digits=15, decimal_places=2, verbose_name="Total")
    
    # Estado y control
    estado = models.CharField(max_length=20, choices=ESTADO_COMPROBANTE, default='BORRADOR', verbose_name="Estado")
    enviar_arca = models.BooleanField(default=False, verbose_name="Enviar a ARCA")
    impreso = models.BooleanField(default=False, verbose_name="Impreso")
    
    # Datos ARCA (si aplica)
    arca_envio_id = models.CharField(max_length=100, blank=True, verbose_name="ID Envío ARCA")
    arca_cae = models.CharField(max_length=50, blank=True, verbose_name="CAE")
    arca_fecha_vto_cae = models.DateField(null=True, blank=True, verbose_name="Fecha Vto. CAE")
    arca_resultado = models.CharField(max_length=50, blank=True, verbose_name="Resultado ARCA")
    arca_observaciones = models.TextField(blank=True, verbose_name="Observaciones ARCA")
    arca_respuesta_raw = models.JSONField(null=True, blank=True, verbose_name="Respuesta ARCA")
    
    # Archivos generados
    pdf = models.FileField(upload_to='comprobantes/pdf/%Y/%m/', null=True, blank=True, verbose_name="PDF")
    xml = models.FileField(upload_to='comprobantes/xml/%Y/%m/', null=True, blank=True, verbose_name="XML")
    
    # Observaciones
    observaciones = models.TextField(blank=True, verbose_name="Observaciones")
    
    # Auditoría
    creado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='comprobantes_creados')
    creado_en = models.DateTimeField(auto_now_add=True)
    modificado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='comprobantes_modificados')
    modificado_en = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Comprobante"
        verbose_name_plural = "Comprobantes"
        unique_together = ['contribuyente', 'tipo', 'punto_venta', 'numero']
        ordering = ['-fecha_emision', '-numero']
        permissions = [
            ("puede_emitir_comprobante", "Puede emitir comprobantes"),
            ("puede_anular_comprobante", "Puede anular comprobantes"),
            ("puede_ver_todos_comprobantes", "Puede ver todos los comprobantes"),
            ("puede_exportar_comprobantes", "Puede exportar comprobantes"),
        ]
    
    def __str__(self):
        return f"{self.get_tipo_display()} {self.punto_venta.numero:04d}-{self.numero:08d}"
    
    def save(self, *args, **kwargs):
        # Generar número secuencial si es nuevo
        if not self.numero:
            ultimo = Comprobante.objects.filter(
                contribuyente=self.contribuyente,
                tipo=self.tipo,
                punto_venta=self.punto_venta
            ).order_by('-numero').first()
            self.numero = (ultimo.numero + 1) if ultimo else 1
        
        # Calcular total si hay cambios
        if not self.total or 'items' in kwargs.get('update_fields', []):
            self.calcular_totales()
        
        super().save(*args, **kwargs)
    
    def calcular_totales(self):
        """Calcula los totales del comprobante"""
        items = self.items.all()
        self.subtotal = sum(item.subtotal for item in items)
        self.iva = sum(item.iva_monto for item in items)
        self.total = self.subtotal + self.iva + self.percepciones - self.retenciones - self.descuento
    
    @property
    def numero_completo(self):
        return f"{self.punto_venta.numero:04d}-{self.numero:08d}"

class ItemComprobante(models.Model):
    """Items detallados de un comprobante"""
    comprobante = models.ForeignKey(Comprobante, on_delete=models.CASCADE, related_name='items')
    producto = models.ForeignKey(ProductoServicio, on_delete=models.PROTECT, null=True, blank=True)
    curso = models.ForeignKey('web.Curso', on_delete=models.PROTECT, null=True, blank=True)
    codigo = models.CharField(max_length=50, blank=True, verbose_name="Código")
    descripcion = models.CharField(max_length=200, verbose_name="Descripción")
    cantidad = models.DecimalField(max_digits=10, decimal_places=2, default=1, verbose_name="Cantidad")
    precio_unitario = models.DecimalField(max_digits=15, decimal_places=2, verbose_name="Precio Unitario")
    
    # Impuestos
    iva_porcentaje = models.DecimalField(max_digits=5, decimal_places=2, default=21.00, verbose_name="IVA %")
    iva_monto = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name="Monto IVA")
    
    # Totales
    descuento = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name="Descuento")
    subtotal = models.DecimalField(max_digits=15, decimal_places=2, verbose_name="Subtotal")
    
    # Orden
    orden = models.IntegerField(default=1, verbose_name="Orden")
    
    class Meta:
        verbose_name = "Item de Comprobante"
        verbose_name_plural = "Items de Comprobante"
        ordering = ['orden']
    
    def __str__(self):
        return f"{self.descripcion[:50]} - {self.cantidad} x ${self.precio_unitario}"
    
    def save(self, *args, **kwargs):
        # Calcular subtotal e IVA
        self.subtotal = (self.cantidad * self.precio_unitario) - self.descuento
        self.iva_monto = self.subtotal * (self.iva_porcentaje / Decimal('100'))
        super().save(*args, **kwargs)
        
    
class DetalleComprobante(models.Model):
    """Items específicos dentro de un comprobante (productos, servicios, cursos)"""
    comprobante = models.ForeignKey(
        Comprobante, 
        on_delete=models.CASCADE, 
        related_name='detalles'
    )
    
    # Puede ser un producto, servicio, o curso
    productoServicio = models.ForeignKey(
        ProductoServicio, 
        on_delete=models.PROTECT, 
        null=True, 
        blank=True,
        verbose_name="Producto/Servicio"
    )
    
    curso = models.ForeignKey(
        'web.Curso',  # ← CADENA
        on_delete=models.PROTECT, 
        null=True, 
        blank=True,
        verbose_name="Curso"
    )
    
    descripcion = models.CharField(max_length=200, verbose_name="Descripción")
    cantidad = models.DecimalField(max_digits=10, decimal_places=2, default=1, verbose_name="Cantidad")
    precio_unitario = models.DecimalField(max_digits=15, decimal_places=2, verbose_name="Precio Unitario")
    subtotal = models.DecimalField(max_digits=15, decimal_places=2, verbose_name="Subtotal")
    
    # Para relacionar con pagos específicos si es necesario
    pago = models.ForeignKey(
        'Pago', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='detalles_comprobante',
        verbose_name="Pago relacionado"
    )
    
    class Meta:
        verbose_name = "Detalle de Comprobante"
        verbose_name_plural = "Detalles de Comprobantes"
    
    def __str__(self):
        return f"{self.descripcion} - {self.cantidad} x ${self.precio_unitario}"
    
    def save(self, *args, **kwargs):
        self.subtotal = self.cantidad * self.precio_unitario
        super().save(*args, **kwargs)
        

def crear_comprobante_multiple(request):
    """Crear comprobante que agrupa varios pagos"""
    if request.method == 'POST':
        # Obtener IDs de pagos seleccionados
        pago_ids = request.POST.getlist('pagos')
        
        # Crear comprobante
        comprobante = Comprobante.objects.create(
            tipo='FACTURA_B',  # o el tipo correspondiente
            # ... otros campos
            creado_por=request.user
        )
        
        # Asociar pagos al comprobante
        pagos = Pago.objects.filter(id__in=pago_ids)
        for pago in pagos:
            pago.comprobante = comprobante
            pago.save()
            
            # Crear detalle por cada pago
            DetalleComprobante.objects.create(
                comprobante=comprobante,
                descripcion=f"Pago #{pago.id} - {pago.alumno}",
                cantidad=1,
                precio_unitario=pago.monto,
                pago=pago
            )
        
        # Recalcular total del comprobante
        comprobante.calcular_totales()
        
        return redirect('facturacion:detalle_comprobante', uuid=comprobante.uuid)
    
    # GET: Mostrar pagos disponibles para agrupar
    pagos_pendientes = Pago.objects.filter(
        comprobante__isnull=True,
        confirmado=True
    ).select_related('alumno')
    
    return render(request, 'facturacion/comprobantes/crear_multiple.html', {
        'pagos_pendientes': pagos_pendientes
    })
    

class MovimientoStock(models.Model):
    """Registro de movimientos de stock"""
    TIPO_MOVIMIENTO = [
        ('INGRESO', 'Ingreso'),
        ('EGRESO', 'Egreso'),
        ('AJUSTE', 'Ajuste'),
        ('VENTA', 'Venta'),
        ('DEVOLUCION', 'Devolución'),
    ]
    
    producto = models.ForeignKey(ProductoServicio, on_delete=models.CASCADE, related_name='movimientos')
    tipo = models.CharField(max_length=20, choices=TIPO_MOVIMIENTO)
    cantidad = models.IntegerField()
    stock_anterior = models.IntegerField()
    stock_posterior = models.IntegerField()
    
    # Relaciones
    comprobante = models.ForeignKey(Comprobante, on_delete=models.SET_NULL, null=True, blank=True)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    
    observaciones = models.TextField(blank=True)
    fecha = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Movimiento de Stock"
        verbose_name_plural = "Movimientos de Stock"
        ordering = ['-fecha']
    
    def __str__(self):
        return f"{self.get_tipo_display()} - {self.producto.nombre} - {self.cantidad}"

class Caja(models.Model):
    """Control de cajas/puntos de venta"""
    ESTADO_CAJA = [
        ('ABIERTA', 'Abierta'),
        ('CERRADA', 'Cerrada'),
        ('EN_PROCESO', 'En Proceso de Cierre'),
    ]
    
    punto_venta = models.ForeignKey(PuntoVenta, on_delete=models.PROTECT)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    fecha_apertura = models.DateTimeField(auto_now_add=True)
    fecha_cierre = models.DateTimeField(null=True, blank=True)
    
    saldo_inicial = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    saldo_final = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    
    estado = models.CharField(max_length=20, choices=ESTADO_CAJA, default='ABIERTA')
    observaciones = models.TextField(blank=True)
    
    class Meta:
        verbose_name = "Caja"
        verbose_name_plural = "Cajas"
        ordering = ['-fecha_apertura']
    
    def __str__(self):
        return f"Caja {self.punto_venta} - {self.usuario.username} - {self.estado}"

class ConfiguracionFacturacion(models.Model):
    """Configuración general del sistema de facturación"""
    contribuyente_principal = models.ForeignKey(Contribuyente, on_delete=models.SET_NULL, null=True)
    dias_vencimiento_presupuesto = models.IntegerField(default=30)
    generar_pdf_automatico = models.BooleanField(default=True)
    notificar_stock_bajo = models.BooleanField(default=True)
    email_notificaciones = models.EmailField(blank=True)
    
    class Meta:
        verbose_name = "Configuración de Facturación"
        verbose_name_plural = "Configuraciones de Facturación"
    
    def __str__(self):
        return "Configuración General Facturación"
    
    def save(self, *args, **kwargs):
        # Asegurar que solo haya una configuración
        self.__class__.objects.exclude(id=self.id).delete()
        super().save(*args, **kwargs)
        
        

# ========== DETALLE DE PAGO ==========

class DetallePago(models.Model):
    MESES = [
        (1, 'Enero'), (2, 'Febrero'), (3, 'Marzo'), (4, 'Abril'),
        (5, 'Mayo'), (6, 'Junio'), (7, 'Julio'), (8, 'Agosto'),
        (9, 'Septiembre'), (10, 'Octubre'), (11, 'Noviembre'), (12, 'Diciembre'),
    ]
    TIPO_DETALLE = [
        ('CUOTA', 'Cuota Mensual'),
        ('MATRICULA', 'Matrícula'),
        ('CURSO', 'Curso'),
        ('PRODUCTO', 'Producto'),
        ('SERVICIO', 'Servicio'),
        ('OTRO', 'Otro'),
    ]

    pago = models.ForeignKey('Pago', on_delete=models.CASCADE, related_name='detalles')
    curso = models.ForeignKey('web.Curso', on_delete=models.PROTECT, null=True, blank=True)
    cuota = models.ForeignKey('web.CuotaAlumno', on_delete=models.SET_NULL, null=True, blank=True)
    producto = models.ForeignKey('ProductoServicio', on_delete=models.SET_NULL, null=True, blank=True)

    tipo = models.CharField(max_length=20, choices=TIPO_DETALLE, default='OTRO')
    descripcion = models.CharField(max_length=200)
    cantidad = models.IntegerField(default=1)
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=2)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    mes = models.PositiveSmallIntegerField(choices=MESES, null=True, blank=True)
    año = models.PositiveSmallIntegerField(null=True, blank=True)

    observaciones = models.CharField(max_length=100, blank=True, null=True)

    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)
    
    def save(self, *args, **kwargs):
        if not self.subtotal:
            self.subtotal = self.cantidad * self.precio_unitario
        super().save(*args, **kwargs)
    
   
# ========== SEÑALES Y MÉTODOS UTILITARIOS ==========

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.db import transaction

@receiver(post_save, sender=ItemComprobante)
def actualizar_stock_desde_item(sender, instance, created, **kwargs):
    """Actualiza stock cuando se crea/modifica un item de comprobante"""
    if instance.producto and instance.producto.maneja_stock:
        if instance.comprobante.estado in ['ACEPTADO_ARCA', 'IMPRESO']:
            # Solo actualizar stock para comprobantes confirmados
            if instance.comprobante.tipo in ['FACTURA_A', 'FACTURA_B', 'FACTURA_C', 'REMITO']:
                # Registrar movimiento de stock
                with transaction.atomic():
                    producto = instance.producto
                    cantidad = int(instance.cantidad)
                    
                    # Crear movimiento
                    MovimientoStock.objects.create(
                        producto=producto,
                        tipo='VENTA',
                        cantidad=cantidad,
                        stock_anterior=producto.stock_actual,
                        stock_posterior=producto.stock_actual - cantidad,
                        comprobante=instance.comprobante,
                        usuario=instance.comprobante.creado_por,
                        observaciones=f"Venta comprobante {instance.comprobante.numero_completo}"
                    )
                    
                    # Actualizar stock
                    producto.stock_actual -= cantidad
                    producto.save()

@receiver(pre_save, sender=ProductoServicio)
def notificar_stock_bajo(sender, instance, **kwargs):
    """Notificar cuando el stock está por debajo del mínimo"""
    if instance.pk:
        original = ProductoServicio.objects.get(pk=instance.pk)
        if (original.stock_actual > instance.stock_minimo and 
            instance.stock_actual <= instance.stock_minimo and
            instance.maneja_stock):
            
            # Crear notificación
            from web.models import Notificacion
            Notificacion.objects.create(
                titulo=f"Stock Bajo: {instance.nombre}",
                mensaje=f"El producto {instance.nombre} tiene stock bajo: {instance.stock_actual} unidades (mínimo: {instance.stock_minimo})",
                usuario_destino=settings.AUTH_USER_MODEL.objects.filter(is_superuser=True).first(),
                prioridad='MEDIA',
                tipo=Notificacion.objects.filter(nombre='Stock').first()
            )
            
            
class HistorialContactoMora(models.Model):
    """Registro de contactos con alumnos en mora"""
    TIPO_CONTACTO_CHOICES = [
        ('TELEFONICO', 'Telefónico'),
        ('EMAIL', 'Email'),
        ('PRESENCIAL', 'Presencial'),
        ('WHATSAPP', 'WhatsApp'),
        ('OTRO', 'Otro'),
    ]
    
    RESULTADO_CHOICES = [
        ('CONTACTADO', 'Contactado'),
        ('NO_CONTESTA', 'No contesta'),
        ('NUMERO_INCORRECTO', 'Número incorrecto'),
        ('ACUERDO_PAGO', 'Acuerdo de pago'),
        ('PROMESA_PAGO', 'Promesa de pago'),
        ('RECHAZADO', 'Rechazado'),
        ('OTRO', 'Otro'),
    ]
    
    alumno = models.ForeignKey('web.Alumno', on_delete=models.CASCADE)
    usuario = models.ForeignKey(User, on_delete=models.CASCADE)
    tipo_contacto = models.CharField(max_length=20, choices=TIPO_CONTACTO_CHOICES)
    resultado = models.CharField(max_length=20, choices=RESULTADO_CHOICES)
    observaciones = models.TextField(blank=True)
    proximo_contacto = models.DateField(null=True, blank=True)
    fecha_contacto = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-fecha_contacto']
        verbose_name = 'Historial de Contacto Mora'
        verbose_name_plural = 'Historial de Contactos Mora'
    
    def __str__(self):
        return f"{self.alumno.nombre_completo()} - {self.get_tipo_contacto_display()} - {self.fecha_contacto.strftime('%d/%m/%Y')}"

class Egreso(models.Model):
    """Modelo para registrar gastos, devoluciones, etc."""
    CATEGORIAS = [
        ('DEVOLUCION', 'Devolución'),
        ('GASTO', 'Gasto'),
        ('COMPRA', 'Compra de insumos'),
        ('MANTENIMIENTO', 'Mantenimiento'),
        ('SERVICIO', 'Servicio'),
        ('OTRO', 'Otro'),
    ]
    concepto = models.CharField(max_length=200, verbose_name="Concepto")
    monto = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Monto")
    fecha = models.DateTimeField(default=timezone.now, verbose_name="Fecha")
    categoria = models.CharField(max_length=20, choices=CATEGORIAS, default='OTRO', verbose_name="Categoría")
    comprobante = models.ForeignKey('Comprobante', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Comprobante asociado")
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, verbose_name="Usuario")
    observaciones = models.TextField(blank=True, verbose_name="Observaciones")

    class Meta:
        verbose_name = "Egreso"
        verbose_name_plural = "Egresos"
        ordering = ['-fecha']

    def __str__(self):
        return f"{self.concepto} - ${self.monto} ({self.fecha.strftime('%d/%m/%Y')})"
    
# # Agregar campo al modelo Alumno
# class Alumno(models.Model):
#     # ... campos existentes ...
    
#     # Nuevo campo para seguimiento de moras
#     ultimo_contacto_mora = models.DateTimeField(null=True, blank=True, verbose_name='Último contacto por mora')
    
#     def curso_actual(self):
#         """Obtener el curso actual del alumno"""
#         inscripcion_activa = self.inscripcion_set.filter(activa=True).first()
#         return inscripcion_activa.curso if inscripcion_activa else None