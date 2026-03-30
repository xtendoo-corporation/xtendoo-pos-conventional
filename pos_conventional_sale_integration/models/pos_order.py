from odoo import api, fields, models, _

class PosOrder(models.Model):
    _inherit = "pos.order"

    state = fields.Selection(
        selection_add=[("linked", "Vinculado a Venta")],
        ondelete={"linked": "set default"},
    )

    linked_sale_order_id = fields.Many2one(
        "sale.order",
        string="Pedido de venta vinculado",
        readonly=True,
        copy=False,
        help="Pedido de venta tradicional creado desde este pedido POS",
    )

    is_linked_to_sale = fields.Boolean(
        string="Vinculado a venta",
        compute="_compute_is_linked_to_sale",
        store=True,
        help="Indica si este pedido POS está vinculado a un pedido de venta tradicional",
    )

    @api.depends("linked_sale_order_id")
    def _compute_is_linked_to_sale(self):
        for order in self:
            order.is_linked_to_sale = bool(order.linked_sale_order_id)

    def open_linked_sale_order(self):
        self.ensure_one()
        if self.linked_sale_order_id:
            return {
                "type": "ir.actions.act_window",
                "res_model": "sale.order",
                "res_id": self.linked_sale_order_id.id,
                "view_mode": "form",
                "target": "current",
            }
        return {
            "type": "ir.actions.act_window",
            "res_model": "pos.order",
            "res_id": self.id,
            "view_mode": "form",
            "target": "current",
        }
