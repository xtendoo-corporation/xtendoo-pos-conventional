/** @odoo-module **/

import { actionService } from "@web/webclient/actions/action_service";
import { patch } from "@web/core/utils/patch";

/**
 * Parcheamos el servicio de acciones de Odoo para que, siempre que se dispare
 * una acción propia del TPV Convencional, se autorice automáticamente la 
 * navegación (bypassPosLeave). Esto evita bloqueos en transiciones complejas
 * como la validación de pagos desde asistentes o redirecciones de servidor.
 */
patch(actionService, {
    async doAction(action) {
        const actionTag = (typeof action === 'string') ? action : (action && action.tag);
        
        if (actionTag && actionTag.startsWith('pos_conventional_')) {
            console.log(`[ActionService Patch] POS Conventional action detected: ${actionTag}. Activating navigation bypass.`);
            window.bypassPosLeave = true;
            
            // Limpieza de seguridad tras un tiempo razonable si no se completó la navegación
            setTimeout(() => {
                if (window.bypassPosLeave) {
                    // Solo limpiamos si seguimos en la misma URL (mismo pedido)
                    window.bypassPosLeave = false;
                }
            }, 5000);
        }
        
        return await super.doAction(...arguments);
    }
});
