from odoo import fields, models

class ResUsers(models.Model):
    _inherit = "res.users"

    allowed_pos_config_ids = fields.Many2many(
        'pos.config',
        'res_users_pos_config_rel',
        'user_id',
        'pos_config_id',
        string='Cajas permitidas (POS)',
        help='Cajas (puntos de venta) a las que el usuario puede acceder. Filtrado por las compañías asignadas al usuario.',
    )
