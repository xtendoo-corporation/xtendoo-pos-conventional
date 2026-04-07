from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)

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
    )

    show_albaran_button = fields.Boolean(
        string="Mostrar botón albarán",
        compute="_compute_show_albaran_button",
        store=False,
    )

    @api.depends("linked_sale_order_id")
    def _compute_is_linked_to_sale(self):
        for order in self:
            order.is_linked_to_sale = bool(order.linked_sale_order_id)

    @api.depends("session_id", "session_id.config_id", "session_id.config_id.pos_enable_albaran")
    def _compute_show_albaran_button(self):
        for order in self:
            order.show_albaran_button = bool(
                order.session_id
                and order.session_id.config_id
                and order.session_id.config_id.pos_enable_albaran
            )

    def action_pay_account(self):
        """
        Intercambia el pedido POS por un pedido de venta tradicional (Albarán).
        """
        self.ensure_one()
        if self.state != "draft":
            raise UserError(_("Solo se pueden convertir a albarán pedidos en estado borrador."))

        if not self.lines:
            raise UserError(_("No se puede crear un albarán de un pedido sin líneas."))

        if not self.partner_id:
            raise UserError(_("Debe seleccionar un cliente para crear el albarán."))

        sale_order_lines = []
        for line in self.lines:
            taxes = line.tax_ids_after_fiscal_position or line.tax_ids
            sale_order_lines.append((0, 0, {
                "product_id": line.product_id.id,
                "name": line.full_product_name or line.product_id.display_name,
                "product_uom_qty": line.qty,
                "price_unit": line.price_unit,
                "discount": line.discount or 0.0,
                "tax_ids": [(6, 0, taxes.ids)] if taxes else False,
            }))

        sale_order_vals = {
            "partner_id": self.partner_id.id,
            "order_line": sale_order_lines,
            "origin": self.name,
            "note": _("Creado desde pedido POS: %s") % self.name,
            "picking_policy": "direct",
        }

        if self.company_id:
            sale_order_vals["company_id"] = self.company_id.id

        created_picking = False
        try:
            sale_order = self.env["sale.order"].create(sale_order_vals)
            _logger.info("POS Order %s: Creado sale.order %s", self.name, sale_order.name)

            self.write({
                "linked_sale_order_id": sale_order.id,
                "name": sale_order.name,
                "state": "linked",
            })

            sale_order.action_confirm()

            for picking in sale_order.picking_ids:
                created_picking = picking
                if picking.state == "draft":
                    picking.action_confirm()
                if picking.state != "done":
                    picking.action_assign()
                    for move in picking.move_ids:
                        move.quantity = move.product_uom_qty
                    picking.button_validate()

        except Exception as e:
            _logger.exception("Error al crear sale.order desde POS: %s", str(e))
            raise UserError(_("Error al crear el albarán: %s") % str(e))

        # Acción de navegación post-pago: usa pos_conventional_core si está disponible
        _get_post_action = getattr(self, "_get_post_validation_action", None)

        if created_picking:
            report_url = f"/report/html/pos_conventional_picking_integration.report_albaran_80mm/{created_picking.id}"
            params = {"url": report_url}
            if _get_post_action:
                params["next_action"] = _get_post_action()
            return {
                "type": "ir.actions.client",
                "tag": "pos_conventional_print_iframe",
                "params": params,
            }

        if _get_post_action:
            return _get_post_action()
        return {"type": "ir.actions.act_window_close"}
