from collections import defaultdict

from odoo import api, fields, models


class PosOrderEmployees(models.Model):
    _inherit = "pos.order"

    employees_summary = fields.Char(
        string="Employees Summary",
        compute="_compute_employees_summary",
        store=True,
    )

    @api.depends("lines.employee_ids", "lines.price_subtotal")
    def _compute_employees_summary(self):
        for order in self:
            if not order.lines:
                order.employees_summary = ""
                continue
            # accumulate per employee id
            accum = defaultdict(float)
            currency = order.currency_id or order.company_id.currency_id
            for line in order.lines:
                # compute total for line (price_subtotal if present)
                try:
                    line_total = float(line.price_subtotal or 0.0)
                except Exception:
                    line_total = float((line.qty or 0.0) * (line.price_unit or 0.0) * (1.0 - (line.discount or 0.0) / 100.0))
                n = len(line.employee_ids or [])
                if n:
                    per = line_total / n
                    for emp in line.employee_ids:
                        accum[emp.id] += per
                else:
                    # No employees on this line: attribute to a special key 0
                    accum[0] += line_total

            parts = []
            # if there is a generic amount (no employee), show it first
            if accum.get(0.0):
                parts.append("Unassigned: %s" % (currency._format_amount(accum[0.0]) if hasattr(currency, '_format_amount') else "%.2f" % accum[0.0]))
            # map ids to names
            employees = self.env["hr.employee"].browse([k for k in accum.keys() if k])
            for emp in employees:
                amt = accum.get(emp.id, 0.0)
                # format amount with currency symbol (fallback simple)
                try:
                    formatted = currency and currency.symbol + "%.2f" % round(amt, 2) or "%.2f" % round(amt, 2)
                except Exception:
                    formatted = "%.2f" % round(amt, 2)
                parts.append(f"{emp.name}: {formatted}")

            order.employees_summary = "; ".join(parts)
