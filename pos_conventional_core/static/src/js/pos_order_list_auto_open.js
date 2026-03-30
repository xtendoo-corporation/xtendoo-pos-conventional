/** @odoo-module **/

import { registry } from "@web/core/registry";

/**
 * Servicio para abrir automáticamente un pedido nuevo cuando se vuelve a la lista
 */
const posConventionalAutoOpenService = {
    dependencies: ["action"],

    start(env, { action }) {
        const checkPendingOrder = () => {
            const pendingOrderId = sessionStorage.getItem('pos_conventional_new_order_id');
            const sessionId = sessionStorage.getItem('pos_conventional_session_id');

            if (pendingOrderId) {
                const currentUrl = window.location.href;
                if (currentUrl.includes('model=pos.order') && currentUrl.includes('view_type=list')) {
                    sessionStorage.removeItem('pos_conventional_new_order_id');
                    sessionStorage.removeItem('pos_conventional_session_id');

                    setTimeout(() => {
                        action.doAction({
                            type: "ir.actions.act_window",
                            res_model: "pos.order",
                            res_id: parseInt(pendingOrderId),
                            views: [[false, "form"]],
                            target: "current",
                            context: {
                                default_session_id: parseInt(sessionId),
                            },
                        });
                    }, 600);
                }
            }
        };

        const interval = setInterval(checkPendingOrder, 500);
        setTimeout(() => clearInterval(interval), 5000);

        return {};
    },
};

registry.category("services").add("pos_conventional_auto_open", posConventionalAutoOpenService);
