from odoo import models


class ResUsers(models.Model):
    _inherit = "res.users"

    def _has_cash_move_permission(self):
        """Allow POS users to make cash moves in addition to managers."""
        return super()._has_cash_move_permission() or self.has_group('point_of_sale.group_pos_user')

    def _has_cash_delete_permission(self):
        """Allow POS users to delete cash moves in addition to managers."""
        return super()._has_cash_delete_permission() or self.has_group('point_of_sale.group_pos_user')
