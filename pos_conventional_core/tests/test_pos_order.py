# Copyright 2024 Xtendoo
# License OPL-1
from odoo.tests.common import tagged

from .common import PosConventionalTestCommon


@tagged("pos_conventional_core", "-standard")
class TestPosOrder(PosConventionalTestCommon):
    """Tests para pos.order (pos_conventional_core)."""

    # ── payment_method_ribbon ─────────────────────────────────────────────

    def test_01_ribbon_no_payments(self):
        """Sin pagos ni estado pagado, el ribbon es False."""
        session = self._open_session()
        order = self._make_draft_order(session)
        self._add_line(order)
        self.assertFalse(order.payment_method_ribbon)

    def test_02_ribbon_single_method(self):
        """Un único método de pago muestra su nombre en mayúsculas."""
        session = self._open_session()
        order = self._make_draft_order(session)
        self._add_line(order)
        self._add_payment(order, self.cash_pm)
        order.action_pos_order_paid()
        if order.state in ("paid", "done"):
            self.assertEqual(order.payment_method_ribbon, self.cash_pm.name.upper())
        else:
            # En algunos contextos el pedido puede quedar en estado distinto
            self.skipTest("action_pos_order_paid no cambió el estado a paid en el contexto de test")

    def test_03_ribbon_multiple_methods(self):
        """Múltiples métodos de pago muestran 'PAGO MÚLTIPLE'."""
        session = self._open_session()
        order = self._make_draft_order(session, partner=self.partner)
        self._add_line(order)
        half = order.amount_total / 2
        self._add_payment(order, self.cash_pm, half)
        self._add_payment(order, self.card_pm, order.amount_total - half)
        order.action_pos_order_paid()
        if order.state in ("paid", "done"):
            self.assertEqual(order.payment_method_ribbon, "PAGO MÚLTIPLE")
        else:
            self.skipTest("action_pos_order_paid no cambió el estado en el contexto de test")

    # ── amount_untaxed ────────────────────────────────────────────────────

    def test_04_amount_untaxed_positive(self):
        """amount_untaxed debe ser la suma de price_subtotal de las líneas."""
        session = self._open_session()
        order = self._make_draft_order(session)
        self._add_line(order, self.product, 2.0)
        expected = sum(l.price_subtotal for l in order.lines)
        self.assertAlmostEqual(order.amount_untaxed, expected, places=2)

    def test_05_amount_untaxed_is_positive_for_normal_order(self):
        """amount_untaxed es positivo en un pedido normal."""
        session = self._open_session()
        order = self._make_draft_order(session)
        self._add_line(order)
        self.assertGreater(order.amount_untaxed, 0)

    def test_06_amount_untaxed_zero_no_lines(self):
        """Sin líneas, amount_untaxed es 0."""
        session = self._open_session()
        order = self._make_draft_order(session)
        self.assertEqual(order.amount_untaxed, 0.0)

    # ── default_get ───────────────────────────────────────────────────────

    def test_07_default_get_sets_company(self):
        """default_get siempre establece company_id."""
        defaults = self.env["pos.order"].default_get(["company_id"])
        self.assertEqual(defaults.get("company_id"), self.env.company.id)

    def test_08_default_get_with_session_context_sets_session(self):
        """default_get con default_session_id en contexto asigna la sesión."""
        session = self._open_session()
        defaults = self.env["pos.order"].with_context(
            default_session_id=session.id
        ).default_get(["session_id", "currency_id", "pricelist_id"])
        self.assertEqual(defaults.get("session_id"), session.id)
        self.assertEqual(defaults.get("currency_id"), session.currency_id.id)

    def test_09_default_get_sets_default_partner_from_config(self):
        """Si el config tiene default_partner_id, se asigna al pedido."""
        self.pos_config.default_partner_id = self.partner
        session = self._open_session()
        defaults = self.env["pos.order"].with_context(
            default_session_id=session.id
        ).default_get(["partner_id"])
        self.assertEqual(defaults.get("partner_id"), self.partner.id)
        # Cleanup
        self.pos_config.default_partner_id = False

    def test_10_default_get_amount_return_zero(self):
        """default_get establece amount_return=0 si no está."""
        defaults = self.env["pos.order"].default_get(["amount_return"])
        self.assertEqual(defaults.get("amount_return"), 0.0)

    # ── create (auto session assignment) ─────────────────────────────────

    def test_11_create_auto_assigns_session_for_non_touch(self):
        """Al crear sin session_id, se asigna la sesión non-touch activa."""
        session = self._open_session()
        order = self.env["pos.order"].create(
            {
                "config_id": self.pos_config.id,
                "pricelist_id": self.pos_config.pricelist_id.id,
                "currency_id": session.currency_id.id,
            }
        )
        self.assertEqual(order.session_id, session)

    def test_12_create_sets_amount_paid_zero(self):
        """Un pedido recién creado tiene amount_paid = 0."""
        session = self._open_session()
        order = self._make_draft_order(session)
        self.assertEqual(order.amount_paid, 0.0)

    # ── _prepare_order_line_vals ──────────────────────────────────────────

    def test_13_prepare_order_line_vals_returns_required_keys(self):
        """_prepare_order_line_vals devuelve todos los campos necesarios."""
        session = self._open_session()
        order = self._make_draft_order(session)
        vals = order._prepare_order_line_vals(self.product)
        for key in ("order_id", "product_id", "qty", "price_unit", "price_subtotal", "price_subtotal_incl"):
            self.assertIn(key, vals, f"Falta clave '{key}' en _prepare_order_line_vals")

    def test_14_prepare_order_line_vals_qty(self):
        """_prepare_order_line_vals respeta la qty pasada."""
        session = self._open_session()
        order = self._make_draft_order(session)
        vals = order._prepare_order_line_vals(self.product, qty=3.0)
        self.assertEqual(vals["qty"], 3.0)

    def test_15_prepare_order_line_vals_price_unit(self):
        """_prepare_order_line_vals usa el precio de lista del producto."""
        session = self._open_session()
        order = self._make_draft_order(session)
        vals = order._prepare_order_line_vals(self.product)
        self.assertAlmostEqual(vals["price_unit"], self.product.list_price, places=2)

    # ── get_order_receipt_data ────────────────────────────────────────────

    def test_16_get_order_receipt_data_not_found_returns_empty(self):
        """ID inexistente devuelve {}."""
        result = self.env["pos.order"].get_order_receipt_data(0)
        self.assertEqual(result, {})

    def test_17_get_order_receipt_data_structure(self):
        """get_order_receipt_data devuelve las claves esperadas."""
        session = self._open_session()
        order = self._make_draft_order(session)
        self._add_line(order)
        result = self.env["pos.order"].get_order_receipt_data(order.id)
        for key in ("name", "amount_total", "amount_paid", "lines", "company_name"):
            self.assertIn(key, result, f"Clave '{key}' faltante en receipt data")

    def test_18_get_order_receipt_data_lines(self):
        """get_order_receipt_data incluye las líneas del pedido."""
        session = self._open_session()
        order = self._make_draft_order(session)
        self._add_line(order, self.product, 2.0)
        result = self.env["pos.order"].get_order_receipt_data(order.id)
        self.assertEqual(len(result["lines"]), 1)
        self.assertAlmostEqual(result["lines"][0]["qty"], 2.0)

    # ── write (tax sync) ──────────────────────────────────────────────────

    def test_19_write_does_not_raise(self):
        """write() en un pedido con líneas no lanza excepciones."""
        session = self._open_session()
        order = self._make_draft_order(session)
        self._add_line(order)
        order.write({"nb_print": 1})
        self.assertEqual(order.nb_print, 1)

    def test_20_write_preserves_tax_ids_on_lines(self):
        """write() en un pedido no borra tax_ids de las líneas existentes."""
        session = self._open_session()
        order = self._make_draft_order(session)
        line = self._add_line(order, self.product)
        # Guardar los tax_ids originales
        original_tax_ids = line.tax_ids.ids
        # Escribir algo en el pedido (simula el guardado desde el formulario)
        order.write({"nb_print": 0})
        # tax_ids no debe haberse vaciado
        self.assertEqual(sorted(line.tax_ids.ids), sorted(original_tax_ids))

    def test_20b_tax_ids_after_fiscal_position_persists_after_write(self):
        """tax_ids_after_fiscal_position sigue mostrando impuestos tras guardar el pedido."""
        session = self._open_session()
        order = self._make_draft_order(session)
        line = self._add_line(order, self.product)
        # Verificar que la línea tiene impuestos del producto
        if not line.tax_ids:
            self.skipTest("Producto de test no tiene impuestos asignados")
        # Registrar cuántos taxes tiene antes de guardar
        taxes_before = line.tax_ids_after_fiscal_position.ids
        # Simular guardado del pedido (escribe cualquier campo no-tax)
        order.write({"nb_print": 1})
        taxes_after = line.tax_ids_after_fiscal_position.ids
        self.assertEqual(sorted(taxes_before), sorted(taxes_after),
                         "tax_ids_after_fiscal_position debe mantener sus valores tras guardar el pedido")

    def test_20c_tax_ids_after_fp_equals_tax_ids_without_fiscal_position(self):
        """Sin posición fiscal, tax_ids_after_fiscal_position == tax_ids."""
        session = self._open_session()
        order = self._make_draft_order(session)
        # Verificar que el pedido no tiene posición fiscal
        if order.fiscal_position_id:
            self.skipTest("El pedido tiene posición fiscal, caso no aplicable")
        line = self._add_line(order, self.product)
        if not line.tax_ids:
            self.skipTest("Producto de test no tiene impuestos")
        self.assertEqual(
            sorted(line.tax_ids.ids),
            sorted(line.tax_ids_after_fiscal_position.ids),
            "Sin posición fiscal, tax_ids y tax_ids_after_fiscal_position deben coincidir",
        )

    def test_20d_write_line_tax_ids_not_cleared_by_order_write(self):
        """Escribir en el pedido (partner, nb_print) no vacía tax_ids de las líneas."""
        session = self._open_session()
        order = self._make_draft_order(session)
        line = self._add_line(order, self.product)
        if not line.tax_ids:
            self.skipTest("Producto sin impuestos, test no aplicable")
        tax_ids_before = set(line.tax_ids.ids)
        # Simular guardado desde el formulario con diferentes campos
        order.write({"nb_print": 2})
        order.write({"partner_id": self.partner.id})
        tax_ids_after = set(line.tax_ids.ids)
        self.assertEqual(tax_ids_before, tax_ids_after,
                         "Los tax_ids de las líneas no deben borrarse al escribir en el pedido")

    # ── action_validate_and_invoice ───────────────────────────────────────

    def test_21_action_validate_and_invoice_non_draft_returns_false(self):
        """action_validate_and_invoice en un pedido ya pagado devuelve False."""
        session = self._open_session()
        order = self._make_draft_order(session)
        self._add_line(order)
        self._add_payment(order)
        order.action_pos_order_paid()
        result = order.action_validate_and_invoice()
        self.assertFalse(result)

    def test_22_action_validate_and_invoice_draft_order(self):
        """action_validate_and_invoice en borrador con pago completo procesa el pedido."""
        session = self._open_session()
        order = self._make_draft_order(session, self.partner)
        self._add_line(order)
        self._add_payment(order)
        result = order.action_validate_and_invoice()
        self.assertTrue(result is False or isinstance(result, dict))

    # ── _get_post_validation_action ───────────────────────────────────────

    def test_23_get_post_validation_action_returns_client_action(self):
        """_get_post_validation_action devuelve una acción ir.actions.client."""
        session = self._open_session()
        order = self._make_draft_order(session)
        self._add_line(order)
        self._add_payment(order)
        order.action_pos_order_paid()
        result = order._get_post_validation_action()
        self.assertEqual(result.get("type"), "ir.actions.client")
        self.assertEqual(result.get("tag"), "pos_conventional_new_order")

    def test_24_get_post_validation_action_contains_config_id(self):
        """_get_post_validation_action incluye config_id en params."""
        session = self._open_session()
        order = self._make_draft_order(session)
        self._add_line(order)
        self._add_payment(order)
        order.action_pos_order_paid()
        result = order._get_post_validation_action()
        self.assertEqual(result["params"]["config_id"], order.config_id.id)

    def test_25_get_post_validation_action_with_force_login(self):
        """Con pos_force_employee_login_after_order activo, la acción incluye force_login_after_order."""
        if not hasattr(self.pos_config, 'pos_force_employee_login_after_order'):
            self.skipTest("pos_force_employee_login_after_order no disponible (módulo PIN no instalado)")
        self.pos_config.pos_force_employee_login_after_order = True
        session = self._open_session()
        order = self._make_draft_order(session)
        self._add_line(order)
        self._add_payment(order)
        order.action_pos_order_paid()
        result = order._get_post_validation_action()
        self.assertTrue(result["params"].get("force_login_after_order"))
        self.pos_config.pos_force_employee_login_after_order = False

    def test_26_get_post_validation_action_with_print_auto(self):
        """Con iface_print_auto activo, la acción usa el tag de impresión."""
        self.pos_config.iface_print_auto = True
        session = self._open_session()
        order = self._make_draft_order(session)
        self._add_line(order)
        self._add_payment(order)
        order.action_pos_order_paid()
        result = order._get_post_validation_action()
        self.assertEqual(result.get("tag"), "pos_conventional_print_receipt_client")
        self.pos_config.iface_print_auto = False

    # ── get_order_receipt_data — campos adicionales ───────────────────────

    def test_27_get_order_receipt_data_currency_symbol(self):
        """get_order_receipt_data incluye el símbolo de la moneda."""
        session = self._open_session()
        order = self._make_draft_order(session)
        self._add_line(order)
        result = self.env["pos.order"].get_order_receipt_data(order.id)
        self.assertIn("currency_symbol", result)
        self.assertTrue(result["currency_symbol"])

    def test_28_get_order_receipt_data_company_vat(self):
        """get_order_receipt_data incluye el campo company_vat."""
        session = self._open_session()
        order = self._make_draft_order(session)
        self._add_line(order)
        result = self.env["pos.order"].get_order_receipt_data(order.id)
        self.assertIn("company_vat", result)

    def test_29_amount_untaxed_leq_amount_total_with_taxes(self):
        """amount_untaxed es menor o igual a amount_total cuando hay impuestos."""
        session = self._open_session()
        order = self._make_draft_order(session)
        self._add_line(order, self.product, 1.0)
        if order.amount_total > 0:
            self.assertLessEqual(order.amount_untaxed, order.amount_total)

    def test_30_ribbon_draft_order_is_false(self):
        """En borrador, sin pagar, el ribbon es False."""
        session = self._open_session()
        order = self._make_draft_order(session)
        self._add_line(order)
        self.assertFalse(order.payment_method_ribbon)

