from odoo.tests.common import tagged
from odoo.exceptions import UserError

from .common import PosConventionalReturnsCommon


@tagged("pos_conventional_returns", "post_install", "-at_install")
class TestPosConventionalReturns(PosConventionalReturnsCommon):
    def test_01_action_open_conventional_returns_filters_same_config(self):
        session = self._open_session()

        other_cash_pm = self._make_fresh_cash_pm("Otra caja devoluciones")
        other_config = self.env["pos.config"].create({
            "name": "Otra caja",
            "payment_method_ids": [(6, 0, [other_cash_pm.id])],
            "invoice_journal_id": self.invoice_journal.id,
            "pos_non_touch": True,
        })
        self._open_session(other_config)

        action = self.env["pos.order"].with_context(
            default_session_id=session.id,
            session_id=session.id,
        ).action_open_conventional_returns()

        self.assertEqual(action["name"], "Devoluciones")
        self.assertEqual(
            action["domain"],
            [("config_id", "=", session.config_id.id), ("state", "not in", ["draft", "cancel"])],
        )
        self.assertTrue(action["context"].get("conventional_returns_mode"))
        self.assertEqual(action["context"].get("default_session_id"), session.id)

    def test_02_refund_created_in_current_session_of_same_config(self):
        original_session = self._open_session()
        order = self._make_draft_order(original_session, partner=self.partner)
        self._add_line(order)
        self._add_payment(order, self.cash_pm, order.amount_total)
        order.action_pos_order_paid()

        original_session.write({"state": "closed"})
        new_session = self._open_session(original_session.config_id)

        action = order.refund()
        refund_order = self.env["pos.order"].browse(action["res_id"])

        self.assertEqual(refund_order.session_id, new_session)
        self.assertTrue(refund_order.is_refund)
        self.assertTrue(any(line.qty < 0 for line in refund_order.lines))

    def test_03_refund_without_refundable_lines_raises_functional_error(self):
        session = self._open_session()
        order = self._make_draft_order(session, partner=self.partner)
        self._add_line(order)
        self._add_payment(order, self.cash_pm, order.amount_total)
        order.action_pos_order_paid()

        refund_action = order.refund()
        refund_order = self.env["pos.order"].browse(refund_action["res_id"])

        with self.assertRaisesRegex(UserError, "no tiene líneas disponibles para devolver"):
            refund_order.refund()

