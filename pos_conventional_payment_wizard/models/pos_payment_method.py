from odoo import models


class PosPaymentMethod(models.Model):
    _inherit = "pos.payment.method"

    def action_pay_order_from_kanban(self):
        self.ensure_one()
        order_id = self.env.context.get("active_id")
        if not order_id:
            return False

        order = self.env["pos.order"].browse(order_id)
        if order.exists():
            return order.action_pos_convention_pay_with_method(self.id)
        return False

