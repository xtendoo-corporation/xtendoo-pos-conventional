from pathlib import Path

from odoo.addons.pos_conventional_core.tests.common import PosConventionalTestCommon
from odoo.exceptions import UserError
from odoo.tests.common import tagged


@tagged("pos_conventional_core", "xtendoo_cash_drawer", "-standard", "post_install", "-at_install")
class TestPosConventionalCashDrawer(PosConventionalTestCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._module_root = Path(__file__).resolve().parents[1]

    def test_action_open_cash_drawer_from_conventional_returns_client_action(self):
        session = self._open_session()
        order = self._make_draft_order(session)
        config = session.config_id
        config.write({
            "cash_drawer_use_bridge": True,
            "cash_drawer_bridge_url": "http://127.0.0.1:3211",
            "cash_drawer_printer_name": "POS-80C",
            "cash_drawer_api_key": "secret",
        })

        action = order.action_open_cash_drawer_from_conventional()

        self.assertEqual(action["type"], "ir.actions.client")
        self.assertEqual(action["tag"], "xtendoo_cash_drawer_open_test")
        self.assertEqual(action["params"]["bridge_url"], "http://127.0.0.1:3211")
        self.assertEqual(action["params"]["printer_name"], "POS-80C")
        self.assertEqual(action["params"]["api_key"], "secret")

    def test_action_open_cash_drawer_from_conventional_raises_without_bridge_url(self):
        session = self._open_session()
        order = self._make_draft_order(session)
        config = session.config_id
        config.write({
            "cash_drawer_use_bridge": True,
            "cash_drawer_bridge_url": False,
            "cash_drawer_open_url": False,
        })

        with self.assertRaises(UserError):
            order.action_open_cash_drawer_from_conventional()

    def test_assets_and_view_are_registered(self):
        manifest = (self._module_root / "__manifest__.py").read_text(encoding="utf-8")
        template = (self._module_root / "static/src/xml/pos_payment_buttons_cash_drawer.xml").read_text(
            encoding="utf-8"
        )
        view = self.env.ref(
            "pos_conventional_cash_drawer.view_pos_pos_form_payment_wizard_cash_drawer"
        )

        self.assertIn('"xtendoo_cash_drawer"', manifest)
        self.assertIn('"pos_conventional_payment_wizard"', manifest)
        self.assertIn("pos_payment_buttons_cash_drawer", manifest)
        self.assertIn("Abrir cajón", template)
        self.assertIn("pos_payment_buttons_cash_drawer", view.arch_db)

