# Copyright 2026 Xtendoo
# License OPL-1
import odoo.tests

from odoo.addons.web.tests.test_js import HOOTCommon, unit_test_error_checker


@odoo.tests.tagged("post_install", "-at_install")
class TestPosOrderBarcodeFrontend(HOOTCommon):
    """Frontend HOOT tests for local barcode accumulation in POS conventional."""

    _test_params = [(
        "+",
        "@pos_conventional_order_barcode/barcode_controller/addLineLocally accumulates quantity for repeated scans in a new order,"
        "@pos_conventional_order_barcode/barcode_controller/addLineLocally creates a new line with barcode values in a new order,"
        "@pos_conventional_order_barcode/barcode_controller/processBarcode saves the order, blurs focus, resolves the barcode and then adds the product,"
        "@pos_conventional_order_barcode/barcode_controller/addProductToLines adds the scanned product through RPC on an already saved order,"
        "@pos_conventional_order_barcode/barcode_controller/addLineViaRPC reloads, saves the order and clears focus after adding the scanned product,"
        "@pos_conventional_order_barcode/barcode_controller/_blurActiveElement removes focus from generic focusable elements in the editable line,"
        "@pos_conventional_order_barcode/barcode_controller/_tryCleanupManualLineFocus blurs manual focus inside the lines one2many row,"
        "@pos_conventional_order_barcode/barcode_controller/onKeyDown removes focus from lines before buffering a barcode key,"
        "@pos_conventional_order_barcode/barcode_controller/onKeyDown still ignores editable targets outside lines",
    )]

    @odoo.tests.no_retry
    def test_hoot_barcode_controller(self):
        self.browser_js(
            f"/web/tests?headless&loglevel=2&timeout=15000{self.hoot_filters}",
            "",
            "",
            login="admin",
            timeout=1800,
            success_signal="[HOOT] Test suite succeeded",
            error_checker=unit_test_error_checker,
        )

