from odoo import api, fields, models

class PosDetails(models.TransientModel):
    _inherit = 'pos.details.wizard'


    pos_order_ids = fields.Many2many(
        'pos.order',
        string='Pedidos',
        help='Seleccione pedidos específicos para incluirlos en el informe.'
    )

    def generate_report(self):
        data = {
            'date_start': self.start_date,
            'date_stop': self.end_date,
            'config_ids': self.pos_config_ids.ids,
            'pos_order_ids': self.pos_order_ids.ids,
        }
        return self.env.ref(
            'pos_conventional_line_employees.sale_details_custom_report'
        ).report_action([], data=data)
