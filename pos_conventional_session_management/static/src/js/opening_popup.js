/** @odoo-module **/

import { Dialog } from "@web/core/dialog/dialog";
import { Component, useState, onWillStart, useRef, onMounted } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { standardActionServiceProps } from "@web/webclient/actions/action_service";

export class OpeningPopup extends Component {
    static template = "pos_conventional_session_management.OpeningPopup";
    static components = { Dialog };
    static props = {
        close: { type: Function, optional: true },
        sessionId: { type: Number, optional: true },
        configId: { type: Number, optional: true },
        onOpened: { type: Function, optional: true },
        action: { type: Object, optional: true },
        actionId: { type: Number, optional: true },
        updateActionState: { type: Function, optional: true },
    };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.action = useService("action");
        this.openingCashInput = useRef("openingCashInput");
        this.sessionId = this.props.sessionId || this.props.action?.context?.session_id || this.props.action?.params?.session_id;
        this.configId = this.props.configId || this.props.action?.context?.config_id || this.props.action?.params?.config_id;

        this.state = useState({
            loading: true,
            notes: "",
            openingCash: "0,00",
            sessionName: "",
            configName: "",
            currencySymbol: "€",
        });

        onWillStart(async () => await this.loadSessionData());

        onMounted(() => {
            // Seleccionar el valor del campo para que el usuario pueda teclear directamente
            if (this.openingCashInput.el) {
                this.openingCashInput.el.select();
                this.openingCashInput.el.focus();
            }
        });
    }

    async loadSessionData() {
        try {
            const session = await this.orm.read("pos.session", [this.sessionId], ["name", "config_id", "cash_register_balance_start", "currency_id"]);
            if (session.length > 0) {
                this.state.sessionName = session[0].name;
                this.state.openingCash = (session[0].cash_register_balance_start || 0).toFixed(2).replace(".", ",");
                const config = await this.orm.read("pos.config", [session[0].config_id[0]], ["name"]);
                this.state.configName = config[0].name;
                const currency = await this.orm.read("res.currency", [session[0].currency_id[0]], ["symbol"]);
                this.state.currencySymbol = currency[0].symbol || "€";
            }
            this.state.loading = false;
        } catch (e) {
            console.error(e);
            this.state.loading = false;
        }
    }

    async confirm() {
        try {
            const amount = parseFloat(this.state.openingCash.replace(",", ".")) || 0;
            await this.orm.call("pos.session", "set_opening_control", [this.sessionId, amount, this.state.notes]);
            this.notification.add(_t("Caja abierta"), { type: "success" });
            if (this.props.onOpened) this.props.onOpened();
            if (this.props.close) await this.props.close();

            await this.action.doAction("point_of_sale.action_pos_pos_form", {
                viewType: 'list',
                additionalContext: { default_session_id: this.sessionId, default_config_id: this.configId }
            });
        } catch (e) {
            this.notification.add(_t("Error al abrir caja"), { type: "danger" });
        }
    }

    async cancel() {
        if (this.props.close) {
            await this.props.close();
        }
        await this.action.doAction("point_of_sale.action_pos_config_kanban");
    }
}

class OpeningPopupAction extends Component {
    static template = "pos_conventional_session_management.OpeningPopupAction";
    static props = { ...standardActionServiceProps };

    setup() {
        this.dialog = useService("dialog");
        this.notification = useService("notification");
        this.orm = useService("orm");
        this.action = useService("action");

        onMounted(async () => {
            await this.openPopup();
        });
    }

    async openPopup() {
        try {
            const context = this.props.action?.context || {};
            let sessionId = context.session_id || context.default_session_id;
            const configId = context.config_id || context.default_config_id;

            if (!sessionId && configId) {
                const sessions = await this.orm.searchRead(
                    "pos.session",
                    [["config_id", "=", configId], ["state", "=", "opening_control"]],
                    ["id"],
                    { limit: 1, order: "id desc" }
                );
                if (sessions.length > 0) {
                    sessionId = sessions[0].id;
                }
            }

            if (!sessionId) {
                this.notification.add(_t("No se encontró ninguna sesión pendiente de apertura."), { type: "danger" });
                await this.action.doAction("point_of_sale.action_pos_config_kanban");
                return;
            }

            let removeDialog = null;
            removeDialog = this.dialog.add(OpeningPopup, {
                sessionId,
                configId,
                close: async () => {
                    if (removeDialog) {
                        removeDialog();
                    }
                },
            });
        } catch (error) {
            console.error("Error opening opening popup:", error);
            this.notification.add(_t("Error al abrir el popup de apertura"), { type: "danger" });
            await this.action.doAction("point_of_sale.action_pos_config_kanban");
        }
    }
}

registry.category("actions").add("pos_conventional_opening_popup", OpeningPopupAction);
registry.category("pos_conventional_dialogs").add("OpeningPopup", OpeningPopup);
