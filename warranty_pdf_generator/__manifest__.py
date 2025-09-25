{
    'name': 'Warranty PDF Generator',
    'version': '1.0.1',
    'category': 'Sales',
    'summary': 'Generate warranty certificates using reportlab',
    'description': """
        This module provides warranty certificate generation functionality:
        - Creates PDF documents directly using reportlab (no external dependencies)
        - Fills customer, product, and warranty information automatically
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