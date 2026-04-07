import logging
from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class PosOrder(models.Model):
    _inherit = "pos.order"

    payment_method_ribbon = fields.Char(
        string="Payment Method Ribbon",
        compute="_compute_payment_method_ribbon",
        store=False,
    )

    has_order_lines = fields.Boolean(
        string="Has Order Lines",
        compute="_compute_has_order_lines",
        store=False,
    )

    amount_untaxed = fields.Monetary(
        string="Untaxed Amount",
        compute="_compute_amount_untaxed",
        store=False,
        help="Subtotal excluding taxes, computed from order lines.",
    )

    @api.depends("lines")
    def _compute_has_order_lines(self):
        for order in self:
            order.has_order_lines = bool(order.lines)

    @api.depends("lines.price_subtotal")
    def _compute_amount_untaxed(self):
        for order in self:
            order.amount_untaxed = sum(line.price_subtotal for line in order.lines)

    @api.onchange("lines")
    def _onchange_lines_recompute_totals(self):
        """
        Recalcula amount_total y amount_tax en tiempo real en la vista de formulario.

        En Odoo 19 OWL los campos readonly=True del registro padre no se incluyen
        en el payload de guardado salvo que la vista declare force_save="1".
        Este onchange calcula los valores; force_save garantiza su persistencia.
        """
        for order in self:
            lines = order.lines
            tax_total = sum(
                line.price_subtotal_incl - line.price_subtotal for line in lines
            )
            amount_total = sum(line.price_subtotal_incl for line in lines)
            currency = order.currency_id or self.env.company.currency_id
            if currency:
                order.amount_tax = currency.round(tax_total)
                order.amount_total = currency.round(amount_total)
            else:
                order.amount_tax = tax_total
                order.amount_total = amount_total


    @api.depends("payment_ids", "state")
    def _compute_payment_method_ribbon(self):
        for order in self:
            if order.state not in ("paid", "done"):
                order.payment_method_ribbon = False
                continue
            methods = order.payment_ids.filtered(lambda p: p.amount > 0).mapped("payment_method_id")
            if not methods:
                order.payment_method_ribbon = False
            elif len(methods) > 1:
                order.payment_method_ribbon = "MULTIPLE PAYMENT"
            else:
                order.payment_method_ribbon = methods[0].name.upper()

    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if "company_id" not in res or not res.get("company_id"):
            res["company_id"] = self.env.company.id
        if "amount_return" not in res:
            res["amount_return"] = 0.0
        if "amount_paid" not in res:
            res["amount_paid"] = 0.0

        session_id = self.env.context.get("default_session_id") or self.env.context.get("session_id")
        if session_id:
            session = self.env["pos.session"].browse(session_id).exists()
            if session:
                res["session_id"] = session.id
                if "pricelist_id" not in res:
                    res["pricelist_id"] = session.config_id.pricelist_id.id
                if "currency_id" not in res:
                    res["currency_id"] = session.currency_id.id
                if "partner_id" in fields_list and not res.get("partner_id"):
                    if session.config_id.default_partner_id:
                        res["partner_id"] = session.config_id.default_partner_id.id

        if not res.get("session_id"):
             active_session = self.env["pos.session"].search([
                 ("state", "=", "opened"),
                 ("config_id.pos_non_touch", "=", True)
             ], limit=1, order="id desc")
             if active_session:
                 res["session_id"] = active_session.id
        return res

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("session_id"):
                session = self.env["pos.session"].search([
                    ("user_id", "=", self.env.user.id),
                    ("state", "=", "opened"),
                    ("config_id.pos_non_touch", "=", True),
                ], limit=1, order="id desc")
                if not session:
                    session = self.env["pos.session"].search([
                        ("state", "=", "opened"),
                        ("config_id.pos_non_touch", "=", True),
                    ], limit=1, order="id desc")
                if session:
                    vals["session_id"] = session.id
                    if not vals.get("pricelist_id"):
                        vals["pricelist_id"] = session.config_id.pricelist_id.id
                    if not vals.get("currency_id"):
                        vals["currency_id"] = session.currency_id.id
            if "amount_paid" not in vals:
                vals["amount_paid"] = 0.0
            # Avoid NOT NULL violation on amount fields
            for _f in ("amount_tax", "amount_total", "amount_return"):
                if _f not in vals:
                    vals[_f] = 0.0
        return super().create(vals_list)


    def _prepare_order_line_vals(self, product, qty=1.0):
        """
        Prepara los valores para crear/actualizar una línea de pedido POS.

        Aplica la tarifa activa del pedido para determinar el precio unitario y
        el descuento. Los subtotales se calculan siempre sobre el precio efectivo
        (precio de tarifa), no sobre el precio de lista, para que los totales
        del pedido sean correctos.
        """
        self.ensure_one()

        # Precio de lista (precio público para mostrar al cliente)
        public_price = product.lst_price
        pricelist = self.pricelist_id or self.config_id.pricelist_id
        discount = 0.0

        if pricelist:
            pricelist_price = pricelist._get_product_price(
                product, qty, partner=self.partner_id, uom=product.uom_id
            )
            if public_price > pricelist_price and public_price > 0:
                # Mostrar precio de lista con descuento explícito
                discount = (public_price - pricelist_price) / public_price * 100
                price_unit = public_price
            else:
                price_unit = pricelist_price
        else:
            price_unit = public_price

        # Impuestos aplicables al producto
        product_taxes = product.taxes_id.filtered(
            lambda t: t.company_id == self.company_id
        )

        # Aplicar posición fiscal si está definida
        taxes_after_fp = product_taxes
        if self.fiscal_position_id:
            taxes_after_fp = self.fiscal_position_id.map_tax(product_taxes)

        # Precio efectivo neto = precio unitario menos descuento
        # Los subtotales siempre se calculan sobre el precio real que paga el cliente
        effective_price = price_unit * (1.0 - discount / 100.0)
        price_subtotal = effective_price * qty
        price_subtotal_incl = effective_price * qty

        if taxes_after_fp:
            tax_results = taxes_after_fp.compute_all(
                effective_price,
                currency=self.currency_id,
                quantity=qty,
                product=product,
                partner=self.partner_id,
            )
            price_subtotal = tax_results["total_excluded"]
            price_subtotal_incl = tax_results["total_included"]

        return {
            "order_id": self.id,
            "product_id": product.id,
            "full_product_name": product.display_name,
            "qty": qty,
            "price_unit": price_unit,
            "discount": discount,
            "price_subtotal": price_subtotal,
            "price_subtotal_incl": price_subtotal_incl,
            "tax_ids": [(6, 0, product_taxes.ids)],
        }

    @api.onchange("partner_id")
    def _onchange_partner_id_update_pricelist(self):
        """
        Actualiza la tarifa de precios al cambiar el cliente y recalcula líneas.

        Cuando se selecciona un cliente con tarifa asignada distinta a la activa,
        la tarifa del pedido se actualiza automáticamente y los precios de todas
        las líneas se recalculan. Si el cliente no tiene tarifa o no hay cliente,
        se restaura la tarifa por defecto de la sesión.

        Este comportamiento es equivalente al de un pedido de ventas convencional.
        """
        for order in self:
            if order.state != "draft":
                continue

            # Tarifa de respaldo: la que está configurada en la sesión/config
            config_pricelist = (
                order.config_id.pricelist_id
                or order.session_id.config_id.pricelist_id
            )

            if order.partner_id:
                partner_pricelist = order.partner_id.property_product_pricelist
                new_pricelist = partner_pricelist or config_pricelist
            else:
                # Sin cliente → tarifa por defecto de la sesión
                new_pricelist = config_pricelist

            if not new_pricelist or new_pricelist == order.pricelist_id:
                continue

            order.pricelist_id = new_pricelist
            if order.lines:
                order._recompute_lines_with_pricelist()


    def _recompute_lines_with_pricelist(self):
        """
        Recalcula price_unit, discount y subtotales de todas las líneas del pedido
        aplicando la tarifa activa (self.pricelist_id).

        Este método puede llamarse tanto desde un @api.onchange (registros virtuales)
        como sobre registros guardados. En ambos casos, asigna directamente los
        campos de la línea con los nuevos valores calculados por _prepare_order_line_vals.

        Los impuestos de la línea no se modifican: sólo dependen del producto
        y de la posición fiscal, no de la tarifa.
        """
        self.ensure_one()
        if not self.pricelist_id or not self.lines:
            return
        for line in self.lines:
            product = line.product_id
            if not product:
                continue
            qty = line.qty or 1.0
            new_vals = self._prepare_order_line_vals(product, qty)
            line.price_unit = new_vals["price_unit"]
            line.discount = new_vals["discount"]
            line.price_subtotal = new_vals["price_subtotal"]
            line.price_subtotal_incl = new_vals["price_subtotal_incl"]
        # Recalcular totales del pedido tras actualizar todas las líneas
        self._onchange_lines_recompute_totals()

    def action_validate_and_invoice(self):
        """
        Full logic to validate and invoice a POS order from the backend.
        """
        self.ensure_one()
        if self.state not in ("draft",):
            return False

        # 1. Assign default partner if missing (mirrors check() behavior)
        if not self.partner_id:
            fallback_partner = (
                getattr(self.config_id, "default_partner_id", False)
                or self.company_id.partner_id
            )
            if fallback_partner:
                self.write({"partner_id": fallback_partner.id})

        # 2. Mark for invoicing
        self.write({"to_invoice": True})

        # 3. Validate order (transitions to 'paid' state)
        self.action_pos_order_paid()

        # 4. Generate invoice only when a customer is set
        #    (action_pos_order_paid only sets state='paid',
        #    it does NOT create the account.move; we must call this explicitly)
        if not self.account_move and self.config_id.invoice_journal_id and self.partner_id:
            self._generate_pos_order_invoice()

        # 5. Return action based on configuration (redirect or print)
        return self._get_post_validation_action()

    def _get_post_validation_action(self):
        """
        Returns the client action to execute after a POS order has been validated.
        """
        self.ensure_one()

        # Base action: New Order
        next_action = {
            "type": "ir.actions.client",
            "tag": "pos_conventional_new_order",
            "params": {
                "config_id": self.config_id.id,
                "default_session_id": self.session_id.id,
            },
        }

        # If force employee login after order is enabled, propagate the flag
        if getattr(self.config_id, "pos_force_employee_login_after_order", False):
            next_action["params"]["force_login_after_order"] = True

        # Print receipt if iface_print_auto is enabled in the POS config
        # ("Automatic Receipt Printing"). This controls both ticket and invoice printing.
        if self.config_id.iface_print_auto:
            return {
                "type": "ir.actions.client",
                "tag": "pos_conventional_print_receipt_client",
                "params": {
                    "order_id": self.id,
                    "move_id": self.account_move.id if self.account_move else False,
                    "next_action": next_action,
                },
            }

        return next_action

    @api.model
    def get_order_receipt_data(self, order_id):
        """
        Returns the data required to print a receipt from JS.
        Format compatible with what the frontend expects (MockOrder/MockOrderLine).

        Sub-modules that extend this method (e.g. pos_conventional_receipt_custom)
        are called via super() and may return additional fields to be merged.
        Since pos_conventional_core loads AFTER sub-modules (as the aggregator),
        core is higher in the MRO and must call super() to invoke sub-module extensions.
        """
        order = self.browse(order_id)
        if not order.exists():
            return {}

        company = order.company_id
        currency = order.currency_id
        session = order.session_id
        config = session.config_id if session else self.env["pos.config"].browse()
        partner = order.partner_id

        result = {
            "name": order.name,
            "pos_reference": order.pos_reference,
            "ticket_code": order.ticket_code,
            "access_token": order.access_token,
            "date_order": order.date_order.strftime("%Y-%m-%d %H:%M:%S") if order.date_order else "",
            "amount_total": order.amount_total,
            "amount_paid": order.amount_paid,
            "amount_return": order.amount_return,
            "amount_tax": order.amount_tax,
            # Top-level shortcuts expected by tests and frontend
            "company_name": company.name,
            "company_vat": company.vat or "",
            "currency_symbol": currency.symbol,
            "receipt_header": config.receipt_header or "",
            "receipt_footer": config.receipt_footer or "",
            # List format compatible with MockOrder ([id, symbol, position, decimals])
            "currency_id": [
                currency.id,
                currency.symbol,
                currency.position,
                currency.decimal_places,
            ],
            "company": {
                "id": company.id,
                "name": company.name,
                "vat": company.vat or "",
                "logo": bool(company.logo),
                "country_id": {
                    "vat_label": company.country_id.vat_label or "VAT",
                } if company.country_id else {"vat_label": "VAT"},
            },
            # Cashier: [id, name] so that MockOrder.getCashierName() works
            "user_id": [order.user_id.id, order.user_id.name] if order.user_id else False,
            # Customer for MockOrder.partner_id
            "partner": {
                "id": partner.id,
                "name": partner.name,
                "address": partner.contact_address or "",
                "vat": partner.vat or "",
                "email": partner.email or "",
                "phone": partner.phone or "",
            } if partner else False,
            # Payments: list compatible with MockOrder.payment_ids
            "payment_ids": [{
                "amount": p.amount,
                "payment_method_id": [p.payment_method_id.id, p.payment_method_id.name],
            } for p in order.payment_ids],
            "lines": [{
                "id": line.id,
                "product_id": [
                    line.product_id.id,
                    line.full_product_name or line.product_id.display_name,
                ],
                "qty": line.qty,
                "price_unit": line.price_unit,
                "price_subtotal": line.price_subtotal,
                "price_subtotal_incl": line.price_subtotal_incl,
                "discount": line.discount,
                "customer_note": line.note or "",
                "tax_ids": [t.name for t in line.tax_ids_after_fiscal_position],
            } for line in order.lines],
        }

        # Allow sub-modules loaded before core (receipt_custom, etc.) to enrich
        # the result via the super() chain. Since core is higher in MRO, calling
        # super() here invokes those sub-module extensions.
        parent = super()
        if hasattr(parent, "get_order_receipt_data"):
            enrichments = parent.get_order_receipt_data(order_id)
            if isinstance(enrichments, dict):
                for key, val in enrichments.items():
                    if key == "company" and isinstance(val, dict):
                        result.setdefault("company", {}).update(val)
                    elif val is not False:
                        result[key] = val

        return result

