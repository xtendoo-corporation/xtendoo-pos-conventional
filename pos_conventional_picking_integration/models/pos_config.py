from odoo import fields, models

class PosConfig(models.Model):
    _inherit = "pos.config"

    pos_enable_albaran = fields.Boolean(
        string="Albarán desde el POS",
        help="Permite crear albaranes desde el POS.",
    )
