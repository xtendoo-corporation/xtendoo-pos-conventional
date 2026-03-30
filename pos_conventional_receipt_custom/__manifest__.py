{
    "name": "POS Conventional Receipt Custom",
    "version": "1.0",
    "category": "Point of Sale",
    "summary": "Customized receipts for POS Conventional",
    "description": "Customized 80mm simplified invoice report for POS Conventional.",
    "author": "Xtendoo",
    "website": "https://xtendoo.es",
    "depends": ["pos_conventional_core"],
    "data": [
        "report/pos_order_report.xml",
        "models/pos_order.py", # This should be in data too if it adds views, but here it is for models
    ],
    "installable": True,
}
