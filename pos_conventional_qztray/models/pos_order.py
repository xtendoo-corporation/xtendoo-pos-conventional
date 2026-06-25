import re

from odoo import fields, models


class PosOrder(models.Model):
    _inherit = "pos.order"

    def _qztray_receipt_line_width(self):
        return 42

    def _qztray_receipt_clean(self, value):
        value = str(value or "")
        value = re.sub(r"\s+", " ", value.replace("\r", "\n")).strip()
        return value

    def _qztray_receipt_center(self, value, width=None):
        width = width or self._qztray_receipt_line_width()
        return self._qztray_receipt_clean(value)[:width].center(width)

    def _qztray_receipt_pair(self, left, right, width=None):
        width = width or self._qztray_receipt_line_width()
        left = self._qztray_receipt_clean(left)
        right = self._qztray_receipt_clean(right)
        space = max(width - len(left) - len(right), 1)
        return f"{left[:width - len(right) - 1]}{' ' * space}{right}"

    def _qztray_receipt_wrap(self, value, width=None):
        width = width or self._qztray_receipt_line_width()
        value = self._qztray_receipt_clean(value)
        if not value:
            return []
        words = value.split(" ")
        lines = []
        current = ""
        for word in words:
            if len(word) > width:
                if current:
                    lines.append(current)
                    current = ""
                lines.extend(word[i : i + width] for i in range(0, len(word), width))
                continue
            candidate = f"{current} {word}".strip()
            if len(candidate) <= width:
                current = candidate
            else:
                lines.append(current)
                current = word
        if current:
            lines.append(current)
        return lines

    def _qztray_receipt_money(self, amount):
        symbol = "EUR" if self.currency_id.name == "EUR" else (self.currency_id.symbol or "")
        return f"{amount:.2f} {symbol}".strip()

    def _get_pos_conventional_qztray_raw_receipt(self):
        self.ensure_one()
        width = self._qztray_receipt_line_width()
        company = self.company_id
        move = self.account_move
        separator = "-" * width
        lines = ["\x1b@", "\x1bt\x13"]

        if self.config_id.receipt_header:
            for header_line in self.config_id.receipt_header.splitlines():
                lines.extend(self._qztray_receipt_wrap(header_line, width))
                lines.append("")

        lines.append("\x1bE\x01")
        lines.append(self._qztray_receipt_clean(company.name).upper()[:width])
        lines.append("\x1bE\x00")
        if company.street:
            lines.extend(self._qztray_receipt_wrap(company.street, width))
        city_line = " ".join(part for part in [company.zip, company.city] if part)
        if city_line:
            lines.extend(self._qztray_receipt_wrap(city_line, width))
        if company.vat:
            lines.append(self._qztray_receipt_clean(company.vat)[:width])
        lines.append(separator)

        title = "FACTURA SIMPLIFICADA RECTIFICATIVA:" if move and move.move_type == "out_refund" else "FACTURA SIMPLIFICADA:"
        document_name = move.name if move else self.name
        lines.append("\x1bE\x01")
        lines.append(f"{title} {document_name}"[:width])
        lines.append("\x1bE\x00")
        date_order = fields.Datetime.context_timestamp(self, self.date_order)
        lines.append(f"FECHA: {date_order.strftime('%d/%m/%Y %H:%M')}")

        if self.partner_id:
            lines.append("")
            lines.append("CLIENTE:")
            lines.extend(self._qztray_receipt_wrap(self.partner_id.name, width))
            if self.partner_id.vat:
                lines.append(f"NIF: {self.partner_id.vat}"[:width])

        lines.append(separator)
        lines.append(self._qztray_receipt_pair("Nombre", "UD   TOTAL", width))
        lines.append(separator)
        for order_line in self.lines:
            line_name = order_line.full_product_name or order_line.product_id.display_name
            amount = self._qztray_receipt_money(order_line.price_subtotal_incl)
            qty = f"{order_line.qty:.0f}"
            wrapped_name = self._qztray_receipt_wrap(line_name, width - 14) or [""]
            lines.append(f"{wrapped_name[0]:<{width - 14}} {qty:>3} {amount:>9}"[:width])
            lines.extend(wrapped_name[1:])

        lines.append(separator)
        lines.append(self._qztray_receipt_pair("Base", "Impuesto Cuota", width))
        tax_rows = []
        if move and move.tax_totals:
            for subtotal in move.tax_totals.get("subtotals", []):
                for tax_group in subtotal.get("tax_groups", []):
                    tax_rows.append((
                        tax_group.get("base_amount_currency", 0.0),
                        tax_group.get("group_name", ""),
                        tax_group.get("tax_amount_currency", 0.0),
                    ))
        else:
            tax_rows.append((self.amount_total - self.amount_tax, "IVA", self.amount_tax))
        for base, tax_name, tax_amount in tax_rows:
            left = self._qztray_receipt_money(base)
            right = f"{self._qztray_receipt_clean(tax_name)[:8]} {self._qztray_receipt_money(tax_amount)}"
            lines.append(self._qztray_receipt_pair(left, right, width))

        lines.append(separator)
        lines.append("\x1bE\x01")
        lines.append(self._qztray_receipt_pair("TOTAL", self._qztray_receipt_money(self.amount_total), width))
        lines.append("\x1bE\x00")
        payment_names = ", ".join(self.payment_ids.mapped("payment_method_id.name"))
        if payment_names:
            lines.append(self._qztray_receipt_center(f"Pagado: {payment_names}", width))
        lines.append(separator)

        if self.config_id.receipt_footer:
            for footer_line in self.config_id.receipt_footer.splitlines():
                lines.extend(self._qztray_receipt_wrap(footer_line, width))
                lines.append("")

        lines.append(self._qztray_receipt_center("Gracias por su visita", width))
        if self.user_id:
            lines.append(self._qztray_receipt_center(f"Atendido por: {self.user_id.name}", width))
        lines.extend(["", "", "", "\x1bd\x08", "\x1dV\x00"])
        centered_lines = [
            line if not line or line[0] in ("\x1b", "\x1d") else f"   {line}"
            for line in lines
        ]
        return "\n".join(centered_lines)

    def get_pos_conventional_qztray_raw_receipt(self):
        self.ensure_one()
        return self._get_pos_conventional_qztray_raw_receipt()

    def _pos_conventional_qztray_enrich_print_action(self, action):
        self.ensure_one()
        if not isinstance(action, dict):
            return action
        if action.get("tag") not in (
            "pos_conventional_print_receipt_client",
            "pos_conventional_print_receipt_window",
        ):
            return action

        params = dict(action.get("params") or {})
        params["use_qztray"] = bool(self.config_id.pos_print_receipt_with_qztray)
        original_report_name = "pos_conventional_receipt_custom.report_factura_simplificada_80mm"
        params.setdefault("report_name", original_report_name)
        if params["use_qztray"]:
            params["printer_report_name"] = original_report_name
            params["report_name"] = "pos_conventional_qztray.report_pos_order_80mm_qztray"
            params["report_res_id"] = self.id
            params["raw_receipt"] = True
        action["params"] = params
        if params["use_qztray"] and action.get("tag") == "pos_conventional_print_receipt_window":
            action["tag"] = "pos_conventional_print_receipt_qztray_window"
        return action

    def action_print_factura_simplificada(self):
        self.ensure_one()
        if not self.config_id.pos_print_receipt_with_qztray:
            return super().action_print_factura_simplificada()
        return {
            "type": "ir.actions.client",
            "tag": "pos_conventional_print_receipt_qztray_window",
            "params": {
                "use_qztray": True,
                "raw_receipt": True,
                "order_id": self.id,
                "report_res_id": self.id,
                "move_id": self.account_move.id if self.account_move else False,
                "printer_report_name": "pos_conventional_receipt_custom.report_factura_simplificada_80mm",
                "report_name": "pos_conventional_qztray.report_pos_order_80mm_qztray",
            },
        }

    def _get_pos_conventional_qztray_print_params(self):
        self.ensure_one()
        original_report_name = "pos_conventional_receipt_custom.report_factura_simplificada_80mm"
        return {
            "use_qztray": bool(self.config_id.pos_print_receipt_with_qztray),
            "order_id": self.id,
            "move_id": self.account_move.id if self.account_move else False,
            "printer_report_name": original_report_name,
            "report_name": "pos_conventional_qztray.report_pos_order_80mm_qztray",
            "report_res_id": self.id,
            "raw_receipt": True,
        }

    def _get_post_validation_action(self):
        action = super()._get_post_validation_action()
        return self._pos_conventional_qztray_enrich_print_action(action)

    def action_pos_convention_pay_with_method(self, payment_method_id, force_print=False):
        action = super().action_pos_convention_pay_with_method(
            payment_method_id,
            force_print=force_print,
        )
        return self._pos_conventional_qztray_enrich_print_action(action)
