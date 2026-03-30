{
    "name": "POS Conventional Config User Filter",
    "version": "1.0",
    "category": "Point of Sale",
    "summary": "Filter POS configurations by user",
    "author": "Xtendoo",
    "website": "https://xtendoo.es",
    "depends": ["pos_conventional_core"],
    "data": [
        "security/pos_config_record_rules.xml",
        "views/res_users_views.xml",
    ],
    "installable": True,
}
