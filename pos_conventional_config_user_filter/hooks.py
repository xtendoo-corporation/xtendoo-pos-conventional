# El core de point_of_sale define varias reglas ir.rule para el grupo POS
# User que muestran cualquier registro contable ligado a CUALQUIER caja
# (facturas, líneas de factura, líneas de extracto bancario). Todas viven en
# point_of_sale/security/point_of_sale_security.xml dentro de un bloque
# <data noupdate="1">, así que:
#   - No pueden acotarse añadiendo una regla nueva para ese mismo grupo: las
#     reglas de un mismo grupo se combinan con OR (nunca con AND), y la
#     regla del core, más permisiva, seguiría ganando.
#   - No pueden sobrescribirse por XML reutilizando su external id, al ser
#     noupdate=True.
# La única forma de acotarlas es sobrescribir su domain_force por ORM. Se
# hace en ResUsers._register_hook() (se autoaplica en cada carga del
# registro: arranque o -u) y se revierte en uninstall_hook.
POS_USER_CORE_RULES = {
    "point_of_sale.rule_invoice_pos_user": {
        "core": "[('pos_order_ids', '!=', False)]",
        "restricted": (
            "[('pos_order_ids', '!=', False), "
            "('pos_order_ids.config_id', 'in', user.allowed_pos_config_ids.ids)]"
        ),
    },
    "point_of_sale.rule_invoice_line_pos_user": {
        "core": "[('move_id.pos_order_ids', '!=', False)]",
        "restricted": (
            "[('move_id.pos_order_ids', '!=', False), "
            "('move_id.pos_order_ids.config_id', 'in', user.allowed_pos_config_ids.ids)]"
        ),
    },
    "point_of_sale.rule_pos_bank_statement_line_user": {
        "core": "[('pos_session_id', '!=', False)]",
        "restricted": (
            "[('pos_session_id', '!=', False), "
            "('pos_session_id.config_id', 'in', user.allowed_pos_config_ids.ids)]"
        ),
    },
}


def uninstall_hook(env):
    """Restaura el domain_force original de las reglas del core al desinstalar.

    Es imprescindible: los dominios restringidos referencian
    user.allowed_pos_config_ids, campo definido por este módulo. Si no se
    revierten, esas reglas del core romperían para todo usuario POS tras
    desinstalar (el campo ya no existiría en res.users).
    """
    for xmlid, domains in POS_USER_CORE_RULES.items():
        rule = env.ref(xmlid, raise_if_not_found=False)
        if rule:
            rule.sudo().write({"domain_force": domains["core"]})
