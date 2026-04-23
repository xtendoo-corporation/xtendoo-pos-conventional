{
    "name": "POS Conventional Cash Drawer",
    "version": "19.0.1.0.0",
    "category": "Point of Sale",
    "summary": "Abre el cajón desde los botones rápidos de pago del POS convencional",
    "author": "Xtendoo",
    "website": "https://xtendoo.es",
    "license": "LGPL-3",
    "depends": [
        "pos_conventional_payment_wizard",
        "xtendoo_cash_drawer",
    ],
    "data": [
        "views/pos_order_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "pos_conventional_cash_drawer/static/src/js/pos_payment_buttons_cash_drawer.js",
            "pos_conventional_cash_drawer/static/src/xml/pos_payment_buttons_cash_drawer.xml",
        ],
    },
    "installable": True,
    "application": False,
}

