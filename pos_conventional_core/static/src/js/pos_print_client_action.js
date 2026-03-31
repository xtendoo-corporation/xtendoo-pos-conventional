/** @odoo-module */

import { registry } from "@web/core/registry";
import { openUrlInHiddenPrintIframe } from "@pos_conventional_core/js/pos_print_iframe";

/**
 * Acción de cliente para imprimir un informe en un iframe oculto.
 * Espera action.params.url con la URL del informe HTML.
 */
async function printIframeAction(env, action) {
    const params = action.params || {};
    const url = params.url;
    if (!url) {
        env.services.notification.add('No se ha proporcionado URL para imprimir.', { type: 'warning' });
        return;
    }
    const absolute = new URL(url, window.location.origin).toString();
    try {
        await openUrlInHiddenPrintIframe(absolute + '?download=false');
        env.services.notification.add('Enviado a impresora.', { type: 'success' });
    } catch (err) {
        console.error('Error imprimiendo en iframe:', err);
        env.services.notification.add('Error al imprimir: ' + (err.message || err), { type: 'danger' });
    }

    if (params.next_action) {
        await env.services.action.doAction(params.next_action, { clearBreadcrumbs: true });
    }
}

registry.category('actions').add('pos_conventional_print_iframe', printIframeAction, { force: true });
