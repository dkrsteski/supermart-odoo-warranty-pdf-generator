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
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.pdfbase import pdfmetrics
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle, ListFlowable, ListItem
    from reportlab.lib.units import inch
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    from reportlab.lib.colors import black, blue, orange

    # Support both PyPDF2 v1.x and v2.x+
    try:
        from PyPDF2 import PdfWriter, PdfReader
    except ImportError:
        # Fallback for PyPDF2 v1.x
        from PyPDF2 import PdfFileWriter as PdfWriter, PdfFileReader as PdfReader

    import subprocess
    import tempfile

    pdfmetrics.registerFont(TTFont('DejaVuSans', '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'))

except ImportError as e:
    logging.getLogger(__name__).warning(f"Required libraries not installed: {e}. PDF generation will not work.")

_logger = logging.getLogger(__name__)


class AccountMoveWarranty(models.Model):
    _inherit = 'account.move'

    def generate_warranty_pdfs(self):
     
        try:
            # Get products from invoice lines
            products = []
            for line in self.invoice_line_ids:
                if not line.product_id:
                    continue
                # Exclude specific product IDs and names
                product = line.product_id
                if product.id in (7884, 6):
                    continue
                if "Gift Card" in (product.display_name or ""):
                    continue
                products.append(product)
            
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
            
            # Pre-check for products without warranty (explicit False)
            missing_warranty_products = []
            for product in products:
                if getattr(product, 'x_studio_warranty', None) is False:
                    missing_warranty_products.append(product)

            if missing_warranty_products and not self.env.context.get('confirm_missing_warranty'):
                # Open confirmation wizard listing products with missing warranties
                return {
                    'type': 'ir.actions.act_window',
                    'name': 'Missing Warranties',
                    'res_model': 'warranty.missing.warranty.wizard',
                    'view_mode': 'form',
                    'target': 'new',
                    'context': {
                        'default_move_id': self.id,
                        'default_product_ids': [(6, 0, [p.id for p in missing_warranty_products])],
                    }
                }

            # Generate filled warranty PDFs
            pdf_content = self._create_warranty_pdf_direct(products)
            
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
            
            # Create PDF document with narrow margins
            doc = SimpleDocTemplate(buffer, pagesize=A4, 
                                  rightMargin=18, leftMargin=18, 
                                  topMargin=18, bottomMargin=18)
            
            # Get customer name from invoice partner
            customer_name = self.partner_id.name or "___________________"
            
            # Get product brand/name
            product_name = product.name or "________________"
            
            # Get warranty period (default to 1 if empty or False)
            warranty_value = getattr(product, 'x_studio_warranty', '1')
            if warranty_value is False:
                warranty_period = '1'
            else:
                warranty_period = str(warranty_value).replace(' muaj', '').replace(' month', '').strip()
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
            fontSize=20,
            spaceAfter=10,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold',
            textColor=black
        )
        
        subtitle_style = ParagraphStyle(
            'WarrantySubtitle',
            parent=styles['Heading2'],
            fontSize=12,
            spaceAfter=10,
            alignment=TA_CENTER,
            fontName='Helvetica',
            textColor=black
        )
        
        field_style = ParagraphStyle(
            'WarrantyField',
            parent=styles['Normal'],
            fontSize=10,
            spaceAfter=6,
            fontName='Helvetica-Bold',
            textColor=black
        )
        
        value_style = ParagraphStyle(
            'WarrantyValue',
            parent=styles['Normal'],
            fontSize=10,
            spaceAfter=6,
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
        
        # Contact info styles
        contact_label_style = ParagraphStyle(
            'ContactLabel',
            parent=styles['Normal'],
            fontSize=8,
            fontName='Helvetica-Bold',
            textColor=orange,
            spaceAfter=2
        )
        
        contact_value_style = ParagraphStyle(
            'ContactValue',
            parent=styles['Normal'],
            fontSize=8,
            fontName='Helvetica',
            textColor=black,
            spaceAfter=2
        )
        
        # Build story
        story = []
        
        # Header section with logo and contact info
        story.extend(self._create_header_section())
        story.append(Spacer(1, 10))
        
        # Customer and product information section with FLETË GARANCIE box
        story.extend(self._create_customer_product_section(customer_name, product_name, warranty_period))
        story.append(Spacer(1, 10))
        
        # Add italic disclaimer text
        disclaimer_style = ParagraphStyle(
            'Disclaimer',
            parent=styles['Normal'],
            fontSize=6,
            fontName='Helvetica-Oblique',
            textColor=black,
            spaceAfter=3,
            alignment=TA_LEFT
        )
        
        disclaimer_text = """
        Para se të blini produktin, kontrollojeni nëse është në gjendje të rregullt dhe nëse përmban të gjitha pjesët përkatëse që ofrohen me paketimin. Detyrimisht kjo fletë garancie duhet të nënshkruhet nga të dyja palët dhe të vuloset nga shitësi.<br/>
        Para se të blini produktin, kërkoni informacione të sakta lidhur me cilësinë, karakteristikat, mënyrën e përdorimit, montimin dhe kushtet e pagesës, si dhe lexoni me vëmendje kushtet e garancisë më poshtë:
        """
        
        story.append(Paragraph(disclaimer_text, disclaimer_style))        
        # Add bold section title
        section_title_style = ParagraphStyle(
            'SectionTitle',
            parent=styles['Normal'],
            fontSize=9,
            fontName='Helvetica-Bold',
            textColor=black,
            spaceAfter=2,
            spaceBefore=2,
            alignment=TA_LEFT
        )
        
        story.append(Paragraph("Kushtet e përgjithshme të garancisë:", section_title_style))
        
        # Add warranty terms with bullet points
        terms_style = ParagraphStyle(
            'WarrantyTerms',
            parent=styles['Normal'],
            fontSize=7,
            fontName='Helvetica',
            textColor=black,
            spaceAfter=1,
            spaceBefore=1,
            leading=7,
            alignment=TA_LEFT,
            leftIndent=4,
            bulletIndent=1
        )
        
        warranty_terms = [
            "Periudha e garancisë është e vlefshme vetëm brenda kohës së lartpërmendur në këtë fletë garancie, duke filluar nga data e blerjes.",
            "Garancia vlen vetëm për riparimin e produktit, në rast se produkti nuk mund të riparohet brenda afatit të përcaktuar prej dyzet e pesë ditësh atëherë, \"Supermart\" i ofron blerësit zëvendësim të produktit por në asnjë mënyrë kthimin e tij apo të pagesës.",
            "Periudha e reklamimit është e vlefshme për 24 orë, nëse brenda kësaj periudhe është vërejtur se produkti nuk funksionon si duhet atëherë, \"Supermart\" do të zëvendësojë produktin vetëm pasi të verifikohet nga tekniku përkatës që teknikisht është në gjendje të mirë dhe nuk është dëmtuar nga ana e blerësit.",
            "Blerësi është i detyruar që në momentin e dorëzimit të produktit për servis të prezantojë: faturën e blerjes ose kuponin fiskal dhe fletën e garancisë të plotësuar me të gjitha informacionet e nevojshme dhe të sakta, të nënshkruar nga të dyja palët dhe të vulosur nga shitësi. Në mungesë të ndonjë dokumenti apo informacioni të lartpërmendur garancia është e pavlefshme.",
            "Shërbimet duhet të kryhen vetëm nga \"Supermart\" ose në serviset e autorizuara prej \"Supermart\".",
            "Blerësi është i detyruar të përdorë produktin duke zbatuar udhëzimet dhe manualin e përdorimit. Garancia nuk do të jetë e vlefshme nëse dëmtimi i produktit është shkaktuar si rezultat i moszbatimit të kushteve të përshkruara në manualin e përdorimit.",
            "Në rastin kur blerësi dorëzon produktin për servis, është i detyruar të sjellë së bashku edhe pjesët përkatëse: karikuesin, pajisjet përcjellëse të energjisë, telekomandën, të heqë kodin e mbylljes (pasuordin , pinin, etj.), si dhe të ruajë të dhënat apo programet e tij personale. \"Supermart\" nuk merr asnjë përgjegjësi për humbjen apo dëmtimin e programeve aplikative, humbjen apo dëmtimin e shënimeve ose informacioneve të tjera.",
            "Në rast defekti, \"Supermart\" është i detyruar të riparojë produktin brenda afatit maksimal prej 45 ditëve. Nëse produkti nuk mund të riparohet apo defekti nuk mund të eliminohet brenda afatit të garancisë atëherë, do të zëvendësohet me një të ri (nëse çmimi i produktit të ri ndryshon ose produkti në defekt është amortizuar, dëmtuar ose i mungon ndonjë pjesë, blerësi detyrohet të paguajë ndryshimin apo zhvlerësimin). Periudha e mbetur e garancisë të produktit paraprak do të jetë e vlefshme edhe për produktin e ri duke i shtuar ditët sa ka qëndruar në servis.",
            "Pajisjet përcjellëse (të cilat cilësohen materiale të konsumueshme) si: telekomanda, bateria, karikuesi, kufjet, telekomanda, kabllot e ndryshme, filtrat etj., kanë vetëm 24 orë reklamim me kusht që nuk janë të dëmtuara fizikisht.",
            "Garancia nuk përfshin sistemet operative apo aplikacionet e ndryshme softuerike. Ky shërbim mund të kryhet vetëm kundrejt pagesës për klientët që kanë ende garancinë për produktin në fjalë. \"Supermart\" nuk garanton për mosfunksionimin e aplikacioneve të palëve të treta.",
            "Produkti duhet të dorëzohet për servis në \"Supermart\" së bashku me këto dy fletë garancie. Në rastet kur produkti vjen me garancinë origjinale të prodhuesit atëherë, përveç kushteve të përmendura në formën zyrtare nga \"Supermart\" duhet të zbatohen dhe kushtet shtesë të përmendura në këtë fletë garancie. Në mungesë të ndonjë dokumenti apo informacioni të lartpërmendur garancia është e pavlefshme.",
            "Servisi në shtëpi mund të ofrohet vetëm kundrejt pagesës, në të kundërt klienti detyrohet të dorëzojë produktin për servis në njërën nga pikat e \"Supermart\"."
        ]

        
        
        # Create list items for warranty terms
        list_items = [ListItem(Paragraph(term, terms_style)) for term in warranty_terms]
        warranty_list = ListFlowable(list_items, bulletType='bullet', start='-')
        story.append(warranty_list)

        story.append(Paragraph("Garancia nuk është e vlefshme :", section_title_style))
                
        # Add warranty exclusions and additional terms
        exclusions_terms = [
            "Në rastet kur dëmtimet janë shkaktuar nga goditjet, presioni fizik, keqpërdorimi ose pakujdesia dhe transporti i papërshtatshëm.",
            "Në rastet e dëmtimeve të shkaktuara nga tensioni i lartë apo i ulët i rrymës elektrike, dëmtimet termike apo mekanike, rrufeja etj.",
            "Në rastet kur produkti është ekspozuar ndaj lagështisë, nxehtësisë, korrozionit, pluhurit, tymit, dridhjeve, papastërtive, insekteve apo kushteve të tjera të jashtëzakonshme apo të papërshtatshme.",
            "Në rastet kur numri i pikselave të vdekur në ekran nuk është me i lartë se shtatë në TV, katër në laptop, tre në tablet dhe në telefon.",
            "Në rastet e keqpërdorimit të produktit nga ana e përdoruesit.",
            "Në rastet kur produkti përdoret për qëllime tregtare (pa autorizimin e shitësit) si: restorante, hotele, kafene, pastrim kimik, sallone, shkolla etj.",
            "Në rastet kur keqpërdoren kapacitetet teknike apo produkti montohet në mënyrë jo profesionale apo të gabuar.",
            "Në rastet e përdorimit të pajisjeve lidhëse të cilat nuk janë pajisje përcjellëse të dizenjuara për këtë produkt.",
            "Në rastet kur pjesët e xhamit, plastikës apo gomës dëmtohen si pasojë e keqpërdorimit, presionit, goditjeve të ndryshme të brendshme apo të jashtme.",
            "Në rastet e ndryshimit apo modifikimit të programit \"sistemit operativ\" apo aplikacioneve softuerike.",
            "Në rastet kur produktit i janë kryer shërbime apo instalime nga persona të paautorizuar nga \"Supermart\".",
            "Në rastet kur ka mospërputhshmëri në mes të të dhënave në këtë fletë garancie dhe të produktit apo është tentuar ndryshimi tyre.",
            "Garancia nuk mbulon ndërrimin, mbushjen, apo zëvendësimin e materialeve të konsumueshme, shërbimet e tilla mund të kryhen vetëm me pagesë.",
            "Nëse kondicionerët montohen nga montues të \"Supermart\" garancia është e plotë, në të kundërt garancia ofrohet me kushte të tjera (kryesisht me periudhë të përgjysmuar). Gjithashtu nëse kondicionerët montohen nga montues të tjerë dhe montimi nuk është kryer në rregull atëherë kompania \"Supermart\" nuk merr përgjegjësi të ofrojë periudhë garantuese.",
            "Montimi i kondicionerëve ofrohet brenda periudhës nga 1 deri në 5 ditë (përveç ditës së diel dhe festave zyrtare) dhe brenda intervalit kohor 08:30 - 20:00.",
            "Ndërhyrja në kondicionerë ofrohet brenda periudhës nga 1 deri në 3 ditë (përveç ditës së diel dhe festave zyrtare) dhe brenda intervalit kohor 08:30 - 21:00.",
            "Në rastet kur klienti kërkon shërbime nga servisi dhe konstatohet se produkti është në gjendje të rregullt apo problemi është krijuar si pasojë e përdorimit jo të përshtatshëm atëherë klienti detyrohet të paguajë të gjitha shpenzimet që i janë shkaktuar kompanisë \"Supermart\". Garancia mbulon produktin vetëm nëse defekti ka ardhur si pasojë e ndonjë gabimi të prodhuesit.",
            "Nëse klienti ka shkelur ndonjërën nga pikat e lartpërmendura dhe riparimi i produktit në fjalë mund të realizohet, atëherë klienti është i detyruar të paguajë për pjesën e ndërruar, shërbimin, kohën dhe transportin e realizuar nga kompania \"Supermart\"",
            "Në rastet kur janë shkelur rregullat e lartpërmendura dhe shërbimi i ofruar ose servisi e autorizuar nga \"Supermart\" duhet të faturohet, por klienti refuzon të paguaj detyrimin ndaj kompanisë atëherë garancia për produktin në fjalë do të bëhet e pavlefshme dhe kjo çështje do ti kalojë departamentit juridik për hapa të mëtejshëm sipas legjislacionit në fuqi të RSH."
        ]
        
        # Create list items for exclusions terms
        exclusions_list_items = [ListItem(Paragraph(term, terms_style)) for term in exclusions_terms]
        exclusions_list = ListFlowable(exclusions_list_items, bulletType='bullet', start='-')
        story.append(exclusions_list)
        
        
        # Signature section (three columns)
        story.extend(self._create_signature_section())
        
        # Attention section at the bottom
        story.extend(self._create_attention_section())
        
        return story

    def _create_signature_section(self):
        """
        Create three-column signature section for Buyer, Installer, Seller.
        
        Returns:
            list: Story elements for the signature section
        """
        story = []
        
        # Styles
        label_style = ParagraphStyle(
            'SignLabel',
            parent=getSampleStyleSheet()['Normal'],
            fontSize=9,
            fontName='Helvetica-Bold',
            alignment=TA_CENTER,
            spaceAfter=2
        )
        sub_label_style = ParagraphStyle(
            'SignSubLabel',
            parent=getSampleStyleSheet()['Normal'],
            fontSize=8,
            fontName='Helvetica',
            alignment=TA_CENTER,
            spaceAfter=2
        )
        
        # Underline as a long line
        underline_para = Paragraph("_" * 30, ParagraphStyle('UnderlineLine', fontSize=6, alignment=TA_CENTER, spaceAfter=4))
        
        # Build columns
        col1 = [underline_para, Paragraph("Bleresi", label_style), Paragraph("(emer,mbiemer dhe nenshkirmi)", sub_label_style)]
        col2 = [underline_para, Paragraph("Montuesi", label_style), Paragraph("(emer,mbiemer dhe nenshkrimi)", sub_label_style)]
        col3 = [underline_para, Paragraph("Shitesi", label_style), Paragraph("(emer,mbiemer,nenshkrimi dhe vula)", sub_label_style)]
        
        table = Table([[col1, col2, col3]], colWidths=[2.2*inch, 2.2*inch, 2.2*inch])
        table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ]))
        
        story.append(Spacer(1, 8))
        story.append(table)
        
        return story

    def _create_attention_section(self):
        """
        Create the bottom attention section with a black box and explanatory text.
        """
        story = []
        
        # Left: black box with white bold text "Vëmendje"
        attention_box = Table([["Vëmendje"]], colWidths=[2.5*inch], rowHeights=[0.7*inch])
        attention_box.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), black),
            ('TEXTCOLOR', (0, 0), (-1, -1), 'white'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 18),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 12),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ]))
        
        # Right: paragraph text
        right_style = ParagraphStyle(
            'AttentionText',
            parent=getSampleStyleSheet()['Normal'],
            fontSize=8,
            fontName='Helvetica',
            alignment=TA_LEFT,
            spaceAfter=0
        )
        right_para = Paragraph(
            "Blerësi konfirmon se bleu produktin në kushte të mira dhe me të gjitha pjesët përkatëse. Blerësi konfirmon se i ka lexuar kushtet e lartpërmendura në këtë fletë garancie dhe do ti përmbahet rregullave për çdo pikë të lartpërmendur, në të kundërtën pajtohet se garancia do të jetë e pavlefshme!.",
            right_style
        )
        
        table = Table([[attention_box, right_para]], colWidths=[3.0*inch, 3.8*inch])
        table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ]))
        
        story.append(table)
        return story

    def _create_header_section(self):
        """
        Create header section with logo on the left and contact information on the right.
        
        Returns:
            list: Story elements for the header section
        """
        story = []
        
        try:
            # Get the logo path
            module_path = os.path.dirname(os.path.dirname(__file__))
            logo_path = os.path.join(module_path, 'static', 'data', 'logo.jpeg')
            
            # Check if logo exists
            if os.path.exists(logo_path):
                # Create logo image
                logo = Image(logo_path, width=2*inch, height=0.5*inch)
            else:
                # Create a placeholder if logo doesn't exist
                logo = Paragraph("LOGO", ParagraphStyle(
                    'LogoPlaceholder',
                    fontSize=24,
                    fontName='Helvetica-Bold',
                    textColor=black,
                    alignment=TA_CENTER
                ))
            
            # Create contact information table
            contact_data = [
                ['Adresa', 'Rr Mihal Grameno, 10m mbi BKT Tirane Albania'],
                ['Shërbimi i klientit', '0697015351'],
                ['E-mail', 'info@supermart.al'],
                ['Web', 'www.supermart.al']
            ]
            
            # Create table with contact information
            contact_table = Table(contact_data, colWidths=[1.5*inch, 3*inch])
            contact_table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 8),
                ('TEXTCOLOR', (0, 0), (0, -1), orange),
                ('TEXTCOLOR', (1, 0), (1, -1), black),
                ('LEFTPADDING', (0, 0), (-1, -1), 0),
                ('RIGHTPADDING', (0, 0), (-1, -1), 6),
                ('TOPPADDING', (0, 0), (-1, -1), 1),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
            ]))
            
            # Create header table with logo and contact info
            header_data = [[logo, contact_table]]
            header_table = Table(header_data, colWidths=[2.5*inch, 4.5*inch])
            header_table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('LEFTPADDING', (0, 0), (-1, -1), 0),
                ('RIGHTPADDING', (0, 0), (-1, -1), 0),
                ('TOPPADDING', (0, 0), (-1, -1), 0),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
            ]))
            
            story.append(header_table)
            
        except Exception as e:
            _logger.error(f'Error creating header section: {str(e)}')
            # Fallback: create simple header without logo
            story.append(Paragraph("SUPERMART", ParagraphStyle(
                'HeaderFallback',
                fontSize=20,
                fontName='Helvetica-Bold',
                textColor=black,
                alignment=TA_CENTER
            )))
        
        return story

    def _create_customer_product_section(self, customer_name, product_name, warranty_period):
        """
        Create customer and product information section with FLETË GARANCIE box.
        
        Args:
            customer_name (str): Customer name
            product_name (str): Product name
            warranty_period (str): Warranty period in months
            
        Returns:
            list: Story elements for the customer/product section
        """
        story = []
        
        try:
            # Create styles for the form fields with UTF-8 compatible font
            form_label_style = ParagraphStyle(
                'FormLabel',
                parent=getSampleStyleSheet()['Normal'],
                fontSize=8,
                fontName='DejaVuSans',
                textColor=black,
                spaceAfter=1
            )
            
            # Create the left side content with form fields in a single row
            left_content = []
            
            # Create a table with three rows for Emer Mbiemer, Marka, and Afati
            # Ensure proper UTF-8 encoding for customer and product names
            safe_customer_name = customer_name.encode('utf-8').decode('utf-8') if customer_name else "___________________"
            safe_product_name = product_name.encode('utf-8').decode('utf-8') if product_name else "________________"
            safe_warranty_period = warranty_period.encode('utf-8').decode('utf-8') if warranty_period else "1"
            
            form_data = [
                [
                    Paragraph("Emer Mbiemer:", form_label_style),
                    Paragraph(safe_customer_name, ParagraphStyle(
                        'Value',
                        fontSize=8,
                        fontName='DejaVuSans',
                        textColor=black,
                        spaceAfter=2
                    ))
                ],
                [
                    Paragraph("Marka:", form_label_style),
                    Paragraph(safe_product_name, ParagraphStyle(
                        'Value',
                        fontSize=8,
                        fontName='DejaVuSans',
                        textColor=black,
                        spaceAfter=2
                    ))
                ],
                [
                    Paragraph("Afati Garancise:", form_label_style),
                    Paragraph(f"{safe_warranty_period} Muaj", ParagraphStyle(
                        'Value',
                        fontSize=8,
                        fontName='DejaVuSans',
                        textColor=black,
                        spaceAfter=2
                    ))
                ]
            ]
            
            form_table = Table(form_data, colWidths=[1.0*inch, 1.5*inch])
            form_table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('LEFTPADDING', (0, 0), (-1, -1), 0),
                ('RIGHTPADDING', (0, 0), (-1, -1), 3),
                ('TOPPADDING', (0, 0), (-1, -1), 0),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
            ]))
            
            left_content.append(form_table)
            
            # Create the right side content - FLETË GARANCIE box
            flete_garancie_style = ParagraphStyle(
                'FleteGarancie',
                fontSize=12,
                fontName='Helvetica-Bold',
                textColor=black,
                alignment=TA_CENTER,
                spaceAfter=0
            )
            
            # Create a table cell with black background for FLETË GARANCIE
            flete_garancie_cell = Table([["FLETË GARANCIE"]], colWidths=[2.5*inch])
            flete_garancie_cell.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (0, 0), black),
                ('TEXTCOLOR', (0, 0), (0, 0), 'white'),
                ('ALIGN', (0, 0), (0, 0), 'CENTER'),
                ('VALIGN', (0, 0), (0, 0), 'MIDDLE'),
                ('FONTNAME', (0, 0), (0, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (0, 0), 12),
                ('LEFTPADDING', (0, 0), (0, 0), 8),
                ('RIGHTPADDING', (0, 0), (0, 0), 8),
                ('TOPPADDING', (0, 0), (0, 0), 10),
                ('BOTTOMPADDING', (0, 0), (0, 0), 10),
            ]))
            
            # Create the main table with left and right content
            main_data = [[left_content, flete_garancie_cell]]
            main_table = Table(main_data, colWidths=[3.5*inch, 2.5*inch])
            main_table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (0, 0), 'LEFT'),
                ('ALIGN', (1, 0), (1, 0), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('LEFTPADDING', (0, 0), (-1, -1), 0),
                ('RIGHTPADDING', (0, 0), (-1, -1), 0),
                ('TOPPADDING', (0, 0), (-1, -1), 0),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
            ]))
            
            story.append(main_table)
            
        except Exception as e:
            _logger.error(f'Error creating customer/product section: {str(e)}')
            # Fallback: create simple section with proper UTF-8 encoding
            safe_customer_name = customer_name.encode('utf-8').decode('utf-8') if customer_name else "___________________"
            safe_product_name = product_name.encode('utf-8').decode('utf-8') if product_name else "________________"
            safe_warranty_period = warranty_period.encode('utf-8').decode('utf-8') if warranty_period else "1"
            story.append(Paragraph("Emer Mbiemer: " + safe_customer_name, form_label_style))
            story.append(Paragraph("Marka: " + safe_product_name, form_label_style))
            story.append(Paragraph("Afati Garancise: " + safe_warranty_period + " Muaj", form_label_style))
        
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


class WarrantyMissingWarrantyWizard(models.TransientModel):
    _name = 'warranty.missing.warranty.wizard'
    _description = 'Confirm Printing When Products Have No Warranty'

    move_id = fields.Many2one('account.move', string='Invoice', required=True)
    product_ids = fields.Many2many('product.product', string='Products Without Warranty', required=True)
    warning_message = fields.Text(string='Warning', readonly=True, default=lambda self: 'Some products have no warranty set. Do you want to continue printing?')

    def action_print(self):
        self.ensure_one()
        return self.move_id.with_context(confirm_missing_warranty=True).generate_warranty_pdfs()

    def action_cancel(self):
        return {'type': 'ir.actions.act_window_close'}