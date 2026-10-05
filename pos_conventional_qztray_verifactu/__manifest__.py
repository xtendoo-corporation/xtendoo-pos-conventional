{
    "name": "POS Conventional QZ Tray Veri*Factu",
    "version": "19.0.1.0.0",
    "category": "Accounting/Localizations/Point of Sale",
    "summary": "Imprime el QR Veri*Factu en los tickets QZ Tray (HTML y RAW ESC/POS)",
    "author": "Xtendoo",
    "website": "https://xtendoo.es",
    "license": "LGPL-3",
    "depends": [
        "pos_conventional_qztray",
        "pos_conventional_verifactu",
    ],
    "data": [
        "report/receipt_templates.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": True,
}
