/** @odoo-module **/

import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { useService } from "@web/core/utils/hooks";
import { Component, useState, onWillStart, onWillUpdateProps } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import {
    loadPaymentMethods,
    payOrderWithMethod,
} from "@pos_conventional_core/js/pos_order_workflow_utils";

export class PosPaymentButtonsCashDrawer extends Component {
    static template = "pos_conventional_cash_drawer.PosPaymentButtonsCashDrawer";
    static props = { ...standardFieldProps };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.state = useState({
            methods: [],
            openingCashDrawer: false,
        });

        onWillStart(async () => {
            await this.updateMethods(this.props);
        });

        onWillUpdateProps(async (nextProps) => {
            await this.updateMethods(nextProps);
        });
    }

    async updateMethods(props) {
        const fieldData = props.record.data[props.name];
        this.state.methods = await loadPaymentMethods(this.orm, fieldData);
    }

    get paymentMethods() {
        return this.state.methods;
    }

    get cashDrawerConfigId() {
        const configValue = this.props.record.data.config_id;
        if (!configValue) {
            return null;
        }
        if (typeof configValue === "number") {
            return configValue;
        }
        if (Array.isArray(configValue)) {
            return configValue[0] || null;
        }
        if (typeof configValue === "object") {
            if (typeof configValue.resId === "number") {
                return configValue.resId;
            }
            if (typeof configValue.id === "number") {
                return configValue.id;
            }
        }
        return null;
    }

    async onPaymentMethodClick(methodId) {
        await payOrderWithMethod({
            record: this.props.record,
            methodId,
            orm: this.orm,
            action: this.action,
            notification: this.notification,
        });
    }

    async onOpenCashDrawerClick() {
        if (this.state.openingCashDrawer) {
            return;
        }

        this.state.openingCashDrawer = true;
        try {
            let action;
            const configId = this.cashDrawerConfigId;
            if (configId) {
                action = await this.orm.call(
                    "pos.config",
                    "action_test_cash_drawer",
                    [[configId]]
                );
            } else if (this.props.record.resId) {
                action = await this.orm.call(
                    "pos.order",
                    "action_open_cash_drawer_from_conventional",
                    [this.props.record.resId]
                );
            } else {
                this.notification.add(
                    _t("No se pudo identificar la configuración del TPV para abrir el cajón."),
                    { type: "warning" }
                );
                return;
            }

            if (action) {
                await this.action.doAction(action);
            }
        } catch (error) {
            this.notification.add(
                _t("Error al abrir el cajón: ") + (error.message || String(error)),
                { type: "danger", sticky: true }
            );
            console.error("[CashDrawer] Error al abrir el cajón desde POS convencional:", error);
        } finally {
            this.state.openingCashDrawer = false;
        }
    }
}

registry.category("fields").add("pos_payment_buttons_cash_drawer", {
    component: PosPaymentButtonsCashDrawer,
    supportedTypes: ["many2many"],
});



