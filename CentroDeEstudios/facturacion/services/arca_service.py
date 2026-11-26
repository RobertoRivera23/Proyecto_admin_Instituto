import requests
import json
from django.conf import settings
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)

class ArcaService:
    """Servicio para integración con ARCA"""
    
    def __init__(self, contribuyente):
        self.contribuyente = contribuyente
        self.base_url = contribuyente.arca_endpoint or "https://api.arca.test"
        self.token = contribuyente.arca_token
        
    def autenticar(self):
        """Autenticación con ARCA"""
        try:
            response = requests.post(
                f"{self.base_url}/auth",
                json={
                    'usuario': self.contribuyente.arca_usuario,
                    'password': self.contribuyente.arca_password,
                },
                timeout=30
            )
            response.raise_for_status()
            data = response.json()
            self.token = data.get('token')
            return data
        except Exception as e:
            logger.error(f"Error autenticando con ARCA: {e}")
            return None
    
    def emitir_comprobante(self, comprobante):
        """Envía comprobante a ARCA"""
        if not self.token:
            if not self.autenticar():
                return False, "Error de autenticación"
        
        try:
            # Construir payload según especificaciones ARCA
            payload = self._construir_payload_afip(comprobante)
            
            headers = {
                'Authorization': f'Bearer {self.token}',
                'Content-Type': 'application/json'
            }
            
            response = requests.post(
                f"{self.base_url}/comprobantes/emitir",
                json=payload,
                headers=headers,
                timeout=60
            )
            
            response.raise_for_status()
            data = response.json()
            
            # Actualizar comprobante con respuesta
            comprobante.arca_envio_id = data.get('id')
            comprobante.arca_cae = data.get('cae')
            comprobante.arca_fecha_vto_cae = data.get('fechaVtoCae')
            comprobante.arca_resultado = data.get('resultado')
            comprobante.arca_observaciones = data.get('observaciones')
            comprobante.arca_respuesta_raw = data
            comprobante.estado = 'ACEPTADO_ARCA' if data.get('estado') == 'A' else 'RECHAZADO_ARCA'
            comprobante.save()
            
            return comprobante.estado == 'ACEPTADO_ARCA', comprobante.arca_observaciones
            
        except Exception as e:
            logger.error(f"Error emitiendo comprobante en ARCA: {e}")
            return False, str(e)
    
    def _construir_payload_afip(self, comprobante):
        """Construye payload según especificaciones AFIP"""
        items = []
        for item in comprobante.items.all():
            items.append({
                'codigo': item.codigo or item.producto.codigo if item.producto else '',
                'descripcion': item.descripcion,
                'cantidad': float(item.cantidad),
                'precioUnitario': float(item.precio_unitario),
                'subtotal': float(item.subtotal),
                'ivaPorcentaje': float(item.iva_porcentaje),
                'ivaMonto': float(item.iva_monto),
                'unidadMedida': item.producto.unidad_medida if item.producto else 'UNIDAD',
            })
        
        return {
            'comprobante': {
                'tipo': comprobante.get_codigo_tipo_afip(),
                'puntoVenta': comprobante.punto_venta.numero,
                'numero': comprobante.numero,
                'fechaEmision': comprobante.fecha_emision.strftime('%Y-%m-%d'),
                'moneda': comprobante.moneda,
                'condicionVenta': comprobante.condicion_venta,
            },
            'emisor': {
                'cuit': self.contribuyente.cuit,
                'razonSocial': self.contribuyente.razon_social,
                'domicilio': self.contribuyente.domicilio,
                'condicionIva': self.contribuyente.tipo_responsabilidad,
                'nroIngresosBrutos': self.contribuyente.nro_iibb,
            },
            'receptor': {
                'tipoDocumento': comprobante.get_codigo_documento_afip(),
                'numeroDocumento': comprobante.cliente_numero_documento,
                'razonSocial': comprobante.cliente_razon_social,
                'domicilio': comprobante.cliente_domicilio,
                'condicionIva': comprobante.cliente_condicion_iva,
            },
            'items': items,
            'totales': {
                'subtotal': float(comprobante.subtotal),
                'descuento': float(comprobante.descuento),
                'iva': float(comprobante.iva),
                'percepciones': float(comprobante.percepciones),
                'retenciones': float(comprobante.retenciones),
                'total': float(comprobante.total),
            }
        }

# facturacion/services/pdf_service.py
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm, mm
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
import qrcode
from django.core.files import File
import tempfile
import os

