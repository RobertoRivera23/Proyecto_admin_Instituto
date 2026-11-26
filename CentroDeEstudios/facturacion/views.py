from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.views.generic import ListView, DetailView, CreateView, UpdateView
from django.urls import reverse_lazy
from django.db.models import Sum, Count, Q
from django.utils import timezone
from datetime import datetime, timedelta
from django.forms import model_to_dict
from django.db import transaction
import json
from .utils import get_or_create_default_contribuyente

from .models import *
from .forms import *
from .services.arca_service import ArcaService
from .services.pdf_service import PDFService
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill
import io
from web.decorators import personal_required, es_coordinador
from web.views import (
    seguimiento_moras,
    reporte_moras_pdf,
    obtener_detalle_alumno,
    obtener_cuotas_alumno,
    marcar_cuota_pagada,
    contactar_alumno_mora,
    generar_notificaciones_mora_manual,
    exportar_moras_excel
)
from facturacion.models import Pago, Comprobante, Contribuyente, ProductoServicio
from web.models import Alumno, CuotaAlumno, Curso

# ========== VISTAS DE COMPROBANTES ==========

@login_required
@permission_required('facturacion.puede_emitir_comprobante', raise_exception=True)
def crear_comprobante(request):
    """Vista para crear un nuevo comprobante (alumno o tercero)"""
    if request.method == 'POST':
        form = ComprobanteForm(request.POST)
        formset = ItemComprobanteFormSet(request.POST)

        if form.is_valid() and formset.is_valid():
            # Determinar si es alumno o tercero
            es_alumno = request.POST.get('es_alumno') == 'on'

            # Validar y preparar datos del cliente
            if es_alumno:
                alumno = form.cleaned_data.get('alumno')
                if not alumno:
                    form.add_error('alumno', 'Debe seleccionar un alumno')
                    # No continuar
                else:
                    # Usar datos del alumno para los campos del cliente
                    cliente_tipo_documento = 'DNI'  # o el que corresponda
                    cliente_numero_documento = alumno.dni or ''
                    cliente_razon_social = alumno.nombre_completo()
                    cliente_domicilio = alumno.direccion or ''
                    cliente_email = alumno.mail or ''
                    cliente_condicion_iva = 'CF'  # valor por defecto, podrías tenerlo en alumno
            else:
                # Obtener datos manuales del formulario
                cliente_tipo_documento = form.cleaned_data.get('cliente_tipo_documento')
                cliente_numero_documento = form.cleaned_data.get('cliente_numero_documento')
                cliente_razon_social = form.cleaned_data.get('cliente_razon_social')
                cliente_domicilio = form.cleaned_data.get('cliente_domicilio', '')
                cliente_email = form.cleaned_data.get('cliente_email', '')
                cliente_condicion_iva = form.cleaned_data.get('cliente_condicion_iva', 'CF')

                # Validaciones mínimas
                if not cliente_numero_documento:
                    form.add_error('cliente_numero_documento', 'El número de documento es obligatorio')
                if not cliente_razon_social:
                    form.add_error('cliente_razon_social', 'El nombre/razón social es obligatorio')

                # Validar que el DNI no exista en Alumno (opcional, según requerimiento)
                if cliente_numero_documento and Alumno.objects.filter(dni=cliente_numero_documento).exists():
                    form.add_error('cliente_numero_documento', 
                                   f'El DNI {cliente_numero_documento} ya corresponde a un alumno registrado. Si es el mismo, seleccione "Alumno" en lugar de "Tercero".')

                alumno = None  # No hay alumno asociado

            # Si hay errores, renderizar de nuevo
            if form.errors:
                return render(request, 'facturacion/comprobantes/crear.html', {
                    'form': form,
                    'formset': formset,
                    'contribuyentes': Contribuyente.objects.filter(activo=True),
                    'productos': ProductoServicio.objects.filter(activo=True),
                })

            # Crear comprobante (sin guardar aún)
            comprobante = form.save(commit=False)
            comprobante.creado_por = request.user

            # Asignar alumno si existe
            if es_alumno:
                comprobante.alumno = alumno

            # Asignar datos del cliente (provengan de alumno o manual)
            comprobante.cliente_tipo_documento = cliente_tipo_documento
            comprobante.cliente_numero_documento = cliente_numero_documento
            comprobante.cliente_razon_social = cliente_razon_social
            comprobante.cliente_domicilio = cliente_domicilio
            comprobante.cliente_email = cliente_email
            comprobante.cliente_condicion_iva = cliente_condicion_iva

            # Guardar comprobante
            comprobante.save()

            # Guardar items (formset)
            formset.instance = comprobante
            formset.save()

            # Calcular totales
            comprobante.calcular_totales()
            comprobante.save()

            messages.success(request, 'Comprobante creado exitosamente')
            return redirect('facturacion:preview_comprobante', uuid=comprobante.uuid)

    else:
        # GET: inicializar formulario
        initial = {
            'fecha_emision': timezone.now().date(),
            'contribuyente': Contribuyente.objects.filter(activo=True).first(),
        }
        form = ComprobanteForm(initial=initial)
        formset = ItemComprobanteFormSet()

    return render(request, 'facturacion/comprobantes/crear.html', {
        'form': form,
        'formset': formset,
        'contribuyentes': Contribuyente.objects.filter(activo=True),
        'productos': ProductoServicio.objects.filter(activo=True),
    })

@login_required
def preview_comprobante(request, uuid):
    """Vista previa antes de confirmar el comprobante"""
    comprobante = get_object_or_404(Comprobante, uuid=uuid)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'confirmar':
            # Generar PDF
            PDFService.generar_comprobante_pdf(comprobante)
            
            # Enviar a ARCA si está marcado
            if comprobante.enviar_arca and comprobante.contribuyente.arca_habilitado:
                arca_service = ArcaService(comprobante.contribuyente)
                success, message = arca_service.emitir_comprobante(comprobante)
                
                if success:
                    messages.success(request, f'Comprobante enviado a ARCA: {message}')
                    comprobante.estado = 'ACEPTADO_ARCA'
                else:
                    messages.error(request, f'Error ARCA: {message}')
                    comprobante.estado = 'RECHAZADO_ARCA'
            else:
                comprobante.estado = 'IMPRESO'
            
            comprobante.save()
            return redirect('facturacion:detalle_comprobante', uuid=comprobante.uuid)
        
        elif action == 'editar':
            return redirect('facturacion:editar_comprobante', uuid=comprobante.uuid)
    
    return render(request, 'facturacion/comprobantes/preview.html', {
        'comprobante': comprobante,
    })

@login_required
def detalle_comprobante(request, uuid):
    """Detalle completo del comprobante"""
    comprobante = get_object_or_404(Comprobante, uuid=uuid)
    
    return render(request, 'facturacion/comprobantes/detalle.html', {
        'comprobante': comprobante,
    })

