from odoo import api, fields, models
from odoo.exceptions import UserError

class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    pos_non_touch = fields.Boolean(
        related="pos_config_id.pos_non_touch",
        readonly=False,
        string="POS no táctil",
    )

    pos_default_partner_id = fields.Many2one(
        "res.partner",
        related="pos_config_id.default_partner_id",
        readonly=False,
        string="Cliente por Defecto",
        help="Cliente que se asignará automáticamente a los nuevos pedidos creados desde el backend.",
        domain="[('customer_rank', '>', 0)]",
    )

    has_open_pos_sessions = fields.Boolean(
        string="Tiene sesiones POS abiertas",
        compute="_compute_has_open_pos_sessions",
        readonly=True,
    )

    @api.depends("pos_config_id")
    def _compute_has_open_pos_sessions(self):
        for settings in self:
            if not settings.pos_config_id:
                settings.has_open_pos_sessions = False
                continue
            open_sessions_count = self.env["pos.session"].search_count([
                ("config_id", "=", settings.pos_config_id.id),
                ("state", "!=", "closed"),
            ])
            settings.has_open_pos_sessions = open_sessions_count > 0

    def write(self, vals):
        """Interceptar escritura para bloquear cambio de modo con sesión abierta."""
        if 'pos_non_touch' in vals:
            for record in self:
                if not record.pos_config_id:
                    continue
                has_open = self.env["pos.session"].search_count([
                    ("config_id", "=", record.pos_config_id.id),
                    ("state", "!=", "closed"),
                ]) > 0
                if has_open:
                    current = bool(record.pos_config_id.pos_non_touch)
                    new_val = bool(vals['pos_non_touch'])
                    if current != new_val:
                        raise UserError(
                            "No se puede cambiar el modo táctil/no táctil mientras existan sesiones POS abiertas."
                        )
        return super().write(vals)

    def set_values(self):
        for record in self:
            if not record.pos_config_id:
                continue
            has_open = self.env["pos.session"].search_count([
                ("config_id", "=", record.pos_config_id.id),
                ("state", "!=", "closed"),
            ]) > 0
            if has_open:
                current = bool(record.pos_config_id.pos_non_touch)
                new = bool(record.pos_non_touch)
                if current != new:
                    raise UserError(
                        "No se puede cambiar el modo táctil/no táctil mientras existan sesiones POS abiertas."
                    )
        return super().set_values()
