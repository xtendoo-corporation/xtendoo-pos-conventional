# Copyright 2024 Xtendoo
# License OPL-1
from odoo import fields
from odoo.tests.common import TransactionCase, tagged


@tagged("pos_conventional_core", "-standard")
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

        # ── Diario de caja exclusivo para los tests ────────────────────────
        # Se crea uno nuevo para evitar el error "same journal on multiples
        # cash payment methods" si ya existe un PM de caja en la BD.
        import uuid
        _suffix = uuid.uuid4().hex[:4].upper()
        cls.cash_journal_test = cls.env["account.journal"].create(
            {
                "name": f"Caja Test POS {_suffix}",
                "type": "cash",
                "code": f"CP{_suffix}",
                "company_id": company.id,
            }
        )

        # ── Mtodos de pago ────────────────────────────────────────────────
        cls.cash_pm = cls.env["pos.payment.method"].create(
            {
                "name": f"Efectivo Test {_suffix}",
                "journal_id": cls.cash_journal_test.id,
                "is_cash_count": True,
            }
        )
        cls.card_pm = cls.env["pos.payment.method"].create(
            {
                "name": f"Tarjeta Test {_suffix}",
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

        # ── Cuenta de ingresos (obligatoria en Odoo 19 para _compute_prices) ───────
        cls.income_account = cls.env["account.account"].search([
            ("account_type", "=", "income"),
            ("company_ids", "in", [company.id]),
        ], limit=1)
        if not cls.income_account:
            cls.income_account = cls.env["account.account"].search([
                ("account_type", "like", "income"),
            ], limit=1)

        # ── Productos ──────────────────────────────────────────────────────
        cls.product = cls.env["product.product"].create(
            {
                "name": "Producto POS Test",
                "type": "consu",
                "list_price": 100.0,
                "taxes_id": [(6, 0, [cls.tax_21.id])],
                "available_in_pos": True,
                "property_account_income_id": cls.income_account.id if cls.income_account else False,
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
                "property_account_income_id": cls.income_account.id if cls.income_account else False,
            }
        )

        # ── Partner ────────────────────────────────────────────────────────
        cls.partner = cls.env["res.partner"].create(
            {"name": "Cliente Test POS", "customer_rank": 1}
        )

        # ── Diario de facturas de clientes ────────────────────────────────
        cls.invoice_journal = cls.env["account.journal"].search(
            [("type", "=", "sale"), ("company_id", "=", company.id)], limit=1
        )
        if not cls.invoice_journal:
            cls.invoice_journal = cls.env["account.journal"].create(
                {
                    "name": "Facturas Clientes Test POS",
                    "type": "sale",
                    "code": "FCTST",
                    "company_id": company.id,
                }
            )

        # ── Configuración POS (modo no táctil) ─────────────────────────────
        cls.pos_config = cls.env["pos.config"].create(
            {
                "name": "Test POS Non-Touch",
                "pos_non_touch": True,
                "payment_method_ids": [(6, 0, [cls.cash_pm.id, cls.card_pm.id])],
                "invoice_journal_id": cls.invoice_journal.id,
                "default_partner_id": cls.partner.id,
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

    def _make_fresh_cash_pm(self, name=None):
        """Crea un método de pago en efectivo con su propio diario único.

        Cada pos.config necesita su propio PM de caja, y cada PM de caja
        debe tener un diario exclusivo (restricción de Odoo).
        """
        import uuid
        suffix = uuid.uuid4().hex[:3].upper()
        pm_name = name or f"Efectivo {suffix}"
        journal = self.env["account.journal"].create(
            {
                "name": f"Caja {suffix}",
                "type": "cash",
                "code": f"CT{suffix}",   # 5 chars max: CT + 3
                "company_id": self.env.company.id,
            }
        )
        return self.env["pos.payment.method"].create(
            {
                "name": pm_name,
                "journal_id": journal.id,
                "is_cash_count": True,
            }
        )

    def _make_draft_order(self, session=None, partner=None):
        """Crea un pedido POS en estado borrador."""
        if session is None:
            session = self._open_session()
        pricelist = session.config_id.pricelist_id
        vals = {
            "session_id": session.id,
            "config_id": session.config_id.id,
            "pricelist_id": pricelist.id if pricelist else False,
            "currency_id": session.currency_id.id,
            "amount_tax": 0.0,
            "amount_total": 0.0,
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
        line = self.env["pos.order.line"].create(vals)
        # En Odoo 19, _compute_prices usa @api.onchange, no @api.depends.
        # Hay que llamarlo manualmente para actualizar amount_total.
        # Si falla (p.ej. producto sin cuenta de ingresos), calculamos manualmente.
        try:
            order._compute_prices()
        except Exception:
            amount_total = sum(l.price_subtotal_incl for l in order.lines)
            amount_tax = sum(
                l.price_subtotal_incl - l.price_subtotal for l in order.lines
            )
            order.write({"amount_total": amount_total, "amount_tax": amount_tax})
        return line

    def _add_payment(self, order, payment_method=None, amount=None):
        """Registra un pago en el pedido."""
        payment_method = payment_method or self.cash_pm
        if amount is None:
            # Calcular desde líneas para evitar el compute diferido de amount_total
            if order.lines:
                amount = sum(line.price_subtotal_incl for line in order.lines)
            else:
                amount = order.amount_total or 0.0
        order.add_payment(
            {
                "pos_order_id": order.id,
                "payment_method_id": payment_method.id,
                "amount": amount,
            }
        )

    def _make_no_cash_control_config(self):
        """Crea un config POS non-touch SIN control de caja para tests de cierre limpio."""
        pm = self._make_fresh_cash_pm(
            name=f"PM NCC {self.env['ir.sequence'].next_by_code('pos.order') or ''}"
        )
        return self.env["pos.config"].create({
            "name": "Test POS No Cash Control",
            "pos_non_touch": True,
            "cash_control": False,
            "payment_method_ids": [(6, 0, [pm.id])],
        })

