# Copyright 2024 Xtendoo
# License OPL-1
"""
Tests de cobertura para el flujo completo de cobro en POS Convencional.

Comportamiento esperado:
  - CARD: pos.make.payment.check() debe cerrar el pedido y devolver
    ir.actions.client tag=pos_conventional_new_order SIN ask_new_order;
    el JS navega directamente al nuevo pedido sin mostrar ningún diálogo.
  - CASH: pos.make.payment.wizard._execute_validation() debe cerrar el pedido,
    gestionar el cambio y devolver ir.actions.client
    tag=pos_conventional_new_order SIN ask_new_order (navegación directa).
  - Ambos flujos (CARD y CASH) navegan directamente al nuevo pedido.
  - POS no convencional: devuelve act_window_close (sin navegar a nuevo pedido).
"""
from odoo.tests.common import tagged
from odoo.exceptions import UserError
from odoo.addons.pos_conventional_core.tests.common import PosConventionalTestCommon


@tagged("pos_conventional_core", "-standard")
class TestPaymentFlow(PosConventionalTestCommon):
    """Tests del flujo completo de pago: wizard, cierre de pedido y nuevo pedido."""

    # ── Helpers internos ──────────────────────────────────────────────────

    def _pay_card_check(self, order):
        """Crea un wizard pos.make.payment (CARD) y llama check()."""
        wizard = self.env["pos.make.payment"].with_context(
            active_id=order.id, card_payment=True
        ).create({
            "amount": order.amount_total,
            "payment_method_id": self.card_pm.id,
        })
        return wizard.check()

    def _pay_cash_wizard_validate(self, order, tendered=None):
        """Crea un wizard pos.make.payment.wizard (CASH) y llama action_validate()."""
        tendered = tendered if tendered is not None else order.amount_total
        wizard = self.env["pos.make.payment.wizard"].with_context(
            active_id=order.id
        ).create({
            "order_id": order.id,
            "payment_method_id": self.cash_pm.id,
            "amount_tendered": tendered,
        })
        return wizard, wizard.action_validate()

    def _order_with_line(self, session=None):
        """Crea un pedido con una línea de producto."""
        session = session or self._open_session()
        order = self._make_draft_order(session)
        self._add_line(order)
        return order

    # ══════════════════════════════════════════════════════════════════════
    # BLOQUE 1 — CARD: pos.make.payment.check() con card_payment=True
    # ══════════════════════════════════════════════════════════════════════

    def test_01_card_check_returns_client_action_type(self):
        """check() CARD devuelve ir.actions.client (no act_window ni False)."""
        order = self._order_with_line()
        action = self._pay_card_check(order)
        self.assertIsInstance(action, dict, "check() debe devolver un dict")
        self.assertEqual(
            action.get("type"), "ir.actions.client",
            f"Tipo esperado 'ir.actions.client', obtenido: {action.get('type')}",
        )

    def test_02_card_check_returns_new_order_tag(self):
        """check() CARD devuelve tag=pos_conventional_new_order."""
        order = self._order_with_line()
        action = self._pay_card_check(order)
        self.assertEqual(
            action.get("tag"), "pos_conventional_new_order",
            f"Tag esperado 'pos_conventional_new_order', obtenido: {action.get('tag')}",
        )

    def test_03_card_check_no_ask_new_order(self):
        """check() CARD NO incluye ask_new_order: el flujo navega directo al nuevo pedido."""
        order = self._order_with_line()
        action = self._pay_card_check(order)
        params = action.get("params", {})
        self.assertFalse(
            params.get("ask_new_order"),
            f"CARD NO debe incluir ask_new_order (flujo directo sin diálogo). params={params}",
        )

    def test_04_card_check_order_becomes_paid(self):
        """Tras check() CARD el pedido queda en estado 'paid' o 'done'."""
        order = self._order_with_line()
        self._pay_card_check(order)
        self.assertIn(
            order.state, ("paid", "done"),
            f"Estado esperado 'paid'/'done', actual: {order.state}",
        )

    def test_05_card_check_params_has_config_id(self):
        """Los params del action CARD contienen config_id válido."""
        order = self._order_with_line()
        action = self._pay_card_check(order)
        params = action.get("params", {})
        self.assertIn("config_id", params, f"Falta config_id en params: {params}")
        self.assertEqual(params["config_id"], order.config_id.id)

    def test_06_card_check_params_has_default_session_id(self):
        """Los params del action CARD contienen default_session_id válido."""
        order = self._order_with_line()
        action = self._pay_card_check(order)
        params = action.get("params", {})
        self.assertIn("default_session_id", params,
                      f"Falta default_session_id en params: {params}")
        self.assertEqual(params["default_session_id"],
                         order.session_id.id)

    def test_07_card_check_non_conventional_pos_returns_window_close(self):
        """check() CARD en POS no convencional NO devuelve pos_conventional_new_order."""
        config_normal = self.env["pos.config"].create({
            "name": "POS Normal (no convencional)",
            "pos_non_touch": False,
            "payment_method_ids": [(6, 0, [self.card_pm.id])],
        })
        session = self._open_session(config_normal)
        order = self._order_with_line(session)
        wizard = self.env["pos.make.payment"].with_context(
            active_id=order.id, card_payment=True
        ).create({
            "amount": order.amount_total,
            "payment_method_id": self.card_pm.id,
        })
        action = wizard.check()
        self.assertNotEqual(
            action.get("tag"), "pos_conventional_new_order",
            "POS no convencional NO debe devolver pos_conventional_new_order",
        )
        self.assertEqual(
            action.get("type"), "ir.actions.act_window_close",
            f"POS no convencional debe retornar act_window_close. action={action}",
        )

    def test_08_card_check_zero_amount_order_stays_draft(self):
        """check() CARD con amount=0 NO valida el pedido (permanece en draft)."""
        order = self._order_with_line()
        self.assertGreater(order.amount_total, 0, "El pedido necesita tener un total > 0")
        try:
            wizard = self.env["pos.make.payment"].with_context(
                active_id=order.id, card_payment=True
            ).create({
                "amount": 0.0,
                "payment_method_id": self.card_pm.id,
            })
            wizard.check()
        except Exception:
            pass  # launch_payment() puede fallar fuera del TPV
        self.assertEqual(
            order.state, "draft",
            "Con amount=0, el pedido NO debe cambiar de estado 'draft'",
        )

    # ══════════════════════════════════════════════════════════════════════
    # BLOQUE 2 — CASH: pos.make.payment.wizard._execute_validation()
    # ══════════════════════════════════════════════════════════════════════

    def test_09_cash_wizard_validate_returns_client_action_type(self):
        """action_validate() CASH devuelve ir.actions.client."""
        order = self._order_with_line()
        _wizard, action = self._pay_cash_wizard_validate(order)
        self.assertIsInstance(action, dict)
        self.assertEqual(
            action.get("type"), "ir.actions.client",
            f"Tipo esperado 'ir.actions.client', obtenido: {action.get('type')}",
        )

    def test_10_cash_wizard_validate_returns_new_order_tag(self):
        """action_validate() CASH devuelve tag=pos_conventional_new_order."""
        order = self._order_with_line()
        _wizard, action = self._pay_cash_wizard_validate(order)
        self.assertEqual(
            action.get("tag"), "pos_conventional_new_order",
            f"Tag esperado 'pos_conventional_new_order', obtenido: {action.get('tag')}",
        )

    def test_11_cash_wizard_validate_no_ask_new_order(self):
        """action_validate() CASH NO incluye ask_new_order (navegación directa)."""
        order = self._order_with_line()
        _wizard, action = self._pay_cash_wizard_validate(order)
        params = action.get("params", {})
        self.assertFalse(
            params.get("ask_new_order"),
            f"CASH NO debe tener ask_new_order=True. params={params}",
        )

    def test_12_cash_wizard_validate_order_becomes_paid(self):
        """Tras action_validate() CASH el pedido queda en 'paid' o 'done'."""
        order = self._order_with_line()
        self._pay_cash_wizard_validate(order)
        self.assertIn(
            order.state, ("paid", "done"),
            f"Estado esperado 'paid'/'done', actual: {order.state}",
        )

    def test_13_cash_wizard_params_has_config_and_session(self):
        """action_validate() CASH → params contiene config_id y default_session_id."""
        order = self._order_with_line()
        _wizard, action = self._pay_cash_wizard_validate(order)
        params = action.get("params", {})
        self.assertIn("config_id", params)
        self.assertIn("default_session_id", params)
        self.assertEqual(params["config_id"], order.config_id.id)
        self.assertEqual(params["default_session_id"], order.session_id.id)

    def test_14_cash_wizard_with_change_returns_new_order(self):
        """Con importe entregado > total (cambio), sigue devolviendo new_order."""
        order = self._order_with_line()
        total = order.amount_total
        if total <= 0:
            self.skipTest("Pedido sin importe")
        _wizard, action = self._pay_cash_wizard_validate(order, tendered=total + 50.0)
        self.assertEqual(
            action.get("tag"), "pos_conventional_new_order",
            f"Con cambio debe devolver new_order. action={action}",
        )

    def test_15_cash_wizard_with_change_order_becomes_paid(self):
        """Con importe entregado > total, el pedido también queda en 'paid'."""
        order = self._order_with_line()
        total = order.amount_total
        if total <= 0:
            self.skipTest("Pedido sin importe")
        self._pay_cash_wizard_validate(order, tendered=total + 50.0)
        self.assertIn(
            order.state, ("paid", "done"),
            f"Estado esperado 'paid'/'done', actual: {order.state}",
        )

    def test_16_cash_wizard_with_change_adds_negative_payment(self):
        """Con cambio a devolver, se registra un pago negativo en el pedido."""
        order = self._order_with_line()
        total = order.amount_total
        if total <= 0:
            self.skipTest("Pedido sin importe")
        extra = 20.0
        wizard, _action = self._pay_cash_wizard_validate(order, tendered=total + extra)
        if wizard.amount_change > 0.01:
            negative = order.payment_ids.filtered(lambda p: p.amount < 0)
            self.assertTrue(
                len(negative) > 0,
                "Debe existir al menos un pago negativo de cambio",
            )
            self.assertAlmostEqual(
                abs(sum(negative.mapped("amount"))),
                wizard.amount_change,
                places=2,
                msg="El pago negativo debe coincidir con el cambio calculado",
            )

    def test_17_cash_wizard_insufficient_payment_raises_user_error(self):
        """action_validate() con importe insuficiente lanza UserError."""
        order = self._order_with_line()
        total = order.amount_total
        if total <= 0:
            self.skipTest("Pedido sin importe")
        with self.assertRaises(UserError):
            self._pay_cash_wizard_validate(order, tendered=total / 2)

    def test_18_cash_wizard_non_conventional_returns_window_close(self):
        """action_validate() en POS no convencional devuelve act_window_close."""
        fresh_cash = self._make_fresh_cash_pm()
        config_normal = self.env["pos.config"].create({
            "name": "POS Normal Cash Test",
            "pos_non_touch": False,
            "payment_method_ids": [(6, 0, [fresh_cash.id])],
        })
        session = self._open_session(config_normal)
        order = self._order_with_line(session)
        wizard = self.env["pos.make.payment.wizard"].with_context(
            active_id=order.id
        ).create({
            "order_id": order.id,
            "payment_method_id": fresh_cash.id,
            "amount_tendered": order.amount_total,
        })
        action = wizard.action_validate()
        self.assertEqual(
            action.get("type"), "ir.actions.act_window_close",
            f"POS no convencional debe retornar act_window_close. action={action}",
        )
        self.assertIsNone(
            action.get("tag"),
            "POS no convencional NO debe incluir tag pos_conventional_new_order",
        )

    # ══════════════════════════════════════════════════════════════════════
    # BLOQUE 3 — Enrutamiento: action_pos_convention_pay_with_method
    # ══════════════════════════════════════════════════════════════════════

    def test_19_pay_with_card_method_returns_new_order_action(self):
        """action_pos_convention_pay_with_method CARD → pos_conventional_new_order."""
        order = self._order_with_line()
        action = order.action_pos_convention_pay_with_method(self.card_pm)
        self.assertIsInstance(action, dict)
        self.assertEqual(
            action.get("tag"), "pos_conventional_new_order",
            f"CARD debe devolver new_order. tag={action.get('tag')}",
        )

    def test_20_pay_with_card_no_ask_new_order(self):
        """action_pos_convention_pay_with_method CARD → navega directo, sin ask_new_order."""
        order = self._order_with_line()
        action = order.action_pos_convention_pay_with_method(self.card_pm)
        self.assertFalse(
            action.get("params", {}).get("ask_new_order"),
            f"CARD NO debe tener ask_new_order (flujo directo). params={action.get('params')}",
        )

    def test_21_pay_with_card_order_becomes_paid(self):
        """Tras action_pos_convention_pay_with_method CARD, pedido queda 'paid'."""
        order = self._order_with_line()
        order.action_pos_convention_pay_with_method(self.card_pm)
        self.assertIn(
            order.state, ("paid", "done"),
            f"Pedido debe quedar pagado tras CARD. state={order.state}",
        )

    def test_22_pay_with_cash_method_opens_wizard_not_new_order(self):
        """action_pos_convention_pay_with_method CASH abre el wizard (no new_order)."""
        order = self._order_with_line()
        action = order.action_pos_convention_pay_with_method(self.cash_pm)
        self.assertIsInstance(action, dict)
        self.assertEqual(
            action.get("res_model"), "pos.make.payment.wizard",
            f"CASH debe abrir wizard. action={action}",
        )
        self.assertNotEqual(
            action.get("tag"), "pos_conventional_new_order",
            "CASH NO debe devolver directamente new_order (abre wizard primero)",
        )

    def test_23_pay_with_cash_no_ask_new_order_in_wizard_action(self):
        """action_pos_convention_pay_with_method CASH → sin ask_new_order."""
        order = self._order_with_line()
        action = order.action_pos_convention_pay_with_method(self.cash_pm)
        self.assertFalse(
            action.get("params", {}).get("ask_new_order"),
            "El wizard de CASH NO debe contener ask_new_order=True",
        )

    # ══════════════════════════════════════════════════════════════════════
    # BLOQUE 4 — Diferencia CARD vs CASH: ask_new_order
    # ══════════════════════════════════════════════════════════════════════

    def test_24_card_no_ask_new_order_cash_opens_wizard(self):
        """Contraste: CARD devuelve new_order sin ask_new_order; CASH abre wizard.
        Ambos pedidos usan la misma sesión (no se puede abrir dos sesiones del mismo config).
        """
        session = self._open_session()

        order_card = self._order_with_line(session)
        action_card = order_card.action_pos_convention_pay_with_method(self.card_pm)
        self.assertFalse(
            action_card.get("params", {}).get("ask_new_order"),
            "CARD NO debe incluir ask_new_order (flujo directo)",
        )
        self.assertEqual(
            action_card.get("tag"), "pos_conventional_new_order",
            "CARD debe devolver tag=pos_conventional_new_order",
        )

        # Reutilizamos la misma sesión para el pedido CASH
        order_cash = self._order_with_line(session)
        action_cash = order_cash.action_pos_convention_pay_with_method(self.cash_pm)
        self.assertEqual(
            action_cash.get("res_model"), "pos.make.payment.wizard",
            "CASH debe abrir el wizard de pago",
        )
        self.assertFalse(
            action_cash.get("params", {}).get("ask_new_order"),
            "CASH NO debe tener ask_new_order",
        )

    def test_25_both_card_and_cash_navigate_directly(self):
        """Contraste: ambos CARD y CASH devuelven new_order sin ask_new_order.
        Ambos pedidos usan la misma sesión abierta.
        """
        session = self._open_session()

        # CARD
        order_card = self._order_with_line(session)
        action_card = self._pay_card_check(order_card)
        self.assertFalse(action_card.get("params", {}).get("ask_new_order"),
                         "CARD NO debe tener ask_new_order (flujo directo)")

        # CASH — mismo session, ya que no se pueden tener dos sesiones del mismo config
        order_cash = self._order_with_line(session)
        _wizard, action_cash = self._pay_cash_wizard_validate(order_cash)
        self.assertFalse(action_cash.get("params", {}).get("ask_new_order"),
                         "CASH NO debe tener ask_new_order")

        # Ambos deben devolver el mismo tag
        self.assertEqual(action_card.get("tag"), "pos_conventional_new_order")
        self.assertEqual(action_cash.get("tag"), "pos_conventional_new_order")

    # ══════════════════════════════════════════════════════════════════════
    # BLOQUE 5 — action_register_payments_and_validate (flujo popup UI)
    # ══════════════════════════════════════════════════════════════════════

    def test_26_register_and_validate_cash_returns_success_true(self):
        """action_register_payments_and_validate CASH devuelve success=True."""
        order = self._order_with_line()
        result = order.action_register_payments_and_validate([{
            "payment_method_id": self.cash_pm.id,
            "amount": order.amount_total,
        }])
        self.assertTrue(result.get("success"),
                        f"Debe devolver success=True. result={result}")

    def test_27_register_and_validate_card_returns_success_true(self):
        """action_register_payments_and_validate CARD devuelve success=True."""
        order = self._order_with_line()
        result = order.action_register_payments_and_validate([{
            "payment_method_id": self.card_pm.id,
            "amount": order.amount_total,
        }])
        self.assertTrue(result.get("success"),
                        f"Debe devolver success=True. result={result}")

    def test_28_register_and_validate_order_state_becomes_paid(self):
        """Tras action_register_payments_and_validate, el pedido queda 'paid'."""
        order = self._order_with_line()
        order.action_register_payments_and_validate([{
            "payment_method_id": self.cash_pm.id,
            "amount": order.amount_total,
        }])
        self.assertIn(
            order.state, ("paid", "done"),
            f"Pedido debe quedar pagado. state={order.state}",
        )

    def test_29_register_and_validate_action_is_new_order_or_print(self):
        """La acción de register_and_validate es new_order o print_receipt."""
        order = self._order_with_line()
        result = order.action_register_payments_and_validate([{
            "payment_method_id": self.cash_pm.id,
            "amount": order.amount_total,
        }])
        action = result.get("action")
        if isinstance(action, dict):
            self.assertIn(
                action.get("tag"),
                ("pos_conventional_new_order", "pos_conventional_print_receipt_client"),
                f"Acción inesperada: {action}",
            )

    def test_30_register_and_validate_overpayment_adds_change(self):
        """Con sobrepago CASH, se añade un pago negativo de cambio."""
        order = self._order_with_line()
        total = order.amount_total
        if total <= 0:
            self.skipTest("Pedido sin importe")
        extra = 15.0
        order.action_register_payments_and_validate([{
            "payment_method_id": self.cash_pm.id,
            "amount": total + extra,
        }])
        negative = order.payment_ids.filtered(lambda p: p.amount < 0)
        self.assertTrue(
            len(negative) > 0,
            "Con sobrepago debe registrarse un pago negativo de cambio",
        )
        self.assertAlmostEqual(
            abs(sum(negative.mapped("amount"))),
            extra,
            places=2,
            msg=f"El cambio debe ser {extra}€. pagos_negativos={negative.mapped('amount')}",
        )

