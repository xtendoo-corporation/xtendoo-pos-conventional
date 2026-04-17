from odoo import models, _


class PosConfig(models.Model):
    _inherit = "pos.config"

    def _get_non_touch_opening_action(self, session):
        self.ensure_one()
        return {
            "type": "ir.actions.client",
            "tag": "pos_conventional_opening_popup",
            "name": _("Control de apertura"),
            "target": "current",
            "context": {
                "session_id": session.id,
                "config_id": self.id,
            },
        }

