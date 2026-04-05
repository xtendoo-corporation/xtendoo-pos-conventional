# Copyright 2024 Xtendoo
# License OPL-1
"""
Tests de cobertura para los campos de coste y margen en pos.order.line.

Campos verificados:
  - total_cost               (compute _compute_total_cost_conventional)
  - is_total_cost_computed   (compute _compute_total_cost_conventional)
  - margin                   (compute _compute_margin – nativo Odoo)
  - margin_percent           (compute _compute_margin – nativo Odoo)

Flujos cubiertos:
  - Creación directa de línea con producto con coste conocido
  - Cambio de cantidad recomputa coste
  - Producto sin coste (standard_price = 0) → margen igual al subtotal
  - Producto con coste = precio de venta → margen cero
  - Coste > precio de venta → margen negativo
  - Múltiples líneas → suma de costes y margen del pedido
  - Carga de producto por código de barras (add_product_by_barcode)
  - Línea sin producto → total_cost = 0, is_total_cost_computed = False
  - Relación margin = price_subtotal − total_cost
  - Relación margin_percent = margin / price_subtotal
"""

from odoo.tests.common import tagged
from .common import PosConventionalTestCommon


@tagged("pos_conventional_core", "-standard")
class TestPosOrderLineCostMargin(PosConventionalTestCommon):
    """Cobertura de los campos total_cost, is_total_cost_computed, margin y margin_percent."""

    # ── helpers propios ──────────────────────────────────────────────────

    def _product_with_cost(self, name="Producto Con Coste", list_price=100.0, standard_price=60.0):
        """Crea un producto con precio de lista y coste estándar explícitos."""
        product = self.env["product.product"].create({
            "name": name,
            "type": "consu",
            "list_price": list_price,
            "standard_price": standard_price,
            "available_in_pos": True,
            "property_account_income_id": self.income_account.id if self.income_account else False,
        })
        return product

    def _make_line(self, product, qty=1.0, session=None):
        """Crea pedido + línea y devuelve la línea."""
        if session is None:
            session = self._open_session()
        order = self._make_draft_order(session)
        return self._add_line(order, product, qty), order

    # ── 1. total_cost se calcula al crear la línea ────────────────────────

    def test_01_total_cost_computed_on_create(self):
        """Tras crear una línea con standard_price=60, total_cost debe ser 60×qty."""
        product = self._product_with_cost(standard_price=60.0)
        line, _ = self._make_line(product, qty=1.0)
        self.assertAlmostEqual(line.total_cost, 60.0, places=2)

    def test_02_total_cost_respects_qty(self):
        """total_cost escala con la cantidad: 3 unidades × 60 = 180."""
        product = self._product_with_cost(standard_price=60.0)
        line, _ = self._make_line(product, qty=3.0)
        self.assertAlmostEqual(line.total_cost, 180.0, places=2)

    def test_03_is_total_cost_computed_is_true(self):
        """is_total_cost_computed debe ser True para un producto con coste."""
        product = self._product_with_cost(standard_price=40.0)
        line, _ = self._make_line(product, qty=1.0)
        self.assertTrue(line.is_total_cost_computed)

    # ── 2. Recomputo al cambiar cantidad ─────────────────────────────────

    def test_04_total_cost_recomputes_on_qty_change(self):
        """Al cambiar qty de 1 a 5, total_cost debe actualizarse."""
        product = self._product_with_cost(standard_price=20.0)
        line, _ = self._make_line(product, qty=1.0)
        self.assertAlmostEqual(line.total_cost, 20.0, places=2)
        line.write({"qty": 5.0})
        line.invalidate_recordset(["total_cost"])
        self.assertAlmostEqual(line.total_cost, 100.0, places=2)

    def test_05_total_cost_recomputes_on_product_change(self):
        """Al cambiar el producto, total_cost se recalcula con el nuevo coste."""
        product_a = self._product_with_cost("ProdA", standard_price=10.0)
        product_b = self._product_with_cost("ProdB", standard_price=50.0)
        session = self._open_session()
        order = self._make_draft_order(session)
        line = self._add_line(order, product_a, qty=1.0)
        self.assertAlmostEqual(line.total_cost, 10.0, places=2)
        line.write({"product_id": product_b.id})
        line.invalidate_recordset(["total_cost"])
        self.assertAlmostEqual(line.total_cost, 50.0, places=2)

    # ── 3. Producto sin coste ─────────────────────────────────────────────

    def test_06_zero_standard_price_gives_zero_total_cost(self):
        """Con standard_price=0, total_cost=0 y margin = price_subtotal."""
        product = self._product_with_cost(list_price=100.0, standard_price=0.0)
        line, _ = self._make_line(product, qty=1.0)
        self.assertAlmostEqual(line.total_cost, 0.0, places=2)

    def test_07_margin_equals_subtotal_when_zero_cost(self):
        """Sin coste, el margen debe ser igual al subtotal sin impuestos."""
        product = self._product_with_cost(list_price=100.0, standard_price=0.0)
        # Producto sin impuestos para simplificar
        product.write({"taxes_id": [(5,)]})
        line, _ = self._make_line(product, qty=1.0)
        # margin = price_subtotal - total_cost = price_subtotal - 0
        self.assertAlmostEqual(line.margin, line.price_subtotal, places=2)

    # ── 4. Margen cero cuando coste = precio de venta ────────────────────

    def test_08_margin_zero_when_cost_equals_price(self):
        """Cuando coste = precio, el margen debe ser (aproximadamente) 0."""
        product = self._product_with_cost(list_price=80.0, standard_price=80.0)
        product.write({"taxes_id": [(5,)]})          # sin impuestos
        line, _ = self._make_line(product, qty=1.0)
        # total_cost ≈ 80, price_subtotal ≈ 80 → margin ≈ 0
        self.assertAlmostEqual(line.margin, 0.0, places=2)

    def test_09_margin_percent_zero_when_cost_equals_price(self):
        """margin_percent debe ser 0 cuando coste = precio de venta."""
        product = self._product_with_cost(list_price=80.0, standard_price=80.0)
        product.write({"taxes_id": [(5,)]})
        line, _ = self._make_line(product, qty=1.0)
        self.assertAlmostEqual(line.margin_percent, 0.0, delta=0.001)

    # ── 5. Margen negativo cuando coste > precio ─────────────────────────

    def test_10_negative_margin_when_cost_exceeds_price(self):
        """Si coste > precio de venta, margin debe ser negativo."""
        product = self._product_with_cost(list_price=50.0, standard_price=70.0)
        product.write({"taxes_id": [(5,)]})
        line, _ = self._make_line(product, qty=1.0)
        self.assertLess(line.margin, 0.0)

    # ── 6. Relación margin = price_subtotal − total_cost ─────────────────

    def test_11_margin_formula_is_correct(self):
        """Verificar que margin = price_subtotal − total_cost (fórmula base)."""
        product = self._product_with_cost(list_price=120.0, standard_price=45.0)
        product.write({"taxes_id": [(5,)]})
        line, _ = self._make_line(product, qty=2.0)
        expected_margin = line.price_subtotal - line.total_cost
        self.assertAlmostEqual(line.margin, expected_margin, places=2)

    def test_12_margin_percent_formula_is_correct(self):
        """Verificar que margin_percent ≈ margin / price_subtotal."""
        product = self._product_with_cost(list_price=100.0, standard_price=30.0)
        product.write({"taxes_id": [(5,)]})
        line, _ = self._make_line(product, qty=1.0)
        if line.price_subtotal > 0:
            expected_pct = line.margin / line.price_subtotal
            self.assertAlmostEqual(line.margin_percent, expected_pct, delta=0.0001)

    # ── 7. Múltiples líneas ───────────────────────────────────────────────

    def test_13_total_cost_sum_multiple_lines(self):
        """Suma de total_cost de varias líneas debe ser coherente."""
        product_a = self._product_with_cost("MultiA", list_price=100.0, standard_price=40.0)
        product_b = self._product_with_cost("MultiB", list_price=50.0, standard_price=25.0)
        product_a.write({"taxes_id": [(5,)]})
        product_b.write({"taxes_id": [(5,)]})
        session = self._open_session()
        order = self._make_draft_order(session)
        line_a = self._add_line(order, product_a, qty=2.0)  # cost = 80
        line_b = self._add_line(order, product_b, qty=3.0)  # cost = 75
        total_cost_sum = sum(l.total_cost for l in order.lines)
        self.assertAlmostEqual(total_cost_sum, 155.0, places=2)

    def test_14_margin_is_positive_for_profitable_order(self):
        """Un pedido con margen positivo debe tener margin > 0 en todas las líneas rentables."""
        product = self._product_with_cost(list_price=100.0, standard_price=30.0)
        product.write({"taxes_id": [(5,)]})
        line, _ = self._make_line(product, qty=1.0)
        self.assertGreater(line.margin, 0.0)

    def test_15_order_margin_is_sum_of_line_margins(self):
        """El margen total del pedido debe coincidir con la suma de márgenes de líneas."""
        product_a = self._product_with_cost("OrdA", list_price=100.0, standard_price=40.0)
        product_b = self._product_with_cost("OrdB", list_price=80.0, standard_price=50.0)
        product_a.write({"taxes_id": [(5,)]})
        product_b.write({"taxes_id": [(5,)]})
        session = self._open_session()
        order = self._make_draft_order(session)
        self._add_line(order, product_a, qty=1.0)
        self._add_line(order, product_b, qty=1.0)
        expected_margin = sum(l.margin for l in order.lines)
        self.assertAlmostEqual(order.margin, expected_margin, places=2)

    # ── 8. Carga de producto por código de barras ─────────────────────────
    # Estos tests requieren el módulo pos_conventional_order_barcode instalado.
    # Si no está disponible, se omiten automáticamente.

    def _skip_if_no_barcode_module(self, order):
        """Omite el test si el módulo de barcode no está instalado."""
        if not hasattr(order, "add_product_by_barcode"):
            self.skipTest(
                "pos_conventional_order_barcode no está instalado – test omitido"
            )

    def test_16_barcode_load_sets_total_cost(self):
        """add_product_by_barcode crea línea con total_cost > 0 si producto tiene coste."""
        self.product_barcode.write({"standard_price": 15.0, "taxes_id": [(5,)]})
        session = self._open_session()
        order = self._make_draft_order(session)
        self._skip_if_no_barcode_module(order)
        result = order.add_product_by_barcode(barcode="TST0001BARCODE")
        self.assertTrue(result.get("success"))
        self.assertEqual(len(order.lines), 1)
        line = order.lines[0]
        self.assertAlmostEqual(line.total_cost, 15.0, places=2)

    def test_17_barcode_load_is_total_cost_computed_true(self):
        """Línea creada por código de barras tiene is_total_cost_computed = True."""
        self.product_barcode.write({"standard_price": 8.0})
        session = self._open_session()
        order = self._make_draft_order(session)
        self._skip_if_no_barcode_module(order)
        order.add_product_by_barcode(barcode="TST0001BARCODE")
        self.assertTrue(order.lines[0].is_total_cost_computed)

    def test_18_barcode_load_margin_is_computed(self):
        """Línea creada por barcode tiene margin calculado correctamente."""
        self.product_barcode.write({"standard_price": 10.0, "taxes_id": [(5,)]})
        session = self._open_session()
        order = self._make_draft_order(session)
        self._skip_if_no_barcode_module(order)
        order.add_product_by_barcode(barcode="TST0001BARCODE")
        line = order.lines[0]
        expected = line.price_subtotal - line.total_cost
        self.assertAlmostEqual(line.margin, expected, places=2)

    def test_19_barcode_increment_qty_updates_total_cost(self):
        """Al añadir el mismo producto dos veces (qty=2), total_cost se duplica."""
        self.product_barcode.write({"standard_price": 12.0})
        session = self._open_session()
        order = self._make_draft_order(session)
        self._skip_if_no_barcode_module(order)
        order.add_product_by_barcode(barcode="TST0001BARCODE")  # qty = 1
        order.add_product_by_barcode(barcode="TST0001BARCODE")  # qty = 2
        line = order.lines[0]
        self.assertEqual(line.qty, 2.0)
        self.assertAlmostEqual(line.total_cost, 24.0, places=2)

    # ── 9. Línea sin producto ─────────────────────────────────────────────

    def test_20_get_total_cost_no_product_returns_zero(self):
        """_get_total_cost_for_line devuelve (0.0, False) si no hay product_id."""
        session = self._open_session()
        order = self._make_draft_order(session)
        # Crear línea mínima sin producto para forzar el branch "no product"
        # (solo posible en contexto de test, eludiendo constraints de UI)
        line = self.env["pos.order.line"].new({
            "order_id": order.id,
            "qty": 1.0,
            "price_unit": 0.0,
            "price_subtotal": 0.0,
            "price_subtotal_incl": 0.0,
        })
        total_cost, computed = line._get_total_cost_for_line()
        self.assertEqual(total_cost, 0.0)
        self.assertFalse(computed)

    # ── 10. Coherencia con distintas cantidades y costes ──────────────────

    def test_21_total_cost_with_fractional_qty(self):
        """total_cost funciona correctamente con cantidades fraccionadas."""
        product = self._product_with_cost(standard_price=100.0)
        line, _ = self._make_line(product, qty=0.5)
        self.assertAlmostEqual(line.total_cost, 50.0, places=2)

    def test_22_total_cost_with_large_qty(self):
        """total_cost es correcto con cantidades grandes."""
        product = self._product_with_cost(standard_price=5.0)
        line, _ = self._make_line(product, qty=1000.0)
        self.assertAlmostEqual(line.total_cost, 5000.0, places=2)

    def test_23_margin_percent_is_between_0_and_1_for_profitable_product(self):
        """Para producto rentable, margin_percent debe estar entre 0 y 1 (0–100%)."""
        product = self._product_with_cost(list_price=100.0, standard_price=30.0)
        product.write({"taxes_id": [(5,)]})
        line, _ = self._make_line(product, qty=1.0)
        self.assertGreater(line.margin_percent, 0.0)
        self.assertLessEqual(line.margin_percent, 1.0)

    def test_24_total_cost_positive_for_positive_qty(self):
        """total_cost es positivo cuando qty > 0 y standard_price > 0."""
        product = self._product_with_cost(standard_price=25.0)
        line, _ = self._make_line(product, qty=2.0)
        self.assertGreater(line.total_cost, 0.0)

    def test_25_prepare_order_line_vals_contains_product_id(self):
        """_prepare_order_line_vals incluye product_id, condición para que se compute total_cost."""
        product = self._product_with_cost(standard_price=55.0)
        session = self._open_session()
        order = self._make_draft_order(session)
        vals = order._prepare_order_line_vals(product, qty=1.0)
        self.assertEqual(vals["product_id"], product.id)

    def test_26_total_cost_matches_standard_price_times_qty(self):
        """total_cost = standard_price × qty para producto con coste estándar (AVCO/estándar)."""
        standard_price = 35.0
        qty = 4.0
        product = self._product_with_cost(standard_price=standard_price)
        line, _ = self._make_line(product, qty=qty)
        self.assertAlmostEqual(line.total_cost, standard_price * qty, places=2)

    def test_27_margin_and_total_cost_type(self):
        """total_cost y margin son valores numéricos (float), no False ni None."""
        product = self._product_with_cost(standard_price=20.0)
        line, _ = self._make_line(product, qty=1.0)
        self.assertIsInstance(line.total_cost, float)
        self.assertIsInstance(line.margin, float)

    def test_28_is_total_cost_computed_false_for_new_record(self):
        """Un new() record sin producto tiene is_total_cost_computed = False."""
        session = self._open_session()
        order = self._make_draft_order(session)
        line = self.env["pos.order.line"].new({"order_id": order.id})
        _, computed = line._get_total_cost_for_line()
        self.assertFalse(computed)

    def test_29_multiple_qty_changes_keep_cost_consistent(self):
        """Varias actualizaciones de qty producen total_cost siempre coherente."""
        product = self._product_with_cost(standard_price=10.0)
        line, _ = self._make_line(product, qty=1.0)
        for qty in [2.0, 5.0, 0.5, 10.0]:
            line.write({"qty": qty})
            line.invalidate_recordset(["total_cost"])
            self.assertAlmostEqual(line.total_cost, 10.0 * qty, places=2)

    def test_30_margin_is_zero_for_zero_qty_zero_cost(self):
        """Con qty=0 y coste 0, margin es 0."""
        product = self._product_with_cost(list_price=0.0, standard_price=0.0)
        product.write({"taxes_id": [(5,)]})
        session = self._open_session()
        order = self._make_draft_order(session)
        line = self._add_line(order, product, qty=0.0)
        self.assertAlmostEqual(line.margin, 0.0, places=2)

    # ── _onchange_total_cost_conventional ─────────────────────────────────

    def test_31_onchange_total_cost_conventional_computes_correctly(self):
        """_onchange_total_cost_conventional calcula total_cost e is_total_cost_computed."""
        product = self._product_with_cost(standard_price=45.0)
        session = self._open_session()
        order = self._make_draft_order(session)
        # Crear un registro virtual (new) para probar el onchange
        line = self.env["pos.order.line"].new({
            "order_id": order.id,
            "product_id": product.id,
            "qty": 3.0,
            "price_unit": product.list_price,
            "price_subtotal": product.list_price * 3,
            "price_subtotal_incl": product.list_price * 3,
        })
        line._onchange_total_cost_conventional()
        self.assertAlmostEqual(
            line.total_cost, 135.0, places=2,
            msg="_onchange debe calcular total_cost = qty * standard_price = 3 * 45",
        )
        self.assertTrue(
            line.is_total_cost_computed,
            "_onchange debe marcar is_total_cost_computed=True para producto con coste",
        )

    def test_32_onchange_total_cost_no_product_returns_zero(self):
        """_onchange con línea sin producto: total_cost=0, is_total_cost_computed=False."""
        session = self._open_session()
        order = self._make_draft_order(session)
        line = self.env["pos.order.line"].new({"order_id": order.id, "qty": 1.0})
        line._onchange_total_cost_conventional()
        self.assertEqual(line.total_cost, 0.0)
        self.assertFalse(line.is_total_cost_computed)

    # ── _inverse_tax_ids_after_fiscal_position ────────────────────────────

    def test_33_inverse_syncs_tax_ids_when_no_fiscal_position(self):
        """_inverse sincroniza tax_ids cuando tax_ids_after_fp difiere y no hay FP."""
        session = self._open_session()
        order = self._make_draft_order(session)
        line = self._add_line(order, self.product)
        self.assertTrue(line.tax_ids, "La línea debe tener impuestos para este test")

        # Crear un impuesto diferente para asignar
        other_tax = self.env["account.tax"].create({
            "name": "IVA 10% Inverse Test",
            "amount": 10.0,
            "type_tax_use": "sale",
            "company_id": self.env.company.id,
        })
        # Asignar directamente tax_ids_after_fiscal_position (sin FP) → inverse sincroniza
        line.tax_ids_after_fiscal_position = other_tax
        # El inverse debe haber propagado el cambio a tax_ids
        self.assertIn(
            other_tax,
            line.tax_ids,
            "_inverse debe sincronizar tax_ids cuando no hay fiscal_position_id",
        )

    def test_34_inverse_does_nothing_with_fiscal_position(self):
        """_inverse NO modifica tax_ids cuando el pedido tiene fiscal_position_id."""
        session = self._open_session()
        order = self._make_draft_order(session)
        fp = self.env["account.fiscal.position"].create({"name": "FP Inverse Test"})
        order.write({"fiscal_position_id": fp.id})
        line = self._add_line(order, self.product)
        original_tax_ids = set(line.tax_ids.ids)

        # Llamar directamente al inverse con FP activa
        # La condición `if not line.order_id.fiscal_position_id:` es False → no sincroniza
        line._inverse_tax_ids_after_fiscal_position()

        self.assertEqual(
            set(line.tax_ids.ids),
            original_tax_ids,
            "_inverse no debe modificar tax_ids cuando hay fiscal_position_id",
        )

    def test_35_inverse_no_op_when_taxes_already_equal(self):
        """_inverse es un no-op cuando tax_ids_after_fp ya coincide con tax_ids."""
        session = self._open_session()
        order = self._make_draft_order(session)
        line = self._add_line(order, self.product)
        original_tax_ids = set(line.tax_ids.ids)

        # Llamar inverse directamente sin cambios → los taxes coinciden → no-op
        line._inverse_tax_ids_after_fiscal_position()

        self.assertEqual(
            set(line.tax_ids.ids),
            original_tax_ids,
            "_inverse no debe cambiar tax_ids cuando ya coinciden con tax_ids_after_fp",
        )

    # ── write() en PosOrderLine — ramas de restauración de taxes ──────────

    def test_36_write_restores_tax_ids_when_cleared_for_product_with_taxes(self):
        """write() restaura tax_ids automáticamente cuando quedan vacíos y el producto tiene taxes.

        Cubre la rama: not line.tax_ids AND product_id AND product_taxes → restaurar.
        """
        session = self._open_session()
        order = self._make_draft_order(session)
        line = self._add_line(order, self.product)
        self.assertTrue(line.tax_ids, "La línea debe tener impuestos antes del test")
        original_taxes = set(line.tax_ids.ids)

        # Intentar borrar tax_ids via write() — nuestro override los restaurará
        line.write({"tax_ids": [(5,)]})

        # Los impuestos deben haber sido restaurados desde el producto
        self.assertEqual(
            set(line.tax_ids.ids),
            original_taxes,
            "write() debe restaurar tax_ids desde el producto cuando quedan vacíos",
        )

    def test_37_write_no_restore_when_product_has_no_taxes(self):
        """write() no restaura tax_ids cuando el producto no tiene ningún impuesto.

        Cubre la rama: not line.tax_ids AND product_id AND NOT product_taxes → sin restaurar.
        """
        product_no_tax = self.env["product.product"].create({
            "name": "Prod Sin Tax Write Test",
            "type": "consu",
            "list_price": 30.0,
            "taxes_id": [(5,)],
            "available_in_pos": True,
        })
        session = self._open_session()
        order = self._make_draft_order(session)
        line_vals = {
            "order_id": order.id,
            "product_id": product_no_tax.id,
            "qty": 1.0,
            "price_unit": 30.0,
            "price_subtotal": 30.0,
            "price_subtotal_incl": 30.0,
            "tax_ids": [(5,)],
        }
        line = self.env["pos.order.line"].create(line_vals)
        self.assertFalse(line.tax_ids, "La línea no debe tener impuestos")

        # write() con producto sin taxes → la rama `if product_taxes:` es False → no restaura
        line.write({"qty": 2.0})

        self.assertFalse(
            line.tax_ids,
            "write() no debe restaurar tax_ids cuando el producto no tiene impuestos",
        )

    # ── _get_total_cost_for_line — rama de excepción ──────────────────────

    def test_38_get_total_cost_exception_uses_fallback(self):
        """_get_total_cost_for_line usa qty * standard_price como fallback si _convert falla.

        Cubre la rama `except Exception: total_cost = qty * product.standard_price`.
        """
        from unittest.mock import patch
        product = self._product_with_cost(standard_price=40.0)
        session = self._open_session()
        order = self._make_draft_order(session)
        line = self._add_line(order, product, qty=3.0)

        with patch.object(
            type(product.sudo().cost_currency_id),
            "_convert",
            side_effect=Exception("Error de conversión simulado"),
        ):
            total_cost, computed = line._get_total_cost_for_line()

        # Fallback: qty * standard_price = 3 * 40 = 120
        self.assertAlmostEqual(
            total_cost, 120.0, places=2,
            msg="El fallback debe devolver qty * standard_price cuando _convert falla",
        )
        self.assertTrue(computed, "is_total_cost_computed debe ser True incluso con fallback")


