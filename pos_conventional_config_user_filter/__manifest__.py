{
    "name": "POS Conventional Config User Filter",
    "version": "19.0.1.0.0",
    "category": "Point of Sale",
    "summary": "Filter POS configurations by user",
    "author": "Xtendoo",
    "website": "https://xtendoo.es",
    "license": "LGPL-3",
    "depends": ["pos_conventional_core", "point_of_sale", "account"],
    "data": [
        "security/pos_config_record_rules.xml",
        "security/pos_session_record_rules.xml",
        "security/pos_order_record_rules.xml",
        "security/account_move_record_rules.xml",
        "views/res_users_views.xml",
    ],
    "installable": True,
    "uninstall_hook": "uninstall_hook",
}
