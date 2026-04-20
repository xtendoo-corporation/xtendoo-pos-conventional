# Copyright 2024 Xtendoo
# License OPL-1
"""
Tests de cobertura para el flujo completo de cobro en POS Convencional.

Comportamiento esperado:
  - CARD: pos.make.payment.check() debe cerrar el pedido y devolver:
    · ir.actions.client tag=pos_conventional_print_receipt_client cuando
      iface_print_auto=True y se generó factura.
    · ir.actions.client tag=pos_conventional_new_order cuando
      iface_print_auto=False (independientemente de si hay factura).
  - CASH: pos.make.payment.wizard._execute_validation() mismo comportamiento.
    Adicionalmente, action_validate_print() imprime siempre (print_invoice=True).
  - La configuración de test usa iface_print_auto=False (valor por defecto),
    por lo que los tests del flujo normal esperan pos_conventional_new_order.
  - POS no convencional: devuelve act_window_close (sin navegar a nuevo pedido).

Nota: Esta clase requiere que pos_conventional_core esté cargado (campo
pos_non_touch en pos.config). Si el módulo no está cargado en el momento de
ejecutar estos tests (ocurre cuando pos_conventional_payment_wizard se carga
ANTES de pos_conventional_core en el orden de dependencias), los tests se
omiten automáticamente.
"""
import unittest
from odoo.tests.common import tagged
from odoo.exceptions import UserError
from odoo.addons.pos_conventional_core.tests.common import PosConventionalTestCommon