class PDFService:
    """Servicio para generación de PDFs de comprobantes"""
    
    @staticmethod
    def generar_comprobante_pdf(comprobante):
        """Genera PDF para un comprobante"""
        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=2*cm,
            leftMargin=2*cm,
            topMargin=2*cm,
            bottomMargin=2*cm
        )
        
        story = []
        styles = getSampleStyleSheet()
        
        # Estilos personalizados
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=16,
            alignment=TA_CENTER,
            spaceAfter=20
        )
        
        header_style = ParagraphStyle(
            'Header',
            parent=styles['Normal'],
            fontSize=10,
            alignment=TA_CENTER
        )
        
        # Logo si existe
        if comprobante.contribuyente.logo:
            try:
                logo_path = comprobante.contribuyente.logo.path
                logo = Image(logo_path, width=4*cm, height=2*cm)
                logo.hAlign = 'CENTER'
                story.append(logo)
                story.append(Spacer(1, 0.5*cm))
            except:
                pass
        
        # Título del comprobante
        story.append(Paragraph(f"{comprobante.get_tipo_display()}", title_style))
        story.append(Paragraph(f"N°: {comprobante.numero_completo}", header_style))
        story.append(Spacer(1, 1*cm))
        
        # Información del emisor
        emisor_data = [
            ['<b>EMISOR</b>', ''],
            ['Razón Social:', comprobante.contribuyente.razon_social],
            ['CUIT:', comprobante.contribuyente.cuit],
            ['Domicilio:', comprobante.contribuyente.domicilio],
            ['Condición IVA:', comprobante.contribuyente.get_tipo_responsabilidad_display()],
            ['Inicio Actividades:', comprobante.contribuyente.fecha_inicio_actividades.strftime('%d/%m/%Y')],
        ]
        
        # Información del receptor
        receptor_data = [
            ['<b>RECEPTOR</b>', ''],
            ['Razón Social:', comprobante.cliente_razon_social],
            ['Documento:', f"{comprobante.get_cliente_tipo_documento_display()} {comprobante.cliente_numero_documento}"],
            ['Domicilio:', comprobante.cliente_domicilio or ''],
            ['Condición IVA:', comprobante.get_cliente_condicion_iva_display()],
        ]
        
        # Tablas de información
        emisor_table = Table(emisor_data, colWidths=[6*cm, 10*cm])
        emisor_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ]))
        
        receptor_table = Table(receptor_data, colWidths=[6*cm, 10*cm])
        receptor_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ]))
        
        # Tabla de items
        items_data = [['Código', 'Descripción', 'Cant.', 'P. Unit.', 'IVA %', 'Subtotal']]
        
        for item in comprobante.items.all():
            items_data.append([
                item.codigo or '',
                item.descripcion[:50],
                str(item.cantidad),
                f"${item.precio_unitario:,.2f}",
                f"{item.iva_porcentaje}%",
                f"${item.subtotal:,.2f}"
            ])
        
        items_table = Table(items_data, colWidths=[2*cm, 8*cm, 2*cm, 2*cm, 2*cm, 2*cm])
        items_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
            ('ALIGN', (2, 1), (5, -1), 'RIGHT'),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ]))
        
        # Totales
        totales_data = [
            ['', '', '', '<b>TOTALES</b>', ''],
            ['', '', '', 'Subtotal:', f"${comprobante.subtotal:,.2f}"],
            ['', '', '', 'Descuento:', f"${comprobante.descuento:,.2f}"],
            ['', '', '', 'IVA:', f"${comprobante.iva:,.2f}"],
            ['', '', '', 'Percepciones:', f"${comprobante.percepciones:,.2f}"],
            ['', '', '', 'Retenciones:', f"${comprobante.retenciones:,.2f}"],
            ['', '', '', '<b>TOTAL GENERAL:</b>', f"<b>${comprobante.total:,.2f}</b>"],
        ]
        
        totales_table = Table(totales_data, colWidths=[2*cm, 2*cm, 2*cm, 6*cm, 2*cm])
        totales_table.setStyle(TableStyle([
            ('ALIGN', (3, 0), (3, -1), 'RIGHT'),
            ('ALIGN', (4, 0), (4, -1), 'RIGHT'),
            ('FONTNAME', (3, -1), (4, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (3, -1), (4, -1), 12),
            ('TEXTCOLOR', (4, -1), (4, -1), colors.red),
        ]))
        
        # Agregar QR si tiene CAE
        if comprobante.arca_cae:
            # Generar QR
            qr_data = comprobante.generar_qr_data()
            qr = qrcode.make(qr_data)
            
            # Guardar QR temporalmente
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
                qr.save(tmp.name)
                qr_image = Image(tmp.name, width=4*cm, height=4*cm)
                qr_image.hAlign = 'CENTER'
                
                story.append(Spacer(1, 1*cm))
                story.append(qr_image)
                story.append(Paragraph("Código QR para verificación", styles['Normal']))
                
                os.unlink(tmp.name)
        
        # Construir documento
        story.append(emisor_table)
        story.append(Spacer(1, 0.5*cm))
        story.append(receptor_table)
        story.append(Spacer(1, 1*cm))
        story.append(items_table)
        story.append(Spacer(1, 0.5*cm))
        story.append(totales_table)
        story.append(Spacer(1, 2*cm))
        
        # Observaciones
        if comprobante.observaciones:
            story.append(Paragraph("<b>Observaciones:</b>", styles['Normal']))
            story.append(Paragraph(comprobante.observaciones, styles['Normal']))
            story.append(Spacer(1, 1*cm))
        
        # CAE si existe
        if comprobante.arca_cae:
            cae_data = [
                ['CAE:', comprobante.arca_cae],
                ['Fecha Vto. CAE:', comprobante.arca_fecha_vto_cae.strftime('%d/%m/%Y') if comprobante.arca_fecha_vto_cae else ''],
                ['Resultado ARCA:', comprobante.arca_resultado],
            ]
            cae_table = Table(cae_data, colWidths=[4*cm, 8*cm])
            cae_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), colors.lightgrey),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ]))
            story.append(cae_table)
        
        doc.build(story)
        
        # Guardar PDF en el modelo
        buffer.seek(0)
        filename = f"comprobante_{comprobante.numero_completo}_{comprobante.uuid}.pdf"
        comprobante.pdf.save(filename, File(buffer))
        
        return comprobante.pdf.path
    
    


