{
    "name": "POS Conventional Users PIN",
    "version": "19.0.1.0.0",
    "category": "Point of Sale",
    "summary": "User PIN management for POS",
    "depends": ["pos_conventional_core"],
    "data": [
        "security/ir.model.access.csv",
        "views/res_users_views.xml",
        "views/pos_session_pin_wizard_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "pos_conventional_users_pin/static/src/js/pos_new_order_action.js",
        ],
    },
    "installable": True,
}
