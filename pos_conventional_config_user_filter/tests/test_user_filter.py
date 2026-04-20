# Copyright 2024 Xtendoo
# License OPL-1
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
                "groups_id": [(6, 0, group_ids)],
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

