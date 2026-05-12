from odoo import api, models, _
import logging

_logger = logging.getLogger(__name__)


class PosOrder(models.Model):
    _inherit = "pos.order"

    def _prepare_barcode_line_vals_from_scan(self, product, line_vals=None):
        """Combina los valores calculados del escaneo con la estructura estándar de línea POS."""
        self.ensure_one()
        base_vals = self._prepare_barcode_line_vals(product, qty=1.0)
        if not line_vals:
            return base_vals

        qty = line_vals.get("qty") or base_vals["qty"]
        price_unit = line_vals.get("price_unit", base_vals["price_unit"])
        discount = line_vals.get("discount", base_vals.get("discount", 0.0))
        tax_ids = line_vals.get("tax_ids")
        if tax_ids is None:
            taxes = self.env["account.tax"].browse(base_vals["tax_ids"][0][2])
        else:
            taxes = self.env["account.tax"].browse(tax_ids)

        price = price_unit * (1 - discount / 100.0)
        currency = self.currency_id or self.env.company.currency_id
        if taxes:
            tax_results = taxes.compute_all(
                price,
                currency=currency,
                quantity=qty,
                product=product,
                partner=self.partner_id,
            )
            price_subtotal = tax_results["total_excluded"]
            price_subtotal_incl = tax_results["total_included"]
        else:
            price_subtotal = price * qty
            price_subtotal_incl = price * qty

        base_vals.update(
            {
                "full_product_name": line_vals.get(
                    "full_product_name", base_vals["full_product_name"]
                ),
                "qty": qty,
                "price_unit": price_unit,
                "discount": discount,
                "price_subtotal": price_subtotal,
                "price_subtotal_incl": price_subtotal_incl,
                "tax_ids": [(6, 0, taxes.ids)],
            }
        )
        return base_vals

    def _prepare_barcode_line_vals(self, product, qty=1.0):
        """Prepara los valores de línea usados al crear o acumular un producto escaneado."""
        self.ensure_one()
        if hasattr(self, "_prepare_order_line_vals"):
            return self._prepare_order_line_vals(product, qty)

        price_unit = product.lst_price
        taxes = product.taxes_id.filtered(lambda t: t.company_id == self.env.company)
        if taxes:
            tax_results = taxes.compute_all(
                price_unit,
                currency=self.currency_id or self.env.company.currency_id,
                quantity=qty,
                product=product,
            )
            price_subtotal = tax_results["total_excluded"]
            price_subtotal_incl = tax_results["total_included"]
        else:
            price_subtotal = price_unit * qty
            price_subtotal_incl = price_unit * qty
        return {
            "order_id": self.id,
            "product_id": product.id,
            "full_product_name": product.display_name,
            "qty": qty,
            "price_unit": price_unit,
            "discount": 0.0,
            "price_subtotal": price_subtotal,
            "price_subtotal_incl": price_subtotal_incl,
            "tax_ids": [(6, 0, taxes.ids)],
        }

    def _recompute_barcode_order_amounts(self):
        """Recalcula y persiste los totales del pedido tras cambios por barcode."""
        self.ensure_one()
        if hasattr(self, "_compute_prices"):
            try:
                self._compute_prices()
                return
            except Exception:
                _logger.exception(
                    "Error al recalcular totales con _compute_prices() para el pedido %s",
                    self.id,
                )

        refund_factor = -1 if self.is_refund else 1
        tax_total = refund_factor * sum(
            line.price_subtotal_incl - line.price_subtotal for line in self.lines
        )
        amount_total = refund_factor * sum(line.price_subtotal_incl for line in self.lines)
        currency = self.currency_id or self.env.company.currency_id

        if currency:
            tax_total = currency.round(tax_total)
            amount_total = currency.round(amount_total)

        self.write({
            "amount_tax": tax_total,
            "amount_total": amount_total,
        })

    @api.model
    def get_product_line_data_by_barcode(
        self, barcode, pricelist_id=False, fiscal_position_id=False, partner_id=False
    ):
        """
        Busca un producto por código de barras y devuelve los datos necesarios
        para crear una línea de pedido POS en el backend.
        """
        Product = self.env["product.product"]
        product = Product.search([("barcode", "=", barcode)], limit=1)

        # Fallback: buscar por referencia interna (default_code)
        if not product:
            product = Product.search([("default_code", "=", barcode)], limit=1)

        if not product:
            return {
                "success": False,
                "message": _("No se encontró ningún producto con el código: %s") % barcode,
            }

        # Obtener precio desde la lista de precios
        public_price = product.lst_price
        price_unit = public_price
        discount = 0.0

        if pricelist_id:
            pricelist = self.env["product.pricelist"].browse(pricelist_id)
            partner = self.env["res.partner"].browse(partner_id) if partner_id else False
            price_unit = pricelist._get_product_price(
                product, 1.0, partner=partner, uom=product.uom_id
            )

            if public_price > price_unit and public_price > 0:
                discount = (public_price - price_unit) / public_price * 100
                price_unit = public_price

        # Obtener impuestos aplicables
        taxes = product.taxes_id.filtered(lambda t: t.company_id == self.env.company)

        # Aplicar posición fiscal si existe
        if fiscal_position_id:
            fiscal_position = self.env["account.fiscal.position"].browse(fiscal_position_id)
            taxes = fiscal_position.map_tax(taxes)

        return {
            "success": True,
            "product": {
                "id": product.id,
                "display_name": product.display_name,
            },
            "line_vals": {
                "full_product_name": product.display_name,
                "qty": 1.0,
                "price_unit": price_unit,
                "discount": discount,
                "tax_ids": taxes.ids,
            },
        }

    def add_product_by_barcode(self, barcode=None, product_id=None, line_vals=None):
        """
        Añade un producto al pedido POS mediante código de barras o product_id.
        """
        self.ensure_one()
        if self.state != "draft":
            return {
                "success": False,
                "message": _("No se pueden añadir productos a un pedido que no está en borrador."),
            }

        Product = self.env["product.product"]
        if product_id:
            product = Product.browse(product_id)
            if not product.exists():
                return {"success": False, "message": _("Producto no encontrado con ID: %s") % product_id}
        elif barcode:
            product = Product.search([("barcode", "=", barcode)], limit=1)
            if not product:
                product = Product.search([("default_code", "=", barcode)], limit=1)
            if not product:
                return {"success": False, "message": _("No se encontró ningún producto con el código: %s") % barcode}
        else:
            return {"success": False, "message": _("Debe proporcionar un código de barras o ID de producto.")}

        # Buscar si ya existe una línea con este producto
        existing_line = self.lines.filtered(lambda l: l.product_id.id == product.id)
        if existing_line:
            line = existing_line[0]
            qty_to_add = (line_vals or {}).get("qty") or 1.0
            new_qty = line.qty + qty_to_add
            price_unit = line.price_unit
            discount = line.discount or 0.0
            taxes = line.tax_ids
            price = price_unit * (1 - discount / 100.0)
            currency = self.currency_id or self.env.company.currency_id

            if taxes:
                tax_results = taxes.compute_all(
                    price,
                    currency=currency,
                    quantity=new_qty,
                    product=product,
                    partner=self.partner_id,
                )
                price_subtotal = tax_results["total_excluded"]
                price_subtotal_incl = tax_results["total_included"]
            else:
                price_subtotal = price * new_qty
                price_subtotal_incl = price * new_qty

            line.write(
                {
                    "full_product_name": line.full_product_name or product.display_name,
                    "qty": new_qty,
                    "price_unit": price_unit,
                    "discount": discount,
                    "price_subtotal": price_subtotal,
                    "price_subtotal_incl": price_subtotal_incl,
                    "tax_ids": [(6, 0, taxes.ids)],
                }
            )
            self._recompute_barcode_order_amounts()
            return {"success": True, "message": _("Cantidad actualizada: %s x %s") % (new_qty, product.display_name)}

        # Crear nueva línea
        try:
            vals = self._prepare_barcode_line_vals_from_scan(product, line_vals=line_vals)
            self.env["pos.order.line"].create(vals)
            self._recompute_barcode_order_amounts()
            return {"success": True, "message": _("Añadido: %s") % product.display_name}
        except Exception as e:
            _logger.exception("Error al añadir producto por código de barras: %s", str(e))
            return {"success": False, "message": _("Error al añadir el producto: %s") % str(e)}
