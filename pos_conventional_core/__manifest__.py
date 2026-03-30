{
    "name": "POS Conventional Core",
    "version": "1.0",
    "category": "Point of Sale",
    "summary": "Core functionalities for POS Conventional",
    "description": "Base module for POS Conventional, handling settings, ticket codes, and basic UI improvements.",
    "author": "Xtendoo",
    "website": "https://xtendoo.es",
    "depends": ["point_of_sale"],
    "data": [
        "views/pos_config_views.xml",
        "views/res_config_settings_views.xml",
        "views/pos_order_views.xml",
        "data/pos_order_sequence.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "pos_conventional_core/static/src/js/pos_print_iframe.js",
            "pos_conventional_core/static/src/js/pos_new_order_action.js",
            "pos_conventional_core/static/src/js/pos_order_list_controller.js",
            "pos_conventional_core/static/src/js/pos_order_list_auto_open.js",
            "pos_conventional_core/static/src/js/pos_print_client_action.js",
            "pos_conventional_core/static/src/js/pos_receipt_client_action.js",
        ],
    },
    "installable": True,
}
