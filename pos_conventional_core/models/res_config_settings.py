from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    pos_non_touch = fields.Boolean(
        related="pos_config_id.pos_non_touch",
        readonly=False,
    )

    has_open_pos_sessions = fields.Selection(
        related="pos_config_id.has_open_session",
        readonly=True,
    )
