from odoo import fields, models

class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    pos_force_employee_login_after_order = fields.Boolean(
        related="pos_config_id.pos_force_employee_login_after_order",
        readonly=False,
        string="Pedir PIN del usuario",
        help="Si está activo, pedirá el PIN del usuario después de cada venta y cambiará el usuario de la sesión.",
    )
