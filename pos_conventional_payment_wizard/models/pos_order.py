import logging

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools import float_compare, float_is_zero
from odoo.tools.translate import _

_logger = logging.getLogger(__name__)


class PosOrder(models.Model):
    _inherit = "pos.order"

    use_fast_payment = fields.Boolean(
        related="config_id.use_fast_payment",
        string="Pago con un solo clic",
        readonly=True,
        store=False,
    )
    available_fast_payment_method_ids = fields.Many2many(
        "pos.payment.method",
        compute="_compute_available_fast_payment_method_ids",
        string="Métodos de pago rápido disponibles",
        store=False,
        readonly=True,
    )

    @api.depends(
        "config_id.use_fast_payment",
        "config_id.fast_payment_method_ids",
        "config_id.fast_payment_method_ids.use_payment_terminal",
        "config_id.fast_payment_method_ids.split_transactions",
    )
    def _compute_available_fast_payment_method_ids(self):
        for order in self:
            config = order.config_id
            if not config or not config.use_fast_payment:
                order.available_fast_payment_method_ids = False
                continue

            order.available_fast_payment_method_ids = config.fast_payment_method_ids.filtered(
                lambda payment_method: not payment_method.use_payment_terminal
                and not payment_method.split_transactions
            )

    def _get_previous_sale_banner_params(self):
        """Datos a mostrar en la siguiente venta como resumen de la operación anterior."""
        self.ensure_one()

        currency = self.currency_id or self.session_id.currency_id or self.env.company.currency_id
        round_amount = currency.round if currency else lambda amount: round(amount, 2)
        rounding = currency.rounding if currency else 0.01

        change_amount = 0.0
        is_cash = False
        if self.amount_total > 0:
            negative_payments = self.payment_ids.filtered(
                lambda payment: float_compare(
                    payment.amount, 0.0, precision_rounding=rounding
                ) < 0
            )
            if negative_payments:
                change_amount = abs(sum(negative_payments.mapped("amount")))
            elif float_compare(getattr(self, "amount_return", 0.0), 0.0, precision_rounding=rounding) > 0:
                change_amount = self.amount_return

            # Detectamos si se ha usado algún método de efectivo
            cash_methods = self.payment_ids.filtered(
                lambda p: p.payment_method_id.type == "cash" or p.payment_method_id.is_cash_count
            )
            is_cash = bool(cash_methods)

        return {
            "previous_sale_total": round_amount(self.amount_total),
            "previous_sale_change": round_amount(change_amount),
            "previous_sale_currency": currency.symbol if currency and currency.symbol else "€",
            "previous_sale_is_cash": is_cash,
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

    def _get_fast_payment_methods(self):
        self.ensure_one()
        return self.available_fast_payment_method_ids

    def _get_fast_payment_method(self, payment_method_id):
        self.ensure_one()
        payment_method = payment_method_id
        if not hasattr(payment_method, "id"):
            try:
                payment_method = self.env["pos.payment.method"].browse(int(payment_method_id))
            except (ValueError, TypeError):
                return self.env["pos.payment.method"]

        if not payment_method or not payment_method.exists():
            return self.env["pos.payment.method"]

        return payment_method

    def _is_cash_payment_method(self, payment_method):
        self.ensure_one()
        payment_method = self._get_fast_payment_method(payment_method)
        if not payment_method:
            return False

        name_lower = (payment_method.name or "").lower()
        return bool(
            getattr(payment_method, "type", False) == "cash"
            or payment_method.is_cash_count
            or payment_method.journal_id.type == "cash"
        )

    def _ensure_fast_payment_order_is_valid(self):
        self.ensure_one()
        if not self.has_order_lines:
            raise UserError(
                _("No se puede cobrar un pedido sin líneas. Añada productos al pedido.")
            )

    def _ensure_fast_payment_method_is_allowed(self, payment_method):
        self.ensure_one()
        if not self.use_fast_payment:
            raise UserError(_("El pago rápido no está habilitado en este TPV."))
        if not payment_method:
            raise UserError(_("No se encontró el método de pago rápido solicitado."))
        if payment_method not in self._get_fast_payment_methods():
            raise UserError(_("El método de pago seleccionado no está configurado para pago rápido."))

    def get_fast_payment_methods_data(self):
        self.ensure_one()
        return [
            {
                "id": payment_method.id,
                "name": payment_method.name,
            }
            for payment_method in self._get_fast_payment_methods()
        ]

    def action_validate_fast_payment(self, payment_method_id):
        self.ensure_one()
        self._ensure_fast_payment_order_is_valid()
        payment_method = self._get_fast_payment_method(payment_method_id)
        self._ensure_fast_payment_method_is_allowed(payment_method)
        return self.action_pos_convention_pay_with_method(
            payment_method,
            force_print=not self._is_cash_payment_method(payment_method),
        )

    def action_pay_cash(self):
        self.ensure_one()

        cash_method = self.config_id.payment_method_ids.filtered("is_cash_count")[:1]
        if not cash_method:
            cash_method = self.config_id.payment_method_ids.filtered(
                lambda p: p.journal_id.type == "cash"
            )[:1]
        if not cash_method:
            raise UserError(_("No se encontró método de pago en efectivo para este TPV."))


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

        card_method = self.config_id.payment_method_ids.filtered(
            lambda p: p.journal_id.type == "bank"
        )[:1]
        if not card_method:
            raise UserError(_("No se encontró método de pago bancario para este TPV."))

        return self.action_pos_convention_pay_with_method(card_method, force_print=True)

    def action_pos_convention_pay_with_method(self, payment_method_id, force_print=False):
        self.ensure_one()
        self._ensure_fast_payment_order_is_valid()

        payment_method = self._get_fast_payment_method(payment_method_id)
        if not payment_method:
            return False


        is_cash = self._is_cash_payment_method(payment_method)

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

        if payment_method.use_payment_terminal:
            return False

        amount_due = self.amount_total - self.amount_paid
        is_paid = False
        if float_compare(self.amount_total, 0.0, precision_rounding=self.currency_id.rounding or 0.01) >= 0:
            is_paid = float_compare(amount_due, 0.0, precision_rounding=self.currency_id.rounding or 0.01) <= 0
        else:
            is_paid = float_compare(amount_due, 0.0, precision_rounding=self.currency_id.rounding or 0.01) >= 0

        if is_paid:
            raise UserError(_("The order is already fully paid."))

        wizard = self.env["pos.make.payment"].with_context(active_id=self.id).create({
            "amount": amount_due,
            "payment_method_id": payment_method.id,
        })
        return wizard.check(force_print=force_print)

    def action_open_payment_popup(self):
        self.ensure_one()

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
