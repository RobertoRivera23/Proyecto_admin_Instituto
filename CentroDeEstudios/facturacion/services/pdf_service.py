"""
Servicio para generación de PDFs de comprobantes
"""
import os
import tempfile
from io import BytesIO
from decimal import Decimal
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm, mm
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT, TA_JUSTIFY
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table,
    TableStyle, Image, KeepTogether, PageBreak
)
from reportlab.pdfgen import canvas
from reportlab.graphics.barcode import qr
from reportlab.graphics.shapes import Drawing
from reportlab.graphics import renderPDF

import qrcode
from django.core.files import File
from django.utils import timezone
from django.conf import settings


class PDFService:
    """Servicio para generación de PDFs de comprobantes"""

    @staticmethod
    def generar_comprobante_pdf(comprobante):
        """Genera PDF para un comprobante (recibo, factura, etc.)"""
        buffer = BytesIO()

        # Configurar documento
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=1.5*cm,
            leftMargin=1.5*cm,
            topMargin=1.5*cm,
            bottomMargin=1.5*cm
        )

        story = []
        styles = getSampleStyleSheet()

        # ========== ESTILOS PERSONALIZADOS BÁSICOS ==========
        titulo_estilo = ParagraphStyle(
            'Titulo', parent=styles['Heading1'], fontSize=16,
            alignment=TA_CENTER, spaceAfter=20, textColor=colors.HexColor('#2c3e50')
        )
        subtitulo_estilo = ParagraphStyle(
            'Subtitulo', parent=styles['Heading2'], fontSize=12,
            alignment=TA_CENTER, spaceAfter=10, textColor=colors.HexColor('#34495e')
        )
        normal_estilo = ParagraphStyle('NormalCentrado', parent=styles['Normal'], alignment=TA_CENTER, fontSize=10)
        etiqueta_estilo = ParagraphStyle('Etiqueta', parent=styles['Normal'], fontSize=9, textColor=colors.HexColor('#7f8c8d'))
        valor_estilo = ParagraphStyle('Valor', parent=styles['Normal'], fontSize=10, textColor=colors.HexColor('#2c3e50'), fontName='Helvetica-Bold')

        # ========== DISEÑO ESPECIAL PARA RECIBOS (ESTILO ARCA/AFIP) ==========
        if comprobante.tipo == 'RECIBO':
            # Logo
            logo_path = None
            if comprobante.contribuyente.logo and comprobante.contribuyente.logo.path:
                logo_path = comprobante.contribuyente.logo.path
            else:
                logo_path = os.path.join(settings.BASE_DIR, 'web', 'static', 'web', 'image', 'logo_sf.jpg')

            logo_img = None
            if os.path.exists(logo_path):
                try:
                    # Ajustamos el tamaño para que entre bien en la cabecera
                    logo_img = Image(logo_path, width=4*cm, height=2.5*cm) 
                    logo_img.hAlign = 'CENTER'
                except:
                    pass

            # Estilos tipográficos estilo fiscal
            estilo_texto = ParagraphStyle('TextoBase', parent=styles['Normal'], fontSize=9, leading=11)
            estilo_bold = ParagraphStyle('TextoBold', parent=estilo_texto, fontName='Helvetica-Bold')
            estilo_chico = ParagraphStyle('TextoChico', parent=estilo_texto, fontSize=8, leading=10)

          # ================= 1. CABECERA DIVIDIDA =================
            # Izquierda (Emisor)
            left_content = []
            if logo_img:
                left_content.append(logo_img)
                left_content.append(Spacer(1, 0.2*cm))
            left_content.append(Paragraph(f"<b>Razón Social:</b> {comprobante.contribuyente.razon_social}", estilo_texto))
            left_content.append(Paragraph(f"<b>Domicilio Comercial:</b> {comprobante.contribuyente.domicilio}", estilo_texto))
            left_content.append(Paragraph(f"<b>Condición frente al IVA:</b> {comprobante.contribuyente.get_tipo_responsabilidad_display()}", estilo_texto))

            # Centro (Letra del comprobante)
            letra_style = ParagraphStyle('Letra', parent=styles['Normal'], alignment=TA_CENTER, fontSize=24, fontName='Helvetica-Bold')
            cod_style = ParagraphStyle('Cod', parent=styles['Normal'], alignment=TA_CENTER, fontSize=8, fontName='Helvetica-Bold')
            
            tabla_letra = Table([
                [Paragraph("X", letra_style)],
                [Paragraph("Cód. 000", cod_style)]
            ], colWidths=[1.5*cm])
            tabla_letra.setStyle(TableStyle([
                ('BOX', (0, 0), (-1, -1), 1, colors.black),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ]))

            mid_content = [
                tabla_letra,
                Spacer(1, 0.2*cm),
                Paragraph("Documento no", ParagraphStyle('DocNo', parent=cod_style, fontSize=6)),
                Paragraph("válido como", ParagraphStyle('DocNo2', parent=cod_style, fontSize=6)),
                Paragraph("factura", ParagraphStyle('DocNo3', parent=cod_style, fontSize=6)),
            ]

            # Derecha (Datos del Recibo)
            right_content = []
            right_content.append(Paragraph("<b>RECIBO</b>", ParagraphStyle('TitRecibo', parent=styles['Heading2'], fontSize=18, fontName='Helvetica-Bold')))
            right_content.append(Spacer(1, 0.2*cm))
            right_content.append(Paragraph(f"<b>Nº:</b> {comprobante.numero_completo}", estilo_texto))
            right_content.append(Paragraph(f"<b>Fecha de Emisión:</b> {comprobante.fecha_emision.strftime('%d/%m/%Y')}", estilo_texto))
            right_content.append(Spacer(1, 0.2*cm))
            right_content.append(Paragraph(f"<b>CUIT:</b> {comprobante.contribuyente.cuit}", estilo_texto))
            right_content.append(Paragraph(f"<b>Ingresos Brutos:</b> {comprobante.contribuyente.nro_iibb or 'Exento'}", estilo_texto))
            fecha_inicio = comprobante.contribuyente.fecha_inicio_actividades.strftime('%d/%m/%Y') if comprobante.contribuyente.fecha_inicio_actividades else "-"
            right_content.append(Paragraph(f"<b>Fecha de Inicio de Actividades:</b> {fecha_inicio}", estilo_texto))

            # Ensamblar Cabecera
            header_table = Table([[left_content, mid_content, right_content]], colWidths=[8*cm, 2*cm, 8*cm])
            header_table.setStyle(TableStyle([
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('BOX', (0, 0), (-1, -1), 1, colors.black),
                ('LINEBEFORE', (2, 0), (2, -1), 1, colors.black), # Línea divisoria central
                ('LEFTPADDING', (0, 0), (-1, -1), 8),
                ('RIGHTPADDING', (0, 0), (-1, -1), 8),
                ('TOPPADDING', (0, 0), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ]))
            story.append(header_table)
            
            # ELIMINADO: Spacer entre cabecera y receptor

            # ================= 2. DATOS DEL RECEPTOR Y CONDICIONES (UNIFICADO) =================
            tipo_doc = comprobante.get_cliente_tipo_documento_display()
            condicion_iva = comprobante.get_cliente_condicion_iva_display() if hasattr(comprobante, 'get_cliente_condicion_iva_display') else "Consumidor Final"
            
            receptor_y_condiciones_data = [
                [Paragraph(f"<b>{tipo_doc}:</b> {comprobante.cliente_numero_documento}", estilo_texto),
                 Paragraph(f"<b>Apellido y Nombre / Razón Social:</b> {comprobante.cliente_razon_social}", estilo_texto)],
                [Paragraph(f"<b>Condición IVA:</b> {condicion_iva}", estilo_texto),
                 Paragraph(f"<b>Domicilio Comercial:</b> {comprobante.cliente_domicilio or '-'}", estilo_texto)],
                [Paragraph(f"<b>Condición de Venta:</b> {comprobante.get_condicion_venta_display()}", estilo_texto),
                 Paragraph(f"<b>Moneda:</b> {comprobante.get_moneda_display()}", estilo_texto)]
            ]

            # Ancho de 9cm y 9cm suma 18cm en total, exactamente igual a la cabecera (8+2+8)
            receptor_table = Table(receptor_y_condiciones_data, colWidths=[9*cm, 9*cm])
            receptor_table.setStyle(TableStyle([
                ('BOX', (0, 0), (-1, -1), 1, colors.black),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('LEFTPADDING', (0, 0), (-1, -1), 8),
                ('TOPPADDING', (0, 0), (-1, -1), 5),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ]))
            story.append(receptor_table)
            story.append(Spacer(1, 0.5*cm)) # Este sí lo dejamos para separar del detalle de ítems

            # ================= 3. DETALLE DE CONCEPTOS =================
            items_header = [
                Paragraph("<b>Cant.</b>", estilo_bold),
                Paragraph("<b>Descripción</b>", estilo_bold),
                Paragraph("<b>Precio Unit.</b>", ParagraphStyle('R', parent=estilo_bold, alignment=TA_RIGHT)),
                Paragraph("<b>Importe</b>", ParagraphStyle('R', parent=estilo_bold, alignment=TA_RIGHT))
            ]
            items_data = [items_header]

            for item in comprobante.items.all():
                p_unitario = item.precio_unitario if hasattr(item, 'precio_unitario') else (item.subtotal / item.cantidad if item.cantidad else 0)
                
                items_data.append([
                    Paragraph(str(item.cantidad), estilo_texto),
                    Paragraph(item.descripcion, estilo_texto),
                    Paragraph(f"${p_unitario:,.2f}", ParagraphStyle('R', parent=estilo_texto, alignment=TA_RIGHT)),
                    Paragraph(f"${item.subtotal:,.2f}", ParagraphStyle('R', parent=estilo_texto, alignment=TA_RIGHT))
                ])

            items_table = Table(items_data, colWidths=[2*cm, 10*cm, 3*cm, 3*cm])
            items_table.setStyle(TableStyle([
                ('BOX', (0, 0), (-1, -1), 1, colors.black),
                # Modificación: En lugar de GRID (que hace cuadros internos), definimos solo las líneas que queremos
                ('LINEBELOW', (0, 0), (-1, 0), 1, colors.black), # Línea debajo del encabezado
                ('LINEAFTER', (0, 0), (-2, -1), 0.5, colors.HexColor('#bdc3c7')), # Separadores verticales de columnas
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e0e0e0')), # Gris claro tipo AFIP
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('TOPPADDING', (0, 0), (-1, -1), 5),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ]))
            story.append(items_table)
            
            # ELIMINADO: Spacer entre ítems y totales

            # ================= 4. TOTALES =================
            totales_data = [
                ["", Paragraph("<b>Subtotal:</b>", ParagraphStyle('R', parent=estilo_bold, alignment=TA_RIGHT)), Paragraph(f"${comprobante.total:,.2f}", ParagraphStyle('R', parent=estilo_bold, alignment=TA_RIGHT))],
                ["", Paragraph("<b>TOTAL A PAGAR:</b>", ParagraphStyle('R', parent=estilo_bold, alignment=TA_RIGHT, fontSize=11)), Paragraph(f"${comprobante.total:,.2f}", ParagraphStyle('R', parent=estilo_bold, alignment=TA_RIGHT, fontSize=11))]
            ]

            totales_table = Table(totales_data, colWidths=[10*cm, 4*cm, 4*cm])
            totales_table.setStyle(TableStyle([
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('TOPPADDING', (0, 0), (-1, -1), 5),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
                ('BOX', (1, 0), (-1, -1), 1, colors.black),
                # Mantenemos el GRID interno solo para la cajita de totales (las 4 celdas)
                ('GRID', (1, 0), (-1, -1), 0.5, colors.black),
                ('BACKGROUND', (1, -1), (-1, -1), colors.HexColor('#e0e0e0')),
            ]))
            story.append(totales_table)
            story.append(Spacer(1, 1.5*cm)) 

            duplicado_data = [ 
                ['============================ Duplicado Emisor ===================================='],
                ]
        # ================= DATOS DEL RECEPTOR Y CONDICIONES (UNIFICADO) =================
            tipo_doc = comprobante.get_cliente_tipo_documento_display()
            condicion_iva = comprobante.get_cliente_condicion_iva_display() if hasattr(comprobante, 'get_cliente_condicion_iva_display') else "Consumidor Final"
            
            receptor_y_condiciones_data = [
                [Paragraph(f"<b>{tipo_doc}:</b> {comprobante.cliente_numero_documento}", estilo_texto),
                 Paragraph(f"<b>Apellido y Nombre / Razón Social:</b> {comprobante.cliente_razon_social}", estilo_texto)],
                [Paragraph(f"<b>Condición IVA:</b> {condicion_iva}", estilo_texto),
                 Paragraph(f"<b>Domicilio Comercial:</b> {comprobante.cliente_domicilio or '-'}", estilo_texto)],
                [Paragraph(f"<b>Condición de Venta:</b> {comprobante.get_condicion_venta_display()}", estilo_texto),
                 Paragraph(f"<b>Moneda:</b> {comprobante.get_moneda_display()}", estilo_texto)]
            ]

            # Ancho de 9cm y 9cm suma 18cm en total, exactamente igual a la cabecera (8+2+8)
            receptor_table = Table(receptor_y_condiciones_data, colWidths=[9*cm, 9*cm])
            receptor_table.setStyle(TableStyle([
                ('BOX', (0, 0), (-1, -1), 1, colors.black),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('LEFTPADDING', (0, 0), (-1, -1), 8),
                ('TOPPADDING', (0, 0), (-1, -1), 5),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ]))
            story.append(receptor_table)
            story.append(Spacer(1, 0.5*cm)) # Este sí lo dejamos para separar del detalle de ítems

            # ================= 3. DETALLE DE CONCEPTOS =================
            items_header = [
                Paragraph("<b>Cant.</b>", estilo_bold),
                Paragraph("<b>Descripción</b>", estilo_bold),
                Paragraph("<b>Precio Unit.</b>", ParagraphStyle('R', parent=estilo_bold, alignment=TA_RIGHT)),
                Paragraph("<b>Importe</b>", ParagraphStyle('R', parent=estilo_bold, alignment=TA_RIGHT))
            ]
            items_data = [items_header]

            for item in comprobante.items.all():
                p_unitario = item.precio_unitario if hasattr(item, 'precio_unitario') else (item.subtotal / item.cantidad if item.cantidad else 0)
                
                items_data.append([
                    Paragraph(str(item.cantidad), estilo_texto),
                    Paragraph(item.descripcion, estilo_texto),
                    Paragraph(f"${p_unitario:,.2f}", ParagraphStyle('R', parent=estilo_texto, alignment=TA_RIGHT)),
                    Paragraph(f"${item.subtotal:,.2f}", ParagraphStyle('R', parent=estilo_texto, alignment=TA_RIGHT))
                ])

            items_table = Table(items_data, colWidths=[2*cm, 10*cm, 3*cm, 3*cm])
            items_table.setStyle(TableStyle([
                ('BOX', (0, 0), (-1, -1), 1, colors.black),
                # Modificación: En lugar de GRID (que hace cuadros internos), definimos solo las líneas que queremos
                ('LINEBELOW', (0, 0), (-1, 0), 1, colors.black), # Línea debajo del encabezado
                ('LINEAFTER', (0, 0), (-2, -1), 0.5, colors.HexColor('#bdc3c7')), # Separadores verticales de columnas
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e0e0e0')), # Gris claro tipo AFIP
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('TOPPADDING', (0, 0), (-1, -1), 5),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ]))
            story.append(items_table)
            
            # ELIMINADO: Spacer entre ítems y totales

            # ================= 4. TOTALES =================
            totales_data = [
                ["", Paragraph("<b>Subtotal:</b>", ParagraphStyle('R', parent=estilo_bold, alignment=TA_RIGHT)), Paragraph(f"${comprobante.total:,.2f}", ParagraphStyle('R', parent=estilo_bold, alignment=TA_RIGHT))],
                ["", Paragraph("<b>TOTAL A PAGAR:</b>", ParagraphStyle('R', parent=estilo_bold, alignment=TA_RIGHT, fontSize=11)), Paragraph(f"${comprobante.total:,.2f}", ParagraphStyle('R', parent=estilo_bold, alignment=TA_RIGHT, fontSize=11))]
            ]

            totales_table = Table(totales_data, colWidths=[10*cm, 4*cm, 4*cm])
            totales_table.setStyle(TableStyle([
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('TOPPADDING', (0, 0), (-1, -1), 5),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
                ('BOX', (1, 0), (-1, -1), 1, colors.black),
                # Mantenemos el GRID interno solo para la cajita de totales (las 4 celdas)
                ('GRID', (1, 0), (-1, -1), 0.5, colors.black),
                ('BACKGROUND', (1, -1), (-1, -1), colors.HexColor('#e0e0e0')),
            ]))
            story.append(totales_table)
            story.append(Spacer(1, 1.5*cm))


        # # ================= 5. FIRMAS =================
        #     firma_data = [
        #         ['_________________________', '_________________________'],
        #         ['Aclaración y Firma Emisor', 'Aclaración y Firma Receptor']
        #     ]
        #     firma_table = Table(firma_data, colWidths=[9*cm, 9*cm])
        #     firma_table.setStyle(TableStyle([
        #         ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        #         ('FONTNAME', (0, 1), (-1, 1), 'Helvetica'),
        #         ('FONTSIZE', (0, 1), (-1, 1), 8),
        #         # REDUCIDO: Bajamos el padding interno de 10 a 5 para que el texto esté más pegado a la línea
        #         ('TOPPADDING', (0, 0), (-1, -1), 5), 
        #     ]))
        #     story.append(firma_table)

        #     # Leyenda
        #     # ESPACIO REDUCIDO: Bajamos de 1*cm a 0.5*cm
        #     story.append(Spacer(1, 0.5*cm)) 
        #     story.append(Paragraph("Este documento es un recibo interno sin validez fiscal.", styles['Italic']))

        #     doc.build(story)
        #     buffer.seek(0)
        #     filename = f"recibo_{comprobante.numero_completo}_{comprobante.uuid}.pdf"
        #     comprobante.pdf.save(filename, File(buffer))
        #     return comprobante.pdf.path

        # ========== DISEÑO ORIGINAL PARA OTROS COMPROBANTES ==========
        # (Facturas, notas de crédito, etc.)

        # ========== CABECERA CON LOGO ==========
        if comprobante.contribuyente.logo and comprobante.contribuyente.logo.path:
            try:
                logo = Image(comprobante.contribuyente.logo.path, width=3*cm, height=3*cm)
                logo.hAlign = 'CENTER'
                story.append(logo)
                story.append(Spacer(1, 0.5*cm))
            except:
                pass

        # ========== TÍTULO DEL COMPROBANTE ==========
        tipo_comprobante = comprobante.get_tipo_display()
        story.append(Paragraph(tipo_comprobante, titulo_estilo))
        story.append(Paragraph(f"N°: {comprobante.numero_completo}", subtitulo_estilo))
        story.append(Spacer(1, 1*cm))

        # ========== INFORMACIÓN DEL EMISOR ==========
        emisor_data = [
            ['EMISOR', ''],
            ['Razón Social:', comprobante.contribuyente.razon_social],
            ['CUIT:', comprobante.contribuyente.cuit],
            ['Domicilio:', comprobante.contribuyente.domicilio],
            ['Condición IVA:', comprobante.contribuyente.get_tipo_responsabilidad_display()],
            ['Inicio Actividades:', comprobante.contribuyente.fecha_inicio_actividades.strftime('%d/%m/%Y') if comprobante.contribuyente.fecha_inicio_actividades else ''],
        ]

        if comprobante.contribuyente.nro_iibb:
            emisor_data.append(['N° IIBB:', comprobante.contribuyente.nro_iibb])

        emisor_table = Table(emisor_data, colWidths=[4*cm, 10*cm])
        emisor_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3498db')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#ecf0f1')),
            ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#bdc3c7')),
            ('LEFTPADDING', (0, 0), (0, -1), 6),
            ('RIGHTPADDING', (-1, 0), (-1, -1), 6),
        ]))

        story.append(emisor_table)
        story.append(Spacer(1, 0.8*cm))

        # ========== INFORMACIÓN DEL RECEPTOR ==========
        receptor_data = [
            ['RECEPTOR', ''],
            ['Nombre/Razón Social:', comprobante.cliente_razon_social],
            ['Documento:', f"{comprobante.get_cliente_tipo_documento_display()} {comprobante.cliente_numero_documento}"],
            ['Condición IVA:', comprobante.get_cliente_condicion_iva_display()],
        ]

        if comprobante.cliente_domicilio:
            receptor_data.append(['Domicilio:', comprobante.cliente_domicilio])

        if comprobante.cliente_email:
            receptor_data.append(['Email:', comprobante.cliente_email])

        receptor_table_orig = Table(receptor_data, colWidths=[4*cm, 10*cm])
        receptor_table_orig.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2ecc71')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#ecf0f1')),
            ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#bdc3c7')),
            ('LEFTPADDING', (0, 0), (0, -1), 6),
            ('RIGHTPADDING', (-1, 0), (-1, -1), 6),
        ]))

        story.append(receptor_table_orig)
        story.append(Spacer(1, 1*cm))

        # ========== DETALLE DE ITEMS ==========
        items_header_orig = [
            'Código', 'Descripción', 'Cant.',
            'P. Unitario', 'IVA %', 'Subtotal'
        ]

        items_data_orig = [items_header_orig]

        for item in comprobante.items.all().order_by('orden'):
            items_data_orig.append([
                item.codigo or '',
                item.descripcion[:40] + ('...' if len(item.descripcion) > 40 else ''),
                f"{item.cantidad}",
                f"${item.precio_unitario:,.2f}",
                f"{item.iva_porcentaje}%",
                f"${item.subtotal:,.2f}"
            ])

        items_table_orig = Table(items_data_orig, colWidths=[2*cm, 6.5*cm, 1.5*cm, 2*cm, 1.5*cm, 2*cm])
        items_table_orig.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#34495e')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
            ('ALIGN', (2, 1), (-1, -1), 'RIGHT'),
            ('ALIGN', (0, 1), (0, -1), 'CENTER'),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#bdc3c7')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')]),
        ]))

        story.append(items_table_orig)
        story.append(Spacer(1, 0.8*cm))

        # ========== TOTALES ==========
        totales_data_orig = [
            ['', '', '', '<b>TOTALES</b>', ''],
            ['', '', '', 'Subtotal:', f"${comprobante.subtotal:,.2f}"],
            ['', '', '', 'Descuento:', f"${comprobante.descuento:,.2f}"],
            ['', '', '', 'IVA:', f"${comprobante.iva:,.2f}"],
            ['', '', '', 'Percepciones:', f"${comprobante.percepciones:,.2f}"],
            ['', '', '', 'Retenciones:', f"${comprobante.retenciones:,.2f}"],
            ['', '', '', '', ''],
            ['', '', '', '<b>TOTAL GENERAL:</b>', f"<b>${comprobante.total:,.2f}</b>"],
        ]

        totales_table_orig = Table(totales_data_orig, colWidths=[2*cm, 2*cm, 2*cm, 5*cm, 3*cm])
        totales_table_orig.setStyle(TableStyle([
            ('ALIGN', (3, 0), (3, -1), 'RIGHT'),
            ('ALIGN', (4, 0), (4, -1), 'RIGHT'),
            ('FONTNAME', (3, 0), (3, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (3, 0), (3, 0), 11),
            ('FONTNAME', (3, -1), (4, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (3, -1), (4, -1), 12),
            ('TEXTCOLOR', (4, -1), (4, -1), colors.HexColor('#e74c3c')),
            ('LINEABOVE', (3, -1), (4, -1), 1, colors.black),
            ('TOPPADDING', (3, -1), (4, -1), 6),
            ('BOTTOMPADDING', (3, -1), (4, -1), 6),
        ]))

        story.append(totales_table_orig)
        story.append(Spacer(1, 1*cm))

        # ========== INFORMACIÓN ADICIONAL ==========
        info_adicional = [
            ['Fecha Emisión:', comprobante.fecha_emision.strftime('%d/%m/%Y')],
            ['Condición Venta:', comprobante.get_condicion_venta_display()],
            ['Moneda:', comprobante.get_moneda_display()],
        ]

        if comprobante.fecha_vencimiento:
            info_adicional.append(['Fecha Vencimiento:', comprobante.fecha_vencimiento.strftime('%d/%m/%Y')])

        info_table = Table(info_adicional, colWidths=[4*cm, 10*cm])
        info_table.setStyle(TableStyle([
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#ecf0f1')),
        ]))

        story.append(info_table)
        story.append(Spacer(1, 1*cm))

        # ========== CÓDIGO QR (si tiene CAE) ==========
        if comprobante.arca_cae:
            qr_data = PDFService._generar_qr_data_afip(comprobante)

            qr_img = qrcode.make(qr_data)
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
                qr_img.save(tmp.name)
                qr_image = Image(tmp.name, width=4*cm, height=4*cm)
                qr_image.hAlign = 'CENTER'

                story.append(qr_image)
                story.append(Paragraph("Código QR para verificación", normal_estilo))

                os.unlink(tmp.name)

            cae_data = [
                ['CAE:', comprobante.arca_cae],
                ['Fecha Vto. CAE:', comprobante.arca_fecha_vto_cae.strftime('%d/%m/%Y') if comprobante.arca_fecha_vto_cae else ''],
                ['Resultado ARCA:', comprobante.arca_resultado or 'Aceptado'],
            ]

            cae_table = Table(cae_data, colWidths=[3*cm, 8*cm])
            cae_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f8f9fa')),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#bdc3c7')),
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
            ]))

            story.append(Spacer(1, 0.5*cm))
            story.append(cae_table)

        # ========== OBSERVACIONES ==========
        if comprobante.observaciones:
            story.append(Spacer(1, 1*cm))
            story.append(Paragraph("<b>Observaciones:</b>", etiqueta_estilo))
            story.append(Paragraph(comprobante.observaciones, styles['Normal']))

        # ========== PIE DE PÁGINA ==========
        story.append(Spacer(1, 2*cm))
        pie_texto = f"Comprobante generado el {timezone.now().strftime('%d/%m/%Y %H:%M')} por el sistema de gestión"
        story.append(Paragraph(pie_texto, etiqueta_estilo))

        # ========== CONSTRUIR DOCUMENTO ==========
        doc.build(story)

        buffer.seek(0)
        filename = f"comprobante_{comprobante.numero_completo}_{comprobante.uuid}.pdf"
        comprobante.pdf.save(filename, File(buffer))

        return comprobante.pdf.path

    @staticmethod
    def _generar_qr_data_afip(comprobante):
        """Genera datos para QR según especificaciones AFIP"""
        from datetime import datetime

        tipo_cbte = PDFService._get_codigo_afip_comprobante(comprobante.tipo)
        tipo_doc = PDFService._get_codigo_afip_documento(comprobante.cliente_tipo_documento)

        data = {
            "ver": 1,
            "fecha": comprobante.fecha_emision.strftime("%Y-%m-%d"),
            "cuit": comprobante.contribuyente.cuit.replace('-', ''),
            "ptoVta": comprobante.punto_venta.numero,
            "tipoCmp": tipo_cbte,
            "nroCmp": comprobante.numero,
            "importe": f"{comprobante.total:.2f}",
            "moneda": "PES" if comprobante.moneda == 'ARS' else "DOL",
            "ctz": "1.000" if comprobante.moneda == 'ARS' else "",
            "tipoDocRec": tipo_doc,
            "nroDocRec": comprobante.cliente_numero_documento.replace('-', '').replace('.', ''),
            "tipoCodAut": "E" if comprobante.arca_cae else "A",
            "codAut": comprobante.arca_cae if comprobante.arca_cae else str(comprobante.uuid)[:14],
        }

        import json
        return json.dumps(data)

    @staticmethod
    def _get_codigo_afip_comprobante(tipo_comprobante):
        codigos = {
            'FACTURA_A': 1, 'FACTURA_B': 6, 'FACTURA_C': 11,
            'NOTA_CREDITO_A': 3, 'NOTA_CREDITO_B': 8, 'NOTA_CREDITO_C': 13,
            'NOTA_DEBITO_A': 2, 'NOTA_DEBITO_B': 7, 'NOTA_DEBITO_C': 12,
            'PRESUPUESTO': 0, 'REMITO': 0, 'RECIBO': 0,
        }
        return codigos.get(tipo_comprobante, 0)

    @staticmethod
    def _get_codigo_afip_documento(tipo_documento):
        codigos = {
            'DNI': 96, 'CUIT': 80, 'CUIL': 86, 'PASAPORTE': 94,
        }
        return codigos.get(tipo_documento, 99)

    @staticmethod
    def generar_reporte_ventas(comprobantes, fecha_desde, fecha_hasta):
        """Genera PDF de reporte de ventas"""
        buffer = BytesIO()

        doc = SimpleDocTemplate(
            buffer, pagesize=A4, rightMargin=1.5*cm, leftMargin=1.5*cm,
            topMargin=1.5*cm, bottomMargin=1.5*cm
        )

        story = []
        styles = getSampleStyleSheet()

        titulo = ParagraphStyle(
            'ReporteTitulo', parent=styles['Heading1'], fontSize=14,
            alignment=TA_CENTER, textColor=colors.HexColor('#2c3e50')
        )

        story.append(Paragraph("Reporte de Ventas", titulo))
        story.append(Paragraph(
            f"Período: {fecha_desde.strftime('%d/%m/%Y')} - {fecha_hasta.strftime('%d/%m/%Y')}",
            styles['Normal']
        ))
        story.append(Spacer(1, 1*cm))

        headers = ['Fecha', 'Comprobante', 'Cliente', 'Tipo', 'Total', 'Estado']
        data = [headers]

        total_general = Decimal('0')

        for comp in comprobantes:
            data.append([
                comp.fecha_emision.strftime('%d/%m/%Y'),
                comp.numero_completo,
                comp.cliente_razon_social[:30] + ('...' if len(comp.cliente_razon_social) > 30 else ''),
                comp.get_tipo_display(),
                f"${comp.total:,.2f}",
                comp.get_estado_display()
            ])
            total_general += comp.total

        data.append(['', '', '', '<b>TOTAL</b>', f"<b>${total_general:,.2f}</b>", ''])

        table = Table(data, colWidths=[2.5*cm, 3*cm, 5*cm, 3*cm, 2.5*cm, 2.5*cm])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#34495e')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('BACKGROUND', (0, 1), (-1, -2), colors.white),
            ('GRID', (0, 0), (-1, -2), 0.5, colors.HexColor('#bdc3c7')),
            ('ALIGN', (4, 1), (4, -2), 'RIGHT'),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#ecf0f1')),
            ('TEXTCOLOR', (4, -1), (4, -1), colors.HexColor('#e74c3c')),
        ]))

        story.append(table)
        story.append(Spacer(1, 1*cm))

        stats_data = [
            ['<b>ESTADÍSTICAS</b>', ''],
            ['Total Comprobantes:', str(comprobantes.count())],
            ['Ventas Totales:', f"${total_general:,.2f}"],
            ['Promedio por Comprobante:', f"${total_general / comprobantes.count() if comprobantes.count() > 0 else 0:,.2f}"],
        ]

        stats_table = Table(stats_data, colWidths=[6*cm, 6*cm])
        stats_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3498db')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#bdc3c7')),
        ]))

        story.append(stats_table)
        doc.build(story)

        buffer.seek(0)
        return buffer
    
    
