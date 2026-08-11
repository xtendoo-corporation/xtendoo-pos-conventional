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
        "pos_conventional_receipt_custom",
        "base_report_to_printer_qztray",
    ],
    "data": [
        "data/pos_receipt_report.xml",
        "report/pos_original_receipt_report.xml",
        "views/res_config_settings_views.xml",
    ],
    "assets": {
        "point_of_sale.assets": [
            "pos_conventional_qztray/static/src/js/pos_receipt_qztray_patch.js",
        ],
    },
    "installable": True,
    "application": False,
}
