from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)

class PosOrder(models.Model):
    _inherit = "pos.order"

    available_payment_method_ids = fields.Many2many(
        "pos.payment.method",
        compute="_compute_available_payment_methods",
        string="Métodos de pago disponibles",
        help="Métodos de pago configurados para el punto de venta de esta sesión",
    )

    @api.depends("session_id.config_id.payment_method_ids")
    def _compute_available_payment_methods(self):
        for order in self:
            if order.session_id and order.session_id.config_id:
                order.available_payment_method_ids = order.session_id.config_id.payment_method_ids
            else:
                order.available_payment_method_ids = False

    def action_pay_cash(self):
        self.ensure_one()
        cash_method = self.config_id.payment_method_ids.filtered('is_cash_count')[:1]
        if not cash_method:
            cash_method = self.config_id.payment_method_ids.filtered(lambda p: p.journal_id.type == 'cash')[:1]

        if not cash_method:
            raise UserError(_("No se encontró método de pago en efectivo en la caja."))

        return {
            "type": "ir.actions.act_window",
            "res_model": "pos.make.payment.wizard",
            "name": _("Pago en Efectivo"),
            "view_mode": "form",
            "target": "new",
            "context": {
                "active_id": self.id,
                "default_payment_method_id": cash_method.id,
                "cash_only": True,
            },
        }

    def action_pay_card(self):
        self.ensure_one()
        card_method = self.config_id.payment_method_ids.filtered(lambda p: p.journal_id.type == 'bank')[:1]
        if not card_method:
            raise UserError(_("No se encontró método de pago con tarjeta en la caja."))
        return self.action_pos_convention_pay_with_method(card_method)

    def action_pos_convention_pay_with_method(self, payment_method_id):
        self.ensure_one()
        payment_method = payment_method_id
        if not hasattr(payment_method, "id"):
            try:
                payment_method = self.env["pos.payment.method"].browse(int(payment_method_id))
            except (ValueError, TypeError):
                return False

        if not payment_method or not payment_method.exists():
            return False

        name_lower = (payment_method.name or "").lower()
        is_cash = (
            getattr(payment_method, "type", False) == "cash"
            or payment_method.is_cash_count
            or payment_method.journal_id.type == "cash"
            or "efectivo" in name_lower
            or "cash" in name_lower
            or "caja" in name_lower
        )

        if is_cash:
            view = self.env.ref("pos_conventional_payment_wizard.view_pos_make_payment_wizard_cash_form", False)
            return {
                "type": "ir.actions.act_window",
                "res_model": "pos.make.payment.wizard",
                "name": _("Cobro en Efectivo"),
                "view_mode": "form",
                "views": [[view.id if view else False, "form"]],
                "target": "new",
                "context": {
                    "active_id": self.id,
                    "default_payment_method_id": payment_method.id,
                    "cash_only": True,
                },
            }

        is_bank = (
            getattr(payment_method, "type", False) == "bank"
            or payment_method.journal_id.type == "bank"
            or payment_method.use_payment_terminal
            or "tarjeta" in name_lower
            or "banco" in name_lower
            or "card" in name_lower
        )

        if not is_bank:
            return False

        amount_due = self.amount_total - self.amount_paid
        if amount_due <= 0:
            raise UserError(_("El pedido ya está completamente pagado."))

        wizard = self.env["pos.make.payment"].with_context(active_id=self.id).create({
            "amount": amount_due,
            "payment_method_id": payment_method.id,
        })
        return wizard.check()

    def action_open_payment_popup(self):
        self.ensure_one()
        view = self.env.ref("pos_conventional_payment_wizard.view_pos_make_payment_wizard_form", False)
        return {
            "type": "ir.actions.act_window",
            "res_model": "pos.make.payment.wizard",
            "name": _("Realizar Pago"),
            "view_mode": "form",
            "views": [[view.id if view else False, "form"]],
            "target": "new",
            "context": {
                "active_id": self.id,
            },
        }

    def get_payment_popup_data(self):
        self.ensure_one()
        self.flush_recordset()

        methods = []
        for pm in self.config_id.payment_method_ids:
            methods.append({
                'id': pm.id,
                'name': pm.name,
                'type': pm.type,
                'icon': "fa-money" if pm.journal_id.type == "cash" else "fa-credit-card",
            })

        payments = []
        for p in self.payment_ids:
            payments.append({
                'id': p.id,
                'payment_method_id': p.payment_method_id.id,
                'payment_method_name': p.payment_method_id.name,
                'amount': p.amount,
            })

        amount_due = self.amount_total - self.amount_paid
        return {
            'order_id': self.id,
            'amount_total': self.amount_total,
            'amount_paid': self.amount_paid,
            'amount_due': round(amount_due, self.currency_id.decimal_places),
            'currency_symbol': self.currency_id.symbol,
            'available_methods': methods,
            'payments': payments,
        }

    def add_payment_from_ui(self, payment_method_id, amount):
        self.ensure_one()
        self.add_payment({
            'pos_order_id': self.id,
            'amount': float(amount),
            'payment_method_id': int(payment_method_id),
        })
        return self.get_payment_popup_data()

    def remove_payment_from_ui(self, payment_id):
        self.ensure_one()
        payment = self.env['pos.payment'].browse(int(payment_id))
        if payment.exists() and payment.pos_order_id.id == self.id:
            payment.unlink()
        return self.get_payment_popup_data()

    def action_register_payments_and_validate(self, payments, print_invoice=False):
        self.ensure_one()
        self.payment_ids.unlink()
        for pay in payments:
            amount = float(pay.get('amount', 0))
            if amount != 0:
                self.add_payment({
                    'pos_order_id': self.id,
                    'payment_method_id': int(pay.get('payment_method_id')),
                    'amount': amount,
                })

        # Change management
        amount_paid = sum(self.payment_ids.mapped('amount'))
        if amount_paid > self.amount_total:
            change = amount_paid - self.amount_total
            cash_method = self.config_id.payment_method_ids.filtered('is_cash_count')[:1]
            if cash_method:
                self.add_payment({
                    'pos_order_id': self.id,
                    'amount': -change,
                    'payment_method_id': cash_method.id,
                    'is_change': True,
                })

        return {'success': True, 'action': self.action_validate_and_invoice()}
