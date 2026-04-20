from odoo import fields, models


class ResUsers(models.Model):
    _inherit = "res.users"

    allowed_pos_config_ids = fields.Many2many(
        'pos.config',
        'res_users_pos_config_rel',
        'user_id',
        'pos_config_id',
        string='Cajas permitidas (POS)',
        help='Cajas (puntos de venta) a las que el usuario puede acceder. Filtrado por las compañías asignadas al usuario.',
    )

    def _has_limited_pos_config_access(self):
        self.ensure_one()
        return self.has_group("point_of_sale.group_pos_user") and not self.has_group(
            "point_of_sale.group_pos_manager"
        )

    def _get_effective_allowed_pos_config_ids(self):
        self.ensure_one()
        allowed_configs = self.sudo().allowed_pos_config_ids.filtered(
            lambda config: config.company_id in self.company_ids
        )
        return allowed_configs.ids

    def _can_access_pos_config(self, pos_config):
        self.ensure_one()
        pos_config = pos_config.sudo().exists()
        if not pos_config:
            return False
        if not self._has_limited_pos_config_access():
            return True
        return pos_config.id in self._get_effective_allowed_pos_config_ids()