@login_required
def imprimir_comprobante(request, uuid):
    """Imprimir comprobante"""
    comprobante = get_object_or_404(Comprobante, uuid=uuid)
    
    if comprobante.pdf:
        response = HttpResponse(comprobante.pdf.read(), content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="{comprobante.numero_completo}.pdf"'
        return response
    
    messages.error(request, 'El PDF no está disponible')
    return redirect('facturacion:detalle_comprobante', uuid=uuid)

class ListaComprobantesView(ListView):
    model = Comprobante
    template_name = 'facturacion/comprobantes/listar.html'
    context_object_name = 'comprobantes'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = Comprobante.objects.select_related(
            'contribuyente', 'punto_venta', 'creado_por'
        ).order_by('-fecha_emision', '-numero')
        
        # Filtros
        tipo = self.request.GET.get('tipo')
        if tipo:
            queryset = queryset.filter(tipo=tipo)
        
        estado = self.request.GET.get('estado')
        if estado:
            queryset = queryset.filter(estado=estado)
        
        fecha_desde = self.request.GET.get('fecha_desde')
        if fecha_desde:
            queryset = queryset.filter(fecha_emision__gte=fecha_desde)
        
        fecha_hasta = self.request.GET.get('fecha_hasta')
        if fecha_hasta:
            queryset = queryset.filter(fecha_emision__lte=fecha_hasta)
        
        contribuyente = self.request.GET.get('contribuyente')
        if contribuyente:
            queryset = queryset.filter(contribuyente_id=contribuyente)
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['contribuyentes'] = Contribuyente.objects.filter(activo=True)
        context['total_ventas'] = self.get_queryset().aggregate(Sum('total'))['total__sum'] or 0
        return context

# ========== VISTAS DE PAGOS ==========
# ========== VISTAS DE PAGOS (COMPLETAS) ==========

@login_required
@personal_required
def listar_pagos(request):
    """Listar todos los pagos con filtros - Reemplaza la vista actual si existe"""
    try:
        # Filtros
        fecha_desde = request.GET.get('fecha_desde', '')
        fecha_hasta = request.GET.get('fecha_hasta', '')
        alumno_filter = request.GET.get('alumno', '')
        metodo_pago_filter = request.GET.get('metodo_pago', '')
        estado_filter = request.GET.get('estado', '')
        
        # Consulta base
        pagos = Pago.objects.select_related('alumno', 'cuota', 'usuario_registro').order_by('-fecha_pago', '-id')
        
        # Aplicar filtros
        if fecha_desde:
            try:
                fecha_desde_obj = datetime.strptime(fecha_desde, '%Y-%m-%d').date()
                pagos = pagos.filter(fecha_pago__gte=fecha_desde_obj)
            except ValueError:
                fecha_desde = ''
        
        if fecha_hasta:
            try:
                fecha_hasta_obj = datetime.strptime(fecha_hasta, '%Y-%m-%d').date()
                pagos = pagos.filter(fecha_pago__lte=fecha_hasta_obj)
            except ValueError:
                fecha_hasta = ''
        
        if alumno_filter:
            pagos = pagos.filter(
                Q(alumno__nombre__icontains=alumno_filter) |
                Q(alumno__apellido__icontains=alumno_filter) |
                Q(alumno__dni__icontains=alumno_filter)
            )
        
        if metodo_pago_filter:
            metodo_pago_filter = metodo_pago_filter.upper()
            pagos = pagos.filter(metodo_pago=metodo_pago_filter)
            
            
        if estado_filter:
            if estado_filter == 'confirmados':
                pagos = pagos.filter(confirmado=True)
            elif estado_filter == 'pendientes':
                pagos = pagos.filter(confirmado=False)
        
        # Estadísticas
        hoy = timezone.now().date()
        inicio_mes = hoy.replace(day=1)
        inicio_anio = hoy.replace(month=1, day=1)
        
        # Total recaudado (todos los pagos confirmados)
        total_recaudado = Pago.objects.filter(confirmado=True).aggregate(
            total=Sum('monto')
        )['total'] or Decimal('0')
        
        # Pagos hoy
        pagos_hoy = Pago.objects.filter(fecha_pago=hoy, confirmado=True).count()
        monto_hoy = Pago.objects.filter(fecha_pago=hoy, confirmado=True).aggregate(
            total=Sum('monto')
        )['total'] or Decimal('0')
        
        # Pagos este mes
        pagos_mes = Pago.objects.filter(fecha_pago__gte=inicio_mes, confirmado=True).count()
        monto_mes = Pago.objects.filter(fecha_pago__gte=inicio_mes, confirmado=True).aggregate(
            total=Sum('monto')
        )['total'] or Decimal('0')
        
        # Pagos este año
        pagos_anio = Pago.objects.filter(fecha_pago__gte=inicio_anio, confirmado=True).count()
        monto_anio = Pago.objects.filter(fecha_pago__gte=inicio_anio, confirmado=True).aggregate(
            total=Sum('monto')
        )['total'] or Decimal('0')
        
        # Deuda activa (cuotas pendientes)
        from web.models import CuotaAlumno
        deuda_activa = CuotaAlumno.objects.filter(
        pagada=False,
        fecha_vencimiento__lt=hoy,
        inscripcion__alumno__activo=True
        ).aggregate(total=Sum('monto'))['total'] or Decimal('0')
        
        # Métodos de pago más utilizados
        metodos_pago = Pago.objects.filter(confirmado=True).values('metodo_pago').annotate(
            total=Count('id'),
            monto_total=Sum('monto')
        ).order_by('-monto_total')
        
        # Paginación
        from django.core.paginator import Paginator
        paginator = Paginator(pagos, 20)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        
        context = {
            'page_obj': page_obj,
            'pagos': page_obj,
            'total_recaudado': total_recaudado,
            'pagos_hoy': pagos_hoy,
            'monto_hoy': monto_hoy,
            'pagos_mes': pagos_mes,
            'monto_mes': monto_mes,
            'pagos_anio': pagos_anio,
            'monto_anio': monto_anio,
            'deuda_activa': deuda_activa,
            'metodos_pago': metodos_pago,
            'fecha_desde': fecha_desde,
            'fecha_hasta': fecha_hasta,
            'alumno_filter': alumno_filter,
            'metodo_pago_filter': metodo_pago_filter,
            'estado_filter': estado_filter,
            'hoy': hoy,
        }
        
        return render(request, 'facturacion/pagos/listar.html', context)
        
    except Exception as e:
        messages.error(request, f'Error al cargar los pagos: {str(e)}')
        return render(request, 'facturacion/pagos/listar.html', {'error': str(e)})







@login_required
@personal_required
def registrar_pago(request):
    if request.method == 'POST':
        try:
            with transaction.atomic():
                # ----- Datos del pagador -----
                es_alumno = request.POST.get('es_alumno') == 'on'
                if es_alumno:
                    alumno_id = request.POST.get('alumno_id')
                    if not alumno_id:
                        raise ValueError("Debe seleccionar un alumno")
                    alumno = get_object_or_404(Alumno, id=alumno_id)
                    # Limpiar datos de tercero
                    tercero_nombre = tercero_apellido = tercero_dni = tercero_cuil = tercero_domicilio = ''
                else:
                    # Validar campos obligatorios del tercero
                    tercero_nombre = request.POST.get('tercero_nombre', '').strip()
                    tercero_apellido = request.POST.get('tercero_apellido', '').strip()
                    tercero_dni = request.POST.get('tercero_dni', '').strip()
                    if not all([tercero_nombre, tercero_apellido, tercero_dni]):
                        raise ValueError("Nombre, apellido y DNI del tercero son obligatorios")
                    # Opcionales
                    tercero_cuil = request.POST.get('tercero_cuil', '').strip()
                    tercero_domicilio = request.POST.get('tercero_domicilio', '').strip()
                    # Verificar que el DNI no pertenezca a un alumno existente
                    if Alumno.objects.filter(dni=tercero_dni).exists():
                        raise ValueError(f"El DNI {tercero_dni} ya corresponde a un alumno registrado")
                    alumno = None

                # ----- Datos del pago -----
                fecha_pago_str = request.POST.get('fecha_pago')
                if not fecha_pago_str:
                    raise ValueError("Fecha de pago es obligatoria")
                try:
                    fecha_pago = datetime.fromisoformat(fecha_pago_str)
                except ValueError:
                    fecha_pago = datetime.strptime(fecha_pago_str, '%Y-%m-%d')

                metodo_pago = request.POST.get('metodo_pago')
                referencia = request.POST.get('referencia', '')
                descripcion = request.POST.get('descripcion', '')
                confirmado = request.POST.get('confirmado') == 'on'

                # Crear pago con monto temporal 0 (luego se actualizará)
                pago = Pago.objects.create(
                    alumno=alumno,
                    tercero_nombre=tercero_nombre,
                    tercero_apellido=tercero_apellido,
                    tercero_dni=tercero_dni,
                    tercero_cuil=tercero_cuil,
                    tercero_domicilio=tercero_domicilio,
                    fecha_pago=fecha_pago,
                    metodo_pago=metodo_pago,
                    referencia=referencia,
                    descripcion=descripcion,
                    confirmado=confirmado,
                    monto=Decimal('0.00'),          # temporal
                    usuario_registro=request.user,
                    estado='CONFIRMADO' if confirmado else 'PENDIENTE'
                )

                # ----- Procesar detalles (vienen como JSON) -----
                detalles_json = request.POST.get('detalles', '[]')
                detalles_data = json.loads(detalles_json)

                total_calculado = Decimal('0.00')
                for det in detalles_data:
                    tipo = det.get('tipo', 'OTRO')
                    cantidad = Decimal(str(det.get('cantidad', 1)))
                    precio_unitario = Decimal(str(det.get('precio_unitario', 0)))
                    subtotal = cantidad * precio_unitario
                    total_calculado += subtotal

                    # Crear el detalle
                    detalle = DetallePago(
                        pago=pago,
                        tipo=tipo,
                        descripcion=det.get('descripcion', ''),
                        cantidad=cantidad,
                        precio_unitario=precio_unitario,
                        subtotal=subtotal,
                        observaciones=det.get('observaciones', '')
                    )

                    # Asignar mes/año (si vienen)
                    mes_val = det.get('mes')
                    if mes_val is not None and str(mes_val).strip():
                        try:
                            detalle.mes = int(float(mes_val))
                            print(f"DEBUG: mes_val = {mes_val!r}, tipo = {type(mes_val)}")
                            print(f"DEBUG: anio_val = {anio_val!r}, tipo = {type(anio_val)}")
                        except (ValueError, TypeError):
                            pass
                    else:
                        detalle.mes = None

                    # Asignar año (si viene y es número)
                    anio_val = det.get('año')
                    if anio_val is not None and str(anio_val).strip():
                        try:
                            detalle.año = int(float(anio_val))
                            print(f"DEBUG: mes_val = {mes_val!r}, tipo = {type(mes_val)}")
                            print(f"DEBUG: anio_val = {anio_val!r}, tipo = {type(anio_val)}")
                        except (ValueError, TypeError):
                            pass
                    else:
                        detalle.año = None
                    # Asignar relaciones según tipo
                    if tipo == 'CUOTA' and det.get('cuota_id'):
                        try:
                            detalle.cuota_id = int(det['cuota_id'])
                            if confirmado:
                                cuota = CuotaAlumno.objects.get(id=det['cuota_id'])
                                cuota.pagada = True
                                cuota.fecha_pago = fecha_pago
                                cuota.save()
                        except (ValueError, CuotaAlumno.DoesNotExist):
                            pass

                    elif tipo == 'CURSO' and det.get('curso_id'):
                        try:
                            detalle.curso_id = int(det['curso_id'])
                        except (ValueError, TypeError):
                            pass

                    elif tipo == 'PRODUCTO' and det.get('producto_id'):
                        try:
                            detalle.producto_id = int(det['producto_id'])
                        except (ValueError, TypeError):
                            pass

                    detalle.save()

                # ----- Actualizar el monto del pago con el total calculado -----
                pago.monto = total_calculado
                pago.save()

                messages.success(request, f'Pago registrado exitosamente por ${total_calculado}')
                return redirect('facturacion:detalle_pago', pago_id=pago.id)

        except Exception as e:
            logger.exception("Error en registrar_pago")
            messages.error(request, f'Error al registrar el pago: {str(e)}')
            return redirect('facturacion:registrar_pago')

    # GET
    hoy = timezone.now().date()
    return render(request, 'facturacion/pagos/registrar.html', {'hoy': hoy})


@login_required
@personal_required
def detalle_pago(request, pago_id):
    pago = get_object_or_404(Pago.objects.select_related('alumno', 'usuario_registro'), id=pago_id)
    detalles = pago.detalles.all()  # usa el related_name 'detalles'
    context = {
        'pago': pago,
        'detalles': detalles,
    }
    return render(request, 'facturacion/pagos/detalle.html', context)

# facturacion/views.py (fragmento editar_pago)
from django.forms import modelformset_factory

@login_required
@personal_required
def editar_pago(request, pago_id):
    pago = get_object_or_404(Pago.objects.select_related('alumno'), id=pago_id)
    if pago.estado == 'ANULADO':
        messages.error(request, 'No se puede editar un pago anulado.')
        return redirect('facturacion:listar_pagos')

    # 1. No permitir editar pagos confirmados
    if pago.confirmado:
        messages.error(request, 'No se puede editar un pago confirmado. Anule el pago si es necesario.')
        return redirect('facturacion:detalle_pago', pago_id=pago.id)

    DetalleFormSet = modelformset_factory(
        DetallePago,
        fields=('tipo', 'cantidad', 'precio_unitario', 'mes', 'año'),
        extra=1,
        can_delete=True,
    )

    # --- GET: cargar formulario inicial ---
    if request.method == 'GET':
        cuotas = []
        if pago.alumno:
            cuotas = CuotaAlumno.objects.filter(
                inscripcion__alumno=pago.alumno, pagada=False
            ).select_related('inscripcion')

        formset = DetalleFormSet(queryset=DetallePago.objects.filter(pago=pago).order_by('id'))
        context = {
            'pago': pago,
            'formset': formset,
            'alumnos': Alumno.objects.filter(activo=True).order_by('apellido', 'nombre'),
            'cursos': Curso.objects.filter(activo=True).order_by('nombre'),
            'productos': ProductoServicio.objects.filter(activo=True).order_by('nombre'),
            'cuotas': cuotas,
            'hoy': timezone.now().date(),
        }
        return render(request, 'facturacion/pagos/editar.html', context)

    # --- POST: procesar el formulario ---
    with transaction.atomic():
        # --- Datos del pagador ---
        es_alumno = request.POST.get('es_alumno') == 'on'
        if es_alumno:
            alumno_id = request.POST.get('alumno_id')
            pago.alumno = Alumno.objects.get(id=alumno_id) if alumno_id else None
            pago.tercero_nombre = pago.tercero_apellido = pago.tercero_dni = pago.tercero_cuil = pago.tercero_domicilio = ''
        else:
            pago.alumno = None
            pago.tercero_nombre = request.POST.get('tercero_nombre', '')
            pago.tercero_apellido = request.POST.get('tercero_apellido', '')
            pago.tercero_dni = request.POST.get('tercero_dni', '')
            pago.tercero_cuil = request.POST.get('tercero_cuil', '')
            pago.tercero_domicilio = request.POST.get('tercero_domicilio', '')

        # --- Datos del pago ---
        pago.fecha_pago = datetime.strptime(request.POST.get('fecha_pago'), '%Y-%m-%d').date()
        pago.metodo_pago = request.POST.get('metodo_pago')
        pago.referencia = request.POST.get('referencia', '')
        pago.descripcion = request.POST.get('descripcion', '')
        pago.confirmado = request.POST.get('confirmado') == 'on'
        pago.save()

        # --- Procesar formset de detalles ---
        formset = DetalleFormSet(request.POST, queryset=DetallePago.objects.filter(pago=pago))

        if formset.is_valid():
            instances = []
            for form in formset.forms:
                if form in formset.deleted_forms:
                    if form.instance.id:
                        form.instance.delete()
                    continue

                instance = form.save(commit=False)
                instance.pago = pago
                idx = formset.forms.index(form)

                # Asignar relaciones desde los campos extra
                instance.curso_id = request.POST.get(f'extra_curso_id_{idx}') or None
                instance.cuota_id = request.POST.get(f'extra_cuota_id_{idx}') or None
                instance.producto_id = request.POST.get(f'extra_producto_id_{idx}') or None
                instance.descripcion = request.POST.get(f'extra_descripcion_{idx}', '')
                instance.subtotal = instance.cantidad * instance.precio_unitario
                instance.save()
                instances.append(instance)

            # Recalcular total del pago
            total_pago = DetallePago.objects.filter(pago=pago).aggregate(total=Sum('subtotal'))['total'] or Decimal('0')
            pago.monto = total_pago
            pago.save()

            messages.success(request, 'Pago actualizado correctamente.')
            return redirect('facturacion:detalle_pago', pago_id=pago.id)

        else:
            # --- Error en el formset: volver a renderizar con datos actuales ---
            formset_errors = []
            for idx, form in enumerate(formset.forms):
                if form.errors:
                    formset_errors.append(f"Concepto {idx}: {form.errors}")
                    messages.error(request, f"Concepto {formset.forms.index(form)}: {form.errors}")

            cuotas = []
            if pago.alumno:
                cuotas = CuotaAlumno.objects.filter(
                    inscripcion__alumno=pago.alumno, pagada=False
                ).select_related('inscripcion')

            context = {
                'pago': pago,
                'formset': formset,
                'alumnos': Alumno.objects.filter(activo=True).order_by('apellido', 'nombre'),
                'cursos': Curso.objects.filter(activo=True).order_by('nombre'),
                'productos': ProductoServicio.objects.filter(activo=True).order_by('nombre'),
                'cuotas': cuotas,
                'hoy': timezone.now().date(),
                'formset_errors': formset_errors,
            }
            messages.error(request, 'Error en los detalles del pago. Verifique los datos.')
            return render(request, 'facturacion/pagos/editar.html', context)


@login_required
def generar_recibo(request, pago_id):
    pago = get_object_or_404(Pago, id=pago_id, confirmado=True, anulado=False)

    if pago.comprobante:
        return redirect('facturacion:imprimir_comprobante', uuid=pago.comprobante.uuid)

    # Obtener el contribuyente por defecto (Instituto Argentino de Capacitación Laboral)
    contribuyente = get_or_create_default_contribuyente()

    # Obtener punto de venta activo
    punto_venta = contribuyente.puntos_venta.filter(activo=True).first()
    if not punto_venta:
        punto_venta = PuntoVenta.objects.create(
            contribuyente=contribuyente,
            numero=1,
            descripcion='Punto de Venta Principal',
            activo=True
        )

    # Datos del cliente (evitar null)
    if pago.alumno:
        cliente_tipo_documento = 'DNI'
        cliente_numero_documento = pago.alumno.dni or ''
        cliente_razon_social = pago.alumno.nombre_completo()
        cliente_domicilio = pago.alumno.direccion or ''
        cliente_email = pago.alumno.mail or ''
    else:
        cliente_tipo_documento = 'DNI'
        cliente_numero_documento = pago.tercero_dni or ''
        cliente_razon_social = f"{pago.tercero_nombre} {pago.tercero_apellido}".strip()
        cliente_domicilio = pago.tercero_domicilio or ''
        cliente_email = ''

    # Asegurar que ningún campo quede como None
    cliente_numero_documento = cliente_numero_documento or ''
    cliente_razon_social = cliente_razon_social or 'Cliente sin nombre'
    cliente_domicilio = cliente_domicilio or ''
    cliente_email = cliente_email or ''

    # Crear comprobante tipo RECIBO
    comprobante = Comprobante.objects.create(
        tipo='RECIBO',
        punto_venta=punto_venta,
        fecha_emision=timezone.now().date(),
        contribuyente=contribuyente,
        cliente_tipo_documento=cliente_tipo_documento,
        cliente_numero_documento=cliente_numero_documento,
        cliente_razon_social=cliente_razon_social,
        cliente_domicilio=cliente_domicilio,
        cliente_email=cliente_email,
        condicion_venta='CONTADO',
        subtotal=pago.monto,
        iva=Decimal('0.00'),
        total=pago.monto,
        estado='IMPRESO',
        enviar_arca=False,
        alumno=pago.alumno,
        creado_por=request.user,
    )

    # Items del comprobante
    for detalle in pago.detalles.all():
        descripcion = detalle.descripcion
        if detalle.mes:
            descripcion += f" - Mes: {detalle.get_mes_display()}"
        if detalle.año:
            descripcion += f" {detalle.año}"

        ItemComprobante.objects.create(
            comprobante=comprobante,
            descripcion=descripcion,
            cantidad=detalle.cantidad,
            precio_unitario=detalle.precio_unitario,
            iva_porcentaje=0,
            subtotal=detalle.subtotal,
        )

    comprobante.calcular_totales()
    comprobante.save()

    pago.comprobante = comprobante
    pago.save()

    # Generar PDF
    PDFService.generar_comprobante_pdf(comprobante)

    messages.success(request, 'Recibo generado exitosamente')
    return redirect('facturacion:detalle_comprobante', uuid=comprobante.uuid)



@login_required
@permission_required('facturacion.puede_emitir_comprobante', raise_exception=True)
def emitir_factura_arca(request, pago_id):
    """Emite una factura electrónica ARCA para el pago"""
    pago = get_object_or_404(Pago, id=pago_id, confirmado=True, anulado=False)
    
    # Si ya tiene comprobante y es factura, redirigir
    if pago.comprobante and pago.comprobante.tipo.startswith('FACTURA'):
        return redirect('facturacion:detalle_comprobante', uuid=pago.comprobante.uuid)
    
    try:
        # Verificar si el alumno tiene CUIT/CUIL, si no, será consumidor final
        if pago.alumno.cuil or pago.alumno.cuit:
            tipo_doc = 'CUIT' if pago.alumno.cuit else 'CUIL'
            nro_doc = pago.alumno.cuit or pago.alumno.cuil
            condicion_iva = 'RI'  # O lo que corresponda según el alumno
        else:
            tipo_doc = 'DNI'
            nro_doc = pago.alumno.dni or '00000000'
            condicion_iva = 'CF'
        
        # Buscar contribuyente
        config = ConfiguracionFacturacion.objects.first()
        if not config or not config.contribuyente_principal:
            messages.error(request, 'No hay contribuyente configurado para facturación')
            return redirect('facturacion:detalle_pago', pago_id=pago.id)
        
        punto_venta = config.contribuyente_principal.puntos_venta.filter(activo=True).first()
        if not punto_venta:
            messages.error(request, 'No hay punto de venta activo')
            return redirect('facturacion:detalle_pago', pago_id=pago.id)
        
        # Crear comprobante (tipo FACTURA_B por defecto)
        comprobante = Comprobante.objects.create(
            tipo='FACTURA_B',
            punto_venta=punto_venta,
            fecha_emision=timezone.now().date(),
            contribuyente=config.contribuyente_principal,
            cliente_tipo_documento=tipo_doc,
            cliente_numero_documento=nro_doc,
            cliente_razon_social=pago.alumno.nombre_completo(),
            cliente_domicilio=pago.alumno.direccion or '',
            cliente_email=pago.alumno.mail or '',
            cliente_condicion_iva=condicion_iva,
            condicion_venta='CONTADO',
            subtotal=pago.monto,
            iva=Decimal('0.00'),  # Se calculará en items
            total=pago.monto,
            estado='BORRADOR',
            enviar_arca=True,
            alumno=pago.alumno,
            creado_por=request.user,
        )
        
        # Crear items del comprobante (agrupar por alícuota de IVA si es necesario)
        # Por simplicidad, creamos un item por cada detalle de pago
        for detalle in pago.detalles.all():
            # Determinar alícuota según el producto/curso
            iva_porcentaje = Decimal('21.00')  # Valor por defecto
            if detalle.producto:
                iva_porcentaje = detalle.producto.alicuota_iva
            elif detalle.curso:
                # Asumir 21% para cursos, o podrías tener un campo en Curso
                iva_porcentaje = Decimal('21.00')
            
            ItemComprobante.objects.create(
                comprobante=comprobante,
                descripcion=detalle.descripcion,
                cantidad=detalle.cantidad,
                precio_unitario=detalle.precio_unitario,
                iva_porcentaje=iva_porcentaje,
                subtotal=detalle.precio_total,
            )
        
        # Calcular IVA y totales
        comprobante.calcular_totales()
        comprobante.save()
        
        # Asociar al pago
        pago.comprobante = comprobante
        pago.save()
        
        # Redirigir a vista previa para confirmar envío a ARCA
        return redirect('facturacion:preview_comprobante', uuid=comprobante.uuid)
        
    except Exception as e:
        messages.error(request, f'Error al preparar factura: {str(e)}')
        return redirect('facturacion:detalle_pago', pago_id=pago.id)

@login_required
@personal_required
def confirmar_pago(request, pago_id):
    pago = get_object_or_404(Pago, id=pago_id)

    # Solo permitir confirmar si está pendiente y no anulado
    if pago.estado != 'PENDIENTE':
        messages.error(request, 'Solo se pueden confirmar pagos pendientes.')
        return redirect('facturacion:detalle_pago', pago_id=pago.id)

    try:
        pago.confirmado = True
        pago.estado = 'CONFIRMADO'
        pago.fecha_confirmacion = timezone.now()
        pago.usuario_confirmacion = request.user
        pago.save()

        # Si tiene cuota asociada, marcarla como pagada
        if pago.cuota:
            pago.cuota.pagada = True
            pago.cuota.fecha_pago = pago.fecha_pago
            pago.cuota.save()

        messages.success(request, 'Pago confirmado exitosamente')

    except Exception as e:
        messages.error(request, f'Error al confirmar el pago: {str(e)}')

    return redirect('facturacion:detalle_pago', pago_id=pago.id)


@login_required
@personal_required
def anular_pago(request, pago_id):
    pago = get_object_or_404(Pago.objects.select_related('alumno', 'cuota'), id=pago_id)

    if request.method == 'POST':
        motivo = request.POST.get('motivo_anulacion', '').strip()
        confirmado = request.POST.get('confirmar_anulacion') == 'on'

        if not motivo:
            messages.error(request, 'Debe especificar un motivo para la anulación.')
            return redirect('facturacion:anular_pago', pago_id=pago.id)

        if not confirmado:
            messages.error(request, 'Debe confirmar la anulación marcando el checkbox.')
            return redirect('facturacion:anular_pago', pago_id=pago.id)

        try:
            # Marcar pago como anulado
            pago.anulado = True
            pago.confirmado = False
            pago.estado = 'ANULADO'          # ← NUEVO
            pago.motivo_anulacion = motivo
            pago.fecha_anulacion = timezone.now()
            pago.usuario_anulacion = request.user
            pago.save()

            # Si tenía una cuota asociada, marcar como no pagada
            if pago.cuota:
                pago.cuota.pagada = False
                pago.cuota.save()
                messages.info(request, f'Cuota {pago.cuota.mes_correspondiente} marcada como no pagada')

            # Registrar en historial de auditoría
            HistorialPago.objects.create(
                pago=pago,
                usuario=request.user,
                accion='ANULAR',
                descripcion=f'Pago anulado: {motivo}'
            )

            messages.success(request, f'Pago #{pago.id} anulado exitosamente')
            return redirect('facturacion:detalle_pago', pago_id=pago.id)

        except Exception as e:
            messages.error(request, f'Error al anular el pago: {str(e)}')
            return redirect('facturacion:anular_pago', pago_id=pago.id)

    # GET: mostrar página de confirmación
    return render(request, 'facturacion/pagos/anular.html', {'pago': pago})



from .models import Pago, DetallePago, Egreso


@login_required
@personal_required
def reporte_pagos(request):
    """
    Reporte de pagos con:
    - KPIs: ingresos del día, del mes actual, egresos del período, total neto, alumnos que pagaron.
    - Filtros por período, tipo de reporte, curso, alumno y tipo de detalle.
    - Tabla con detalles de cada pago (línea por línea, mostrando curso específico).
    - Gráficos de evolución y métodos de pago.
    - Top 10 alumnos con sus cursos.
    """
    try:
        # --- Parámetros GET ---
        periodo = request.GET.get('periodo', 'mes')
        tipo_reporte = request.GET.get('tipo_reporte', 'general')
        curso_id = request.GET.get('curso_id', '')
        alumno_id = request.GET.get('alumno_id', '')
        tipo_detalle = request.GET.get('tipo_detalle', '')

        hoy = timezone.now().date()

        # --- Rango de fechas según período ---
        if periodo == 'hoy':
            fecha_desde = fecha_hasta = hoy
        elif periodo == 'semana':
            fecha_desde = hoy - timedelta(days=7)
            fecha_hasta = hoy
        elif periodo == 'mes':
            fecha_desde = hoy.replace(day=1)
            fecha_hasta = hoy
        elif periodo == 'trimestre':
            fecha_desde = hoy - timedelta(days=90)
            fecha_hasta = hoy
        elif periodo == 'anio':
            fecha_desde = hoy.replace(month=1, day=1)
            fecha_hasta = hoy
        else:  # personalizado
            fecha_desde_str = request.GET.get('fecha_desde', '')
            fecha_hasta_str = request.GET.get('fecha_hasta', '')
            if fecha_desde_str:
                fecha_desde = datetime.strptime(fecha_desde_str, '%Y-%m-%d').date()
            else:
                fecha_desde = hoy - timedelta(days=30)
            if fecha_hasta_str:
                fecha_hasta = datetime.strptime(fecha_hasta_str, '%Y-%m-%d').date()
            else:
                fecha_hasta = hoy

        # --- Consulta base de detalles de pago (ingresos) ---
        # Filtramos pagos confirmados, no anulados, y dentro del rango de fechas.
        detalles = DetallePago.objects.filter(
            pago__fecha_pago__date__gte=fecha_desde,
            pago__fecha_pago__date__lte=fecha_hasta,
            pago__anulado=False,
            pago__confirmado=True,
            pago__estado='CONFIRMADO'
        ).select_related(
            'pago__alumno',   # para acceso rápido al alumno
            'curso',          # para mostrar el curso en la tabla
            'producto'        # para futuras expansiones
        )

        # Filtros adicionales
        if curso_id:
            detalles = detalles.filter(curso_id=curso_id)
        if alumno_id:
            detalles = detalles.filter(pago__alumno_id=alumno_id)
        if tipo_detalle:
            detalles = detalles.filter(tipo=tipo_detalle)

        # --- KPIs ---
        # Ingresos del día (pagos de hoy)
        ingresos_dia = DetallePago.objects.filter(
            pago__fecha_pago__date=hoy,
            pago__confirmado=True,
            pago__anulado=False,
            pago__estado='CONFIRMADO'
        ).aggregate(total=Sum('subtotal'))['total'] or Decimal('0')

        # Ingresos del mes actual (desde primer día hasta hoy)
        primer_dia_mes = hoy.replace(day=1)
        ingresos_mes = DetallePago.objects.filter(
            pago__fecha_pago__date__gte=primer_dia_mes,
            pago__fecha_pago__date__lte=hoy,
            pago__confirmado=True,
            pago__anulado=False,
            pago__estado='CONFIRMADO'
        ).aggregate(total=Sum('subtotal'))['total'] or Decimal('0')

        # Ingresos del período seleccionado
        ingresos_periodo = detalles.aggregate(total=Sum('subtotal'))['total'] or Decimal('0')

        # Egresos del período (usando modelo Egreso)
        egresos_periodo = Egreso.objects.filter(
            fecha__date__gte=fecha_desde,
            fecha__date__lte=fecha_hasta
        ).aggregate(total=Sum('monto'))['total'] or Decimal('0')

        total_neto = ingresos_periodo - egresos_periodo

        # Cantidad de alumnos distintos que pagaron en el período
        alumnos_pagaron = detalles.filter(pago__alumno__isnull=False).values('pago__alumno').distinct().count()

        # --- Estadísticas generales (compatibilidad) ---
        total_recaudado = ingresos_periodo
        total_pagos = detalles.values('pago').distinct().count()        # facturas únicas
        pagos_confirmados = detalles.count()                            # líneas de detalle
        promedio_pago = total_recaudado / total_pagos if total_pagos > 0 else Decimal('0')
        total_alumnos = alumnos_pagaron

        # --- Métodos de pago (agrupados) ---
        metodos = detalles.values('pago__metodo_pago').annotate(
            total=Sum('subtotal'),
            cantidad=Count('pago__id', distinct=True)
        ).order_by('-total')

        # --- Gráfico de evolución (últimos 30 días) ---
        fechas = []
        montos = []
        for i in range(30):
            fecha = fecha_hasta - timedelta(days=30 - i)
            total_dia = DetallePago.objects.filter(
                pago__fecha_pago__date=fecha,
                pago__anulado=False,
                pago__confirmado=True,
                pago__estado='CONFIRMADO'
            ).aggregate(total=Sum('subtotal'))['total'] or 0
            fechas.append(fecha.strftime('%d/%m'))
            montos.append(float(total_dia))

        # --- Gráfico de torta de métodos ---
        metodos_labels = []
        metodos_data = []
        for metodo in metodos:
            metodos_labels.append(
                dict(Pago.METODOS_PAGO).get(metodo['pago__metodo_pago'], metodo['pago__metodo_pago'])
            )
            metodos_data.append(float(metodo['total']))

        # --- Resumen diario (últimos 7 días) ---
        resumen_diario = []
        for i in range(7):
            fecha = fecha_hasta - timedelta(days=6 - i)
            detalles_dia = detalles.filter(pago__fecha_pago__date=fecha)
            total_dia = detalles_dia.aggregate(total=Sum('subtotal'))['total'] or Decimal('0')
            total_pagos_dia = detalles_dia.values('pago').distinct().count()
            alumnos_dia = detalles_dia.filter(pago__alumno__isnull=False).values('pago__alumno').distinct().count()
            metodo_principal = detalles_dia.values('pago__metodo_pago').annotate(
                count=Count('pago__id', distinct=True)
            ).order_by('-count').first()

            resumen_diario.append({
                'fecha': fecha,
                'monto_total': total_dia,
                'total_pagos': total_pagos_dia,
                'alumnos_unicos': alumnos_dia,
                'promedio': total_dia / total_pagos_dia if total_pagos_dia > 0 else Decimal('0'),
                'metodo_principal': dict(Pago.METODOS_PAGO).get(metodo_principal['pago__metodo_pago'], 'N/A') if metodo_principal else 'N/A',
                'metodo_principal_color': 'primary' if metodo_principal and metodo_principal['pago__metodo_pago'] == 'efectivo' else
                                         'success' if metodo_principal and metodo_principal['pago__metodo_pago'] == 'transferencia' else 'secondary'
            })

        # --- Top 10 alumnos (con suma de pagos y lista de cursos) ---
        top_alumnos = detalles.filter(pago__alumno__isnull=False).values(
            'pago__alumno__id',
            'pago__alumno__nombre',
            'pago__alumno__apellido',
            'pago__alumno__dni'
        ).annotate(
            total_pagado=Sum('subtotal'),
            total_pagos=Count('pago__id', distinct=True)
        ).order_by('-total_pagado')[:10]

        # Enriquecer cada alumno con nombre completo y lista de cursos
        for alumno in top_alumnos:
            alumno_obj = Alumno.objects.get(id=alumno['pago__alumno__id'])
            alumno['nombre_completo'] = f"{alumno['pago__alumno__nombre']} {alumno['pago__alumno__apellido']}"

            # Obtener los cursos en los que pagó en el período (desde detalles)
            cursos_pagados = detalles.filter(pago__alumno=alumno_obj).values_list('curso__nombre', flat=True).distinct()
            alumno['cursos'] = ', '.join(cursos_pagados) if cursos_pagados else "Sin curso"

        # --- Datos para filtros (selects) ---
        cursos = Curso.objects.filter(activo=True)
        alumnos = Alumno.objects.filter(activo=True).order_by('apellido', 'nombre')[:50]
        tipos_detalle = DetallePago.TIPO_DETALLE

        # --- Detalles para la tabla (limitamos a 200 para rendimiento) ---
        detalles_tabla = detalles[:200]  # puedes ajustar el límite o paginar

        context = {
            # Parámetros para mantener en los filtros
            'periodo': periodo,
            'tipo_reporte': tipo_reporte,
            'tipo_detalle': tipo_detalle,
            'fecha_desde': fecha_desde,
            'fecha_hasta': fecha_hasta,
            'curso_id': curso_id,
            'alumno_id': alumno_id,

            # KPIs
            'ingresos_dia': ingresos_dia,
            'ingresos_mes': ingresos_mes,
            'egresos_periodo': egresos_periodo,
            'total_neto': total_neto,
            'alumnos_pagaron': alumnos_pagaron,

            # Estadísticas generales (compatibilidad)
            'total_recaudado': total_recaudado,
            'total_pagos': total_pagos,
            'pagos_confirmados': pagos_confirmados,
            'promedio_pago': promedio_pago,
            'total_alumnos': total_alumnos,

            # Métodos y gráficos
            'metodos': metodos,
            'fechas': json.dumps(fechas),
            'montos': json.dumps(montos),
            'metodos_labels': json.dumps(metodos_labels),
            'metodos_data': json.dumps(metodos_data),

            'resumen_diario': resumen_diario,
            'top_alumnos': top_alumnos,

            # Datos para selects
            'cursos': cursos,
            'alumnos': alumnos,
            'tipos_detalle': tipos_detalle,

            # Tabla de detalle (líneas de pago)
            'detalles': detalles_tabla,
        }

        return render(request, 'facturacion/pagos/reporte.html', context)

    except Exception as e:
        messages.error(request, f'Error al generar el reporte: {str(e)}')
        return render(request, 'facturacion/pagos/reporte.html', {'error': str(e)})
    

@login_required
@personal_required
def exportar_pagos(request):
    """Exportar pagos a Excel"""
    try:
        # Filtros (mismos que listar_pagos)
        fecha_desde = request.GET.get('fecha_desde', '')
        fecha_hasta = request.GET.get('fecha_hasta', '')
        alumno_filter = request.GET.get('alumno', '')
        metodo_pago_filter = request.GET.get('metodo_pago', '')
        
        # Consulta base
        pagos = Pago.objects.select_related('alumno', 'cuota').order_by('-fecha_pago', '-id')
        
        # Aplicar filtros (igual que en listar_pagos)
        if fecha_desde:
            fecha_desde_obj = datetime.strptime(fecha_desde, '%Y-%m-%d').date()
            pagos = pagos.filter(fecha_pago__gte=fecha_desde_obj)
        
        if fecha_hasta:
            fecha_hasta_obj = datetime.strptime(fecha_hasta, '%Y-%m-%d').date()
            pagos = pagos.filter(fecha_pago__lte=fecha_hasta_obj)
        
        if alumno_filter:
            pagos = pagos.filter(
                Q(alumno__nombre__icontains=alumno_filter) |
                Q(alumno__apellido__icontains=alumno_filter) |
                Q(alumno__dni__icontains=alumno_filter)
            )
        
        if metodo_pago_filter:
            pagos = pagos.filter(metodo_pago=metodo_pago_filter)
        
        # Crear libro de Excel
        from openpyxl import Workbook
        from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
        from django.http import HttpResponse
        
        wb = Workbook()
        ws = wb.active
        ws.title = "Pagos"
        
        # Estilos
        header_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
        header_font = Font(color="FFFFFF", bold=True)
        border = Border(
            left=Side(style='thin'),
            right=Side(style='thin'),
            top=Side(style='thin'),
            bottom=Side(style='thin')
        )
        
        # Encabezados
        headers = ['ID', 'Fecha', 'Alumno', 'DNI', 'Monto', 'Método', 'Referencia', 'Confirmado', 'Descripción']
        ws.append(headers)
        
        # Aplicar estilos a encabezados
        for col in range(1, len(headers) + 1):
            cell = ws.cell(row=1, column=col)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal='center')
            cell.border = border
        
        # Datos
        row_num = 2
        for pago in pagos:
            ws.append([
                pago.id,
                pago.fecha_pago.strftime('%d/%m/%Y'),
                pago.alumno.nombre_completo(),
                pago.alumno.dni or '',
                float(pago.monto),
                pago.get_metodo_pago_display(),
                pago.referencia or '',
                'Sí' if pago.confirmado else 'No',
                pago.descripcion or ''
            ])
            
            # Aplicar bordes a la fila
            for col in range(1, len(headers) + 1):
                ws.cell(row=row_num, column=col).border = border
            
            row_num += 1
        
        # Ajustar anchos de columna
        column_widths = [8, 12, 30, 12, 12, 15, 20, 12, 30]
        for i, width in enumerate(column_widths, 1):
            ws.column_dimensions[chr(64 + i)].width = width
        
        # Crear respuesta
        from io import BytesIO
        output = BytesIO()
        wb.save(output)
        output.seek(0)
        
        # Nombre del archivo
        filename = f'pagos_export_{timezone.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
        
        response = HttpResponse(
            output.getvalue(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        return response
        
    except Exception as e:
        messages.error(request, f'Error exportando pagos: {str(e)}')
        return redirect('facturacion:listar_pagos')

# ========== VISTAS AUXILIARES PARA APIs ==========

@login_required
@personal_required
def obtener_detalle_alumno(request, alumno_id):
    """API para obtener detalles de un alumno (JSON) - Ya existe pero la adapto"""
    try:
        from web.models import Alumno
        alumno = get_object_or_404(Alumno, id=alumno_id)
        
        # Calcular deuda
        cuotas_pendientes = CuotaAlumno.objects.filter(
            alumno=alumno,
            pagada=False,
            fecha_vencimiento__lt=timezone.now().date()
        )
        
        total_deuda = cuotas_pendientes.aggregate(total=Sum('monto'))['total'] or Decimal('0')
        cuotas_vencidas = cuotas_pendientes.count()
        
        # Obtener cuotas pendientes
        cuotas_pendientes_list = []
        for cuota in CuotaAlumno.objects.filter(alumno=alumno, pagada=False).order_by('fecha_vencimiento'):
            cuotas_pendientes_list.append({
                'id': cuota.id,
                'descripcion': cuota.descripcion or f'Cuota {cuota.mes_correspondiente}',
                'monto': float(cuota.monto),
                'fecha_vencimiento': cuota.fecha_vencimiento.strftime('%d/%m/%Y'),
                'dias_vencido': max(0, (timezone.now().date() - cuota.fecha_vencimiento).days) if cuota.fecha_vencimiento < timezone.now().date() else 0
            })
        
        data = {
            'id': alumno.id,
            'nombre_completo': alumno.nombre_completo(),
            'dni': alumno.dni,
            'telefono': alumno.telefono,
            'email': alumno.email,
            'curso_actual': alumno.curso_actual().nombre if alumno.curso_actual() else 'Sin curso',
            'activo': alumno.activo,
            'total_deuda': float(total_deuda),
            'cuotas_vencidas': cuotas_vencidas,
            'cuotas_pendientes': cuotas_pendientes_list
        }
        
        return JsonResponse(data)
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

import logging
logger = logging.getLogger(__name__)

def obtener_cuotas_alumno(request, alumno_id):
    cuotas = CuotaAlumno.objects.filter(
        inscripcion__alumno_id=alumno_id,
        pagada=False
    ).select_related('inscripcion')
    data = []
    for c in cuotas:
        data.append({
            'id': c.id,
            'text': f"Cuota {c.get_mes_display()} {c.año} - ${c.monto}",
            'monto': str(c.monto),
            'mes': c.mes,
            'año': c.año,
            'pagada': c.pagada
        })
    return JsonResponse({'success': True, 'data': data})

@login_required
@personal_required
def marcar_cuota_pagada(request, cuota_id):
    """Marcar cuota como pagada"""
    try:
        cuota = get_object_or_404(CuotaAlumno, id=cuota_id, pagada=False)
        
        if request.method == 'POST':
            monto = Decimal(request.POST.get('monto', cuota.monto))
            metodo_pago = request.POST.get('metodo_pago', 'efectivo')
            referencia = request.POST.get('referencia', '')
            
            # Crear pago
            pago = Pago.objects.create(
                alumno=cuota.alumno,
                fecha_pago=timezone.now().date(),
                monto=monto,
                metodo_pago=metodo_pago,
                cuota=cuota,
                referencia=referencia,
                descripcion=f'Pago de {cuota.descripcion}',
                confirmado=True,
                usuario_registro=request.user
            )
            
            # Marcar cuota como pagada
            cuota.pagada = True
            cuota.fecha_pago = timezone.now().date()
            cuota.save()
            
            return JsonResponse({
                'success': True,
                'message': 'Cuota marcada como pagada',
                'pago_id': pago.id
            })
        
        return JsonResponse({
            'success': False,
            'error': 'Método no permitido'
        }, status=405)
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)
        
# ========== REPORTES ==========

@login_required
@permission_required('facturacion.puede_exportar_comprobantes', raise_exception=True)
def generar_reporte(request):
    """Genera reportes en diferentes formatos"""
    if request.method == 'POST':
        form = ReporteForm(request.POST)
        
        if form.is_valid():
            tipo = form.cleaned_data['tipo_reporte']
            formato = form.cleaned_data['formato']
            fecha_desde = form.cleaned_data['fecha_desde']
            fecha_hasta = form.cleaned_data['fecha_hasta']
            
            # Filtrar datos
            comprobantes = Comprobante.objects.filter(
                fecha_emision__range=[fecha_desde, fecha_hasta],
                estado__in=['ACEPTADO_ARCA', 'IMPRESO']
            )
            
            if formato == 'EXCEL':
                return generar_excel_report(comprobantes, tipo)
            elif formato == 'PDF':
                return generar_pdf_report(comprobantes, tipo)
    
    else:
        form = ReporteForm(initial={
            'fecha_desde': timezone.now().replace(day=1).date(),
            'fecha_hasta': timezone.now().date(),
        })
    
    return render(request, 'facturacion/reports/generar.html', {'form': form})

def generar_excel_report(comprobantes, tipo):
    """Genera reporte en Excel"""
    wb = Workbook()
    ws = wb.active
    ws.title = f"Reporte {tipo}"
    
    # Estilos
    header_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
    header_font = Font(color="FFFFFF", bold=True)
    
    if tipo == 'VENTAS':
        headers = ['Fecha', 'Comprobante', 'Cliente', 'Tipo', 'Subtotal', 'IVA', 'Total', 'Estado']
        ws.append(headers)
        
        for cell in ws[1]:
            cell.fill = header_fill
            cell.font = header_font
        
        for comp in comprobantes:
            ws.append([
                comp.fecha_emision,
                comp.numero_completo,
                comp.cliente_razon_social,
                comp.get_tipo_display(),
                comp.subtotal,
                comp.iva,
                comp.total,
                comp.get_estado_display(),
            ])
    
    # Ajustar anchos
    for column in ws.columns:
        max_length = 0
        column_letter = column[0].column_letter
        for cell in column:
            try:
                if len(str(cell.value)) > max_length:
                    max_length = len(str(cell.value))
            except:
                pass
        adjusted_width = min(max_length + 2, 50)
        ws.column_dimensions[column_letter].width = adjusted_width
    
    # Guardar en memoria
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    
    response = HttpResponse(
        output.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="reporte_{tipo}_{timezone.now().date()}.xlsx"'
    
    return response


from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import inch, cm
from reportlab.pdfgen import canvas
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from io import BytesIO
from django.http import HttpResponse
from datetime import datetime

@login_required
@personal_required
def reporte_moras_pdf(request):
    """Generar reporte de moras en PDF"""
    try:
        if not (request.user.is_superuser or es_coordinador(request.user)):
            return HttpResponse('No autorizado', status=403)
        
        # Obtener parámetros
        fecha_inicio_str = request.GET.get('fecha_inicio', '')
        fecha_fin_str = request.GET.get('fecha_fin', '')
        curso_id = request.GET.get('curso', '')
        
        hoy = timezone.now().date()
        
        if fecha_inicio_str:
            fecha_inicio = datetime.strptime(fecha_inicio_str, '%Y-%m-%d').date()
        else:
            fecha_inicio = hoy - timedelta(days=30)
        
        if fecha_fin_str:
            fecha_fin = datetime.strptime(fecha_fin_str, '%Y-%m-%d').date()
        else:
            fecha_fin = hoy
        
        # Consultar datos
        alumnos_query = Alumno.objects.filter(
            cuotaalumno__pagada=False,
            cuotaalumno__fecha_vencimiento__lt=fecha_fin,
            cuotaalumno__fecha_vencimiento__gte=fecha_inicio,
            activo=True
        ).distinct()
        
        if curso_id:
            alumnos_query = alumnos_query.filter(
                inscripcion__curso_id=curso_id,
                inscripcion__activa=True
            ).distinct()
        
        alumnos_mora = alumnos_query.annotate(
            total_deuda=Sum('cuotaalumno__monto', 
                filter=Q(cuotaalumno__pagada=False) & 
                Q(cuotaalumno__fecha_vencimiento__lt=hoy)
            ),
            cuotas_vencidas=Count('cuotaalumno',
                filter=Q(cuotaalumno__pagada=False) & 
                Q(cuotaalumno__fecha_vencimiento__lt=hoy)
            ),
            primera_cuota_vencida=Min('cuotaalumno__fecha_vencimiento',
                filter=Q(cuotaalumno__pagada=False) & 
                Q(cuotaalumno__fecha_vencimiento__lt=hoy)
            )
        ).filter(total_deuda__gt=0).order_by('-total_deuda')
        
        # Calcular días de mora
        for alumno in alumnos_mora:
            if alumno.primera_cuota_vencida:
                alumno.dias_mora = (hoy - alumno.primera_cuota_vencida).days
            else:
                alumno.dias_mora = 0
        
        # Estadísticas
        total_deuda = alumnos_mora.aggregate(total=Sum('total_deuda'))['total'] or Decimal('0')
        total_alumnos = alumnos_mora.count()
        
        if total_alumnos > 0:
            total_cuotas = sum(alumno.cuotas_vencidas for alumno in alumnos_mora)
            promedio_dias = alumnos_mora.aggregate(promedio=Avg('dias_mora'))['promedio'] or 0
            cuota_promedio = total_deuda / total_cuotas if total_cuotas > 0 else Decimal('0')
        else:
            total_cuotas = 0
            promedio_dias = 0
            cuota_promedio = Decimal('0')
        
        # Análisis por curso
        cursos_analisis = []
        cursos = Curso.objects.filter(activo=True)
        
        for curso in cursos:
            alumnos_curso = alumnos_mora.filter(
                inscripcion__curso=curso,
                inscripcion__activa=True
            ).distinct()
            
            if alumnos_curso.exists():
                deuda_total = alumnos_curso.aggregate(total=Sum('total_deuda'))['total'] or Decimal('0')
                total_inscritos = Inscripcion.objects.filter(curso=curso, activa=True).count()
                
                cursos_analisis.append({
                    'nombre': curso.nombre,
                    'total_alumnos': total_inscritos,
                    'alumnos_mora': alumnos_curso.count(),
                    'deuda_total': deuda_total,
                    'deuda_promedio': deuda_total / alumnos_curso.count() if alumnos_curso.count() > 0 else Decimal('0'),
                    'porcentaje_mora': (alumnos_curso.count() / total_inscritos * 100) if total_inscritos > 0 else 0
                })
        
        # Preparar datos para el contexto
        context = {
            'fecha_inicio': fecha_inicio,
            'fecha_fin': fecha_fin,
            'fecha_generacion': timezone.now(),
            'alumnos_mora': alumnos_mora,
            'total_deuda': total_deuda,
            'total_alumnos': total_alumnos,
            'total_cuotas': total_cuotas,
            'promedio_dias': promedio_dias,
            'cuota_promedio': cuota_promedio,
            'cursos_analisis': cursos_analisis,
            'usuario_actual': request.user,
        }
        
        # Si se solicita descargar como PDF
        if request.GET.get('download') == 'true':
            return generar_pdf_reportlab(context)
        
        # Si no, mostrar vista previa HTML
        return render(request, 'web/facturacion/reporte_moras_pdf.html', context)
        
    except Exception as e:
        messages.error(request, f'Error generando reporte: {str(e)}')
        return redirect('seguimiento_moras')


def generar_pdf_reportlab(context):
    """Generar PDF usando ReportLab"""
    try:
        # Crear buffer para el PDF
        buffer = BytesIO()
        
        # Crear documento
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=72
        )
        
        # Estilos
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=16,
            textColor=colors.HexColor('#dc3545'),
            alignment=TA_CENTER,
            spaceAfter=20
        )
        
        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=12,
            textColor=colors.HexColor('#0d6efd'),
            spaceAfter=10
        )
        
        normal_style = ParagraphStyle(
            'Normal',
            parent=styles['Normal'],
            fontSize=10,
            spaceAfter=5
        )
        
        # Contenido
        story = []
        
        # Título
        story.append(Paragraph('REPORTE DE MORAS', title_style))
        
        # Información del reporte
        info_data = [
            ['Período:', f'{context["fecha_inicio"].strftime("%d/%m/%Y")} - {context["fecha_fin"].strftime("%d/%m/%Y")}'],
            ['Generado:', context['fecha_generacion'].strftime("%d/%m/%Y %H:%M")],
            ['Generado por:', context['usuario_actual'].get_full_name()],
        ]
        
        info_table = Table(info_data, colWidths=[100, 300])
        info_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
            ('ALIGN', (1, 0), (1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BOX', (0, 0), (-1, -1), 1, colors.grey),
            ('INNERGRID', (0, 0), (-1, -1), 0.25, colors.grey),
            ('PADDING', (0, 0), (-1, -1), 6),
        ]))
        
        story.append(info_table)
        story.append(Spacer(1, 20))
        
        # Estadísticas principales
        story.append(Paragraph('ESTADÍSTICAS PRINCIPALES', heading_style))
        
        stats_data = [
            ['Total Deuda', f'${context["total_deuda"]:,.2f}'],
            ['Alumnos en Mora', str(context['total_alumnos'])],
            ['Cuotas Vencidas', str(context['total_cuotas'])],
            ['Días Promedio', f'{context["promedio_dias"]:.0f} días'],
            ['Cuota Promedio', f'${context["cuota_promedio"]:,.2f}'],
        ]
        
        stats_table = Table(stats_data, colWidths=[200, 200])
        stats_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f8f9fa')),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BOX', (0, 0), (-1, -1), 1, colors.grey),
            ('INNERGRID', (0, 0), (-1, -1), 0.25, colors.grey),
            ('PADDING', (0, 0), (-1, -1), 8),
        ]))
        
        story.append(stats_table)
        story.append(Spacer(1, 20))
        
        # Tabla de alumnos
        if context['alumnos_mora']:
            story.append(Paragraph('DETALLE DE ALUMNOS EN MORA', heading_style))
            
            # Cabecera de tabla
            table_data = [['Alumno', 'Matrícula', 'Deuda', 'Cuotas', 'Días']]
            
            # Datos de alumnos
            for alumno in context['alumnos_mora']:
                table_data.append([
                    alumno.nombre_completo(),
                    alumno.matricula or '-',
                    f'${alumno.total_deuda:,.2f}',
                    str(alumno.cuotas_vencidas),
                    str(alumno.dias_mora)
                ])
            
            # Crear tabla
            alumno_table = Table(table_data, colWidths=[180, 80, 80, 60, 60])
            alumno_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e9ecef')),
                ('ALIGN', (2, 1), (2, -1), 'RIGHT'),
                ('ALIGN', (3, 1), (4, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('BOX', (0, 0), (-1, -1), 1, colors.grey),
                ('INNERGRID', (0, 0), (-1, -1), 0.25, colors.grey),
                ('PADDING', (0, 0), (-1, -1), 6),
            ]))
            
            story.append(alumno_table)
            story.append(Spacer(1, 20))
        
        # Análisis por curso
        if context['cursos_analisis']:
            story.append(Paragraph('ANÁLISIS POR CURSO', heading_style))
            
            curso_data = [['Curso', 'Total', 'En Mora', 'Deuda Total', '% Mora']]
            
            for curso in context['cursos_analisis']:
                curso_data.append([
                    curso['nombre'],
                    str(curso['total_alumnos']),
                    str(curso['alumnos_mora']),
                    f'${curso["deuda_total"]:,.2f}',
                    f'{curso["porcentaje_mora"]:.1f}%'
                ])
            
            curso_table = Table(curso_data, colWidths=[150, 60, 60, 80, 60])
            curso_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e9ecef')),
                ('ALIGN', (1, 1), (2, -1), 'CENTER'),
                ('ALIGN', (3, 1), (-1, -1), 'RIGHT'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('BOX', (0, 0), (-1, -1), 1, colors.grey),
                ('INNERGRID', (0, 0), (-1, -1), 0.25, colors.grey),
                ('PADDING', (0, 0), (-1, -1), 6),
            ]))
            
            story.append(curso_table)
            story.append(Spacer(1, 20))
        
        # Recomendaciones
        story.append(Paragraph('RECOMENDACIONES', heading_style))
        
        recomendaciones = [
            "1. Contactar urgentemente a los 5 mayores deudores",
            "2. Implementar planes de pago personalizados",
            "3. Reforzar el sistema de recordatorios automáticos",
            "4. Revisar datos de contacto de alumnos en mora prolongada",
            "5. Programar reuniones con deudores recurrentes"
        ]
        
        for rec in recomendaciones:
            story.append(Paragraph(rec, normal_style))
        
        story.append(Spacer(1, 20))
        
        # Firmas
        firmas_data = [
            ['', '', ''],
            ['________________________', '________________________', '________________________'],
            ['Generado por', 'Revisado por', 'Aprobado por']
        ]
        
        firmas_table = Table(firmas_data, colWidths=[150, 150, 150])
        firmas_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('SPAN', (0, 0), (2, 0)),
            ('PADDING', (0, 0), (-1, -1), 10),
        ]))
        
        story.append(firmas_table)
        
        # Pie de página
        pie_data = [
            ['Reporte generado automáticamente por el Sistema de Gestión IACL'],
            [f'Página 1 de 1 | Fecha: {timezone.now().strftime("%d/%m/%Y %H:%M")}']
        ]
        
        pie_table = Table(pie_data, colWidths=[500])
        pie_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Oblique'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.grey),
            ('PADDING', (0, 0), (-1, -1), 5),
        ]))
        
        story.append(Spacer(1, 10))
        story.append(pie_table)
        
        # Construir PDF
        doc.build(story)
        
        # Obtener el valor del buffer
        pdf = buffer.getvalue()
        buffer.close()
        
        # Crear respuesta HTTP
        response = HttpResponse(pdf, content_type='application/pdf')
        filename = f'reporte_moras_{context["fecha_inicio"].strftime("%Y%m%d")}_{context["fecha_fin"].strftime("%Y%m%d")}.pdf'
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        return response
        
    except Exception as e:
        # En caso de error, devolver respuesta simple
        response = HttpResponse(f'Error generando PDF: {str(e)}', content_type='text/plain')
        return response

