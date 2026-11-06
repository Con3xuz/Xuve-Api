#!/usr/bin/env python3
"""
OMNI SuperApp - Generador de PDF para Presentación Ejecutiva
"""

import os
import requests
from io import BytesIO
from datetime import datetime

from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, cm
from reportlab.lib.colors import HexColor, black, white, grey
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    Image,
    PageBreak,
    ListFlowable,
    ListItem,
)
from reportlab.pdfgen import canvas

# Colors
OMNI_GREEN = HexColor("#39FF14")
OMNI_DARK = HexColor("#121212")
OMNI_GRAY = HexColor("#1a1a1a")
OMNI_LIGHT_GRAY = HexColor("#2a2a2a")
WHITE = HexColor("#FFFFFF")
YELLOW = HexColor("#FFD700")
RED = HexColor("#FF4444")

LOGO_URL = "https://static.prod-images.emergentagent.com/jobs/de9f300e-f299-48e4-a7f1-8491aaf96611/images/75fd3fd65491a025809deae7edff66ef4d08f4ad71685d2df376a8ed4bbed89e.png"


def download_logo():
    """Download logo from URL"""
    try:
        response = requests.get(LOGO_URL, timeout=10)
        if response.status_code == 200:
            return BytesIO(response.content)
    except:
        pass
    return None


