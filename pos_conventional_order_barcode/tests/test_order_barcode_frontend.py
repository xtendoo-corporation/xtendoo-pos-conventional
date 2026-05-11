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
        "@pos_conventional_order_barcode/barcode_controller/addProductToLines uses local flow and saves the new order after barcode scans",
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

