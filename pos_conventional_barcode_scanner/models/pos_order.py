import logging

from odoo import models
from odoo.exceptions import UserError
from odoo.fields import Command
from odoo.tools.translate import _

_logger = logging.getLogger(__name__)


class PosOrder(models.Model):
    _name = "pos.order"
    _inherit = ["pos.order", "barcodes.barcode_events_mixin"]

    def _barcode_scan_log_prefix(self):
        self.ensure_one()
        order_ref = self.name or f"pos.order({self.id or 'new'})"
        return f"[pos_conventional_barcode_scanner] [{order_ref}]"

    def _barcode_scan_warning(self, message, *, raise_on_error=False):
        self.ensure_one()
        _logger.warning("%s %s", self._barcode_scan_log_prefix(), message)
        if raise_on_error:
            raise UserError(message)
        return {
            "warning": {
                "title": _("Escaneo de código de barras"),
                "message": message,
            }
        }

    def _barcode_scan_allowed_states(self):
        return {"draft"}

    def _is_barcode_scan_allowed(self):
        self.ensure_one()
        return self.state in self._barcode_scan_allowed_states()

    def _get_barcode_scan_product_domain(self, barcode):
        self.ensure_one()
        return [
            ("barcode", "=", barcode),
            ("sale_ok", "=", True),
            ("available_in_pos", "=", True),
        ]

    def _find_barcode_scan_products(self, barcode):
        self.ensure_one()
        return self.env["product.product"].search(
            self._get_barcode_scan_product_domain(barcode),
            limit=2,
        )

    def _get_existing_scanned_product_line(self, product):
        self.ensure_one()
        return self.lines.filtered(
            lambda line: not getattr(line, "display_type", False) and line.product_id == product
        )[:1]

    def _prepare_scanned_order_line_values(self, product):
        self.ensure_one()
        if hasattr(self, "_prepare_order_line_vals"):
            vals = dict(self._prepare_order_line_vals(product, qty=1.0))
        else:
            vals = {
                "order_id": self.id,
                "product_id": product.id,
                "full_product_name": product.display_name,
                "qty": 1.0,
                "price_unit": product.lst_price,
                "discount": 0.0,
                "price_subtotal": product.lst_price,
                "price_subtotal_incl": product.lst_price,
                "tax_ids": [(6, 0, product.taxes_id.ids)],
            }

        if not self.id:
            vals.pop("order_id", None)
        return vals

    def _prepare_existing_scanned_line_update_values(self, line, qty_to_add=1.0):
        self.ensure_one()
        qty = (line.qty or 0.0) + qty_to_add
        price_unit = line.price_unit or 0.0
        discount = line.discount or 0.0
        taxes = line.tax_ids
        price = price_unit * (1 - discount / 100.0)
        currency = self.currency_id or self.env.company.currency_id

        if taxes:
            tax_results = taxes.compute_all(
                price,
                currency=currency,
                quantity=qty,
                product=line.product_id,
                partner=self.partner_id,
            )
            price_subtotal = tax_results["total_excluded"]
            price_subtotal_incl = tax_results["total_included"]
        else:
            price_subtotal = price * qty
            price_subtotal_incl = price * qty

        return {
            "qty": qty,
            "price_subtotal": price_subtotal,
            "price_subtotal_incl": price_subtotal_incl,
        }

    def _recompute_barcode_scan_totals(self):
        self.ensure_one()
        if hasattr(self, "_compute_prices"):
            try:
                self._compute_prices()
                return
            except Exception:
                _logger.exception(
                    "%s Error al recalcular totales con _compute_prices()",
                    self._barcode_scan_log_prefix(),
                )

        if hasattr(self, "_get_amounts_from_lines"):
            amount_tax, amount_total = self._get_amounts_from_lines()
            self.update(
                {
                    "amount_tax": amount_tax,
                    "amount_total": amount_total,
                }
            )

    def _apply_scanned_barcode(self, barcode, *, raise_on_error=False):
        self.ensure_one()
        barcode = (barcode or "").strip()
        if not barcode:
            return {"status": "ignored"}

        _logger.info("%s Escaneo recibido: %s", self._barcode_scan_log_prefix(), barcode)

        if not self._is_barcode_scan_allowed():
            return self._barcode_scan_warning(
                _(
                    "El pedido no es editable. No se pueden añadir productos por código de barras."
                ),
                raise_on_error=raise_on_error,
            )

        products = self._find_barcode_scan_products(barcode)
        if not products:
            return self._barcode_scan_warning(
                _(
                    "No se ha encontrado ningún producto disponible en POS con el código de barras '%(barcode)s'.",
                    barcode=barcode,
                ),
                raise_on_error=raise_on_error,
            )
        if len(products) > 1:
            return self._barcode_scan_warning(
                _(
                    "Se han encontrado varios productos disponibles en POS con el código de barras '%(barcode)s'. No se añadirá ningún producto automáticamente.",
                    barcode=barcode,
                ),
                raise_on_error=raise_on_error,
            )

        product = products[0]
        existing_line = self._get_existing_scanned_product_line(product)
        if existing_line:
            update_vals = self._prepare_existing_scanned_line_update_values(existing_line, qty_to_add=1.0)
            existing_line.update(update_vals)
            self._recompute_barcode_scan_totals()
            _logger.info(
                "%s Línea existente incrementada para %s. Nueva cantidad: %s",
                self._barcode_scan_log_prefix(),
                product.display_name,
                existing_line.qty,
            )
            return {
                "status": "incremented",
                "product_id": product.id,
                "line_id": existing_line.id or False,
                "quantity": existing_line.qty,
            }

        line_vals = self._prepare_scanned_order_line_values(product)
        if self.id:
            self.env["pos.order.line"].create(line_vals)
        else:
            self.update({"lines": [Command.create(line_vals)]})

        self._recompute_barcode_scan_totals()
        new_line = self.lines.filtered(
            lambda line: not getattr(line, "display_type", False) and line.product_id == product
        )[-1:]
        _logger.info(
            "%s Nueva línea creada para %s.",
            self._barcode_scan_log_prefix(),
            product.display_name,
        )
        return {
            "status": "created",
            "product_id": product.id,
            "line_id": new_line.id or False,
            "quantity": new_line.qty if new_line else 1.0,
        }

    def on_barcode_scanned(self, barcode):
        self.ensure_one()
        result = self._apply_scanned_barcode(barcode, raise_on_error=False)
        if result.get("warning"):
            return result
        return False

    def action_scan_barcode(self, barcode):
        self.ensure_one()
        return self._apply_scanned_barcode(barcode, raise_on_error=True)


