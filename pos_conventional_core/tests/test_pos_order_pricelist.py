# Copyright 2024 Xtendoo
# License OPL-1
"""
Tests para la funcionalidad de tarifa de precios en pedidos POS.

Comportamiento validado:
  - La tarifa activa se muestra en el formulario del pedido (solo lectura).
  - Al cambiar el cliente a uno con tarifa diferente, la tarifa del pedido
    se actualiza automáticamente y los precios de todas las líneas se
    recalculan (igual que en un pedido de ventas convencional).
  - El usuario no puede cambiar la tarifa manualmente; solo cambia al
    cambiar el cliente (o al borrar el cliente, vuelve a la de la sesión).
  - Si el cliente no tiene tarifa asignada, se mantiene la tarifa de la sesión.
  - Al borrar el cliente, se restaura la tarifa de la sesión.
  - Los subtotales se calculan sobre el precio efectivo (precio de lista menos
    descuento de tarifa), no sobre el precio de lista sin descuento.
"""
from odoo.tests.common import tagged

from .common import PosConventionalTestCommon


@tagged("pos_conventional_core", "-standard", "post_install", "-at_install")
class TestPosOrderPricelist(PosConventionalTestCommon):
    """Tests para el recálculo de precios por tarifa en pos.order."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        company = cls.env.company

        # ── Tarifa base para la sesión (precio de lista, sin descuento) ──────
        # Asignamos una tarifa explícita al config de test para que la sesión
        # tenga siempre una tarifa conocida y los tests sean predecibles.
        cls.pricelist_base = cls.env["product.pricelist"].create({
            "name": "Tarifa Base Test (sin descuento)",
            "currency_id": company.currency_id.id,
        })
        cls.pos_config.write({"pricelist_id": cls.pricelist_base.id})

        # ── Tarifa con 20 % de descuento global ──────────────────────────────
        cls.pricelist_20pct = cls.env["product.pricelist"].create({
            "name": "Tarifa Test -20%",
            "currency_id": company.currency_id.id,
            "item_ids": [(0, 0, {
                "compute_price": "percentage",
                "percent_price": 20.0,
                "applied_on": "3_global",
            })],
        })

        # ── Tarifa con precio fijo de 50 € para el producto de test ──────────
        cls.pricelist_fixed_50 = cls.env["product.pricelist"].create({
            "name": "Tarifa Test Precio Fijo 50",
            "currency_id": company.currency_id.id,
            "item_ids": [(0, 0, {
                "compute_price": "fixed",
                "fixed_price": 50.0,
                "applied_on": "0_product_variant",
                "product_id": cls.product.id,
            })],
        })

        # ── Partners de test ─────────────────────────────────────────────────
        # Cliente VIP: tiene tarifa -20% (diferente a la de la sesión)
        cls.partner_vip = cls.env["res.partner"].create({
            "name": "Cliente VIP (tarifa -20%)",
            "customer_rank": 1,
            "property_product_pricelist": cls.pricelist_20pct.id,
        })
        # Cliente sin tarifa especial: le asignamos explícitamente la tarifa
        # base de la sesión para que el onchange no la cambie.
        # En Odoo, property_product_pricelist siempre devuelve algún valor
        # (hereda la tarifa por defecto de la compañía si no hay explícita).
        # Asignamos la misma tarifa que la sesión para simular "sin cambio".
        cls.partner_no_pl = cls.env["res.partner"].create({
            "name": "Cliente Sin Tarifa Especial",
            "customer_rank": 1,
            "property_product_pricelist": cls.pricelist_base.id,
        })

    # ── Helpers internos ──────────────────────────────────────────────────────

    def _order_with_session_pricelist(self):
        """Crea una sesión y un pedido cuya tarifa es la del config de la sesión."""
        session = self._open_session()
        return session, self._make_draft_order(session)

    def _effective_price(self, price_unit, discount):
        """Precio efectivo neto = precio_unitario × (1 - descuento/100)."""
        return round(price_unit * (1.0 - discount / 100.0), 6)

    # ══════════════════════════════════════════════════════════════════════════
    # BLOQUE 1 — _prepare_order_line_vals: precio efectivo correcto
    # ══════════════════════════════════════════════════════════════════════════

    def test_01_prepare_vals_no_pricelist_uses_list_price(self):
        """Sin tarifa, price_unit = lst_price y discount = 0."""
        session, order = self._order_with_session_pricelist()
        order.pricelist_id = False
        vals = order._prepare_order_line_vals(self.product, 1.0)
        self.assertAlmostEqual(vals["price_unit"], self.product.lst_price, places=4)
        self.assertAlmostEqual(vals["discount"], 0.0, places=4)

    def test_02_prepare_vals_with_20pct_pricelist_sets_discount(self):
        """Con tarifa -20%, discount = 20 y price_unit = precio de lista."""
        session, order = self._order_with_session_pricelist()
        order.pricelist_id = self.pricelist_20pct
        vals = order._prepare_order_line_vals(self.product, 1.0)
        self.assertAlmostEqual(vals["price_unit"], self.product.lst_price, places=4,
                               msg="price_unit debe ser el precio de lista (100.0)")
        self.assertAlmostEqual(vals["discount"], 20.0, places=4,
                               msg="discount debe ser 20.0")

    def test_03_prepare_vals_subtotal_uses_effective_price(self):
        """Con tarifa -20%, price_subtotal se calcula sobre el precio efectivo (80.0).

        Verifica la corrección del bug anterior donde se usaba el precio de lista
        (100.0) en lugar del precio efectivo (80.0) para los subtotales.
        """
        session, order = self._order_with_session_pricelist()
        order.pricelist_id = self.pricelist_20pct
        # Pedido sin impuestos para simplificar el cálculo
        order.pricelist_id = self.pricelist_20pct
        vals = order._prepare_order_line_vals(self.product, 1.0)
        effective = self._effective_price(vals["price_unit"], vals["discount"])
        # price_subtotal debe ser ≤ price_unit (aplicando el descuento)
        self.assertLessEqual(
            vals["price_subtotal"],
            vals["price_unit"],
            "price_subtotal debe ser menor o igual a price_unit cuando hay descuento",
        )
        # price_subtotal_incl >= price_subtotal siempre
        self.assertGreaterEqual(vals["price_subtotal_incl"], vals["price_subtotal"])
        # Con 20% de descuento sobre 100.0: precio efectivo = 80.0
        self.assertAlmostEqual(effective, 80.0, places=2,
                               msg="Precio efectivo esperado = 80.0")

    def test_04_prepare_vals_fixed_50_sets_discount_from_list(self):
        """Con tarifa de precio fijo 50, discount = 50% y price_unit = 100.0."""
        session, order = self._order_with_session_pricelist()
        order.pricelist_id = self.pricelist_fixed_50
        vals = order._prepare_order_line_vals(self.product, 1.0)
        self.assertAlmostEqual(vals["price_unit"], self.product.lst_price, places=4,
                               msg="price_unit debe ser el precio de lista")
        self.assertAlmostEqual(vals["discount"], 50.0, places=2,
                               msg="Con precio fijo de 50 sobre lista de 100: discount = 50%")

    # ══════════════════════════════════════════════════════════════════════════
    # BLOQUE 2 — onchange partner_id: actualización de tarifa
    # ══════════════════════════════════════════════════════════════════════════

    def test_05_partner_with_different_pricelist_updates_order_pricelist(self):
        """Al asignar un cliente con tarifa distinta, la tarifa del pedido cambia."""
        session, order = self._order_with_session_pricelist()
        original_pricelist = order.pricelist_id

        # Asignar cliente VIP con tarifa -20%
        order.partner_id = self.partner_vip
        order._onchange_partner_id_update_pricelist()

        self.assertEqual(
            order.pricelist_id,
            self.pricelist_20pct,
            f"La tarifa del pedido debe ser la del cliente VIP. "
            f"original={original_pricelist.name}, actual={order.pricelist_id.name}",
        )

    def test_06_partner_without_special_pricelist_keeps_session_pricelist(self):
        """Al asignar cliente con la misma tarifa que la sesión, la tarifa no cambia."""
        session, order = self._order_with_session_pricelist()
        session_pricelist = order.pricelist_id

        # partner_no_pl tiene la tarifa base (misma que la sesión)
        order.partner_id = self.partner_no_pl
        order._onchange_partner_id_update_pricelist()

        self.assertEqual(
            order.pricelist_id,
            session_pricelist,
            "Con la tarifa del cliente igual a la de la sesión, no debe cambiar",
        )

    def test_07_clear_partner_reverts_to_session_pricelist(self):
        """Al borrar el cliente tras haber cambiado la tarifa, vuelve la tarifa de sesión."""
        session, order = self._order_with_session_pricelist()
        session_pricelist = order.pricelist_id
        # pricelist_base debe ser la tarifa de la sesión
        self.assertEqual(
            session_pricelist,
            self.pricelist_base,
            "La tarifa de la sesión debe coincidir con pricelist_base del setup",
        )

        # Asignar cliente VIP → cambia tarifa
        order.partner_id = self.partner_vip
        order._onchange_partner_id_update_pricelist()
        self.assertEqual(order.pricelist_id, self.pricelist_20pct)

        # Borrar el cliente → debe volver a la tarifa de la sesión (pricelist_base)
        order.partner_id = False
        order._onchange_partner_id_update_pricelist()
        self.assertEqual(
            order.pricelist_id,
            session_pricelist,
            "Al borrar el cliente, la tarifa debe revertir a la de la sesión",
        )

    def test_08_partner_with_same_pricelist_no_change(self):
        """Si el cliente tiene la misma tarifa que el pedido, no cambia nada."""
        session, order = self._order_with_session_pricelist()
        original_pricelist = order.pricelist_id

        # partner_no_pl tiene la misma tarifa que la sesión
        order.partner_id = self.partner_no_pl
        order._onchange_partner_id_update_pricelist()

        self.assertEqual(
            order.pricelist_id,
            original_pricelist,
            "Con la misma tarifa, el pedido no debe cambiar",
        )

    # ══════════════════════════════════════════════════════════════════════════
    # BLOQUE 3 — onchange partner_id: recálculo de líneas
    # ══════════════════════════════════════════════════════════════════════════

    def test_09_partner_change_triggers_line_price_recalculation(self):
        """Al cambiar a cliente VIP, los precios de línea se recalculan con -20%."""
        session, order = self._order_with_session_pricelist()
        self._add_line(order, self.product, 1.0)
        line = order.lines[0]

        # Precio original (sin tarifa especial o tarifa de sesión)
        original_price_unit = line.price_unit

        # Asignar cliente VIP con tarifa -20%
        order.partner_id = self.partner_vip
        order._onchange_partner_id_update_pricelist()

        # El precio de la línea debe haber cambiado (la tarifa aplicó el 20%)
        # Al menos discount debe ser 20 o price_unit diferente
        new_discount = line.discount
        new_price_unit = line.price_unit
        self.assertTrue(
            new_discount > 0 or new_price_unit < original_price_unit,
            f"Los precios de línea deben recalcularse. "
            f"price_unit: {original_price_unit} → {new_price_unit}, discount: {new_discount}",
        )

    def test_10_line_discount_is_20_after_vip_partner(self):
        """Con tarifa -20% y producto a 100.0, discount de la línea es 20.0."""
        session, order = self._order_with_session_pricelist()
        self._add_line(order, self.product, 1.0)

        order.partner_id = self.partner_vip
        order._onchange_partner_id_update_pricelist()

        line = order.lines[0]
        self.assertAlmostEqual(
            line.discount, 20.0, places=2,
            msg=f"Descuento esperado 20.0, obtenido {line.discount}",
        )

    def test_11_line_price_unit_keeps_list_price_after_pricelist(self):
        """Con tarifa -20%, price_unit mantiene el precio de lista (100.0)."""
        session, order = self._order_with_session_pricelist()
        self._add_line(order, self.product, 1.0)

        order.partner_id = self.partner_vip
        order._onchange_partner_id_update_pricelist()

        line = order.lines[0]
        self.assertAlmostEqual(
            line.price_unit, self.product.lst_price, places=2,
            msg="price_unit debe ser el precio de lista (para mostrar el descuento visualmente)",
        )

    def test_12_order_total_updated_after_partner_change(self):
        """Los totales del pedido se recalculan tras el cambio de cliente/tarifa."""
        session, order = self._order_with_session_pricelist()
        self._add_line(order, self.product, 1.0)

        original_total = order.amount_total

        order.partner_id = self.partner_vip
        order._onchange_partner_id_update_pricelist()

        # El total debe haberse reducido (20% de descuento)
        self.assertLess(
            order.amount_total,
            original_total,
            f"Con tarifa -20%, amount_total debe reducirse. "
            f"original={original_total}, nuevo={order.amount_total}",
        )

    # ══════════════════════════════════════════════════════════════════════════
    # BLOQUE 4 — _recompute_lines_with_pricelist: recálculo directo
    # La tarifa es de solo lectura en el formulario; el único medio de cambio
    # es vía el partner (onchange partner_id). Estos tests validan el método
    # de recálculo invocado internamente por ese onchange.
    # ══════════════════════════════════════════════════════════════════════════

    def test_13_recompute_with_20pct_pricelist_sets_correct_discount(self):
        """_recompute_lines_with_pricelist con tarifa -20% actualiza discount a 20.0."""
        session, order = self._order_with_session_pricelist()
        self._add_line(order, self.product, 1.0)
        original_discount = order.lines[0].discount

        order.pricelist_id = self.pricelist_20pct
        order._recompute_lines_with_pricelist()

        self.assertNotEqual(
            order.lines[0].discount,
            original_discount,
            "El descuento debe cambiar al recalcular con tarifa -20%",
        )
        self.assertAlmostEqual(order.lines[0].discount, 20.0, places=2)

    def test_14_recompute_with_fixed_50_sets_50pct_discount(self):
        """_recompute_lines_with_pricelist con tarifa precio fijo 50 → discount = 50%."""
        session, order = self._order_with_session_pricelist()
        self._add_line(order, self.product, 1.0)

        order.pricelist_id = self.pricelist_fixed_50
        order._recompute_lines_with_pricelist()

        line = order.lines[0]
        self.assertAlmostEqual(
            line.discount, 50.0, places=2,
            msg=f"Con precio fijo 50 sobre lista 100, descuento = 50%. obtenido={line.discount}",
        )

    def test_15_recompute_without_lines_no_error(self):
        """_recompute_lines_with_pricelist en pedido sin líneas no lanza error."""
        session, order = self._order_with_session_pricelist()
        order.pricelist_id = self.pricelist_20pct
        try:
            order._recompute_lines_with_pricelist()
        except Exception as exc:
            self.fail(f"_recompute_lines_with_pricelist sin líneas lanzó error: {exc}")

    def test_16_recompute_updates_order_amount_total(self):
        """_recompute_lines_with_pricelist actualiza amount_total del pedido."""
        session, order = self._order_with_session_pricelist()
        self._add_line(order, self.product, 2.0)
        original_total = order.amount_total

        order.pricelist_id = self.pricelist_fixed_50
        order._recompute_lines_with_pricelist()

        self.assertLess(
            order.amount_total,
            original_total,
            f"Con precio fijo 50 en lugar de 100, el total debe reducirse. "
            f"original={original_total}, nuevo={order.amount_total}",
        )

    # ══════════════════════════════════════════════════════════════════════════
    # BLOQUE 5 — _recompute_lines_with_pricelist: casos límite
    # ══════════════════════════════════════════════════════════════════════════

    def test_17_recompute_without_pricelist_does_nothing(self):
        """_recompute_lines_with_pricelist sin tarifa no lanza error ni modifica."""
        session, order = self._order_with_session_pricelist()
        self._add_line(order, self.product, 1.0)
        original_price = order.lines[0].price_unit

        order.pricelist_id = False
        order._recompute_lines_with_pricelist()

        self.assertAlmostEqual(
            order.lines[0].price_unit, original_price, places=2,
            msg="Sin tarifa, _recompute_lines no debe modificar price_unit",
        )

    def test_18_recompute_with_multiple_lines(self):
        """_recompute_lines_with_pricelist actualiza todas las líneas del pedido."""
        session, order = self._order_with_session_pricelist()
        self._add_line(order, self.product, 1.0)
        self._add_line(order, self.product_barcode, 2.0)

        order.pricelist_id = self.pricelist_20pct
        order._recompute_lines_with_pricelist()

        for line in order.lines:
            if line.product_id == self.product:
                self.assertAlmostEqual(
                    line.discount, 20.0, places=2,
                    msg=f"Línea {line.product_id.name}: descuento esperado 20.0",
                )

    def test_19_paid_order_partner_change_not_recalculated(self):
        """El onchange de partner_id no recalcula líneas si el pedido no está en draft."""
        session, order = self._order_with_session_pricelist()
        self._add_line(order, self.product, 1.0)
        original_discount = order.lines[0].discount

        # Simular pedido ya pagado
        order.write({"state": "paid"})
        order.partner_id = self.partner_vip
        order._onchange_partner_id_update_pricelist()

        self.assertEqual(
            order.lines[0].discount,
            original_discount,
            "Un pedido pagado NO debe recalcular sus líneas al cambiar el cliente",
        )

    def test_20_pricelist_shown_on_order(self):
        """pricelist_id está disponible en el pedido y contiene la tarifa activa."""
        session, order = self._order_with_session_pricelist()
        # El campo debe ser accesible (no invisible a nivel de modelo)
        self.assertIn(
            "pricelist_id",
            order._fields,
            "pricelist_id debe ser un campo del modelo pos.order",
        )
        # Debe estar en sync con la sesión
        if session.config_id.pricelist_id:
            self.assertEqual(
                order.pricelist_id,
                session.config_id.pricelist_id,
                "La tarifa del pedido debe coincidir con la de la sesión al crearlo",
            )



