# Copyright 2024 Xtendoo
# License OPL-1
from odoo import fields
from odoo.tests.common import TransactionCase, tagged


@tagged("pos_conventional", "-standard")
class PosConventionalTestCommon(TransactionCase):
    """
    Clase base para todos los tests de pos_conventional_*.
    Crea un entorno mínimo operativo: config POS non-touch, sesión, productos,
    partner, métodos de pago (efectivo + tarjeta).
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        company = cls.env.company

        # ── Diarios contables ──────────────────────────────────────────────
        cls.cash_journal = cls.env["account.journal"].search(
            [("type", "=", "cash"), ("company_id", "=", company.id)], limit=1
        )
        if not cls.cash_journal:
            cls.cash_journal = cls.env["account.journal"].create(
                {
                    "name": "Test Cash POS",
                    "type": "cash",
                    "code": "TSTCSH",
                    "company_id": company.id,
                }
            )

        cls.bank_journal = cls.env["account.journal"].search(
            [("type", "=", "bank"), ("company_id", "=", company.id)], limit=1
        )
        if not cls.bank_journal:
            cls.bank_journal = cls.env["account.journal"].create(
                {
                    "name": "Test Bank POS",
                    "type": "bank",
                    "code": "TSTBNK",
                    "company_id": company.id,
                }
            )

        # ── Métodos de pago ────────────────────────────────────────────────
        cls.cash_pm = cls.env["pos.payment.method"].create(
            {
                "name": "Efectivo Test",
                "journal_id": cls.cash_journal.id,
                "is_cash_count": True,
            }
        )
        cls.card_pm = cls.env["pos.payment.method"].create(
            {
                "name": "Tarjeta Test",
                "journal_id": cls.bank_journal.id,
            }
        )

        # ── Impuesto ───────────────────────────────────────────────────────
        cls.tax_21 = cls.env["account.tax"].create(
            {
                "name": "IVA 21% Test Conv",
                "amount": 21.0,
                "type_tax_use": "sale",
                "company_id": company.id,
            }
        )

        # ── Productos ──────────────────────────────────────────────────────
        cls.product = cls.env["product.product"].create(
            {
                "name": "Producto POS Test",
                "type": "consu",
                "list_price": 100.0,
                "taxes_id": [(6, 0, [cls.tax_21.id])],
                "available_in_pos": True,
            }
        )
        cls.product_barcode = cls.env["product.product"].create(
            {
                "name": "Producto Barcode Test",
                "type": "consu",
                "list_price": 25.0,
                "barcode": "TST0001BARCODE",
                "default_code": "TST0001",
                "available_in_pos": True,
            }
        )

        # ── Partner ────────────────────────────────────────────────────────
        cls.partner = cls.env["res.partner"].create(
            {"name": "Cliente Test POS", "customer_rank": 1}
        )

        # ── Configuración POS (modo no táctil) ─────────────────────────────
        cls.pos_config = cls.env["pos.config"].create(
            {
                "name": "Test POS Non-Touch",
                "pos_non_touch": True,
                "payment_method_ids": [(6, 0, [cls.cash_pm.id, cls.card_pm.id])],
            }
        )

    # ── Helpers ────────────────────────────────────────────────────────────

    def _open_session(self, config=None):
        """Crea y abre una sesión POS en modo backend (sin popup OWL)."""
        config = config or self.pos_config
        session = self.env["pos.session"].with_context(skip_auto_open=True).create(
            {"config_id": config.id, "user_id": self.env.uid}
        )
        session.write({"state": "opened", "start_at": fields.Datetime.now()})
        return session

    def _make_draft_order(self, session=None, partner=None):
        """Crea un pedido POS en estado borrador."""
        if session is None:
            session = self._open_session()
        vals = {
            "session_id": session.id,
            "config_id": session.config_id.id,
            "pricelist_id": session.config_id.pricelist_id.id,
            "currency_id": session.currency_id.id,
            "amount_tax": 0.0,
            "amount_paid": 0.0,
            "amount_return": 0.0,
        }
        if partner:
            vals["partner_id"] = partner.id
        return self.env["pos.order"].create(vals)

    def _add_line(self, order, product=None, qty=1.0):
        """Añade una línea de pedido usando el helper del core."""
        product = product or self.product
        vals = order._prepare_order_line_vals(product, qty)
        return self.env["pos.order.line"].create(vals)

    def _add_payment(self, order, payment_method=None, amount=None):
        """Registra un pago en el pedido."""
        payment_method = payment_method or self.cash_pm
        if amount is None:
            amount = order.amount_total
        order.add_payment(
            {
                "pos_order_id": order.id,
                "payment_method_id": payment_method.id,
                "amount": amount,
            }
        )

