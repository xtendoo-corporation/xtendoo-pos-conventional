{
    "name": "POS Conventional Veri*Factu",
    "version": "19.0.1.0.0",
    "category": "Accounting/Localizations/Point of Sale",
    "summary": "Imprime el QR Veri*Factu en los tickets de POS Conventional",
    "author": "Xtendoo",
    "website": "https://xtendoo.es",
    "license": "LGPL-3",
    "depends": [
        "pos_conventional_receipt_custom",
        "l10n_es_edi_verifactu_pos",
    ],
    "data": [
        "report/receipt_templates.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": True,
}
