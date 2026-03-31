{
    'name': 'pos_conventional_receipt',
    'summary': 'Personalización de recibos POS convencional',
    'version': '19.0.1.0.0',
    'author': 'Xtendoo',
    'website': 'https://xtendoo.es',
    'category': 'Point of Sale',
    'license': 'OPL-1',
    'depends': ['point_of_sale', 'l10n_es_pos'],
    'assets': {
        'point_of_sale._assets_pos': [
            'pos_conventional_receipt/static/src/css/pos_receipt.scss',
            'pos_conventional_receipt/static/src/xml/receipt_templates.xml',
            'pos_conventional_receipt/static/src/js/receipt_order.js',
        ],
    },
    'data': [],
    'installable': True,
    'application': False,
    'auto_install': False,
}
