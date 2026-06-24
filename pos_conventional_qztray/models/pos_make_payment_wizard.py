from odoo import models


class PosMakePaymentWizard(models.TransientModel):
    _inherit = "pos.make.payment.wizard"

    def _pos_conventional_qztray_enrich_wizard_action(self, action):
        self.ensure_one()
        if self.order_id:
            return self.order_id._pos_conventional_qztray_enrich_print_action(action)
        return action

    def _execute_validation(self, print_invoice=False):
        action = super()._execute_validation(print_invoice=print_invoice)
        return self._pos_conventional_qztray_enrich_wizard_action(action)

    def action_validate(self):
        action = super().action_validate()
        return self._pos_conventional_qztray_enrich_wizard_action(action)

    def action_validate_print(self):
        action = super().action_validate_print()
        return self._pos_conventional_qztray_enrich_wizard_action(action)
