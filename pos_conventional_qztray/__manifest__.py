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
        "web.assets_backend": [
            # Registra los mismos tags de ir.actions.client
            # (pos_conventional_print_receipt_window y
            # _qztray_window) que action_print_factura_simplificada puede
            # devolver desde el botón del formulario de pedido TPV. El
            # backend tiene disponibles qz (base_report_to_printer_qztray,
            # inyectado en web.layout) y PosReceiptClientAction
            # (pos_conventional_core), así que este fichero funciona igual
            # aquí que en la UI del TPV.
            "pos_conventional_qztray/static/src/js/pos_receipt_qztray_patch.js",
        ],
    },
    "installable": True,
    "application": False,
}
