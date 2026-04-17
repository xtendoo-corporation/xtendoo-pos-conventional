/** @odoo-module **/

import { Dialog } from "@web/core/dialog/dialog";
import { Component, useState, onWillStart, onMounted, useRef } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { standardActionServiceProps } from "@web/webclient/actions/action_service";
import { CashMovePopup } from "./cash_move_popup";

class PaymentMethodBreakdown extends Component {
    static template = "pos_conventional_session_management.PaymentMethodBreakdown";
    static props = {
        title: { type: String, optional: true },
        total_amount: { type: Number },
        transactions: { type: Array },
        currencyId: { type: Number, optional: true },
        currencyName: { type: String, optional: true },
    };

    setup() {
        this.state = useState({ open: false });
    }

    toggle() {
        this.state.open = !this.state.open;
    }

    formatCurrency(amount) {
        const iso = this.props.currencyName || "EUR";
        return new Intl.NumberFormat("es-ES", {
            style: "currency",
            currency: iso,
        }).format(amount);
    }
}

export class ClosingPopup extends Component {
    static template = "pos_conventional_session_management.ClosingPopup";
    static components = { Dialog, PaymentMethodBreakdown };
    static props = {
        close: { type: Function },
        sessionId: { type: Number },
        onSuccess: { type: Function, optional: true },
    };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.dialog = useService("dialog");
        this.cashCountInput = useRef("cashCountInput");

        this.state = useState({
            loading: true,
            notes: "",
            payments: {},
            sessionData: null,
            sessionName: "",
            ordersDetails: { quantity: 0, amount: 0 },
            cashDetails: null,
            paymentMethods: [],
            cashMoves: [],
            currencyId: null,
            currencyName: "EUR",
            currencySymbol: "€",
        });

        onWillStart(async () => {
            await this.loadClosingData();
        });

