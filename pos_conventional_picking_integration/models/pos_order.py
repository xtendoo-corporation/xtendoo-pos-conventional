from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)

class PosOrder(models.Model):
    _inherit = "pos.order"

    show_albaran_button = fields.Boolean(
        string="Mostrar botón albarán",
        compute="_compute_show_albaran_button",
        store=False,
    )

    @api.depends("session_id", "session_id.config_id", "session_id.config_id.pos_enable_albaran")
    def _compute_show_albaran_button(self):
        for order in self:
            order.show_albaran_button = bool(
                order.session_id
                and order.session_id.config_id
                and order.session_id.config_id.pos_enable_albaran
            )

    def action_create_picking(self):
        """
        Crea un sale.order y su picking correspondiente desde el pedido POS.
        """
        self.ensure_one()
        if not self.partner_id:
             raise UserError(_("Debe seleccionar un cliente para crear el albarán."))
        if not self.lines:
             raise UserError(_("No hay líneas en el pedido."))

        sale_order_lines = []
        for line in self.lines:
            sale_order_lines.append((0, 0, {
                "product_id": line.product_id.id,
                "product_uom_qty": line.qty,
                "price_unit": line.price_unit,
                "discount": line.discount,
                "tax_id": [(6, 0, line.tax_ids_after_fiscal_position.ids or line.tax_ids.ids)],
                "name": line.full_product_name or line.product_id.display_name,
            }))

        sale_order_vals = {
            "partner_id": self.partner_id.id,
            "order_line": sale_order_lines,
            "origin": self.name,
            "note": _("Creado desde pedido POS: %s") % self.name,
            "company_id": self.company_id.id,
        }

        created_picking = False
        try:
            sale_order = self.env["sale.order"].create(sale_order_vals)
            # Link the POS order to the sale order if we have a field for it (we should add it in sale_integration)
            # In this module, we just create it and validate.

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
            _logger.exception("Error al crear albarán: %s", str(e))
            raise UserError(_("Error al crear el albarán: %s") % str(e))

        if created_picking:
            report_url = f"/report/html/pos_conventional_picking_integration.report_albaran_80mm/{created_picking.id}"
            return {
                "type": "ir.actions.client",
                "tag": "pos_conventional_print_iframe",
                "params": {
                    "url": report_url,
                    "next_action": {
                        "type": "ir.actions.act_window",
                        "res_model": "pos.order",
                        "res_id": self.id,
                        "view_mode": "form",
                        "target": "current",
                    },
                },
            }
        return True
