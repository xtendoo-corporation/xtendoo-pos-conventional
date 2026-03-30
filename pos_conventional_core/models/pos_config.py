from odoo import fields, models, _


class PosConfig(models.Model):
    _inherit = "pos.config"

    pos_non_touch = fields.Boolean(
        string="POS no táctil",
        default=False,
        help="Activa un modo de punto de venta optimizado para equipos sin pantalla táctil.",
    )

    default_partner_id = fields.Many2one(
        "res.partner",
        string="Cliente por Defecto",
        help="Cliente que se asignará automáticamente a los nuevos pedidos POS creados desde el backend.",
        domain="[('customer_rank', '>', 0)]",
    )

    def open_ui(self):
        """
        Override del método open_ui para interceptar la apertura
        cuando pos_non_touch está activo.
        """
        self.ensure_one()

        if self.pos_non_touch:
            if not self.current_session_id:
                res = self._check_before_creating_new_session()
                if res:
                    return res
                self.env["pos.session"].with_context(skip_auto_open=True).create({
                    "user_id": self.env.uid,
                    "config_id": self.id
                })
            
            session = self.current_session_id
            if session.state in ["opened", "closing_control"]:
                return self._redirect_to_pos_orders(session)
            
            # Cases for other states (opening_control) will be handled by other modules
            # such as pos_conventional_session_management or pos_conventional_users_pin

        return super(PosConfig, self).open_ui()

    def _redirect_to_pos_orders(self, session):
        self.ensure_one()
        config_sessions = self.env["pos.session"].search([
            ("config_id", "=", session.config_id.id)
        ])
        action = self.env.ref("point_of_sale.action_pos_pos_form").read()[0]
        action["domain"] = [("session_id", "in", config_sessions.ids)]
        action["context"] = {
            "default_session_id": session.id,
        }
        return action
