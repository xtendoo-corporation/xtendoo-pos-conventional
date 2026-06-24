{
    "name": "POS Conventional QZ Tray",
    "version": "19.0.1.0.0",
    "category": "Point of Sale",
    "summary": "Impresión de tickets POS Conventional mediante QZ Tray",
    "author": "Xtendoo",
    "website": "https://xtendoo.es",
    "license": "LGPL-3",
    "depends": [
        "pos_conventional_core",
        "pos_conventional_payment_wizard",
        "base_report_to_printer_qztray",
    ],
    "data": [
        "views/res_config_settings_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "pos_conventional_qztray/static/src/js/pos_receipt_qztray_patch.js",
        ],
    },
    "installable": True,
    "application": False,
}
