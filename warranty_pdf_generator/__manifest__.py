{
    'name': 'Warranty PDF Generator',
    'version': '1.0.0',
    'category': 'Sales',
    'summary': 'Generate warranty certificates using PDF templates',
    'description': """
        This module provides warranty certificate generation functionality:
        - Uses PDF templates for warranty certificates
        - Fills customer, product, and warranty information automatically
        - Supports the garancia.pdf template format
        - Integrates with invoice and product management
        - Generates professional warranty documents
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