# ========== API ENDPOINTS ==========

@login_required
def api_buscar_cliente(request):
    """API para búsqueda de clientes"""
    query = request.GET.get('q', '')
    
    resultados = []
    
    # Buscar por DNI
    if query.isdigit() and len(query) >= 7:
        alumnos = Alumno.objects.filter(dni__icontains=query, activo=True)[:10]
        for alumno in alumnos:
            resultados.append({
                'id': f'alumno_{alumno.id}',
                'text': f"{alumno.nombre_completo()} - DNI: {alumno.dni}",
                'nombre': alumno.nombre_completo(),
                'dni': alumno.dni,
                'email': alumno.mail or '',
                'domicilio': alumno.direccion or '',
                'tipo': 'alumno'
            })
    
    # Buscar por nombre
    alumnos_nombre = Alumno.objects.filter(
        Q(nombre__icontains=query) | Q(apellido__icontains=query),
        activo=True
    )[:10]
    
    for alumno in alumnos_nombre:
        resultados.append({
            'id': f'alumno_{alumno.id}',
            'text': f"{alumno.nombre_completo()} - DNI: {alumno.dni}",
            'nombre': alumno.nombre_completo(),
            'dni': alumno.dni,
            'email': alumno.mail or '',
            'domicilio': alumno.direccion or '',
            'tipo': 'alumno'
        })
    
    return JsonResponse({'results': resultados})

