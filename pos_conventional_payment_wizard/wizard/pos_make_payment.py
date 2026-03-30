from odoo import api, fields, models, _
from odoo.tools import float_is_zero
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class PosMakePaymentConventional(models.TransientModel):
    _inherit = "pos.make.payment"

    amount_received = fields.Float(
        string="Importe recibido",
        digits=0,
        help="Importe recibido del cliente (solo para efectivo)",
    )
    amount_change = fields.Float(
        string="Cambio",
        digits=0,
        compute="_compute_amount_change",
        store=False,
        help="Cambio a devolver al cliente",
    )
    is_cash_payment = fields.Boolean(
        string="Es pago en efectivo", compute="_compute_is_cash_payment", store=False
    )

    @api.depends("payment_method_id")
    def _compute_is_cash_payment(self):
        for record in self:
            record.is_cash_payment = (
                record.payment_method_id.is_cash_count
                if record.payment_method_id
                else False
            )

    @api.depends("amount_received", "amount", "is_cash_payment")
    def _compute_amount_change(self):
        for record in self:
            if record.is_cash_payment and record.amount_received > 0:
                record.amount_change = record.amount_received - record.amount
            else:
                record.amount_change = 0.0

    @api.onchange("payment_method_id")
    def _onchange_payment_method_id(self):
        if not self.is_cash_payment:
            self.amount_received = 0.0
        else:
            self.amount_received = self.amount

    def check(self, payment_method_id=None):
        self.ensure_one()
        order = self.env["pos.order"].browse(self.env.context.get("active_id", False))

        if payment_method_id:
            self.payment_method_id = payment_method_id

        if self.payment_method_id.split_transactions and not order.partner_id:
            raise UserError(_("Customer is required for %s payment method.", self.payment_method_id.name))

        currency = order.currency_id
        is_conventional = order.config_id and order.config_id.pos_non_touch
        init_data = self.read()[0]
        payment_method = self.env["pos.payment.method"].browse(init_data["payment_method_id"][0])

        if not float_is_zero(init_data["amount"], precision_rounding=currency.rounding):
            order.add_payment({
                "pos_order_id": order.id,
                "amount": order._get_rounded_amount(
                    init_data["amount"],
                    payment_method.is_cash_count or not order.config_id.only_round_cash_method,
                ),
                "name": init_data["payment_name"],
                "payment_method_id": init_data["payment_method_id"][0],
            })

        if order.state == "draft" and order._is_pos_order_paid():
            order._process_saved_order(False)
            if order.state in {"paid", "done"}:
                order._send_order()
                order.config_id.notify_synchronisation(order.config_id.current_session_id.id, 0)

            if is_conventional and order.state in {"paid", "done"}:
                return {
                    "type": "ir.actions.client",
                    "tag": "pos_conventional_new_order",
                    "params": {
                        "config_id": order.config_id.id,
                        "session_id": order.config_id.current_session_id.id,
                    },
                }
            return {"type": "ir.actions.act_window_close"}

        return super().check()
