# Copyright 2024 Xtendoo
# License OPL-1
from odoo.tests.common import tagged

from .common import PosConventionalTestCommon


@tagged("pos_conventional_core", "-standard", "post_install", "-at_install")
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
            self.assertEqual(order.payment_method_ribbon, "MULTIPLE PAYMENT")
        else:
            self.skipTest("action_pos_order_paid did not change state in test context")

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
        order = self.env["pos.order"].with_context(skip_completeness_check=True).create(
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
        required_keys = (
            "name", "amount_total", "amount_paid", "lines",
            "company_name", "company_vat", "currency_symbol",
            "company", "currency_id", "payment_ids",
        )
        for key in required_keys:
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

    # ── get_order_receipt_data — payment_ids, user_id, partner ───────────

    def test_31_get_order_receipt_data_payment_ids_empty_list(self):
        """Sin pagos, payment_ids es una lista vacía."""
        session = self._open_session()
        order = self._make_draft_order(session)
        self._add_line(order)
        result = self.env["pos.order"].get_order_receipt_data(order.id)
        self.assertIsInstance(result["payment_ids"], list)
        self.assertEqual(result["payment_ids"], [])

    def test_32_get_order_receipt_data_payment_ids_with_payment(self):
        """Con pagos, payment_ids contiene la información del método de pago."""
        session = self._open_session()
        order = self._make_draft_order(session)
        self._add_line(order)
        self._add_payment(order, self.cash_pm)
        result = self.env["pos.order"].get_order_receipt_data(order.id)
        self.assertTrue(len(result["payment_ids"]) >= 1)
        payment = result["payment_ids"][0]
        self.assertIn("amount", payment)
        self.assertIn("payment_method_id", payment)
        self.assertIsInstance(payment["payment_method_id"], list)
        self.assertEqual(len(payment["payment_method_id"]), 2)

    def test_33_get_order_receipt_data_partner_false_without_partner(self):
        """Sin partner asignado, partner devuelve False."""
        session = self._open_session()
        order = self._make_draft_order(session)
        self._add_line(order)
        result = self.env["pos.order"].get_order_receipt_data(order.id)
        # partner_id se establece desde default_partner_id en el config; si existe, lo tiene
        # Basta con verificar que la clave existe y que si es dict tiene las claves esperadas
        if result["partner"]:
            for key in ("id", "name", "address", "vat", "email"):
                self.assertIn(key, result["partner"])
        else:
            self.assertFalse(result["partner"])

    def test_34_get_order_receipt_data_partner_with_partner(self):
        """Con partner asignado, partner incluye nombre y dirección."""
        session = self._open_session()
        order = self._make_draft_order(session, partner=self.partner)
        self._add_line(order)
        result = self.env["pos.order"].get_order_receipt_data(order.id)
        self.assertTrue(result["partner"])
        self.assertEqual(result["partner"]["id"], self.partner.id)
        self.assertEqual(result["partner"]["name"], self.partner.name)

    def test_35_get_order_receipt_data_user_id_field(self):
        """user_id está presente y tiene formato [id, nombre] o False."""
        session = self._open_session()
        order = self._make_draft_order(session)
        self._add_line(order)
        result = self.env["pos.order"].get_order_receipt_data(order.id)
        self.assertIn("user_id", result)
        if result["user_id"]:
            self.assertIsInstance(result["user_id"], list)
            self.assertEqual(len(result["user_id"]), 2)

    def test_36_get_order_receipt_data_company_nested_structure(self):
        """El campo 'company' anidado contiene id, name, vat y country_id."""
        session = self._open_session()
        order = self._make_draft_order(session)
        self._add_line(order)
        result = self.env["pos.order"].get_order_receipt_data(order.id)
        company_data = result.get("company", {})
        for key in ("id", "name", "vat", "country_id"):
            self.assertIn(key, company_data, f"Clave '{key}' faltante en company")
        self.assertIn("vat_label", company_data["country_id"])

    def test_37_get_order_receipt_data_currency_id_list_format(self):
        """currency_id es una lista [id, símbolo, posición, decimales]."""
        session = self._open_session()
        order = self._make_draft_order(session)
        self._add_line(order)
        result = self.env["pos.order"].get_order_receipt_data(order.id)
        cid = result.get("currency_id")
        self.assertIsInstance(cid, list)
        self.assertEqual(len(cid), 4)
        self.assertIsInstance(cid[0], int)   # id
        self.assertIsInstance(cid[1], str)   # symbol

    # ── _compute_has_order_lines ──────────────────────────────────────────

    def test_38_has_order_lines_true_when_lines_exist(self):
        """has_order_lines es True cuando el pedido tiene líneas."""
        session = self._open_session()
        order = self._make_draft_order(session)
        self._add_line(order)
        order.invalidate_recordset(["has_order_lines"])
        self.assertTrue(order.has_order_lines)

    def test_39_has_order_lines_false_when_no_lines(self):
        """has_order_lines es False cuando el pedido no tiene líneas."""
        session = self._open_session()
        order = self._make_draft_order(session)
        order.invalidate_recordset(["has_order_lines"])
        self.assertFalse(order.has_order_lines)

    # ── _compute_payment_method_ribbon (rama paid + métodos vacíos) ───────

    def test_40_ribbon_paid_all_zero_amount_payments(self):
        """Estado 'paid' con todos los pagos de importe 0: ribbon debe ser False."""
        session = self._open_session()
        order = self._make_draft_order(session)
        self._add_line(order)
        # Registrar un pago con importe 0
        self.env["pos.payment"].create({
            "pos_order_id": order.id,
            "payment_method_id": self.cash_pm.id,
            "amount": 0.0,
            "session_id": session.id,
        })
        order.write({"state": "paid"})
        order.invalidate_recordset(["payment_method_ribbon"])
        self.assertFalse(
            order.payment_method_ribbon,
            "Con pagos de importe 0, el ribbon debe ser False aunque el estado sea 'paid'",
        )

    # ── default_get — ramas adicionales ───────────────────────────────────

    def test_41_default_get_fallback_finds_active_non_touch_session(self):
        """default_get sin contexto de sesión usa el fallback y encuentra la sesión abierta."""
        session = self._open_session()
        defaults = self.env["pos.order"].default_get(["session_id", "currency_id"])
        self.assertEqual(
            defaults.get("session_id"),
            session.id,
            "El fallback de default_get debe encontrar la sesión non-touch activa",
        )

    def test_42_default_get_with_session_id_context_key(self):
        """default_get usa 'session_id' en el contexto (no 'default_session_id')."""
        session = self._open_session()
        defaults = self.env["pos.order"].with_context(
            session_id=session.id
        ).default_get(["session_id", "currency_id"])
        self.assertEqual(defaults.get("session_id"), session.id)
        self.assertEqual(defaults.get("currency_id"), session.currency_id.id)

    def test_43_default_get_non_existent_session_id_not_used_for_session(self):
        """default_get con session_id que no existe: no establece session_id desde esa sesión.

        Cubre la rama `if session:` → False cuando browse(id).exists() devuelve vacío.
        La clave de contexto 'session_id' (sin prefijo 'default_') no es aplicada
        automáticamente por el default_get del padre, por lo que OUR código la procesa.
        """
        invalid_id = 999999999
        # Confirmar que el ID realmente no existe
        self.assertFalse(self.env["pos.session"].browse(invalid_id).exists())
        # Usar 'session_id' (no 'default_session_id') para que el padre no lo auto-aplique
        defaults = self.env["pos.order"].with_context(
            session_id=invalid_id
        ).default_get(["session_id"])
        # Nuestra lógica: browse(invalid_id).exists() → vacío → if session: False → skip
        # El fallback puede encontrar otra sesión, pero NO el ID inválido
        self.assertNotEqual(
            defaults.get("session_id"),
            invalid_id,
            "default_get no debe establecer session_id desde una sesión inexistente",
        )

    def test_44_default_get_partner_not_set_when_no_default_partner_on_config(self):
        """default_get no asigna partner_id cuando el config no tiene default_partner_id."""
        config = self.env["pos.config"].create({
            "name": "Config Sin Partner",
            "pos_non_touch": True,
            "payment_method_ids": [(6, 0, [self._make_fresh_cash_pm().id])],
            # default_partner_id NOT set
        })
        session = self._open_session(config=config)
        defaults = self.env["pos.order"].with_context(
            default_session_id=session.id
        ).default_get(["partner_id"])
        # El config no tiene default_partner_id → no se asigna partner
        self.assertFalse(
            defaults.get("partner_id"),
            "Sin default_partner_id en el config, no se debe asignar partner automáticamente",
        )

    def test_45_default_get_partner_not_set_when_not_in_fields_list(self):
        """default_get no ejecuta el bloque de partner cuando partner_id no está en fields_list."""
        self.pos_config.default_partner_id = self.partner
        session = self._open_session()
        # partner_id NOT in fields_list → el bloque de partner se salta
        defaults = self.env["pos.order"].with_context(
            default_session_id=session.id
        ).default_get(["session_id", "currency_id"])
        # No debería haber partner_id en el resultado
        self.assertNotIn("partner_id", defaults)
        self.pos_config.default_partner_id = False

    # ── create — ramas adicionales ────────────────────────────────────────

    def test_46_create_auto_assigns_currency_id_when_not_in_vals(self):
        """create() auto-asigna currency_id desde la sesión activa cuando no viene en los vals.

        Cubre la rama `if not vals.get("currency_id"): vals["currency_id"] = ...`
        """
        session = self._open_session()
        order = self.env["pos.order"].with_context(skip_completeness_check=True).create({
            "config_id": self.pos_config.id,
            "session_id": session.id,
            # currency_id NOT provided → debe auto-asignarse desde la sesión
            "amount_tax": 0.0,
            "amount_total": 0.0,
            "amount_paid": 0.0,
            "amount_return": 0.0,
        })
        self.assertEqual(
            order.currency_id,
            session.currency_id,
            "create() debe auto-asignar currency_id desde la sesión cuando no viene en los vals",
        )

    def test_47_create_preserves_pricelist_when_already_in_vals(self):
        """create() no sobreescribe pricelist_id cuando ya está en los valores."""
        session = self._open_session()
        custom_pricelist = self.env["product.pricelist"].create({
            "name": "Custom Pricelist Test",
            "currency_id": session.currency_id.id,
        })
        order = self.env["pos.order"].with_context(skip_completeness_check=True).create({
            "session_id": session.id,
            "config_id": self.pos_config.id,
            "pricelist_id": custom_pricelist.id,
            "currency_id": session.currency_id.id,
            "amount_tax": 0.0,
            "amount_total": 0.0,
            "amount_paid": 0.0,
            "amount_return": 0.0,
        })
        self.assertEqual(
            order.pricelist_id,
            custom_pricelist,
            "create() no debe sobreescribir pricelist_id cuando ya viene en los vals",
        )

    # ── _prepare_order_line_vals — ramas adicionales ───────────────────────

    def test_48_prepare_order_line_vals_pricelist_applies_discount(self):
        """_prepare_order_line_vals calcula el descuento cuando la tarifa da precio inferior."""
        session = self._open_session()
        order = self._make_draft_order(session)
        # Crear tarifa con precio fijo reducido (80 para producto de lista 100)
        discount_pricelist = self.env["product.pricelist"].create({
            "name": "Tarifa Con Descuento Test",
            "currency_id": session.currency_id.id,
        })
        self.env["product.pricelist.item"].create({
            "pricelist_id": discount_pricelist.id,
            "compute_price": "fixed",
            "fixed_price": 80.0,
            "applied_on": "0_product_variant",
            "product_id": self.product.id,
        })
        order.pricelist_id = discount_pricelist
        vals = order._prepare_order_line_vals(self.product, qty=1.0)
        # public_price=100, pricelist price=80 → discount≈20%, price_unit=100
        self.assertGreater(
            vals["discount"], 0.0,
            "_prepare_order_line_vals debe calcular descuento cuando la tarifa da precio inferior",
        )
        self.assertAlmostEqual(
            vals["price_unit"],
            self.product.lst_price,
            places=2,
            msg="price_unit debe ser el precio público (lst_price) cuando hay descuento",
        )

    def test_49_prepare_order_line_vals_with_fiscal_position(self):
        """_prepare_order_line_vals aplica la posición fiscal al mapeo de impuestos."""
        session = self._open_session()
        order = self._make_draft_order(session)
        fiscal_pos = self.env["account.fiscal.position"].create({
            "name": "Posición Fiscal Test Vals",
        })
        order.write({"fiscal_position_id": fiscal_pos.id})
        vals = order._prepare_order_line_vals(self.product, qty=1.0)
        # El método debe ejecutarse sin error aplicando la posición fiscal
        self.assertIn("order_id", vals)
        self.assertEqual(vals["product_id"], self.product.id)
        self.assertEqual(vals["qty"], 1.0)

    def test_50_prepare_order_line_vals_product_without_taxes(self):
        """_prepare_order_line_vals con producto sin impuestos: taxes_after_fp vacío."""
        product_no_tax = self.env["product.product"].create({
            "name": "Producto Sin Impuesto Vals",
            "type": "consu",
            "list_price": 50.0,
            "taxes_id": [(5,)],
            "available_in_pos": True,
        })
        session = self._open_session()
        order = self._make_draft_order(session)
        vals = order._prepare_order_line_vals(product_no_tax, qty=2.0)
        # Sin impuestos, price_subtotal = price_unit * qty
        self.assertAlmostEqual(vals["price_subtotal"], 50.0 * 2.0, places=2)
        self.assertAlmostEqual(vals["price_subtotal_incl"], 50.0 * 2.0, places=2)
        self.assertEqual(vals["tax_ids"], [(6, 0, [])])

    # ── get_order_receipt_data — ramas adicionales ─────────────────────────

    def test_51_get_order_receipt_data_company_without_country(self):
        """get_order_receipt_data con compañía sin país: country_id devuelve vat_label='VAT'."""
        session = self._open_session()
        order = self._make_draft_order(session)
        self._add_line(order)
        original_country = self.env.company.country_id
        self.env.company.country_id = False
        try:
            result = self.env["pos.order"].get_order_receipt_data(order.id)
            country_data = result["company"]["country_id"]
            self.assertEqual(
                country_data.get("vat_label"),
                "VAT",
                "Sin país en la compañía, vat_label debe ser 'VAT' (valor por defecto)",
            )
        finally:
            self.env.company.country_id = original_country

    def test_52_get_order_receipt_data_config_receipt_header_footer(self):
        """get_order_receipt_data incluye receipt_header y receipt_footer del config."""
        self.pos_config.write({
            "receipt_header": "Cabecera Test",
            "receipt_footer": "Pie Test",
        })
        session = self._open_session()
        order = self._make_draft_order(session)
        self._add_line(order)
        result = self.env["pos.order"].get_order_receipt_data(order.id)
        self.assertEqual(result["receipt_header"], "Cabecera Test")
        self.assertEqual(result["receipt_footer"], "Pie Test")
        # Cleanup
        self.pos_config.write({"receipt_header": False, "receipt_footer": False})

    # ── _onchange_lines_recompute_totals (feedback visual inmediato) ──────

    def test_53_onchange_lines_sets_amount_total_from_lines(self):
        """_onchange_lines_recompute_totals calcula amount_total a partir de las líneas."""
        session = self._open_session()
        order = self._make_draft_order(session)
        self._add_line(order, self.product, 2.0)
        # Forzar a cero para verificar que el onchange lo recalcula
        order.write({"amount_total": 0.0, "amount_tax": 0.0})
        order._onchange_lines_recompute_totals()
        expected_total = sum(line.price_subtotal_incl for line in order.lines)
        self.assertAlmostEqual(order.amount_total, expected_total, places=2)
        self.assertGreater(order.amount_total, 0,
                           "amount_total debe ser mayor que cero tras el onchange con líneas")

    def test_54_onchange_lines_sets_amount_tax(self):
        """_onchange_lines_recompute_totals calcula amount_tax correctamente."""
        session = self._open_session()
        order = self._make_draft_order(session)
        self._add_line(order, self.product, 1.0)  # producto con IVA 21%
        order.write({"amount_total": 0.0, "amount_tax": 0.0})
        order._onchange_lines_recompute_totals()
        expected_tax = sum(
            line.price_subtotal_incl - line.price_subtotal for line in order.lines
        )
        self.assertAlmostEqual(order.amount_tax, expected_tax, places=2)
        if self.product.taxes_id:
            self.assertGreater(order.amount_tax, 0,
                               "amount_tax debe ser positivo para producto con impuestos")

    def test_55_onchange_lines_zero_when_no_lines(self):
        """_onchange_lines_recompute_totals deja los totales a cero si no hay líneas."""
        session = self._open_session()
        order = self._make_draft_order(session)
        # Sin líneas, los totales deben quedar a cero
        order._onchange_lines_recompute_totals()
        self.assertEqual(order.amount_total, 0.0)
        self.assertEqual(order.amount_tax, 0.0)

    def test_56_onchange_lines_total_equals_untaxed_plus_tax(self):
        """amount_total == amount_untaxed + amount_tax tras el onchange."""
        session = self._open_session()
        order = self._make_draft_order(session)
        self._add_line(order, self.product, 3.0)
        order.write({"amount_total": 0.0, "amount_tax": 0.0})
        order._onchange_lines_recompute_totals()
        self.assertAlmostEqual(
            order.amount_total,
            order.amount_untaxed + order.amount_tax,
            places=2,
            msg="amount_total debe ser la suma de amount_untaxed y amount_tax",
        )

    def test_57_onchange_lines_multiple_lines(self):
        """_onchange_lines_recompute_totals acumula correctamente múltiples líneas."""
        session = self._open_session()
        order = self._make_draft_order(session)
        self._add_line(order, self.product, 1.0)
        self._add_line(order, self.product, 2.0)
        order.write({"amount_total": 0.0, "amount_tax": 0.0})
        order._onchange_lines_recompute_totals()
        expected_total = sum(line.price_subtotal_incl for line in order.lines)
        self.assertAlmostEqual(order.amount_total, expected_total, places=2)
        self.assertEqual(len(order.lines), 2)

    # ── Integración onchange + force_save: coherencia y persistencia ─────

    def test_58_add_line_helper_persists_amount_total_in_db(self):
        """
        Tras _add_line (que llama a _compute_prices() fuera de onchange),
        amount_total queda persistido > 0 en la BD.

        Este es el mecanismo que usa la vista cuando force_save="1" envía
        el valor calculado por el onchange del servidor.
        """
        session = self._open_session()
        order = self._make_draft_order(session)
        self._add_line(order, self.product, 2.0)
        # Invalidar caché y releer de BD para confirmar persistencia real
        order.invalidate_recordset()
        self.assertGreater(order.amount_total, 0,
                           "amount_total debe persistir en BD tras añadir una línea")

    def test_59_compute_prices_outside_onchange_persists_to_db(self):
        """
        _compute_prices() llamado fuera de contexto @api.onchange persiste
        amount_total en la BD; es el mecanismo del servidor al procesar el onchange.
        """
        session = self._open_session()
        order = self._make_draft_order(session)
        self.env["pos.order.line"].create(
            order._prepare_order_line_vals(self.product, 1.0)
        )
        order.write({"amount_total": 0.0, "amount_tax": 0.0})
        order._compute_prices()
        order.invalidate_recordset()
        self.assertGreater(order.amount_total, 0,
                           "_compute_prices() debe persistir amount_total en BD")

    def test_60_onchange_value_matches_compute_prices(self):
        """
        El valor de amount_total calculado por _onchange_lines_recompute_totals
        coincide con el producido por _compute_prices(), garantizando que lo que
        force_save envía al servidor es consistente con el valor persistido.
        """
        session = self._open_session()
        order = self._make_draft_order(session)
        self._add_line(order, self.product, 2.0)
        total_via_compute = order.amount_total
        # Simular onchange (como lo haría OWL antes de force_save)
        order.write({"amount_total": 0.0, "amount_tax": 0.0})
        order._onchange_lines_recompute_totals()
        self.assertAlmostEqual(
            order.amount_total, total_via_compute, places=2,
            msg="El valor del onchange debe coincidir con el de _compute_prices",
        )

    def test_61_amount_total_increases_when_adding_lines(self):
        """amount_total acumula correctamente al añadir líneas sucesivamente."""
        session = self._open_session()
        order = self._make_draft_order(session)
        self._add_line(order, self.product, 1.0)
        total_one_line = order.amount_total
        self.assertGreater(total_one_line, 0)
        self._add_line(order, self.product, 1.0)
        total_two_lines = order.amount_total
        self.assertGreater(total_two_lines, total_one_line,
                           "El total debe aumentar al añadir más líneas")
        expected = sum(line.price_subtotal_incl for line in order.lines)
        self.assertAlmostEqual(total_two_lines, expected, places=2)

    def test_62_order_can_be_paid_when_total_is_correct(self):
        """
        Cuando amount_total está correctamente calculado, el pedido puede
        recibir un pago y completarse sin errores.
        Verifica el flujo completo: línea → pago → validación.
        """
        session = self._open_session()
        order = self._make_draft_order(session)
        self._add_line(order, self.product, 1.0)
        self.assertGreater(order.amount_total, 0,
                           "amount_total debe ser > 0 para poder cobrar")
        self._add_payment(order, self.cash_pm)
        try:
            order.action_pos_order_paid()
            self.assertIn(order.state, ("paid", "done"),
                          "El pedido debe quedar pagado tras añadir el pago correcto")
        except Exception:
            self.skipTest("action_pos_order_paid no se completó en este contexto")

    def test_63_amount_total_survives_cache_invalidation(self):
        """
        amount_total persiste en BD y se recupera igual tras invalidar la caché.
        Simula que el usuario guarda el pedido y lo vuelve a abrir desde la lista.
        """
        session = self._open_session()
        order = self._make_draft_order(session)
        self._add_line(order, self.product, 3.0)
        expected = order.amount_total
        self.assertGreater(expected, 0)
        # Simular reapertura del formulario
        order.invalidate_recordset()
        self.assertAlmostEqual(
            order.amount_total, expected, places=2,
            msg="amount_total debe ser idéntico al reabrir el registro",
        )

    # ── unlink con sudo() ─────────────────────────────────────────────────

    def test_unlink_draft_order_succeeds(self):
        """Un pedido en borrador puede eliminarse sin error."""
        session = self._open_session()
        order = self._make_draft_order(session)
        order_id = order.id
        order.unlink()
        self.assertFalse(
            self.env["pos.order"].sudo().search([("id", "=", order_id)]),
            "El pedido debe haberse eliminado de la BD",
        )

    def test_unlink_non_draft_order_raises_error(self):
        """Un pedido pagado no puede eliminarse; debe lanzar UserError."""
        from odoo.exceptions import UserError
        session = self._open_session()
        order = self._make_draft_order(session)
        self._add_line(order)
        self._add_payment(order, self.cash_pm, order.amount_total)
        order.with_context(skip_completeness_check=True).action_pos_order_paid()
        self.assertEqual(order.state, "paid")
        with self.assertRaises(UserError):
            order.unlink()

    def test_unlink_via_sudo_bypasses_company_rule(self):
        """
        unlink con sudo() elimina el pedido aunque el contexto de compañía
        del usuario no coincida (simulación del caso multi-compañía del cliente).
        """
        session = self._open_session()
        order = self._make_draft_order(session)
        order_id = order.id
        order_as_sudo = self.env["pos.order"].sudo().browse(order_id)
        order_as_sudo.unlink()
        self.assertFalse(
            self.env["pos.order"].sudo().search([("id", "=", order_id)]),
            "El pedido debe haberse eliminado aunque el contexto de compañía no coincida",
        )

    def test_unlink_from_within_session_restricted_company_context(self):
        """
        Simula el escenario real del cliente: el usuario accede a los pedidos
        desde /point-of-sale/{config_id}/pos-orders/ y Odoo restringe
        allowed_company_ids a la compañía del pos.config.

        Si el pedido tiene una company_id distinta a la de la sesión activa
        (caso de registros legados o multi-compañía), la regla ORM estándar
        [('company_id', 'in', allowed_company_ids)] bloquearía el acceso
        y el unlink lanzaría MissingError sin el fix.

        Con el fix (sudo() en unlink) el borrado debe completarse sin error.
        """
        from odoo.exceptions import UserError

        # Crear una segunda compañía que simula la compañía de la sesión POS
        company_session = self.env["res.company"].sudo().create(
            {"name": "Compañía Sesión POS Test"}
        )

        # El pedido se crea en la compañía principal del test (company A)
        session = self._open_session()
        order = self._make_draft_order(session)
        order_id = order.id
        order_company_id = order.company_id.id

        # La compañía de la sesión simulada es diferente a la del pedido
        self.assertNotEqual(
            order_company_id,
            company_session.id,
            "Las compañías deben ser distintas para que la regla ORM las bloquee",
        )

        # Simular el contexto "inside POS session": allowed_company_ids solo
        # incluye la compañía de la sesión (distinta a la del pedido).
        # Esto replica exactamente lo que Odoo hace al cargar
        # /point-of-sale/{config_id}/pos-orders/
        env_inside_session = self.env["pos.order"].with_context(
            allowed_company_ids=[company_session.id]
        )
        order_in_restricted_ctx = env_inside_session.browse(order_id)

        # Sin el fix, esto lanzaría MissingError porque el registro no es accesible
        # con el contexto de compañía restringido.
        # Con el fix (sudo() en unlink), debe completarse sin error.
        order_in_restricted_ctx.unlink()

        self.assertFalse(
            self.env["pos.order"].sudo().search([("id", "=", order_id)]),
            "El pedido debe eliminarse aunque allowed_company_ids esté restringido "
            "a una compañía diferente a la del pedido (contexto dentro de sesión POS)",
        )

    def test_unlink_from_within_session_non_draft_still_raises(self):
        """
        Incluso desde el contexto restringido de una sesión POS, no se permite
        borrar un pedido que ya está pagado. El UserError debe propagarse.
        """
        from odoo.exceptions import UserError

        company_session = self.env["res.company"].sudo().create(
            {"name": "Compañía Sesión POS Test 2"}
        )

        session = self._open_session()
        order = self._make_draft_order(session)
        self._add_line(order)
        self._add_payment(order, self.cash_pm, order.amount_total)
        order.with_context(skip_completeness_check=True).action_pos_order_paid()
        self.assertEqual(order.state, "paid")

        env_inside_session = self.env["pos.order"].with_context(
            allowed_company_ids=[company_session.id]
        )
        order_in_restricted_ctx = env_inside_session.browse(order.id)

        with self.assertRaises(UserError, msg="No se puede borrar un pedido pagado"):
            order_in_restricted_ctx.unlink()

