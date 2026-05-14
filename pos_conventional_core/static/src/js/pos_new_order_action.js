/** @odoo-module **/

import { registry } from "@web/core/registry";

const STORAGE_KEY_PREVIOUS_TOTAL = "pos_conventional_previous_sale_total";
const STORAGE_KEY_PREVIOUS_CHANGE = "pos_conventional_previous_sale_change";
const STORAGE_KEY_PREVIOUS_CURRENCY = "pos_conventional_previous_sale_currency";
const STORAGE_KEY_PREVIOUS_IS_CASH = "pos_conventional_previous_sale_is_cash";
const LEGACY_STORAGE_KEY_CHANGE = "pos_conventional_cash_change";
const LEGACY_STORAGE_KEY_CURRENCY = "pos_conventional_cash_change_currency";

/**
 * Acción de cliente para nuevo pedido en POS Conventional.
 * Cierra el pedido actual y navega directamente a un nuevo pedido vacío.
 */
async function posConventionalNewOrder(env, action) {
    const actionService = env.services.action;
    const orm = env.services.orm;
    const context = action.params || {};

    console.log("[NEW_ORDER] posConventionalNewOrder called, params:", context);

    _storePreviousSaleSummary(context);

    await _navigateToNewOrder(actionService, orm, context);
}

function _storePreviousSaleSummary(context) {
    const previousSaleTotal = Number.parseFloat(context.previous_sale_total);
    const previousSaleChange = Number.parseFloat(
        context.previous_sale_change ?? context.cash_change ?? 0
    );
    const currencySymbol =
        context.previous_sale_currency || context.cash_change_currency || "€";
    const isCash = !!context.previous_sale_is_cash;
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
        sessionStorage.setItem(STORAGE_KEY_PREVIOUS_IS_CASH, isCash ? "1" : "0");

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
    sessionStorage.removeItem(STORAGE_KEY_PREVIOUS_IS_CASH);
    sessionStorage.removeItem(LEGACY_STORAGE_KEY_CHANGE);
    sessionStorage.removeItem(LEGACY_STORAGE_KEY_CURRENCY);
}

async function _getConfigSessionIds(orm, context) {
    const configId = Number.parseInt(context.config_id, 10);
    if (!configId || !orm) {
        return [];
    }

    try {
        const sessions = await orm.searchRead(
            "pos.session",
            [["config_id", "=", configId]],
            ["id"]
        );
        return (sessions || []).map((session) => session.id).filter(Boolean);
    } catch (error) {
        console.warn("[NEW_ORDER] No se pudieron recuperar las sesiones de la caja actual:", error);
        return [];
    }
}

export async function buildPosOrdersListAction(orm, context) {
    const defaultSessionId = Number.parseInt(context.default_session_id, 10) || false;
    const sessionIds = await _getConfigSessionIds(orm, context);
    const domain = sessionIds.length
        ? [["session_id", "in", sessionIds]]
        : defaultSessionId
            ? [["session_id", "=", defaultSessionId]]
            : [];

    return {
        type: "ir.actions.act_window",
        res_model: "pos.order",
        name: "Pedidos",
        target: "main",
        view_mode: "list,form",
        views: [[false, "list"], [false, "form"]],
        domain,
        context: {
            ...context,
            default_session_id: defaultSessionId,
        },
    };
}

async function _navigateToNewOrder(actionService, orm, context) {
    console.log("[NEW_ORDER] _navigateToNewOrder called, context:", context);

    const listAction = await buildPosOrdersListAction(orm, context);

    // Ir a la lista primero (limpia breadcrumbs)
    await actionService.doAction(listAction, {
        clearBreadcrumbs: true,
        viewType: "list",
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
        await actionService.doAction({
            type: "ir.actions.act_window",
            res_model: "pos.order",
            views: [[false, "form"]],
            target: "current",
            context: {
                ...context,
                default_session_id: Number.parseInt(context.default_session_id, 10) || false,
            },
        });
    }
}

registry.category("actions").add("pos_conventional_new_order", posConventionalNewOrder);