#     """
# Servicio para generación de PDFs de comprobantes
# """
# import os
# import tempfile
# from io import BytesIO
# from decimal import Decimal
# from datetime import datetime

# from reportlab.lib import colors
# from reportlab.lib.pagesizes import A4
# from reportlab.lib.units import cm, mm
# from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT, TA_JUSTIFY
# from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
# from reportlab.platypus import (
#     SimpleDocTemplate, Paragraph, Spacer, Table,
#     TableStyle, Image, KeepTogether, PageBreak
# )
# from reportlab.pdfgen import canvas
# from reportlab.graphics.barcode import qr
# from reportlab.graphics.shapes import Drawing
# from reportlab.graphics import renderPDF

# import qrcode
# from django.core.files import File
# from django.utils import timezone
# from django.conf import settings


# class PDFService:
#     """Servicio para generación de PDFs de comprobantes"""

#     @staticmethod
#     def generar_comprobante_pdf(comprobante):
#         """Genera PDF para un comprobante (recibo, factura, etc.)"""
#         buffer = BytesIO()

#         # Configurar documento
#         doc = SimpleDocTemplate(
#             buffer,
#             pagesize=A4,
#             rightMargin=1.5*cm,
#             leftMargin=1.5*cm,
#             topMargin=1.5*cm,
#             bottomMargin=1.5*cm
#         )

