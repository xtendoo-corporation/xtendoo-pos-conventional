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

    pos_print_original_receipt_with_qztray = fields.Boolean(
        string="Imprimir el ticket original en lugar del rápido",
        help=(
            "Cuando QZ Tray está activo, imprime el informe original del ticket "
            "en vez del ticket rápido enviado a la ticketera."
        ),
    )
