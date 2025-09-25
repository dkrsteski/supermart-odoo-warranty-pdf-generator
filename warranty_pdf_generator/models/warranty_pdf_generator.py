from odoo import models, fields, api
import logging
from datetime import datetime
from io import BytesIO
import base64
import os

try:
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4
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
        Fill warranty template with product-specific data using exact formatting from DOCX.
        
        Args:
            template_path (str): Path to garancia.docx template
            product: Product record
            
        Returns:
            bytes: Filled PDF content
        """
        try:
            # First, convert the DOCX template to PDF using LibreOffice
            pdf_template_path = self._convert_docx_to_pdf_template(template_path)
            if not pdf_template_path:
                return None
            
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
            
            # Create overlay with form data
            overlay_buffer = BytesIO()
            c = canvas.Canvas(overlay_buffer, pagesize=A4)
            
            # Fill form fields - these positions may need adjustment based on your template
            # You'll need to inspect the converted PDF to get exact coordinates
            c.setFont("Helvetica", 9)
            
            # Customer name field (Emer Mbiemer) - adjust coordinates as needed
            c.drawString(155, 162, customer_name[:30])  # Limit length to fit field
            
            # Product brand field (Marka) - adjust coordinates as needed
            c.drawString(110, 194, product_name[:25])  # Limit length to fit field
            
            # Warranty period field (Afati Garancise) - adjust coordinates as needed
            c.drawString(155, 225, warranty_period)  # Warranty period before "Muaj"
            
            # Invoice number - adjust coordinates as needed
            c.drawString(155, 256, invoice_number[:20])
            
            # Invoice date - adjust coordinates as needed
            c.drawString(155, 287, invoice_date)
            
            c.save()
            overlay_buffer.seek(0)
            
            # Read template and overlay
            template_reader = PdfReader(pdf_template_path)
            overlay_reader = PdfReader(overlay_buffer)
            
            # Create output buffer
            output_buffer = BytesIO()
            output_writer = PdfWriter()
            
            # Merge overlay with template pages
            for page_num in range(len(template_reader.pages)):
                page = template_reader.pages[page_num]
                
                # Apply overlay to the page where form fields are
                # You may need to adjust this based on which page has the form fields
                if page_num == 0 and len(overlay_reader.pages) > 0:
                    overlay_page = overlay_reader.pages[0]
                    page.merge_page(overlay_page)
                
                output_writer.add_page(page)
            
            # Write to buffer
            output_writer.write(output_buffer)
            output_content = output_buffer.getvalue()
            
            # Cleanup
            overlay_buffer.close()
            output_buffer.close()
            os.unlink(pdf_template_path)  # Clean up temporary PDF template
            
            return output_content
            
        except Exception as e:
            _logger.error(f'Error filling warranty template for product {product.id}: {str(e)}')
            return None

    def _convert_docx_to_pdf_template(self, docx_path):
        """
        Convert Word document template to PDF using LibreOffice.
        
        Args:
            docx_path (str): Path to the Word document template
            
        Returns:
            str: Path to the converted PDF template, or None if failed
        """
        try:
            # Create temporary PDF file
            with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temp_pdf:
                temp_pdf_path = temp_pdf.name
            
            # Use LibreOffice to convert DOCX to PDF
            cmd = [
                'libreoffice',
                '--headless',
                '--convert-to', 'pdf',
                '--outdir', os.path.dirname(temp_pdf_path),
                docx_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode != 0:
                _logger.error(f'LibreOffice conversion failed: {result.stderr}')
                return None
            
            # Return the path to the generated PDF
            pdf_path = os.path.splitext(temp_pdf_path)[0] + '.pdf'
            if os.path.exists(pdf_path):
                return pdf_path
            else:
                _logger.error(f'PDF template not generated: {pdf_path}')
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