# Copyright 2024 Xtendoo
# License LGPL-3
from odoo import fields, models


class PosSession(models.Model):
    _inherit = "pos.session"

    last_cash_change = fields.Monetary(
        string="Último cambio en efectivo",
        default=0.0,
        help=(
            "Importe del cambio devuelto en la última operación de caja. "
            "Se muestra como banner informativo en el formulario del siguiente "
            "pedido y desaparece en cuanto se añade la primera línea de venta."
        ),
    )

