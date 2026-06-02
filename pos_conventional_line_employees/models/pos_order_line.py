from odoo import api, fields, models


class PosOrderLineEmployee(models.Model):
    _inherit = "pos.order.line"

    employee_ids = fields.Many2many(
        "hr.employee",
        string="Empleado/s",
        relation="pos_order_line_hr_employee_rel",
        column1="pos_order_line_id",
        column2="hr_employee_id",
    )

    @api.model
    def _load_pos_data_fields(self, config):
        """Ensure `employee_ids` is included when POS frontend requests pos.order.line data."""
        fields = super()._load_pos_data_fields(config) or []
        if "employee_ids" not in fields:
            fields = fields + ["employee_ids"]
        return fields
