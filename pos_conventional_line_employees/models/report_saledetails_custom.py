from odoo import models


class ReportSaledetailsCustom(models.AbstractModel):
    _name = 'report.pos_conventional_line_employees.sale_custom'
    _inherit = 'report.point_of_sale.report_saledetails'
    # Hereda toda la lógica ya personalizada (employee_sales_grouped, pos_order_ids, etc.)