#         story = []
#         styles = getSampleStyleSheet()

#         # ========== ESTILOS PERSONALIZADOS ==========
#         titulo_estilo = ParagraphStyle(
#             'Titulo',
#             parent=styles['Heading1'],
#             fontSize=16,
#             alignment=TA_CENTER,
#             spaceAfter=20,
#             textColor=colors.HexColor('#2c3e50')
#         )

#         subtitulo_estilo = ParagraphStyle(
#             'Subtitulo',
#             parent=styles['Heading2'],
#             fontSize=12,
#             alignment=TA_CENTER,
#             spaceAfter=10,
#             textColor=colors.HexColor('#34495e')
#         )

#         normal_estilo = ParagraphStyle(
#             'NormalCentrado',
#             parent=styles['Normal'],
#             alignment=TA_CENTER,
#             fontSize=10
#         )

#         etiqueta_estilo = ParagraphStyle(
#             'Etiqueta',
#             parent=styles['Normal'],
#             fontSize=9,
#             textColor=colors.HexColor('#7f8c8d')
#         )

#         valor_estilo = ParagraphStyle(
#             'Valor',
#             parent=styles['Normal'],
#             fontSize=10,
#             textColor=colors.HexColor('#2c3e50'),
#             fontName='Helvetica-Bold'
#         )

