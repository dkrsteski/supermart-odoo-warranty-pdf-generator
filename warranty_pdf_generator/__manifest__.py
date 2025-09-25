{
    'name': 'Warranty PDF Generator',
    'version': '1.0.0',
    'category': 'Sales',
    'summary': 'Generate warranty certificates using Word document templates',
    'description': """
        This module provides warranty certificate generation functionality:
        - Uses Word document templates for warranty certificates
        - Fills customer, product, and warranty information automatically
        - Supports the garancia.docx template format
        - Converts filled Word documents to PDF
        - Integrates with invoice and product management
        - Generates professional warranty documents
    """,
    'depends': ['account', 'product'],
    'external_dependencies': {
        'python': ['python-docx', 'reportlab', 'PyPDF2']
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