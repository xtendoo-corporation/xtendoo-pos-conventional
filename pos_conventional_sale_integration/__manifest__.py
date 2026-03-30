{
    "name": "POS Conventional Sale Integration",
    "version": "1.0",
    "category": "Point of Sale",
    "summary": "Integration with sale orders",
    "description": "Allows linking POS orders to traditional sale orders.",
    "author": "Xtendoo",
    "website": "https://xtendoo.es",
    "depends": ["pos_conventional_core", "pos_conventional_picking_integration", "sale"],
    "data": [
        "views/pos_order_views.xml",
        "views/report_sale_details_customer_account.xml",
    ],
    "installable": True,
}
