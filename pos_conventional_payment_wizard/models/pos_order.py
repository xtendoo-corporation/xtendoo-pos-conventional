import logging

from odoo import models
from odoo.exceptions import UserError
from odoo.tools import float_is_zero
from odoo.tools.translate import _

_logger = logging.getLogger(__name__)


class PosOrder(models.Model):
    _inherit = "pos.order"

    def _get_previous_sale_banner_params(self):
        """Datos a mostrar en la siguiente venta como resumen de la operación anterior."""
        self.ensure_one()

        currency = self.currency_id or self.session_id.currency_id or self.env.company.currency_id
        round_amount = currency.round if currency else lambda amount: round(amount, 2)

        change_amount = 0.0
        if self.amount_total > 0:
            negative_payments = self.payment_ids.filtered(lambda payment: payment.amount < -0.005)
            if negative_payments:
                change_amount = abs(sum(negative_payments.mapped("amount")))
            elif getattr(self, "amount_return", 0.0) > 0:
                change_amount = self.amount_return

        return {
            "previous_sale_total": round_amount(self.amount_total),
            "previous_sale_change": round_amount(change_amount),
            "previous_sale_currency": currency.symbol if currency and currency.symbol else "€",
        }

    def _is_negative_payment_flow(self):
        self.ensure_one()
        return self.amount_total < 0 or bool(getattr(self, "is_refund", False))

    def _action_standard_payment_wizard(self, payment_method=None):
        self.ensure_one()
        wizard_vals = {}
        if payment_method:
            wizard_vals["payment_method_id"] = payment_method.id
        wizard = self.env["pos.make.payment"].with_context(
            **dict(self.env.context, active_id=self.id)
        ).create(wizard_vals)
        return wizard.check()

    def action_pay_cash(self):
        self.ensure_one()
        if float_is_zero(self.amount_total, precision_rounding=self.currency_id.rounding):
            raise UserError(
                _("No se puede cobrar un pedido con importe cero. Por favor, añada productos.")
            )

        cash_method = self.config_id.payment_method_ids.filtered("is_cash_count")[:1]
        if not cash_method:
            cash_method = self.config_id.payment_method_ids.filtered(
                lambda p: p.journal_id.type == "cash"
            )[:1]
        if not cash_method:
            raise UserError(_("No se encontró método de pago en efectivo para este TPV."))

        if self._is_negative_payment_flow():
            return self._action_standard_payment_wizard(cash_method)

        view = self.env.ref(
            "pos_conventional_payment_wizard.view_pos_make_payment_wizard_cash_form",
            False,
        )
        return {
            "type": "ir.actions.act_window",
            "res_model": "pos.make.payment.wizard",
            "name": _("Cash Payment"),
            "view_mode": "form",
            "views": [[view.id if view else False, "form"]],
            "target": "new",
            "context": {
                "active_id": self.id,
                "default_payment_method_id": cash_method.id,
                "default_amount_tendered": self.amount_total,
                "cash_only": True,
                "cash_quick_mode": True,
            },
        }

    def action_pay_card(self):
        self.ensure_one()
        if float_is_zero(self.amount_total, precision_rounding=self.currency_id.rounding):
            raise UserError(
                _("No se puede cobrar un pedido con importe cero. Por favor, añada productos.")
            )

        card_method = self.config_id.payment_method_ids.filtered(
            lambda p: p.journal_id.type == "bank"
        )[:1]
        if not card_method:
            raise UserError(_("No se encontró método de pago bancario para este TPV."))

        return self.action_pos_convention_pay_with_method(card_method)

    def action_pos_convention_pay_with_method(self, payment_method_id):
        self.ensure_one()
        if float_is_zero(self.amount_total, precision_rounding=self.currency_id.rounding):
            raise UserError(
                _("No se puede cobrar un pedido con importe cero. Por favor, añada productos.")
            )

        payment_method = payment_method_id
        if not hasattr(payment_method, "id"):
            try:
                payment_method = self.env["pos.payment.method"].browse(
                    int(payment_method_id)
                )
            except (ValueError, TypeError):
                return False

        if not payment_method or not payment_method.exists():
            return False

        if self._is_negative_payment_flow():
            return self._action_standard_payment_wizard(payment_method)

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
            view = self.env.ref(
                "pos_conventional_payment_wizard.view_pos_make_payment_wizard_cash_form",
                False,
            )
            return {
                "type": "ir.actions.act_window",
                "res_model": "pos.make.payment.wizard",
                "name": _("Cash Payment"),
                "view_mode": "form",
                "views": [[view.id if view else False, "form"]],
                "target": "new",
                "context": {
                    "active_id": self.id,
                    "default_payment_method_id": payment_method.id,
                    "default_amount_tendered": self.amount_total,
                    "cash_only": True,
                    "cash_quick_mode": True,
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
            raise UserError(_("The order is already fully paid."))

        wizard = self.env["pos.make.payment"].with_context(
            active_id=self.id, card_payment=True
        ).create({
            "amount": amount_due,
            "payment_method_id": payment_method.id,
        })
        return wizard.check()

    def action_open_payment_popup(self):
        self.ensure_one()
        if float_is_zero(self.amount_total, precision_rounding=self.currency_id.rounding):
            raise UserError(
                _("No se puede cobrar un pedido con importe cero. Por favor, añada productos.")
            )

        if self._is_negative_payment_flow():
            return {
                "type": "ir.actions.act_window",
                "res_model": "pos.make.payment",
                "name": _("Make Payment"),
                "view_mode": "form",
                "view_id": False,
                "target": "new",
                "views": False,
                "context": {
                    **self.env.context,
                    "active_id": self.id,
                },
            }

        view = self.env.ref(
            "pos_conventional_payment_wizard.view_pos_make_payment_wizard_form", False
        )
        return {
            "type": "ir.actions.act_window",
            "res_model": "pos.make.payment.wizard",
            "name": _("Make Payment"),
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

        methods = [
            {
                "id": pm.id,
                "name": pm.name,
                "type": pm.type,
                "icon": "fa-money"
                if pm.journal_id.type == "cash"
                else "fa-credit-card",
            }
            for pm in self.config_id.payment_method_ids
        ]

        payments = [
            {
                "id": p.id,
                "payment_method_id": p.payment_method_id.id,
                "payment_method_name": p.payment_method_id.name,
                "amount": p.amount,
            }
            for p in self.payment_ids
        ]

        amount_due = self.amount_total - self.amount_paid
        return {
            "order_id": self.id,
            "amount_total": self.amount_total,
            "amount_paid": self.amount_paid,
            "amount_due": round(amount_due, self.currency_id.decimal_places),
            "currency_symbol": self.currency_id.symbol,
            "available_methods": methods,
            "payments": payments,
        }

    def add_payment_from_ui(self, payment_method_id, amount):
        self.ensure_one()
        self.add_payment({
            "pos_order_id": self.id,
            "amount": float(amount),
            "payment_method_id": int(payment_method_id),
        })
        return self.get_payment_popup_data()

    def remove_payment_from_ui(self, payment_id):
        self.ensure_one()
        payment = self.env["pos.payment"].browse(int(payment_id))
        if payment.exists() and payment.pos_order_id.id == self.id:
            payment.unlink()
        return self.get_payment_popup_data()

    def action_register_payments_and_validate(self, payments, print_invoice=False):
        self.ensure_one()
        self.payment_ids.unlink()

        for pay in payments:
            amount = float(pay.get("amount", 0))
            method_id = int(pay.get("payment_method_id"))
            if amount != 0:
                self.add_payment({
                    "pos_order_id": self.id,
                    "payment_method_id": method_id,
                    "amount": amount,
                })

        # Return change as negative cash payment
        amount_paid = sum(self.payment_ids.mapped("amount"))
        if amount_paid > self.amount_total:
            change = amount_paid - self.amount_total
            cash_method = self.config_id.payment_method_ids.filtered("is_cash_count")[:1]
            if cash_method:
                self.add_payment({
                    "pos_order_id": self.id,
                    "amount": -change,
                    "payment_method_id": cash_method.id,
                    "is_change": True,
                })

        return {"success": True, "action": self.action_validate_and_invoice()}
