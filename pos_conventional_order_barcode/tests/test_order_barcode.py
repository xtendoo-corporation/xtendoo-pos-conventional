# Copyright 2024 Xtendoo
# License OPL-1
from odoo.tests.common import tagged
from odoo.addons.pos_conventional_core.tests.common import PosConventionalTestCommon


@tagged("pos_conventional", "-standard")
class TestPosOrderBarcode(PosConventionalTestCommon):
    """Tests para get_product_line_data_by_barcode / add_product_by_barcode."""

    # ── get_product_line_data_by_barcode ──────────────────────────────────

    def test_01_found_by_barcode(self):
        """Busca un producto por código de barras y devuelve success=True."""
        result = self.env["pos.order"].get_product_line_data_by_barcode(
            "TST0001BARCODE"
        )
        self.assertTrue(result.get("success"))
        self.assertEqual(result["product"]["id"], self.product_barcode.id)

    def test_02_found_by_default_code(self):
        """Fallback al código interno cuando no hay barcode coincidente."""
        result = self.env["pos.order"].get_product_line_data_by_barcode("TST0001")
        self.assertTrue(result.get("success"))
        self.assertEqual(result["product"]["id"], self.product_barcode.id)

    def test_03_not_found_returns_success_false(self):
        """Código inexistente devuelve success=False con mensaje."""
        result = self.env["pos.order"].get_product_line_data_by_barcode(
            "CODIGOINEXISTENTE9999"
        )
        self.assertFalse(result.get("success"))
        self.assertIn("message", result)

    def test_04_line_vals_contain_required_keys(self):
        """line_vals tiene los campos mínimos necesarios para crear una línea."""
        result = self.env["pos.order"].get_product_line_data_by_barcode(
            "TST0001BARCODE"
        )
        self.assertTrue(result.get("success"))
        for key in ("qty", "price_unit", "discount", "tax_ids"):
            self.assertIn(key, result["line_vals"], f"Falta clave '{key}'")

    def test_05_price_unit_matches_list_price(self):
        """price_unit en line_vals coincide con el precio de lista."""
        result = self.env["pos.order"].get_product_line_data_by_barcode(
            "TST0001BARCODE"
        )
        self.assertAlmostEqual(
            result["line_vals"]["price_unit"],
            self.product_barcode.list_price,
            places=2,
        )

    def test_06_with_pricelist(self):
        """Con pricelist_id se calcula el precio correctamente."""
        pricelist = self.pos_config.pricelist_id
        if not pricelist:
            self.skipTest("No hay lista de precios configurada en el POS")
        result = self.env["pos.order"].get_product_line_data_by_barcode(
            "TST0001BARCODE", pricelist_id=pricelist.id
        )
        self.assertTrue(result.get("success"))

    # ── add_product_by_barcode ────────────────────────────────────────────

    def test_07_add_new_line_by_barcode(self):
        """add_product_by_barcode añade una nueva línea al pedido."""
        session = self._open_session()
        order = self._make_draft_order(session)
        result = order.add_product_by_barcode(barcode="TST0001BARCODE")
        self.assertTrue(result.get("success"))
        self.assertEqual(len(order.lines), 1)

    def test_08_add_existing_line_increments_qty(self):
        """Añadir el mismo producto dos veces incrementa la cantidad."""
        session = self._open_session()
        order = self._make_draft_order(session)
        order.add_product_by_barcode(barcode="TST0001BARCODE")
        order.add_product_by_barcode(barcode="TST0001BARCODE")
        self.assertEqual(len(order.lines), 1)
        self.assertEqual(order.lines[0].qty, 2.0)

    def test_09_add_by_product_id(self):
        """add_product_by_barcode funciona con product_id en lugar de barcode."""
        session = self._open_session()
        order = self._make_draft_order(session)
        result = order.add_product_by_barcode(product_id=self.product_barcode.id)
        self.assertTrue(result.get("success"))

    def test_10_add_to_non_draft_order_returns_error(self):
        """No se puede añadir a un pedido que no está en borrador."""
        session = self._open_session()
        order = self._make_draft_order(session)
        self._add_line(order, self.product_barcode)
        self._add_payment(order)
        order.action_pos_order_paid()
        result = order.add_product_by_barcode(barcode="TST0001BARCODE")
        self.assertFalse(result.get("success"))

    def test_11_add_without_barcode_or_product_returns_error(self):
        """Sin barcode ni product_id devuelve error."""
        session = self._open_session()
        order = self._make_draft_order(session)
        result = order.add_product_by_barcode()
        self.assertFalse(result.get("success"))

    def test_12_add_nonexistent_product_id_returns_error(self):
        """ID de producto inexistente devuelve error."""
        session = self._open_session()
        order = self._make_draft_order(session)
        result = order.add_product_by_barcode(product_id=99999999)
        self.assertFalse(result.get("success"))

