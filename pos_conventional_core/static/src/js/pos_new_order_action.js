/** @odoo-module **/

import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";

/**
 * Acción de cliente para nuevo pedido en POS Conventional.
 * - Si params.ask_new_order=true (pago CARD): muestra diálogo de confirmación
 * - Si no (pago EFECTIVO): navega directamente al nuevo pedido
 */
async function posConventionalNewOrder(env, action) {
    const actionService = env.services.action;
    const dialogService = env.services.dialog;
    const context = action.params || {};

    console.log("[NEW_ORDER] posConventionalNewOrder called, params:", context);

    if (context.ask_new_order) {
        // CARD: preguntar al usuario si quiere crear un nuevo pedido
        // El pedido ya está cobrado; nos quedamos en el formulario actual hasta que el usuario decida.
        console.log("[NEW_ORDER] ask_new_order=true -> showing confirmation dialog");
        return new Promise((resolve) => {
            dialogService.add(ConfirmationDialog, {
                title: _t("Cobro registrado"),
                body: _t("El pago con tarjeta se ha registrado correctamente. ¿Desea crear un nuevo pedido?"),
                confirmLabel: _t("Nuevo Pedido"),
                cancelLabel: _t("Seguir en el pedido"),
                confirm: async () => {
                    console.log("[NEW_ORDER] User confirmed new order (CARD)");
                    await _navigateToNewOrder(actionService, context);
                    resolve();
                },
                cancel: () => {
                    // El usuario quiere quedarse en el pedido actual (ya cobrado).
                    // Simplemente cerramos el diálogo; el formulario se recargará
                    // desde pos_payment_buttons.js tras resolver la promesa.
                    console.log("[NEW_ORDER] User chose to stay on current order (CARD)");
                    resolve();
                },
            });
        });
    }

    // EFECTIVO: navegar directamente al nuevo pedido
    console.log("[NEW_ORDER] Direct new order navigation (CASH flow)");
    await _navigateToNewOrder(actionService, context);
}

async function _navigateToNewOrder(actionService, context) {
    console.log("[NEW_ORDER] _navigateToNewOrder called, context:", context);

    // Ir a la lista primero (limpia breadcrumbs)
    await actionService.doAction("point_of_sale.action_pos_pos_form", {
        clearBreadcrumbs: true,
        viewType: "list",
        additionalContext: context,
    });

    if (context.force_login_after_order) {
        console.log("[NEW_ORDER] force_login_after_order=true -> PIN wizard");
        await actionService.doAction({
            type: "ir.actions.act_window",
            res_model: "pos.session.pin.wizard",
            view_mode: "form",
            views: [[false, "form"]],
            target: "new",
            context: {
                default_session_id: context.default_session_id,
                force_new_order_flow: true,
                no_cancel: true,
            },
        });
    } else {
        console.log("[NEW_ORDER] Opening new empty order form");
        await actionService.doAction("point_of_sale.action_pos_pos_form", {
            viewType: "form",
            props: { resId: false },
            additionalContext: context,
        });
    }
}

registry.category("actions").add("pos_conventional_new_order", posConventionalNewOrder);
