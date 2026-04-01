/** @odoo-module **/

import { ListController } from "@web/views/list/list_controller";
import { registry } from "@web/core/registry";
import { listView } from "@web/views/list/list_view";
import { useState, onWillStart, onWillUnmount } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class PosOrderListController extends ListController {
    setup() {
        super.setup();
        this.dialogService = useService("dialog");
        this.actionService = useService("action");
        this.state = useState({ showCloseButton: false });
        this.activeSessionId = null;

        this.handleBeforeUnload = () => {
            if (this.activeSessionId) {
                sessionStorage.setItem('pos_conventional_active_session_id', this.activeSessionId);
            }
        };

        window.addEventListener('beforeunload', this.handleBeforeUnload);

        onWillStart(async () => {
            await this.checkIfInsideNonTouchSession();
        });

        onWillUnmount(() => {
            window.removeEventListener('beforeunload', this.handleBeforeUnload);
        });
    }

    async openRecord(record, mode) {
        if (record.data.linked_sale_order_id) {
            const saleOrder = record.data.linked_sale_order_id;
            const saleOrderId = Array.isArray(saleOrder) ? saleOrder[0] : (saleOrder.id || saleOrder);
            if (saleOrderId && typeof saleOrderId === 'number') {
                return this.actionService.doAction({
                    type: 'ir.actions.act_window',
                    res_model: 'sale.order',
                    res_id: saleOrderId,
                    views: [[false, 'form']],
                    target: 'current',
                });
            }
        }
        return super.openRecord(record, mode);
    }

    async checkIfInsideNonTouchSession() {
        const context = this.props.context || {};
        let sessionId = context.default_session_id;
        const storedSessionId = sessionStorage.getItem('pos_conventional_active_session_id');
        sessionStorage.removeItem('pos_conventional_active_session_id');

        if (!sessionId && storedSessionId) {
            sessionId = parseInt(storedSessionId);
        }
        this.activeSessionId = sessionId;

        if (!sessionId) {
            this.state.showCloseButton = false;
            return;
        }

        try {
            const sessionData = await this.model.orm.read("pos.session", [sessionId], ["state", "config_id"]);
            if (sessionData?.length > 0 && ['opened', 'opening_control'].includes(sessionData[0].state)) {
                const configId = Array.isArray(sessionData[0].config_id) ? sessionData[0].config_id[0] : sessionData[0].config_id;
                const configData = await this.model.orm.read("pos.config", [configId], ["pos_non_touch", "pos_force_employee_login_after_order"]);
                if (configData?.length > 0) {
                    this.state.showCloseButton = !!configData[0].pos_non_touch;
                    this.forceLogin = configData[0].pos_force_employee_login_after_order;
                    this.currentSessionId = sessionId;
                }
            }
        } catch (error) {
            console.error("Error verifying sesión:", error);
        }
    }

    async createRecord() {
        if (this.forceLogin && this.currentSessionId) {
            return this.actionService.doAction({
                type: 'ir.actions.act_window',
                res_model: 'pos.session.pin.wizard',
                view_mode: 'form',
                views: [[false, 'form']],
                target: 'new',
                context: {
                    default_session_id: this.currentSessionId,
                    force_new_order_flow: true,
                    no_cancel: true,
                }
            });
        }
        super.createRecord();
    }

    async onCloseCashRegister() {
        const ClosingPopup = registry.category("pos_conventional_dialogs").get("ClosingPopup", null);
        const sessionId = this.currentSessionId || this.activeSessionId;
        console.log("[CERRAR CAJA] onCloseCashRegister: sessionId=", sessionId, "ClosingPopup disponible=", !!ClosingPopup);
        if (!ClosingPopup) {
            console.error("[CERRAR CAJA] ClosingPopup no disponible — ¿está instalado pos_conventional_session_management?");
            return;
        }
        if (!sessionId) {
            console.error("[CERRAR CAJA] sessionId no disponible — no se puede abrir el popup de cierre");
            return;
        }
        this.dialogService.add(ClosingPopup, {
            sessionId: sessionId,
            onSuccess: () => this.actionService.doAction("point_of_sale.action_pos_config_kanban"),
            close: () => this.model.load(),
        });
    }

    async onCashInOut() {
        const CashMovePopup = registry.category("pos_conventional_dialogs").get("CashMovePopup", null);
        if (!CashMovePopup) {
            console.warn("[CERRAR CAJA] CashMovePopup no disponible — ¿está instalado pos_conventional_session_management?");
            return;
        }
        const sessionId = this.currentSessionId || this.activeSessionId;
        this.dialogService.add(CashMovePopup, { sessionId: sessionId, close: () => {} });
    }

    get actionMenuItems() {
        const items = super.actionMenuItems;
        if (this.state.showCloseButton) {
            items.action.push({
                key: "cash_in_out",
                description: "Entrada / Salida de efectivo",
                icon: "fa fa-money",
                callback: () => this.onCashInOut(),
                sequence: 100,
            }, {
                key: "close_session",
                description: "Cerrar caja",
                icon: "fa fa-times-circle",
                class: "text-danger",
                callback: () => this.onCloseCashRegister(),
                sequence: 110,
            });
        }
        return items;
    }
}

export const posOrderListView = { ...listView, Controller: PosOrderListController };
registry.category("views").add("button_in_tree", posOrderListView);
