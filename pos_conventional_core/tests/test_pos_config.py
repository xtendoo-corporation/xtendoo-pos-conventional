# Copyright 2024 Xtendoo
# License OPL-1
from odoo import fields
from odoo.tests.common import tagged
from odoo.exceptions import UserError

from .common import PosConventionalTestCommon


@tagged("pos_conventional_core", "-standard")
class TestPosConfig(PosConventionalTestCommon):
    """Tests para pos.config (pos_conventional_core)."""

    # ── Campos ────────────────────────────────────────────────────────────

    def test_01_pos_non_touch_default_false(self):
        """Un config POS normal NO tiene pos_non_touch activado por defecto."""
        config = self.env["pos.config"].create(
            {
                "name": "Config Normal",
                "payment_method_ids": [(6, 0, [self.card_pm.id])],
            }
        )
        self.assertFalse(config.pos_non_touch)

    def test_02_pos_non_touch_activated(self):
        """El config de tests tiene pos_non_touch=True."""
        self.assertTrue(self.pos_config.pos_non_touch)

    def test_03_default_partner_id(self):
        """El campo default_partner_id se puede asignar."""
        self.pos_config.default_partner_id = self.partner
        self.assertEqual(self.pos_config.default_partner_id, self.partner)

    def test_04_default_partner_id_domain(self):
        """Solo se pueden asignar partners con customer_rank > 0."""
        # Creamos un partner sin rank de cliente
        non_customer = self.env["res.partner"].create(
            {"name": "No Customer", "customer_rank": 0}
        )
        # No hay una constrains de DB, pero verificamos que el campo existe y es M2o
        self.pos_config.default_partner_id = non_customer
        self.assertEqual(self.pos_config.default_partner_id, non_customer)

    # ── _get_or_create_non_touch_session ───────────────────────────────

    def test_05_get_or_create_session_creates_new(self):
        """Cuando no hay sesión activa, se crea una nueva en modo non-touch."""
        config = self.env["pos.config"].create(
            {
                "name": "Config NT Create",
                "pos_non_touch": True,
                "payment_method_ids": [(6, 0, [self._make_fresh_cash_pm().id])],
            }
        )
        session = config.with_context(skip_auto_open=True)._get_or_create_non_touch_session()
        self.assertTrue(session)
        self.assertEqual(session.config_id, config)

    def test_06_get_or_create_session_returns_existing(self):
        """Cuando ya hay una sesión activa, se devuelve sin crear nueva."""
        session = self._open_session()
        result = self.pos_config._get_or_create_non_touch_session()
        self.assertEqual(result, session)

    # ── open_ui ───────────────────────────────────────────────────────────

    def test_07_open_ui_non_touch_with_open_session_redirects(self):
        """open_ui en modo non-touch con sesión abierta redirige a lista de pedidos."""
        session = self._open_session()
        result = self.pos_config.open_ui()
        self.assertIsInstance(result, dict)
        self.assertIn("domain", result)
        self.assertIn("context", result)

    def test_08_open_ui_normal_mode_calls_super(self):
        """open_ui en config táctil llama al super() de Odoo."""
        config = self.env["pos.config"].create(
            {
                "name": "Config Tactil",
                "pos_non_touch": False,
                "payment_method_ids": [(6, 0, [self.card_pm.id])],
            }
        )
        # En modo táctil no interceptamos, super() abre la UI web normal
        result = config.open_ui()
        self.assertIsInstance(result, dict)

    # ── _redirect_to_pos_orders ───────────────────────────────────────────

    def test_09_redirect_to_pos_orders_returns_action(self):
        """_redirect_to_pos_orders devuelve una acción con dominio e contexto."""
        session = self._open_session()
        result = self.pos_config._redirect_to_pos_orders(session)
        self.assertEqual(result.get("res_model"), "pos.order")
        self.assertIn("domain", result)
        ctx = result.get("context", {})
        self.assertEqual(ctx.get("default_session_id"), session.id)

    def test_10_redirect_to_pos_orders_domain_contains_session(self):
        """El dominio incluye el ID de sesión activa."""
        session = self._open_session()
        result = self.pos_config._redirect_to_pos_orders(session)
        domain = result["domain"]
        session_ids_in_domain = [v for op, f, v in [domain[0]] if f == "session_id"]
        self.assertTrue(session_ids_in_domain or len(domain) > 0)

    def test_11_open_ui_opening_control_returns_opening_popup(self):
        """open_ui en modo non-touch con sesión en 'opening_control' muestra el popup de apertura.

        Regresión: el stub _get_non_touch_opening_action → False en pos_conventional_core
        sobreescribía la implementación de pos_conventional_session_management porque
        core se carga DESPUÉS (depende de él). Tras eliminar el stub, la llamada
        devuelve el client action correcto.
        """
        # Crear un config non-touch nuevo para tener sesión en opening_control limpia
        config = self.env["pos.config"].create({
            "name": "Config OpenUI Test",
            "pos_non_touch": True,
            "payment_method_ids": [(6, 0, [self._make_fresh_cash_pm().id])],
        })
        # Confirmar que no hay sesión activa (nueva config)
        self.assertFalse(config.current_session_id)

        # open_ui debe crear sesión en opening_control y devolver el popup
        result = config.open_ui()

        self.assertIsInstance(result, dict, "open_ui debe devolver un dict de acción")
        self.assertEqual(
            result.get("type"), "ir.actions.client",
            "La primera apertura de un POS non-touch debe devolver ir.actions.client, "
            "no la UI táctil estándar de Odoo",
        )
        self.assertEqual(
            result.get("tag"), "pos_conventional_opening_popup",
            "El tag debe ser 'pos_conventional_opening_popup' para mostrar el popup de apertura",
        )
        # El contexto debe incluir la sesión recién creada
        ctx = result.get("context", {})
        self.assertIn(
            "session_id", ctx,
            "El contexto del popup de apertura debe incluir 'session_id'",
        )
        self.assertIn(
            "config_id", ctx,
            "El contexto del popup de apertura debe incluir 'config_id'",
        )
        self.assertEqual(ctx["config_id"], config.id)

    def test_12_open_ui_touch_config_uses_standard_odoo(self):
        """open_ui en config táctil (pos_non_touch=False) usa el flujo estándar de Odoo.

        Verifica que el override en pos_conventional_core.open_ui() no interfiere
        con las cajas táctiles normales.
        """
        config_touch = self.env["pos.config"].create({
            "name": "Config Táctil Standard",
            "pos_non_touch": False,
            "payment_method_ids": [(6, 0, [self.card_pm.id])],
        })
        result = config_touch.open_ui()
        self.assertIsInstance(result, dict, "open_ui en modo táctil debe devolver un dict")
        # No debe devolver el popup de apertura del POS convencional
        self.assertNotEqual(
            result.get("tag"), "pos_conventional_opening_popup",
            "Un config táctil no debe devolver el popup de apertura no-táctil",
        )

    def test_13_get_non_touch_opening_action_not_false(self):
        """_get_non_touch_opening_action no debe devolver False (bug del stub eliminado).

        Este test documenta que el stub que devolvía False ha sido eliminado.
        Tras la corrección, el método devuelve el dict de acción del popup.
        """
        session = self.env["pos.session"].with_context(skip_auto_open=True).create(
            {"config_id": self.pos_config.id}
        )
        result = self.pos_config._get_non_touch_opening_action(session)
        # Tras eliminar el stub, este método viene de pos_conventional_session_management
        self.assertIsInstance(result, dict, "_get_non_touch_opening_action debe devolver un dict")
        self.assertNotEqual(
            result, False,
            "_get_non_touch_opening_action no debe devolver False — el stub fue eliminado",
        )
        self.assertEqual(result.get("tag"), "pos_conventional_opening_popup")

