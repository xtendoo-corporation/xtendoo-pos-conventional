{
    "name": "POS Conventional Users PIN",
    "version": "19.0.1.0.0",
    "category": "Point of Sale",
    "summary": "User PIN management for POS",
    "author": "Xtendoo",
    "website": "https://xtendoo.es",
    "license": "LGPL-3",
    "depends": ["point_of_sale", "pos_conventional_session_management"],
    "data": [
        "security/ir.model.access.csv",
        "views/res_users_views.xml",
        "views/res_config_settings_views.xml",
        "views/pos_session_pin_wizard_views.xml",
    ],
    "installable": True,
}
