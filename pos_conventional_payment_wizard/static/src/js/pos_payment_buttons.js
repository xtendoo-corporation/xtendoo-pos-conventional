/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, useState, onWillStart, onWillUpdateProps } from "@odoo/owl";
import {
    loadPaymentMethods,
    payOrderWithMethod,
} from "@pos_conventional_core/js/pos_order_workflow_utils";

export class PosFastPaymentButtons extends Component {
    static template = "pos_conventional_payment_wizard.PosFastPaymentButtons";
    static props = {
        record: { type: Object },
        readonly: { type: Boolean, optional: true },
        name: { type: String, optional: true },
        methodsField: { type: String, optional: true },
    };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.state = useState({
            methods: [],
        });

        onWillStart(async () => {
            await this.updateMethods(this.props);
        });

        onWillUpdateProps(async (nextProps) => {
            await this.updateMethods(nextProps);
        });
    }

    async updateMethods(props) {
        const fieldData = props.record?.data?.[this.getMethodsFieldName(props)];
        if (!fieldData) {
            this.state.methods = [];
            return;
        }
        this.state.methods = await loadPaymentMethods(this.orm, fieldData);
    }

    getMethodsFieldName(props = this.props) {
        return props.methodsField || props.name;
    }

    get paymentMethods() {
        return this.state.methods;
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
}

registry.category("view_widgets").add("pos_fast_payment_buttons", {
    component: PosFastPaymentButtons,
    extractProps: ({ attrs }) => ({
        methodsField: attrs.methods_field,
    }),
});

registry.category("fields").add("pos_payment_buttons", {
    component: PosFastPaymentButtons,
    supportedTypes: ["many2many"],
});

