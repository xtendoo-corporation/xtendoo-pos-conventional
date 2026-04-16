from odoo import fields
from odoo.tests.common import TransactionCase, tagged


@tagged("pos_conventional_returns", "-standard")
class PosConventionalReturnsCommon(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        company = cls.env.company

        cls.bank_journal = cls.env["account.journal"].search(
            [("type", "=", "bank"), ("company_id", "=", company.id)], limit=1
        )
        if not cls.bank_journal:
            cls.bank_journal = cls.env["account.journal"].create(
                {
                    "name": "Banco Test POS Returns",
                    "type": "bank",
                    "code": "RTRNB",
                    "company_id": company.id,
                }
            )

        cls.invoice_journal = cls.env["account.journal"].search(
            [("type", "=", "sale"), ("company_id", "=", company.id)], limit=1
        )
        if not cls.invoice_journal:
            cls.invoice_journal = cls.env["account.journal"].create(
                {
                    "name": "Facturas Test POS Returns",
                    "type": "sale",
                    "code": "RTRNS",
                    "company_id": company.id,
                }
            )

        import uuid

        suffix = uuid.uuid4().hex[:4].upper()
        cash_journal = cls.env["account.journal"].create(
            {
                "name": f"Caja Test Returns {suffix}",
                "type": "cash",
                "code": f"RT{suffix}",
                "company_id": company.id,
            }
        )
        cls.cash_pm = cls.env["pos.payment.method"].create(
            {
                "name": f"Efectivo Returns {suffix}",
                "journal_id": cash_journal.id,
                "is_cash_count": True,
            }
        )

        cls.tax_21 = cls.env["account.tax"].create(
            {
                "name": "IVA 21% Test Returns",
                "amount": 21.0,
                "type_tax_use": "sale",
                "company_id": company.id,
            }
        )

        cls.income_account = cls.env["account.account"].search(
            [("account_type", "=", "income"), ("company_ids", "in", [company.id])],
            limit=1,
        )
        if not cls.income_account:
            cls.income_account = cls.env["account.account"].search(
                [("account_type", "like", "income")], limit=1
            )

        cls.product = cls.env["product.product"].create(
            {
                "name": "Producto Returns",
                "type": "consu",
                "list_price": 100.0,
                "taxes_id": [(6, 0, [cls.tax_21.id])],
                "available_in_pos": True,
                "property_account_income_id": cls.income_account.id if cls.income_account else False,
            }
        )
        cls.partner = cls.env["res.partner"].create(
            {"name": "Cliente Returns", "customer_rank": 1}
        )

        config_vals = {
            "name": "TPV Returns",
            "payment_method_ids": [(6, 0, [cls.cash_pm.id])],
            "invoice_journal_id": cls.invoice_journal.id,
        }
        if "pos_non_touch" in cls.env["pos.config"]._fields:
            config_vals["pos_non_touch"] = True
        cls.pos_config = cls.env["pos.config"].create(config_vals)

    def _open_session(self, config=None):
        config = config or self.pos_config
        session = self.env["pos.session"].with_context(skip_auto_open=True).create(
            {"config_id": config.id, "user_id": self.env.uid}
        )
        session.write({"state": "opened", "start_at": fields.Datetime.now()})
        return session

    def _make_fresh_cash_pm(self, name=None):
        import uuid

        suffix = uuid.uuid4().hex[:3].upper()
        journal = self.env["account.journal"].create(
            {
                "name": f"Caja Returns {suffix}",
                "type": "cash",
                "code": f"RR{suffix}",
                "company_id": self.env.company.id,
            }
        )
        return self.env["pos.payment.method"].create(
            {
                "name": name or f"PM Returns {suffix}",
                "journal_id": journal.id,
                "is_cash_count": True,
            }
        )

    def _make_draft_order(self, session=None, partner=None):
        session = session or self._open_session()
        vals = {
            "session_id": session.id,
            "config_id": session.config_id.id,
            "pricelist_id": session.config_id.pricelist_id.id,
            "currency_id": session.currency_id.id,
            "amount_tax": 0.0,
            "amount_total": 0.0,
            "amount_paid": 0.0,
            "amount_return": 0.0,
        }
        if partner:
            vals["partner_id"] = partner.id
        return self.env["pos.order"].with_context(skip_completeness_check=True).create(vals)

    def _add_line(self, order, product=None, qty=1.0):
        product = product or self.product
        if hasattr(order, "_prepare_order_line_vals"):
            vals = order._prepare_order_line_vals(product, qty)
        else:
            price_unit = product.list_price
            taxes = product.taxes_id.filtered(
                lambda t: t.company_id == (order.company_id or self.env.company)
            )
            if taxes:
                tax_results = taxes.compute_all(
                    price_unit,
                    currency=order.currency_id or self.env.company.currency_id,
                    quantity=qty,
                    product=product,
                )
                price_subtotal = tax_results["total_excluded"]
                price_subtotal_incl = tax_results["total_included"]
            else:
                price_subtotal = price_unit * qty
                price_subtotal_incl = price_unit * qty
            vals = {
                "order_id": order.id,
                "product_id": product.id,
                "full_product_name": product.display_name,
                "qty": qty,
                "price_unit": price_unit,
                "discount": 0.0,
                "price_subtotal": price_subtotal,
                "price_subtotal_incl": price_subtotal_incl,
                "tax_ids": [(6, 0, taxes.ids)],
            }
        line = self.env["pos.order.line"].create(vals)
        try:
            order._compute_prices()
        except Exception:
            order.write(
                {
                    "amount_total": sum(l.price_subtotal_incl for l in order.lines),
                    "amount_tax": sum(l.price_subtotal_incl - l.price_subtotal for l in order.lines),
                }
            )
        return line

    def _add_payment(self, order, payment_method=None, amount=None):
        payment_method = payment_method or self.cash_pm
        if amount is None:
            amount = sum(line.price_subtotal_incl for line in order.lines) or order.amount_total
        order.add_payment(
            {
                "pos_order_id": order.id,
                "payment_method_id": payment_method.id,
                "amount": amount,
            }
        )

