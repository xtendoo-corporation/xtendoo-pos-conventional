/** @odoo-module **/

import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { useService } from "@web/core/utils/hooks";
import { Component, useState, onWillStart, onWillUpdateProps } from "@odoo/owl";

export class PosPaymentButtons extends Component {
    static template = "pos_conventional.PosPaymentButtons";
    static props = { ...standardFieldProps };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({ methods: [] });

        onWillStart(async () => await this.updateMethods(this.props));
        onWillUpdateProps(async (nextProps) => await this.updateMethods(nextProps));
    }

    async updateMethods(props) {
        const fieldData = props.record.data[props.name];
        if (!fieldData?.currentIds?.length) {
            this.state.methods = [];
            return;
        }

        try {
            const methods = await this.orm.read("pos.payment.method", fieldData.currentIds, ["name"]);
            this.state.methods = methods.map(m => ({ id: m.id, name: m.name }));
        } catch (error) {
            console.error("Error reading payment methods:", error);
        }
    }

    async onPaymentMethodClick(methodId) {
        const saved = await this.props.record.save();
        if (!saved && !this.props.record.resId) return;

        const orderId = this.props.record.resId;
        try {
            const action = await this.orm.call("pos.order", "action_pos_convention_pay_with_method", [orderId, methodId]);
            if (action) await this.action.doAction(action);
            else await this.props.record.load();
        } catch (error) {
            console.error("Error processing payment:", error);
        }
    }
}

registry.category("fields").add("pos_payment_buttons", {
    component: PosPaymentButtons,
    supportedTypes: ["many2many"],
});
