# Copyright 2024 Xtendoo
# License OPL-1
"""
Tests para la restricción de completitud de pedidos POS backend.

Comportamiento validado:
  - No se puede guardar un pedido de modo backend (pos_non_touch) en borrador
    si le falta el cliente, la tarifa de precios o las líneas de producto.
  - Los pedidos en estado distinto a 'draft' no están sujetos a esta validación.
  - Los pedidos de configuraciones no-backend (pos_non_touch=False) no se ven
    afectados por la restricción.
  - El contexto 'skip_completeness_check' permite crear pedidos incompletos
    en operaciones programáticas (tests, migraciones, imports).
  - Un pedido completo (cliente + tarifa + líneas) se guarda sin errores.
"""
from odoo.exceptions import ValidationError
from odoo.tests.common import tagged

from .common import PosConventionalTestCommon


@tagged("pos_conventional_core", "-standard", "post_install", "-at_install")
class TestPosOrderCompleteness(PosConventionalTestCommon):
    """Tests para _check_order_completeness en pos.order."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Asignar una tarifa explícita al config de test para que la sesión
        # siempre tenga una tarifa conocida y los tests sean predecibles.
        cls.pricelist_base = cls.env["product.pricelist"].create({
            "name": "Tarifa Base Completeness Test",
            "currency_id": cls.env.company.currency_id.id,
        })
        cls.pos_config.write({"pricelist_id": cls.pricelist_base.id})

    # ── Helpers internos ──────────────────────────────────────────────────────

    def _complete_order_vals(self, session):
        """Devuelve un dict con todos los campos requeridos para un pedido completo."""
        pricelist = session.config_id.pricelist_id
        return {
            "session_id": session.id,
            "config_id": session.config_id.id,
            "partner_id": self.partner.id,
            "pricelist_id": pricelist.id if pricelist else False,
            "currency_id": session.currency_id.id,
            "amount_tax": 0.0,
            "amount_total": 0.0,
            "amount_paid": 0.0,
            "amount_return": 0.0,
        }

    def _create_order_with_line(self, session):
        """Crea un pedido completo (cliente + tarifa + línea) sin bypass."""
        vals = self._complete_order_vals(session)
        price_unit = self.product.lst_price
        vals["lines"] = [(0, 0, {
            "product_id": self.product.id,
            "full_product_name": self.product.display_name,
            "qty": 1.0,
            "price_unit": price_unit,
            "discount": 0.0,
            "price_subtotal": price_unit,
            "price_subtotal_incl": price_unit,
            "tax_ids": [(6, 0, [])],
        })]
        return self.env["pos.order"].create(vals)

    # ══════════════════════════════════════════════════════════════════════════
    # BLOQUE 1 — Guardar pedido completo: debe funcionar sin errores
    # ══════════════════════════════════════════════════════════════════════════

    def test_01_complete_order_saves_without_error(self):
        """Un pedido con cliente, tarifa y líneas se guarda correctamente."""
        session = self._open_session()
        try:
            order = self._create_order_with_line(session)
        except ValidationError as exc:
            self.fail(f"Un pedido completo no debería fallar al guardarse: {exc}")
        self.assertTrue(order.exists())
        self.assertTrue(order.partner_id)
        self.assertTrue(order.pricelist_id)
        self.assertTrue(order.lines)

    # ══════════════════════════════════════════════════════════════════════════
    # BLOQUE 2 — Guardar pedido incompleto: debe lanzar ValidationError
    # ══════════════════════════════════════════════════════════════════════════

    def test_02_save_without_partner_raises_error(self):
        """Guardar un pedido sin cliente lanza ValidationError."""
        session = self._open_session()
        price_unit = self.product.lst_price
        pricelist = session.config_id.pricelist_id
        vals = {
            "session_id": session.id,
            "config_id": session.config_id.id,
            # Sin partner_id
            "pricelist_id": pricelist.id if pricelist else False,
            "currency_id": session.currency_id.id,
            "amount_tax": 0.0,
            "amount_total": 0.0,
            "amount_paid": 0.0,
            "amount_return": 0.0,
            "lines": [(0, 0, {
                "product_id": self.product.id,
                "full_product_name": self.product.display_name,
                "qty": 1.0,
                "price_unit": price_unit,
                "discount": 0.0,
                "price_subtotal": price_unit,
                "price_subtotal_incl": price_unit,
                "tax_ids": [(6, 0, [])],
            })],
        }
        with self.assertRaises(ValidationError, msg="Debe fallar sin cliente"):
            self.env["pos.order"].create(vals)

    def test_03_save_without_pricelist_raises_error(self):
        """Guardar un pedido sin tarifa de precios lanza ValidationError."""
        session = self._open_session()
        price_unit = self.product.lst_price
        vals = {
            "session_id": session.id,
            "config_id": session.config_id.id,
            "partner_id": self.partner.id,
            # Sin pricelist_id
            "pricelist_id": False,
            "currency_id": session.currency_id.id,
            "amount_tax": 0.0,
            "amount_total": 0.0,
            "amount_paid": 0.0,
            "amount_return": 0.0,
            "lines": [(0, 0, {
                "product_id": self.product.id,
                "full_product_name": self.product.display_name,
                "qty": 1.0,
                "price_unit": price_unit,
                "discount": 0.0,
                "price_subtotal": price_unit,
                "price_subtotal_incl": price_unit,
                "tax_ids": [(6, 0, [])],
            })],
        }
        with self.assertRaises(ValidationError, msg="Debe fallar sin tarifa"):
            self.env["pos.order"].create(vals)

    def test_04_save_without_lines_raises_error(self):
        """Guardar un pedido sin líneas de producto lanza ValidationError."""
        session = self._open_session()
        pricelist = session.config_id.pricelist_id
        vals = {
            "session_id": session.id,
            "config_id": session.config_id.id,
            "partner_id": self.partner.id,
            "pricelist_id": pricelist.id if pricelist else False,
            "currency_id": session.currency_id.id,
            "amount_tax": 0.0,
            "amount_total": 0.0,
            "amount_paid": 0.0,
            "amount_return": 0.0,
            # Sin lines
        }
        with self.assertRaises(ValidationError, msg="Debe fallar sin líneas"):
            self.env["pos.order"].create(vals)

    def test_05_remove_partner_from_draft_raises_error(self):
        """Borrar el cliente de un pedido en borrador lanza ValidationError."""
        session = self._open_session()
        order = self._create_order_with_line(session)
        with self.assertRaises(ValidationError, msg="Debe fallar al borrar el cliente"):
            order.write({"partner_id": False})

    def test_06_remove_pricelist_from_draft_raises_error(self):
        """Borrar la tarifa de un pedido en borrador lanza ValidationError."""
        session = self._open_session()
        order = self._create_order_with_line(session)
        with self.assertRaises(ValidationError, msg="Debe fallar al borrar la tarifa"):
            order.write({"pricelist_id": False})

    # ══════════════════════════════════════════════════════════════════════════
    # BLOQUE 3 — Pedidos en estado no-draft: sin restricción
    # ══════════════════════════════════════════════════════════════════════════

    def test_07_paid_order_without_partner_no_error(self):
        """Un pedido ya pagado (no draft) no está sujeto a la restricción."""
        session = self._open_session()
        # Crear pedido completo primero
        order = self._create_order_with_line(session)
        # Simular estado pagado
        order.write({"state": "paid"})
        # Ahora borrar el partner: no debe lanzar error
        try:
            order.write({"partner_id": False})
        except ValidationError as exc:
            self.fail(f"Un pedido pagado no debería validar completitud: {exc}")

    # ══════════════════════════════════════════════════════════════════════════
    # BLOQUE 4 — Contexto skip_completeness_check: permite pedidos incompletos
    # ══════════════════════════════════════════════════════════════════════════

    def test_08_skip_context_allows_incomplete_order(self):
        """Con skip_completeness_check=True se pueden guardar pedidos incompletos."""
        session = self._open_session()
        pricelist = session.config_id.pricelist_id
        try:
            order = self.env["pos.order"].with_context(
                skip_completeness_check=True
            ).create({
                "session_id": session.id,
                "config_id": session.config_id.id,
                # Sin partner, sin líneas
                "pricelist_id": pricelist.id if pricelist else False,
                "currency_id": session.currency_id.id,
                "amount_tax": 0.0,
                "amount_total": 0.0,
                "amount_paid": 0.0,
                "amount_return": 0.0,
            })
        except ValidationError as exc:
            self.fail(
                f"Con skip_completeness_check no debería fallar: {exc}"
            )
        self.assertTrue(order.exists())

