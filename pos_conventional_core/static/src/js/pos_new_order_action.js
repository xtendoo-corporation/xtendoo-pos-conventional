/** @odoo-module **/

import { registry } from "@web/core/registry";

/**
 * Acción de cliente para nuevo pedido en POS Conventional.
 * Cierra el pedido actual y navega directamente a un nuevo pedido vacío.
 */
async function posConventionalNewOrder(env, action) {
    const actionService = env.services.action;
    const context = action.params || {};

    console.log("[NEW_ORDER] posConventionalNewOrder called, params:", context);

    // If the previous payment was cash with change, store it in sessionStorage so the
    // order form can display a prominent banner reminding the cashier how much to return.
    const cashChange = parseFloat(context.cash_change || 0);
    if (cashChange > 0.005) {
        try {
            sessionStorage.setItem("pos_conventional_cash_change", cashChange.toFixed(2));
            sessionStorage.setItem(
                "pos_conventional_cash_change_currency",
                context.cash_change_currency || "€"
            );
        } catch (e) {
            // sessionStorage may not be available (private browsing, etc.)
        }
    }

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
