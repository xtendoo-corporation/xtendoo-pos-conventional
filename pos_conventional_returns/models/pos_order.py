from odoo import api, models
from odoo.exceptions import UserError
from odoo.tools.translate import _


class PosOrder(models.Model):
    _inherit = "pos.order"

    def _refund(self):
        return super(PosOrder, self.with_context(skip_completeness_check=True))._refund()

    def refund(self):
        non_refundable = self.filtered(lambda order: not order.has_refundable_lines)
        if non_refundable:
            raise UserError(
                _(
                    "El pedido «%s» no tiene líneas disponibles para devolver.",
                    non_refundable[0].name or "",
                )
            )
        return super().refund()

    @api.model
    def action_open_conventional_returns(self):
        session_id = self.env.context.get("default_session_id") or self.env.context.get("session_id")
        if not session_id and self.env.context.get("active_model") == "pos.order" and self.env.context.get("active_id"):
            active_order = self.env["pos.order"].browse(self.env.context["active_id"]).exists()
            session_ids = active_order.mapped("session_id.id") if active_order else []
            session_id = session_ids[0] if session_ids else False

        session_id = int(session_id) if session_id else False

        session = self.env["pos.session"].browse(session_id).exists()
        if not session:
            raise UserError(_("No se ha podido determinar la caja/sesión activa para gestionar devoluciones."))

        config_ids = session.mapped("config_id.id")
        config_id = config_ids[0] if config_ids else False
        if not config_id:
            raise UserError(_("La sesión seleccionada no tiene una configuración de TPV válida."))

        action = self.env.ref("point_of_sale.action_pos_pos_form").read()[0]
        action.update({
            "name": _("Devoluciones"),
            "domain": [
                ("config_id", "=", config_id),
                ("state", "not in", ["draft", "cancel"]),
            ],
            "context": {
                "default_session_id": session.id,
                "search_default_posted": 1,
                "conventional_returns_mode": True,
                "pos_conventional_returns_session_id": session.id,
                "pos_conventional_returns_config_id": config_id,
            },
        })
        return action