class OMNIPDFGenerator:
    def __init__(self, output_path):
        self.output_path = output_path
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()

    def _setup_custom_styles(self):
        """Setup custom paragraph styles"""
        self.styles.add(
            ParagraphStyle(
                name="OMNITitle",
                fontSize=28,
                leading=34,
                textColor=OMNI_GREEN,
                alignment=TA_CENTER,
                fontName="Helvetica-Bold",
                spaceAfter=20,
            )
        )

        self.styles.add(
            ParagraphStyle(
                name="OMNISubtitle",
                fontSize=14,
                leading=18,
                textColor=grey,
                alignment=TA_CENTER,
                fontName="Helvetica",
                spaceAfter=30,
            )
        )

        self.styles.add(
            ParagraphStyle(
                name="SectionTitle",
                fontSize=18,
                leading=22,
                textColor=OMNI_GREEN,
                fontName="Helvetica-Bold",
                spaceBefore=20,
                spaceAfter=12,
            )
        )

        self.styles.add(
            ParagraphStyle(
                name="SubsectionTitle",
                fontSize=14,
                leading=18,
                textColor=HexColor("#4DFF91"),
                fontName="Helvetica-Bold",
                spaceBefore=15,
                spaceAfter=8,
            )
        )

        self.styles.add(
            ParagraphStyle(
                name="OMNIBodyText",
                fontSize=10,
                leading=14,
                textColor=black,
                fontName="Helvetica",
                alignment=TA_JUSTIFY,
                spaceAfter=8,
            )
        )

        self.styles.add(
            ParagraphStyle(
                name="TableHeader",
                fontSize=10,
                leading=12,
                textColor=white,
                fontName="Helvetica-Bold",
                alignment=TA_CENTER,
            )
        )

        self.styles.add(
            ParagraphStyle(
                name="TableCell",
                fontSize=9,
                leading=11,
                textColor=black,
                fontName="Helvetica",
                alignment=TA_LEFT,
            )
        )

    def create_table(self, data, col_widths=None, header_color=OMNI_GREEN):
        """Create a styled table"""
        if col_widths is None:
            col_widths = [2 * inch] * len(data[0])

        table = Table(data, colWidths=col_widths)

        style = TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), header_color),
                ("TEXTCOLOR", (0, 0), (-1, 0), white),
                ("ALIGN", (0, 0), (-1, 0), "CENTER"),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 10),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 10),
                ("TOPPADDING", (0, 0), (-1, 0), 10),
                ("BACKGROUND", (0, 1), (-1, -1), HexColor("#F5F5F5")),
                ("TEXTCOLOR", (0, 1), (-1, -1), black),
                ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 1), (-1, -1), 9),
                ("ALIGN", (0, 1), (-1, -1), "LEFT"),
                ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#CCCCCC")),
                (
                    "ROWBACKGROUNDS",
                    (0, 1),
                    (-1, -1),
                    [HexColor("#FFFFFF"), HexColor("#F0F0F0")],
                ),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 1), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 1), (-1, -1), 6),
            ]
        )

        table.setStyle(style)
        return table

    def generate(self):
        """Generate the PDF document"""
        doc = SimpleDocTemplate(
            self.output_path,
            pagesize=letter,
            rightMargin=0.75 * inch,
            leftMargin=0.75 * inch,
            topMargin=0.75 * inch,
            bottomMargin=0.75 * inch,
        )

        story = []

        # ============ COVER PAGE ============
        story.append(Spacer(1, 1 * inch))

        # Logo
        logo_data = download_logo()
        if logo_data:
            logo = Image(logo_data, width=2 * inch, height=2 * inch)
            logo.hAlign = "CENTER"
            story.append(logo)

        story.append(Spacer(1, 0.5 * inch))
        story.append(Paragraph("OMNI SuperApp", self.styles["OMNITitle"]))
        story.append(
            Paragraph(
                "Plataforma de Movilidad y Comercio para Venezuela",
                self.styles["OMNISubtitle"],
            )
        )
        story.append(Spacer(1, 0.5 * inch))

        # Cover info box
        cover_data = [
            ["RESUMEN EJECUTIVO"],
            [f'Fecha: {datetime.now().strftime("%d de Marzo, 2026")}'],
            ["Estado: BETA 1.0 - Funcional"],
            ["Versión del Documento: 1.0"],
        ]
        cover_table = Table(cover_data, colWidths=[4 * inch])
        cover_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), OMNI_GREEN),
                    ("TEXTCOLOR", (0, 0), (-1, 0), black),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, 0), 12),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("BACKGROUND", (0, 1), (-1, -1), HexColor("#F5F5F5")),
                    ("GRID", (0, 0), (-1, -1), 1, OMNI_GREEN),
                    ("TOPPADDING", (0, 0), (-1, -1), 10),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                ]
            )
        )
        cover_table.hAlign = "CENTER"
        story.append(cover_table)

        story.append(PageBreak())

        # ============ PAGE 2: QUÉ ES OMNI ============
        story.append(Paragraph("1. ¿Qué es OMNI?", self.styles["SectionTitle"]))
        story.append(
            Paragraph(
                "<b>OMNI</b> es una <b>SuperApp de movilidad y comercio</b> diseñada específicamente para "
                "<b>Venezuela</b>, que integra múltiples servicios de transporte, delivery, marketplace y "
                "alquiler de vehículos en una sola plataforma.",
                self.styles["OMNIBodyText"],
            )
        )
        story.append(Spacer(1, 0.2 * inch))

        # Key features
        story.append(Paragraph("Propuesta de Valor", self.styles["SubsectionTitle"]))
        features = [
            "Una sola app para transporte, delivery, market y alquiler",
            "Modelo B2B y B2C - Terminales, líneas urbanas y usuarios finales",
            "Billetera digital con tasa BCV en tiempo real",
            "Diseño venezolano - Fondos de paisajes nacionales",
            "Funciona sin mapa - Fallbacks de texto para zonas con mala conexión",
            "Sistema de garantías - Hold de fondos para alquileres",
            "Chat integrado - Comunicación fluida entre todas las partes",
        ]
        for f in features:
            story.append(Paragraph(f"• {f}", self.styles["OMNIBodyText"]))

        story.append(Spacer(1, 0.3 * inch))

        # ============ FUNCIONALIDADES ACTIVAS ============
        story.append(
            Paragraph(
                "2. Funcionalidades Activas (100% Operativas)",
                self.styles["SectionTitle"],
            )
        )

        # 2.1 Transporte Urbano
        story.append(
            Paragraph(
                "2.1 Transporte Urbano (Taxis/Carros)", self.styles["SubsectionTitle"]
            )
        )
        taxi_data = [
            ["Característica", "Descripción"],
            ["Solicitar viaje", "Búsqueda por texto (sin depender del mapa)"],
            ["Tipos de vehículo", "Carro particular, Taxi de línea, Mototaxi"],
            ["Tarifa estimada", "Cálculo automático por distancia y tiempo"],
            ["GPS en tiempo real", "Tracking del conductor"],
            ["Chat con conductor", "Comunicación estilo Uber durante el viaje"],
        ]
        story.append(self.create_table(taxi_data, [1.8 * inch, 4.2 * inch]))
        story.append(Spacer(1, 0.2 * inch))

        # 2.2 Transporte Público
        story.append(
            Paragraph(
                "2.2 Transporte Público (Busetas)", self.styles["SubsectionTitle"]
            )
        )
        buseta_data = [
            ["Característica", "Descripción"],
            ["Rutas urbanas", "Gestión de líneas con waypoints y paradas"],
            ["Torniquete digital", "QR único por chofer para cobro de pasaje"],
            ["Vista de rutas", "Mapa o Lista (toggle)"],
            ["Pago de pasaje", "Escáner QR + descuento de wallet"],
            ["Fee fijo", "$0.02 USD por pasaje para OMNI"],
        ]
        story.append(self.create_table(buseta_data, [1.8 * inch, 4.2 * inch]))
        story.append(Spacer(1, 0.2 * inch))

        # 2.3 Terminales
        story.append(
            Paragraph(
                "2.3 Terminales Interurbanos (B2B)", self.styles["SubsectionTitle"]
            )
        )
        terminal_data = [
            ["Característica", "Descripción"],
            ["Gestión de viajes", "Programación con destino, precio, asientos"],
            ["Billetera centralizada", "Saldo por línea con comisión del 10%"],
            ["Flota y choferes", "CRUD completo de vehículos y operadores"],
            ["Venta de boletos", "Sistema de reservas y pagos"],
        ]
        story.append(self.create_table(terminal_data, [1.8 * inch, 4.2 * inch]))

        story.append(PageBreak())

        # 2.4 Delivery
        story.append(
            Paragraph("2.4 Delivery y Marketplace", self.styles["SubsectionTitle"])
        )
        delivery_data = [
            ["Característica", "Descripción"],
            ["Tiendas", "14 categorías (Restaurante, Farmacia, etc.)"],
            ["Productos", "Catálogo con fotos y precios"],
            ["Carrito", "Agregar productos y checkout"],
            ["Pedidos", "Flujo: Entrante → Preparando → Listo → Entregado"],
            ["Chat con repartidor", "Comunicación durante la entrega"],
        ]
        story.append(self.create_table(delivery_data, [1.8 * inch, 4.2 * inch]))
        story.append(Spacer(1, 0.2 * inch))

        # 2.5 Rent-a-Car
        story.append(
            Paragraph("2.5 Rent-a-Car (Alquiler P2P)", self.styles["SubsectionTitle"])
        )
        rent_data = [
            ["Característica", "Descripción"],
            ["Publicar vehículos", "Fotos, precio/día, descripción"],
            ["Calendario", "Disponibilidad por fechas"],
            ["Depósito de garantía", "Hold automático (2 días como garantía)"],
            ["Solicitudes", "Sistema de aprobar/rechazar"],
            ["Chat con dueño", "Coordinación de entrega"],
        ]
        story.append(self.create_table(rent_data, [1.8 * inch, 4.2 * inch]))
        story.append(Spacer(1, 0.2 * inch))

        # 2.6 Chat
        story.append(
            Paragraph("2.6 Sistema de Chat Integrado", self.styles["SubsectionTitle"])
        )
        chat_data = [
            ["Tipo", "Descripción"],
            ["Chat Operativo", "Soporte OMNI, mensajes generales"],
            ["Chat de Servicio", "Cliente ↔ Conductor/Repartidor (estilo Uber)"],
            ["Mensajes rápidos", "Predefinidos según rol"],
            ["Compartir ubicación", "Link de Google Maps en tiempo real"],
        ]
        story.append(self.create_table(chat_data, [1.8 * inch, 4.2 * inch]))
        story.append(Spacer(1, 0.2 * inch))

        # 2.7 KYC
        story.append(
            Paragraph(
                "2.7 Sistema KYC (Know Your Customer)", self.styles["SubsectionTitle"]
            )
        )
        kyc_data = [
            ["Característica", "Descripción"],
            ["Wizard adaptativo", "Formularios dinámicos según el rol"],
            ["9 tipos de socios", "Conductor, Repartidor, Comercial, Línea, etc."],
            ["Documentos", "Cédula, Licencia, RCV, Fotos de vehículo/local"],
            ["Panel Admin", "Aprobar/Rechazar con un clic"],
            ["Notificaciones", "Al usuario cuando se aprueba/rechaza"],
        ]
        story.append(self.create_table(kyc_data, [1.8 * inch, 4.2 * inch]))

        story.append(PageBreak())

        # ============ MODELO DE NEGOCIO ============
        story.append(
            Paragraph("3. Modelo de Negocio - Comisiones", self.styles["SectionTitle"])
        )

        comision_data = [
            ["Vertical", "Comisión OMNI"],
            ["Transporte (Taxis)", "10%"],
            ["Market/Delivery", "12%"],
            ["Rent-a-Car", "10%"],
            ["Terminales B2B", "10%"],
            ["Líneas Urbanas B2B", "10%"],
            ["Busetas (Fee fijo)", "$0.02 por pasaje"],
        ]
        story.append(
            self.create_table(comision_data, [3 * inch, 3 * inch], HexColor("#2E7D32"))
        )
        story.append(Spacer(1, 0.3 * inch))

        # ============ ROLES ============
        story.append(
            Paragraph("4. Roles de Usuario (11 tipos)", self.styles["SectionTitle"])
        )

        roles_data = [
            ["Rol", "Dashboard", "Descripción"],
            [
                "Cliente/Usuario",
                "/dashboard/cliente",
                "Pide servicios, compra, alquila",
            ],
            ["Conductor", "/dashboard/conductor", "Acepta viajes de taxi"],
            ["Repartidor", "/dashboard/repartidor", "Entrega pedidos del market"],
            ["Comercial", "/dashboard/comercial", "Gestiona su tienda y pedidos"],
            ["Rent Owner", "/dashboard/rent", "Publica vehículos para alquiler"],
            ["Carga Pesada", "/dashboard/carga", "Operador de fletes"],
            ["Admin Terminal", "/dashboard/linea", "Gestiona terminal interurbano"],
            [
                "Admin Línea Urbana",
                "/dashboard/linea-urbana",
                "Gestiona rutas de busetas",
            ],
            ["Chofer Interurbano", "/dashboard/chofer", "Conduce en terminales"],
            ["Chofer Urbano", "/dashboard/chofer-urbano", "Conduce buseta con QR"],
            ["Administrador", "/admin", "Control total del sistema"],
        ]
        story.append(self.create_table(roles_data, [1.5 * inch, 2 * inch, 2.5 * inch]))

        story.append(PageBreak())

        # ============ TAREAS PENDIENTES ============
        story.append(
            Paragraph("5. Roadmap - Tareas Pendientes", self.styles["SectionTitle"])
        )

        # P1
        story.append(
            Paragraph("🔴 Alta Prioridad (P1)", self.styles["SubsectionTitle"])
        )
        p1_data = [
            ["Tarea", "Beneficio"],
            ["Notificaciones Push", "Alertas instantáneas a conductores/comercios"],
            [
                "Búsqueda automática de repartidor",
                "Al aceptar pedido, asignar automáticamente",
            ],
            ["Integración Stripe/PayPal", "Recargas de wallet con tarjetas"],
        ]
        story.append(
            self.create_table(p1_data, [3 * inch, 3 * inch], HexColor("#D32F2F"))
        )
        story.append(Spacer(1, 0.2 * inch))

        # P2
        story.append(
            Paragraph("🟡 Media Prioridad (P2)", self.styles["SubsectionTitle"])
        )
        p2_data = [
            ["Tarea", "Beneficio"],
            ["Persistencia del carrito", "No perder items al navegar"],
            ["Tracking de repartidor", "Cliente ve en tiempo real dónde va su pedido"],
        ]
        story.append(
            self.create_table(p2_data, [3 * inch, 3 * inch], HexColor("#FFA000"))
        )
        story.append(Spacer(1, 0.2 * inch))

        # P3
        story.append(
            Paragraph("🟢 Baja Prioridad (P3)", self.styles["SubsectionTitle"])
        )
        p3_data = [
            ["Tarea", "Beneficio"],
            ["Sistema de cupones", "Promociones y descuentos"],
            ["Programa de referidos", "Crecimiento viral"],
            ["Reportes y analytics", "Dashboard de métricas para admins"],
        ]
        story.append(
            self.create_table(p3_data, [3 * inch, 3 * inch], HexColor("#388E3C"))
        )

        story.append(Spacer(1, 0.3 * inch))

        # ============ TECNOLOGÍAS ============
        story.append(Paragraph("6. Stack Tecnológico", self.styles["SectionTitle"]))

        tech_data = [
            ["Capa", "Tecnología"],
            ["Frontend", "React 18, Tailwind CSS, Framer Motion, Shadcn/UI"],
            ["Backend", "FastAPI (Python), Pydantic"],
            ["Base de Datos", "MongoDB"],
            ["Mapas", "Google Maps API + Nominatim (fallback)"],
            ["QR", "Scanner y Generador integrados"],
            ["Autenticación", "JWT + Google OAuth"],
            ["PWA", "Instalable como app nativa"],
        ]
        story.append(self.create_table(tech_data, [2 * inch, 4 * inch]))

        story.append(PageBreak())

        # ============ ESTADO ACTUAL ============
        story.append(
            Paragraph("7. Estado Actual: BETA 1.0", self.styles["SectionTitle"])
        )

        status_data = [
            ["Métrica", "Valor"],
            ["Tests Backend", "116+ pasados"],
            ["Tests Frontend", "100% verificado"],
            ["Roles funcionales", "11/11"],
            ["Dashboards operativos", "11/11"],
            ["Flujos E2E probados", "14+"],
        ]
        story.append(
            self.create_table(status_data, [3 * inch, 3 * inch], HexColor("#1976D2"))
        )
        story.append(Spacer(1, 0.3 * inch))

        # Credenciales
        story.append(Paragraph("Credenciales de Demo", self.styles["SubsectionTitle"]))
        creds_data = [
            ["Rol", "Email", "Password"],
            ["Admin", "admin@omni.ve", "admin123"],
            ["Cliente", "cliente@omni.ve", "cliente123"],
            ["Conductor", "conductor@omni.ve", "conductor123"],
            ["Repartidor", "repartidor@omni.ve", "repartidor123"],
            ["Comercial", "comercial@omni.ve", "comercial123"],
            ["Línea Urbana", "linea@omni.ve", "linea123"],
        ]
        story.append(self.create_table(creds_data, [1.5 * inch, 2.5 * inch, 2 * inch]))

        story.append(Spacer(1, 0.5 * inch))

        # Final note
        story.append(Paragraph("Problemas Conocidos", self.styles["SubsectionTitle"]))
        story.append(
            Paragraph(
                "<b>Google Maps:</b> Muestra marca de agua 'For development purposes only'. "
                "Requiere activar facturación en Google Cloud Console. "
                "<b>Solución implementada:</b> Fallbacks de búsqueda por texto que funcionan 100% sin el mapa.",
                self.styles["OMNIBodyText"],
            )
        )

        # Build PDF
        doc.build(story)
        return self.output_path


if __name__ == "__main__":
    output_file = "/app/OMNI_SuperApp_Presentacion_Ejecutiva.pdf"
    generator = OMNIPDFGenerator(output_file)
    result = generator.generate()
    print(f"PDF generado exitosamente: {result}")
