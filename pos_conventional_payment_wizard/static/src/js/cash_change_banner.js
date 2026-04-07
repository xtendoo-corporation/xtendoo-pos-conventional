/** @odoo-module **/

/**
 * CashChangeBanner — view widget shown on the new POS order form after a cash
 * payment that produced change.
 *
 * The amount is stored in sessionStorage by `pos_new_order_action.js` when the
 * `pos_conventional_new_order` action is dispatched. The banner stays visible
 * until:
 *   - The cashier adds the first product line (auto-dismiss), or
 *   - The cashier clicks the dismiss button.
 */

import { registry } from "@web/core/registry";
import { Component, useState, onMounted, onWillPatch } from "@odoo/owl";

const STORAGE_KEY_AMOUNT = "pos_conventional_cash_change";
const STORAGE_KEY_CURRENCY = "pos_conventional_cash_change_currency";

export class CashChangeBanner extends Component {
    static template = "pos_conventional_payment_wizard.CashChangeBanner";
    static props = {
        record: { type: Object, optional: true },
    };

    setup() {
        this.state = useState({
            changeAmount: this._readChangeAmount(),
            currencySymbol: this._readCurrencySymbol(),
            dismissed: false,
        });

        const dismissIfLinesExist = () => {
            if (this.state.dismissed || this.state.changeAmount <= 0.005) {
                return;
            }
            const lineCount = this._getLineCount();
            if (lineCount > 0) {
                this._clearStorage();
                this.state.dismissed = true;
            }
        };

        // Check on initial mount (edge case: form opened with lines already present)
        onMounted(dismissIfLinesExist);

        // Check before each re-render so we react as soon as the first line is added
        onWillPatch(dismissIfLinesExist);
    }

    _readChangeAmount() {
        try {
            const val = sessionStorage.getItem(STORAGE_KEY_AMOUNT);
            return val ? parseFloat(val) : 0.0;
        } catch (e) {
            return 0.0;
        }
    }

    _readCurrencySymbol() {
        try {
            return sessionStorage.getItem(STORAGE_KEY_CURRENCY) || "€";
        } catch (e) {
            return "€";
        }
    }

    _getLineCount() {
        const lines = this.props.record?.data?.lines;
        if (!lines) return 0;
        if (typeof lines.count === "number") return lines.count;
        if (Array.isArray(lines.records)) return lines.records.length;
        return 0;
    }

    _clearStorage() {
        try {
            sessionStorage.removeItem(STORAGE_KEY_AMOUNT);
            sessionStorage.removeItem(STORAGE_KEY_CURRENCY);
        } catch (e) {
            // silent
        }
    }

    get visible() {
        return !this.state.dismissed && this.state.changeAmount > 0.005;
    }

    get formattedChange() {
        return this.state.changeAmount.toFixed(2);
    }

    onDismiss() {
        this._clearStorage();
        this.state.dismissed = true;
    }
}

registry.category("view_widgets").add("pos_cash_change_banner", {
    component: CashChangeBanner,
    extractProps: ({ attrs, record }) => ({ record }),
});

