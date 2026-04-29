import logging

from odoo import api, fields, models, _
from odoo.exceptions import UserError, MissingError

_logger = logging.getLogger(__name__)


class PosMakePaymentWizard(models.TransientModel):
    _name = "pos.make.payment.wizard"
    _description = "Asistente de Pago POS"

    def _is_cash_quick_mode(self):
        """Popup rápido de efectivo: cobra el ticket completo en un solo paso.

        En este modo no se reutilizan pagos borrador previos; el cajero ve el
        total actual del ticket como importe sugerido y, al validar, dichos pagos
        temporales se sustituyen por el cobro final.
        """
        return bool(self.env.context.get("cash_quick_mode"))

    def _get_order_amounts(self, order, ignore_existing_payments=False):
        """Devuelve total, pagado y pendiente recalculados desde el pedido."""
        order = order.sudo()
        total = sum(order.lines.mapped("price_subtotal_incl")) or order.amount_total
        paid = 0.0 if ignore_existing_payments else sum(order.payment_ids.mapped("amount"))
        due = total - paid
        return total, paid, due if due > 0 else 0.0

    # check_company=False: el wizard puede operar sobre pedidos de cualquier
    # compañía activa del usuario. La regla multi-compañía estándar de pos.order
    # ([('company_id', 'in', company_ids)]) excluiría el pedido si el contexto
    # de compañía del usuario no coincide exactamente, provocando un MissingError
    # al crear/escribir el wizard. El acceso real se controla en _execute_validation.
    order_id = fields.Many2one(
        "pos.order",
        string="Pedido",
        required=True,
        ondelete="cascade",
        check_company=False,
    )
    # Los campos relacionados se computan manualmente con sudo() para evitar
    # que la regla multi-compañía de pos.order bloquee el acceso al leer los datos.
    currency_id = fields.Many2one(
        "res.currency",
        string="Moneda",
        compute="_compute_order_fields",
        store=False,
    )
    currency_symbol = fields.Char(
        string="Símbolo moneda",
        compute="_compute_order_fields",
        store=False,
        readonly=True,
    )
    amount_total = fields.Monetary(
        string="Total Pedido",
        compute="_compute_order_fields",
        currency_field="currency_id",
        store=False,
        readonly=True,
    )
    config_id = fields.Many2one(
        "pos.config",
        string="Configuración",
        compute="_compute_order_fields",
        store=False,
    )
    amount_paid = fields.Monetary(string="Pagado", compute="_compute_totals", currency_field="currency_id")
    amount_due = fields.Monetary(string="Total a Pagar", compute="_compute_totals", currency_field="currency_id")
    amount_tendered = fields.Monetary(string="Importe Entregado", default=0.0, currency_field="currency_id")
    amount_change = fields.Monetary(string="Cambio a Devolver", compute="_compute_amount_change", currency_field="currency_id")
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
    available_payment_method_ids = fields.Many2many(
        "pos.payment.method",
        compute="_compute_available_payment_methods",
    )


    @api.depends("order_id")
    def _compute_order_fields(self):
        """Lee currency_id, amount_total y config_id directamente via sudo()
        para evitar MissingError cuando la compañía del contexto no coincide."""
        for wizard in self:
            order = wizard.order_id.sudo()
            total, _paid, _due = wizard._get_order_amounts(order)
            wizard.currency_id = order.currency_id
            wizard.currency_symbol = order.currency_id.symbol or ""
            wizard.amount_total = total
            wizard.config_id = order.config_id

    @api.depends("order_id.amount_total", "order_id.payment_ids", "order_id.payment_ids.amount")
    def _compute_totals(self):
        for wizard in self:
            order = wizard.order_id.sudo()
            _total, paid, due = wizard._get_order_amounts(
                order,
                ignore_existing_payments=wizard._is_cash_quick_mode(),
            )
            wizard.amount_paid = paid
            wizard.amount_due = due

    @api.depends("order_id.payment_ids")
    def _compute_payment_ids(self):
        for wizard in self:
            wizard.payment_ids = wizard.order_id.sudo().payment_ids

    def _inverse_payment_ids(self):
        """Elimina del pedido los pagos que el usuario quitó de la lista."""
        for wizard in self:
            to_remove = wizard.order_id.sudo().payment_ids - wizard.payment_ids
            to_remove.unlink()

    @api.onchange("payment_ids")
    def _onchange_payment_ids_totals(self):
        """Actualiza importes en tiempo real cuando el usuario elimina una fila."""
        for wizard in self:
            if wizard._is_cash_quick_mode():
                wizard.amount_paid = 0.0
                wizard.amount_due = wizard.amount_total
                continue
            paid = sum(wizard.payment_ids.mapped("amount"))
            wizard.amount_paid = paid
            due = wizard.amount_total - paid
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

    @api.depends("amount_tendered", "amount_due", "is_cash_payment")
    def _compute_amount_change(self):
        """
        Cambio = Total a pagar (amount_due) - Importe entregado (amount_tendered).

        Interpretación:
          > 0  → el cliente aún debe pagar esa cantidad (se muestra en ROJO).
          = 0  → pago exacto.
          < 0  → hay cambio que devolver al cliente (se muestra en VERDE,
                 el importe es el valor absoluto).

        Solo aplica para pagos en efectivo; para otros métodos devuelve 0.
        """
        for wizard in self:
            if wizard.is_cash_payment:
                wizard.amount_change = wizard.amount_due - wizard.amount_tendered
            else:
                wizard.amount_change = 0.0

    @api.onchange("amount_tendered", "payment_ids", "payment_method_id")
    def _onchange_amount_tendered(self):
        """
        Actualiza amount_change en tiempo real cuando el usuario edita el importe
        o cambia el método de pago.

        amount_change = amount_due - amount_tendered.
        Solo aplica para efectivo; para otros métodos amount_change es 0.
        """
        for wizard in self:
            if wizard.is_cash_payment:
                _total, _paid, due = wizard._get_order_amounts(
                    wizard.order_id,
                    ignore_existing_payments=wizard._is_cash_quick_mode(),
                )
                wizard.amount_change = due - wizard.amount_tendered
            else:
                wizard.amount_change = 0.0


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
        active_id = self.env.context.get("active_id")
        if not active_id:
            return res

        # sudo() necesario para evitar MissingError en entornos multi-compañía
        # cuando el contexto de compañía del usuario no coincide con la del pedido.
        order = self.env["pos.order"].sudo().browse(active_id)
        if not order.exists():
            _logger.warning(
                "PosMakePaymentWizard.default_get: pos.order(%s) no encontrado "
                "para el usuario %s",
                active_id,
                self.env.user.id,
            )
            return res

        res["order_id"] = order.id

        # Calcular el total directamente desde las líneas del pedido.
        # El campo almacenado amount_total puede estar desactualizado si el usuario
        # no ha guardado el formulario antes de pulsar el botón de pago (el onchange
        # de lines actualiza amount_total en memoria pero force_save solo persiste
        # al guardar). Usar las líneas garantiza el valor correcto en cualquier caso.
        ignore_existing_payments = bool(self.env.context.get("cash_quick_mode"))
        amount_total, _paid, due = self._get_order_amounts(
            order,
            ignore_existing_payments=ignore_existing_payments,
        )

        res["amount_tendered"] = self.env.context.get(
            "default_amount_tendered",
            amount_total if ignore_existing_payments else due,
        )

        payment_methods = order.config_id.payment_method_ids
        if self.env.context.get("cash_only"):
            payment_methods = payment_methods.filtered(
                lambda payment_method: payment_method.is_cash_count
                or payment_method.journal_id.type == "cash"
            )

        default_payment_method = self.env.context.get("default_payment_method_id")
        if default_payment_method:
            res["payment_method_id"] = default_payment_method
        elif payment_methods:
            cash_payment_method = payment_methods.filtered(
                lambda payment_method: payment_method.is_cash_count
                or payment_method.journal_id.type == "cash"
            )[:1]
            res["payment_method_id"] = (
                cash_payment_method.id if cash_payment_method else payment_methods[0].id
            )
        return res

    def _get_wizard_view_id(self):
        if self.env.context.get("cash_only"):
            return self.env.ref("pos_conventional_payment_wizard.view_pos_make_payment_wizard_cash_form").id
        return self.env.ref("pos_conventional_payment_wizard.view_pos_make_payment_wizard_form").id

    def _warning_notification_action(self, message, title=None):
        """Muestra un banner warning sin cerrar el wizard."""
        self.ensure_one()
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": title or _("Aviso"),
                "message": message,
                "type": "warning",
                "sticky": True,
            },
        }

    def _add_payment(self, payment_method_id):
        self.ensure_one()
        if self.amount_tendered <= 0.0:
            raise UserError(_("Debe ingresar un importe mayor a cero o el pedido ya está pagado."))

        payment_method = self.env["pos.payment.method"].browse(payment_method_id)
        if not payment_method.exists():
            raise UserError(_("Método de pago no válido."))

        order = self.order_id.sudo()
        order.add_payment(
            {
                "pos_order_id": order.id,
                "amount": self.amount_tendered,
                "payment_method_id": payment_method.id,
            }
        )

        due = order.amount_total - order.amount_paid
        self.amount_tendered = due if due > 0 else 0.0

        return {
            "type": "ir.actions.act_window",
            "res_model": "pos.make.payment.wizard",
            "res_id": self.id,
            "view_mode": "form",
            "view_id": self._get_wizard_view_id(),
            "target": "new",
            "context": self.env.context,
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
        order = self.order_id.sudo()
        if order.payment_ids:
            order.payment_ids.unlink()
        return {
            "type": "ir.actions.act_window",
            "res_model": "pos.make.payment.wizard",
            "res_id": self.id,
            "view_mode": "form",
            "view_id": self._get_wizard_view_id(),
            "target": "new",
            "context": self.env.context,
        }

    def _execute_validation(self, print_invoice=False):
        self.ensure_one()

        # Verificar existencia del pedido antes de operar (guard contra MissingError
        # en entornos multi-compañía o si el pedido fue eliminado concurrentemente).
        try:
            order = self.order_id.sudo()
            if not order.exists():
                raise UserError(_("El pedido asociado ya no existe o ha sido eliminado."))
        except MissingError as exc:
            raise UserError(
                _("El pedido no es accesible. Compruebe que tiene los permisos necesarios.")
            ) from exc

        if self.amount_total <= 0:
            raise UserError(_("No se puede cobrar un pedido con importe cero. Por favor, añada productos."))

        # amount_change = amount_due - amount_tendered:
        #   > 0.01  → importe insuficiente (falta por pagar)
        #   < -0.01 → hay cambio que devolver al cliente
        if self.is_cash_payment:
            if self.amount_change > 0.01:
                return self._warning_notification_action(
                    _("Importe insuficiente para completar el pago.")
                )
        else:
            total_covered = self.amount_paid + self.amount_tendered
            if total_covered < self.amount_total - 0.01:
                return self._warning_notification_action(
                    _("Importe insuficiente para completar el pago.")
                )

        is_conventional = bool(
            order.config_id and getattr(order.config_id, "pos_non_touch", False)
        )

        if order.state == "draft":
            if self._is_cash_quick_mode() and order.payment_ids:
                order.payment_ids.unlink()
                order.invalidate_recordset(["payment_ids", "amount_paid"])

            cash_method = self.payment_method_id
            if not cash_method.is_cash_count and cash_method.journal_id.type != "cash":
                cash_method = order.config_id.payment_method_ids.filtered("is_cash_count")[:1]
                if not cash_method:
                    cash_method = order.config_id.payment_method_ids.filtered(
                        lambda payment_method: payment_method.journal_id.type == "cash"
                    )[:1]

            # amount_change = amount_due - amount_tendered:
            #   < -0.01 → cliente entregó más → hay cambio que devolver
            # cash_change_for_banner: valor positivo del cambio a devolver
            cash_change_for_banner = (
                -self.amount_change
                if self.is_cash_payment and self.amount_change < -0.01
                else 0.0
            )

            if self.is_cash_payment and self.amount_change < -0.01:
                order.add_payment({
                    "pos_order_id": order.id,
                    "amount": self.amount_tendered,
                    "payment_method_id": self.payment_method_id.id,
                })
                if cash_method:
                    order.add_payment({
                        "pos_order_id": order.id,
                        "amount": self.amount_change,  # ya es negativo → pago de vuelta
                        "payment_method_id": cash_method.id,
                    })
            else:
                _total, _paid, due = self._get_order_amounts(order)
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
                    getattr(order.config_id, "default_partner_id", False)
                    or order.company_id.partner_id
                )
                if fallback_partner:
                    order.with_context(skip_completeness_check=True).write(
                        {"partner_id": fallback_partner.id}
                    )
                    _logger.info(
                        "POS: default partner assigned (%s) for order %s",
                        fallback_partner.name, order.name,
                    )

            # Mark for automatic invoicing when the order has a customer.
            # _process_saved_order generates the invoice if to_invoice=True and state='paid'.
            # This must be set BEFORE calling _process_saved_order.
            if order.partner_id and not order.account_move:
                vals = {"to_invoice": True}
                # Si existe el campo de factura simplificada (localización española), lo marcamos
                if "is_l10n_es_simplified_invoice" in order._fields:
                    vals["is_l10n_es_simplified_invoice"] = True
                
                order.with_context(skip_completeness_check=True).write(vals)
                _logger.info(
                    "POS: to_invoice=True (simplified=%s) for order %s",
                    vals.get("is_l10n_es_simplified_invoice", False), order.name
                )

            order._process_saved_order(False)

            if order.state in {"paid", "done"}:
                order._send_order()
                order.config_id.notify_synchronisation(
                    order.config_id.current_session_id.id, 0
                )

            if not is_conventional or order.state not in {"paid", "done"}:
                return {"type": "ir.actions.act_window_close"}

            previous_sale_params = order._get_previous_sale_banner_params()

            next_action = {
                "type": "ir.actions.client",
                "tag": "pos_conventional_new_order",
                "params": {
                    "config_id": order.config_id.id,
                    "default_session_id": order.config_id.current_session_id.id,
                    **previous_sale_params,
                },
            }

            if cash_change_for_banner > 0.005:
                next_action["params"]["cash_change"] = round(cash_change_for_banner, 2)
                next_action["params"]["cash_change_currency"] = previous_sale_params["previous_sale_currency"]

            # Print receipt if iface_print_auto is enabled (or explicitly requested)
            # and an invoice has been generated.
            should_print = print_invoice or order.config_id.iface_print_auto
            if should_print and order.account_move:
                is_cash = False
                if self.payment_method_id and self.payment_method_id.type == 'cash':
                    is_cash = True

                return {
                    "type": "ir.actions.client",
                    "tag": "pos_conventional_print_receipt_client",
                    "params": {
                        "order_id": order.id,
                        "move_id": order.account_move.id if order.account_move else False,
                        "session_id": order.session_id.id,
                        "previous_sale_total": order.amount_total,
                        "previous_sale_change": self.change_amount,
                        "previous_sale_currency": order.currency_id.symbol,
                        "previous_sale_is_cash": is_cash,
                        "force_login_after_order": self.pos_config_id.force_login_after_order,
                    },
                }

            return next_action

        return {"type": "ir.actions.act_window_close"}

    def action_validate(self):
        return self._execute_validation(print_invoice=False)

    def action_validate_print(self):
        return self._execute_validation(print_invoice=True)
