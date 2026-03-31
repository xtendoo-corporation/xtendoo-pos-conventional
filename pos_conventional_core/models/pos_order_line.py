import logging
from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class PosOrderLine(models.Model):
    _inherit = "pos.order.line"

    total_cost = fields.Float(
        compute="_compute_total_cost_conventional",
        store=True,
        readonly=False,
    )

    is_total_cost_computed = fields.Boolean(
        compute="_compute_total_cost_conventional",
        store=True,
        readonly=False,
    )

    def _get_total_cost_for_line(self):
        """Calcula total_cost para una línea usando el coste estándar del producto."""
        self.ensure_one()
        product = self.product_id
        if not product:
            return 0.0, False
        cost_currency = product.sudo().cost_currency_id
        order = self.order_id
        currency = order.currency_id or self.env.company.currency_id
        company = order.company_id or self.env.company
        date = (order.date_order.date() if order.date_order else None) or fields.Date.today()
        try:
            total_cost = self.qty * cost_currency._convert(
                from_amount=product.standard_price,
                to_currency=currency,
                company=company,
                date=date,
                round=False,
            )
        except Exception:
            total_cost = self.qty * product.standard_price
        return total_cost, True

    @api.depends(
        "product_id",
        "qty",
        "order_id.currency_id",
        "order_id.company_id",
        "order_id.date_order",
    )
    def _compute_total_cost_conventional(self):
        for line in self:
            total_cost, computed = line._get_total_cost_for_line()
            line.total_cost = total_cost
            line.is_total_cost_computed = computed

    @api.onchange("product_id", "qty")
    def _onchange_total_cost_conventional(self):
        """Cálculo en tiempo real para registros no guardados (nuevos pedidos)."""
        for line in self:
            total_cost, computed = line._get_total_cost_for_line()
            line.total_cost = total_cost
            line.is_total_cost_computed = computed
