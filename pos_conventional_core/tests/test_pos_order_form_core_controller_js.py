# Copyright 2026 Xtendoo
# License OPL-1
import odoo.tests

from odoo.addons.web.tests.test_js import HOOTCommon, unit_test_error_checker


@odoo.tests.tagged("post_install", "-at_install")
class TestPosOrderFormCoreControllerFrontend(HOOTCommon):
    """Frontend HOOT tests for the shared POS conventional form controller."""

    _test_params = [(
        "+",
        "@pos_conventional_core/order_workflow_utils/getRelationalValueId supports number, array and object values,"
        "@pos_conventional_core/order_workflow_utils/hasRealProductLines ignores notes and sections,"
        "@pos_conventional_core/order_workflow_utils/isZeroAmount allows negative totals but blocks zeros,"
        "@pos_conventional_core/order_workflow_utils/hasRecordedPayments detects payment records and amount_paid,"
        "@pos_conventional_core/order_workflow_utils/shouldBlockDraftOrderLeave only blocks draft orders with product lines and no payment,"
        "@pos_conventional_core/order_workflow_utils/loadPaymentMethods returns empty array when field has no ids,"
        "@pos_conventional_core/order_workflow_utils/loadPaymentMethods reads server names and keeps ids,"
        "@pos_conventional_core/order_workflow_utils/notifyInvalidOrderForPayment warns when order has no real lines,"
        "@pos_conventional_core/order_workflow_utils/notifyInvalidOrderForPayment warns when total is zero,"
        "@pos_conventional_core/order_workflow_utils/notifyInvalidOrderForPayment accepts negative totals with product lines,"
        "@pos_conventional_core/order_workflow_utils/activateNavigationBypass and clearNavigationBypass toggle the global flag,"
        "@pos_conventional_core/order_workflow_utils/payOrderWithMethod stops before RPC when order is invalid,"
        "@pos_conventional_core/order_workflow_utils/payOrderWithMethod saves, triggers RPC and executes the returned action,"
        "@pos_conventional_core/order_workflow_utils/payOrderWithMethod reloads the order and clears bypass when server returns no action,"
        "@pos_conventional_core/order_form_core_controller/_hasProductLines only returns true when there is at least one real product line,"
        "@pos_conventional_core/order_form_core_controller/beforeLeave allows leaving draft orders without product lines,"
        "@pos_conventional_core/order_form_core_controller/beforeLeave blocks leaving draft orders with product lines and no payment,"
        "@pos_conventional_core/order_form_core_controller/beforeLeave allows leaving draft orders with product lines when a payment is already registered,"
        "@pos_conventional_core/order_form_core_controller/_onPaymentButtonClick allows cancel to activate the navigation bypass,"
        "@pos_conventional_core/order_form_core_controller/_onPaymentButtonClick blocks empty or zero-total orders,"
        "@pos_conventional_core/order_form_core_controller/_onPaymentButtonClick activates bypass for valid orders,"
        "@pos_conventional_core/order_form_core_controller/_onDocClick activates bypass for stock forecast navigation",
    )]

    @odoo.tests.no_retry
    def test_hoot_order_form_core_controller(self):
        self.browser_js(
            f"/web/tests?headless&loglevel=2&timeout=15000{self.hoot_filters}",
            "",
            "",
            login="admin",
            timeout=1800,
            success_signal="[HOOT] Test suite succeeded",
            error_checker=unit_test_error_checker,
        )

