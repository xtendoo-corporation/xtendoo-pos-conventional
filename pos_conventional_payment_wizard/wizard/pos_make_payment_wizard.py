import logging

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class PosMakePaymentWizard(models.TransientModel):
    _name = "pos.make.payment.wizard"
    _description = "Asistente de Pago POS"

    order_id = fields.Many2one("pos.order", string="Pedido", required=True, ondelete="cascade")
    currency_id = fields.Many2one(related="order_id.currency_id", depends=["order_id"])
    amount_total = fields.Monetary(related="order_id.amount_total", string="Total Pedido", readonly=True)
    amount_paid = fields.Monetary(string="Pagado", compute="_compute_totals")
    amount_due = fields.Monetary(string="Total a Pagar", compute="_compute_totals")
    amount_tendered = fields.Monetary(string="Importe Entregado", default=0.0)
    amount_change = fields.Monetary(string="Cambio a Devolver", compute="_compute_amount_change")
    is_cash_payment = fields.Boolean(compute="_compute_is_cash_payment")
    payment_ids = fields.Many2many(
        comodel_name="pos.payment",
        compute="_compute_payment_ids",
        inverse="_inverse_payment_ids",
        string="Pagos Registrados",
    )
    payment_method_id = fields.Many2one(
        "pos.payment.method",
        string="Diario",
        domain="[('id', 'in', available_payment_method_ids)]",
    )
    config_id = fields.Many2one(related="order_id.config_id")
    available_payment_method_ids = fields.Many2many(
        "pos.payment.method",
        compute="_compute_available_payment_methods",
    )

    @api.depends("order_id.payment_ids")
    def _compute_payment_ids(self):
        for wizard in self:
            wizard.payment_ids = wizard.order_id.payment_ids

    def _inverse_payment_ids(self):
        """Elimina del pedido los pagos que el usuario quitó de la lista."""
        for wizard in self:
            to_remove = wizard.order_id.payment_ids - wizard.payment_ids
            to_remove.unlink()

    @api.onchange("payment_ids")
    def _onchange_payment_ids_totals(self):
        """Actualiza importes en tiempo real cuando el usuario elimina una fila."""
        for wizard in self:
            paid = sum(wizard.payment_ids.mapped("amount"))
            wizard.amount_paid = paid
            due = wizard.order_id.amount_total - paid
            wizard.amount_due = due if due > 0 else 0.0

    @api.depends("payment_method_id")
    def _compute_is_cash_payment(self):
        for wizard in self:
            wizard.is_cash_payment = bool(
                wizard.payment_method_id
                and (
                    wizard.payment_method_id.is_cash_count
                    or wizard.payment_method_id.journal_id.type == "cash"
                )
            )

    @api.depends("amount_tendered", "amount_paid", "amount_total")
    def _compute_amount_change(self):
        """
        Calcula la diferencia entre lo entregado (pagos previos + importe actual)
        y el total del pedido. Positivo: devolver cambio. Negativo: falta por pagar.
        """
        for wizard in self:
            wizard.amount_change = (
                wizard.amount_paid + wizard.amount_tendered - wizard.amount_total
            )

    @api.onchange("amount_tendered", "payment_ids")
    def _onchange_amount_tendered(self):
        """
        Actualiza amount_change en tiempo real cuando el usuario edita el importe.

        En OWL 17+ @api.depends actualiza computed fields en el contexto ORM,
        pero para actualizaciones instantáneas en el formulario se requiere
        @api.onchange explícito sobre los campos que el usuario puede editar.
        """
        for wizard in self:
            paid = sum(wizard.order_id.payment_ids.mapped("amount"))
            wizard.amount_change = (
                paid + wizard.amount_tendered - wizard.order_id.amount_total
            )

    @api.depends("order_id.amount_total", "order_id.payment_ids", "order_id.payment_ids.amount")
    def _compute_totals(self):
        for wizard in self:
            paid = sum(wizard.order_id.payment_ids.mapped("amount"))
            wizard.amount_paid = paid
            due = wizard.order_id.amount_total - paid
            wizard.amount_due = due if due > 0 else 0.0

    @api.depends("config_id")
    def _compute_available_payment_methods(self):
        for wizard in self:
            if self._context.get("cash_only"):
                wizard.available_payment_method_ids = wizard.config_id.payment_method_ids.filtered(
                    lambda payment_method: payment_method.is_cash_count or payment_method.journal_id.type == "cash"
                )
            else:
                wizard.available_payment_method_ids = wizard.config_id.payment_method_ids

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        active_id = self._context.get("active_id")
        if active_id:
            order = self.env["pos.order"].browse(active_id)
            if order.exists():
                res["order_id"] = order.id
                try:
                    order._compute_prices()
                except Exception:
                    order.amount_total = sum(order.lines.mapped("price_subtotal_incl"))

                due = order.amount_total - order.amount_paid
                res["amount_tendered"] = due if due > 0 else 0.0

                payment_methods = order.config_id.payment_method_ids
                if self._context.get("cash_only"):
                    payment_methods = payment_methods.filtered(
                        lambda payment_method: payment_method.is_cash_count or payment_method.journal_id.type == "cash"
                    )

                default_payment_method = self._context.get("default_payment_method_id")
                if default_payment_method:
                    res["payment_method_id"] = default_payment_method
                elif payment_methods:
                    cash_payment_method = payment_methods.filtered(
                        lambda payment_method: payment_method.is_cash_count or payment_method.journal_id.type == "cash"
                    )[:1]
                    res["payment_method_id"] = cash_payment_method.id if cash_payment_method else payment_methods[0].id
        return res

    def _get_wizard_view_id(self):
        if self._context.get("cash_only"):
            return self.env.ref("pos_conventional_payment_wizard.view_pos_make_payment_wizard_cash_form").id
        return self.env.ref("pos_conventional_payment_wizard.view_pos_make_payment_wizard_form").id

    def _add_payment(self, payment_method_id):
        self.ensure_one()
        if self.amount_tendered <= 0.0:
            raise UserError(_("Debe ingresar un importe mayor a cero o el pedido ya está pagado."))

        payment_method = self.env["pos.payment.method"].browse(payment_method_id)
        if not payment_method.exists():
            raise UserError(_("Método de pago no válido."))

        self.order_id.add_payment(
            {
                "pos_order_id": self.order_id.id,
                "amount": self.amount_tendered,
                "payment_method_id": payment_method.id,
            }
        )

        due = self.order_id.amount_total - self.order_id.amount_paid
        self.amount_tendered = due if due > 0 else 0.0

        return {
            "type": "ir.actions.act_window",
            "res_model": "pos.make.payment.wizard",
            "res_id": self.id,
            "view_mode": "form",
            "view_id": self._get_wizard_view_id(),
            "target": "new",
            "context": self._context,
        }

    def action_pay_cash(self):
        cash_method = self.env["pos.payment.method"].search([("is_cash_count", "=", True)], limit=1)
        if not cash_method:
            cash_method = self.env["pos.payment.method"].search([("journal_id.type", "=", "cash")], limit=1)
        if not cash_method:
            raise UserError(_("No se encontró método de pago en efectivo."))
        return self._add_payment(cash_method.id)

    def action_pay_card(self):
        self.ensure_one()
        card_method = self.env["pos.payment.method"].search([("name", "ilike", "tarjeta")], limit=1)
        if not card_method:
            raise UserError(_("No se encontró método de pago con tarjeta."))
        return self._add_payment(card_method.id)

    def action_add_payment(self):
        self.ensure_one()
        if not self.payment_method_id:
            raise UserError(_("Debe seleccionar un método de pago."))
        return self._add_payment(self.payment_method_id.id)

    def action_clear_payments(self):
        self.ensure_one()
        if self.order_id.payment_ids:
            self.order_id.payment_ids.unlink()
        return {
            "type": "ir.actions.act_window",
            "res_model": "pos.make.payment.wizard",
            "res_id": self.id,
            "view_mode": "form",
            "view_id": self._get_wizard_view_id(),
            "target": "new",
            "context": self._context,
        }

    def _execute_validation(self, print_invoice=False):
        self.ensure_one()

        if self.amount_total <= 0:
            raise UserError(_("Cannot charge an order with zero amount. Please add products."))

        total_covered = self.amount_paid + self.amount_tendered
        if total_covered < self.amount_total - 0.01:
            raise UserError(_("Insufficient amount paid."))

        order = self.order_id
        is_conventional = order.config_id and order.config_id.pos_non_touch

        if order.state == "draft":
            cash_method = self.payment_method_id
            if not cash_method.is_cash_count and cash_method.journal_id.type != "cash":
                cash_method = order.config_id.payment_method_ids.filtered("is_cash_count")[:1]
                if not cash_method:
                    cash_method = order.config_id.payment_method_ids.filtered(
                        lambda payment_method: payment_method.journal_id.type == "cash"
                    )[:1]

            if self.is_cash_payment and self.amount_change > 0.01:
                order.add_payment({
                    "pos_order_id": order.id,
                    "amount": self.amount_tendered,
                    "payment_method_id": self.payment_method_id.id,
                })
                if cash_method:
                    order.add_payment({
                        "pos_order_id": order.id,
                        "amount": -self.amount_change,
                        "payment_method_id": cash_method.id,
                    })
            else:
                due = order.amount_total - order.amount_paid
                if due > 0.01:
                    order.add_payment({
                        "pos_order_id": order.id,
                        "amount": due,
                        "payment_method_id": self.payment_method_id.id,
                    })

            # If no explicit customer, assign the default partner from config
            # (anonymous sale → 'End Consumer'). Must be done BEFORE _process_saved_order.
            if not order.partner_id:
                fallback_partner = (
                    order.config_id.default_partner_id
                    or order.company_id.partner_id
                )
                if fallback_partner:
                    order.write({"partner_id": fallback_partner.id})
                    _logger.info(
                        "POS: default partner assigned (%s) for order %s",
                        fallback_partner.name, order.name,
                    )

            # Mark for automatic invoicing when the order has a customer.
            # _process_saved_order generates the invoice if to_invoice=True and state='paid'.
            # This must be set BEFORE calling _process_saved_order.
            if order.partner_id and not order.account_move:
                order.write({"to_invoice": True})
                _logger.info(
                    "POS: to_invoice=True for order %s with customer %s",
                    order.name, order.partner_id.name,
                )

            order._process_saved_order(False)

            if order.state in {"paid", "done"}:
                order._send_order()
                order.config_id.notify_synchronisation(order.config_id.current_session_id.id, 0)

            if not is_conventional or order.state not in {"paid", "done"}:
                return {"type": "ir.actions.act_window_close"}

            next_action = {
                "type": "ir.actions.client",
                "tag": "pos_conventional_new_order",
                "params": {
                    "config_id": order.config_id.id,
                    "default_session_id": order.config_id.current_session_id.id,
                },
            }

            # Print receipt if iface_print_auto is enabled (or explicitly requested)
            # and an invoice has been generated.
            should_print = print_invoice or order.config_id.iface_print_auto
            if should_print and order.account_move:
                return {
                    "type": "ir.actions.client",
                    "tag": "pos_conventional_print_receipt_client",
                    "params": {
                        "order_id": order.id,
                        "move_id": order.account_move.id,
                        "next_action": next_action,
                    },
                }

            return next_action

        return {"type": "ir.actions.act_window_close"}

    def action_validate(self):
        return self._execute_validation(print_invoice=False)

    def action_validate_print(self):
        return self._execute_validation(print_invoice=True)

