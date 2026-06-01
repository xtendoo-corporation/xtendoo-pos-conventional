from odoo import models


class PosMakePayment(models.TransientModel):
    _inherit = "pos.make.payment"

    def check(self, payment_method_id=None, force_print=False):
        self.ensure_one()
        order = self.env["pos.order"].browse(self.env.context.get("active_id")).exists()
        payment_method = (
            self.env["pos.payment.method"].browse(payment_method_id)
            if payment_method_id
            else self.payment_method_id
        )

        result = super().check(
            payment_method_id=payment_method_id,
            force_print=force_print,
        )

        if (
            not order
            or order.state not in {"paid", "done"}
            or not order._is_cash_payment_method(payment_method)
        ):
            return result

        return order._wrap_action_with_cash_drawer(result, require_auto_open=True)