@tagged("pos_conventional_core", "-standard", "post_install", "-at_install")
class TestPaymentFlow(PosConventionalTestCommon):
    """Tests del flujo completo de pago: wizard, cierre de pedido y nuevo pedido."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if "pos_non_touch" not in cls.env["pos.config"]._fields:
            raise unittest.SkipTest(
                "pos_conventional_core no está cargado: campo pos_non_touch no disponible. "
                "Estos tests se ejecutan correctamente cuando pos_conventional_core "
                "está completamente inicializado."
            )

    # ── Helpers internos ──────────────────────────────────────────────────

    def _get_final_params(self, action):
        """Extrae los params del tag final.

        Si la acción es pos_conventional_print_receipt_client, los parámetros
        de navegación (config_id, default_session_id) están en next_action.params.
        """
        if action.get("tag") == "pos_conventional_print_receipt_client":
            return action.get("params", {}).get("next_action", {}).get("params", {})
        return action.get("params", {})

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
        """check() CARD devuelve tag=pos_conventional_new_order cuando iface_print_auto=False.
        Cuando iface_print_auto=True y hay factura, devuelve pos_conventional_print_receipt_client."""
        order = self._order_with_line()
        action = self._pay_card_check(order)
        # El config de test tiene iface_print_auto=False → new_order
        self.assertEqual(
            action.get("tag"), "pos_conventional_new_order",
            f"Con iface_print_auto=False debe devolver 'pos_conventional_new_order'. tag={action.get('tag')}",
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
        """Los params del action CARD contienen config_id válido.
        Con iface_print_auto=False la acción es new_order y params están en el nivel raíz.
        Con iface_print_auto=True la acción es print_receipt_client y están en next_action.params."""
        order = self._order_with_line()
        action = self._pay_card_check(order)
        params = self._get_final_params(action)
        self.assertIn("config_id", params, f"Falta config_id en params: {params}")
        self.assertEqual(params["config_id"], order.config_id.id)

    def test_06_card_check_params_has_default_session_id(self):
        """Los params del action CARD contienen default_session_id válido.
        Con iface_print_auto=False la acción es new_order y params están en el nivel raíz.
        Con iface_print_auto=True la acción es print_receipt_client y están en next_action.params."""
        order = self._order_with_line()
        action = self._pay_card_check(order)
        params = self._get_final_params(action)
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
        """action_validate() CASH devuelve tag=pos_conventional_new_order cuando iface_print_auto=False.
        Cuando iface_print_auto=True devuelve pos_conventional_print_receipt_client si hay factura."""
        order = self._order_with_line()
        _wizard, action = self._pay_cash_wizard_validate(order)
        # El config de test tiene iface_print_auto=False → new_order
        self.assertEqual(
            action.get("tag"), "pos_conventional_new_order",
            f"Con iface_print_auto=False debe devolver 'pos_conventional_new_order'. tag={action.get('tag')}",
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
        """action_validate() CASH → params contiene config_id y default_session_id.
        Con iface_print_auto=False la acción es new_order y params están en el nivel raíz.
        Con iface_print_auto=True están en next_action.params (usa _get_final_params)."""
        order = self._order_with_line()
        _wizard, action = self._pay_cash_wizard_validate(order)
        params = self._get_final_params(action)
        self.assertIn("config_id", params)
        self.assertIn("default_session_id", params)
        self.assertEqual(params["config_id"], order.config_id.id)
        self.assertEqual(params["default_session_id"], order.session_id.id)
        self.assertIn("previous_sale_total", params)
        self.assertIn("previous_sale_change", params)
        self.assertIn("previous_sale_currency", params)
        self.assertAlmostEqual(params["previous_sale_total"], order.amount_total, places=2)
        self.assertAlmostEqual(params["previous_sale_change"], 0.0, places=2)
        self.assertEqual(params["previous_sale_currency"], order.currency_id.symbol or "€")

    def test_14_cash_wizard_with_change_returns_new_order(self):
        """Con importe entregado > total (cambio), sigue devolviendo new_order (iface_print_auto=False)."""
        order = self._order_with_line()
        total = order.amount_total
        if total <= 0:
            self.skipTest("Pedido sin importe")
        _wizard, action = self._pay_cash_wizard_validate(order, tendered=total + 50.0)
        self.assertEqual(
            action.get("tag"), "pos_conventional_new_order",
            f"Con cambio e iface_print_auto=False debe devolver new_order. action={action}",
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

    def test_17_cash_wizard_insufficient_payment_returns_warning(self):
        """action_validate() con importe insuficiente devuelve un banner warning."""
        order = self._order_with_line()
        total = order.amount_total
        if total <= 0:
            self.skipTest("Pedido sin importe")
        _wizard, action = self._pay_cash_wizard_validate(order, tendered=total / 2)
        self.assertEqual(action.get("type"), "ir.actions.client")
        self.assertEqual(action.get("tag"), "display_notification")
        self.assertEqual(action.get("params", {}).get("type"), "warning")
        self.assertIn("insuficiente", action.get("params", {}).get("message", "").lower())
        self.assertEqual(order.state, "draft")

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
        """action_pos_convention_pay_with_method CARD → pos_conventional_new_order
        cuando iface_print_auto=False. Con iface_print_auto=True y factura devuelve
        pos_conventional_print_receipt_client."""
        order = self._order_with_line()
        action = order.action_pos_convention_pay_with_method(self.card_pm)
        self.assertIsInstance(action, dict)
        # El config de test tiene iface_print_auto=False → new_order
        self.assertEqual(
            action.get("tag"), "pos_conventional_new_order",
            f"Con iface_print_auto=False debe devolver new_order. tag={action.get('tag')}",
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
        """Contraste: CARD devuelve new_order sin ask_new_order (iface_print_auto=False);
        CASH abre wizard. Ambos pedidos usan la misma sesión.
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
            "Con iface_print_auto=False CARD debe devolver tag=pos_conventional_new_order",
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
        """Contraste: ambos CARD y CASH devuelven new_order sin ask_new_order
        cuando iface_print_auto=False. Ambos pedidos usan la misma sesión abierta.
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

        # Con iface_print_auto=False ambos deben devolver new_order
        self.assertEqual(action_card.get("tag"), "pos_conventional_new_order",
                         f"CARD tag inesperado: {action_card.get('tag')}")
        self.assertEqual(action_cash.get("tag"), "pos_conventional_new_order",
                         f"CASH tag inesperado: {action_cash.get('tag')}")

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

    # ══════════════════════════════════════════════════════════════════════
    # BLOQUE 6 — iface_print_auto=True: debe imprimir cuando hay factura
    # ══════════════════════════════════════════════════════════════════════

    def test_31_card_with_iface_print_auto_returns_print_receipt(self):
        """Con iface_print_auto=True y factura generada, check() CARD devuelve
        pos_conventional_print_receipt_client con next_action=pos_conventional_new_order."""
        fresh_cash = self._make_fresh_cash_pm()
        config_print = self.env["pos.config"].create({
            "name": "POS Print Auto Test",
            "pos_non_touch": True,
            "iface_print_auto": True,
            "payment_method_ids": [(6, 0, [fresh_cash.id, self.card_pm.id])],
            "invoice_journal_id": self.invoice_journal.id,
            "default_partner_id": self.partner.id,
        })
        session = self._open_session(config_print)
        order = self._order_with_line(session)
        wizard = self.env["pos.make.payment"].with_context(
            active_id=order.id, card_payment=True
        ).create({
            "amount": order.amount_total,
            "payment_method_id": self.card_pm.id,
        })
        action = wizard.check()
        self.assertEqual(
            action.get("tag"), "pos_conventional_print_receipt_client",
            f"Con iface_print_auto=True y factura debe devolver print_receipt_client. tag={action.get('tag')}",
        )
        next_action = action.get("params", {}).get("next_action", {})
        self.assertEqual(
            next_action.get("tag"), "pos_conventional_new_order",
            f"next_action debe ser pos_conventional_new_order. next_action={next_action}",
        )

    def test_32_cash_with_iface_print_auto_returns_print_receipt(self):
        """Con iface_print_auto=True y factura generada, action_validate() CASH devuelve
        pos_conventional_print_receipt_client con next_action=pos_conventional_new_order."""
        fresh_cash = self._make_fresh_cash_pm()
        config_print = self.env["pos.config"].create({
            "name": "POS Print Auto Cash Test",
            "pos_non_touch": True,
            "iface_print_auto": True,
            "payment_method_ids": [(6, 0, [fresh_cash.id])],
            "invoice_journal_id": self.invoice_journal.id,
            "default_partner_id": self.partner.id,
        })
        session = self._open_session(config_print)
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
            action.get("tag"), "pos_conventional_print_receipt_client",
            f"Con iface_print_auto=True y factura debe devolver print_receipt_client. tag={action.get('tag')}",
        )
        next_action = action.get("params", {}).get("next_action", {})
        self.assertEqual(
            next_action.get("tag"), "pos_conventional_new_order",
            f"next_action debe ser pos_conventional_new_order. next_action={next_action}",
        )

    # ══════════════════════════════════════════════════════════════════════
    # BLOQUE 7 — Banner de cambio: cash_change en params de next_action
    # ══════════════════════════════════════════════════════════════════════

    def test_33_cash_with_change_includes_cash_change_in_params(self):
        """Con cambio a devolver, next_action incluye cash_change en params.

        Valida que al pagar en efectivo con importe mayor al total, la acción de
        navegación al nuevo pedido lleva el importe de cambio para que el frontend
        muestre el banner al cajero.
        """
        order = self._order_with_line()
        total = order.amount_total
        if total <= 0:
            self.skipTest("Pedido sin importe")
        change = 5.0
        _wizard, action = self._pay_cash_wizard_validate(order, tendered=total + change)
        params = self._get_final_params(action)
        self.assertIn(
            "cash_change", params,
            f"Debe existir 'cash_change' en params cuando hay cambio. params={params}",
        )
        self.assertAlmostEqual(
            params["cash_change"],
            change,
            places=2,
            msg=f"El valor de cash_change debe ser {change}. obtenido={params['cash_change']}",
        )
        self.assertAlmostEqual(
            params["previous_sale_total"],
            order.amount_total,
            places=2,
            msg="El resumen debe incluir el total de la venta anterior",
        )
        self.assertAlmostEqual(
            params["previous_sale_change"],
            change,
            places=2,
            msg="El resumen debe incluir el cambio de la venta anterior",
        )

    def test_34_cash_with_change_includes_currency_symbol_in_params(self):
        """Con cambio a devolver, next_action incluye cash_change_currency en params."""
        order = self._order_with_line()
        total = order.amount_total
        if total <= 0:
            self.skipTest("Pedido sin importe")
        _wizard, action = self._pay_cash_wizard_validate(order, tendered=total + 3.0)
        params = self._get_final_params(action)
        self.assertIn(
            "cash_change_currency", params,
            f"Debe incluir 'cash_change_currency' cuando hay cambio. params={params}",
        )
        currency_symbol = order.currency_id.symbol or "€"
        self.assertEqual(
            params["cash_change_currency"],
            currency_symbol,
            f"Símbolo de moneda incorrecto. esperado={currency_symbol}, "
            f"obtenido={params.get('cash_change_currency')}",
        )

    def test_35_cash_exact_amount_no_cash_change_in_params(self):
        """Con importe exacto (sin cambio), next_action NO incluye cash_change en params.

        Cuando el cliente paga exactamente, no hay cambio que mostrar en el banner.
        """
        order = self._order_with_line()
        total = order.amount_total
        if total <= 0:
            self.skipTest("Pedido sin importe")
        _wizard, action = self._pay_cash_wizard_validate(order, tendered=total)
        params = self._get_final_params(action)
        self.assertNotIn(
            "cash_change", params,
            f"Sin cambio NO debe incluir 'cash_change' en params. params={params}",
        )
        self.assertAlmostEqual(
            params["previous_sale_total"],
            order.amount_total,
            places=2,
            msg="El banner debe seguir mostrando el total de la venta anterior aunque no haya cambio",
        )
        self.assertAlmostEqual(
            params["previous_sale_change"],
            0.0,
            places=2,
            msg="Sin cambio, previous_sale_change debe ser 0",
        )

    def test_36_card_flow_includes_previous_sale_summary(self):
        """El flujo de tarjeta también debe enviar total, cambio y moneda al nuevo pedido."""
        order = self._order_with_line()
        action = self._pay_card_check(order)
        params = self._get_final_params(action)
        self.assertAlmostEqual(params["previous_sale_total"], order.amount_total, places=2)
        self.assertAlmostEqual(params["previous_sale_change"], 0.0, places=2)
        self.assertEqual(params["previous_sale_currency"], order.currency_id.symbol or "€")

    def test_37_cash_with_change_in_print_receipt_next_action_params(self):
        """Con iface_print_auto=True y cambio, el cash_change está en next_action.params
        dentro de la acción pos_conventional_print_receipt_client.
        """
        fresh_cash = self._make_fresh_cash_pm()
        config_print = self.env["pos.config"].create({
            "name": "POS Print Auto + Change Banner Test",
            "pos_non_touch": True,
            "iface_print_auto": True,
            "payment_method_ids": [(6, 0, [fresh_cash.id])],
            "invoice_journal_id": self.invoice_journal.id,
            "default_partner_id": self.partner.id,
        })
        session = self._open_session(config_print)
        order = self._order_with_line(session)
        total = order.amount_total
        if total <= 0:
            self.skipTest("Pedido sin importe")
        change = 7.0
        wizard = self.env["pos.make.payment.wizard"].with_context(
            active_id=order.id
        ).create({
            "order_id": order.id,
            "payment_method_id": fresh_cash.id,
            "amount_tendered": total + change,
        })
        action = wizard.action_validate()
        self.assertEqual(
            action.get("tag"), "pos_conventional_print_receipt_client",
            f"Con iface_print_auto=True debe devolver print_receipt_client. tag={action.get('tag')}",
        )
        # cash_change debe estar en next_action.params (donde lo leerá pos_new_order_action.js)
        next_action_params = action.get("params", {}).get("next_action", {}).get("params", {})
        self.assertIn(
            "cash_change", next_action_params,
            f"cash_change debe estar en next_action.params. next_action_params={next_action_params}",
        )
        self.assertAlmostEqual(
            next_action_params["cash_change"],
            change,
            places=2,
            msg=f"cash_change incorrecto. esperado={change}, obtenido={next_action_params.get('cash_change')}",
        )
        self.assertAlmostEqual(next_action_params["previous_sale_total"], order.amount_total, places=2)
        self.assertAlmostEqual(next_action_params["previous_sale_change"], change, places=2)

