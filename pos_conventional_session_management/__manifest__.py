{
    "name": "POS Conventional Session Management",
    "version": "1.0",
    "category": "Point of Sale",
    "summary": "Session lifecycle management for POS Conventional",
    "author": "Xtendoo",
    "website": "https://xtendoo.es",
    "depends": ["pos_conventional_core", "pos_conventional_cash_calculator"],
    "data": [
        "security/ir.model.access.csv",
        "data/pos_session_sequence.xml",
        "wizard/pos_session_opening_wizard_views.xml",
        "wizard/pos_session_closing_wizard_views.xml",
        "wizard/pos_session_cash_move_wizard_views.xml",
        "views/pos_session_views.xml",
        "views/pos_config_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "pos_conventional_session_management/static/src/js/opening_popup.js",
            "pos_conventional_session_management/static/src/xml/opening_popup.xml",
            "pos_conventional_session_management/static/src/js/closing_popup.js",
            "pos_conventional_session_management/static/src/xml/closing_popup.xml",
            "pos_conventional_session_management/static/src/js/cash_move_popup.js",
            "pos_conventional_session_management/static/src/xml/cash_move_popup.xml",
        ],
    },
    "installable": True,
}
