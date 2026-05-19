/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { patch } from "@web/core/utils/patch";
import { PosOrderListController } from "@pos_conventional_core/js/pos_order_list_controller";
import { sendCashDrawerRequest } from "@xtendoo_cash_drawer/js/cash_drawer_utils";

function getRelationalId(value) {
    if (!value) {
        return false;
    }
    if (typeof value === "number") {
        return value;
    }
    if (Array.isArray(value)) {
        return value[0] || false;
    }
    if (typeof value === "object") {
        return value.id || value.resId || false;
    }
    return false;
}

patch(PosOrderListController.prototype, {
    async _getCashDrawerConfigForSession(sessionId) {
        if (!sessionId) {
            return false;
        }

        const sessionData = await this.model.orm.read("pos.session", [sessionId], ["config_id"]);
        const configId = getRelationalId(sessionData?.[0]?.config_id);
        if (!configId) {
            return false;
        }

        const configData = await this.model.orm.read("pos.config", [configId], [
            "cash_drawer_bridge_url",
            "cash_drawer_open_url",
            "cash_drawer_printer_name",
            "cash_drawer_api_key",
        ]);
        const config = configData?.[0];
        const bridgeUrl = config?.cash_drawer_bridge_url || config?.cash_drawer_open_url;
        if (!bridgeUrl) {
            return false;
        }

        return {
            cash_drawer_bridge_url: bridgeUrl,
            cash_drawer_open_url: config?.cash_drawer_open_url || "",
            cash_drawer_printer_name: config?.cash_drawer_printer_name || "",
            cash_drawer_api_key: config?.cash_drawer_api_key || "",
        };
    },

    _notifyCashDrawerOpenError(error) {
        const message = _t("No se pudo abrir el cajón: ") + (error?.message || String(error));
        console.warn("[CashDrawer] Error al abrir el cajón desde Entrada/Salida de efectivo:", error);
        return this.actionService.doAction({
            type: "ir.actions.client",
            tag: "display_notification",
            params: {
                message,
                type: "warning",
                sticky: true,
            },
        });
    },

    async onCashInOut() {
        const cashMovePopup = registry.category("pos_conventional_dialogs").get("CashMovePopup", null);
        if (!cashMovePopup) {
            return await super.onCashInOut(...arguments);
        }

        const sessionId = this.currentSessionId || this.activeSessionId;

        Promise.resolve(this._getCashDrawerConfigForSession(sessionId))
            .then((cashDrawerConfig) => {
                if (!cashDrawerConfig) {
                    return false;
                }
                return sendCashDrawerRequest(cashDrawerConfig);
            })
            .catch((error) => this._notifyCashDrawerOpenError(error));

        return await super.onCashInOut(...arguments);
    },
});


