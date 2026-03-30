/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { Component, useState, onWillStart, useExternalListener, xml } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { standardActionServiceProps } from "@web/webclient/actions/action_service";

export class PaymentPopup extends Component {
    static template = "pos_conventional.PaymentPopup";
    static components = { Dialog };
    static props = { close: { type: Function }, orderId: { type: Number }, onSuccess: { type: Function, optional: true } };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.action = useService("action");
        this.state = useState({ orderData: null, payments: [], selectedPaymentId: null, inputBuffer: "", loading: true });

        useExternalListener(window, "keydown", this.handleKeydown.bind(this));
        onWillStart(async () => await this.loadOrderData());
    }

    async loadOrderData() {
        try {
            const data = await this.orm.call("pos.order", "get_payment_popup_data", [this.props.orderId]);
            this.state.orderData = data;
            this.state.payments = data.payments.map(p => ({ ...p }));
            if (this.state.payments.length > 0) this.selectPayment(this.state.payments[this.state.payments.length - 1]);
            this.state.loading = false;
        } catch (e) {
            this.notification.add(_t("Error al cargar datos"), { type: "danger" });
        }
    }

    get amountDue() {
        if (!this.state.orderData) return 0;
        const total = this.state.orderData.amount_total;
        const paid = this.state.payments.reduce((sum, p) => sum + p.amount, 0);
        return parseFloat((total - paid).toFixed(2));
    }

    selectPayment(payment) {
        this.state.selectedPaymentId = payment.id;
        this.state.inputBuffer = payment.amount.toString();
    }

    handleKeydown(ev) {
        if (this.state.loading) return;
        if (["INPUT", "TEXTAREA"].includes(ev.target.tagName)) return;
        if (/^[0-9,.]$/.test(ev.key)) {
            this.handleInput(ev.key.replace(".", ","));
            ev.preventDefault();
        } else if (ev.key === "Backspace") {
            this.handleBackspace();
            ev.preventDefault();
        } else if (ev.key === "Enter") {
            this.validate();
            ev.preventDefault();
        }
    }

    handleInput(char) {
        if (!this.state.selectedPaymentId) return;
        if (char === "," && this.state.inputBuffer.includes(",")) return;
        this.state.inputBuffer += char;
        this.updatePayment();
    }

    handleBackspace() {
        if (this.state.inputBuffer.length > 0) {
            this.state.inputBuffer = this.state.inputBuffer.slice(0, -1);
            this.updatePayment();
        }
    }

    updatePayment() {
        const amount = parseFloat(this.state.inputBuffer.replace(",", ".")) || 0;
        const payment = this.state.payments.find(p => p.id === this.state.selectedPaymentId);
        if (payment) payment.amount = amount;
    }

    addPayment(methodId) {
        const method = this.state.orderData.available_methods.find(m => m.id === methodId);
        const newPayment = { id: "new_" + Date.now(), payment_method_id: method.id, payment_method_name: method.name, amount: this.amountDue };
        this.state.payments.push(newPayment);
        this.selectPayment(newPayment);
    }

    async validate() {
        if (this.amountDue > 0.01) {
            this.notification.add(_t("Falta importe por pagar"), { type: "warning" });
            return;
        }
        try {
            const result = await this.orm.call("pos.order", "action_register_payments_and_validate", [this.props.orderId, this.state.payments]);
            if (result.success) {
                this.props.close();
                if (result.action) await this.action.doAction(result.action);
            }
        } catch (e) {
            this.notification.add(_t("Error de validación"), { type: "danger" });
        }
    }
}

class PaymentPopupAction extends Component {
    static template = xml`<Dialog t-if="state.show" title="'Pago'" close="props.close"><PaymentPopup orderId="props.action.context.active_id" close="props.close"/></Dialog>`;
    static components = { Dialog, PaymentPopup };
    static props = { ...standardActionServiceProps };
    setup() { this.state = useState({ show: true }); }
}

registry.category("actions").add("pos_conventional_payment_popup", PaymentPopupAction);
