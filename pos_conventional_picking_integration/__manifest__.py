{
    "name": "POS Conventional Picking Integration",
    "version": "1.0",
    "category": "Point of Sale",
    "summary": "Integration with stock pickings (albaranes)",
    "description": "Allows creating stock pickings (albaranes) directly from the POS backend.",
    "author": "Xtendoo",
    "website": "https://xtendoo.es",
    "depends": ["pos_conventional_core", "stock", "sale"],
    "data": [
        "views/pos_order_views.xml",
        "report/albaran_receipt.xml",
    ],
    "installable": True,
}
