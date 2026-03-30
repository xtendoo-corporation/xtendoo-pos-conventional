from odoo import api, fields, models, _

class PosOrder(models.Model):
    _inherit = "pos.order"

    # Redundant fields removed, they are in picking_integration
    # This module could be used for other sale-related features if needed.
    pass