#         # ========== DISEÑO ESPECIAL PARA RECIBOS ==========
#         if comprobante.tipo == 'RECIBO':
#             # Logo
#             logo_path = None
#             if comprobante.contribuyente.logo and comprobante.contribuyente.logo.path:
#                 logo_path = comprobante.contribuyente.logo.path
#             else:
#                 logo_path = os.path.join(settings.BASE_DIR, 'web', 'static', 'web', 'image', 'logo_sf.jpg')

#             logo_img = None
#             if os.path.exists(logo_path):
#                 try:
#                     # User requested smaller and proportional logo. Set a reasonable width.
#                     logo_img = Image(logo_path, width=2.5*cm, kind='proportional')
#                 except:
#                     pass

#             # Estilos para el recibo
#             title_style_original = ParagraphStyle(
#                 'TituloReciboOriginal',
#                 parent=styles['Heading1'],
#                 fontSize=18,
#                 alignment=TA_CENTER,
#                 textColor=colors.HexColor('#2c3e50'),
#                 spaceAfter=10
#             )
#             title_style_copy = ParagraphStyle(
#                 'TituloReciboCopia',
#                 parent=styles['Heading1'],
#                 fontSize=18,
#                 alignment=TA_CENTER,
#                 textColor=colors.HexColor('#2c3e50'),
#                 spaceAfter=10
#             )
#             normal_style = styles['Normal']
#             bold_style = ParagraphStyle('Bold', parent=normal_style, fontName='Helvetica-Bold')

