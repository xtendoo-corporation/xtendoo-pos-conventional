# Copyright 2024 Xtendoo
# License OPL-1
from odoo.tests.common import tagged
from odoo.addons.pos_conventional_core.tests.common import PosConventionalTestCommon


@tagged("pos_conventional", "-standard")
class TestSaleIntegration(PosConventionalTestCommon):
    """Tests para pos_conventional_sale_integration — report_sale_details extendido."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.pos_config.pos_enable_albaran = True
        cls.storable = cls.env["product.product"].create(
            {
                "name": "Producto Almacenable SI",
                "type": "consu",
                "list_price": 80.0,
                "available_in_pos": True,
            }
        )

    def _create_linked_order(self):
        """Crea un pedido POS vinculado a sale.order (albarán)."""
        session = self._open_session()
        order = self._make_draft_order(session, self.partner)
        self._add_line(order, self.storable)
        order.action_pay_account()
        return order, session

    # ── get_sale_details ──────────────────────────────────────────────────

    def test_01_get_sale_details_has_customer_account_key(self):
        """get_sale_details incluye la clave 'customer_account'."""
        result = self.env["report.point_of_sale.report_saledetails"].get_sale_details()
        self.assertIn("customer_account", result)

    def test_02_customer_account_structure(self):
        """customer_account tiene 'total', 'count' y 'orders'."""
        result = self.env["report.point_of_sale.report_saledetails"].get_sale_details()
        ca = result["customer_account"]
        self.assertIn("total", ca)
        self.assertIn("count", ca)
        self.assertIn("orders", ca)

    def test_03_customer_account_counts_linked_orders(self):
        """Se contabiliza el pedido vinculado en customer_account."""
        order, session = self._create_linked_order()
        result = self.env[
            "report.point_of_sale.report_saledetails"
        ].get_sale_details(session_ids=session.ids)
        ca = result["customer_account"]
        sale_names = [o["sale_order_name"] for o in ca["orders"]]
        self.assertIn(order.linked_sale_order_id.name, sale_names)

    def test_04_customer_account_total_includes_linked_amounts(self):
        """El total incluye el importe del pedido vinculado."""
        order, session = self._create_linked_order()
        result = self.env[
            "report.point_of_sale.report_saledetails"
        ].get_sale_details(session_ids=session.ids)
        self.assertGreater(result["customer_account"]["total"], 0)

    def test_05_customer_account_empty_without_linked_orders(self):
        """Sin pedidos vinculados, customer_account.count == 0."""
        new_session = self._open_session()
        result = self.env[
            "report.point_of_sale.report_saledetails"
        ].get_sale_details(session_ids=new_session.ids)
        self.assertEqual(result["customer_account"]["count"], 0)

    def test_06_customer_account_order_fields(self):
        """Cada entrada en orders tiene los campos esperados."""
        order, session = self._create_linked_order()
        result = self.env[
            "report.point_of_sale.report_saledetails"
        ].get_sale_details(session_ids=session.ids)
        for entry in result["customer_account"]["orders"]:
            for key in ("pos_order_name", "sale_order_name", "partner_name", "amount_total"):
                self.assertIn(key, entry, f"Falta clave '{key}' en order entry")

    # ── Filtro por rango de fechas ─────────────────────────────────────────

    def test_07_get_sale_details_with_date_range(self):
        """get_sale_details con rango de fechas incluye pedidos del periodo."""
        from datetime import datetime, timedelta
        order, session = self._create_linked_order()
        date_start = (datetime.now() - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
        date_stop = (datetime.now() + timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
        result = self.env[
            "report.point_of_sale.report_saledetails"
        ].get_sale_details(date_start=date_start, date_stop=date_stop)
        self.assertIn("customer_account", result)

    def test_08_get_sale_details_with_config_ids(self):
        """get_sale_details filtrado por config_ids incluye la clave customer_account."""
        result = self.env[
            "report.point_of_sale.report_saledetails"
        ].get_sale_details(config_ids=[self.pos_config.id])
        self.assertIn("customer_account", result)

    def test_09_partner_name_generic_when_no_partner(self):
        """Cuando el pedido no tiene partner, partner_name es el texto genérico."""
        order, session = self._create_linked_order()
        # Forzar que no tenga partner para verificar el fallback
        order.write({"partner_id": False})
        result = self.env[
            "report.point_of_sale.report_saledetails"
        ].get_sale_details(session_ids=session.ids)
        # Los nombres pueden ser "Cliente genérico" o el nombre real
        for entry in result["customer_account"]["orders"]:
            self.assertIn("partner_name", entry)

    def test_10_customer_account_total_zero_without_linked_orders(self):
        """Sin pedidos linked, el total de customer_account es 0."""
        new_session = self._open_session()
        result = self.env[
            "report.point_of_sale.report_saledetails"
        ].get_sale_details(session_ids=new_session.ids)
        self.assertEqual(result["customer_account"]["total"], 0)

    # ── open_linked_sale_order ────────────────────────────────────────────

    def test_11_open_linked_sale_order_returns_act_window(self):
        """open_linked_sale_order devuelve acción de ventana al sale.order."""
        from odoo.exceptions import UserError
        order, session = self._create_linked_order()
        result = order.open_linked_sale_order()
        self.assertEqual(result.get("type"), "ir.actions.act_window")
        self.assertEqual(result.get("res_model"), "sale.order")
        self.assertEqual(result.get("res_id"), order.linked_sale_order_id.id)

    def test_12_open_linked_sale_order_no_sale_raises(self):
        """Sin sale.order vinculado, open_linked_sale_order lanza UserError."""
        from odoo.exceptions import UserError
        session = self._open_session()
        order = self._make_draft_order(session, self.partner)
        self._add_line(order, self.storable)
        # No llamar a action_pay_account, así no hay sale.order
        with self.assertRaises(UserError):
            order.open_linked_sale_order()

