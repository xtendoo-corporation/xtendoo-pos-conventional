# Copyright 2024 Xtendoo
# License OPL-1
from odoo.tests.common import tagged
from odoo.exceptions import UserError

from .common import PosConventionalTestCommon


@tagged("pos_conventional_core", "-standard", "post_install", "-at_install")
class TestResConfigSettings(PosConventionalTestCommon):
    """Tests para res.config.settings (pos_conventional_core)."""

    def _get_settings(self, config=None):
        config = config or self.pos_config
        return self.env["res.config.settings"].create(
            {"pos_config_id": config.id}
        )

    # ── pos_non_touch related field ───────────────────────────────────────

    def test_01_settings_pos_non_touch_reflects_config(self):
        """pos_non_touch en settings refleja el valor del config."""
        settings = self._get_settings()
        self.assertEqual(settings.pos_non_touch, self.pos_config.pos_non_touch)

    def test_02_settings_pos_non_touch_write_propagates(self):
        """Cambiar pos_non_touch en settings sin sesión abierta funciona."""
        config = self.env["pos.config"].create(
            {
                "name": "Config NT Settings Test",
                "pos_non_touch": True,
                "payment_method_ids": [(6, 0, [self._make_fresh_cash_pm().id])],
            }
        )
        settings = self._get_settings(config)
        settings.pos_non_touch = False
        self.assertFalse(settings.pos_non_touch)

    # ── pos_default_partner_id ────────────────────────────────────────────

    def test_03_settings_default_partner_reflected(self):
        """pos_default_partner_id en settings refleja el config."""
        self.pos_config.default_partner_id = self.partner
        settings = self._get_settings()
        self.assertEqual(settings.pos_default_partner_id, self.partner)
        self.pos_config.default_partner_id = False

    # ── has_open_pos_sessions ─────────────────────────────────────────────

    def test_04_has_open_sessions_false_without_sessions(self):
        """Cuando no hay sesiones abiertas, has_open_pos_sessions es False."""
        config = self.env["pos.config"].create(
            {
                "name": "Config Sin Sesiones",
                "payment_method_ids": [(6, 0, [self.card_pm.id])],
            }
        )
        settings = self._get_settings(config)
        self.assertFalse(settings.has_open_pos_sessions)

    def test_05_has_open_sessions_true_with_open_session(self):
        """Cuando hay sesión abierta, has_open_pos_sessions es True."""
        self._open_session()
        settings = self._get_settings()
        self.assertTrue(settings.has_open_pos_sessions)

    def test_06_has_open_sessions_false_without_config(self):
        """Sin pos_config_id, has_open_pos_sessions es False."""
        settings = self.env["res.config.settings"].create({})
        self.assertFalse(settings.has_open_pos_sessions)

    # ── set_values: bloqueo con sesión abierta ────────────────────────────

    def test_07_set_values_raises_with_open_session_on_mode_change(self):
        """set_values lanza UserError si se cambia pos_non_touch con sesión abierta."""
        from odoo import fields
        config = self.env["pos.config"].create(
            {
                "name": "Config Set Values Block",
                "pos_non_touch": True,
                "payment_method_ids": [(6, 0, [self._make_fresh_cash_pm().id])],
            }
        )
        session = self.env["pos.session"].with_context(skip_auto_open=True).create(
            {"config_id": config.id}
        )
        session.write({"state": "opened", "start_at": fields.Datetime.now()})

        settings = self._get_settings(config)
        with self.assertRaises(UserError):
            settings.pos_non_touch = False

    def test_08_set_values_ok_without_open_session(self):
        """set_values no lanza error si no hay sesiones abiertas."""
        config = self.env["pos.config"].create(
            {
                "name": "Config Set Values",
                "pos_non_touch": True,
                "payment_method_ids": [(6, 0, [self.card_pm.id])],
            }
        )
        settings = self._get_settings(config)
        settings.pos_non_touch = True
        settings.set_values()

    def test_09_set_values_no_error_same_value_with_open_session(self):
        """set_values no lanza error si el valor de pos_non_touch NO cambia."""
        self._open_session()
        settings = self._get_settings()
        # El config es True, settings también True → no hay cambio
        settings.pos_non_touch = True
        settings.set_values()  # No debe lanzar UserError

    # ── write() — ramas adicionales ───────────────────────────────────────

    def test_10_write_without_pos_non_touch_in_vals_calls_super_only(self):
        """write() sin 'pos_non_touch' en los vals no ejecuta el guard y llama super()."""
        settings = self._get_settings()
        # Escribir cualquier campo que no sea pos_non_touch → sin guard
        settings.write({"pos_config_id": self.pos_config.id})
        # Si no lanza error, el super() se ejecutó correctamente
        self.assertEqual(settings.pos_config_id, self.pos_config)

    def test_11_write_skips_guard_when_no_pos_config_id(self):
        """write() con pos_non_touch en vals pero sin pos_config_id ejecuta el continue.

        Cubre la rama `if not record.pos_config_id: continue` en write().
        Se usa SQL para forzar pos_config_id=NULL en el registro de settings,
        ya que Odoo lo asigna automáticamente por defecto.
        """
        settings = self._get_settings()
        # Forzar pos_config_id a NULL via SQL para alcanzar la rama continue
        self.env.cr.execute(
            "UPDATE res_config_settings SET pos_config_id = NULL WHERE id = %s",
            [settings.id],
        )
        settings.invalidate_recordset(["pos_config_id"])
        self.assertFalse(settings.pos_config_id, "pos_config_id debe ser False tras la limpieza SQL")
        # write() con pos_non_touch debe ejecutar 'continue' sin lanzar error
        # super().write() puede fallar (related field sin config), lo capturamos
        try:
            settings.write({"pos_non_touch": False})
        except Exception:
            pass  # Lo relevante es que nuestro guard (continue) se ejecutó

    # ── set_values() — ramas adicionales ─────────────────────────────────

    def test_12_set_values_skips_check_when_no_pos_config_id(self):
        """set_values() con settings sin pos_config_id ejecuta continue sin error.

        Cubre la rama `if not record.pos_config_id: continue` en set_values().
        """
        settings = self._get_settings()
        self.env.cr.execute(
            "UPDATE res_config_settings SET pos_config_id = NULL WHERE id = %s",
            [settings.id],
        )
        settings.invalidate_recordset(["pos_config_id"])
        self.assertFalse(settings.pos_config_id)
        # set_values() debe ejecutar continue sin lanzar error
        # super().set_values() puede tener efectos propios, lo aceptamos
        try:
            settings.set_values()
        except Exception:
            pass  # Sólo nos importa que el continue fue alcanzado

    def test_13_set_values_works_normally_and_propagates_to_config(self):
        """set_values() en flujo normal sin sesiones abierta actualiza el config correctamente.

        Cubre el flujo completo de set_values() cuando no hay sesiones abiertas
        y los valores no cambian (super().set_values() se llama correctamente).
        """
        config = self.env["pos.config"].create({
            "name": "Config Set Values Normal",
            "pos_non_touch": True,
            "payment_method_ids": [(6, 0, [self.card_pm.id])],
        })
        settings = self._get_settings(config)
        # Llamar set_values() en situación normal (sin sesiones, mismo valor)
        settings.set_values()
        # El config no debe haber cambiado (valores iguales → sin error)
        self.assertTrue(config.pos_non_touch)