#             # Helper function to generate common receipt elements
#             def get_receipt_elements(is_original=True):
#                 elements = []
                
#                 # Title and "Original" or "Copia"
#                 status_text = "(ORIGINAL)" if is_original else "(COPIA)"
#                 title_style = title_style_original if is_original else title_style_copy
#                 elements.append(Paragraph(f"RECIBO N°: {comprobante.numero_completo} {status_text}", title_style))
#                 elements.append(Spacer(1, 0.5*cm))

#                 # Prepare content
#                 left_content = []
#                 if logo_img:
#                     left_content.append(logo_img)
#                     left_content.append(Spacer(1, 0.3*cm))
                
#                 # Emitente data
#                 left_content.append(Paragraph(f"<b>{comprobante.contribuyente.razon_social}</b>", bold_style))
#                 left_content.append(Paragraph(comprobante.contribuyente.domicilio, normal_style))
#                 left_content.append(Paragraph(f"CUIT: {comprobante.contribuyente.cuit}", normal_style))
#                 if comprobante.contribuyente.telefono:
#                     left_content.append(Paragraph(f"Tel: {comprobante.contribuyente.telefono}", normal_style))
#                 if comprobante.contribuyente.email:
#                     left_content.append(Paragraph(f"Email: {comprobante.contribuyente.email}", normal_style))

