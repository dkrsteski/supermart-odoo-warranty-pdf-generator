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
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image
    from reportlab.lib.units import inch
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    from reportlab.lib.colors import black, blue
    from PyPDF2 import PdfWriter, PdfReader
    import subprocess
    import tempfile
except ImportError as e:
    logging.getLogger(__name__).warning(f"Required libraries not installed: {e}. PDF generation will not work.")

_logger = logging.getLogger(__name__)


class AccountMoveWarranty(models.Model):
    _inherit = 'account.move'

    def generate_warranty_pdfs(self):
        """
        Generate warranty PDFs using the garancia.docx template with exact formatting.
        
        Business Rules:
        - Use garancia.docx template from module directory
        - Convert to PDF using LibreOffice to preserve exact formatting
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
        Generate warranty PDF using the garancia.docx template with exact formatting.
        
        Args:
            products: List of product.product records
            
        Returns:
            bytes: PDF content as bytes
        """
        try:
            # Get the template path from the warranty_pdf_generator module
            module_path = os.path.dirname(os.path.dirname(__file__))
            template_path = os.path.join(module_path, 'garancia.docx')
            
            if not os.path.exists(template_path):
                _logger.error(f'Template file not found at: {template_path}')
                return None
            
            # Create a new PDF writer for the final output
            output_pdf = PdfWriter()
            
            # Process each product
            for product in products:
                filled_pdf = self._fill_warranty_template(template_path, product)
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

    def _fill_warranty_template(self, template_path, product):
        """
        Create warranty PDF with product-specific data.
        Falls back to direct PDF creation if LibreOffice is not available.
        
        Args:
            template_path (str): Path to garancia.docx template (for reference)
            product: Product record
            
        Returns:
            bytes: Filled PDF content
        """
        try:
            # Try to use LibreOffice conversion first
            pdf_template_path = self._convert_docx_to_pdf_template(template_path)
            if pdf_template_path:
                # LibreOffice is available, use the converted template
                with open(pdf_template_path, 'rb') as pdf_file:
                    pdf_content = pdf_file.read()
                os.unlink(pdf_template_path)
                return pdf_content
            else:
                # LibreOffice not available, create PDF directly
                _logger.info('LibreOffice not available, creating PDF directly')
                return self._create_warranty_pdf_direct(product)
            
        except Exception as e:
            _logger.error(f'Error creating warranty PDF for product {product.id}: {str(e)}')
            # Fallback to direct PDF creation
            return self._create_warranty_pdf_direct(product)

    def _create_warranty_pdf_direct(self, product):
        """
        Create warranty PDF directly using reportlab with professional formatting.
        
        Args:
            product: Product record
            
        Returns:
            bytes: PDF content as bytes
        """
        try:
            # Create buffer for PDF content
            buffer = BytesIO()
            
            # Create PDF document with proper margins
            doc = SimpleDocTemplate(buffer, pagesize=A4, 
                                  rightMargin=72, leftMargin=72, 
                                  topMargin=72, bottomMargin=72)
            
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
            story = self._create_warranty_content_professional(customer_name, product_name, warranty_period, invoice_number, invoice_date)
            
            # Build PDF
            doc.build(story)
            
            # Get PDF content
            pdf_content = buffer.getvalue()
            buffer.close()
            
            return pdf_content
            
        except Exception as e:
            _logger.error(f'Error creating direct warranty PDF for product {product.id}: {str(e)}')
            return None

    def _create_warranty_content_professional(self, customer_name, product_name, warranty_period, invoice_number, invoice_date):
        """
        Create professional warranty certificate content for PDF.
        
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
            'WarrantyTitle',
            parent=styles['Heading1'],
            fontSize=28,
            spaceAfter=40,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold',
            textColor=black
        )
        
        subtitle_style = ParagraphStyle(
            'WarrantySubtitle',
            parent=styles['Heading2'],
            fontSize=16,
            spaceAfter=20,
            alignment=TA_CENTER,
            fontName='Helvetica',
            textColor=black
        )
        
        field_style = ParagraphStyle(
            'WarrantyField',
            parent=styles['Normal'],
            fontSize=14,
            spaceAfter=15,
            fontName='Helvetica-Bold',
            textColor=black
        )
        
        value_style = ParagraphStyle(
            'WarrantyValue',
            parent=styles['Normal'],
            fontSize=14,
            spaceAfter=15,
            fontName='Helvetica',
            textColor=black
        )
        
        terms_style = ParagraphStyle(
            'WarrantyTerms',
            parent=styles['Normal'],
            fontSize=12,
            spaceAfter=8,
            fontName='Helvetica',
            textColor=black
        )
        
        signature_style = ParagraphStyle(
            'WarrantySignature',
            parent=styles['Normal'],
            fontSize=12,
            spaceAfter=10,
            fontName='Helvetica',
            textColor=black,
            alignment=TA_RIGHT
        )
        
        # Build story
        story = []
        
        # Title
        story.append(Paragraph("GARANCIA", title_style))
        story.append(Paragraph("Certifikata e Garancise", subtitle_style))
        story.append(Spacer(1, 30))
        
        # Customer information
        story.append(Paragraph("Emer Mbiemer:", field_style))
        story.append(Paragraph(customer_name, value_style))
        story.append(Spacer(1, 10))
        
        # Product information
        story.append(Paragraph("Marka/Produkti:", field_style))
        story.append(Paragraph(product_name, value_style))
        story.append(Spacer(1, 10))
        
        # Warranty period
        story.append(Paragraph("Afati i Garancise:", field_style))
        story.append(Paragraph(f"{warranty_period} Muaj", value_style))
        story.append(Spacer(1, 10))
        
        # Invoice information
        story.append(Paragraph("Numri i Fatures:", field_style))
        story.append(Paragraph(invoice_number, value_style))
        story.append(Spacer(1, 10))
        
        story.append(Paragraph("Data e Fatures:", field_style))
        story.append(Paragraph(invoice_date, value_style))
        story.append(Spacer(1, 30))
        
        # Warranty terms
        story.append(Paragraph("Kushtet e Garancise", field_style))
        story.append(Spacer(1, 10))
        
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
        
        story.append(Paragraph(terms_text, terms_style))
        story.append(Spacer(1, 40))
        
        # Signature section
        story.append(Paragraph("Nenshkrimi: _________________________", signature_style))
        story.append(Paragraph("Data: _________________________", signature_style))
        
        return story

    def _convert_docx_to_pdf_template(self, docx_path):
        """
        Convert Word document template to PDF using LibreOffice.
        
        Args:
            docx_path (str): Path to the Word document template
            
        Returns:
            str: Path to the converted PDF template, or None if failed
        """
        try:
            # Create temporary directory for output
            temp_dir = tempfile.mkdtemp()
            
            # Use LibreOffice to convert DOCX to PDF
            cmd = [
                'libreoffice',
                '--headless',
                '--convert-to', 'pdf',
                '--outdir', temp_dir,
                docx_path
            ]
            
            _logger.info(f'Converting DOCX to PDF: {docx_path}')
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            
            if result.returncode != 0:
                _logger.error(f'LibreOffice conversion failed: {result.stderr}')
                return None
            
            # Find the generated PDF file
            base_name = os.path.splitext(os.path.basename(docx_path))[0]
            pdf_path = os.path.join(temp_dir, f'{base_name}.pdf')
            
            if os.path.exists(pdf_path):
                _logger.info(f'PDF template generated successfully: {pdf_path}')
                return pdf_path
            else:
                _logger.error(f'PDF template not found at expected location: {pdf_path}')
                # List files in temp directory for debugging
                try:
                    files = os.listdir(temp_dir)
                    _logger.error(f'Files in temp directory: {files}')
                except:
                    pass
                return None
                
        except subprocess.TimeoutExpired:
            _logger.error('LibreOffice conversion timed out')
            return None
        except Exception as e:
            _logger.error(f'Error converting DOCX template to PDF: {str(e)}')
            return None


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