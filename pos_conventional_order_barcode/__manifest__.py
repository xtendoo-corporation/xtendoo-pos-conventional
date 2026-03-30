{
    "name": "POS Conventional Order Barcode",
    "version": "1.0",
    "category": "Point of Sale",
    "summary": "Barcode support for POS Conventional orders",
    "description": "Allows scanning barcodes in the backend POS order form.",
    "author": "Xtendoo",
    "website": "https://xtendoo.es",
    "depends": ["pos_conventional_core"],
    "data": [
        "views/pos_order_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "pos_conventional_order_barcode/static/src/js/pos_order_form_barcode_controller.js",
        ],
    },
    "installable": True,
}
