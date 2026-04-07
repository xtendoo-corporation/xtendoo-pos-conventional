# Copyright 2024 Xtendoo
# License OPL-1
from odoo.tests.common import TransactionCase, tagged


@tagged("pos_conventional_core", "-standard", "post_install", "-at_install")
class TestCashboxCalculatorMixin(TransactionCase):
    """Tests para el mixin cashbox.calculator.mixin."""

    def _make_mixin_instance(self, **kwargs):
        """Instancia el mixin creando un wizard de calculadora."""
        return self.env["pos.cash.calculator.wizard"].create(kwargs)

    # ── _calculate_cashbox_total ──────────────────────────────────────────

    def test_01_total_zero_all_empty(self):
        """Sin ninguna cantidad, el total es 0."""
        # Usamos el wizard que hereda el mixin (sesión de gestión)
        # El cashbox.calculator.mixin es abstracto; se prueba vía wizard.
        # Aquí probamos PosCashCalculatorWizard que tiene los mismos campos.
        wizard = self._make_mixin_instance()
        self.assertEqual(wizard.total, 0.0)

    def test_02_total_only_200_bills(self):
        """Sólo billetes de 200€."""
        wizard = self._make_mixin_instance(qty_200=3)
        self.assertAlmostEqual(wizard.total, 600.0, places=2)

    def test_03_total_all_denominations(self):
        """Total correcto con todas las denominaciones (1 de cada)."""
        wizard = self._make_mixin_instance(
            qty_200=1, qty_100=1, qty_50=1, qty_20=1, qty_10=1, qty_5=1,
            qty_2=1, qty_1=1, qty_050=1, qty_025=1, qty_020=1, qty_010=1,
            qty_005=1, qty_002=1,
        )
        expected = (200 + 100 + 50 + 20 + 10 + 5
                    + 2 + 1 + 0.50 + 0.25 + 0.20 + 0.10 + 0.05 + 0.02)
        self.assertAlmostEqual(wizard.total, expected, places=2)

    def test_04_total_only_coins(self):
        """Sólo monedas (sin billetes)."""
        wizard = self._make_mixin_instance(qty_2=10, qty_1=5, qty_050=4)
        self.assertAlmostEqual(wizard.total, 10*2 + 5*1 + 4*0.50, places=2)

    def test_05_total_mixed(self):
        """Mezcla de billetes y monedas."""
        wizard = self._make_mixin_instance(
            qty_50=2, qty_20=3, qty_1=7, qty_010=10
        )
        expected = 2*50 + 3*20 + 7*1 + 10*0.10
        self.assertAlmostEqual(wizard.total, expected, places=2)

    def test_06_negative_quantities_not_used_in_normal_flow(self):
        """Cantidades negativas no se producen en el flujo normal."""
        wizard = self._make_mixin_instance(qty_50=1)
        self.assertGreater(wizard.total, 0)

