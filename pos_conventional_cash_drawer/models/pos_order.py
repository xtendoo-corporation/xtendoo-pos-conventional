from odoo import models
from odoo.exceptions import UserError
from odoo.tools.translate import _


class PosOrder(models.Model):
    _inherit = "pos.order"

    def action_open_cash_drawer_from_conventional(self):
        self.ensure_one()
        if not self.config_id:
            raise UserError(
                _(
                    "No se pudo identificar la configuración del TPV para abrir el cajón."
                )
            )
        return self.config_id.action_test_cash_drawer()


