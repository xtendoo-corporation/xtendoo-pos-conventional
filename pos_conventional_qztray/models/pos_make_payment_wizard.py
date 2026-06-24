from odoo import models


class PosMakePaymentWizard(models.TransientModel):
    _inherit = "pos.make.payment.wizard"

    def _execute_validation(self, print_invoice=False):
        action = super()._execute_validation(print_invoice=print_invoice)
        if self.order_id:
            action = self.order_id._pos_conventional_qztray_enrich_print_action(action)
        return action
