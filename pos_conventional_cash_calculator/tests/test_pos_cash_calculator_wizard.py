# Copyright 2024 Xtendoo
# License OPL-1
from odoo.tests.common import TransactionCase, tagged


@tagged("pos_conventional", "-standard")
class TestPosCashCalculatorWizard(TransactionCase):
    """Tests para pos.cash.calculator.wizard."""

    def _make_wizard(self, **kwargs):
        return self.env["pos.cash.calculator.wizard"].create(kwargs)

    # ── _compute_total ────────────────────────────────────────────────────

    def test_01_compute_total_empty(self):
        w = self._make_wizard()
        self.assertEqual(w.total, 0.0)

    def test_02_compute_total_200_bills(self):
        w = self._make_wizard(qty_200=5)
        self.assertAlmostEqual(w.total, 1000.0, places=2)

    def test_03_compute_total_full_denominations(self):
        w = self._make_wizard(
            qty_200=1, qty_100=1, qty_50=1, qty_20=1, qty_10=1, qty_5=1,
            qty_2=1, qty_1=1, qty_050=1, qty_025=1, qty_020=1, qty_010=1,
            qty_005=1, qty_002=1,
        )
        expected = 200+100+50+20+10+5+2+1+0.5+0.25+0.2+0.1+0.05+0.02
        self.assertAlmostEqual(w.total, expected, places=2)

    # ── increment / decrement ─────────────────────────────────────────────

    def test_04_increment_200(self):
        w = self._make_wizard()
        w.increment_200()
        self.assertEqual(w.qty_200, 1)

    def test_05_increment_100(self):
        w = self._make_wizard()
        w.increment_100()
        self.assertEqual(w.qty_100, 1)

    def test_06_increment_50(self):
        w = self._make_wizard()
        w.increment_50()
        self.assertEqual(w.qty_50, 1)

    def test_07_increment_20(self):
        w = self._make_wizard()
        w.increment_20()
        self.assertEqual(w.qty_20, 1)

    def test_08_increment_10(self):
        w = self._make_wizard()
        w.increment_10()
        self.assertEqual(w.qty_10, 1)

    def test_09_increment_5(self):
        w = self._make_wizard()
        w.increment_5()
        self.assertEqual(w.qty_5, 1)

    def test_10_increment_2(self):
        w = self._make_wizard()
        w.increment_2()
        self.assertEqual(w.qty_2, 1)

    def test_11_increment_1(self):
        w = self._make_wizard()
        w.increment_1()
        self.assertEqual(w.qty_1, 1)

    def test_12_increment_050(self):
        w = self._make_wizard()
        w.increment_050()
        self.assertEqual(w.qty_050, 1)

    def test_13_increment_025(self):
        w = self._make_wizard()
        w.increment_025()
        self.assertEqual(w.qty_025, 1)

    def test_14_increment_020(self):
        w = self._make_wizard()
        w.increment_020()
        self.assertEqual(w.qty_020, 1)

    def test_15_increment_010(self):
        w = self._make_wizard()
        w.increment_010()
        self.assertEqual(w.qty_010, 1)

    def test_16_increment_005(self):
        w = self._make_wizard()
        w.increment_005()
        self.assertEqual(w.qty_005, 1)

    def test_17_increment_002(self):
        w = self._make_wizard()
        w.increment_002()
        self.assertEqual(w.qty_002, 1)

    def test_18_decrement_200_below_zero_stays_zero(self):
        w = self._make_wizard()
        w.decrement_200()
        self.assertEqual(w.qty_200, 0)

    def test_19_decrement_200_reduces(self):
        w = self._make_wizard(qty_200=3)
        w.decrement_200()
        self.assertEqual(w.qty_200, 2)

    def test_20_decrement_all_methods_floor_zero(self):
        """Todos los decrements respetan el suelo en 0."""
        w = self._make_wizard()
        for method in (
            w.decrement_100, w.decrement_50, w.decrement_20, w.decrement_10,
            w.decrement_5, w.decrement_2, w.decrement_1, w.decrement_050,
            w.decrement_025, w.decrement_020, w.decrement_010, w.decrement_005,
            w.decrement_002,
        ):
            method()
        for attr in ("qty_100","qty_50","qty_20","qty_10","qty_5","qty_2",
                     "qty_1","qty_050","qty_025","qty_020","qty_010","qty_005","qty_002"):
            self.assertEqual(getattr(w, attr), 0, f"{attr} debería ser 0")

    # ── increment returns reload action ──────────────────────────────────

    def test_21_increment_returns_act_window(self):
        w = self._make_wizard()
        result = w.increment_200()
        self.assertEqual(result.get("type"), "ir.actions.act_window")
        self.assertEqual(result.get("res_model"), "pos.cash.calculator.wizard")

    def test_22_decrement_returns_act_window(self):
        w = self._make_wizard(qty_50=2)
        result = w.decrement_50()
        self.assertEqual(result.get("type"), "ir.actions.act_window")

    # ── _get_parent_wizard ────────────────────────────────────────────────

    def test_23_get_parent_wizard_no_parent_returns_false(self):
        w = self._make_wizard()
        self.assertFalse(w._get_parent_wizard())

    # ── action_cancel without parent ─────────────────────────────────────

    def test_24_action_cancel_no_parent_closes_window(self):
        w = self._make_wizard()
        result = w.action_cancel()
        self.assertEqual(result.get("type"), "ir.actions.act_window_close")

    # ── action_confirm without parent ────────────────────────────────────

    def test_25_action_confirm_no_parent_closes_window(self):
        w = self._make_wizard(qty_100=1)
        result = w.action_confirm()
        self.assertEqual(result.get("type"), "ir.actions.act_window_close")

    # ── currency_id default ───────────────────────────────────────────────

    def test_26_currency_defaults_to_company_currency(self):
        w = self._make_wizard()
        self.assertEqual(w.currency_id, self.env.company.currency_id)

    # ── action_confirm con wizard padre de cierre ─────────────────────────

    def _make_fresh_cash_pm(self, name="Test Cash Calc"):
        """Crea PM de caja con diario exclusivo (cada config POS necesita el suyo)."""
        import uuid
        suffix = uuid.uuid4().hex[:3].upper()
        cash_journal = self.env["account.journal"].create(
            {
                "name": f"Caja {name[:8]} {suffix}",
                "type": "cash",
                "code": f"CC{suffix}",   # 5 chars: CC + 3
                "company_id": self.env.company.id,
            }
        )
        return self.env["pos.payment.method"].create({
            "name": f"{name} {suffix}",
            "journal_id": cash_journal.id,
            "is_cash_count": True,
        })

    def test_27_action_confirm_with_closing_wizard_parent(self):
        """action_confirm actualiza el saldo del wizard de cierre padre."""
        cash_pm = self._make_fresh_cash_pm("Cash Confirm")
        config = self.env["pos.config"].create(
            {
                "name": "Config Calc Confirm",
                "payment_method_ids": [(6, 0, [cash_pm.id])],
            }
        )

        from odoo import fields as odoo_fields
        session = self.env["pos.session"].with_context(skip_auto_open=True).create(
            {"config_id": config.id}
        )
        session.write({"state": "opened", "start_at": odoo_fields.Datetime.now()})

        closing_wizard = self.env["pos.session.closing.wizard"].create(
            {"session_id": session.id, "cash_register_balance_end_real": 0.0}
        )

        calc_wizard = self._make_wizard(
            qty_100=2,
            parent_model="pos.session.closing.wizard",
            parent_res_id=closing_wizard.id,
        )
        result = calc_wizard.action_confirm()
        self.assertIsInstance(result, dict)
        self.assertAlmostEqual(closing_wizard.cash_register_balance_end_real, 200.0, places=2)

    def test_28_action_cancel_with_parent_returns_parent_action(self):
        """action_cancel con wizard padre devuelve la acción de vuelta al padre."""
        cash_pm = self._make_fresh_cash_pm("Cash Cancel")
        config = self.env["pos.config"].create(
            {
                "name": "Config Calc Cancel",
                "payment_method_ids": [(6, 0, [cash_pm.id])],
            }
        )
        from odoo import fields as odoo_fields
        session = self.env["pos.session"].with_context(skip_auto_open=True).create(
            {"config_id": config.id}
        )
        session.write({"state": "opened", "start_at": odoo_fields.Datetime.now()})
        closing_wizard = self.env["pos.session.closing.wizard"].create(
            {"session_id": session.id}
        )
        calc_wizard = self._make_wizard(
            parent_model="pos.session.closing.wizard",
            parent_res_id=closing_wizard.id,
        )
        result = calc_wizard.action_cancel()
        self.assertEqual(result.get("type"), "ir.actions.act_window")
        self.assertEqual(result.get("res_model"), "pos.session.closing.wizard")

    # ── parent_model selection field ──────────────────────────────────────

    def test_29_parent_model_field_values(self):
        """parent_model acepta los valores de selección válidos."""
        w1 = self._make_wizard(parent_model="pos.session.closing.wizard")
        self.assertEqual(w1.parent_model, "pos.session.closing.wizard")

    # ── increment/decrement con recálculo de total ─────────────────────────

    def test_30_multiple_increments_accumulate_total(self):
        """Varios incrementos acumulan el total correctamente."""
        w = self._make_wizard()
        w.increment_50()
        w.increment_50()
        w.increment_50()
        self.assertAlmostEqual(w.total, 150.0, places=2)

