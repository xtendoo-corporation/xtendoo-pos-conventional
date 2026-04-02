import logging
from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class PosOrder(models.Model):
    _inherit = "pos.order"

    payment_method_ribbon = fields.Char(
        string="Cinta de método de pago",
        compute="_compute_payment_method_ribbon",
        store=False,
    )

    has_order_lines = fields.Boolean(
        string="Tiene líneas de pedido",
        compute="_compute_has_order_lines",
        store=False,
    )

    amount_untaxed = fields.Monetary(
        string="Importe base",
        compute="_compute_amount_untaxed",
        store=False,
        help="Subtotal sin impuestos calculado desde las líneas del pedido",
    )

    amount_tax = fields.Monetary(
        string="Impuestos",
        compute="_compute_amount_tax_total",
        store=True,
    )

    amount_total = fields.Monetary(
        string="Total",
        compute="_compute_amount_tax_total",
        store=True,
    )

    @api.depends("lines")
    def _compute_has_order_lines(self):
        for order in self:
            order.has_order_lines = bool(order.lines)

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
                order.payment_method_ribbon = "PAGO MÚLTIPLE"
            else:
                order.payment_method_ribbon = methods[0].name.upper()

    @api.depends("lines.price_subtotal")
    def _compute_amount_untaxed(self):
        for order in self:
            order.amount_untaxed = sum(line.price_subtotal for line in order.lines)

    @api.depends("lines.price_subtotal_incl", "lines.price_subtotal")
    def _compute_amount_tax_total(self):
        for order in self:
            total_incl = sum(line.price_subtotal_incl for line in order.lines)
            total_excl = sum(line.price_subtotal for line in order.lines)
            order.amount_tax = total_incl - total_excl
            order.amount_total = total_incl

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
            # Evitar violación NOT NULL en campos de importe
            for _f in ("amount_tax", "amount_total", "amount_return"):
                if _f not in vals:
                    vals[_f] = 0.0
        return super().create(vals_list)

    def write(self, vals):
        return super().write(vals)

    def _prepare_order_line_vals(self, product, qty=1.0):
        """
        Prepara los valores para crear una línea de pedido POS.
        """
        self.ensure_one()

        # Obtener precio desde la lista de precios
        public_price = product.lst_price
        pricelist = self.pricelist_id or self.config_id.pricelist_id
        discount = 0.0
        if pricelist:
            price_unit = pricelist._get_product_price(
                product, qty, partner=self.partner_id, uom=product.uom_id
            )
            if public_price > price_unit and public_price > 0:
                discount = (public_price - price_unit) / public_price * 100
                price_unit = public_price
        else:
            price_unit = public_price

        # Obtener impuestos aplicables del producto
        product_taxes = product.taxes_id.filtered(
            lambda t: t.company_id == self.company_id
        )

        # Aplicar posición fiscal si existe
        taxes_after_fp = product_taxes
        if self.fiscal_position_id:
            taxes_after_fp = self.fiscal_position_id.map_tax(product_taxes)

        # Calcular subtotales
        price = price_unit
        price_subtotal = price * qty
        price_subtotal_incl = price * qty

        if taxes_after_fp:
            tax_results = taxes_after_fp.compute_all(
                price,
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

    def action_validate_and_invoice(self):
        """
        Lógica completa para validar y facturar desde el backend.
        """
        self.ensure_one()
        print("=" * 60)
        print(f"[CORE] action_validate_and_invoice called: order={self.id} state={self.state}")
        if self.state not in ("draft"):
            print(f"[CORE]   state={self.state} is not 'draft' -> returning False")
            return False

        # 1. Marcar para facturar
        self.write({"to_invoice": True})
        print(f"[CORE]   to_invoice=True, calling action_pos_order_paid()")

        # 2. Validar pedido (esto crea la factura)
        self.action_pos_order_paid()
        print(f"[CORE]   after action_pos_order_paid: state={self.state}")

        # 3. Devolver acción según configuración (redirección o impresión)
        result = self._get_post_validation_action()
        print(f"[CORE]   _get_post_validation_action returned: {result.get('type')} tag={result.get('tag','')}")
        return result

    def _get_post_validation_action(self):
        """
        Calcula la acción que debe realizarse después de validar un pedido.
        """
        self.ensure_one()
        print(f"[CORE] _get_post_validation_action called: order={self.id}")

        # Configurar acción base de Nuevo Pedido
        next_action = {
            "type": "ir.actions.client",
            "tag": "pos_conventional_new_order",
            "params": {
                "config_id": self.config_id.id,
                "default_session_id": self.session_id.id,
            },
        }

        # Si está activada la opción de forzar login tras pedido, añadir flag
        if getattr(self.config_id, 'pos_force_employee_login_after_order', False):
            next_action["params"]["force_login_after_order"] = True

        # Imprimir si iface_print_auto está activado en la configuración de la caja
        # ("Impresión automática de recibo"). Este ajuste controla tanto tickets como facturas.
        if self.config_id.iface_print_auto:
            print(f"[CORE]   iface_print_auto=True -> pos_conventional_print_receipt_client")
            return {
                "type": "ir.actions.client",
                "tag": "pos_conventional_print_receipt_client",
                "params": {
                    "order_id": self.id,
                    "next_action": next_action,
                },
            }

        print(f"[CORE]   iface_print_auto=False -> pos_conventional_new_order")
        return next_action

    @api.model
    def get_order_receipt_data(self, order_id):
        """
        Devuelve los datos necesarios para imprimir un ticket desde JS.
        Formato compatible con lo que espera el frontend.
        """
        order = self.browse(order_id)
        if not order.exists():
            return {}

        return {
            "name": order.name,
            "pos_reference": order.pos_reference,
            "ticket_code": order.ticket_code,
            "date_order": order.date_order.strftime("%Y-%m-%d %H:%M:%S") if order.date_order else "",
            "amount_total": order.amount_total,
            "amount_paid": order.amount_paid,
            "amount_return": order.amount_return,
            "amount_tax": order.amount_tax,
            "currency_symbol": order.currency_id.symbol,
            "company_name": order.company_id.name,
            "company_vat": order.company_id.vat,
            "lines": [{
                "product_name": line.full_product_name or line.product_id.display_name,
                "qty": line.qty,
                "price_unit": line.price_unit,
                "price_subtotal_incl": line.price_subtotal_incl,
                "discount": line.discount,
            } for line in order.lines],
        }
