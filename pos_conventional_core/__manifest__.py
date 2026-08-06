{
    "name": "POS Conventional Core",
    "version": "19.0.1.0.0",
    "category": "Point of Sale",
    "summary": "Core functionality for non-touch POS",
    "description": "Base module for the POS Conventional modular system. Handles non-touch mode toggle and base order logic.",
    "author": "Xtendoo",
    "website": "https://xtendoo.es",
    "depends": [
        "point_of_sale",
        "sale",
        "mail",
        "pos_hr"
    ],

    "data": [
        "security/ir.model.access.csv",
        "views/res_config_settings_views.xml",
        "views/pos_config_kanban_views.xml",
        "views/pos_order_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            # Custom POS backend JS/CSS
            "pos_conventional_core/static/src/js/pos_order_workflow_utils.js",
            "pos_conventional_core/static/src/js/pos_order_form_core_controller.js",
            "pos_conventional_core/static/src/xml/pos_print_iframe_template.xml",
            "pos_conventional_core/static/src/js/pos_print_iframe.js",
            "pos_conventional_core/static/src/js/pos_print_client_action.js",
            "pos_conventional_core/static/src/js/pos_new_order_action.js",
            "pos_conventional_core/static/src/js/pos_order_list_controller.js",
            "pos_conventional_core/static/src/js/pos_order_list_auto_open.js",
            "pos_conventional_core/static/src/js/pos_action_service_patch.js",
            "pos_conventional_core/static/src/js/product_label_section_and_note_field_patch.js",
            "pos_conventional_core/static/src/xml/pos_order_list_view.xml",
            # POS receipt components injected into backend, needed by
            # pos_receipt_client_action.js which renders OrderReceipt.
            # pos_conventional_receipt/static/src/xml/receipt_templates.xml
            # is also required here but is contributed by that module's own
            # manifest (web.assets_backend), not listed here, to avoid a
            # circular dependency (pos_conventional_receipt already depends
            # on pos_conventional_core).
            "point_of_sale/static/lib/qrcode.js",
            "point_of_sale/static/src/utils.js",
            "point_of_sale/static/src/css/pos_receipts.css",
            "point_of_sale/static/src/app/utils/use_timed_press.js",
            "point_of_sale/static/src/app/components/centered_icon/centered_icon.js",
            "point_of_sale/static/src/app/screens/receipt_screen/receipt/order_receipt.js",
            "point_of_sale/static/src/app/screens/receipt_screen/receipt/order_receipt.xml",
            "point_of_sale/static/src/app/screens/receipt_screen/receipt_screen.xml",
            "point_of_sale/static/src/app/store/order_change_receipt_template.xml",
            "point_of_sale/static/src/app/components/orderline/orderline.js",
            "point_of_sale/static/src/app/components/orderline/orderline.xml",
            "point_of_sale/static/src/app/screens/receipt_screen/receipt/receipt_header/receipt_header.js",
            "point_of_sale/static/src/app/screens/receipt_screen/receipt/receipt_header/receipt_header.xml",
            "point_of_sale/static/src/app/components/order_display/order_display.js",
            "point_of_sale/static/src/app/components/order_display/order_display.xml",
            "point_of_sale/static/src/app/screens/receipt_screen/receipt_screen.scss",
            # Actual receipt client action (must go after POS components are registered)
            "pos_conventional_core/static/src/js/pos_receipt_client_action.js",
        ],
        "web.assets_unit_tests": [
            "pos_conventional_core/static/tests/pos_order_workflow_utils.test.js",
            "pos_conventional_core/static/tests/pos_order_form_core_controller.test.js",
            "pos_conventional_core/static/tests/product_label_section_and_note_field_patch.test.js",
            "pos_conventional_core/static/tests/pos_new_order_action.test.js",
        ],
    },
    "installable": True,
    "license": "OPL-1",
}
