from odoo import fields, models

from ..hooks import RESTRICTED_INVOICE_POS_USER_DOMAIN


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

    def _register_hook(self):
        super()._register_hook()
        # La regla del core point_of_sale.rule_invoice_pos_user (grupo POS
        # User) permite ver cualquier factura generada por cualquier caja.
        # Al compartir grupo con nuestras propias reglas, ir.rule las
        # combina con OR, así que no puede acotarse añadiendo una regla
        # nueva: hay que sobrescribir su domain_force directamente. El
        # registro es noupdate=True (no se puede vía XML), y por eso se
        # aplica aquí, en cada carga del registro (arranque o -u), en vez
        # de solo en la instalación inicial (ver también uninstall_hook).
        rule = self.env.ref(
            "point_of_sale.rule_invoice_pos_user", raise_if_not_found=False
        )
        if rule and rule.domain_force != RESTRICTED_INVOICE_POS_USER_DOMAIN:
            rule.sudo().write({"domain_force": RESTRICTED_INVOICE_POS_USER_DOMAIN})

    def _has_limited_pos_config_access(self):
        self.ensure_one()
        # Los administradores globales nunca tienen acceso limitado
        if self.has_group("base.group_system"):
            return False
        # Si tiene cajas permitidas asignadas, está limitado
        if self.allowed_pos_config_ids:
            return True
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
