from odoo import api, fields, models, _
import logging

_logger = logging.getLogger(__name__)


class PosOrder(models.Model):
    _inherit = "pos.order"

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
            new_qty = line.qty + 1
            line.write({"qty": new_qty})
            return {"success": True, "message": _("Cantidad actualizada: %s x %s") % (new_qty, product.display_name)}

        # Crear nueva línea
        try:
            if hasattr(self, '_prepare_order_line_vals'):
                vals = self._prepare_order_line_vals(product)
            else:
                price_unit = product.lst_price
                taxes = product.taxes_id.filtered(
                    lambda t: t.company_id == self.env.company
                )
                if taxes:
                    tax_results = taxes.compute_all(
                        price_unit,
                        currency=self.currency_id or self.env.company.currency_id,
                        quantity=1.0,
                        product=product,
                    )
                    price_subtotal = tax_results["total_excluded"]
                    price_subtotal_incl = tax_results["total_included"]
                else:
                    price_subtotal = price_unit
                    price_subtotal_incl = price_unit
                vals = {
                    'order_id': self.id,
                    'product_id': product.id,
                    'full_product_name': product.display_name,
                    'qty': 1.0,
                    'price_unit': price_unit,
                    'discount': 0.0,
                    'price_subtotal': price_subtotal,
                    'price_subtotal_incl': price_subtotal_incl,
                    'tax_ids': [(6, 0, taxes.ids)],
                }
            self.env["pos.order.line"].create(vals)
            return {"success": True, "message": _("Añadido: %s") % product.display_name}
        except Exception as e:
            _logger.exception("Error al añadir producto por código de barras: %s", str(e))
            return {"success": False, "message": _("Error al añadir el producto: %s") % str(e)}
