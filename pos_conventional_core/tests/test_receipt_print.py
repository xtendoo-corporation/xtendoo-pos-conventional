# Copyright 2024 Xtendoo
# License OPL-1
from odoo.tests.common import tagged

from .common import PosConventionalTestCommon

REPORT_XMLID = "pos_conventional_receipt_custom.report_factura_simplificada_80mm"


@tagged("pos_conventional_core", "-standard", "post_install", "-at_install")
class TestReceiptPrint(PosConventionalTestCommon):
    """
    Tests that verify the receipt printing flow after paying a POS order
    from pos_conventional_core.

    After action_validate_and_invoice():
    - The order must have an account.move (invoice).
    - The client action must include move_id pointing to that invoice.
    - The Python report report_factura_simplificada_80mm must be renderable
      for that account.move.
    """

    # ── helpers ───────────────────────────────────────────────────────────

    def _make_paid_order(self, *, iface_print_auto=False):
        """
        Creates a fully paid draft order and calls action_validate_and_invoice().

        Returns (order, action_result).
        """
        self.pos_config.iface_print_auto = iface_print_auto
        session = self._open_session()
        order = self._make_draft_order(session, partner=self.partner)
        self._add_line(order, self.product, qty=1.0)
        self._add_payment(order, self.cash_pm)
        result = order.action_validate_and_invoice()
        return order, result

    # ── account_move creation ─────────────────────────────────────────────

    def test_38_invoice_created_after_validate_and_invoice(self):
        """
        action_validate_and_invoice() must create an account.move linked
        to the order.

        Validates that _generate_pos_order_invoice() is called explicitly
        (since action_pos_order_paid only sets state='paid').
        """
        order, _result = self._make_paid_order()
        self.assertTrue(
            order.account_move,
            "account_move must exist after action_validate_and_invoice()",
        )
        self.assertEqual(
            order.account_move.move_type,
            "out_invoice",
            "The generated invoice must be of type 'out_invoice'",
        )

    def test_39_invoice_is_posted_after_validate(self):
        """
        The generated account.move must be in 'posted' state after
        action_validate_and_invoice(), so it can be printed.
        """
        order, _result = self._make_paid_order()
        if not order.account_move:
            self.skipTest("No invoice journal configured — account_move not created")
        self.assertEqual(
            order.account_move.state,
            "posted",
            "The invoice must be posted (confirmed) before printing",
        )

    def test_40_invoice_amount_matches_order_total(self):
        """
        The amount_total of the generated invoice must match the order total.
        """
        order, _result = self._make_paid_order()
        if not order.account_move:
            self.skipTest("No invoice journal configured — account_move not created")
        self.assertAlmostEqual(
            order.account_move.amount_total,
            order.amount_total,
            places=2,
            msg="Invoice amount_total must match the POS order amount_total",
        )

    def test_41_invoice_partner_matches_order_partner(self):
        """
        The partner on the generated invoice must match the order partner.
        """
        order, _result = self._make_paid_order()
        if not order.account_move:
            self.skipTest("No invoice journal configured — account_move not created")
        self.assertEqual(
            order.account_move.partner_id,
            order.partner_id,
            "Invoice partner must match order partner",
        )

    # ── move_id in client action ──────────────────────────────────────────

    def test_42_print_action_contains_valid_move_id(self):
        """
        With iface_print_auto=True, the returned client action must include
        a non-False move_id pointing to the generated invoice.
        """
        order, result = self._make_paid_order(iface_print_auto=True)
        self.assertIsInstance(result, dict, "action_validate_and_invoice must return a dict")
        self.assertEqual(
            result.get("tag"),
            "pos_conventional_print_receipt_client",
            "The action tag must be 'pos_conventional_print_receipt_client'",
        )
        params = result.get("params", {})
        move_id = params.get("move_id")
        self.assertTrue(
            move_id,
            "move_id in action params must be a valid integer (not False/None)",
        )
        if order.account_move:
            self.assertEqual(
                move_id,
                order.account_move.id,
                "move_id must point to the invoice linked to the order",
            )

    def test_42b_print_action_contains_next_action_for_auto_redirect(self):
        """
        With iface_print_auto=True, the action params must include next_action
        pointing to pos_conventional_new_order so the JS component can redirect
        automatically after printing — no intermediate confirmation screen.
        """
        _order, result = self._make_paid_order(iface_print_auto=True)
        params = result.get("params", {})
        next_action = params.get("next_action")
        self.assertIsNotNone(
            next_action,
            "next_action must be present in print action params so the JS can "
            "redirect automatically to a new order after printing",
        )
        self.assertIsInstance(next_action, dict, "next_action must be a dict")
        self.assertEqual(
            next_action.get("tag"),
            "pos_conventional_new_order",
            "next_action must point to pos_conventional_new_order so that after "
            "printing the receipt the user lands directly on a new blank order",
        )

    def test_43_print_action_move_id_points_to_correct_record(self):
        """
        The move_id in the action params must refer to an existing account.move
        of type 'out_invoice' linked to the order.
        """
        order, result = self._make_paid_order(iface_print_auto=True)
        if not isinstance(result, dict):
            self.skipTest("action_validate_and_invoice did not return a dict")
        move_id = result.get("params", {}).get("move_id")
        if not move_id:
            self.skipTest("No invoice journal configured — move_id is False")
        move = self.env["account.move"].browse(move_id)
        self.assertTrue(move.exists(), "move_id must reference an existing account.move")
        self.assertEqual(move.move_type, "out_invoice")
        self.assertIn(
            order,
            move.pos_order_ids,
            "The POS order must be linked to the generated invoice via pos_order_ids",
        )

    def test_44_without_print_auto_move_id_not_in_action(self):
        """
        With iface_print_auto=False, the action must NOT include a print
        tag — the new order action is returned instead.
        """
        order, result = self._make_paid_order(iface_print_auto=False)
        self.assertIsInstance(result, dict)
        tag = result.get("tag", "")
        self.assertNotEqual(
            tag,
            "pos_conventional_print_receipt_client",
            "Without iface_print_auto, the print client action must not be returned",
        )
        self.assertEqual(
            tag,
            "pos_conventional_new_order",
            "Without iface_print_auto, the new order action must be returned",
        )

    # ── report renderability ──────────────────────────────────────────────

    def test_45_report_xmlid_exists_in_registry(self):
        """
        The ir.actions.report record for report_factura_simplificada_80mm
        must be present and bound to the account.move model.
        """
        report = self.env["ir.actions.report"]._get_report(REPORT_XMLID)
        self.assertTrue(
            report,
            f"Report '{REPORT_XMLID}' not found in ir.actions.report",
        )
        self.assertEqual(
            report.model,
            "account.move",
            "The report must target the account.move model",
        )

    def test_46_report_renders_for_invoice(self):
        """
        The report_factura_simplificada_80mm must render without errors
        for the invoice generated after paying a POS order.

        This is the critical end-to-end test: it proves that the Python
        Qweb report can actually produce HTML output for the account.move
        created by pos_conventional_core.
        """
        order, _result = self._make_paid_order(iface_print_auto=True)
        if not order.account_move:
            self.skipTest("No invoice journal configured — account_move not created")
        html_content, _content_type = self.env["ir.actions.report"]._render(
            REPORT_XMLID,
            order.account_move.ids,
        )
        self.assertTrue(
            html_content,
            "The rendered report must produce non-empty HTML content",
        )
        # The invoice name must appear in the rendered output
        self.assertIn(
            order.account_move.name.encode(),
            html_content,
            "The invoice name must appear in the rendered receipt HTML",
        )

    def test_47_report_contains_order_total(self):
        """
        The rendered HTML must contain the order total amount, confirming
        that o.amount_total is accessible in the Qweb template.
        """
        order, _result = self._make_paid_order(iface_print_auto=True)
        if not order.account_move:
            self.skipTest("No invoice journal configured — account_move not created")
        html_content, _content_type = self.env["ir.actions.report"]._render(
            REPORT_XMLID,
            order.account_move.ids,
        )
        # Format the total with 2 decimal places as the template does
        total_str = f"{order.amount_total:.2f}".encode()
        self.assertIn(
            total_str,
            html_content,
            f"Amount total '{total_str}' must appear in the rendered receipt",
        )

    def test_48_report_renders_company_name(self):
        """
        The rendered HTML must include the company name from res_company.
        """
        order, _result = self._make_paid_order(iface_print_auto=True)
        if not order.account_move:
            self.skipTest("No invoice journal configured — account_move not created")
        html_content, _content_type = self.env["ir.actions.report"]._render(
            REPORT_XMLID,
            order.account_move.ids,
        )
        company_name = self.env.company.name.encode()
        self.assertIn(
            company_name,
            html_content,
            "Company name must appear in the rendered receipt",
        )

    def test_49_report_contains_product_line(self):
        """
        The rendered HTML must contain at least one invoice line,
        confirming that o.invoice_line_ids is populated correctly.
        """
        order, _result = self._make_paid_order(iface_print_auto=True)
        if not order.account_move:
            self.skipTest("No invoice journal configured — account_move not created")
        html_content, _content_type = self.env["ir.actions.report"]._render(
            REPORT_XMLID,
            order.account_move.ids,
        )
        product_name = self.product.name.encode()
        self.assertIn(
            product_name,
            html_content,
            f"Product name '{self.product.name}' must appear in the rendered receipt",
        )

    # ── order state after full flow ───────────────────────────────────────

    def test_50_order_state_is_done_after_invoicing(self):
        """
        After action_validate_and_invoice(), the POS order state must be
        'done' (set by _generate_pos_order_invoice).
        """
        order, _result = self._make_paid_order()
        if not order.account_move:
            self.skipTest("No invoice journal configured — account_move not created")
        self.assertEqual(
            order.state,
            "done",
            "Order state must be 'done' after generating the invoice",
        )

    def test_51_second_call_to_validate_returns_false(self):
        """
        Calling action_validate_and_invoice() a second time on an already
        processed order must return False (idempotency guard).
        """
        order, _first_result = self._make_paid_order()
        second_result = order.action_validate_and_invoice()
        self.assertFalse(
            second_result,
            "Second call to action_validate_and_invoice must return False",
        )
