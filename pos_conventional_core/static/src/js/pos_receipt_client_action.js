/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, onMounted, xml } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

const REPORT_XMLID = "pos_conventional_receipt_custom.report_factura_simplificada_80mm";

export class PosReceiptClientAction extends Component {
    static components = {};
    // Transparent placeholder: navigates away before any content is visible.
    static template = xml`<div class="o_pos_receipt_client_action"/>`;

    setup() {
        this.actionService = useService("action");

        onMounted(() => {
            const params = this.props.action.params || {};
            const moveId = params.move_id;

            if (moveId) {
                // Fire the print in the background — the iframe loads and calls
                // window.print() on its own without blocking navigation.
                this._printReportBackground(moveId);
            } else {
                console.warn(
                    "[PosReceiptClientAction] No move_id provided — skipping print."
                );
            }

            // Navigate immediately to the next action (new order).
            // The print dialog will appear on top once the report is ready.
            this.closeAction();
        });
    }

    /**
     * Loads the receipt report inside a hidden iframe and triggers window.print()
     * once the document is ready. Runs entirely in the background — the caller
     * does not need to await this method.
     *
     * @param {number} moveId - ID of the account.move to print.
     */
    _printReportBackground(moveId) {
        const url = `/report/html/${REPORT_XMLID}/${moveId}`;
        const iframe = document.createElement("iframe");
        iframe.style.cssText = "position:fixed;left:-2000px;width:1px;height:1px;";
        document.body.appendChild(iframe);

        iframe.onload = () => {
            try {
                const iframeWin = iframe.contentWindow;
                // Give the browser a tick to render sub-resources before printing.
                setTimeout(() => {
                    iframeWin.focus();
                    iframeWin.print();
                    setTimeout(() => iframe.remove(), 8000);
                }, 600);
            } catch (error) {
                console.error("[PosReceiptClientAction] Error printing receipt:", error);
                iframe.remove();
            }
        };

        iframe.onerror = () => {
            console.error("[PosReceiptClientAction] Failed to load receipt report.");
            iframe.remove();
        };

        iframe.src = url;
    }

    closeAction() {
        const params = this.props.action.params || {};
        if (params.next_action) {
            this.actionService.doAction(params.next_action);
        } else {
            this.actionService.doAction({ type: "ir.actions.act_window_close" });
        }
    }
}

registry.category("actions").add(
    "pos_conventional_print_receipt_client",
    PosReceiptClientAction
);

