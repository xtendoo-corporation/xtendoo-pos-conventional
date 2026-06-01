/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, useState, onWillStart, onWillUpdateProps } from "@odoo/owl";

export class PosFastPaymentButtons extends Component {
    static template = "pos_conventional_payment_wizard.PosActionpadFastPaymentButtons";
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
        if (!fieldData?.currentIds?.length) {
            this.state.methods = [];
            return;
        }
        const ids = fieldData.currentIds;
        const methods = await this.orm.read("pos.payment.method", ids, ["name"]);
        const methodsById = new Map(methods.map((method) => [method.id, method]));
        this.state.methods = ids
            .map((id) => methodsById.get(id))
            .filter(Boolean)
            .map((method) => ({
                id: method.id,
                name: method.name,
            }));
    }

    getMethodsFieldName(props = this.props) {
        return props.methodsField || props.name;
    }

    get paymentMethods() {
        return this.state.methods;
    }

    async fastValidate(paymentMethod) {
        if (!paymentMethod?.id) {
            return;
        }
        await this.onPaymentMethodClick(paymentMethod.id);
    }

    async onPaymentMethodClick(methodId) {
        const saved = await this.props.record.save();
        if (!saved && !this.props.record.resId) {
            return;
        }

        const orderId = this.props.record.resId;
        if (!orderId) {
            return;
        }

        try {
            const actionResult = await this.orm.call(
                "pos.order",
                "action_validate_fast_payment",
                [orderId, methodId]
            );
            if (actionResult) {
                await this.action.doAction(actionResult);
                return;
            }
            await this.props.record.load();
        } catch (error) {
            const message = error?.data?.message || error?.message;
            if (message) {
                this.notification.add(message, {
                    type: "warning",
                    title: "Pago rápido",
                });
            }
            await this.props.record.load();
        }
    }
}

registry.category("view_widgets").add("pos_actionpad_fast_payment_buttons", {
    component: PosFastPaymentButtons,
    extractProps: ({ attrs }) => ({
        methodsField: attrs.methods_field,
    }),
});


