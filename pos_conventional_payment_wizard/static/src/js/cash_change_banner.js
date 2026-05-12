/** @odoo-module **/

/**
 * CashChangeBanner — view widget shown on the new POS order form after closing
 * the previous sale.
 *
 * The summary is stored in sessionStorage by `pos_new_order_action.js` when the
 * `pos_conventional_new_order` action is dispatched. The banner stays visible until:
 *   - The cashier adds the first product line (auto-dismiss), or
 *   - The cashier clicks the dismiss button.
 */

import { registry } from "@web/core/registry";
import { Component, useEffect, useRef, useState, onMounted, onWillPatch, onWillUnmount } from "@odoo/owl";

const STORAGE_KEY_PREVIOUS_TOTAL = "pos_conventional_previous_sale_total";
const STORAGE_KEY_PREVIOUS_CHANGE = "pos_conventional_previous_sale_change";
const STORAGE_KEY_PREVIOUS_CURRENCY = "pos_conventional_previous_sale_currency";
const STORAGE_KEY_PREVIOUS_IS_CASH = "pos_conventional_previous_sale_is_cash";
const LEGACY_STORAGE_KEY_CHANGE = "pos_conventional_cash_change";
const LEGACY_STORAGE_KEY_CURRENCY = "pos_conventional_cash_change_currency";

export class CashChangeBanner extends Component {
    static template = "pos_conventional_payment_wizard.CashChangeBanner";
    static props = {
        record: { type: Object, optional: true },
        readonly: { type: Boolean, optional: true },
        name: { type: String, optional: true },
    };

    setup() {
        this.rootRef = useRef("bannerRoot");
        this._formObserver = null;
        this.state = useState({
            previousTotal: this._readAmount(STORAGE_KEY_PREVIOUS_TOTAL, null),
            changeAmount: this._readChangeAmount(),
            currencySymbol: this._readCurrencySymbol(),
            isCash: this._readIsCash(),
            dismissed: false,
        });

        const dismissIfLinesExist = () => this._dismissIfLinesExist();

        // Check on initial mount (edge case: form opened with lines already present)
        onMounted(() => {
            dismissIfLinesExist();
            this._observeFormChanges();
        });

        // Check before each re-render so we react as soon as the first line is added
        onWillPatch(dismissIfLinesExist);

        onWillUnmount(() => this._disconnectFormObserver());

        // React also to model updates because adding the first order line may update
        // the x2many value without forcing this widget to patch immediately.
        useEffect(
            (bus) => {
                if (!bus) {
                    return;
                }
                const listener = dismissIfLinesExist.bind(this);
                bus.addEventListener("update", listener);
                return () => bus.removeEventListener("update", listener);
            },
            () => [this.props.record?.model?.bus]
        );
    }

    _readAmount(storageKey, fallbackValue = 0.0) {
        try {
            const val = sessionStorage.getItem(storageKey);
            if (val === null || val === "") {
                return fallbackValue;
            }
            const parsed = parseFloat(val);
            return Number.isFinite(parsed) ? parsed : fallbackValue;
        } catch (e) {
            return fallbackValue;
        }
    }

    _readChangeAmount() {
        return this._readAmount(
            STORAGE_KEY_PREVIOUS_CHANGE,
            this._readAmount(LEGACY_STORAGE_KEY_CHANGE, 0.0)
        );
    }

    _readCurrencySymbol() {
        try {
            return (
                sessionStorage.getItem(STORAGE_KEY_PREVIOUS_CURRENCY) ||
                sessionStorage.getItem(LEGACY_STORAGE_KEY_CURRENCY) ||
                "€"
            );
        } catch (e) {
            return "€";
        }
    }

    _readIsCash() {
        try {
            return sessionStorage.getItem(STORAGE_KEY_PREVIOUS_IS_CASH) === "1";
        } catch (e) {
            return false;
        }
    }

    _getLineCount() {
        const lines = this.props.record?.data?.lines;
        if (!lines) return 0;
        if (this.props.record?.data?.has_order_lines) {
            return 1;
        }
        if (typeof lines.count === "number") return lines.count;
        if (Array.isArray(lines.records)) return lines.records.length;
        if (Array.isArray(lines.currentIds)) return lines.currentIds.length;
        if (Array.isArray(lines.resIds)) return lines.resIds.length;
        return 0;
    }

    _getRenderedLineCount() {
        const bannerEl = this.rootRef.el;
        const formEl = bannerEl?.closest(".o_form_view") || bannerEl?.closest(".o_content");
        if (!formEl) {
            return 0;
        }

        const lineRows = formEl.querySelectorAll(
            '.o_field_x2many[name="lines"] tr.o_data_row[data-id], [name="lines"] tr.o_data_row[data-id]'
        );
        return lineRows.length;
    }


    _dismissIfLinesExist() {
        if (this.state.dismissed || !this.hasSummary) {
            return;
        }
        if (this._getLineCount() > 0 || this._getRenderedLineCount() > 0) {
            this._clearStorage();
            this.state.dismissed = true;
        }
    }

    _observeFormChanges() {
        this._disconnectFormObserver();

        const bannerEl = this.rootRef.el;
        const formEl = bannerEl?.closest(".o_form_view") || bannerEl?.closest(".o_content");
        if (!formEl || typeof MutationObserver === "undefined") {
            return;
        }

        this._formObserver = new MutationObserver(() => this._dismissIfLinesExist());
        this._formObserver.observe(formEl, {
            childList: true,
            subtree: true,
        });
    }

    _disconnectFormObserver() {
        this._formObserver?.disconnect();
        this._formObserver = null;
    }

    _clearStorage() {
        try {
            sessionStorage.removeItem(STORAGE_KEY_PREVIOUS_TOTAL);
            sessionStorage.removeItem(STORAGE_KEY_PREVIOUS_CHANGE);
            sessionStorage.removeItem(STORAGE_KEY_PREVIOUS_CURRENCY);
            sessionStorage.removeItem(STORAGE_KEY_PREVIOUS_IS_CASH);
            sessionStorage.removeItem(LEGACY_STORAGE_KEY_CHANGE);
            sessionStorage.removeItem(LEGACY_STORAGE_KEY_CURRENCY);
        } catch (e) {
            // silent
        }
    }

    get hasSummary() {
        return this.state.previousTotal !== null || this.state.changeAmount > 0.005;
    }

    get visible() {
        return !this.state.dismissed && this.hasSummary && this.state.isCash;
    }

    get formattedTotal() {
        return this.state.previousTotal !== null
            ? this.state.previousTotal.toFixed(2)
            : null;
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
    extractProps: ({ record }) => ({ record }),
});

