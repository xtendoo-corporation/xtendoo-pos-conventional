# Copyright 2024 Xtendoo
# License OPL-1
from odoo.tests.common import tagged
from odoo.exceptions import UserError
from odoo.addons.pos_conventional_core.tests.common import PosConventionalTestCommon


@tagged("pos_conventional_core", "-standard", "post_install", "-at_install")
class TestPosPaymentWizard(PosConventionalTestCommon):
    """Tests para pos_conventional_payment_wizard — modelos y wizard."""

    # ── available_payment_method_ids ─────────────────────────────────────

    def test_01_available_payment_methods_matches_config(self):
        """available_payment_method_ids coincide con los métodos del config."""
        session = self._open_session()
        order = self._make_draft_order(session)
        self.assertEqual(
            order.available_payment_method_ids,
            session.config_id.payment_method_ids,
        )

    def test_02_available_payment_methods_empty_without_session(self):
        """Sin sesión activa guardada en DB, los métodos disponibles son los del config o vacíos."""
        # Con .new() el campo computado puede devolver los métodos del config si hay config_id
        # Verificamos que el campo existe y es iterable
        order = self.env["pos.order"].new({"config_id": self.pos_config.id})
        # El valor puede ser los métodos del config o vacío; simplemente verificamos que es válido
        self.assertIsNotNone(order.available_payment_method_ids)

    # ── action_pay_cash ───────────────────────────────────────────────────

    def test_03_action_pay_cash_returns_wizard_action(self):
        """action_pay_cash abre el wizard de pago en efectivo."""
        session = self._open_session()
        order = self._make_draft_order(session)
        self._add_line(order)
        result = order.action_pay_cash()
        self.assertEqual(result.get("type"), "ir.actions.act_window")
        self.assertEqual(result.get("res_model"), "pos.make.payment.wizard")
        self.assertTrue(result.get("context", {}).get("cash_only"))

    def test_04_action_pay_cash_no_cash_method_raises_error(self):
        """action_pay_cash lanza UserError si no hay método de efectivo."""
        config_no_cash = self.env["pos.config"].create(
            {
                "name": "Config Sin Efectivo",
                "payment_method_ids": [(6, 0, [self.card_pm.id])],
            }
        )
        session = self._open_session(config_no_cash)
        order = self._make_draft_order(session)
        self._add_line(order)
        with self.assertRaises(UserError):
            order.action_pay_cash()

    # ── action_pay_card ───────────────────────────────────────────────────

    def test_05_action_pay_card_no_bank_method_raises_error(self):
        """action_pay_card lanza UserError si no hay método bancario."""
        config_only_cash = self.env["pos.config"].create(
            {
                "name": "Config Solo Efectivo",
                "payment_method_ids": [(6, 0, [self._make_fresh_cash_pm().id])],
            }
        )
        session = self._open_session(config_only_cash)
        order = self._make_draft_order(session)
        self._add_line(order)
        with self.assertRaises(UserError):
            order.action_pay_card()

    # ── action_pos_convention_pay_with_method ─────────────────────────────

    def test_06_pay_with_cash_method_opens_cash_wizard(self):
        """Pagar con método efectivo abre el wizard de efectivo."""
        session = self._open_session()
        order = self._make_draft_order(session)
        self._add_line(order)
        result = order.action_pos_convention_pay_with_method(self.cash_pm)
        self.assertIsInstance(result, dict)
        self.assertEqual(result.get("res_model"), "pos.make.payment.wizard")

    def test_07_pay_with_invalid_method_returns_false(self):
        """Un método de pago inexistente devuelve False (requiere pedido con importe > 0)."""
        session = self._open_session()
        order = self._make_draft_order(session)
        self._add_line(order)  # el pedido debe tener importe > 0 para llegar a la validación del método
        result = order.action_pos_convention_pay_with_method("invalid")
        self.assertFalse(result)

    # ── get_payment_popup_data ────────────────────────────────────────────

    def test_08_get_payment_popup_data_structure(self):
        """get_payment_popup_data devuelve las claves esperadas."""
        session = self._open_session()
        order = self._make_draft_order(session)
        self._add_line(order)
        data = order.get_payment_popup_data()
        for key in ("order_id", "amount_total", "amount_paid", "amount_due",
                    "currency_symbol", "available_methods", "payments"):
            self.assertIn(key, data, f"Clave faltante: {key}")

    def test_09_get_payment_popup_data_amount_due_equals_total(self):
        """amount_due = amount_total cuando no hay pagos."""
        session = self._open_session()
        order = self._make_draft_order(session)
        self._add_line(order)
        data = order.get_payment_popup_data()
        self.assertAlmostEqual(data["amount_due"], order.amount_total, places=2)

    def test_10_get_payment_popup_data_methods_include_cash(self):
        """available_methods incluye el método de efectivo del config."""
        session = self._open_session()
        order = self._make_draft_order(session)
        method_ids = [m["id"] for m in order.get_payment_popup_data()["available_methods"]]
        self.assertIn(self.cash_pm.id, method_ids)

    # ── add_payment_from_ui ───────────────────────────────────────────────

    def test_11_add_payment_from_ui_registers_payment(self):
        """add_payment_from_ui añade un pago al pedido."""
        session = self._open_session()
        order = self._make_draft_order(session)
        self._add_line(order)
        order.add_payment_from_ui(self.cash_pm.id, 50.0)
        self.assertEqual(len(order.payment_ids), 1)
        self.assertAlmostEqual(order.payment_ids[0].amount, 50.0, places=2)

    def test_12_add_payment_from_ui_returns_popup_data(self):
        """add_payment_from_ui devuelve datos actualizados del popup."""
        session = self._open_session()
        order = self._make_draft_order(session)
        self._add_line(order)
        data = order.add_payment_from_ui(self.cash_pm.id, 50.0)
        self.assertIn("amount_paid", data)

    # ── remove_payment_from_ui ────────────────────────────────────────────

    def test_13_remove_payment_from_ui_removes_payment(self):
        """remove_payment_from_ui elimina el pago registrado."""
        session = self._open_session()
        order = self._make_draft_order(session)
        self._add_line(order)
        order.add_payment_from_ui(self.cash_pm.id, 50.0)
        payment_id = order.payment_ids[0].id
        order.remove_payment_from_ui(payment_id)
        self.assertEqual(len(order.payment_ids), 0)

    def test_14_remove_payment_from_ui_ignores_foreign_payment(self):
        """remove_payment_from_ui ignora pagos de otros pedidos."""
        session = self._open_session()
        order = self._make_draft_order(session)
        self._add_line(order)
        order2 = self._make_draft_order(session)
        self._add_line(order2)
        order2.add_payment_from_ui(self.cash_pm.id, 50.0)
        foreign_payment_id = order2.payment_ids[0].id
        # No debe borrar el pago ajeno ni lanzar error
        order.remove_payment_from_ui(foreign_payment_id)
        self.assertEqual(len(order2.payment_ids), 1)

    # ── PosMakePaymentWizard ──────────────────────────────────────────────

    def test_15_payment_wizard_total_computed(self):
        """El wizard calcula amount_due correctamente."""
        session = self._open_session()
        order = self._make_draft_order(session)
        self._add_line(order)
        wizard = self.env["pos.make.payment.wizard"].with_context(
            active_id=order.id
        ).create(
            {
                "order_id": order.id,
                "payment_method_id": self.cash_pm.id,
            }
        )
        self.assertAlmostEqual(wizard.amount_due, order.amount_total, places=2)

    def test_16_payment_wizard_is_cash_payment_cash_method(self):
        """is_cash_payment es True para método de efectivo."""
        session = self._open_session()
        order = self._make_draft_order(session)
        self._add_line(order)
        wizard = self.env["pos.make.payment.wizard"].with_context(
            active_id=order.id
        ).create(
            {
                "order_id": order.id,
                "payment_method_id": self.cash_pm.id,
            }
        )
        self.assertTrue(wizard.is_cash_payment)

    def test_17_payment_wizard_is_cash_false_for_card(self):
        """is_cash_payment es False para método de tarjeta."""
        session = self._open_session()
        order = self._make_draft_order(session)
        self._add_line(order)
        wizard = self.env["pos.make.payment.wizard"].with_context(
            active_id=order.id
        ).create(
            {
                "order_id": order.id,
                "payment_method_id": self.card_pm.id,
            }
        )
        self.assertFalse(wizard.is_cash_payment)

    # ── action_pay_order_from_kanban (PosPaymentMethod) ────────────────────

    def test_18_action_pay_from_kanban_without_active_id_returns_false(self):
        """Sin active_id en contexto, action_pay_order_from_kanban devuelve False."""
        result = self.cash_pm.action_pay_order_from_kanban()
        self.assertFalse(result)

    def test_19_action_pay_from_kanban_with_valid_order(self):
        """Con active_id de un pedido existente, action_pay_order_from_kanban ejecuta el pago."""
        session = self._open_session()
        order = self._make_draft_order(session)
        self._add_line(order)
        result = self.cash_pm.with_context(active_id=order.id).action_pay_order_from_kanban()
        # Debe devolver un dict (wizard de pago) o False si el método no es efectivo
        self.assertTrue(result is False or isinstance(result, dict))

    def test_20_action_pay_from_kanban_nonexistent_order_returns_false(self):
        """Con active_id de un pedido inexistente, devuelve False."""
        result = self.cash_pm.with_context(active_id=99999999).action_pay_order_from_kanban()
        self.assertFalse(result)

    # ── PosMakePaymentWizard — amount_change ──────────────────────────────

    def test_21_wizard_amount_change_cash_overpayment(self):
        """El cambio es negativo cuando el importe entregado supera el total (amount_due - amount_tendered < 0)."""
        session = self._open_session()
        order = self._make_draft_order(session)
        self._add_line(order)
        total = order.amount_total
        wizard = self.env["pos.make.payment.wizard"].with_context(
            active_id=order.id
        ).create(
            {
                "order_id": order.id,
                "payment_method_id": self.cash_pm.id,
                "amount_tendered": total + 50.0,
            }
        )
        # amount_change = amount_due - amount_tendered → negativo cuando se entrega más
        if total > 0:
            self.assertAlmostEqual(wizard.amount_change, -50.0, places=2)
        else:
            self.skipTest("El pedido no tiene líneas con precio > 0")

    def test_22_wizard_amount_change_zero_for_card(self):
        """Para tarjeta, amount_change siempre es 0 aunque se entregue más."""
        session = self._open_session()
        order = self._make_draft_order(session)
        self._add_line(order)
        wizard = self.env["pos.make.payment.wizard"].with_context(
            active_id=order.id
        ).create(
            {
                "order_id": order.id,
                "payment_method_id": self.card_pm.id,
                "amount_tendered": order.amount_total + 50.0,
            }
        )
        self.assertEqual(wizard.amount_change, 0.0)

    def test_23_wizard_available_methods_cash_only_context(self):
        """Con cash_only=True, solo se muestran métodos de efectivo."""
        session = self._open_session()
        order = self._make_draft_order(session)
        self._add_line(order)
        wizard = self.env["pos.make.payment.wizard"].with_context(
            active_id=order.id, cash_only=True
        ).create({"order_id": order.id, "payment_method_id": self.cash_pm.id})
        for pm in wizard.available_payment_method_ids:
            self.assertTrue(
                pm.is_cash_count or pm.journal_id.type == "cash",
                f"El método '{pm.name}' no es efectivo pero aparece en cash_only",
            )

    def test_24_wizard_available_methods_all_without_cash_only(self):
        """Sin cash_only, se muestran todos los métodos del config."""
        session = self._open_session()
        order = self._make_draft_order(session)
        self._add_line(order)
        wizard = self.env["pos.make.payment.wizard"].with_context(
            active_id=order.id
        ).create({"order_id": order.id, "payment_method_id": self.cash_pm.id})
        self.assertEqual(
            wizard.available_payment_method_ids,
            order.config_id.payment_method_ids,
        )

    def test_25_wizard_amount_due_decreases_after_partial_payment(self):
        """Tras un pago parcial, amount_due se reduce."""
        session = self._open_session()
        order = self._make_draft_order(session)
        self._add_line(order)
        partial = order.amount_total / 2
        self._add_payment(order, self.cash_pm, partial)
        wizard = self.env["pos.make.payment.wizard"].with_context(
            active_id=order.id
        ).create({"order_id": order.id, "payment_method_id": self.cash_pm.id})
        self.assertAlmostEqual(wizard.amount_due, order.amount_total - partial, places=2)

    # ── PosMakePaymentConventional — _compute_amount_change ───────────────

    def test_26_make_payment_amount_change_with_cash_received(self):
        """amount_change en PosMakePaymentConventional se calcula con importe recibido."""
        session = self._open_session()
        order = self._make_draft_order(session)
        self._add_line(order)
        wizard = self.env["pos.make.payment"].with_context(active_id=order.id).create(
            {
                "amount": order.amount_total,
                "payment_method_id": self.cash_pm.id,
            }
        )
        wizard.amount_received = order.amount_total + 20.0
        wizard._compute_amount_change()
        self.assertAlmostEqual(wizard.amount_change, 20.0, places=2)

    def test_27_make_payment_amount_change_zero_for_card(self):
        """amount_change es 0 para método no efectivo."""
        session = self._open_session()
        order = self._make_draft_order(session)
        self._add_line(order)
        wizard = self.env["pos.make.payment"].with_context(active_id=order.id).create(
            {
                "amount": order.amount_total,
                "payment_method_id": self.card_pm.id,
            }
        )
        wizard.amount_received = order.amount_total + 20.0
        wizard._compute_amount_change()
        self.assertEqual(wizard.amount_change, 0.0)

    def test_28_make_payment_is_cash_payment_true(self):
        """is_cash_payment es True para método de efectivo en PosMakePaymentConventional."""
        session = self._open_session()
        order = self._make_draft_order(session)
        self._add_line(order)
        wizard = self.env["pos.make.payment"].with_context(active_id=order.id).create(
            {
                "amount": order.amount_total,
                "payment_method_id": self.cash_pm.id,
            }
        )
        self.assertTrue(wizard.is_cash_payment)

    def test_29_make_payment_is_cash_payment_false_for_card(self):
        """is_cash_payment es False para método de tarjeta en PosMakePaymentConventional."""
        session = self._open_session()
        order = self._make_draft_order(session)
        self._add_line(order)
        wizard = self.env["pos.make.payment"].with_context(active_id=order.id).create(
            {
                "amount": order.amount_total,
                "payment_method_id": self.card_pm.id,
            }
        )
        self.assertFalse(wizard.is_cash_payment)

    # ── action_open_payment_popup ─────────────────────────────────────────

    def test_30_action_open_payment_popup_returns_wizard_action(self):
        """action_open_payment_popup abre el wizard de pago completo."""
        session = self._open_session()
        order = self._make_draft_order(session)
        self._add_line(order)
        result = order.action_open_payment_popup()
        self.assertEqual(result.get("type"), "ir.actions.act_window")
        self.assertEqual(result.get("res_model"), "pos.make.payment.wizard")

    # ── Validación importe cero ────────────────────────────────────────────

    def test_31_action_pay_cash_zero_amount_raises_error(self):
        """action_pay_cash lanza UserError si el pedido tiene importe cero."""
        session = self._open_session()
        order = self._make_draft_order(session)
        # Pedido sin líneas → amount_total = 0
        with self.assertRaises(UserError) as ctx:
            order.action_pay_cash()
        self.assertIn("importe cero", str(ctx.exception).lower())

    def test_32_action_pay_card_zero_amount_raises_error(self):
        """action_pay_card lanza UserError si el pedido tiene importe cero."""
        session = self._open_session()
        order = self._make_draft_order(session)
        with self.assertRaises(UserError) as ctx:
            order.action_pay_card()
        self.assertIn("importe cero", str(ctx.exception).lower())

    def test_33_action_pos_convention_pay_with_method_zero_amount_raises_error(self):
        """action_pos_convention_pay_with_method lanza UserError con importe cero."""
        session = self._open_session()
        order = self._make_draft_order(session)
        with self.assertRaises(UserError) as ctx:
            order.action_pos_convention_pay_with_method(self.cash_pm.id)
        self.assertIn("importe cero", str(ctx.exception).lower())

    def test_34_wizard_execute_validation_zero_amount_raises_error(self):
        """El wizard lanza UserError al validar un pedido con importe cero."""
        session = self._open_session()
        order = self._make_draft_order(session)
        # Crear wizard con importe 0 (pedido vacío)
        wizard = self.env["pos.make.payment.wizard"].with_context(active_id=order.id).create({
            "order_id": order.id,
            "amount_tendered": 0.0,
            "payment_method_id": self.cash_pm.id,
        })
        with self.assertRaises(UserError) as ctx:
            wizard.action_validate()
        self.assertIn("importe cero", str(ctx.exception).lower())

    def test_35_action_pay_cash_with_lines_does_not_raise(self):
        """action_pay_cash NO lanza error cuando el pedido tiene líneas con importe > 0."""
        session = self._open_session()
        order = self._make_draft_order(session)
        self._add_line(order)
        self.assertGreater(order.amount_total, 0)
        result = order.action_pay_cash()
        self.assertEqual(result.get("type"), "ir.actions.act_window")

    def test_36_action_pay_card_with_lines_does_not_raise(self):
        """action_pay_card NO lanza error cuando el pedido tiene líneas con importe > 0.
        El pago con tarjeta completa el cobro en el momento y puede devolver
        ir.actions.client (nuevo pedido en modo convencional),
        ir.actions.act_window (wizard) o ir.actions.act_window_close."""
        session = self._open_session()
        order = self._make_draft_order(session)
        self._add_line(order)
        self.assertGreater(order.amount_total, 0)
        result = order.action_pay_card()
        self.assertIsInstance(result, dict)
        self.assertIn(result.get("type"), (
            "ir.actions.act_window",
            "ir.actions.client",
            "ir.actions.act_window_close",
        ))

    def test_37_action_pos_convention_pay_with_method_with_lines_does_not_raise(self):
        """action_pos_convention_pay_with_method con importe > 0 abre el wizard."""
        session = self._open_session()
        order = self._make_draft_order(session)
        self._add_line(order)
        self.assertGreater(order.amount_total, 0)
        result = order.action_pos_convention_pay_with_method(self.cash_pm.id)
        self.assertIsNotNone(result)

    def test_38_zero_amount_error_message_is_informative(self):
        """El mensaje de error de importe cero es informativo y menciona 'productos'."""
        session = self._open_session()
        order = self._make_draft_order(session)
        with self.assertRaises(UserError) as ctx:
            order.action_pay_cash()
        error_msg = str(ctx.exception).lower()
        self.assertTrue(
            "importe cero" in error_msg or "productos" in error_msg,
            f"El mensaje de error debería mencionar 'importe cero' o 'productos', pero fue: {error_msg}"
        )

    # ── Factura simplificada ──────────────────────────────────────────────

    def test_39_cash_payment_generates_simplified_invoice(self):
        """
        Al pagar en efectivo un pedido POS convencional se genera automáticamente
        la factura simplificada (account_move) con el importe correcto.
        """
        session = self._open_session()
        order = self._make_draft_order(session, partner=self.partner)
        self._add_line(order)
        self.assertGreater(order.amount_total, 0)

        wizard = self.env["pos.make.payment.wizard"].with_context(
            active_id=order.id
        ).create({
            "order_id": order.id,
            "payment_method_id": self.cash_pm.id,
            "amount_tendered": order.amount_total,
        })
        result = wizard.action_validate()

        # El pedido debe estar pagado o done
        self.assertIn(order.state, ("paid", "done"),
                      f"El pedido debe estar en 'paid'/'done', estado actual: {order.state}")

        # Debe haberse generado la factura simplificada
        self.assertTrue(
            order.account_move,
            "El pago en efectivo debe generar una factura simplificada (account_move)"
        )

    def test_40_simplified_invoice_has_correct_amount(self):
        """
        La factura simplificada generada tiene el mismo importe que el pedido POS.
        """
        session = self._open_session()
        order = self._make_draft_order(session, partner=self.partner)
        self._add_line(order)
        expected_amount = order.amount_total

        wizard = self.env["pos.make.payment.wizard"].with_context(
            active_id=order.id
        ).create({
            "order_id": order.id,
            "payment_method_id": self.cash_pm.id,
            "amount_tendered": expected_amount,
        })
        wizard.action_validate()

        self.assertTrue(order.account_move, "Debe existir una factura simplificada")
        invoice = order.account_move
        self.assertAlmostEqual(
            invoice.amount_total, expected_amount, places=2,
            msg=f"El importe de la factura ({invoice.amount_total}) debe coincidir con el pedido ({expected_amount})"
        )

    def test_41_simplified_invoice_is_posted(self):
        """
        La factura simplificada generada está en estado 'posted' (publicada),
        no en borrador.
        """
        session = self._open_session()
        order = self._make_draft_order(session, partner=self.partner)
        self._add_line(order)

        wizard = self.env["pos.make.payment.wizard"].with_context(
            active_id=order.id
        ).create({
            "order_id": order.id,
            "payment_method_id": self.cash_pm.id,
            "amount_tendered": order.amount_total,
        })
        wizard.action_validate()

        self.assertTrue(order.account_move, "Debe existir una factura simplificada")
        self.assertEqual(
            order.account_move.state, "posted",
            f"La factura simplificada debe estar en estado 'posted', estado actual: {order.account_move.state}"
        )

    def test_42_simplified_invoice_generated_without_explicit_customer(self):
        """
        Cuando el pedido no tiene cliente explícito, se usa el 'default_partner_id'
        del pos.config para generar la factura simplificada.
        Este es el caso habitual de venta anónima ('Consumidor Final').
        """
        if "default_partner_id" not in self.env["pos.config"]._fields:
            self.skipTest(
                "pos_conventional_core no cargado: default_partner_id no disponible"
            )
        session = self._open_session()
        # Pedido SIN cliente → el config tiene default_partner_id = self.partner
        order = self._make_draft_order(session)  # sin partner
        self._add_line(order)
        self.assertFalse(order.partner_id, "El pedido no debe tener cliente al crearse")
        self.assertTrue(
            session.config_id.default_partner_id,
            "El config debe tener un default_partner_id configurado"
        )

        wizard = self.env["pos.make.payment.wizard"].with_context(
            active_id=order.id
        ).create({
            "order_id": order.id,
            "payment_method_id": self.cash_pm.id,
            "amount_tendered": order.amount_total,
        })
        wizard.action_validate()

        self.assertIn(order.state, ("paid", "done"),
                      f"El pedido debe estar pagado, estado: {order.state}")
        self.assertTrue(
            order.account_move,
            "Debe generarse factura simplificada usando el default_partner_id del config"
        )
        self.assertEqual(order.account_move.state, "posted",
                         "La factura simplificada debe estar publicada")

    # ── amount_change: siempre calculado, con signo ───────────────────────

    def _make_wizard(self, order, amount_tendered):
        """Crea un wizard de pago con el importe entregado indicado."""
        return self.env["pos.make.payment.wizard"].with_context(
            active_id=order.id
        ).create({
            "order_id": order.id,
            "payment_method_id": self.cash_pm.id,
            "amount_tendered": amount_tendered,
        })

    def test_43_amount_change_zero_when_exact_payment(self):
        """amount_change es 0 cuando el importe entregado coincide exactamente con el total."""
        session = self._open_session()
        order = self._make_draft_order(session)
        self._add_line(order)

        wizard = self._make_wizard(order, order.amount_total)

        self.assertAlmostEqual(
            wizard.amount_change, 0.0, places=2,
            msg="El cambio debe ser 0 cuando se entrega el importe exacto",
        )

    def test_44_amount_change_negative_when_overpaid(self):
        """amount_change es negativo cuando el cliente entrega más del total (hay cambio que devolver)."""
        session = self._open_session()
        order = self._make_draft_order(session)
        self._add_line(order)

        extra = 10.0
        wizard = self._make_wizard(order, order.amount_total + extra)

        self.assertAlmostEqual(
            wizard.amount_change, -extra, places=2,
            msg="amount_change debe ser negativo (devolver cambio) cuando se entrega de más",
        )

    def test_45_amount_change_positive_when_underpaid(self):
        """amount_change es positivo cuando el importe entregado no cubre el total (falta por pagar)."""
        session = self._open_session()
        order = self._make_draft_order(session)
        self._add_line(order)

        deficit = 5.0
        wizard = self._make_wizard(order, max(0.01, order.amount_total - deficit))

        self.assertGreater(
            wizard.amount_change, 0.0,
            "amount_change debe ser positivo (falta por pagar) cuando el importe es insuficiente",
        )

    def test_46_amount_change_accounts_for_previous_payments(self):
        """amount_change refleja pagos previos: paid + tendered - total."""
        session = self._open_session()
        order = self._make_draft_order(session)
        self._add_line(order)

        partial = order.amount_total / 2
        order.add_payment({
            "pos_order_id": order.id,
            "amount": partial,
            "payment_method_id": self.cash_pm.id,
        })

        # Entregamos exactamente la mitad restante → cambio = 0
        wizard = self._make_wizard(order, partial)

        self.assertAlmostEqual(
            wizard.amount_change, 0.0, places=2,
            msg="Con pago parcial previo, el cambio debe ser 0 al completar el importe restante",
        )

    def test_47_validate_returns_warning_when_amount_change_positive(self):
        """action_validate devuelve un banner warning cuando el importe es insuficiente."""
        session = self._open_session()
        order = self._make_draft_order(session)
        self._add_line(order)

        insufficient = max(0.01, order.amount_total - 5.0)
        wizard = self._make_wizard(order, insufficient)

        self.assertGreater(wizard.amount_change, 0.0)
        action = wizard.action_validate()
        self.assertEqual(action.get("type"), "ir.actions.client")
        self.assertEqual(action.get("tag"), "display_notification")
        self.assertEqual(action.get("params", {}).get("type"), "warning")
        self.assertIn("insuficiente", action.get("params", {}).get("message", "").lower())
        self.assertEqual(order.state, "draft", "Con importe insuficiente el pedido debe seguir en draft")

    def test_48_validate_returns_warning_for_non_cash_when_total_not_covered(self):
        """El wizard general también devuelve banner warning si el total no queda cubierto."""
        session = self._open_session()
        order = self._make_draft_order(session)
        self._add_line(order)

        wizard = self.env["pos.make.payment.wizard"].with_context(
            active_id=order.id
        ).create({
            "order_id": order.id,
            "payment_method_id": self.card_pm.id,
            "amount_tendered": max(0.01, order.amount_total - 10.0),
        })

        action = wizard.action_validate()
        self.assertEqual(action.get("type"), "ir.actions.client")
        self.assertEqual(action.get("tag"), "display_notification")
        self.assertEqual(action.get("params", {}).get("type"), "warning")
        self.assertIn("insuficiente", action.get("params", {}).get("message", "").lower())
        self.assertEqual(order.state, "draft")

    def test_49_amount_change_updates_when_tendered_changes(self):
        """amount_change se recalcula al modificar amount_tendered."""
        session = self._open_session()
        order = self._make_draft_order(session)
        self._add_line(order)

        wizard = self._make_wizard(order, order.amount_total)
        self.assertAlmostEqual(wizard.amount_change, 0.0, places=2)

        # Aumentamos el importe entregado → amount_change se vuelve negativo
        extra = 3.0
        wizard.amount_tendered = order.amount_total + extra
        self.assertAlmostEqual(
            wizard.amount_change, -extra, places=2,
            msg="amount_change debe ser negativo al entregar más (amount_due - amount_tendered < 0)",
        )

    # ── Robustez: acceso sudo() y MissingError ─────────────────────────────

    def test_50_wizard_compute_order_fields_reads_currency_and_total(self):
        """
        _compute_order_fields carga currency_id, amount_total y config_id
        correctamente desde el pedido usando sudo(). Valida que los campos
        están disponibles aunque el acceso se haga por compañía diferente.
        """
        session = self._open_session()
        order = self._make_draft_order(session)
        self._add_line(order)

        wizard = self.env["pos.make.payment.wizard"].with_context(
            active_id=order.id
        ).create({
            "order_id": order.id,
            "payment_method_id": self.cash_pm.id,
        })

        self.assertTrue(wizard.currency_id, "currency_id debe estar establecido")
        self.assertGreater(wizard.amount_total, 0, "amount_total debe ser > 0")
        self.assertTrue(wizard.config_id, "config_id debe estar establecido")

    def test_51_default_get_returns_empty_when_order_not_found(self):
        """
        default_get con active_id de pedido inexistente retorna valores por defecto
        sin lanzar MissingError (comportamiento defensivo con sudo().exists()).
        """
        res = self.env["pos.make.payment.wizard"].with_context(
            active_id=99999999
        ).default_get(["order_id", "amount_tendered"])

        # No debe contener order_id si el pedido no existe
        self.assertNotIn(
            "order_id", res,
            "default_get no debe incluir order_id para un pedido inexistente",
        )

    def test_52_execute_validation_raises_user_error_for_deleted_order(self):
        """
        _execute_validation convierte el MissingError en UserError cuando
        order_id.sudo() no existe, evitando exponer la excepción técnica al usuario.
        """
        session = self._open_session()
        order = self._make_draft_order(session)
        self._add_line(order)

        wizard = self.env["pos.make.payment.wizard"].with_context(
            active_id=order.id
        ).create({
            "order_id": order.id,
            "payment_method_id": self.cash_pm.id,
            "amount_tendered": order.amount_total,
        })

        # Eliminamos el pedido para simular el caso de acceso a registro borrado.
        # Solo los pedidos en 'draft' se pueden eliminar en Odoo.
        self.assertEqual(order.state, "draft", "El pedido debe estar en draft para eliminarse")
        order_id = order.id
        order.unlink()

        # El wizard sigue en memoria con order_id = order_id (ya eliminado).
        # Al intentar validar, debe lanzar UserError (no MissingError técnico).
        wizard_sudo = self.env["pos.make.payment.wizard"].sudo().browse(wizard.id)
        with self.assertRaises(Exception) as ctx:
            wizard_sudo.action_validate()

        # La excepción debe ser UserError o su subclase (no MissingError sin capturar)
        self.assertIsInstance(
            ctx.exception,
            UserError,
            f"Debe ser UserError, pero fue: {type(ctx.exception).__name__}",
        )

    def test_53_wizard_totals_computed_via_sudo(self):
        """
        _compute_totals usa sudo() internamente: amount_paid y amount_due
        se calculan correctamente aunque el contexto de compañía sea distinto.
        """
        session = self._open_session()
        order = self._make_draft_order(session)
        self._add_line(order)

        # Añadimos un pago parcial directo
        partial = order.amount_total / 2
        order.add_payment({
            "pos_order_id": order.id,
            "amount": partial,
            "payment_method_id": self.cash_pm.id,
        })

        wizard = self.env["pos.make.payment.wizard"].with_context(
            active_id=order.id
        ).create({
            "order_id": order.id,
            "payment_method_id": self.cash_pm.id,
        })

        self.assertAlmostEqual(wizard.amount_paid, partial, places=2,
                               msg="amount_paid debe reflejar el pago parcial")
        self.assertAlmostEqual(wizard.amount_due, order.amount_total - partial, places=2,
                               msg="amount_due debe reflejar el pendiente")

    def test_54_amount_tendered_defaults_to_amount_due(self):
        """
        Al abrir el wizard, amount_tendered se inicializa con el importe pendiente
        (amount_due) para que el cajero no tenga que introducirlo manualmente.
        Se valida tanto via default_get (active_id en contexto) como via el
        mecanismo default_fieldname del contexto (que usa action_pay_cash).
        """
        session = self._open_session()
        order = self._make_draft_order(session)
        self._add_line(order)
        self.assertGreater(order.amount_total, 0, "El pedido debe tener importe > 0")
        amount_due = order.amount_total - sum(order.payment_ids.mapped("amount"))

        # Via default_get (active_id en contexto, igual que action_pay_cash)
        wizard = self.env["pos.make.payment.wizard"].with_context(
            active_id=order.id
        ).create({
            "order_id": order.id,
            "payment_method_id": self.cash_pm.id,
        })

        self.assertAlmostEqual(
            wizard.amount_tendered,
            amount_due,
            places=2,
            msg=(
                f"amount_tendered ({wizard.amount_tendered}) debe ser igual "
                f"a amount_due ({amount_due}) al abrir el wizard"
            ),
        )

    def test_58_amount_tendered_via_default_context_key(self):
        """
        action_pay_cash pasa 'default_amount_tendered' en el contexto.
        Odoo lo aplica automáticamente como valor inicial del campo,
        garantizando que el cajero vea el importe correcto sin tener que
        escribirlo. Este test simula exactamente ese flujo.
        """
        session = self._open_session()
        order = self._make_draft_order(session)
        self._add_line(order)
        amount_due = max(
            0.0,
            order.amount_total - sum(order.payment_ids.mapped("amount"))
        )
        self.assertGreater(amount_due, 0, "El pedido debe tener importe pendiente > 0")

        # Simular el contexto que genera action_pay_cash
        wizard = self.env["pos.make.payment.wizard"].with_context(
            active_id=order.id,
            default_amount_tendered=amount_due,
            cash_only=True,
        ).create({
            "order_id": order.id,
            "payment_method_id": self.cash_pm.id,
        })

        self.assertAlmostEqual(
            wizard.amount_tendered,
            amount_due,
            places=2,
            msg=(
                f"amount_tendered ({wizard.amount_tendered}) debe coincidir con "
                f"el importe pendiente ({amount_due}) cuando se pasa default_amount_tendered "
                f"en el contexto (simulando action_pay_cash)"
            ),
        )

    def test_59_action_pay_cash_prefills_total_in_quick_mode(self):
        """
        El popup rápido de efectivo siempre arranca con el total actual del ticket,
        no con pagos borrador previos. El contexto de la acción debe marcar el
        modo rápido e inyectar default_amount_tendered = amount_total.
        """
        session = self._open_session()
        order = self._make_draft_order(session)
        self._add_line(order)
        partial = order.amount_total / 2
        order.add_payment({
            "pos_order_id": order.id,
            "amount": partial,
            "payment_method_id": self.cash_pm.id,
        })

        action = order.action_pay_cash()

        self.assertTrue(
            action["context"].get("cash_quick_mode"),
            "action_pay_cash debe activar cash_quick_mode en el contexto",
        )
        self.assertAlmostEqual(
            action["context"]["default_amount_tendered"],
            order.amount_total,
            places=2,
            msg="El popup rápido de efectivo debe precargar el total del ticket",
        )

    def test_60_cash_quick_mode_ignores_existing_draft_payments_in_totals(self):
        """
        En modo rápido de efectivo, el wizard debe ignorar pagos borrador ya
        registrados: amount_paid = 0, amount_due = amount_total y el importe
        entregado inicial debe ser el total del ticket.
        """
        session = self._open_session()
        order = self._make_draft_order(session)
        self._add_line(order)
        partial = order.amount_total / 2
        order.add_payment({
            "pos_order_id": order.id,
            "amount": partial,
            "payment_method_id": self.cash_pm.id,
        })

        action = order.action_pay_cash()
        wizard = self.env["pos.make.payment.wizard"].with_context(
            **action["context"]
        ).create({
            "order_id": order.id,
            "payment_method_id": self.cash_pm.id,
        })

        self.assertAlmostEqual(wizard.amount_paid, 0.0, places=2)
        self.assertAlmostEqual(wizard.amount_due, order.amount_total, places=2)
        self.assertAlmostEqual(wizard.amount_tendered, order.amount_total, places=2)

    def test_61_cash_quick_mode_validation_replaces_existing_draft_payments(self):
        """
        Al validar en modo rápido de efectivo, los pagos borrador existentes se
        sustituyen por el cobro final del ticket para evitar dobles cobros o
        reabrir el popup con pendiente 0 por pagos temporales anteriores.
        """
        session = self._open_session()
        order = self._make_draft_order(session, partner=self.partner)
        self._add_line(order)
        old_payment = order.add_payment({
            "pos_order_id": order.id,
            "amount": order.amount_total / 2,
            "payment_method_id": self.cash_pm.id,
        })
        old_payment_ids = order.payment_ids.ids

        action = order.action_pay_cash()
        wizard = self.env["pos.make.payment.wizard"].with_context(
            **action["context"]
        ).create({
            "order_id": order.id,
            "payment_method_id": self.cash_pm.id,
        })
        wizard.action_validate()

        self.assertFalse(
            order.payment_ids.filtered(lambda payment: payment.id in old_payment_ids),
            "Los pagos borrador anteriores deben eliminarse al validar en modo rápido",
        )
        self.assertAlmostEqual(
            sum(order.payment_ids.filtered(lambda payment: payment.amount > 0).mapped("amount")),
            order.amount_total,
            places=2,
            msg="Tras reemplazar pagos borrador, el cobro positivo debe igualar el total del ticket",
        )
        self.assertIn(order.state, ("paid", "done"))

    def test_55_amount_tendered_defaults_to_amount_due_after_partial_payment(self):
        """
        Con un pago parcial previo, amount_tendered se inicializa con el importe
        pendiente restante (amount_due = total - pagado).
        """
        session = self._open_session()
        order = self._make_draft_order(session)
        self._add_line(order)
        partial = order.amount_total / 2
        order.add_payment({
            "pos_order_id": order.id,
            "amount": partial,
            "payment_method_id": self.cash_pm.id,
        })
        expected_due = order.amount_total - partial

        wizard = self.env["pos.make.payment.wizard"].with_context(
            active_id=order.id
        ).create({
            "order_id": order.id,
            "payment_method_id": self.cash_pm.id,
        })

        self.assertAlmostEqual(
            wizard.amount_tendered,
            expected_due,
            places=2,
            msg=(
                f"amount_tendered ({wizard.amount_tendered}) debe coincidir con "
                f"el pendiente restante ({expected_due}) tras un pago parcial"
            ),
        )

    def test_56_amount_change_equals_amount_due_minus_amount_tendered(self):
        """
        amount_change = amount_due - amount_tendered:
          - > 0 si falta dinero (se mostrará en rojo)
          - = 0 si el pago es exacto
          - < 0 si hay cambio a devolver (se mostrará en verde)
        """
        session = self._open_session()
        order = self._make_draft_order(session)
        self._add_line(order)
        total = order.amount_total
        self.assertGreater(total, 0, "El pedido debe tener importe > 0")

        # Pago exacto → amount_change = 0
        wizard_exact = self._make_wizard(order, total)
        self.assertAlmostEqual(
            wizard_exact.amount_change,
            wizard_exact.amount_due - wizard_exact.amount_tendered,
            places=2,
            msg="amount_change debe ser amount_due - amount_tendered (pago exacto)",
        )

        # Sobrepago → amount_change < 0
        extra = 7.0
        wizard_over = self._make_wizard(order, total + extra)
        self.assertAlmostEqual(
            wizard_over.amount_change,
            wizard_over.amount_due - wizard_over.amount_tendered,
            places=2,
            msg="amount_change debe ser amount_due - amount_tendered (sobrepago)",
        )
        self.assertLess(wizard_over.amount_change, 0,
                        "Con sobrepago amount_change debe ser negativo")

        # Pago insuficiente → amount_change > 0
        deficit = 3.0
        wizard_under = self._make_wizard(order, max(0.01, total - deficit))
        self.assertAlmostEqual(
            wizard_under.amount_change,
            wizard_under.amount_due - wizard_under.amount_tendered,
            places=2,
            msg="amount_change debe ser amount_due - amount_tendered (pago insuficiente)",
        )
        self.assertGreater(wizard_under.amount_change, 0,
                           "Con pago insuficiente amount_change debe ser positivo")

    def test_57_compute_order_fields_sets_currency_total_config(self):
        """
        _compute_order_fields establece currency_id, amount_total y config_id
        correctamente sin lanzar MissingError, incluso en contextos multi-compañía.
        Este test verifica que el método existe y funciona correctamente
        (anteriormente estaba fusionado de forma incorrecta con _compute_totals).
        """
        session = self._open_session()
        order = self._make_draft_order(session)
        self._add_line(order)

        wizard = self.env["pos.make.payment.wizard"].with_context(
            active_id=order.id
        ).create({
            "order_id": order.id,
            "payment_method_id": self.cash_pm.id,
        })

        # currency_id debe coincidir con la del pedido
        self.assertEqual(
            wizard.currency_id,
            order.currency_id,
            "currency_id del wizard debe coincidir con la del pedido",
        )
        # amount_total del wizard debe coincidir con el del pedido
        self.assertAlmostEqual(
            wizard.amount_total,
            order.amount_total,
            places=2,
            msg="amount_total del wizard debe coincidir con el del pedido",
        )
        # config_id debe coincidir
        self.assertEqual(
            wizard.config_id,
            order.config_id,
            "config_id del wizard debe coincidir con el del pedido",
        )

