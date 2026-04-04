{
    "name": "POS Conventional Sale Integration",
    "version": "19.0.1.0.0",
    "category": "Point of Sale",
    "summary": "Integration with sale orders",
    "description": "Allows linking POS orders to traditional sale orders.",
    "author": "Xtendoo",
    "website": "https://xtendoo.es",
    "license": "LGPL-3",
    "depends": ["point_of_sale", "pos_conventional_picking_integration", "sale"],
    "data": [
        "views/pos_order_views.xml",
        "views/report_sale_details_customer_account.xml",
    ],
    "installable": True,
}
