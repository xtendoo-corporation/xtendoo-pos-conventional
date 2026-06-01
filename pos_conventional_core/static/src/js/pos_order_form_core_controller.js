/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { formView } from "@web/views/form/form_view";
import { FormController } from "@web/views/form/form_controller";
import { onMounted, onWillUnmount, useSubEnv } from "@odoo/owl";
import {
    activateNavigationBypass,
    getOrderLineRecords,
    getOrderLinesList,
    getRelationalValueId,
    hasRealProductLines,
    playErrorBeep,
    shouldBlockDraftOrderLeave,
} from "@pos_conventional_core/js/pos_order_workflow_utils";

export class PosConventionalOrderFormController extends FormController {
    setup() {
        super.setup();
        useSubEnv({
            config: {
                ...this.env.config,
                beforeLeave: async () => {
                    if (window.bypassPosLeave) {
                        return true;
                    }
                    if (this._shouldBlockLeavingCurrentOrder()) {
                        this._notifyBlockedOrderLeave();
                        return false;
                    }
                    return await this.model.root.save();
                },
            },
        });

        this.notification = useService("notification");
        this.boundCorePaymentButtonClickHandler = this._onPaymentButtonClick.bind(this);
        this.boundCoreDocClickHandler = this._onDocClick.bind(this);

        onMounted(() => {
            document.addEventListener("click", this.boundCorePaymentButtonClickHandler, true);
            document.addEventListener("click", this.boundCoreDocClickHandler, true);
        });

        onWillUnmount(() => {
            document.removeEventListener("click", this.boundCorePaymentButtonClickHandler, true);
            document.removeEventListener("click", this.boundCoreDocClickHandler, true);
        });
    }

    _onDocClick(ev) {
        if (ev.target.closest('button[name="action_open_stock_forecast"]')) {
            activateNavigationBypass(this.model.root, 2000);
        }
    }

    _onPaymentButtonClick(ev) {
        const btn = ev.target.closest(
            'button[name^="action_pay_"], button[name="action_open_payment_popup"], button[name="action_pos_convention_pay_with_method"], button[name="action_cancel_and_delete_order"]'
        );
        const wizardValidateBtn = ev.target.closest(
            '.o_pos_conventional_payment_wizard_form button[name="action_validate"], .o_pos_conventional_payment_wizard_form button[name="action_validate_print"]'
        );
        const targetButton = btn || wizardValidateBtn;
        if (!targetButton) {
            return;
        }

        const record = this.model.root;
        if (wizardValidateBtn) {
            activateNavigationBypass(record);
            return;
        }

        const isCancelButton = targetButton.name === "action_cancel_and_delete_order";
        if (isCancelButton) {
            activateNavigationBypass(record);
            return;
        }

        const amountTotal = record?.data?.amount_total || 0;
        const hasProductLines = hasRealProductLines(record);
        if (!hasProductLines || amountTotal <= 0) {
            ev.preventDefault();
            ev.stopImmediatePropagation();
            playErrorBeep();
            this.notification.add(
                _t("No se puede cobrar un pedido sin productos o con importe cero."),
                { type: "warning", title: _t("Importe inválido"), sticky: false }
            );
            return;
        }

        activateNavigationBypass(record);
    }

    _getOrderLinesList(record) {
        return getOrderLinesList(record);
    }

    _getOrderLineRecords(record = this.model.root) {
        return getOrderLineRecords(record);
    }

    _getRelationalValueId(value) {
        return getRelationalValueId(value);
    }

    _hasProductLines(record = this.model.root) {
        return hasRealProductLines(record);
    }

    _activateNavigationBypass(record = this.model.root, timeout = 10000) {
        activateNavigationBypass(record, timeout);
    }

    _playErrorBeep() {
        playErrorBeep();
    }

    _shouldBlockLeavingCurrentOrder(record = this.model.root) {
        return shouldBlockDraftOrderLeave(record);
    }

    _notifyBlockedOrderLeave() {
        this._playErrorBeep();
        this.notification.add(
            _t(
                "No puedes salir de un pedido con productos sin pago. Por favor, finaliza el pago o cancélalo y elimínalo antes de salir."
            ),
            {
                type: "warning",
                title: _t("Pedido pendiente de pago"),
                sticky: false,
                autocloseDelay: 10000,
            }
        );
    }

    async beforeLeave({ forceLeave } = {}) {
        if (window.bypassPosLeave) {
            return super.beforeLeave(...arguments);
        }

        const record = this.model.root;
        if (!forceLeave && this._shouldBlockLeavingCurrentOrder(record)) {
            this._notifyBlockedOrderLeave();
            return false;
        }

        return super.beforeLeave(...arguments);
    }
}

export const posConventionalOrderFormView = {
    ...formView,
    Controller: PosConventionalOrderFormController,
};

registry.category("views").add("pos_conventional_order_form", posConventionalOrderFormView);

