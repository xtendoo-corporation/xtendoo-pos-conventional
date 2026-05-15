from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.fields import Command
from odoo import fields
from odoo.tests.common import tagged

from odoo.addons.pos_conventional_core.tests.common import PosConventionalTestCommon


@tagged("pos_conventional_barcode_scanner", "-at_install", "post_install")
class TestPosConventionalBarcodeScanner(PosConventionalTestCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.session = cls.env["pos.session"].with_context(skip_auto_open=True).create(
            {"config_id": cls.pos_config.id, "user_id": cls.env.uid}
        )
        cls.session.write({"state": "opened", "start_at": fields.Datetime.now()})
        cls.duplicate_product = cls.env["product.product"].create(
            {
                "name": "Producto Barcode Duplicado 1",
                "type": "consu",
                "list_price": 20.0,
                "barcode": "TST-DUPLICATE-1",
                "sale_ok": True,
                "available_in_pos": True,
                "property_account_income_id": cls.income_account.id if cls.income_account else False,
            }
        )
        cls.ambiguous_product = cls.env["product.product"].create(
            {
                "name": "Producto Barcode Duplicado 2",
                "type": "consu",
                "list_price": 21.0,
                "barcode": "TST-DUPLICATE-2",
                "sale_ok": True,
                "available_in_pos": True,
                "property_account_income_id": cls.income_account.id if cls.income_account else False,
            }
        )
        cls.hidden_product = cls.env["product.product"].create(
            {
                "name": "Producto No POS",
                "type": "consu",
                "list_price": 30.0,
                "barcode": "TST-HIDDEN",
                "sale_ok": True,
                "available_in_pos": False,
                "property_account_income_id": cls.income_account.id if cls.income_account else False,
            }
        )

    def _new_order(self, **extra_vals):
        vals = {
            "session_id": self.session.id,
            "config_id": self.session.config_id.id,
            "partner_id": self.partner.id,
            "pricelist_id": self.session.config_id.pricelist_id.id,
            "currency_id": self.session.currency_id.id,
            "state": "draft",
            **extra_vals,
        }
        return self.env["pos.order"].with_context(skip_completeness_check=True).new(vals)

    def test_helper_methods_return_expected_values(self):
        order = self._new_order(name=False)

        self.assertEqual(order._barcode_scan_allowed_states(), {"draft"})
        self.assertTrue(order._is_barcode_scan_allowed())
        self.assertEqual(
            order._get_barcode_scan_product_domain("TST0001BARCODE"),
            [
                ("barcode", "=", "TST0001BARCODE"),
                ("sale_ok", "=", True),
                ("available_in_pos", "=", True),
            ],
        )
        self.assertEqual(
            order._prepare_scanned_order_line_values(self.product_barcode)["product_id"],
            self.product_barcode.id,
        )
        self.assertEqual(
            order._barcode_scan_log_prefix(),
            "[pos_conventional_barcode_scanner] [pos.order(new)]",
        )

    def test_find_barcode_scan_products_only_returns_pos_saleable_products(self):
        order = self._new_order()

        self.assertEqual(order._find_barcode_scan_products("TST0001BARCODE"), self.product_barcode)
        self.assertFalse(order._find_barcode_scan_products(self.hidden_product.barcode))

    def test_scan_ignores_empty_or_whitespace_barcodes(self):
        order = self._new_order()

        self.assertFalse(order.on_barcode_scanned(""))
        self.assertFalse(order.on_barcode_scanned("   "))
        self.assertEqual(order.action_scan_barcode("   ")["status"], "ignored")
        self.assertFalse(order.lines)

    def test_scan_creates_line_on_unsaved_order(self):
        order = self._new_order()

        result = order.on_barcode_scanned("TST0001BARCODE")

        self.assertFalse(result)
        self.assertEqual(len(order.lines), 1)
        self.assertEqual(order.lines.product_id, self.product_barcode)
        self.assertEqual(order.lines.qty, 1.0)
        self.assertGreater(order.amount_total, 0.0)

    def test_scan_increments_existing_line_on_unsaved_order(self):
        line_vals = self._new_order()._prepare_order_line_vals(self.product_barcode, qty=1.0)
        line_vals.pop("order_id", None)
        order = self._new_order(lines=[Command.create(line_vals)])

        result = order.on_barcode_scanned("TST0001BARCODE")

        self.assertFalse(result)
        self.assertEqual(len(order.lines), 1)
        self.assertEqual(order.lines.qty, 2.0)

    def test_scan_warns_when_barcode_not_found(self):
        order = self._new_order()

        result = order.on_barcode_scanned("UNKNOWN")

        self.assertEqual(result["warning"]["title"], "Escaneo de código de barras")
        self.assertIn("No se ha encontrado ningún producto disponible en POS", result["warning"]["message"])
        self.assertFalse(order.lines)

    def test_scan_warns_when_barcode_is_ambiguous(self):
        order = self._new_order()

        with patch.object(
            type(order),
            "_find_barcode_scan_products",
            autospec=True,
            return_value=self.duplicate_product | self.ambiguous_product,
        ):
            result = order.on_barcode_scanned("TST-DUPLICATE")

        self.assertEqual(result["warning"]["title"], "Escaneo de código de barras")
        self.assertIn("varios productos disponibles en POS", result["warning"]["message"])
        self.assertFalse(order.lines)

    def test_scan_warns_when_order_is_not_editable(self):
        order = self._new_order(state="paid")

        result = order.on_barcode_scanned("TST0001BARCODE")

        self.assertEqual(result["warning"]["title"], "Escaneo de código de barras")
        self.assertIn("El pedido no es editable", result["warning"]["message"])
        self.assertFalse(order.lines)

    def test_action_scan_barcode_raises_when_order_is_not_editable(self):
        order = self._make_draft_order(self.session, partner=self.partner)
        order.state = "paid"

        with self.assertRaises(UserError):
            order.action_scan_barcode("TST0001BARCODE")

    def test_action_scan_barcode_creates_and_increments_on_saved_order(self):
        order = self._make_draft_order(self.session, partner=self.partner)

        create_result = order.action_scan_barcode("TST0001BARCODE")
        increment_result = order.action_scan_barcode("TST0001BARCODE")

        self.assertEqual(create_result["status"], "created")
        self.assertEqual(increment_result["status"], "incremented")
        self.assertEqual(len(order.lines), 1)
        self.assertEqual(order.lines.product_id, self.product_barcode)
        self.assertEqual(order.lines.qty, 2.0)
        self.assertGreater(order.amount_total, 0.0)

    def test_action_scan_barcode_raises_on_error(self):
        order = self._make_draft_order(self.session, partner=self.partner)

        with self.assertRaises(UserError):
            order.action_scan_barcode("UNKNOWN")




