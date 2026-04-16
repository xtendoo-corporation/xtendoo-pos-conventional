# Copyright 2024 Xtendoo
# License OPL-1
from odoo.tests.common import tagged
from odoo.exceptions import UserError
from odoo.addons.pos_conventional_core.tests.common import PosConventionalTestCommon


@tagged("pos_conventional_core", "-standard", "post_install", "-at_install")
class TestReceiptCustom(PosConventionalTestCommon):
    """Tests para pos_conventional_receipt_custom — pos.order."""

    def _render_factura_simplificada_html(self, move):
        report = self.env.ref("pos_conventional_receipt_custom.action_factura_simplificada_80mm")
        content, _report_type = report._render_qweb_html(move.ids)
        return content.decode() if isinstance(content, bytes) else content

    # ── get_factura_report_url ────────────────────────────────────────────

    def test_01_get_factura_report_url_no_invoice_returns_false(self):
        """Sin factura asociada, devuelve False."""
        session = self._open_session()
        order = self._make_draft_order(session, self.partner)
        self._add_line(order)
        self.assertFalse(order.get_factura_report_url())

    def test_02_get_factura_report_url_with_invoice_returns_url(self):
        """Con factura asociada devuelve una URL con el xmlid del informe."""
        session = self._open_session()
        order = self._make_draft_order(session, self.partner)
        self._add_line(order)
        order.write({"to_invoice": True})
        self._add_payment(order)
        order.action_pos_order_paid()
        if order.account_move:
            url = order.get_factura_report_url()
            self.assertTrue(url)
            self.assertIn("pos_conventional_receipt_custom", url)
            self.assertIn(str(order.account_move.id), url)

    # ── action_send_email — validaciones ──────────────────────────────────

    def test_03_action_send_email_no_invoice_raises(self):
        """Sin factura, action_send_email lanza UserError."""
        session = self._open_session()
        order = self._make_draft_order(session, self.partner)
        self._add_line(order)
        with self.assertRaises(UserError):
            order.action_send_email()

    def test_04_action_send_email_no_partner_raises(self):
        """Sin partner, action_send_email lanza UserError."""
        session = self._open_session()
        order = self._make_draft_order(session)
        self._add_line(order)
        with self.assertRaises(UserError):
            order.action_send_email()

    def test_05_action_send_email_partner_no_email_raises(self):
        """Partner sin email lanza UserError."""
        partner_no_email = self.env["res.partner"].create(
            {"name": "Partner Sin Email", "customer_rank": 1, "email": False}
        )
        session = self._open_session()
        order = self._make_draft_order(session, partner_no_email)
        self._add_line(order)
        order.write({"to_invoice": True})
        self._add_payment(order)
        order.action_pos_order_paid()
        with self.assertRaises(UserError):
            order.action_send_email()

    # ── get_order_receipt_data (versión extendida) ────────────────────────

    def test_06_get_order_receipt_data_extended_has_company_key(self):
        """La versión extendida incluye la clave 'company' con datos de empresa."""
        session = self._open_session()
        order = self._make_draft_order(session, self.partner)
        self._add_line(order)
        result = self.env["pos.order"].get_order_receipt_data(order.id)
        self.assertIn("company", result)
        self.assertIn("name", result["company"])
        self.assertEqual(result["company"]["name"], self.env.company.name)

    def test_07_get_order_receipt_data_extended_has_partner_key(self):
        """Con partner, la clave 'partner' contiene datos del cliente."""
        session = self._open_session()
        order = self._make_draft_order(session, self.partner)
        self._add_line(order)
        result = self.env["pos.order"].get_order_receipt_data(order.id)
        self.assertIn("partner", result)
        self.assertTrue(result["partner"])
        self.assertEqual(result["partner"]["name"], self.partner.name)

    def test_08_get_order_receipt_data_extended_no_partner_is_false(self):
        """Sin partner, la clave 'partner' es False."""
        session = self._open_session()
        order = self._make_draft_order(session)
        self._add_line(order)
        result = self.env["pos.order"].get_order_receipt_data(order.id)
        self.assertFalse(result.get("partner"))

    def test_09_get_order_receipt_data_extended_has_tax_details(self):
        """La clave 'tax_details' está presente en los datos extendidos."""
        session = self._open_session()
        order = self._make_draft_order(session, self.partner)
        self._add_line(order)
        result = self.env["pos.order"].get_order_receipt_data(order.id)
        self.assertIn("tax_details", result)

    # ── _get_receipt_tax_details ──────────────────────────────────────────

    def test_10_get_receipt_tax_details_returns_list(self):
        """_get_receipt_tax_details devuelve una lista."""
        session = self._open_session()
        order = self._make_draft_order(session, self.partner)
        self._add_line(order, self.product)
        details = order._get_receipt_tax_details()
        self.assertIsInstance(details, list)

    def test_11_get_receipt_tax_details_has_required_keys(self):
        """Cada entrada de tax_details tiene las claves id, name, amount, base."""
        session = self._open_session()
        order = self._make_draft_order(session, self.partner)
        self._add_line(order, self.product)
        details = order._get_receipt_tax_details()
        for entry in details:
            for key in ("id", "name", "amount", "base"):
                self.assertIn(key, entry, f"Clave '{key}' faltante en tax_details")

    def test_12_get_receipt_tax_details_aggregates_same_tax(self):
        """Varias líneas con el mismo impuesto se agrupan en una sola entrada."""
        session = self._open_session()
        order = self._make_draft_order(session, self.partner)
        self._add_line(order, self.product, 1.0)
        self._add_line(order, self.product, 2.0)  # mismo producto, mismo IVA
        details = order._get_receipt_tax_details()
        # IDs únicos
        ids = [d["id"] for d in details]
        self.assertEqual(len(ids), len(set(ids)), "Se esperan entradas de impuesto únicas (agrupadas)")

    def test_13_get_receipt_tax_details_empty_without_taxes(self):
        """Sin impuestos en las líneas, tax_details está vacío."""
        product_no_tax = self.env["product.product"].create(
            {
                "name": "Producto Sin IVA Test",
                "type": "consu",
                "list_price": 10.0,
                "taxes_id": [(5, 0, 0)],
                "available_in_pos": True,
            }
        )
        session = self._open_session()
        order = self._make_draft_order(session, self.partner)
        self._add_line(order, product_no_tax)
        details = order._get_receipt_tax_details()
        self.assertEqual(details, [])

    # ── action_print_factura_simplificada ─────────────────────────────────

    def test_14_action_print_factura_simplificada_no_invoice_returns_none(self):
        """Sin factura, action_print_factura_simplificada devuelve None."""
        session = self._open_session()
        order = self._make_draft_order(session, self.partner)
        self._add_line(order)
        result = order.action_print_factura_simplificada()
        self.assertIsNone(result)

    # ── get_order_receipt_data — campo company detallado ──────────────────

    def test_15_get_order_receipt_data_company_has_phone_and_email(self):
        """La clave 'company' incluye phone y email."""
        session = self._open_session()
        order = self._make_draft_order(session, self.partner)
        self._add_line(order)
        result = self.env["pos.order"].get_order_receipt_data(order.id)
        company_data = result.get("company", {})
        self.assertIn("phone", company_data)
        self.assertIn("email", company_data)

    def test_16_report_shows_standard_title_for_regular_invoice(self):
        """Una factura normal debe mantener el título estándar."""
        session = self._open_session()
        order = self._make_draft_order(session, self.partner)
        self._add_line(order)
        order.write({"to_invoice": True})
        self._add_payment(order)
        order.action_pos_order_paid()

        self.assertTrue(order.account_move)
        self.assertEqual(order.account_move.move_type, "out_invoice")

        html = self._render_factura_simplificada_html(order.account_move)

        self.assertIn("FACTURA SIMPLIFICADA:", html)
        self.assertNotIn("FACTURA SIMPLIFICADA RECTIFICATIVA", html)

    def test_17_report_shows_rectificativa_title_for_refund_invoice(self):
        """Una factura rectificativa debe mostrar el título específico."""
        session = self._open_session()
        order = self._make_draft_order(session, self.partner)
        self._add_line(order)
        order.write({"to_invoice": True})
        self._add_payment(order)
        order.action_pos_order_paid()

        self.assertTrue(order.account_move)
        refund_move = order.account_move.copy(
            default={
                "move_type": "out_refund",
                "name": "RINV/TEST/0001",
            }
        )

        html = self._render_factura_simplificada_html(refund_move)

        self.assertEqual(refund_move.move_type, "out_refund")
        self.assertIn("FACTURA SIMPLIFICADA RECTIFICATIVA:", html)