#                 right_content = []
#                 # Cliente data
#                 right_content.append(Paragraph(f"<b>RECIBIDO DE:</b>", bold_style))
#                 right_content.append(Paragraph(f"{comprobante.cliente_razon_social}", normal_style))
#                 right_content.append(Paragraph(f"Documento: {comprobante.get_cliente_tipo_documento_display()} {comprobante.cliente_numero_documento}", normal_style))
#                 if comprobante.cliente_domicilio:
#                     right_content.append(Paragraph(f"Domicilio: {comprobante.cliente_domicilio}", normal_style))

#                 # Data table with two columns
#                 data_table = [[left_content, right_content]]
#                 tabla_datos = Table(data_table, colWidths=[7.5*cm, 7.5*cm])
#                 tabla_datos.setStyle(TableStyle([
#                     ('BOX', (0, 0), (-1, -1), 1, colors.black),
#                     ('VALIGN', (0, 0), (-1, -1), 'TOP'),
#                     ('LEFTPADDING', (0, 0), (-1, -1), 10),
#                     ('RIGHTPADDING', (0, 0), (-1, -1), 10),
#                     ('TOPPADDING', (0, 0), (-1, -1), 10),
#                     ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
#                     ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
#                 ]))
#                 elements.append(tabla_datos)
#                 elements.append(Spacer(1, 0.5*cm))

#                 # Item section
#                 elements.append(Paragraph("<b>Concepto(s) pagado(s):</b>", bold_style))
#                 items_header = ['Cant.', 'Descripción', 'Importe']
#                 items_data = [items_header]
#                 for item in comprobante.items.all():
#                     items_data.append([
#                         f"{item.cantidad}",
#                         item.descripcion,
#                         f"${item.subtotal:,.2f}"
#                     ])
#                 items_table = Table(items_data, colWidths=[2*cm, 8*cm, 4*cm])
#                 items_table.setStyle(TableStyle([
#                     ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#34495e')),
#                     ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
#                     ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
#                     ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
#                     ('FONTSIZE', (0, 0), (-1, 0), 9),
#                     ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#bdc3c7')),
#                     ('ALIGN', (0, 1), (0, -1), 'CENTER'),
#                     ('ALIGN', (2, 1), (2, -1), 'RIGHT'),
#                     ('FONTSIZE', (0, 1), (-1, -1), 9),
#                 ]))
#                 elements.append(items_table)
#                 elements.append(Spacer(1, 0.5*cm))

#                 # Total
#                 elements.append(Paragraph(f"<b>TOTAL:</b> ${comprobante.total:,.2f}", bold_style))
#                 elements.append(Spacer(1, 0.5*cm))

#                 # Payment details
#                 pago_data = [
#                     [f"<b>Fecha:</b> {comprobante.fecha_emision.strftime('%d/%m/%Y')}"],
#                     [f"<b>Forma de pago:</b> {comprobante.get_condicion_venta_display()}"],
#                     [f"<b>Moneda:</b> {comprobante.get_moneda_display()}"],
#                 ]
#                 tabla_pago = Table(pago_data, colWidths=[14*cm])
#                 tabla_pago.setStyle(TableStyle([
#                     ('FONTSIZE', (0, 0), (-1, -1), 10),
#                     ('LEFTPADDING', (0, 0), (-1, -1), 0),
#                 ]))
#                 elements.append(tabla_pago)
#                 elements.append(Spacer(1, 0.5*cm))

#                 # For original, add signatures
#                 if is_original:
#                     firma_data = [
#                         ['_________________________', '_________________________'],
#                         ['Firma del Emisor', 'Firma del Receptor']
#                     ]
#                     firma_table = Table(firma_data, colWidths=[7.5*cm, 7.5*cm])
#                     firma_table.setStyle(TableStyle([
#                         ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
#                         ('FONTSIZE', (0, 0), (-1, -1), 8),
#                         ('TOPPADDING', (0, 0), (-1, -1), 10),
#                     ]))
#                     elements.append(firma_table)
#                     elements.append(Spacer(1, 0.5*cm))

#                 # Final legend
#                 elements.append(Paragraph("Este documento es un recibo interno sin validez fiscal.", styles['Italic']))
                
#                 return elements

#             # Create sections for Original and Copy
#             original_elements = get_receipt_elements(is_original=True)
#             copy_elements = get_receipt_elements(is_original=False)
            
#             # Separator between original and copy
#             separator = Spacer(1, 1.5*cm)

#             # Stack Original on top, then separator, then Copy
#             story.extend(original_elements)
#             story.append(separator)
#             story.extend(copy_elements)

#             doc.build(story)
#             buffer.seek(0)
#             filename = f"recibo_{comprobante.numero_completo}_{comprobante.uuid}.pdf"
#             comprobante.pdf.save(filename, File(buffer))
#             return comprobante.pdf.path

#         # ========== DISEÑO ORIGINAL PARA OTROS COMPROBANTES ==========
#         # (Facturas, notas de crédito, etc.)

#         # ========== CABECERA CON LOGO ==========
#         if comprobante.contribuyente.logo and comprobante.contribuyente.logo.path:
#             try:
#                 logo = Image(comprobante.contribuyente.logo.path, width=4*cm, height=2*cm)
#                 logo.hAlign = 'CENTER'
#                 story.append(logo)
#                 story.append(Spacer(1, 0.5*cm))
#             except:
#                 pass

#         # ========== TÍTULO DEL COMPROBANTE ==========
#         tipo_comprobante = comprobante.get_tipo_display()
#         story.append(Paragraph(tipo_comprobante, titulo_estilo))
#         story.append(Paragraph(f"N°: {comprobante.numero_completo}", subtitulo_estilo))
#         story.append(Spacer(1, 1*cm))

#         # ========== INFORMACIÓN DEL EMISOR ==========
#         emisor_data = [
#             ['EMISOR', ''],
#             ['Razón Social:', comprobante.contribuyente.razon_social],
#             ['CUIT:', comprobante.contribuyente.cuit],
#             ['Domicilio:', comprobante.contribuyente.domicilio],
#             ['Condición IVA:', comprobante.contribuyente.get_tipo_responsabilidad_display()],
#             ['Inicio Actividades:', comprobante.contribuyente.fecha_inicio_actividades.strftime('%d/%m/%Y') if comprobante.contribuyente.fecha_inicio_actividades else ''],
#         ]

