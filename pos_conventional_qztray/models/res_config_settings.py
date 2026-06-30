from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    pos_print_receipt_with_qztray = fields.Boolean(
        related="pos_config_id.pos_print_receipt_with_qztray",
        readonly=False,
        string="Imprimir tickets con QZ Tray",
    )

    pos_print_original_receipt_with_qztray = fields.Boolean(
        related="pos_config_id.pos_print_original_receipt_with_qztray",
        readonly=False,
        string="Imprimir el ticket original en lugar del rápido",
    )
