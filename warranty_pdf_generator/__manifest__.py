{
    'name': 'Warranty PDF Generator',
    'version': '1.0.1',
    'category': 'Sales',
    'summary': 'Generate warranty certificates using Word template with exact formatting',
    'description': """
        This module provides warranty certificate generation functionality:
        - Uses garancia.docx template with exact formatting, images, and styling
        - Converts Word template to PDF using LibreOffice to preserve formatting
        - Fills customer, product, and warranty information automatically
        - Integrates with invoice and product management
        - Generates professional warranty documents with original design
    """,
    'depends': ['account', 'product'],
    'external_dependencies': {
        'python': ['reportlab', 'PyPDF2']
    },
    'data': [
        'security/ir.model.access.csv',
        'views/account_move_views.xml',
    ],
    'assets': {},
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}