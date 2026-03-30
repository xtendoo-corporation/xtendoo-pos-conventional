from odoo import fields, models, _


class PosConfig(models.Model):
    _inherit = "pos.config"

    pos_force_employee_login_after_order = fields.Boolean(
        string="Pedir PIN del usuario",
        default=False,
        help="Si está activo, pedirá el PIN del usuario después de cada venta y cambiará el usuario de la sesión.",
    )

    def open_ui(self):
        self.ensure_one()
        if self.pos_non_touch:
            session = self.current_session_id
            if session and session.state == "opening_control":
                if self.pos_force_employee_login_after_order:
                    return {
                        "type": "ir.actions.act_window",
                        "res_model": "pos.session.pin.wizard",
                        "view_mode": "form",
                        "target": "new",
                        "context": {
                            "default_session_id": session.id,
                            "default_user_id": self.env.uid,
                        },
                    }
        return super().open_ui()
