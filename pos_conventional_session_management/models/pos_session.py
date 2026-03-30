from odoo import api, fields, models, _

class PosSession(models.Model):
    _inherit = "pos.session"

    @api.model_create_multi
    def create(self, vals_list):
        """
        Hereda el saldo final de la última sesión cerrada como saldo inicial.
        """
        for vals in vals_list:
            if 'config_id' in vals and 'cash_register_balance_start' not in vals:
                config = self.env['pos.config'].browse(vals['config_id'])
                if config.cash_control:
                    last_session = self.search([
                        ('config_id', '=', config.id),
                        ('state', '=', 'closed')
                    ], order='id desc', limit=1)
                    if last_session:
                        vals['cash_register_balance_start'] = last_session.cash_register_balance_end_real
        return super().create(vals_list)

    def action_pos_session_open(self):
        """
        Intercepta la apertura de sesión para mostrar el popup OWL en modo no táctil.
        """
        if self.env.context.get("skip_auto_open"):
            return True

        non_touch_sessions = self.filtered(
            lambda s: s.config_id.pos_non_touch and s.state == "opening_control"
        )
        
        if non_touch_sessions:
            # En lugar de abrir la UI, abrir el wizard de apertura
            return {
                "type": "ir.actions.client",
                "tag": "pos_conventional_opening_popup",
                "name": _("Control de apertura"),
                "target": "new",
                "context": {
                    "session_id": self.id,
                    "config_id": self.config_id.id,
                },
            }

        return super().action_pos_session_open()
