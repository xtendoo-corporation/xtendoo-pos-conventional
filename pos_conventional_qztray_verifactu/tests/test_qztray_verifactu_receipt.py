from odoo.tests.common import tagged

from odoo.addons.pos_conventional_verifactu.tests.test_verifactu_receipt import (
    AEAT_QR_URL,
    PosConventionalVerifactuTestCommon,
    _empty_qr_compute,
)

QR_STORE_PREFIX = "\x1d(k"


@tagged("pos_conventional_core", "-standard", "post_install", "-at_install")
class TestQztrayVerifactuReceipt(PosConventionalVerifactuTestCommon):
    def test_qr_command_encodes_esc_pos_bytes(self):
        order = self._make_order()
        command = order._qztray_receipt_qr_command(AEAT_QR_URL)
        raw_bytes = command.encode("cp858")
        data = AEAT_QR_URL.encode("ascii")
        store_length = (len(data) + 3).to_bytes(2, "little")
        self.assertTrue(raw_bytes.startswith(b"\x1d(k\x04\x001A2\x00"))
        self.assertIn(b"\x1d(k" + store_length + b"1P0" + data, raw_bytes)
        self.assertTrue(raw_bytes.endswith(b"\x1d(k\x03\x001Q0"))

    def test_qr_command_supports_store_length_above_127(self):
        order = self._make_order()
        value = "X" * 200
        raw_bytes = order._qztray_receipt_qr_command(value).encode("cp858")
        self.assertIn(b"\x1d(k\xcb\x001P0" + value.encode(), raw_bytes)

    def test_raw_receipt_prints_qr_before_footer(self):
        self._patch_qr("pos.order")
        order = self._make_order()
        receipt = order._get_pos_conventional_qztray_raw_receipt()
        self.assertIn("QR tributario:", receipt)
        self.assertIn("VERI*FACTU", receipt)
        self.assertIn(AEAT_QR_URL, receipt)
        self.assertIn(
            f"Factura simplificada: {order.l10n_es_edi_verifactu_get_invoice_name()}",
            receipt,
        )
        self.assertLess(
            receipt.index(AEAT_QR_URL), receipt.index("Gracias por su visita")
        )
        qr_line = next(line for line in receipt.split("\n") if AEAT_QR_URL in line)
        self.assertTrue(qr_line.startswith(QR_STORE_PREFIX))
        receipt.encode("cp858")

    def test_raw_receipt_prints_qr_before_config_footer(self):
        self._patch_qr("pos.order")
        self.pos_config.receipt_footer = "Pie de ticket\nSegunda línea"
        order = self._make_order()
        receipt = order._get_pos_conventional_qztray_raw_receipt()
        self.assertLess(receipt.index("VERI*FACTU"), receipt.index("Pie de ticket"))
        self.assertIn("   Segunda línea", receipt)

    def test_raw_receipt_without_qr_is_unchanged(self):
        self._patch_qr("pos.order", _empty_qr_compute)
        order = self._make_order()
        receipt = order._get_pos_conventional_qztray_raw_receipt()
        self.assertNotIn("QR tributario:", receipt)
        self.assertNotIn(QR_STORE_PREFIX, receipt)
        self.assertIn("Gracias por su visita", receipt)

    def test_raw_receipt_non_simplified_label(self):
        self._patch_qr("pos.order")
        refunded = self._make_order()
        refund = self._make_order(self.partner)
        refund.write(
            {
                "refunded_order_id": refunded.id,
                "l10n_es_edi_verifactu_refund_reason": "R1",
            }
        )
        receipt = refund._get_pos_conventional_qztray_raw_receipt()
        self.assertIn("\x1ba\x01Factura: ", receipt)

    def test_qztray_order_report_prints_verifactu_block(self):
        self._patch_qr("pos.order")
        order = self._make_order()
        html = self._render(
            "pos_conventional_qztray.action_pos_order_80mm_qztray", order
        )
        self.assertIn("pos-conventional-verifactu", html)
        self.assertIn("QR tributario:", html)

    def test_qztray_standard_invoice_report_prints_verifactu_block(self):
        self._patch_qr("account.move")
        invoice = self._make_invoice()
        html = self._render(
            "pos_conventional_qztray.action_factura_simplificada_80mm_standard_qztray",
            invoice,
        )
        self.assertIn("pos-conventional-verifactu", html)
        self.assertLess(
            html.index("QR tributario:"), html.index("Gracias por su visita")
        )
