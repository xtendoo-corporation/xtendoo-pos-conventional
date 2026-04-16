{
    "name": "POS Conventional Returns",
    "version": "19.0.1.0.0",
    "category": "Point of Sale",
    "summary": "Backend returns flow for conventional POS",
    "description": "Adds a dedicated backend returns flow for conventional POS sessions.",
    "author": "Xtendoo",
    "website": "https://xtendoo.es",
    "depends": [
        "pos_conventional_core",
    ],
    "data": [
        "views/pos_order_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "pos_conventional_returns/static/src/js/pos_order_list_returns_patch.js",
        ],
    },
    "installable": True,
    "license": "OPL-1",
}

