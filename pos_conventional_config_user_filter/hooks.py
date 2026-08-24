CORE_INVOICE_POS_USER_DOMAIN = "[('pos_order_ids', '!=', False)]"

RESTRICTED_INVOICE_POS_USER_DOMAIN = (
    "[('pos_order_ids', '!=', False), "
    "('pos_order_ids.config_id', 'in', user.allowed_pos_config_ids.ids)]"
)


def uninstall_hook(env):
    """Restaura el domain_force original del core al desinstalar el módulo.

    Es imprescindible: el dominio restringido referencia
    user.allowed_pos_config_ids, campo definido por este módulo. Si no se
    revierte, la regla del core rompería para todo usuario POS tras
    desinstalar (el campo ya no existiría en res.users).
    """
    rule = env.ref("point_of_sale.rule_invoice_pos_user", raise_if_not_found=False)
    if rule:
        rule.sudo().write({"domain_force": CORE_INVOICE_POS_USER_DOMAIN})
