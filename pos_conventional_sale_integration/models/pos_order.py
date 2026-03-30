from odoo import api, fields, models, _
from odoo.exceptions import UserError


class PosOrder(models.Model):
    _inherit = "pos.order"

    def open_linked_sale_order(self):
        """Abre el pedido de venta vinculado a este pedido POS."""
        self.ensure_one()
        if not self.linked_sale_order_id:
            raise UserError(_("Este pedido no tiene un pedido de venta vinculado."))
        return {
            "type": "ir.actions.act_window",
            "res_model": "sale.order",
            "res_id": self.linked_sale_order_id.id,
            "view_mode": "form",
            "target": "current",
        }
