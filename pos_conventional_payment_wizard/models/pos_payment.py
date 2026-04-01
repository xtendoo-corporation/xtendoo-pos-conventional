from odoo import models, _


class PosPayment(models.Model):
    _inherit = "pos.payment"

    def action_remove_from_pos_wizard(self):
        """Elimina este pago y mantiene el wizard abierto con los datos actualizados.

        Se llama desde el botón de la lista de pagos en pos.make.payment.wizard.
        En lugar de devolver True (que cierra el diálogo), crea un nuevo wizard
        para el mismo pedido y devuelve su acción, igual que _add_payment.
        """
        self.ensure_one()
        order = self.pos_order_id
        self.unlink()

        wizard = self.env["pos.make.payment.wizard"].with_context(
            active_id=order.id
        ).create({"order_id": order.id})

        return {
            "type": "ir.actions.act_window",
            "res_model": "pos.make.payment.wizard",
            "res_id": wizard.id,
            "view_mode": "form",
            "view_id": wizard._get_wizard_view_id(),
            "target": "new",
            "context": {"active_id": order.id},
        }

