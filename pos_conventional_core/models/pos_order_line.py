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

    @api.depends(
        "product_id",
        "qty",
        "order_id.currency_id",
        "order_id.company_id",
        "order_id.date_order",
    )
    def _compute_total_cost_conventional(self):
        for line in self:
            product = line.product_id
            if not product:
                line.total_cost = 0.0
                line.is_total_cost_computed = False
                continue
            cost_currency = product.sudo().cost_currency_id
            order = line.order_id
            currency = order.currency_id or self.env.company.currency_id
            company = order.company_id or self.env.company
            date = (order.date_order.date() if order.date_order else None) or fields.Date.today()
            try:
                line.total_cost = line.qty * cost_currency._convert(
                    from_amount=product.standard_price,
                    to_currency=currency,
                    company=company,
                    date=date,
                    round=False,
                )
            except Exception:
                line.total_cost = line.qty * product.standard_price
            line.is_total_cost_computed = True
