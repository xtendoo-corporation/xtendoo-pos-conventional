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
        print("=" * 60)
        print("[PAYMENT] _compute_available_payment_methods called")
        for order in self:
            print(f"[PAYMENT]   order.id={order.id} session={order.session_id}")
            if order.session_id and order.session_id.config_id:
                methods = order.session_id.config_id.payment_method_ids
                print(f"[PAYMENT]   methods found: {[(m.id, m.name) for m in methods]}")
                order.available_payment_method_ids = methods
            else:
                print("[PAYMENT]   no session/config -> available_payment_method_ids = False")
                order.available_payment_method_ids = False

    def action_pay_cash(self):
        self.ensure_one()
        print("=" * 60)
        print(f"[PAYMENT] action_pay_cash called for order id={self.id} name={self.name}")
        print(f"[PAYMENT]   config_id={self.config_id.id} name={self.config_id.name}")
        print(f"[PAYMENT]   all payment methods: {[(m.id, m.name, m.journal_id.type) for m in self.config_id.payment_method_ids]}")

        cash_method = self.config_id.payment_method_ids.filtered('is_cash_count')[:1]
        print(f"[PAYMENT]   cash_method by is_cash_count: {cash_method} -> id={cash_method.id if cash_method else None} name={cash_method.name if cash_method else None}")

        if not cash_method:
            cash_method = self.config_id.payment_method_ids.filtered(lambda p: p.journal_id.type == 'cash')[:1]
            print(f"[PAYMENT]   cash_method by journal.type=cash: {cash_method} -> id={cash_method.id if cash_method else None} name={cash_method.name if cash_method else None}")

        if not cash_method:
            print("[PAYMENT]   ERROR: no cash method found, raising UserError")
            raise UserError(_("No se encontró método de pago en efectivo en la caja."))

        print(f"[PAYMENT]   -> opening wizard with cash_method id={cash_method.id} name={cash_method.name}")
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
        print("=" * 60)
        print(f"[PAYMENT] action_pay_card called for order id={self.id} name={self.name}")
        print(f"[PAYMENT]   all payment methods: {[(m.id, m.name, m.journal_id.type) for m in self.config_id.payment_method_ids]}")

        card_method = self.config_id.payment_method_ids.filtered(lambda p: p.journal_id.type == 'bank')[:1]
        print(f"[PAYMENT]   card_method by journal.type=bank: {card_method} -> id={card_method.id if card_method else None} name={card_method.name if card_method else None}")

        if not card_method:
            print("[PAYMENT]   ERROR: no card method found, raising UserError")
            raise UserError(_("No se encontró método de pago con tarjeta en la caja."))

        print(f"[PAYMENT]   -> calling action_pos_convention_pay_with_method with method id={card_method.id}")
        return self.action_pos_convention_pay_with_method(card_method)

    def action_pos_convention_pay_with_method(self, payment_method_id):
        self.ensure_one()
        print("=" * 60)
        print(f"[PAYMENT] action_pos_convention_pay_with_method called for order id={self.id}")
        print(f"[PAYMENT]   payment_method_id param={payment_method_id} type={type(payment_method_id)}")

        payment_method = payment_method_id
        if not hasattr(payment_method, "id"):
            print(f"[PAYMENT]   param is not a recordset, browsing id={payment_method_id}")
            try:
                payment_method = self.env["pos.payment.method"].browse(int(payment_method_id))
                print(f"[PAYMENT]   browsed -> id={payment_method.id} name={payment_method.name}")
            except (ValueError, TypeError) as e:
                print(f"[PAYMENT]   browse failed: {e} -> returning False")
                return False

        if not payment_method or not payment_method.exists():
            print("[PAYMENT]   payment_method does not exist -> returning False")
            return False

        name_lower = (payment_method.name or "").lower()
        print(f"[PAYMENT]   method: id={payment_method.id} name={payment_method.name} name_lower={name_lower}")
        print(f"[PAYMENT]   method attrs: type={getattr(payment_method, 'type', 'N/A')} is_cash_count={payment_method.is_cash_count} journal.type={payment_method.journal_id.type} use_payment_terminal={payment_method.use_payment_terminal}")

        is_cash = (
            getattr(payment_method, "type", False) == "cash"
            or payment_method.is_cash_count
            or payment_method.journal_id.type == "cash"
            or "efectivo" in name_lower
            or "cash" in name_lower
            or "caja" in name_lower
        )
        print(f"[PAYMENT]   is_cash={is_cash} (type==cash: {getattr(payment_method,'type',False)=='cash'}, is_cash_count: {payment_method.is_cash_count}, journal.type==cash: {payment_method.journal_id.type=='cash'}, nombre: {'efectivo' in name_lower or 'cash' in name_lower or 'caja' in name_lower})")

        if is_cash:
            print("[PAYMENT]   -> CASH branch: opening cash wizard")
            view = self.env.ref("pos_conventional_payment_wizard.view_pos_make_payment_wizard_cash_form", False)
            print(f"[PAYMENT]   view ref: {view}")
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
        print(f"[PAYMENT]   is_bank={is_bank} (type==bank: {getattr(payment_method,'type',False)=='bank'}, journal.type==bank: {payment_method.journal_id.type=='bank'}, use_payment_terminal: {payment_method.use_payment_terminal}, nombre: {'tarjeta' in name_lower or 'banco' in name_lower or 'card' in name_lower})")

        if not is_bank:
            print("[PAYMENT]   -> not cash, not bank -> returning False")
            return False

        amount_due = self.amount_total - self.amount_paid
        print(f"[PAYMENT]   -> BANK branch: amount_total={self.amount_total} amount_paid={self.amount_paid} amount_due={amount_due}")

        if amount_due <= 0:
            print("[PAYMENT]   ERROR: amount_due <= 0, raising UserError")
            raise UserError(_("El pedido ya está completamente pagado."))

        print(f"[PAYMENT]   -> calling pos.make.payment.check() with amount={amount_due} method={payment_method.id} card_payment=True")
        wizard = self.env["pos.make.payment"].with_context(active_id=self.id, card_payment=True).create({
            "amount": amount_due,
            "payment_method_id": payment_method.id,
        })
        return wizard.check()

    def action_open_payment_popup(self):
        self.ensure_one()
        print("=" * 60)
        print(f"[PAYMENT] action_open_payment_popup called for order id={self.id} name={self.name}")
        view = self.env.ref("pos_conventional_payment_wizard.view_pos_make_payment_wizard_form", False)
        print(f"[PAYMENT]   view ref: {view} id={view.id if view else None}")
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
        print("=" * 60)
        print(f"[PAYMENT] get_payment_popup_data called for order id={self.id} name={self.name}")
        self.flush_recordset()

        methods = []
        for pm in self.config_id.payment_method_ids:
            methods.append({
                'id': pm.id,
                'name': pm.name,
                'type': pm.type,
                'icon': "fa-money" if pm.journal_id.type == "cash" else "fa-credit-card",
            })
        print(f"[PAYMENT]   available methods: {[(m['id'], m['name'], m['type']) for m in methods]}")

        payments = []
        for p in self.payment_ids:
            payments.append({
                'id': p.id,
                'payment_method_id': p.payment_method_id.id,
                'payment_method_name': p.payment_method_id.name,
                'amount': p.amount,
            })
        print(f"[PAYMENT]   existing payments: {[(p['payment_method_name'], p['amount']) for p in payments]}")

        amount_due = self.amount_total - self.amount_paid
        print(f"[PAYMENT]   amount_total={self.amount_total} amount_paid={self.amount_paid} amount_due={amount_due}")
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
        print("=" * 60)
        print(f"[PAYMENT] add_payment_from_ui called: order id={self.id} payment_method_id={payment_method_id} amount={amount}")
        self.add_payment({
            'pos_order_id': self.id,
            'amount': float(amount),
            'payment_method_id': int(payment_method_id),
        })
        print(f"[PAYMENT]   payment added, refreshing popup data")
        return self.get_payment_popup_data()

    def remove_payment_from_ui(self, payment_id):
        self.ensure_one()
        print("=" * 60)
        print(f"[PAYMENT] remove_payment_from_ui called: order id={self.id} payment_id={payment_id}")
        payment = self.env['pos.payment'].browse(int(payment_id))
        if payment.exists() and payment.pos_order_id.id == self.id:
            print(f"[PAYMENT]   removing payment id={payment_id} method={payment.payment_method_id.name} amount={payment.amount}")
            payment.unlink()
        else:
            print(f"[PAYMENT]   payment id={payment_id} not found or does not belong to this order")
        return self.get_payment_popup_data()

    def action_register_payments_and_validate(self, payments, print_invoice=False):
        self.ensure_one()
        print("=" * 60)
        print(f"[PAYMENT] action_register_payments_and_validate called: order id={self.id} name={self.name}")
        print(f"[PAYMENT]   payments received: {payments}")
        print(f"[PAYMENT]   print_invoice={print_invoice}")

        self.payment_ids.unlink()
        print(f"[PAYMENT]   existing payments unlinked")

        for pay in payments:
            amount = float(pay.get('amount', 0))
            method_id = int(pay.get('payment_method_id'))
            print(f"[PAYMENT]   adding payment: method_id={method_id} amount={amount}")
            if amount != 0:
                self.add_payment({
                    'pos_order_id': self.id,
                    'payment_method_id': method_id,
                    'amount': amount,
                })
                print(f"[PAYMENT]   payment added ok")
            else:
                print(f"[PAYMENT]   amount=0, skipping")

        # Change management
        amount_paid = sum(self.payment_ids.mapped('amount'))
        print(f"[PAYMENT]   total amount_paid={amount_paid} amount_total={self.amount_total}")

        if amount_paid > self.amount_total:
            change = amount_paid - self.amount_total
            print(f"[PAYMENT]   change to return={change}")
            cash_method = self.config_id.payment_method_ids.filtered('is_cash_count')[:1]
            print(f"[PAYMENT]   cash_method for change: {cash_method} id={cash_method.id if cash_method else None}")
            if cash_method:
                self.add_payment({
                    'pos_order_id': self.id,
                    'amount': -change,
                    'payment_method_id': cash_method.id,
                    'is_change': True,
                })
                print(f"[PAYMENT]   change payment -{change} added with method {cash_method.name}")
        else:
            print(f"[PAYMENT]   no change needed")

        print(f"[PAYMENT]   -> calling action_validate_and_invoice()")
        return {'success': True, 'action': self.action_validate_and_invoice()}