        onMounted(() => {
            this.focusCashCountInput();
        });
    }

    async loadClosingData() {
        // Guardar inputs previos del usuario para no perderlos al refrescar
        const previousPayments = { ...this.state.payments };

        try {
            const sessionId = this.props.sessionId;
            const [data, sessionInfo] = await Promise.all([
                this.orm.call("pos.session", "get_closing_control_data_non_touch", [sessionId]),
                this.orm.read("pos.session", [sessionId], ["name", "currency_id"]),
            ]);
            const currencyId = sessionInfo?.[0]?.currency_id?.[0];
            let currencySymbol = "€";
            if (currencyId) {
                const currencyInfo = await this.orm.read("res.currency", [currencyId], ["symbol"]);
                currencySymbol = currencyInfo?.[0]?.symbol || "€";
            }

            this.state.sessionData = data;
            this.state.sessionName = sessionInfo?.[0]?.name || "";
            this.state.ordersDetails = data.orders_details || { quantity: 0, amount: 0 };
            this.state.cashDetails = data.default_cash_details || null;
            this.state.paymentMethods = data.non_cash_payment_methods || [];
            this.state.cashMoves = data.default_cash_details?.moves || [];
            this.state.currencyId = data.currency_id;
            this.state.currencyName = data.currency_name || "EUR";
            this.state.currencySymbol = currencySymbol;

            if (this.state.cashDetails) {
                const prev = previousPayments[this.state.cashDetails.id];
                this.state.payments[this.state.cashDetails.id] = {
                    counted: prev?.counted !== undefined ? prev.counted : this.formatAmount(0),
                };
            }

            for (const pm of this.state.paymentMethods) {
                if (pm.type === "bank") {
                    const prev = previousPayments[pm.id];
                    this.state.payments[pm.id] = {
                        counted: prev?.counted !== undefined ? prev.counted : this.formatAmount(pm.amount),
                    };
                }
            }
            this.state.loading = false;
            this.focusCashCountInput();
        } catch (error) {
            console.error("Error loading closing data:", error);
            this.notification.add(_t("Error al cargar datos de cierre: ") + error.message, { type: "danger" });
            this.state.loading = false;
        }
    }

    focusCashCountInput() {
        const focusInput = () => {
            const input = this.cashCountInput.el;
            if (input) {
                input.focus();
                input.select();
            }
        };
        if (typeof window !== "undefined" && window.requestAnimationFrame) {
            window.requestAnimationFrame(() => window.requestAnimationFrame(focusInput));
        } else {
            setTimeout(focusInput, 0);
        }
    }

    formatAmount(amount) {
        return amount.toFixed(2).replace(".", ",");
    }

    formatCurrency(amount) {
        if (amount === undefined || amount === null) amount = 0;
        const iso = this.state.currencyName || "EUR";
        return new Intl.NumberFormat("es-ES", {
            style: "currency",
            currency: iso,
        }).format(amount);
    }

    parseFloat(value) {
        if (typeof value === "number") return value;
        return parseFloat(String(value).replace(",", ".")) || 0;
    }

    get cashMoveData() {
        const moves = this.state.cashMoves || [];
        const total = moves.reduce((sum, m) => sum + (m.amount || 0), 0);
        return { moves, total };
    }

    getDifference(paymentId) {
        const payment = this.state.payments[paymentId];
        if (!payment) return 0;
        const counted = this.parseFloat(payment.counted);
        let expectedAmount = 0;
        if (this.state.cashDetails && paymentId === this.state.cashDetails.id) {
            expectedAmount = this.state.cashDetails.amount;
        } else {
            const pm = this.state.paymentMethods.find((p) => p.id === paymentId);
            if (pm) expectedAmount = pm.amount;
        }
        return counted - expectedAmount;
    }

    onCashInputChange(event) {
        const paymentId = this.state.cashDetails?.id;
        if (paymentId) this.state.payments[paymentId].counted = event.target.value;
    }

    pasteCashTotal() {
        if (!this.state.cashDetails) return;
        const amount = this.state.cashDetails.amount || 0;
        this.state.payments[this.state.cashDetails.id].counted = this.formatAmount(amount);
    }

    onPMInputChange(paymentId, event) {
        if (this.state.payments[paymentId]) this.state.payments[paymentId].counted = event.target.value;
    }

    async confirm() {
        try {
            const sessionId = this.props.sessionId;
            let countedCash = 0;
            if (this.state.cashDetails) {
                countedCash = this.parseFloat(this.state.payments[this.state.cashDetails.id]?.counted || "0");
            }

            await this.orm.call("pos.session", "post_closing_cash_details", [sessionId], { counted_cash: countedCash });
            await this.orm.call("pos.session", "update_closing_control_state_session", [sessionId, this.state.notes]);

            const bankPaymentMethodDiffPairs = this.state.paymentMethods
                .filter((pm) => pm.type === "bank")
                .map((pm) => [pm.id, this.getDifference(pm.id)]);

            const result = await this.orm.call("pos.session", "close_session_from_ui", [sessionId, bankPaymentMethodDiffPairs]);

            if (result.successful === false) {
                this.notification.add(result.message || _t("Error al cerrar sesión"), { type: "danger" });
                return;
            }

            this.notification.add(_t("Sesión cerrada correctamente"), { type: "success" });
            if (this.props.onSuccess) await this.props.onSuccess();
            this.props.close();
        } catch (error) {
            console.error("Error closing session:", error);
            this.notification.add(_t("Error al cerrar la sesión: ") + (error.message || error.data?.message || "Error desconocido"), { type: "danger" });
        }
    }

    cancel() {
        this.props.close();
    }

    async cashMove() {
        this.dialog.add(
            CashMovePopup,
            { sessionId: this.props.sessionId },
            { onClose: () => this.loadClosingData() }
        );
    }

    async printDailySales() {
        try {
            await this.action.doAction({
                type: "ir.actions.report",
                report_type: "qweb-pdf",
                report_name: "point_of_sale.report_saledetails",
                report_file: "point_of_sale.report_saledetails",
                context: {
                    active_ids: [this.props.sessionId],
                    active_model: "pos.session",
                },
            });
        } catch (error) {
            console.error("Error generating daily sale report:", error);
            this.notification.add(_t("Error al generar el informe de venta diaria"), { type: "danger" });
        }
    }
}

class ClosingPopupAction extends Component {
    static template = "pos_conventional_session_management.ClosingPopupAction";
    static props = { ...standardActionServiceProps };

    setup() {
        this.dialog = useService("dialog");
        this.action = useService("action");
        this.orm = useService("orm");
        this.notification = useService("notification");

        onMounted(async () => {
            await this.openPopup();
        });
    }

    async openPopup() {
        try {
            const context = this.props.action?.context || {};
            let sessionId = context.session_id || context.default_session_id;

            if (!sessionId) {
                const sessions = await this.orm.searchRead(
                    "pos.session",
                    [["state", "in", ["opened", "closing_control"]], ["config_id.pos_non_touch", "=", true]],
                    ["id", "name"],
                    { limit: 1, order: "id desc" }
                );
                if (sessions.length > 0) sessionId = sessions[0].id;
            }

            if (!sessionId) {
                this.notification.add(_t("No se encontró ninguna sesión POS abierta."), { type: "danger" });
                return;
            }

            const removeDialog = this.dialog.add(ClosingPopup, {
                sessionId: sessionId,
                onSuccess: async () => {
                    await this.action.doAction("point_of_sale.action_pos_config_kanban");
                },
                close: () => { removeDialog(); },
            });
        } catch (error) {
            console.error("Error opening closing popup:", error);
            this.notification.add(_t("Error al abrir el popup de cierre"), { type: "danger" });
        }
    }
}

registry.category("actions").add("pos_conventional_closing_popup", ClosingPopupAction);
registry.category("pos_conventional_dialogs").add("ClosingPopup", ClosingPopup);
