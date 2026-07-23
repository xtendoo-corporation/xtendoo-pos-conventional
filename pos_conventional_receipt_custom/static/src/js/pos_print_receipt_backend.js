/** @odoo-module **/

import { registry } from '@web/core/registry';

function _printInBackground(url, reportAutoprints = false) {
    return new Promise((resolve) => {
        const iframe = document.createElement('iframe');
        iframe.style.cssText = 'position:fixed;left:-2000px;width:1px;height:1px;opacity:0;pointer-events:none;';
        document.body.appendChild(iframe);

        const cleanup = () => {
            try { iframe.remove(); } catch (e) {}
            resolve();
        };

        iframe.onload = () => {
            try {
                // If the report auto-calls window.print() on load, we must NOT
                // trigger print() from here to avoid showing the dialog twice.
                setTimeout(() => {
                    try {
                        if (!reportAutoprints) {
                            iframe.contentWindow.focus();
                            iframe.contentWindow.print();
                        }
                    } catch (e) {}
                    setTimeout(cleanup, 1200);
                }, 500);
            } catch (e) {
                cleanup();
            }
        };
        iframe.onerror = () => cleanup();
        iframe.src = url;
    });
}

async function posPrintReceiptBackendAction(env, action) {
    const params = action.params || {};
    const reportName = params.report_name || params.reportName || 'pos_conventional_receipt_custom.report_factura_simplificada_80mm';
    const moveId = params.move_id || params.moveId || params.moveId;
    const reportAutoprints = !!params.report_autoprints || !!params.reportAutoprints || false;
    if (!moveId) {
        env.services.notification.add('No se ha proporcionado move_id para imprimir.', { type: 'warning' });
        return;
    }
    const url = `/report/html/${reportName}/${moveId}`;
    // Print in background without navigating away or opening a new tab.
    // If the report template itself calls window.print() on load (reportAutoprints),
    // do not call iframe.contentWindow.print() to avoid double print dialogs.
    await _printInBackground(url, reportAutoprints);
    // Keep the current view as-is.
}

registry.category('actions').add('pos_conventional_print_receipt_backend', posPrintReceiptBackendAction);

