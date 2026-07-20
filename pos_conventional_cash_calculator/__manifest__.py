{
    "name": "POS Conventional Cash Calculator",
    "version": "19.0.2.0.0",
    "author": "Xtendoo",
    "website": "https://xtendoo.es",
    "license": "LGPL-3",
    "category": "Point of Sale",
    "summary": "Cash calculator utility for POS",
    "depends": ["point_of_sale", "sale", "mail"],
    "data": [
        "security/ir.model.access.csv",
        "views/pos_cash_calculator_wizard_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "pos_conventional_cash_calculator/static/src/scss/pos_cash_calculator_wizard.scss",
        ],
    },
    "installable": True,
}
