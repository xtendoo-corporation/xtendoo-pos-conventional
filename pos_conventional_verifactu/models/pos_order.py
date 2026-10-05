from odoo import models

from ..utils import build_verifactu_receipt_values


class PosOrder(models.Model):
    _inherit = "pos.order"

    def _get_pos_conventional_verifactu_receipt_values(self):
        """Veri*Factu data printed on the POS Conventional 80mm receipts.

        Mirrors ``l10n_es_edi_verifactu_pos``: invoiced orders print the
        invoice record, the rest print the order's own Veri*Factu record.
        """
        self.ensure_one()
        if self.account_move:
            return self.account_move._get_pos_conventional_verifactu_receipt_values()
        if not self.l10n_es_edi_verifactu_required:
            return {}
        is_simplified = (
            not self.refunded_order_id
            or self.l10n_es_edi_verifactu_refund_reason == "R5"
        )
        return build_verifactu_receipt_values(
            self.l10n_es_edi_verifactu_get_invoice_name(),
            is_simplified,
            self.l10n_es_edi_verifactu_qr_code,
        )
