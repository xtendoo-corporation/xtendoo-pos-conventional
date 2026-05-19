from odoo import models


class PosMakePaymentWizard(models.TransientModel):
    _inherit = "pos.make.payment.wizard"

    def _execute_validation(self, print_invoice=False):
        self.ensure_one()
        result = super()._execute_validation(print_invoice=print_invoice)
        order = self.order_id.exists()

        if (
            not order
            or order.state not in {"paid", "done"}
            or not order._is_cash_payment_method(self.payment_method_id)
        ):
            return result

        return order._wrap_action_with_cash_drawer(result, require_auto_open=True)

