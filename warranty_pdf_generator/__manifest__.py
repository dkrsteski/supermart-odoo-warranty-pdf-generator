{
    'name': 'Warranty PDF Generator',
    'version': '1.0.0',
    'category': 'Sales',
    'summary': 'Generate warranty certificates programmatically',
    'description': """
        This module provides warranty certificate generation functionality:
        - Creates Word documents programmatically (no external template files)
        - Fills customer, product, and warranty information automatically
        - Converts generated Word documents to PDF
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