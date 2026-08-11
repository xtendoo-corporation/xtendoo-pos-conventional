{
    "name": "POS Conventional Users PIN",
    "version": "19.0.1.0.0",
    "category": "Point of Sale",
    "summary": "User PIN management for POS",
    "author": "Xtendoo",
    "website": "https://xtendoo.es",
    "license": "LGPL-3",
    "depends": [
        "pos_conventional_core",
        "point_of_sale",
        "pos_conventional_session_management",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/res_users_views.xml",
        "views/res_config_settings_views.xml",
        "views/pos_session_pin_wizard_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "pos_conventional_users_pin/static/src/js/pos_order_list_pin_patch.js",
            "pos_conventional_users_pin/static/src/js/pos_pin_masked_field.js",
            "pos_conventional_users_pin/static/src/xml/pos_pin_masked_field.xml",
            "pos_conventional_users_pin/static/src/scss/pos_pin_masked_field.scss",
        ],
    },
    "installable": True,
}
