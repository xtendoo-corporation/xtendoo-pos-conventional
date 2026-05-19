{
    "name": "pos_conventional_line_employees",
    "version": "1.0.0",
    "summary": "Asignación de empleados a líneas POS",
    "category": "Point of Sale",
    "author": "XTendoo",
    "depends": ["pos_conventional_core", "point_of_sale", "hr"],
    "data": [
        "security/ir.model.access.csv",
        "views/pos_order_line_views.xml",
        "views/pos_order_tree_inherit.xml",
        "views/report_saledetails_inherit.xml",
        "views/report_saledetails_custom.xml",
        "views/pos_details_wizard_inherit.xml",
    ],
    "installable": True,
    "application": False,
}