#         if comprobante.contribuyente.nro_iibb:
#             emisor_data.append(['N° IIBB:', comprobante.contribuyente.nro_iibb])

#         emisor_table = Table(emisor_data, colWidths=[4*cm, 10*cm])
#         emisor_table.setStyle(TableStyle([
#             ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3498db')),
#             ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
#             ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
#             ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
#             ('FONTSIZE', (0, 0), (-1, 0), 11),
#             ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
#             ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#ecf0f1')),
#             ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
#             ('ALIGN', (0, 0), (0, -1), 'LEFT'),
#             ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
#             ('FONTSIZE', (0, 1), (-1, -1), 9),
#             ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#bdc3c7')),
#             ('LEFTPADDING', (0, 0), (0, -1), 6),
#             ('RIGHTPADDING', (-1, 0), (-1, -1), 6),
#         ]))

#         story.append(emisor_table)
#         story.append(Spacer(1, 0.8*cm))

#         # ========== INFORMACIÓN DEL RECEPTOR ==========
#         receptor_data = [
#             ['RECEPTOR', ''],
#             ['Nombre/Razón Social:', comprobante.cliente_razon_social],
#             ['Documento:', f"{comprobante.get_cliente_tipo_documento_display()} {comprobante.cliente_numero_documento}"],
#             ['Condición IVA:', comprobante.get_cliente_condicion_iva_display()],
#         ]

#         if comprobante.cliente_domicilio:
#             receptor_data.append(['Domicilio:', comprobante.cliente_domicilio])

#         if comprobante.cliente_email:
#             receptor_data.append(['Email:', comprobante.cliente_email])

#         receptor_table = Table(receptor_data, colWidths=[4*cm, 10*cm])
#         receptor_table.setStyle(TableStyle([
#             ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2ecc71')),
#             ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
#             ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
#             ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
#             ('FONTSIZE', (0, 0), (-1, 0), 11),
#             ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
#             ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#ecf0f1')),
#             ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
#             ('ALIGN', (0, 0), (0, -1), 'LEFT'),
#             ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
#             ('FONTSIZE', (0, 1), (-1, -1), 9),
#             ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#bdc3c7')),
#             ('LEFTPADDING', (0, 0), (0, -1), 6),
#             ('RIGHTPADDING', (-1, 0), (-1, -1), 6),
#         ]))

#         story.append(receptor_table)
#         story.append(Spacer(1, 1*cm))

#         # ========== DETALLE DE ITEMS ==========
#         items_header = [
#             'Código', 'Descripción', 'Cant.',
#             'P. Unitario', 'IVA %', 'Subtotal'
#         ]

#         items_data = [items_header]

#         for item in comprobante.items.all().order_by('orden'):
#             items_data.append([
#                 item.codigo or '',
#                 item.descripcion[:40] + ('...' if len(item.descripcion) > 40 else ''),
#                 f"{item.cantidad}",
#                 f"${item.precio_unitario:,.2f}",
#                 f"{item.iva_porcentaje}%",
#                 f"${item.subtotal:,.2f}"
#             ])

#         items_table = Table(items_data, colWidths=[2*cm, 6.5*cm, 1.5*cm, 2*cm, 1.5*cm, 2*cm])
#         items_table.setStyle(TableStyle([
#             ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#34495e')),
#             ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
#             ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
#             ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
#             ('FONTSIZE', (0, 0), (-1, 0), 9),
#             ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
#             ('BACKGROUND', (0, 1), (-1, -1), colors.white),
#             ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
#             ('ALIGN', (2, 1), (-1, -1), 'RIGHT'),
#             ('ALIGN', (0, 1), (0, -1), 'CENTER'),
#             ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
#             ('FONTSIZE', (0, 1), (-1, -1), 8),
#             ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#bdc3c7')),
#             ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')]),
#         ]))

#         story.append(items_table)
#         story.append(Spacer(1, 0.8*cm))

#         # ========== TOTALES ==========
#         totales_data = [
#             ['', '', '', '<b>TOTALES</b>', ''],
#             ['', '', '', 'Subtotal:', f"${comprobante.subtotal:,.2f}"],
#             ['', '', '', 'Descuento:', f"${comprobante.descuento:,.2f}"],
#             ['', '', '', 'IVA:', f"${comprobante.iva:,.2f}"],
#             ['', '', '', 'Percepciones:', f"${comprobante.percepciones:,.2f}"],
#             ['', '', '', 'Retenciones:', f"${comprobante.retenciones:,.2f}"],
#             ['', '', '', '', ''],
#             ['', '', '', '<b>TOTAL GENERAL:</b>', f"<b>${comprobante.total:,.2f}</b>"],
#         ]

#         totales_table = Table(totales_data, colWidths=[2*cm, 2*cm, 2*cm, 5*cm, 3*cm])
#         totales_table.setStyle(TableStyle([
#             ('ALIGN', (3, 0), (3, -1), 'RIGHT'),
#             ('ALIGN', (4, 0), (4, -1), 'RIGHT'),
#             ('FONTNAME', (3, 0), (3, 0), 'Helvetica-Bold'),
#             ('FONTSIZE', (3, 0), (3, 0), 11),
#             ('FONTNAME', (3, -1), (4, -1), 'Helvetica-Bold'),
#             ('FONTSIZE', (3, -1), (4, -1), 12),
#             ('TEXTCOLOR', (4, -1), (4, -1), colors.HexColor('#e74c3c')),
#             ('LINEABOVE', (3, -1), (4, -1), 1, colors.black),
#             ('TOPPADDING', (3, -1), (4, -1), 6),
#             ('BOTTOMPADDING', (3, -1), (4, -1), 6),
#         ]))

#         story.append(totales_table)
#         story.append(Spacer(1, 1*cm))

#         # ========== INFORMACIÓN ADICIONAL ==========
#         info_adicional = [
#             ['Fecha Emisión:', comprobante.fecha_emision.strftime('%d/%m/%Y')],
#             ['Condición Venta:', comprobante.get_condicion_venta_display()],
#             ['Moneda:', comprobante.get_moneda_display()],
#         ]

#         if comprobante.fecha_vencimiento:
#             info_adicional.append(['Fecha Vencimiento:', comprobante.fecha_vencimiento.strftime('%d/%m/%Y')])

#         info_table = Table(info_adicional, colWidths=[4*cm, 10*cm])
#         info_table.setStyle(TableStyle([
#             ('FONTSIZE', (0, 0), (-1, -1), 9),
#             ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
#             ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#ecf0f1')),
#         ]))

#         story.append(info_table)
#         story.append(Spacer(1, 1*cm))

#         # ========== CÓDIGO QR (si tiene CAE) ==========
#         if comprobante.arca_cae:
#             qr_data = PDFService._generar_qr_data_afip(comprobante)

#             qr_img = qrcode.make(qr_data)
#             with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
#                 qr_img.save(tmp.name)
#                 qr_image = Image(tmp.name, width=4*cm, height=4*cm)
#                 qr_image.hAlign = 'CENTER'

#                 story.append(qr_image)
#                 story.append(Paragraph("Código QR para verificación", normal_estilo))

