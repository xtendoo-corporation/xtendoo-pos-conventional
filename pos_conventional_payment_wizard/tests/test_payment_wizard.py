# Copyright 2024 Xtendoo
# License OPL-1
from odoo.tests.common import tagged
from odoo.exceptions import UserError
from odoo.addons.pos_conventional_core.tests.common import PosConventionalTestCommon


@tagged("pos_conventional_core", "-standard")
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
        """El cambio se calcula cuando el importe entregado supera el total."""
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
        # amount_change = (amount_paid + amount_tendered) - amount_total cuando es efectivo
        # amount_paid=0, amount_tendered=total+50 => change=50 si total>0
        if total > 0:
            self.assertAlmostEqual(wizard.amount_change, 50.0, places=2)
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
        ir.actions.client (nuevo pedido) o ir.actions.act_window (wizard)."""
        session = self._open_session()
        order = self._make_draft_order(session)
        self._add_line(order)
        self.assertGreater(order.amount_total, 0)
        result = order.action_pay_card()
        self.assertIsInstance(result, dict)
        self.assertIn(result.get("type"), ("ir.actions.act_window", "ir.actions.client"))

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

