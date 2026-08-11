/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { PosOrderListController } from "@pos_conventional_core/js/pos_order_list_controller";

/**
 * Añade el flujo de PIN al crear un pedido desde la lista del TPV convencional.
 *
 * Esta lógica vive aquí (y no en pos_conventional_core) porque el campo
 * pos_force_employee_login_after_order pertenece a este módulo. Core no debe
 * conocer ni leer un campo que no es suyo.
 */
patch(PosOrderListController.prototype, {
    async createRecord() {
        const sessionId = this.currentSessionId || this.activeSessionId;
        if (sessionId && (await this._shouldForceLoginAfterOrder(sessionId))) {
            return this.actionService.doAction({
                type: "ir.actions.act_window",
                res_model: "pos.session.pin.wizard",
                view_mode: "form",
                views: [[false, "form"]],
                target: "new",
                context: {
                    default_session_id: sessionId,
                    force_new_order_flow: true,
                    no_cancel: true,
                },
            });
        }
        return super.createRecord(...arguments);
    },

    async _shouldForceLoginAfterOrder(sessionId) {
        let configId = Number.parseInt(this.props.context?.default_config_id, 10) || false;
        if (!configId) {
            const [session] = await this.model.orm.read(
                "pos.session",
                [sessionId],
                ["config_id"]
            );
            configId = Array.isArray(session?.config_id)
                ? session.config_id[0]
                : session?.config_id || false;
        }
        if (!configId) {
            return false;
        }
        const [config] = await this.model.orm.read(
            "pos.config",
            [configId],
            ["pos_force_employee_login_after_order"]
        );
        return !!config?.pos_force_employee_login_after_order;
    },
});
