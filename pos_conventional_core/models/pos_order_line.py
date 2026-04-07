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

    # Override para añadir inverse: cuando la vista escribe tax_ids_after_fiscal_position
    # (campo computed que Odoo 19 puede enviar al guardar el formulario),
    # sincronizamos tax_ids para que los impuestos no se pierdan.
    tax_ids_after_fiscal_position = fields.Many2many(
        "account.tax",
        compute="_get_tax_ids_after_fiscal_position",
        inverse="_inverse_tax_ids_after_fiscal_position",
        string="Taxes to Apply",
    )

    def _inverse_tax_ids_after_fiscal_position(self):
        """Sincroniza tax_ids cuando tax_ids_after_fiscal_position se escribe desde la vista.

        En Odoo 19, el cliente OWL envía el campo visible (tax_ids_after_fiscal_position)
        al guardar el formulario. Sin un inverse, ese write se ignora silenciosamente y
        tax_ids queda vacío si no se envía por separado. Este inverse lo propaga.
        """
        for line in self:
            # Si no hay posición fiscal, los taxes after FP SON los tax_ids
            if not line.order_id.fiscal_position_id:
                if line.tax_ids_after_fiscal_position != line.tax_ids:
                    line.tax_ids = line.tax_ids_after_fiscal_position
            # Con posición fiscal, no invertimos automáticamente para no
            # romper el mapeo del registro original.

    def write(self, vals):
        """Garantiza que tax_ids no quede vacío si la vista sólo envía
        tax_ids_after_fiscal_position (campo visible en el formulario)."""
        # Si el write incluye tax_ids_after_fiscal_position pero NO tax_ids,
        # y la línea ya tiene tax_ids guardados, los preservamos.
        # (El inverse se encarga del caso donde sí llega tax_ids_after_fiscal_position.)
        result = super().write(vals)
        # Tras el write, si tax_ids quedó vacío pero el producto tiene impuestos,
        # restauramos los impuestos del producto filtrados por compañía.
        for line in self:
            if not line.tax_ids and line.product_id:
                product_taxes = line.product_id.taxes_id.filtered(
                    lambda t: t.company_id == (line.order_id.company_id or self.env.company)
                )
                if product_taxes:
                    _logger.debug(
                        "PosOrderLine %s: tax_ids vacío tras write, restaurando desde producto %s",
                        line.id,
                        line.product_id.name,
                    )
                    super(PosOrderLine, line).write({"tax_ids": [(6, 0, product_taxes.ids)]})
        return result

    def _get_total_cost_for_line(self):
        """Calcula total_cost para una línea usando el coste estándar del producto."""
        self.ensure_one()
        product = self.product_id
        if not product:
            return 0.0, False
        order = self.order_id
        currency = order.currency_id or self.env.company.currency_id
        company = order.company_id or self.env.company
        date = (order.date_order.date() if order.date_order else None) or fields.Date.today()
        standard_price = product.sudo().standard_price
        cost_currency = product.sudo().cost_currency_id
        try:
            if cost_currency and cost_currency != currency:
                total_cost = self.qty * cost_currency._convert(
                    from_amount=standard_price,
                    to_currency=currency,
                    company=company,
                    date=date,
                    round=False,
                )
            else:
                # Misma moneda o sin moneda de coste: usar el precio directamente
                total_cost = self.qty * standard_price
        except Exception:
            total_cost = self.qty * standard_price
        return total_cost, True

    @api.model_create_multi
    def create(self, vals_list):
        """Re-run cost compute after creation.

        In Odoo 19, stored computed fields triggered by @api.depends may run
        before all Many2one fields are fully resolved in the ORM cache, causing
        product_id to appear empty. Re-running the compute after super().create()
        guarantees correct values are stored in the DB.
        """
        lines = super().create(vals_list)
        lines._compute_total_cost_conventional()
        return lines

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