#                 os.unlink(tmp.name)

#             cae_data = [
#                 ['CAE:', comprobante.arca_cae],
#                 ['Fecha Vto. CAE:', comprobante.arca_fecha_vto_cae.strftime('%d/%m/%Y') if comprobante.arca_fecha_vto_cae else ''],
#                 ['Resultado ARCA:', comprobante.arca_resultado or 'Aceptado'],
#             ]

#             cae_table = Table(cae_data, colWidths=[3*cm, 8*cm])
#             cae_table.setStyle(TableStyle([
#                 ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f8f9fa')),
#                 ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#bdc3c7')),
#                 ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
#                 ('FONTSIZE', (0, 0), (-1, -1), 9),
#             ]))

#             story.append(Spacer(1, 0.5*cm))
#             story.append(cae_table)

#         # ========== OBSERVACIONES ==========
#         if comprobante.observaciones:
#             story.append(Spacer(1, 1*cm))
#             story.append(Paragraph("<b>Observaciones:</b>", etiqueta_estilo))
#             story.append(Paragraph(comprobante.observaciones, styles['Normal']))

#         # ========== PIE DE PÁGINA ==========
#         story.append(Spacer(1, 2*cm))
#         pie_texto = f"Comprobante generado el {timezone.now().strftime('%d/%m/%Y %H:%M')} por el sistema de gestión"
#         story.append(Paragraph(pie_texto, etiqueta_estilo))

#         # ========== CONSTRUIR DOCUMENTO ==========
#         doc.build(story)

#         buffer.seek(0)
#         filename = f"comprobante_{comprobante.numero_completo}_{comprobante.uuid}.pdf"
#         comprobante.pdf.save(filename, File(buffer))

#         return comprobante.pdf.path

#     @staticmethod
#     def _generar_qr_data_afip(comprobante):
#         """Genera datos para QR según especificaciones AFIP"""
#         from datetime import datetime

#         tipo_cbte = PDFService._get_codigo_afip_comprobante(comprobante.tipo)
#         tipo_doc = PDFService._get_codigo_afip_documento(comprobante.cliente_tipo_documento)

#         data = {
#             "ver": 1,
#             "fecha": comprobante.fecha_emision.strftime("%Y-%m-%d"),
#             "cuit": comprobante.contribuyente.cuit.replace('-', ''),
#             "ptoVta": comprobante.punto_venta.numero,
#             "tipoCmp": tipo_cbte,
#             "nroCmp": comprobante.numero,
#             "importe": f"{comprobante.total:.2f}",
#             "moneda": "PES" if comprobante.moneda == 'ARS' else "DOL",
#             "ctz": "1.000" if comprobante.moneda == 'ARS' else "",
#             "tipoDocRec": tipo_doc,
#             "nroDocRec": comprobante.cliente_numero_documento.replace('-', '').replace('.', ''),
#             "tipoCodAut": "E" if comprobante.arca_cae else "A",
#             "codAut": comprobante.arca_cae if comprobante.arca_cae else str(comprobante.uuid)[:14],
#         }

#         import json
#         return json.dumps(data)

#     @staticmethod
#     def _get_codigo_afip_comprobante(tipo_comprobante):
#         codigos = {
#             'FACTURA_A': 1, 'FACTURA_B': 6, 'FACTURA_C': 11,
#             'NOTA_CREDITO_A': 3, 'NOTA_CREDITO_B': 8, 'NOTA_CREDITO_C': 13,
#             'NOTA_DEBITO_A': 2, 'NOTA_DEBITO_B': 7, 'NOTA_DEBITO_C': 12,
#             'PRESUPUESTO': 0, 'REMITO': 0, 'RECIBO': 0,
#         }
#         return codigos.get(tipo_comprobante, 0)

#     @staticmethod
#     def _get_codigo_afip_documento(tipo_documento):
#         codigos = {
#             'DNI': 96, 'CUIT': 80, 'CUIL': 86, 'PASAPORTE': 94,
#         }
#         return codigos.get(tipo_documento, 99)

#     @staticmethod
#     def generar_reporte_ventas(comprobantes, fecha_desde, fecha_hasta):
#         """Genera PDF de reporte de ventas"""
#         buffer = BytesIO()

#         doc = SimpleDocTemplate(
#             buffer, pagesize=A4, rightMargin=1.5*cm, leftMargin=1.5*cm,
#             topMargin=1.5*cm, bottomMargin=1.5*cm
#         )

#         story = []
#         styles = getSampleStyleSheet()

#         titulo = ParagraphStyle(
#             'ReporteTitulo', parent=styles['Heading1'], fontSize=14,
#             alignment=TA_CENTER, textColor=colors.HexColor('#2c3e50')
#         )

#         story.append(Paragraph("Reporte de Ventas", titulo))
#         story.append(Paragraph(
#             f"Período: {fecha_desde.strftime('%d/%m/%Y')} - {fecha_hasta.strftime('%d/%m/%Y')}",
#             styles['Normal']
#         ))
#         story.append(Spacer(1, 1*cm))

#         headers = ['Fecha', 'Comprobante', 'Cliente', 'Tipo', 'Total', 'Estado']
#         data = [headers]

#         total_general = Decimal('0')

#         for comp in comprobantes:
#             data.append([
#                 comp.fecha_emision.strftime('%d/%m/%Y'),
#                 comp.numero_completo,
#                 comp.cliente_razon_social[:30] + ('...' if len(comp.cliente_razon_social) > 30 else ''),
#                 comp.get_tipo_display(),
#                 f"${comp.total:,.2f}",
#                 comp.get_estado_display()
#             ])
#             total_general += comp.total

#         data.append(['', '', '', '<b>TOTAL</b>', f"<b>${total_general:,.2f}</b>", ''])

#         table = Table(data, colWidths=[2.5*cm, 3*cm, 5*cm, 3*cm, 2.5*cm, 2.5*cm])
#         table.setStyle(TableStyle([
#             ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#34495e')),
#             ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
#             ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
#             ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
#             ('FONTSIZE', (0, 0), (-1, 0), 9),
#             ('BACKGROUND', (0, 1), (-1, -2), colors.white),
#             ('GRID', (0, 0), (-1, -2), 0.5, colors.HexColor('#bdc3c7')),
#             ('ALIGN', (4, 1), (4, -2), 'RIGHT'),
#             ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
#             ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#ecf0f1')),
#             ('TEXTCOLOR', (4, -1), (4, -1), colors.HexColor('#e74c3c')),
#         ]))

#         story.append(table)
#         story.append(Spacer(1, 1*cm))

#         stats_data = [
#             ['<b>ESTADÍSTICAS</b>', ''],
#             ['Total Comprobantes:', str(comprobantes.count())],
#             ['Ventas Totales:', f"${total_general:,.2f}"],
#             ['Promedio por Comprobante:', f"${total_general / comprobantes.count() if comprobantes.count() > 0 else 0:,.2f}"],
#         ]

#         stats_table = Table(stats_data, colWidths=[6*cm, 6*cm])
#         stats_table.setStyle(TableStyle([
#             ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3498db')),
#             ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
#             ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
#             ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
#             ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#bdc3c7')),
#         ]))

#         story.append(stats_table)
#         doc.build(story)

#         buffer.seek(0)
#         return buffer