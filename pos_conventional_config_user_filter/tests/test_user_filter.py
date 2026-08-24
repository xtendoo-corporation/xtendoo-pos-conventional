# Copyright 2024 Xtendoo
# License OPL-1
from odoo import fields
from odoo.tests.common import tagged
from odoo.addons.pos_conventional_core.tests.common import PosConventionalTestCommon


@tagged("pos_conventional_core", "-standard", "post_install", "-at_install")
class TestResUsersFilter(PosConventionalTestCommon):
    """Tests para res.users — campo allowed_pos_config_ids (pos_conventional_config_user_filter)."""

    def _create_pos_user(self, name, login, extra_group_xmlids=None):
        group_ids = [
            self.env.ref("base.group_user").id,
            self.env.ref("point_of_sale.group_pos_user").id,
        ]
        for xmlid in extra_group_xmlids or []:
            group_ids.append(self.env.ref(xmlid).id)
        return self.env["res.users"].create(
            {
                "name": name,
                "login": login,
                "company_id": self.env.company.id,
                "company_ids": [(6, 0, self.env.company.ids)],
                "group_ids": [(6, 0, group_ids)],
            }
        )

    def test_01_allowed_pos_config_ids_empty_by_default(self):
        """Un nuevo usuario no tiene cajas POS permitidas por defecto."""
        user = self.env["res.users"].create(
            {
                "name": "Test Filter User",
                "login": "test_filter_user@example.com",
                "group_ids": [(4, self.env.ref("point_of_sale.group_pos_user").id)],
            }
        )
        self.assertFalse(user.allowed_pos_config_ids)

    def test_02_assign_pos_config_to_user(self):
        """Se puede asignar una caja POS a un usuario."""
        user = self.env["res.users"].create(
            {
                "name": "Test Filter User 2",
                "login": "test_filter_user2@example.com",
            }
        )
        user.allowed_pos_config_ids = [(4, self.pos_config.id)]
        self.assertIn(self.pos_config, user.allowed_pos_config_ids)

    def test_03_assign_multiple_pos_configs_to_user(self):
        """Se pueden asignar múltiples cajas POS a un usuario."""
        config2 = self.env["pos.config"].create(
            {
                "name": "Config Secundaria",
                "payment_method_ids": [(6, 0, [self.card_pm.id])],
            }
        )
        user = self.env["res.users"].create(
            {
                "name": "Test Filter User 3",
                "login": "test_filter_user3@example.com",
            }
        )
        user.allowed_pos_config_ids = [(6, 0, [self.pos_config.id, config2.id])]
        self.assertEqual(len(user.allowed_pos_config_ids), 2)

    def test_04_remove_config_from_user(self):
        """Se puede quitar una caja POS asignada a un usuario."""
        user = self.env["res.users"].create(
            {
                "name": "Test Filter User 4",
                "login": "test_filter_user4@example.com",
            }
        )
        user.allowed_pos_config_ids = [(4, self.pos_config.id)]
        user.allowed_pos_config_ids = [(3, self.pos_config.id)]
        self.assertNotIn(self.pos_config, user.allowed_pos_config_ids)

    def test_05_config_linked_to_multiple_users(self):
        """Una misma caja POS puede asignarse a múltiples usuarios."""
        u1 = self.env["res.users"].create(
            {"name": "Filter U1", "login": "filter_u1@example.com"}
        )
        u2 = self.env["res.users"].create(
            {"name": "Filter U2", "login": "filter_u2@example.com"}
        )
        u1.allowed_pos_config_ids = [(4, self.pos_config.id)]
        u2.allowed_pos_config_ids = [(4, self.pos_config.id)]
        self.assertIn(self.pos_config, u1.allowed_pos_config_ids)
        self.assertIn(self.pos_config, u2.allowed_pos_config_ids)

    # ── Relación inversa: configuraciones del usuario ─────────────────────

    def test_06_user_sees_allowed_config_in_m2m(self):
        """allowed_pos_config_ids contiene exactamente los configs asignados."""
        config2 = self.env["pos.config"].create(
            {
                "name": "Config Filter Extra",
                "payment_method_ids": [(6, 0, [self.card_pm.id])],
            }
        )
        user = self.env["res.users"].create(
            {"name": "Filter U Extra", "login": "filter_u_extra@example.com"}
        )
        user.allowed_pos_config_ids = [(6, 0, [self.pos_config.id, config2.id])]
        self.assertIn(self.pos_config, user.allowed_pos_config_ids)
        self.assertIn(config2, user.allowed_pos_config_ids)
        self.assertEqual(len(user.allowed_pos_config_ids), 2)

    def test_07_allowed_pos_config_ids_field_is_m2m(self):
        """allowed_pos_config_ids es un campo Many2many (varios configs posibles)."""
        user = self.env["res.users"].create(
            {"name": "Filter M2M Check", "login": "filter_m2m@example.com"}
        )
        config2 = self.env["pos.config"].create(
            {
                "name": "Config Filter M2M",
                "payment_method_ids": [(6, 0, [self.card_pm.id])],
            }
        )
        user.allowed_pos_config_ids = [(4, self.pos_config.id), (4, config2.id)]
        self.assertGreaterEqual(len(user.allowed_pos_config_ids), 2)

    def test_08_clear_all_allowed_configs(self):
        """Se pueden quitar todos los configs asignados a un usuario."""
        user = self.env["res.users"].create(
            {"name": "Filter Clear All", "login": "filter_clear@example.com"}
        )
        user.allowed_pos_config_ids = [(4, self.pos_config.id)]
        user.allowed_pos_config_ids = [(5, 0, 0)]  # Eliminar todos
        self.assertFalse(user.allowed_pos_config_ids)

    def test_09_pos_user_only_sees_assigned_configs(self):
        """Un usuario POS normal solo ve las cajas explícitamente permitidas."""
        config2 = self.env["pos.config"].create(
            {
                "name": "Config No Permitida",
                "payment_method_ids": [(6, 0, [self.card_pm.id])],
            }
        )
        user = self._create_pos_user(
            "POS Limited User",
            "pos_limited_user@example.com",
        )
        user.allowed_pos_config_ids = [(6, 0, [self.pos_config.id])]

        visible_configs = self.env["pos.config"].with_user(user).search(
            [("id", "in", [self.pos_config.id, config2.id])]
        )

        self.assertEqual(visible_configs.ids, self.pos_config.ids)

    def test_10_pos_user_with_no_allowed_configs_sees_none(self):
        """Si no tiene cajas permitidas, un usuario POS normal no ve ninguna."""
        user = self._create_pos_user(
            "POS Without Configs",
            "pos_without_configs@example.com",
        )

        visible_configs = self.env["pos.config"].with_user(user).search(
            [("id", "=", self.pos_config.id)]
        )

        self.assertFalse(visible_configs)

    def test_11_pos_manager_sees_all_configs(self):
        """Un administrador POS mantiene acceso a todas las cajas de su compañía."""
        config2 = self.env["pos.config"].create(
            {
                "name": "Config Manager Visible",
                "payment_method_ids": [(6, 0, [self.card_pm.id])],
            }
        )
        manager = self._create_pos_user(
            "POS Manager User",
            "pos_manager_user@example.com",
            extra_group_xmlids=["point_of_sale.group_pos_manager"],
        )

        visible_configs = self.env["pos.config"].with_user(manager).search(
            [("id", "in", [self.pos_config.id, config2.id])]
        )

        self.assertEqual(set(visible_configs.ids), {self.pos_config.id, config2.id})

    def test_12_can_access_pos_config_helper_matches_security_rules(self):
        """El helper de acceso replica la restricción aplicada a usuarios POS normales."""
        config2 = self.env["pos.config"].create(
            {
                "name": "Config Helper Denied",
                "payment_method_ids": [(6, 0, [self.card_pm.id])],
            }
        )
        user = self._create_pos_user(
            "POS Helper User",
            "pos_helper_user@example.com",
        )
        user.allowed_pos_config_ids = [(6, 0, [self.pos_config.id])]

        self.assertTrue(user._can_access_pos_config(self.pos_config))
        self.assertFalse(user._can_access_pos_config(config2))

    # ── pos.session / pos.order: aislamiento entre cajas ───────────────────

    def _create_second_config(self, name="Config Secundaria Sesion"):
        pm = self._make_fresh_cash_pm(name=f"Efectivo {name}")
        return self.env["pos.config"].create(
            {
                "name": name,
                "payment_method_ids": [(6, 0, [pm.id])],
            }
        )

    def test_13_pos_user_only_sees_sessions_of_allowed_configs(self):
        """Un usuario POS limitado no ve sesiones de cajas no permitidas."""
        config2 = self._create_second_config("Config Sesion No Permitida")
        session1 = self._open_session(self.pos_config)
        session2 = self._open_session(config2)

        user = self._create_pos_user(
            "POS Session Limited User",
            "pos_session_limited_user@example.com",
        )
        user.allowed_pos_config_ids = [(6, 0, [self.pos_config.id])]

        visible_sessions = self.env["pos.session"].with_user(user).search(
            [("id", "in", [session1.id, session2.id])]
        )

        self.assertEqual(visible_sessions.ids, session1.ids)

    def test_14_pos_user_with_no_allowed_configs_sees_no_sessions(self):
        """Sin cajas permitidas, un usuario POS normal no ve ninguna sesión."""
        session1 = self._open_session(self.pos_config)

        user = self._create_pos_user(
            "POS Session Without Configs",
            "pos_session_without_configs@example.com",
        )

        visible_sessions = self.env["pos.session"].with_user(user).search(
            [("id", "=", session1.id)]
        )

        self.assertFalse(visible_sessions)

    def test_15_pos_manager_sees_all_sessions(self):
        """Un manager sin restricción explícita ve las sesiones de todas las cajas."""
        config2 = self._create_second_config("Config Sesion Manager Visible")
        session1 = self._open_session(self.pos_config)
        session2 = self._open_session(config2)

        manager = self._create_pos_user(
            "POS Session Manager User",
            "pos_session_manager_user@example.com",
            extra_group_xmlids=["point_of_sale.group_pos_manager"],
        )

        visible_sessions = self.env["pos.session"].with_user(manager).search(
            [("id", "in", [session1.id, session2.id])]
        )

        self.assertEqual(
            set(visible_sessions.ids), {session1.id, session2.id}
        )

    def test_16_pos_manager_restricted_only_sees_allowed_sessions(self):
        """Un manager con cajas asignadas queda restringido a esas sesiones."""
        config2 = self._create_second_config("Config Sesion Manager Restringido")
        session1 = self._open_session(self.pos_config)
        session2 = self._open_session(config2)

        manager = self._create_pos_user(
            "POS Session Manager Restricted",
            "pos_session_manager_restricted@example.com",
            extra_group_xmlids=["point_of_sale.group_pos_manager"],
        )
        manager.allowed_pos_config_ids = [(6, 0, [self.pos_config.id])]

        visible_sessions = self.env["pos.session"].with_user(manager).search(
            [("id", "in", [session1.id, session2.id])]
        )

        self.assertEqual(visible_sessions.ids, session1.ids)

    def test_17_pos_user_only_sees_orders_of_allowed_configs(self):
        """Un usuario POS limitado no ve pedidos de cajas no permitidas."""
        config2 = self._create_second_config("Config Pedido No Permitida")
        session1 = self._open_session(self.pos_config)
        session2 = self._open_session(config2)
        order1 = self._make_draft_order(session1)
        order2 = self._make_draft_order(session2)

        user = self._create_pos_user(
            "POS Order Limited User",
            "pos_order_limited_user@example.com",
        )
        user.allowed_pos_config_ids = [(6, 0, [self.pos_config.id])]

        visible_orders = self.env["pos.order"].with_user(user).search(
            [("id", "in", [order1.id, order2.id])]
        )

        self.assertEqual(visible_orders.ids, order1.ids)

    def test_18_pos_user_with_no_allowed_configs_sees_no_orders(self):
        """Sin cajas permitidas, un usuario POS normal no ve ningún pedido."""
        session1 = self._open_session(self.pos_config)
        order1 = self._make_draft_order(session1)

        user = self._create_pos_user(
            "POS Order Without Configs",
            "pos_order_without_configs@example.com",
        )

        visible_orders = self.env["pos.order"].with_user(user).search(
            [("id", "=", order1.id)]
        )

        self.assertFalse(visible_orders)

    def test_19_pos_manager_sees_all_orders(self):
        """Un manager sin restricción explícita ve los pedidos de todas las cajas."""
        config2 = self._create_second_config("Config Pedido Manager Visible")
        session1 = self._open_session(self.pos_config)
        session2 = self._open_session(config2)
        order1 = self._make_draft_order(session1)
        order2 = self._make_draft_order(session2)

        manager = self._create_pos_user(
            "POS Order Manager User",
            "pos_order_manager_user@example.com",
            extra_group_xmlids=["point_of_sale.group_pos_manager"],
        )

        visible_orders = self.env["pos.order"].with_user(manager).search(
            [("id", "in", [order1.id, order2.id])]
        )

        self.assertEqual(set(visible_orders.ids), {order1.id, order2.id})

    # ── account.move: facturas (incluidas simplificadas) generadas por POS ──

    def _make_pos_invoice(self, order):
        """Crea una factura mínima y la vincula al pedido POS como su account_move."""
        move = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "journal_id": self.invoice_journal.id,
                "partner_id": self.partner.id,
            }
        )
        order.account_move = move.id
        return move

    def test_20_pos_user_only_sees_invoices_of_allowed_configs(self):
        """Un usuario POS limitado no ve facturas generadas desde cajas no permitidas."""
        config2 = self._create_second_config("Config Factura No Permitida")
        session1 = self._open_session(self.pos_config)
        session2 = self._open_session(config2)
        order1 = self._make_draft_order(session1)
        order2 = self._make_draft_order(session2)
        move1 = self._make_pos_invoice(order1)
        move2 = self._make_pos_invoice(order2)

        user = self._create_pos_user(
            "POS Invoice Limited User",
            "pos_invoice_limited_user@example.com",
        )
        user.allowed_pos_config_ids = [(6, 0, [self.pos_config.id])]

        visible_moves = self.env["account.move"].with_user(user).search(
            [("id", "in", [move1.id, move2.id])]
        )

        self.assertEqual(visible_moves.ids, move1.ids)

    def test_21_pos_user_with_no_allowed_configs_sees_no_pos_invoices(self):
        """Sin cajas permitidas, un usuario POS normal no ve facturas de POS."""
        session1 = self._open_session(self.pos_config)
        order1 = self._make_draft_order(session1)
        move1 = self._make_pos_invoice(order1)

        user = self._create_pos_user(
            "POS Invoice Without Configs",
            "pos_invoice_without_configs@example.com",
        )

        visible_moves = self.env["account.move"].with_user(user).search(
            [("id", "=", move1.id)]
        )

        self.assertFalse(visible_moves)

    def test_22_pos_user_does_not_see_non_pos_invoices(self):
        """Una factura sin origen POS sigue sin ser visible para un cajero.

        La regla del core point_of_sale.rule_invoice_pos_user ya restringía
        a los usuarios POS a solo ver facturas generadas por un pedido POS
        (nunca facturas contables ajenas al POS). Nuestro hook solo añade la
        condición de caja permitida a esa misma restricción; este test
        confirma que ese comportamiento previo no cambia.
        """
        non_pos_move = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "journal_id": self.invoice_journal.id,
                "partner_id": self.partner.id,
            }
        )

        user = self._create_pos_user(
            "POS Invoice Non POS Visible",
            "pos_invoice_non_pos_visible@example.com",
        )

        visible_moves = self.env["account.move"].with_user(user).search(
            [("id", "=", non_pos_move.id)]
        )

        self.assertFalse(visible_moves)

    def test_23_pos_manager_sees_all_pos_invoices(self):
        """Un manager sin restricción explícita ve las facturas de todas las cajas."""
        config2 = self._create_second_config("Config Factura Manager Visible")
        session1 = self._open_session(self.pos_config)
        session2 = self._open_session(config2)
        order1 = self._make_draft_order(session1)
        order2 = self._make_draft_order(session2)
        move1 = self._make_pos_invoice(order1)
        move2 = self._make_pos_invoice(order2)

        manager = self._create_pos_user(
            "POS Invoice Manager User",
            "pos_invoice_manager_user@example.com",
            extra_group_xmlids=["point_of_sale.group_pos_manager"],
        )

        visible_moves = self.env["account.move"].with_user(manager).search(
            [("id", "in", [move1.id, move2.id])]
        )

        self.assertEqual(set(visible_moves.ids), {move1.id, move2.id})

    # ── pos.payment: aislamiento entre cajas ────────────────────────────────

    def test_24_pos_user_only_sees_payments_of_allowed_configs(self):
        """Un usuario POS limitado no ve pagos de pedidos de cajas no permitidas."""
        config2 = self._create_second_config("Config Pago No Permitida")
        session1 = self._open_session(self.pos_config)
        session2 = self._open_session(config2)
        order1 = self._make_draft_order(session1)
        order2 = self._make_draft_order(session2)
        self._add_payment(order1, amount=1.0)
        self._add_payment(
            order2, payment_method=config2.payment_method_ids[:1], amount=1.0
        )
        payment1 = order1.payment_ids
        payment2 = order2.payment_ids

        user = self._create_pos_user(
            "POS Payment Limited User",
            "pos_payment_limited_user@example.com",
        )
        user.allowed_pos_config_ids = [(6, 0, [self.pos_config.id])]

        visible_payments = self.env["pos.payment"].with_user(user).search(
            [("id", "in", [payment1.id, payment2.id])]
        )

        self.assertEqual(visible_payments.ids, payment1.ids)

    def test_25_pos_user_with_no_allowed_configs_sees_no_payments(self):
        """Sin cajas permitidas, un usuario POS normal no ve ningún pago."""
        session1 = self._open_session(self.pos_config)
        order1 = self._make_draft_order(session1)
        self._add_payment(order1, amount=1.0)
        payment1 = order1.payment_ids

        user = self._create_pos_user(
            "POS Payment Without Configs",
            "pos_payment_without_configs@example.com",
        )

        visible_payments = self.env["pos.payment"].with_user(user).search(
            [("id", "=", payment1.id)]
        )

        self.assertFalse(visible_payments)

    def test_26_pos_manager_sees_all_payments(self):
        """Un manager sin restricción explícita ve los pagos de todas las cajas."""
        config2 = self._create_second_config("Config Pago Manager Visible")
        session1 = self._open_session(self.pos_config)
        session2 = self._open_session(config2)
        order1 = self._make_draft_order(session1)
        order2 = self._make_draft_order(session2)
        self._add_payment(order1, amount=1.0)
        self._add_payment(
            order2, payment_method=config2.payment_method_ids[:1], amount=1.0
        )
        payment1 = order1.payment_ids
        payment2 = order2.payment_ids

        manager = self._create_pos_user(
            "POS Payment Manager User",
            "pos_payment_manager_user@example.com",
            extra_group_xmlids=["point_of_sale.group_pos_manager"],
        )

        visible_payments = self.env["pos.payment"].with_user(manager).search(
            [("id", "in", [payment1.id, payment2.id])]
        )

        self.assertEqual(set(visible_payments.ids), {payment1.id, payment2.id})

    # ── account.move.line: aislamiento entre cajas (facturas POS) ──────────

    def _make_pos_invoice_line(self, move):
        return self.env["account.move.line"].create(
            {
                "move_id": move.id,
                "account_id": self.income_account.id,
                "name": "Línea factura POS test",
                "quantity": 1,
                "price_unit": 10.0,
            }
        )

    def test_27_pos_user_only_sees_invoice_lines_of_allowed_configs(self):
        """Un usuario POS limitado no ve líneas de factura de cajas no permitidas."""
        config2 = self._create_second_config("Config Línea Factura No Permitida")
        session1 = self._open_session(self.pos_config)
        session2 = self._open_session(config2)
        order1 = self._make_draft_order(session1)
        order2 = self._make_draft_order(session2)
        move1 = self._make_pos_invoice(order1)
        move2 = self._make_pos_invoice(order2)
        line1 = self._make_pos_invoice_line(move1)
        line2 = self._make_pos_invoice_line(move2)

        user = self._create_pos_user(
            "POS Invoice Line Limited User",
            "pos_invoice_line_limited_user@example.com",
        )
        user.allowed_pos_config_ids = [(6, 0, [self.pos_config.id])]

        visible_lines = self.env["account.move.line"].with_user(user).search(
            [("id", "in", [line1.id, line2.id])]
        )

        self.assertEqual(visible_lines.ids, line1.ids)

    def test_28_pos_manager_sees_all_invoice_lines(self):
        """Un manager sin restricción explícita ve las líneas de factura de todas las cajas."""
        config2 = self._create_second_config("Config Línea Factura Manager Visible")
        session1 = self._open_session(self.pos_config)
        session2 = self._open_session(config2)
        order1 = self._make_draft_order(session1)
        order2 = self._make_draft_order(session2)
        move1 = self._make_pos_invoice(order1)
        move2 = self._make_pos_invoice(order2)
        line1 = self._make_pos_invoice_line(move1)
        line2 = self._make_pos_invoice_line(move2)

        manager = self._create_pos_user(
            "POS Invoice Line Manager User",
            "pos_invoice_line_manager_user@example.com",
            extra_group_xmlids=["point_of_sale.group_pos_manager"],
        )

        visible_lines = self.env["account.move.line"].with_user(manager).search(
            [("id", "in", [line1.id, line2.id])]
        )

        self.assertEqual(set(visible_lines.ids), {line1.id, line2.id})

    # ── account.bank.statement.line: aislamiento entre cajas ───────────────

    def _make_pos_statement_line(self, session, amount=5.0):
        return self.env["account.bank.statement.line"].create(
            {
                "journal_id": self.cash_journal_test.id,
                "amount": amount,
                "date": fields.Date.context_today(self.env.user),
                "pos_session_id": session.id,
            }
        )

    def test_29_pos_user_never_sees_statement_lines_even_of_allowed_config(self):
        """Un cajero raso no ve NINGÚN apunte bancario, ni siquiera de su caja.

        account.bank.statement.line delega en account.move (_inherits), así
        que además de la regla propia del modelo, Odoo aplica también las
        reglas de account.move sobre su move_id delegado. La regla del core
        para group_pos_user en account.move (rule_invoice_pos_user, acotada
        por caja en el hook) exige pos_order_ids != False — condición que un
        apunte bancario nunca cumple, al no ser una factura. El resultado
        (ya en el Odoo estándar, sin este módulo) es que un cajero raso
        jamás ve apuntes bancarios por esta vía; el manager sí, porque su
        propia regla de account.move añade el escape "ve todo si no está
        restringido" que neutraliza esa exigencia (ver test_30).
        """
        config2 = self._create_second_config("Config Apunte No Permitida")
        session1 = self._open_session(self.pos_config)
        session2 = self._open_session(config2)
        line1 = self._make_pos_statement_line(session1)
        line2 = self._make_pos_statement_line(session2)

        user = self._create_pos_user(
            "POS Statement Line Limited User",
            "pos_statement_line_limited_user@example.com",
        )
        user.allowed_pos_config_ids = [(6, 0, [self.pos_config.id])]

        visible_lines = self.env["account.bank.statement.line"].with_user(user).search(
            [("id", "in", [line1.id, line2.id])]
        )

        self.assertFalse(visible_lines)

    def test_30_pos_manager_sees_all_statement_lines(self):
        """Un manager sin restricción explícita ve los apuntes bancarios de todas las cajas."""
        config2 = self._create_second_config("Config Apunte Manager Visible")
        session1 = self._open_session(self.pos_config)
        session2 = self._open_session(config2)
        line1 = self._make_pos_statement_line(session1)
        line2 = self._make_pos_statement_line(session2)

        manager = self._create_pos_user(
            "POS Statement Line Manager User",
            "pos_statement_line_manager_user@example.com",
            extra_group_xmlids=["point_of_sale.group_pos_manager"],
        )

        visible_lines = self.env["account.bank.statement.line"].with_user(manager).search(
            [("id", "in", [line1.id, line2.id])]
        )

        self.assertEqual(set(visible_lines.ids), {line1.id, line2.id})

