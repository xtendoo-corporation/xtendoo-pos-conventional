/** @odoo-module **/

/* global qz */

import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import { rpc } from "@web/core/network/rpc";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { PosReceiptClientAction } from "@pos_conventional_core/js/pos_receipt_client_action";

const DEFAULT_REPORT_NAME = "pos_conventional_receipt_custom.report_factura_simplificada_80mm";

function printUrlInBackground(url, env, { reportAutoprints = false } = {}) {
    return new Promise((resolve) => {
        const iframe = document.createElement("iframe");
        iframe.style.cssText = "position:fixed;left:-2000px;width:1px;height:1px;opacity:0;pointer-events:none;";
        document.body.appendChild(iframe);

        let isSettled = false;
        const cleanup = () => {
            if (isSettled) {
                return;
            }
            isSettled = true;
            iframe.remove();
            window.focus();
            resolve();
        };

        iframe.onload = () => {
            setTimeout(() => {
                if (reportAutoprints) {
                    setTimeout(cleanup, 1200);
                    return;
                }
                try {
                    iframe.contentWindow.focus();
                    iframe.contentWindow.print();
                } catch (error) {
                    console.error("[PosReceiptQzTray] Error imprimiendo fallback:", error);
                    env.services.notification.add(_t("No se pudo abrir la impresión del ticket."), {
                        type: "danger",
                        sticky: true,
                    });
                }
                setTimeout(cleanup, 1200);
            }, 500);
        };

        iframe.onerror = () => {
            env.services.notification.add(_t("No se pudo cargar el ticket para imprimir."), {
                type: "danger",
                sticky: true,
            });
            cleanup();
        };

        iframe.src = url;
    });
}

patch(PosReceiptClientAction.prototype, {
    setup() {
        super.setup();
        this.orm = useService("orm");
        this.notification = useService("notification");
    },

    async _printReportWithQzTray(moveId, params = {}) {
        if (!window.qz) {
            throw new Error(_t("QZ Tray no está disponible en el navegador."));
        }

        const reportName = params.report_name || DEFAULT_REPORT_NAME;
        const printerReportName = params.printer_report_name || reportName;
        const printAction = await this.orm.call(
            "ir.actions.report",
            "print_action_for_report_name",
            [printerReportName],
            { context: { skip_printer_exception: true } }
        );

        if (!printAction || printAction.action !== "server") {
            throw new Error(_t("El informe no está configurado para impresión directa."));
        }
        if (printAction.backend !== "qztray") {
            throw new Error(_t("La impresora configurada no usa el backend QZ Tray."));
        }

        const reportResId = params.report_res_id || moveId;
        const data = await rpc("/web/dataset/call_kw", {
            model: "ir.actions.report",
            method: "get_qz_tray_data",
            args: [printAction.id, [reportResId], "pdf", reportName],
            kwargs: { data: {} },
            context: {},
        });

        qz.security.setCertificatePromise((resolve, reject) => {
            fetch("/qz-certificate", {
                cache: "no-store",
                headers: { "Content-Type": "text/plain" },
            })
                .then((response) =>
                    response.text().then((text) => (response.ok ? resolve(text) : reject(text)))
                )
                .catch(reject);
        });
        qz.security.setSignatureAlgorithm("SHA512");
        qz.security.setSignaturePromise((toSign) => (resolve, reject) => {
            fetch(`/qz-sign-message?request=${toSign}`, {
                cache: "no-store",
                headers: { "Content-Type": "text/plain" },
            })
                .then((response) =>
                    response.text().then((text) => (response.ok ? resolve(text) : reject(text)))
                )
                .catch(reject);
        });

        let printerName = printAction.printer_name;
        if (printerName.includes("\\")) {
            const [host, printer] = printerName.split("\\");
            printerName = printer;
            await qz.websocket.connect({ host });
        } else {
            await qz.websocket.connect();
        }

        try {
            const qzPrinter = await qz.printers.find(printerName);
            const config = qz.configs.create(qzPrinter);
            await qz.print(config, data);
            this.notification.add(_t("Ticket enviado a QZ Tray: %s", printerName), {
                type: "success",
            });
        } finally {
            try {
                await qz.websocket.disconnect();
            } catch {
                // Ignore disconnect errors: the print result is already known.
            }
        }
    },

    _printReportBackground(moveId) {
        const params = this.props.action.params || {};
        if (!params.use_qztray) {
            return super._printReportBackground(moveId);
        }

        this._printReportWithQzTray(moveId, params).catch((error) => {
            console.warn(
                "[PosReceiptQzTray] No se pudo imprimir con QZ Tray. Se usa el flujo normal.",
                error
            );
            this.notification.add(
                _t("No se pudo imprimir con QZ Tray. Se usará la impresión del navegador."),
                { type: "warning" }
            );
            super._printReportBackground(moveId);
        });
    },
});

async function printReceiptWindowQzTrayAction(env, action) {
    const params = action.params || {};
    const clearBreadcrumbs = params.clear_breadcrumbs !== undefined
        ? !!params.clear_breadcrumbs
        : true;

    if (params.use_qztray) {
        const clientAction = Object.create(PosReceiptClientAction.prototype);
        clientAction.orm = env.services.orm;
        clientAction.notification = env.services.notification;
        clientAction.props = { action };

        try {
            await clientAction._printReportWithQzTray(params.move_id, params);
        } catch (error) {
            console.warn(
                "[PosReceiptQzTray] No se pudo imprimir con QZ Tray desde window action.",
                error
            );
            if (params.url) {
                const absoluteUrl = new URL(params.url, window.location.origin).toString();
                await printUrlInBackground(absoluteUrl, env, {
                    reportAutoprints: !!params.report_autoprints,
                });
            }
        }
    } else {
        if (params.url) {
            const absoluteUrl = new URL(params.url, window.location.origin).toString();
            await printUrlInBackground(absoluteUrl, env, {
                reportAutoprints: !!params.report_autoprints,
            });
        }
    }

    if (params.next_action) {
        return env.services.action.doAction(params.next_action, { clearBreadcrumbs });
    }
    return { type: "ir.actions.act_window_close" };
}

registry.category("actions").add(
    "pos_conventional_print_receipt_qztray_window",
    printReceiptWindowQzTrayAction
);
registry.category("actions").add(
    "pos_conventional_print_receipt_window",
    printReceiptWindowQzTrayAction,
    { force: true }
);
