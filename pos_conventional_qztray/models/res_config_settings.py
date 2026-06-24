from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    pos_print_receipt_with_qztray = fields.Boolean(
        related="pos_config_id.pos_print_receipt_with_qztray",
        readonly=False,
        string="Imprimir tickets con QZ Tray",
    )
    pos_qztray_paper_width_mm = fields.Float(
        related="pos_config_id.pos_qztray_paper_width_mm",
        readonly=False,
        string="Ancho de ticket QZ Tray (mm)",
    )
    pos_qztray_rasterize_pdf = fields.Boolean(
        related="pos_config_id.pos_qztray_rasterize_pdf",
        readonly=False,
        string="Rasterizar PDF en QZ Tray",
    )
