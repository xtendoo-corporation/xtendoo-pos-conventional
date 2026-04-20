/** @odoo-module **/

import { registry } from "@web/core/registry";

const STORAGE_KEY_PREVIOUS_TOTAL = "pos_conventional_previous_sale_total";
const STORAGE_KEY_PREVIOUS_CHANGE = "pos_conventional_previous_sale_change";
const STORAGE_KEY_PREVIOUS_CURRENCY = "pos_conventional_previous_sale_currency";
const LEGACY_STORAGE_KEY_CHANGE = "pos_conventional_cash_change";
const LEGACY_STORAGE_KEY_CURRENCY = "pos_conventional_cash_change_currency";

/**
 * Acción de cliente para nuevo pedido en POS Conventional.
 * Cierra el pedido actual y navega directamente a un nuevo pedido vacío.
 */
async function posConventionalNewOrder(env, action) {
    const actionService = env.services.action;
    const context = action.params || {};

    console.log("[NEW_ORDER] posConventionalNewOrder called, params:", context);

    _storePreviousSaleSummary(context);

    await _navigateToNewOrder(actionService, context);
}

function _storePreviousSaleSummary(context) {
    const previousSaleTotal = Number.parseFloat(context.previous_sale_total);
    const previousSaleChange = Number.parseFloat(
        context.previous_sale_change ?? context.cash_change ?? 0
    );
    const currencySymbol =
        context.previous_sale_currency || context.cash_change_currency || "€";
    const hasPreviousSaleSummary =
        Number.isFinite(previousSaleTotal) || Number.isFinite(previousSaleChange);

    try {
        if (!hasPreviousSaleSummary) {
            _clearPreviousSaleSummary();
            return;
        }

        if (Number.isFinite(previousSaleTotal)) {
            sessionStorage.setItem(
                STORAGE_KEY_PREVIOUS_TOTAL,
                previousSaleTotal.toFixed(2)
            );
        } else {
            sessionStorage.removeItem(STORAGE_KEY_PREVIOUS_TOTAL);
        }

        const safeChange = Number.isFinite(previousSaleChange) ? previousSaleChange : 0;
        sessionStorage.setItem(STORAGE_KEY_PREVIOUS_CHANGE, safeChange.toFixed(2));
        sessionStorage.setItem(STORAGE_KEY_PREVIOUS_CURRENCY, currencySymbol);

        if (safeChange > 0.005) {
            sessionStorage.setItem(LEGACY_STORAGE_KEY_CHANGE, safeChange.toFixed(2));
            sessionStorage.setItem(LEGACY_STORAGE_KEY_CURRENCY, currencySymbol);
        } else {
            sessionStorage.removeItem(LEGACY_STORAGE_KEY_CHANGE);
            sessionStorage.removeItem(LEGACY_STORAGE_KEY_CURRENCY);
        }
    } catch (e) {
        // sessionStorage may not be available (private browsing, etc.)
    }
}

function _clearPreviousSaleSummary() {
    sessionStorage.removeItem(STORAGE_KEY_PREVIOUS_TOTAL);
    sessionStorage.removeItem(STORAGE_KEY_PREVIOUS_CHANGE);
    sessionStorage.removeItem(STORAGE_KEY_PREVIOUS_CURRENCY);
    sessionStorage.removeItem(LEGACY_STORAGE_KEY_CHANGE);
    sessionStorage.removeItem(LEGACY_STORAGE_KEY_CURRENCY);
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
