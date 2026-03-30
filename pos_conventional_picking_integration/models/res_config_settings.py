from odoo import fields, models

class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    pos_enable_albaran = fields.Boolean(
        related="pos_config_id.pos_enable_albaran",
        readonly=False,
        string="Albarán desde el POS",
        help="Permite crear albaranes desde el POS.",
    )
