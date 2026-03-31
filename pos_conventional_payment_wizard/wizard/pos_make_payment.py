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
        """Resetear el importe recibido cuando cambia el método de pago"""
        if not self.is_cash_payment:
            self.amount_received = 0.0
        else:
            # Para efectivo, por defecto poner el importe exacto
            self.amount_received = self.amount

    def check(self, payment_method_id=None):
        """
        Permite forzar el método de pago si se pasa como argumento.
        """
        self.ensure_one()
        print("=" * 60)
        print("[MAKE_PAYMENT] check() called")

        order = self.env["pos.order"].browse(self.env.context.get("active_id", False))
        is_card = self.env.context.get("card_payment", False)
        print(f"[MAKE_PAYMENT]   order={order.id} name={order.name} state={order.state}")
        print(f"[MAKE_PAYMENT]   is_card={is_card}")

        if payment_method_id:
            self.payment_method_id = payment_method_id

        print(f"[MAKE_PAYMENT]   payment_method={self.payment_method_id.name} id={self.payment_method_id.id}")

        if self.payment_method_id.split_transactions and not order.partner_id:
            raise UserError(_("Customer is required for %s payment method.", self.payment_method_id.name))

        currency = order.currency_id
        is_conventional = order.config_id and order.config_id.pos_non_touch
        print(f"[MAKE_PAYMENT]   is_conventional={is_conventional}")

        init_data = self.read()[0]
        payment_method = self.env["pos.payment.method"].browse(init_data["payment_method_id"][0])

        if not float_is_zero(init_data["amount"], precision_rounding=currency.rounding):
            amount = order._get_rounded_amount(
                init_data["amount"],
                payment_method.is_cash_count or not order.config_id.only_round_cash_method,
            )
            print(f"[MAKE_PAYMENT]   adding payment: amount={amount} method={payment_method.name}")
            order.add_payment({
                "pos_order_id": order.id,
                "amount": amount,
                "name": init_data["payment_name"],
                "payment_method_id": init_data["payment_method_id"][0],
            })

        print(f"[MAKE_PAYMENT]   _is_pos_order_paid={order._is_pos_order_paid()} state={order.state}")

        if order.state == "draft" and order._is_pos_order_paid():
            order._process_saved_order(False)
            print(f"[MAKE_PAYMENT]   after _process_saved_order: state={order.state}")

            if order.state in {"paid", "done"}:
                order._send_order()
                order.config_id.notify_synchronisation(order.config_id.current_session_id.id, 0)

            if is_conventional and order.state in {"paid", "done"} and not order.account_move:
                print("[MAKE_PAYMENT]   -> calling action_validate_and_invoice()")
                try:
                    result = order.action_validate_and_invoice()
                    print(f"[MAKE_PAYMENT]   action_validate_and_invoice returned: type={type(result)} value={result}")
                    if result and isinstance(result, dict) and result.get("type"):
                        params = result.get("params", {})
                        if not params.get("next_action"):
                            result.setdefault("params", {})["next_action"] = {
                                "type": "ir.actions.client",
                                "tag": "pos_conventional_new_order",
                                "params": {
                                    "config_id": order.config_id.id,
                                    "default_session_id": order.config_id.current_session_id.id,
                                    "ask_new_order": is_card,
                                },
                            }
                        print(f"[MAKE_PAYMENT]   returning result: {result.get('type')} tag={result.get('tag','')}")
                        return result
                except Exception as exc:
                    _logger.exception(
                        "Error al facturar automáticamente el pedido %s: %s",
                        order.name, str(exc),
                    )
                    print(f"[MAKE_PAYMENT]   ERROR in action_validate_and_invoice: {exc}")

                # FALLBACK: action_validate_and_invoice devolvió False o falló → navegar a nuevo pedido
                print(f"[MAKE_PAYMENT]   FALLBACK -> pos_conventional_new_order ask_new_order={is_card}")
                return {
                    "type": "ir.actions.client",
                    "tag": "pos_conventional_new_order",
                    "params": {
                        "config_id": order.config_id.id,
                        "default_session_id": order.config_id.current_session_id.id,
                        "ask_new_order": is_card,
                    },
                }

            elif is_conventional and order.state in {"paid", "done"}:
                print(f"[MAKE_PAYMENT]   -> pos_conventional_new_order (elif) ask_new_order={is_card}")
                return {
                    "type": "ir.actions.client",
                    "tag": "pos_conventional_new_order",
                    "params": {
                        "config_id": order.config_id.id,
                        "default_session_id": order.config_id.current_session_id.id,
                        "ask_new_order": is_card,
                    },
                }

            print("[MAKE_PAYMENT]   -> act_window_close (not conventional or not paid)")
            return {"type": "ir.actions.act_window_close"}

        print("[MAKE_PAYMENT]   -> calling launch_payment() (order not paid)")
        return self.launch_payment()

    def action_pay_cash(self):
        cash_method = self.env["pos.payment.method"].search(
            [("is_cash_count", "=", True)], limit=1
        )
        if not cash_method:
            raise UserError(_("No se encontró método de pago en efectivo."))
        return self.check(payment_method_id=cash_method.id)

    def action_pay_card(self):
        card_method = self.env["pos.payment.method"].search(
            [("name", "ilike", "tarjeta")], limit=1
        )
        if not card_method:
            raise UserError(_("No se encontró método de pago con tarjeta."))
        return self.check(payment_method_id=card_method.id)

    def action_pay_account(self):
        account_method = self.env["pos.payment.method"].search(
            [("name", "ilike", "cuenta")], limit=1
        )
        if not account_method:
            raise UserError(_("No se encontró un método de pago tipo Cuenta."))
        return self.check(payment_method_id=account_method.id)
