/** @odoo-module **/

import { registry } from "@web/core/registry";

/**
 * Servicio para abrir automáticamente un pedido pendiente cuando se vuelve a la lista.
 *
 * IMPORTANTE: verifica que el pedido existe y es accesible vía RPC antes de navegar.
 * Esto evita el MissingError cuando sessionStorage contiene un ID obsoleto (p.ej. de
 * una versión anterior del código) que apunta a un registro eliminado o inaccesible.
 */
const posConventionalAutoOpenService = {
    dependencies: ["action", "orm"],

    start(env, { action, orm }) {
        let pendingCheck = false;

        const checkPendingOrder = async () => {
            if (pendingCheck) return;

            const pendingOrderId = sessionStorage.getItem("pos_conventional_new_order_id");
            const sessionId = sessionStorage.getItem("pos_conventional_session_id");

            if (!pendingOrderId) return;

            const currentUrl = window.location.href;
            const isListView =
                currentUrl.includes("model=pos.order") && currentUrl.includes("view_type=list");

            if (!isListView) return;

            // Limpiar sessionStorage inmediatamente para evitar reintentos
            sessionStorage.removeItem("pos_conventional_new_order_id");
            sessionStorage.removeItem("pos_conventional_session_id");

            const orderId = parseInt(pendingOrderId, 10);
            if (!orderId || isNaN(orderId)) return;

            pendingCheck = true;
            try {
                // Verificar que el pedido existe y el usuario puede acceder a él
                // antes de intentar la navegación (evita MissingError con IDs obsoletos).
                const records = await orm.searchRead(
                    "pos.order",
                    [["id", "=", orderId]],
                    ["id", "state"],
                    { limit: 1 }
                );

                if (!records || records.length === 0) {
                    console.warn(
                        "[AUTO_OPEN] pos.order(%s) no existe o no es accesible — ignorando.",
                        orderId
                    );
                    return;
                }

                setTimeout(() => {
                    action.doAction({
                        type: "ir.actions.act_window",
                        res_model: "pos.order",
                        res_id: orderId,
                        views: [[false, "form"]],
                        target: "current",
                        context: {
                            default_session_id: parseInt(sessionId, 10) || false,
                        },
                    });
                }, 600);
            } catch (error) {
                console.warn(
                    "[AUTO_OPEN] Error al verificar pos.order(%s) — ignorando:",
                    orderId,
                    error
                );
            } finally {
                pendingCheck = false;
            }
        };

        const interval = setInterval(checkPendingOrder, 500);
        setTimeout(() => clearInterval(interval), 5000);

        return {};
    },
};

registry.category("services").add("pos_conventional_auto_open", posConventionalAutoOpenService);
