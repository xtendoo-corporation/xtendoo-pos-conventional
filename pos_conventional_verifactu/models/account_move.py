from odoo import models

from ..utils import build_verifactu_receipt_values


class AccountMove(models.Model):
    _inherit = "account.move"

    def _get_pos_conventional_verifactu_receipt_values(self):
        """Veri*Factu data printed on the POS Conventional 80mm receipts."""
        self.ensure_one()
        if not self.l10n_es_edi_verifactu_required:
            return {}
        return build_verifactu_receipt_values(
            self.name,
            self.l10n_es_is_simplified,
            self.l10n_es_edi_verifactu_qr_code,
        )
