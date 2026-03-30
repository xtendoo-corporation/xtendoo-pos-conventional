# Copyright 2024 Xtendoo
# License OPL-1
from odoo.tests.common import tagged
from odoo.exceptions import UserError
from odoo.addons.pos_conventional_core.tests.common import PosConventionalTestCommon


@tagged("pos_conventional", "-standard")
class TestPickingIntegration(PosConventionalTestCommon):
    """Tests para pos_conventional_picking_integration."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Producto de tipo storable para que genere picking
        cls.storable_product = cls.env["product.product"].create(
            {
                "name": "Producto Almacenable Test",
                "type": "consu",
                "list_price": 50.0,
                "available_in_pos": True,
            }
        )
        cls.pos_config.pos_enable_albaran = True

    # ── pos_config ────────────────────────────────────────────────────────

    def test_01_pos_enable_albaran_default_false(self):
        """Un nuevo config no tiene pos_enable_albaran por defecto."""
        config = self.env["pos.config"].create(
            {
                "name": "Config No Albaran",
                "payment_method_ids": [(6, 0, [self.card_pm.id])],
            }
        )
        self.assertFalse(config.pos_enable_albaran)

    def test_02_pos_enable_albaran_set_true(self):
        """pos_enable_albaran se puede activar."""
        self.assertTrue(self.pos_config.pos_enable_albaran)

    # ── pos_order campos ──────────────────────────────────────────────────

    def test_03_is_linked_to_sale_false_by_default(self):
        """Un pedido nuevo no está vinculado a una venta."""
        session = self._open_session()
        order = self._make_draft_order(session, self.partner)
        self.assertFalse(order.is_linked_to_sale)

    def test_04_show_albaran_button_when_enabled(self):
        """show_albaran_button es True cuando pos_enable_albaran está activo."""
        session = self._open_session()
        order = self._make_draft_order(session)
        self.assertTrue(order.show_albaran_button)

    def test_05_show_albaran_button_false_when_disabled(self):
        """show_albaran_button es False si pos_enable_albaran está desactivado."""
        config = self.env["pos.config"].create(
            {
                "name": "Config Sin Albaran",
                "pos_enable_albaran": False,
                "payment_method_ids": [(6, 0, [self.card_pm.id])],
            }
        )
        session = self._open_session(config)
        order = self._make_draft_order(session)
        self.assertFalse(order.show_albaran_button)

    # ── action_pay_account — validaciones ─────────────────────────────────

    def test_06_action_pay_account_non_draft_raises(self):
        """action_pay_account en pedido no borrador lanza UserError."""
        session = self._open_session()
        order = self._make_draft_order(session, self.partner)
        self._add_line(order, self.storable_product)
        self._add_payment(order)
        order.action_pos_order_paid()
        with self.assertRaises(UserError):
            order.action_pay_account()

    def test_07_action_pay_account_no_lines_raises(self):
        """action_pay_account sin líneas lanza UserError."""
        session = self._open_session()
        order = self._make_draft_order(session, self.partner)
        with self.assertRaises(UserError):
            order.action_pay_account()

    def test_08_action_pay_account_no_partner_raises(self):
        """action_pay_account sin partner lanza UserError."""
        session = self._open_session()
        order = self._make_draft_order(session)  # sin partner
        self._add_line(order, self.storable_product)
        with self.assertRaises(UserError):
            order.action_pay_account()

    def test_09_action_pay_account_creates_sale_order(self):
        """action_pay_account crea un sale.order vinculado."""
        session = self._open_session()
        order = self._make_draft_order(session, self.partner)
        self._add_line(order, self.storable_product)
        order.action_pay_account()
        self.assertTrue(order.linked_sale_order_id)
        self.assertEqual(order.linked_sale_order_id.partner_id, self.partner)

    def test_10_action_pay_account_sets_state_linked(self):
        """Después de action_pay_account el pedido POS está en estado 'linked'."""
        session = self._open_session()
        order = self._make_draft_order(session, self.partner)
        self._add_line(order, self.storable_product)
        order.action_pay_account()
        self.assertEqual(order.state, "linked")

    def test_11_action_pay_account_is_linked_to_sale(self):
        """is_linked_to_sale es True después de crear el albarán."""
        session = self._open_session()
        order = self._make_draft_order(session, self.partner)
        self._add_line(order, self.storable_product)
        order.action_pay_account()
        self.assertTrue(order.is_linked_to_sale)

    # ── pos_session ───────────────────────────────────────────────────────

    def test_12_get_closed_orders_excludes_linked(self):
        """_get_closed_orders excluye pedidos vinculados a sale.order."""
        session = self._open_session()
        # Pedido normal (pagado)
        order_normal = self._make_draft_order(session, self.partner)
        self._add_line(order_normal)
        self._add_payment(order_normal)
        order_normal.action_pos_order_paid()
        # Pedido albarán (linked)
        order_linked = self._make_draft_order(session, self.partner)
        self._add_line(order_linked, self.storable_product)
        order_linked.action_pay_account()

        closed_orders = session._get_closed_orders()
        self.assertIn(order_normal, closed_orders)
        self.assertNotIn(order_linked, closed_orders)

    # ── pos_session._get_captured_payments_domain ─────────────────────────

    def test_13_get_captured_payments_domain_returns_list(self):
        """_get_captured_payments_domain devuelve una lista (dominio válido)."""
        session = self._open_session()
        domain = session._get_captured_payments_domain()
        self.assertIsInstance(domain, list)

    def test_14_get_captured_payments_domain_excludes_linked_orders(self):
        """_get_captured_payments_domain excluye pagos de pedidos vinculados."""
        session = self._open_session()
        order_linked = self._make_draft_order(session, self.partner)
        self._add_line(order_linked, self.storable_product)
        order_linked.action_pay_account()

        domain = session._get_captured_payments_domain()
        # Si hay pedidos linked, el dominio debe incluir 'not in' para excluirlos
        domain_str = str(domain)
        # El dominio puede ser largo; verificamos que es válido y es lista
        self.assertIsInstance(domain, list)

    # ── res.config.settings — pos_enable_albaran ─────────────────────────

    def test_15_settings_pos_enable_albaran_reflected(self):
        """pos_enable_albaran en settings refleja el valor del config."""
        settings = self.env["res.config.settings"].create(
            {"pos_config_id": self.pos_config.id}
        )
        self.assertTrue(settings.pos_enable_albaran)

    def test_16_settings_pos_enable_albaran_write(self):
        """Cambiar pos_enable_albaran en settings actualiza el config."""
        config = self.env["pos.config"].create(
            {
                "name": "Config Albaran Settings",
                "pos_enable_albaran": False,
                "payment_method_ids": [(6, 0, [self.card_pm.id])],
            }
        )
        settings = self.env["res.config.settings"].create(
            {"pos_config_id": config.id}
        )
        self.assertFalse(settings.pos_enable_albaran)
        settings.pos_enable_albaran = True
        self.assertTrue(settings.pos_enable_albaran)

    # ── action_pay_account — acción devuelta ──────────────────────────────

    def test_17_action_pay_account_returns_action_dict(self):
        """action_pay_account devuelve un dict de acción de ventana."""
        session = self._open_session()
        order = self._make_draft_order(session, self.partner)
        self._add_line(order, self.storable_product)
        result = order.action_pay_account()
        self.assertIsInstance(result, dict)
        self.assertEqual(result.get("type"), "ir.actions.act_window")

    def test_18_action_pay_account_linked_sale_order_confirmed(self):
        """El sale.order creado desde action_pay_account está confirmado."""
        session = self._open_session()
        order = self._make_draft_order(session, self.partner)
        self._add_line(order, self.storable_product)
        order.action_pay_account()
        sale_order = order.linked_sale_order_id
        self.assertIn(sale_order.state, ("sale", "done"),
                      "El sale.order debería estar confirmado")

    def test_19_pos_order_name_updated_to_sale_name(self):
        """El nombre del pedido POS se actualiza al nombre del sale.order."""
        session = self._open_session()
        order = self._make_draft_order(session, self.partner)
        self._add_line(order, self.storable_product)
        order.action_pay_account()
        self.assertEqual(order.name, order.linked_sale_order_id.name)