# En facturacion/views.py

@login_required
@personal_required
def api_buscar_alumnos(request):
    term = request.GET.get('term', '')
    alumnos = Alumno.objects.filter(
        Q(activo=True) & 
        (Q(nombre__icontains=term) | Q(apellido__icontains=term) | Q(dni__icontains=term))
    )[:20]
    results = [{'id': a.id, 'text': f"{a.nombre_completo()} - DNI: {a.dni}"} for a in alumnos]
    return JsonResponse({'results': results})

@login_required
@personal_required
def api_buscar_curso(request):
    term = request.GET.get('term', '')
    cursos = Curso.objects.filter(
        Q(nombre__icontains=term) | 
        Q(profesor__nombre__icontains=term) | 
        Q(profesor__apellido__icontains=term),
        activo=True
    ).distinct()[:10]
    results = [{
        'id': c.id,
        'text': c.nombre,
        'precio': float(c.precio) if c.precio else 0
    } for c in cursos]
    return JsonResponse({'results': results})

@login_required
def api_buscar_producto(request):
    term = request.GET.get('term', '')  # Cambiamos a 'term' para consistencia
    productos = ProductoServicio.objects.filter(
        Q(codigo__icontains=term) | Q(nombre__icontains=term),
        activo=True
    )[:10]
    results = [{
        'id': p.id,
        'text': f"{p.codigo} - {p.nombre}",
        'precio': float(p.precio)
    } for p in productos]
    return JsonResponse({'results': results})

