from odoo import models, fields, api
import logging
from datetime import datetime
from io import BytesIO
import base64
import os

try:
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
    from reportlab.lib.units import inch
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    from PyPDF2 import PdfWriter, PdfReader
except ImportError as e:
    logging.getLogger(__name__).warning(f"Required libraries not installed: {e}. PDF generation will not work.")

_logger = logging.getLogger(__name__)


class AccountMoveWarranty(models.Model):
    _inherit = 'account.move'

    def generate_warranty_pdfs(self):
        """
        Generate warranty PDFs directly using reportlab with required fields.
        
        Business Rules:
        - Create PDF documents directly using reportlab (no external dependencies)
        - Fill customer name, product brand, warranty period
        - Generate one PDF per product with warranty
        - Exclude product with ID 7884
        - Default to "1" month if warranty field is empty
        
        Returns:
            dict: Action dictionary for file download
        """
        try:
            # Get products from invoice lines
            products = []
            for line in self.invoice_line_ids:
                if line.product_id and line.product_id.id != 7884:
                    products.append(line.product_id)
            
            if not products:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'No Products',
                        'message': 'No valid products found for warranty generation.',
                        'type': 'warning',
                    }
                }
            
            # Generate filled warranty PDFs
            pdf_content = self._generate_filled_warranty_pdf(products)
            
            if not pdf_content:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Error',
                        'message': 'Failed to generate warranty PDF. Please check template file and dependencies.',
                        'type': 'danger',
                    }
                }
            
            # Create attachment for download
            filename = f"garancia_{self.name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            attachment = self.env['ir.attachment'].create({
                'name': filename,
                'type': 'binary',
                'datas': base64.b64encode(pdf_content),
                'res_model': 'account.move',
                'res_id': self.id,
                'mimetype': 'application/pdf'
            })
            
            return {
                'type': 'ir.actions.act_url',
                'url': f'/web/content/{attachment.id}?download=true',
                'target': 'self',
            }
            
        except Exception as e:
            _logger.error(f'Error generating warranty PDF for invoice {self.id}: {str(e)}')
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Error',
                    'message': f'Error generating warranty PDF: {str(e)}',
                    'type': 'danger',
                }
            }

    def _generate_filled_warranty_pdf(self, products):
        """
        Generate warranty PDF directly using reportlab with product data.
        
        Args:
            products: List of product.product records
            
        Returns:
            bytes: PDF content as bytes
        """
        try:
            # Create a new PDF writer for the final output
            output_pdf = PdfWriter()
            
            # Process each product
            for product in products:
                filled_pdf = self._create_warranty_pdf(product)
                if filled_pdf:
                    # Add the filled page to output
                    reader = PdfReader(BytesIO(filled_pdf))
                    for page in reader.pages:
                        output_pdf.add_page(page)
            
            # Write final PDF to buffer
            output_buffer = BytesIO()
            output_pdf.write(output_buffer)
            pdf_content = output_buffer.getvalue()
            output_buffer.close()
            
            return pdf_content
            
        except Exception as e:
            _logger.error(f'Error generating filled warranty PDF: {str(e)}')
            return None

    def _create_warranty_pdf(self, product):
        """
        Create warranty PDF directly using reportlab with product-specific data.
        
        Args:
            product: Product record
            
        Returns:
            bytes: PDF content as bytes
        """
        try:
            # Create buffer for PDF content
            buffer = BytesIO()
            
            # Create PDF document
            doc = SimpleDocTemplate(buffer, pagesize=A4, 
                                  rightMargin=72, leftMargin=72, 
                                  topMargin=72, bottomMargin=18)
            
            # Get customer name from invoice partner
            customer_name = self.partner_id.name or "___________________"
            
            # Get product brand/name
            product_name = product.name or "________________"
            
            # Get warranty period (default to 1 if empty)
            warranty_period = str(getattr(product, 'x_studio_warranty', '1')).replace(' muaj', '').replace(' month', '').strip()
            if not warranty_period or warranty_period == '':
                warranty_period = '1'
            
            # Get invoice information
            invoice_number = self.name or ''
            invoice_date = self.invoice_date.strftime('%d/%m/%Y') if self.invoice_date else ''
            
            # Create warranty certificate content
            story = self._create_warranty_content(customer_name, product_name, warranty_period, invoice_number, invoice_date)
            
            # Build PDF
            doc.build(story)
            
            # Get PDF content
            pdf_content = buffer.getvalue()
            buffer.close()
            
            return pdf_content
            
        except Exception as e:
            _logger.error(f'Error creating warranty PDF for product {product.id}: {str(e)}')
            return None

    def _create_warranty_content(self, customer_name, product_name, warranty_period, invoice_number, invoice_date):
        """
        Create warranty certificate content for PDF.
        
        Args:
            customer_name (str): Customer name
            product_name (str): Product name
            warranty_period (str): Warranty period in months
            invoice_number (str): Invoice number
            invoice_date (str): Invoice date
            
        Returns:
            list: Story elements for PDF
        """
        # Get styles
        styles = getSampleStyleSheet()
        
        # Create custom styles
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            spaceAfter=30,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold'
        )
        
        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=16,
            spaceAfter=12,
            fontName='Helvetica-Bold'
        )
        
        normal_style = ParagraphStyle(
            'CustomNormal',
            parent=styles['Normal'],
            fontSize=12,
            spaceAfter=6,
            fontName='Helvetica'
        )
        
        bold_style = ParagraphStyle(
            'CustomBold',
            parent=styles['Normal'],
            fontSize=12,
            spaceAfter=6,
            fontName='Helvetica-Bold'
        )
        
        right_style = ParagraphStyle(
            'CustomRight',
            parent=styles['Normal'],
            fontSize=12,
            spaceAfter=6,
            fontName='Helvetica',
            alignment=TA_RIGHT
        )
        
        # Build story
        story = []
        
        # Title
        story.append(Paragraph("GARANCIA", title_style))
        story.append(Spacer(1, 20))
        
        # Customer information
        story.append(Paragraph(f"<b>Emer Mbiemer:</b> {customer_name}", normal_style))
        story.append(Spacer(1, 10))
        
        # Product information
        story.append(Paragraph(f"<b>Marka:</b> {product_name}", normal_style))
        story.append(Spacer(1, 10))
        
        # Warranty period
        story.append(Paragraph(f"<b>Afati Garancise:</b> {warranty_period} Muaj", normal_style))
        story.append(Spacer(1, 10))
        
        # Invoice information
        story.append(Paragraph(f"<b>Numri i Fatures:</b> {invoice_number}", normal_style))
        story.append(Paragraph(f"<b>Data e Fatures:</b> {invoice_date}", normal_style))
        story.append(Spacer(1, 20))
        
        # Warranty terms
        story.append(Paragraph("Kushtet e Garancise", heading_style))
        
        terms_text = """
        Kjo garancia mbulon defekte ne material dhe punim te produktit.<br/>
        Garancia nuk mbulon:<br/>
        • Demet e shkaktuara nga perdorimi gabim<br/>
        • Demet e shkaktuara nga aksidentet<br/>
        • Demet e shkaktuara nga modifikimet e produktit<br/>
        • Konsumimin normal te produktit<br/><br/>
        
        Per te aktivizuar garancine, kontaktoni:<br/>
        Telefon: [NUMRI I TELEFONIT]<br/>
        Email: [EMAIL ADRESA]<br/>
        Adresa: [ADRESA E PLOTE]
        """
        
        story.append(Paragraph(terms_text, normal_style))
        story.append(Spacer(1, 30))
        
        # Signature section
        story.append(Paragraph("Nenshkrimi: _________________________", right_style))
        story.append(Paragraph("Data: _________________________", right_style))
        
        return story


