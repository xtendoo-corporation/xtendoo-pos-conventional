from odoo import models
from odoo.exceptions import UserError
from odoo.tools.translate import _


class PosOrder(models.Model):
    _inherit = "pos.order"

    def _is_cash_payment_method(self, payment_method):
        self.ensure_one()
        if not payment_method:
            return False

        name_lower = (payment_method.name or "").lower()
        return bool(
            getattr(payment_method, "type", False) == "cash"
            or payment_method.is_cash_count
            or payment_method.journal_id.type == "cash"
            or "efectivo" in name_lower
            or "cash" in name_lower
            or "caja" in name_lower
        )

    def _get_cash_drawer_action_params(self):
        self.ensure_one()
        if not self.config_id:
            return False

        try:
            action = self.config_id.action_test_cash_drawer()
        except UserError:
            return False

        return action.get("params") or False

    def _payments_payload_has_cash_method(self, payments):
        self.ensure_one()
        method_ids = []
        for payment in payments or []:
            amount = float(payment.get("amount", 0) or 0)
            if not amount:
                continue
            method_id = payment.get("payment_method_id")
            if not method_id:
                continue
            try:
                method_ids.append(int(method_id))
            except (TypeError, ValueError):
                continue

        if not method_ids:
            return False

        payment_methods = self.env["pos.payment.method"].browse(method_ids).exists()
        return any(self._is_cash_payment_method(payment_method) for payment_method in payment_methods)

    def _wrap_action_with_cash_drawer(self, next_action, require_auto_open=False):
        self.ensure_one()

        if (
            isinstance(next_action, dict)
            and next_action.get("tag")
            == "pos_conventional_cash_drawer_open_and_continue"
        ):
            return next_action

        if require_auto_open and not self.config_id.cash_drawer_auto_open:
            return next_action

        cash_drawer_params = self._get_cash_drawer_action_params()
        if not cash_drawer_params:
            return next_action

        return {
            "type": "ir.actions.client",
            "tag": "pos_conventional_cash_drawer_open_and_continue",
            "params": {
                **cash_drawer_params,
                "next_action": next_action or False,
            },
        }

    def action_open_cash_drawer_from_conventional(self):
        self.ensure_one()
        if not self.config_id:
            raise UserError(
                _(
                    "No se pudo identificar la configuración del TPV para abrir el cajón."
                )
            )
        return self.config_id.action_test_cash_drawer()

    def action_register_payments_and_validate(self, payments, print_invoice=False):
        self.ensure_one()
        should_open_cash_drawer = self._payments_payload_has_cash_method(payments)
        result = super().action_register_payments_and_validate(
            payments, print_invoice=print_invoice
        )

        if (
            not should_open_cash_drawer
            or not isinstance(result, dict)
            or not result.get("success")
            or self.state not in {"paid", "done"}
        ):
            return result

        result["action"] = self._wrap_action_with_cash_drawer(
            result.get("action"), require_auto_open=True
        )
        return result


