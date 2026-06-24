from odoo import models


class PosMakePaymentConventional(models.TransientModel):
    _inherit = "pos.make.payment"

    def check(self, payment_method_id=None, force_print=False):
        action = super().check(payment_method_id=payment_method_id, force_print=force_print)
        order = self.env["pos.order"].browse(self.env.context.get("active_id", False))
        if order:
            action = order._pos_conventional_qztray_enrich_print_action(action)
        return action
