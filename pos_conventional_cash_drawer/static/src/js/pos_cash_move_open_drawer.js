/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import { CashMovePopup } from "@point_of_sale/app/components/popups/cash_move_popup/cash_move_popup";
import { PosStore } from "@point_of_sale/app/services/pos_store";
import { makeAwaitable } from "@point_of_sale/app/utils/make_awaitable_dialog";
import { sendCashDrawerRequest } from "@xtendoo_cash_drawer/js/cash_drawer_utils";

patch(PosStore.prototype, {
    _getCashDrawerBridgeConfig() {
        const bridgeUrl = this.config?.cash_drawer_bridge_url || this.config?.cash_drawer_open_url;
        if (!bridgeUrl) {
            return false;
        }

        return {
            cash_drawer_bridge_url: bridgeUrl,
            cash_drawer_printer_name: this.config?.cash_drawer_printer_name || "",
            cash_drawer_api_key: this.config?.cash_drawer_api_key || "",
        };
    },

    cashMove() {
        const cashDrawerConfig = this._getCashDrawerBridgeConfig();
        if (cashDrawerConfig) {
            Promise.resolve(sendCashDrawerRequest(cashDrawerConfig)).catch((error) => {
                this.notification?.add(
                    _t("No se pudo abrir el cajón: ") + (error.message || String(error)),
                    { type: "warning" }
                );
                console.warn(
                    "[CashDrawer] Error al abrir el cajón desde Cash In/Out:",
                    error
                );
            });
        } else {
            this.openCashbox(_t("Cash in / out"));
        }

        return makeAwaitable(this.dialog, CashMovePopup);
    },
});

