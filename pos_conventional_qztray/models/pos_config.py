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
