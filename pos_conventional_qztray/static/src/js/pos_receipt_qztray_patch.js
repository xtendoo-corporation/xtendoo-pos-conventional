/** @odoo-module **/

/* global qz */

import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import { rpc } from "@web/core/network/rpc";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { PosReceiptClientAction } from "@pos_conventional_core/js/pos_receipt_client_action";

const DEFAULT_REPORT_NAME = "pos_conventional_receipt_custom.report_factura_simplificada_80mm";
const FAST_POS_REPORT_NAMES = new Set([
    "pos_conventional_receipt_custom.report_pos_order_80mm",
    "pos_conventional_qztray.report_pos_order_80mm_qztray",
]);
let qzSecurityConfigured = false;
let qzConnectionKey = null;
const qzPrintConfigCache = new Map();

async function getQzTrayParamsFromOrder(env, params = {}) {
    if (params.use_qztray || !params.order_id) {
        return params;
    }
    try {
        const qzParams = await env.services.orm.call(
            "pos.order",
            "_get_pos_conventional_qztray_print_params",
            [[params.order_id]]
        );
        return {
            ...params,
            ...qzParams,
            next_action: params.next_action,
            clear_breadcrumbs: params.clear_breadcrumbs,
            url: params.url,
            report_autoprints: params.report_autoprints,
        };
    } catch (error) {
        console.warn("[PosReceiptQzTray] No se pudieron recuperar parámetros QZ.", error);
        return params;
    }
}

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

function configureQzSecurity() {
    if (qzSecurityConfigured) {
        return;
    }
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
    qzSecurityConfigured = true;
}

async function ensureQzConnection(host) {
    const connectionKey = host || "__local__";
    if (qz.websocket.isActive() && qzConnectionKey === connectionKey) {
        return;
    }
    if (qz.websocket.isActive()) {
        await qz.websocket.disconnect();
    }
    if (host) {
        await qz.websocket.connect({ host });
    } else {
        await qz.websocket.connect();
    }
    qzConnectionKey = connectionKey;
}

async function getQzPrintConfig(printerName, mode = "raw") {
    const cacheKey = `${mode}:${printerName}`;
    if (qzPrintConfigCache.has(cacheKey)) {
        return qzPrintConfigCache.get(cacheKey);
    }
    const qzPrinter = await qz.printers.find(printerName);
    if (mode === "report") {
        const config = qz.configs.create(qzPrinter, {
            units: "mm",
            size: {
                width: 72,
                height: 297,
            },
            margins: 0,
            scaleContent: false,
            rasterize: true,
            interpolation: "bicubic",
            jobName: "Informe Odoo",
        });
        qzPrintConfigCache.set(cacheKey, config);
        return config;
    }
    const configOptions = {
        units: "mm",
        margins: 0,
        scaleContent: false,
        rasterize: false,
        interpolation: "nearest-neighbor",
        encoding: "CP858",
        jobName: "Ticket POS",
    };
    const config = qz.configs.create(qzPrinter, configOptions);
    qzPrintConfigCache.set(cacheKey, config);
    return config;
}

function parsePrinterName(printerName) {
    if (printerName.includes("\\")) {
        const [host, printer] = printerName.split("\\");
        return { host, printerName: printer };
    }
    return { host: null, printerName };
}

async function getQzPrintAction(orm, reportName) {
    const printAction = await orm.call(
        "ir.actions.report",
        "print_action_for_report_name",
        [reportName],
        { context: { skip_printer_exception: true } }
    );

    if (!printAction || printAction.action !== "server") {
        throw new Error(_t("El informe no está configurado para impresión directa."));
    }
    if (printAction.backend !== "qztray") {
        throw new Error(_t("La impresora configurada no usa el backend QZ Tray."));
    }
    return printAction;
}

async function printRawReceiptWithQzTray(orm, orderId, parsedPrinter) {
    const payload = await orm.call(
        "pos.order",
        "get_pos_conventional_qztray_raw_payload",
        [[orderId]]
    );
    const rawReceipt = payload.raw_receipt || payload;
    const printData = [];
    if (payload.logo) {
        printData.push({
            type: "raw",
            format: "command",
            flavor: "plain",
            data: "\x1ba\x01",
        });
        printData.push({
            type: "raw",
            format: "image",
            flavor: "base64",
            data: payload.logo,
            options: {
                language: "ESCPOS",
                dotDensity: "double",
            },
        });
        printData.push({
            type: "raw",
            format: "command",
            flavor: "plain",
            data: "\x1ba\x00",
        });
    }
    printData.push({
        type: "raw",
        format: "command",
        flavor: "plain",
        data: rawReceipt,
    });
    configureQzSecurity();
    await ensureQzConnection(parsedPrinter.host);
    const config = await getQzPrintConfig(parsedPrinter.printerName, "raw");
    await qz.print(config, printData);
}

