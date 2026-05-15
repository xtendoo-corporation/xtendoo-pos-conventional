/** @odoo-module **/

import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { useService } from "@web/core/utils/hooks";
import { Component, useState, onWillStart, onWillUpdateProps } from "@odoo/owl";
import {
    loadPaymentMethods,
    payOrderWithMethod,
} from "@pos_conventional_core/js/pos_order_workflow_utils";

export class PosPaymentButtons extends Component {
    static template = "pos_conventional_payment_wizard.PosPaymentButtons";
    static props = { ...standardFieldProps };

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
        const fieldData = props.record.data[props.name];
        this.state.methods = await loadPaymentMethods(this.orm, fieldData);
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

registry.category("fields").add("pos_payment_buttons", {
    component: PosPaymentButtons,
    supportedTypes: ["many2many"],
});
