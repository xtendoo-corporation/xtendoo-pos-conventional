from odoo import models

ESC_POS_ALIGN_CENTER = "\x1ba\x01"
ESC_POS_ALIGN_LEFT = "\x1ba\x00"
ESC_POS_BOLD_ON = "\x1bE\x01"
ESC_POS_BOLD_OFF = "\x1bE\x00"
# The QZ Tray raw job is encoded as CP858 (see pos_receipt_qztray_patch.js),
# so binary ESC/POS bytes must be expressed as their CP858 characters.
QZTRAY_RAW_ENCODING = "cp858"
QR_MODULE_SIZE = 6
QR_ERROR_CORRECTION_M = 49


class PosOrder(models.Model):
    _inherit = "pos.order"

    def _qztray_receipt_qr_command(self, value):
        """ESC/POS ``GS ( k`` sequence that prints ``value`` as a QR code."""
        data = value.encode("ascii")
        store_length = len(data) + 3
        command = b"".join(
            [
                b"\x1d(k\x04\x001A2\x00",
                b"\x1d(k\x03\x001C" + bytes([QR_MODULE_SIZE]),
                b"\x1d(k\x03\x001E" + bytes([QR_ERROR_CORRECTION_M]),
                b"\x1d(k" + store_length.to_bytes(2, "little") + b"1P0" + data,
                b"\x1d(k\x03\x001Q0",
            ]
        )
        return command.decode(QZTRAY_RAW_ENCODING)

    def _get_pos_conventional_qztray_raw_receipt_before_footer(self, width):
        lines = super()._get_pos_conventional_qztray_raw_receipt_before_footer(width)
        verifactu = self._get_pos_conventional_verifactu_receipt_values()
        if not verifactu or not verifactu["qr_value"]:
            return lines
        label = "Factura simplificada" if verifactu["is_simplified"] else "Factura"
        invoice_lines = self._qztray_receipt_wrap(
            f"{label}: {verifactu['invoice_name']}", width
        )
        return lines + [
            ESC_POS_ALIGN_CENTER + invoice_lines[0],
            *invoice_lines[1:],
            f"{ESC_POS_BOLD_ON}QR tributario:{ESC_POS_BOLD_OFF}",
            self._qztray_receipt_qr_command(verifactu["qr_value"]),
            f"{ESC_POS_BOLD_ON}VERI*FACTU{ESC_POS_BOLD_OFF}",
            ESC_POS_ALIGN_LEFT + self._qztray_receipt_indent(["-" * width])[0],
        ]
