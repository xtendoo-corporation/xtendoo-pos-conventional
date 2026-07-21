{
    "name": "POS Conventional Barcode Scanner",
    "version": "19.0.1.0.0",
    "category": "Point of Sale",
    "summary": "Añade productos a pedidos POS conventional escaneando códigos de barras",
    "description": "Adapta el patrón de xtendoo_sale_barcode_scanner al formulario backend de pos.order en POS Conventional.",
    "author": "Xtendoo",
    "website": "https://www.xtendoo.es",
    "license": "OPL-1",
    "depends": ["pos_conventional_core", "barcodes"],
    "data": [
        "views/pos_order_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "pos_conventional_barcode_scanner/static/src/js/pos_conventional_barcode_scanner_field.js",
        ],
        "web.assets_unit_tests": [
            "pos_conventional_barcode_scanner/static/tests/**/*.test.js",
        ],
    },
    "installable": True,
    "application": False,
}


