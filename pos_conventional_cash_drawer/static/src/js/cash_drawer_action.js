/** @odoo-module **/

import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { sendCashDrawerRequest } from "@xtendoo_cash_drawer/js/cash_drawer_utils";

registry.category("actions").add(
    "pos_conventional_cash_drawer_open_and_continue",
    async (env, action) => {
        const params = action.params || {};
        const nextAction = params.next_action || false;
        const bridgeUrl = params.bridge_url || "";

        if (bridgeUrl) {
            Promise.resolve(
                sendCashDrawerRequest({
                    cash_drawer_bridge_url: bridgeUrl,
                    cash_drawer_printer_name: params.printer_name || "",
                    cash_drawer_api_key: params.api_key || "",
                })
            ).catch((error) => {
                env.services.notification.add(
                    _t("No se pudo abrir el cajón: ") + (error.message || String(error)),
                    { type: "warning", sticky: true }
                );
                console.warn(
                    "[CashDrawer] Error al abrir automáticamente el cajón en POS convencional:",
                    error
                );
            });
        }

        if (nextAction) {
            return env.services.action.doAction(nextAction);
        }

        return false;
    }
);

