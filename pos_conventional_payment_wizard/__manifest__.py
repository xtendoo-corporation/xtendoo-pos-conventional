{
    "name": "POS Conventional Payment Wizard",
    "version": "1.0",
    "category": "Point of Sale",
    "summary": "Advanced and quick payment interface for POS Conventional",
    "author": "Xtendoo",
    "website": "https://xtendoo.es",
    "depends": ["pos_conventional_core"],
    "data": [
        "security/ir.model.access.csv",
        "views/pos_make_payment_views.xml",
        "views/pos_order_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "pos_conventional_payment_wizard/static/src/js/pos_payment_buttons.js",
            "pos_conventional_payment_wizard/static/src/xml/pos_payment_buttons.xml",
        ],
    },
    "installable": True,
}