class WarrantyPdfSettings(models.TransientModel):
    _name = 'warranty.pdf.settings'
    _description = 'Warranty PDF Generation Settings'

    exclude_product_ids = fields.Many2many(
        'product.product',
        string='Exclude Products',
        help='Products to exclude from warranty generation'
    )
    
    default_warranty_period = fields.Char(
        string='Default Warranty Period',
        default='1',
        help='Default warranty period in months when product warranty is not set'
    )
    
    template_file = fields.Binary(
        string='Template File',
        help='Upload custom warranty template Word document'
    )
    
    template_filename = fields.Char(
        string='Template Filename'
    )

    @api.model
    def get_settings(self):
        """Get warranty PDF generation settings."""
        config = self.env['ir.config_parameter'].sudo()
        return {
            'exclude_product_ids': config.get_param('warranty_pdf.exclude_product_ids', '7884').split(','),
            'default_warranty_period': config.get_param('warranty_pdf.default_warranty_period', '1'),
        }

    def save_settings(self):
        """Save warranty PDF generation settings."""
        config = self.env['ir.config_parameter'].sudo()
        
        exclude_ids = ','.join(str(pid) for pid in self.exclude_product_ids.ids) if self.exclude_product_ids else '7884'
        config.set_param('warranty_pdf.exclude_product_ids', exclude_ids)
        config.set_param('warranty_pdf.default_warranty_period', self.default_warranty_period or '1')
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Settings Saved',
                'message': 'Warranty PDF settings have been saved successfully.',
                'type': 'success',
            }
        }