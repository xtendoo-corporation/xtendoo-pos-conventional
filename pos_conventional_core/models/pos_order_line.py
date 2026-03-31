import logging
from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class PosOrderLine(models.Model):
    _inherit = "pos.order.line"

    def _compute_total_cost_from_product(self, product, qty, order=None):
        """Calcula total_cost usando el precio de coste del producto."""
        if not product or not product.standard_price:
            return 0.0
        cost_currency = product.sudo().cost_currency_id
        currency = (order.currency_id if order else None) or self.env.company.currency_id
        company = (order.company_id if order else None) or self.env.company
        date = (order.date_order if order else None) or fields.Date.today()
        return qty * cost_currency._convert(
            from_amount=product.standard_price,
            to_currency=currency,
            company=company,
            date=date,
            round=False,
        )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            # Solo calcular si no viene ya informado
            if not vals.get("total_cost") and not vals.get("is_total_cost_computed"):
                product_id = vals.get("product_id")
                if product_id:
                    product = self.env["product.product"].browse(product_id)
                    order = (
                        self.env["pos.order"].browse(vals["order_id"])
                        if vals.get("order_id")
                        else None
                    )
                    qty = vals.get("qty", 1.0)
                    total_cost = self._compute_total_cost_from_product(product, qty, order)
                    vals["total_cost"] = total_cost
                    vals["is_total_cost_computed"] = True
        return super().create(vals_list)

    def write(self, vals):
        # Recalcular total_cost cuando cambia qty o product_id
        qty_changed = "qty" in vals
        product_changed = "product_id" in vals
        if (qty_changed or product_changed) and "total_cost" not in vals:
            for line in self:
                product = (
                    self.env["product.product"].browse(vals["product_id"])
                    if product_changed
                    else line.product_id
                )
                qty = vals.get("qty", line.qty)
                order = line.order_id or None
                total_cost = self._compute_total_cost_from_product(product, qty, order)
                super(PosOrderLine, line).write(
                    dict(vals, total_cost=total_cost, is_total_cost_computed=True)
                )
            return True
        return super().write(vals)

