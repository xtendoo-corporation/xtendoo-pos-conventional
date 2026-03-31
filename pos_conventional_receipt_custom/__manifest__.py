{
    "name": "POS Conventional Receipt Custom",
    "version": "19.0.1.0.0",
    "category": "Point of Sale",
    "summary": "Customized receipts for POS Conventional",
    "description": "Customized 80mm simplified invoice report for POS Conventional.",
    "author": "Xtendoo",
    "website": "https://xtendoo.es",
    "license": "LGPL-3",
    "depends": ["pos_conventional_core"],
    "data": [
        "report/pos_order_report.xml",
        "data/mail_template_pos_receipt.xml",
    ],
    "installable": True,
}
