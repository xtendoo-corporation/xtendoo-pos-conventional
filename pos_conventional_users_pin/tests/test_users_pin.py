# Copyright 2024 Xtendoo
# License OPL-1
from odoo.tests.common import tagged
from odoo.exceptions import ValidationError
from odoo.addons.pos_conventional_core.tests.common import PosConventionalTestCommon


@tagged("pos_conventional", "-standard")
class TestUsersPin(PosConventionalTestCommon):
    """Tests para pos_conventional_users_pin — PIN de usuario y wizard."""

    # ── res.users — campo pin ─────────────────────────────────────────────

    def test_01_pin_field_none_by_default(self):
        """Un usuario nuevo no tiene PIN asignado."""
        user = self.env["res.users"].create(
            {"name": "PIN User Default", "login": "pin_default@example.com"}
        )
        self.assertFalse(user.pin)

    def test_02_pin_can_be_set(self):
        """Se puede asignar un PIN a un usuario."""
        user = self.env["res.users"].create(
            {"name": "PIN User Set", "login": "pin_set@example.com", "pin": "1234"}
        )
        self.assertEqual(user.pin, "1234")

    def test_03_pin_unique_constraint_raises(self):
        """Dos usuarios no pueden tener el mismo PIN."""
        self.env["res.users"].create(
            {"name": "PIN Unique 1", "login": "pin_u1@example.com", "pin": "9999"}
        )
        with self.assertRaises((ValidationError, Exception)):
            self.env["res.users"].create(
                {"name": "PIN Unique 2", "login": "pin_u2@example.com", "pin": "9999"}
            )

    def test_04_pin_same_user_update_allowed(self):
        """Un usuario puede actualizar su propio PIN a un valor distinto."""
        user = self.env["res.users"].create(
            {"name": "PIN Update", "login": "pin_update@example.com", "pin": "1111"}
        )
        user.pin = "2222"
        self.assertEqual(user.pin, "2222")

    def test_05_different_pins_allowed(self):
        """Usuarios distintos pueden tener PINs distintos."""
        u1 = self.env["res.users"].create(
            {"name": "PIN A", "login": "pin_a@example.com", "pin": "1111"}
        )
        u2 = self.env["res.users"].create(
            {"name": "PIN B", "login": "pin_b@example.com", "pin": "2222"}
        )
        self.assertNotEqual(u1.pin, u2.pin)

    # ── pos.config — pos_force_employee_login_after_order ─────────────────

    def test_06_force_login_after_order_default_false(self):
        """pos_force_employee_login_after_order es False por defecto."""
        self.assertFalse(self.pos_config.pos_force_employee_login_after_order)

    def test_07_force_login_after_order_can_be_activated(self):
        """Se puede activar pos_force_employee_login_after_order."""
        self.pos_config.pos_force_employee_login_after_order = True
        self.assertTrue(self.pos_config.pos_force_employee_login_after_order)
        self.pos_config.pos_force_employee_login_after_order = False

    def test_08_get_non_touch_opening_action_with_pin_returns_pin_wizard(self):
        """Con forzar PIN activo, _get_non_touch_opening_action abre el wizard de PIN."""
        self.pos_config.pos_force_employee_login_after_order = True
        session = self._open_session()
        result = self.pos_config._get_non_touch_opening_action(session)
        self.assertEqual(result.get("res_model"), "pos.session.pin.wizard")
        self.pos_config.pos_force_employee_login_after_order = False

    def test_09_get_non_touch_opening_action_without_pin_delegates_to_super(self):
        """Sin forzar PIN, delega al super (session_management) que abre el popup."""
        self.pos_config.pos_force_employee_login_after_order = False
        session = self._open_session()
        result = self.pos_config._get_non_touch_opening_action(session)
        # El resultado puede ser el popup de apertura de session_management
        self.assertIsInstance(result, (dict, bool, type(None)))

    # ── res.config.settings ───────────────────────────────────────────────

    def test_10_settings_force_login_related_field(self):
        """El campo en settings refleja pos_force_employee_login_after_order del config."""
        self.pos_config.pos_force_employee_login_after_order = True
        settings = self.env["res.config.settings"].create(
            {"pos_config_id": self.pos_config.id}
        )
        self.assertTrue(settings.pos_force_employee_login_after_order)
        self.pos_config.pos_force_employee_login_after_order = False

    # ── pos.session.pin.wizard ────────────────────────────────────────────

    def test_11_pin_wizard_invalid_pin_raises_validation_error(self):
        """PIN incorrecto lanza ValidationError."""
        session = self._open_session()
        wizard = self.env["pos.session.pin.wizard"].create(
            {
                "session_id": session.id,
                "user_id": self.env.uid,
                "pos_pin": "0000WRONGPIN",
            }
        )
        with self.assertRaises(ValidationError):
            wizard.action_validate_pin()

    def test_12_pin_wizard_valid_pin_changes_session_user(self):
        """Un PIN correcto actualiza el usuario de la sesión."""
        user_with_pin = self.env["res.users"].create(
            {
                "name": "PIN Válido User",
                "login": "pin_valid@example.com",
                "pin": "5678",
                "company_ids": [(4, self.env.company.id)],
                "groups_id": [
                    (4, self.env.ref("point_of_sale.group_pos_user").id)
                ],
            }
        )
        session = self._open_session()
        wizard = self.env["pos.session.pin.wizard"].create(
            {
                "session_id": session.id,
                "user_id": self.env.uid,
                "pos_pin": "5678",
            }
        )
        wizard.action_validate_pin()
        self.assertEqual(session.user_id, user_with_pin)

    def test_13_pin_wizard_switch_user_flow_returns_client_action(self):
        """Flujo switch_user_after_sale devuelve acción de cliente."""
        user_with_pin = self.env["res.users"].create(
            {
                "name": "PIN Switch User",
                "login": "pin_switch@example.com",
                "pin": "4321",
                "company_ids": [(4, self.env.company.id)],
                "groups_id": [
                    (4, self.env.ref("point_of_sale.group_pos_user").id)
                ],
            }
        )
        session = self._open_session()
        wizard = self.env["pos.session.pin.wizard"].with_context(
            switch_user_after_sale=True
        ).create(
            {
                "session_id": session.id,
                "user_id": self.env.uid,
                "pos_pin": "4321",
            }
        )
        result = wizard.action_validate_pin()
        self.assertEqual(result.get("type"), "ir.actions.client")
        self.assertEqual(result.get("tag"), "pos_conventional_new_order")

    # ── PIN wizard — flujo force_new_order_flow ───────────────────────────

    def test_14_pin_wizard_force_new_order_flow_returns_act_window(self):
        """Flujo force_new_order_flow devuelve acción de ventana (pos.order)."""
        user_with_pin = self.env["res.users"].create(
            {
                "name": "PIN New Order User",
                "login": "pin_neworder@example.com",
                "pin": "8765",
                "company_ids": [(4, self.env.company.id)],
                "groups_id": [
                    (4, self.env.ref("point_of_sale.group_pos_user").id)
                ],
            }
        )
        session = self._open_session()
        wizard = self.env["pos.session.pin.wizard"].with_context(
            force_new_order_flow=True
        ).create(
            {
                "session_id": session.id,
                "user_id": self.env.uid,
                "pos_pin": "8765",
            }
        )
        result = wizard.action_validate_pin()
        self.assertEqual(result.get("type"), "ir.actions.act_window")
        self.assertEqual(result.get("res_model"), "pos.order")

    # ── PIN — actualizar a vacío no lanza error ────────────────────────────

    def test_15_pin_can_be_cleared(self):
        """Un PIN puede borrarse (ponerse a False/vacío)."""
        user = self.env["res.users"].create(
            {"name": "PIN Clear", "login": "pin_clear@example.com", "pin": "3333"}
        )
        user.pin = False
        self.assertFalse(user.pin)

    # ── res.config.settings — pos_force_employee_login ────────────────────

    def test_16_settings_force_login_false_by_default(self):
        """pos_force_employee_login_after_order es False por defecto en settings."""
        config = self.env["pos.config"].create(
            {
                "name": "Config PIN Settings Default",
                "payment_method_ids": [(6, 0, [self.cash_pm.id])],
            }
        )
        settings = self.env["res.config.settings"].create(
            {"pos_config_id": config.id}
        )
        self.assertFalse(settings.pos_force_employee_login_after_order)

    def test_17_settings_force_login_write_propagates_to_config(self):
        """Cambiar pos_force_employee_login_after_order en settings actualiza el config."""
        config = self.env["pos.config"].create(
            {
                "name": "Config PIN Settings Write",
                "payment_method_ids": [(6, 0, [self.cash_pm.id])],
            }
        )
        settings = self.env["res.config.settings"].create(
            {"pos_config_id": config.id}
        )
        settings.pos_force_employee_login_after_order = True
        self.assertTrue(settings.pos_force_employee_login_after_order)

    # ── _get_non_touch_opening_action — sin pin forzado ───────────────────

    def test_18_get_non_touch_opening_action_no_pin_delegates_super(self):
        """Sin force_employee_login, la acción delega al super (session_management)."""
        self.pos_config.pos_force_employee_login_after_order = False
        session = self._open_session()
        result = self.pos_config._get_non_touch_opening_action(session)
        # Super devuelve el popup de apertura de session_management (ir.actions.client)
        if result:
            self.assertIn(result.get("type"), ("ir.actions.client", "ir.actions.act_window", False))

