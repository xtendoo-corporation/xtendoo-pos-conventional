from odoo import fields, models


class PosConfig(models.Model):
    _inherit = "pos.config"

    pos_print_receipt_with_qztray = fields.Boolean(
        string="Imprimir tickets con QZ Tray",
        help=(
            "Cuando la impresión automática está activa, envía el ticket de POS "
            "Conventional a la impresora configurada con QZ Tray. Si falla, el "
            "cliente web vuelve al flujo de impresión del navegador."
        ),
    )
    pos_qztray_paper_width_mm = fields.Float(
        string="Ancho de ticket QZ Tray (mm)",
        default=80.0,
        help=(
            "Ancho del papel enviado a QZ Tray. Si el ticket sale demasiado pequeño, "
            "normalmente el driver está usando A4/Letter y hay que indicar aquí el "
            "ancho real del rollo."
        ),
    )
    pos_qztray_rasterize_pdf = fields.Boolean(
        string="Rasterizar PDF en QZ Tray",
        default=True,
        help=(
            "Convierte el PDF a imagen antes de enviarlo a la impresora. Suele evitar "
            "problemas de escala en impresoras térmicas."
        ),
    )

    def _get_pos_qztray_print_options(self):
        self.ensure_one()
        options = {
            "units": "mm",
            "margins": 0,
            "scaleContent": True,
        }
        if self.pos_qztray_paper_width_mm:
            options["size"] = {"width": self.pos_qztray_paper_width_mm}
        if self.pos_qztray_rasterize_pdf:
            options["rasterize"] = True
        return options
