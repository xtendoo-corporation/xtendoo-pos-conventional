/** @odoo-module **/

import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { useService } from "@web/core/utils/hooks";
import { Component, useState, onWillStart, onWillUpdateProps } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";

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
        if (!fieldData || !fieldData.currentIds || fieldData.currentIds.length === 0) {
            this.state.methods = [];
            return;
        }

        const ids = fieldData.currentIds;

        try {
            const methods = await this.orm.read("pos.payment.method", ids, ["name"]);
            this.state.methods = methods.map((method) => ({
                id: method.id,
                name: method.name,
            }));
        } catch (error) {
            console.error("Error al leer nombres de métodos de pago:", error);
            this.state.methods = ids.map((id) => ({ id, name: "Metodo " + id }));
        }
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
        const amountTotal = this.props.record.data.amount_total || 0;
        const linesCount = (this.props.record.data.lines && this.props.record.data.lines.currentIds)
            ? this.props.record.data.lines.currentIds.length
            : 0;

        if (linesCount === 0) {
            this._playErrorBeep();
            this.notification.add(
                _t("No se puede cobrar un pedido sin líneas. Añada productos al pedido."),
                { type: "warning", title: _t("Pedido vacío"), sticky: false }
            );
            return;
        }

        if (Math.abs(amountTotal) < 0.00001) {
            this._playErrorBeep();
            this.notification.add(
                _t("No se puede cobrar un pedido con importe cero."),
                { type: "warning", title: _t("Importe inválido"), sticky: false }
            );
            return;
        }

        const saved = await this.props.record.save();
        if (!saved && !this.props.record.resId) {
            return;
        }

        const orderId = this.props.record.resId;
        if (!orderId) {
            console.error("No se pudo obtener el ID del pedido.");
            return;
        }

        try {
            const action = await this.orm.call(
                "pos.order",
                "action_pos_convention_pay_with_method",
                [orderId, methodId]
            );

            if (action) {
                await this.action.doAction(action);
            } else {
                await this.props.record.load();
            }
        } catch (error) {
            console.error("Error al procesar pago:", error);
        }
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

    _playErrorBeep() {
        try {
            const ctx = new (window.AudioContext || window.webkitAudioContext)();
            const oscillator = ctx.createOscillator();
            const gainNode = ctx.createGain();
            oscillator.connect(gainNode);
            gainNode.connect(ctx.destination);
            oscillator.type = "square";
            oscillator.frequency.setValueAtTime(380, ctx.currentTime);
            oscillator.frequency.setValueAtTime(280, ctx.currentTime + 0.15);
            gainNode.gain.setValueAtTime(0.25, ctx.currentTime);
            gainNode.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.35);
            oscillator.start(ctx.currentTime);
            oscillator.stop(ctx.currentTime + 0.35);
        } catch {
            // Fallback silencioso si Web Audio API no está disponible
        }
    }
}

registry.category("fields").add("pos_payment_buttons_cash_drawer", {
    component: PosPaymentButtonsCashDrawer,
    supportedTypes: ["many2many"],
});