async function printFastPosReportWithQzTray(action, env) {
    if (!FAST_POS_REPORT_NAMES.has(action.report_name)) {
        return false;
    }

    const orderIds = action.context?.active_ids || [];
    const orderId = orderIds[0];
    if (!orderId) {
        return false;
    }

    const printAction = await getQzPrintAction(env.services.orm, DEFAULT_REPORT_NAME);
    const parsedPrinter = parsePrinterName(printAction.printer_name);
    await printRawReceiptWithQzTray(env.services.orm, orderId, parsedPrinter);
    return true;
}

const reportPrintBackends = registry.category("report.print.backends");
const originalQzPrintDispatcher = reportPrintBackends.contains("qztray")
    ? reportPrintBackends.get("qztray")
    : null;

reportPrintBackends.add(
    "qztray",
    async (action, env) => {
        if (await printFastPosReportWithQzTray(action, env)) {
            return true;
        }
        if (originalQzPrintDispatcher) {
            return originalQzPrintDispatcher(action, env);
        }
        return false;
    },
    { force: true }
);

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
        const printAction = await getQzPrintAction(this.orm, printerReportName);
        const parsedPrinter = parsePrinterName(printAction.printer_name);

        const reportResId = params.report_res_id || params.order_id;
        if (params.use_qztray && params.raw_receipt) {
            if (!reportResId) {
                throw new Error(_t("No se pudo identificar el pedido para imprimir en modo rápido."));
            }
            return printRawReceiptWithQzTray(this.orm, reportResId, parsedPrinter);
        }

        const pdfResId = params.report_res_id || moveId;
        const reportContext = {
            ...(this.env?.searchModel?.context || {}),
            ...(this.props.action.context || {}),
            ...(params.context || {}),
        };
        const data = params.print_original_receipt
            ? [{
                type: "pixel",
                format: "html",
                flavor: "file",
                data: new URL(`/report/html/${reportName}/${pdfResId}`, window.location.origin).toString(),
            }]
            : await rpc("/web/dataset/call_kw", {
                model: "ir.actions.report",
                method: "get_qz_tray_data",
                args: [printAction.id, [pdfResId], "pdf", reportName],
                kwargs: { data: {} },
                context: reportContext,
            });

        configureQzSecurity();
        await ensureQzConnection(parsedPrinter.host);
        const config = await getQzPrintConfig(parsedPrinter.printerName, "report");
        await qz.print(config, data);
    },

    async _printReportBackground(moveId) {
        const params = await getQzTrayParamsFromOrder(this.env, this.props.action.params || {});
        if (!params.use_qztray) {
            return super._printReportBackground(moveId);
        }
        if (params.print_original_receipt) {
            return this._printReportWithQzTray(moveId, params).catch((error) => {
                console.warn(
                    "[PosReceiptQzTray] No se pudo imprimir el ticket original con QZ Tray.",
                    error
                );
                this.notification.add(
                    _t("No se pudo imprimir el ticket original con QZ Tray: %s", error?.message || error),
                    { type: "danger", sticky: true }
                );
            });
        }

        this._printReportWithQzTray(moveId, params).catch((error) => {
            console.warn(
                "[PosReceiptQzTray] No se pudo imprimir con QZ Tray.",
                error
            );
            this.notification.add(
                _t("No se pudo imprimir el ticket QZ Tray: %s", error?.message || error),
                { type: "danger", sticky: true }
            );
        });
    },
});

async function printReceiptWindowQzTrayAction(env, action) {
    const params = await getQzTrayParamsFromOrder(env, action.params || {});
    const clearBreadcrumbs = params.clear_breadcrumbs !== undefined
        ? !!params.clear_breadcrumbs
        : true;

    if (params.use_qztray && params.print_original_receipt) {
        const clientAction = Object.create(PosReceiptClientAction.prototype);
        clientAction.orm = env.services.orm;
        clientAction.notification = env.services.notification;
        clientAction.props = { action };

        try {
            await clientAction._printReportWithQzTray(params.move_id, params);
        } catch (error) {
            console.warn(
                "[PosReceiptQzTray] No se pudo imprimir el ticket original con QZ Tray desde window action.",
                error
            );
            env.services.notification.add(
                _t("No se pudo imprimir el ticket original con QZ Tray: %s", error?.message || error),
                { type: "danger", sticky: true }
            );
        }
    } else if (params.use_qztray) {
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
            env.services.notification.add(
                _t("No se pudo imprimir el ticket QZ Tray: %s", error?.message || error),
                { type: "danger", sticky: true }
            );
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
