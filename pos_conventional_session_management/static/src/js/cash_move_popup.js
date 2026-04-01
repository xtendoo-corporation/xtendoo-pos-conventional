/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";
import { Component, useState, onWillStart, onMounted } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { registry } from "@web/core/registry";
import { standardActionServiceProps } from "@web/webclient/actions/action_service";

export class CashMovePopup extends Component {
    static template = "pos_conventional_session_management.CashMovePopup";
    static components = { Dialog };
    static props = {
        close: { type: Function },
        sessionId: { type: Number },
    };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.action = useService("action");

        this.state = useState({
            type: "out",
            amount: "",
            reason: "",
            loading: false,
            currencySymbol: "€",
            currencyPosition: "after",
            cashSalesTotal: 0,
            cashSalesTotalFormatted: "",
        });

        onWillStart(async () => {
            await this.loadCurrencyInfo();
        });
    }

    async loadCurrencyInfo() {
        try {
            const sessionData = await this.orm.read("pos.session", [this.props.sessionId], ["currency_id"]);
            if (sessionData.length > 0 && sessionData[0].currency_id) {
                const currencyId = sessionData[0].currency_id[0];
                const currencyData = await this.orm.read("res.currency", [currencyId], ["symbol", "position"]);
                if (currencyData.length > 0) {
                    this.state.currencySymbol = currencyData[0].symbol || "€";
                    this.state.currencyPosition = currencyData[0].position || "after";
                }
            }
        } catch (error) {
            console.error("Error loading currency info:", error);
        }
        try {
            const closingData = await this.orm.call("pos.session", "get_closing_control_data", [this.props.sessionId]);
            const cashDetails = closingData.default_cash_details;
            if (cashDetails) {
                this.state.cashSalesTotal = cashDetails.amount || 0;
                this.state.cashSalesTotalFormatted = this.formatCurrency(this.state.cashSalesTotal);
            }
        } catch (error) {
            console.error("Error loading cash sales total:", error);
        }
    }

    pasteCashSalesTotal() {
        if (this.state.cashSalesTotal > 0) {
            this.state.amount = this.state.cashSalesTotal.toFixed(2).replace(".", ",");
        }
    }

    parseFloat(value) {
        if (typeof value === "number") return value;
        return parseFloat(String(value).replace(",", ".")) || 0;
    }

    formatCurrency(amount) {
        const num = this.parseFloat(amount);
        const formatted = num.toFixed(2).replace(".", ",");
        if (this.state.currencyPosition === "before") return `${this.state.currencySymbol} ${formatted}`;
        return `${formatted} ${this.state.currencySymbol}`;
    }

    isValidFloat(value) {
        if (!value || value === "") return false;
        const parsed = this.parseFloat(value);
        return !isNaN(parsed) && parsed > 0;
    }

    isValidCashMove() {
        return this.isValidFloat(this.state.amount) && this.state.reason.trim() !== "";
    }

    onClickButton(type) {
        this.state.type = type;
    }

    async confirm() {
        if (!this.isValidCashMove()) {
            this.notification.add(_t("Por favor, introduce un importe válido y un motivo."), { type: "warning" });
            return;
        }

        this.state.loading = true;
        try {
            const amount = this.parseFloat(this.state.amount);
            const formattedAmount = this.formatCurrency(amount);
            const type = this.state.type;
            const reason = this.state.reason.trim();

            await this.orm.call("pos.session", "try_cash_in_out", [
                [this.props.sessionId],
                type,
                amount,
                reason,
                false,
                { formattedAmount, translatedType: type === "in" ? _t("in") : _t("out") },
            ]);

            this.notification.add(_t("Movimiento de efectivo registrado: %s %s", type === "in" ? "Entrada" : "Salida", formattedAmount), { type: "success" });
            this.props.close();
        } catch (error) {
            console.error("Error en movimiento de efectivo:", error);
            this.notification.add(_t("Error al registrar el movimiento: ") + (error.message || error.data?.message || "Error desconocido"), { type: "danger" });
        } finally {
            this.state.loading = false;
        }
    }
}

class CashMovePopupAction extends Component {
    static template = "pos_conventional_session_management.CashMovePopupAction";
    static props = { ...standardActionServiceProps };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.dialog = useService("dialog");
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

            const removeDialog = this.dialog.add(CashMovePopup, {
                sessionId: sessionId,
                close: () => { removeDialog(); },
            });
        } catch (error) {
            console.error("Error opening cash move popup:", error);
            this.notification.add(_t("Error al abrir el popup"), { type: "danger" });
        }
    }
}

registry.category("actions").add("pos_conventional_cash_move_popup", CashMovePopupAction);
registry.category("pos_conventional_dialogs").add("CashMovePopup", CashMovePopup);
