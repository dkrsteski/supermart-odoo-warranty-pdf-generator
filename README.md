# Warranty PDF Generator

A standalone Odoo addon for generating warranty certificates using PDF templates.

## Features

- **Template-Based Generation**: Uses PDF templates (garancia.pdf) for professional warranty certificates
- **Automatic Field Filling**: Fills customer name, product brand, and warranty period automatically
- **Multi-Product Support**: Generates separate certificates for each product on an invoice
- **Configurable Settings**: Exclude specific products and set default warranty periods
- **Integration Ready**: Works with any Odoo invoice/product system

## Installation

1. Copy the `warranty_pdf_generator` folder to your Odoo addons directory
2. Install required Python dependencies:
   ```bash
   pip install reportlab PyPDF2
   ```
3. Update your addon list in Odoo
4. Install the "Warranty PDF Generator" module

## Usage

### Generating Warranty PDFs

1. Open any Customer Invoice
2. Click the "Generate Warranty PDFs" button in the header
3. The system will:
   - Process all products on the invoice
   - Fill the warranty template with customer and product data
   - Generate a downloadable PDF with certificates

### Configuration

Access warranty settings via: **Accounting → Configuration → Warranty PDF Settings**

- **Default Warranty Period**: Set default warranty in months when product warranty is not specified
- **Exclude Products**: Select products to exclude from warranty generation
- **Template Settings**: Upload custom warranty templates (future feature)

## Technical Details

### File Structure
```
warranty_pdf_generator/
├── models/
│   └── warranty_pdf_generator.py    # Main PDF generation logic
├── views/
│   └── account_move_views.xml       # UI integration
├── static/data/
│   └── garancia.pdf                 # Warranty template
└── __manifest__.py                  # Module configuration
```

### Key Methods

- `generate_warranty_pdfs()`: Main entry point for warranty generation
- `_generate_filled_warranty_pdf()`: Processes multiple products
- `_fill_warranty_template()`: Fills individual PDF templates

### Dependencies

- **Odoo Modules**: account, product
- **Python Libraries**: reportlab, PyPDF2

## Business Rules

1. Products with ID 7884 are excluded by default
2. Default warranty period is 1 month if not specified
3. Customer name is taken from invoice partner
4. Product name is used as the brand/product identifier
5. Warranty period is extracted from product's `x_studio_warranty` field

## Template Format

The warranty template (garancia.pdf) contains three fillable fields:
- **Emer Mbiemer** (Customer Name)
- **Marka** (Product Brand)
- **Afati Garancise** (Warranty Period in months)

## Support

For technical support or customization requests, contact your Odoo developer or system administrator.