/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, onMounted, useState, xml } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

const REPORT_XMLID = "pos_conventional_receipt_custom.report_factura_simplificada_80mm";

export class PosReceiptClientAction extends Component {
    static components = {};
    static template = xml`
        <div class="o_pos_receipt_client_action h-100 w-100 d-flex flex-column align-items-center justify-content-center bg-view">
            <div t-if="state.loading" class="text-center">
                <i class="fa fa-spinner fa-spin fa-3x mb-3 text-primary"/>
                <p class="h4">Generating receipt...</p>
            </div>
            <div t-if="state.error" class="text-center text-danger p-5">
                <i class="fa fa-exclamation-circle fa-3x mb-3"/>
                <p class="h5"><t t-esc="state.error"/></p>
                <button class="btn btn-secondary mt-3" t-on-click="closeAction">Close</button>
            </div>
        </div>
    `;

    setup() {
        this.actionService = useService("action");
        this.notification = useService("notification");
        this.state = useState({ loading: true, error: "" });

        onMounted(async () => {
            const params = this.props.action.params || {};
            const moveId = params.move_id;

            if (!moveId) {
                this.state.error = "No invoice found for this order. Cannot print receipt.";
                this.state.loading = false;
                return;
            }

            try {
                await this._printReport(moveId);
                // Redirect immediately to the next action (new order) without
                // showing any intermediate confirmation screen.
                this.closeAction();
            } catch (error) {
                console.error("Error printing receipt:", error);
                this.state.error = error.message || "Unexpected error while printing.";
                this.state.loading = false;
            }
        });
    }

    _printReport(moveId) {
        return new Promise((resolve, reject) => {
            const url = `/report/html/${REPORT_XMLID}/${moveId}`;

            const iframe = document.createElement("iframe");
            iframe.style.cssText = "position:fixed;left:-2000px;width:1px;height:1px;";
            document.body.appendChild(iframe);

            iframe.onload = () => {
                try {
                    // Wait for sub-resources (images, fonts) then print
                    const iframeWin = iframe.contentWindow;
                    const doprint = () => {
                        iframeWin.focus();
                        iframeWin.print();
                        setTimeout(() => iframe.remove(), 8000);
                        resolve();
                    };
                    // Give the browser a tick to render before printing
                    setTimeout(doprint, 600);
                } catch (e) {
                    iframe.remove();
                    reject(e);
                }
            };

            iframe.onerror = () => {
                iframe.remove();
                reject(new Error("Failed to load the receipt report."));
            };

            iframe.src = url;
        });
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