@login_required
def api_datos_alumno(request, alumno_id):
    alumno = get_object_or_404(Alumno, id=alumno_id)
    data = {
        'dni': alumno.dni,
        'nombre_completo': alumno.nombre_completo(),
        'direccion': alumno.direccion or '',
        'mail': alumno.mail or '',
        # Agrega más campos si los necesitas
    }
    return JsonResponse(data)

@login_required
@personal_required
def dashboard_facturacion(request):
    """
    Dashboard principal del módulo de facturación
    """
    try:
        hoy = timezone.now().date()
        inicio_mes = hoy.replace(day=1)
        
        # Importar modelos
        from facturacion.models import Comprobante, Contribuyente, Producto
        
        # Estadísticas del mes
        comprobantes_mes = Comprobante.objects.filter(
            fecha_emision__gte=inicio_mes,
            fecha_emision__lte=hoy
        )
        
        total_comprobantes_mes = comprobantes_mes.count()
        
        # Calcular total de ventas del mes
        total_ventas_mes = comprobantes_mes.aggregate(
            total=Sum('total')
        )['total'] or 0
        
        # Contribuyentes activos
        contribuyentes = Contribuyente.objects.filter(activo=True).order_by('razon_social')
        
        # Comprobantes recientes (últimos 10)
        comprobantes_recientes = Comprobante.objects.select_related(
            'contribuyente'
        ).order_by('-fecha_emision')[:10]
        
        # Estadísticas adicionales
        total_productos = Producto.objects.filter(activo=True).count()
        comprobantes_pendientes = Comprobante.objects.filter(estado='BORRADOR').count()
        
        context = {
            'hoy': hoy,
            'total_comprobantes_mes': total_comprobantes_mes,
            'total_ventas_mes': total_ventas_mes,
            'contribuyentes': contribuyentes,
            'comprobantes_recientes': comprobantes_recientes,
            'total_productos': total_productos,
            'comprobantes_pendientes': comprobantes_pendientes,
        }
        
        return render(request, 'facturacion/dashboard.html', context)
        
    except Exception as e:
        from django.contrib import messages
        messages.error(request, f'Error al cargar el dashboard: {str(e)}')
        # Si el template no existe o hay error, redirigir a una vista simple
        return render(request, 'facturacion/dashboard_simple.html', {'error': str(e)})
    
def dashboard_debug(request):
    """Vista temporal para debug"""
    from django.contrib import messages
    messages.info(request, "Vista de debug - En construcción")
    return render(request, 'facturacion/dashboard_simple.html')

def test_herencia(request):
    """Test de herencia de templates"""
    return render(request, 'facturacion/dashboard_simple.html')

# Si faltan otras vistas mencionadas en urls.py, crea versiones simples
def seguimiento_moras(request):
    """Vista temporal para seguimiento de moras"""
    from django.contrib import messages
    messages.info(request, "Seguimiento de moras - En construcción")
    return render(request, 'facturacion/dashboard_simple.html')


@login_required
@personal_required
def registrar_egreso(request):
    if request.method == 'POST':
        # Procesar formulario
        concepto = request.POST.get('concepto')
        monto = request.POST.get('monto')
        fecha = request.POST.get('fecha')
        observaciones = request.POST.get('observaciones', '')
        # Crear Egreso
        Egreso.objects.create(
            concepto=concepto,
            monto=monto,
            fecha=fecha or timezone.now(),
            usuario=request.user,
            observaciones=observaciones
        )
        messages.success(request, 'Egreso registrado correctamente.')
        return redirect('reporte_pagos')
    return render(request, 'facturacion/egreso_form.html')