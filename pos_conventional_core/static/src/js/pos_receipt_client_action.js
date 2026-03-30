/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, onMounted, useState, useRef, xml } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { OrderReceipt } from "@point_of_sale/app/screens/receipt_screen/receipt/order_receipt";
import { formatCurrency } from "@web/core/currency";
import { _t } from "@web/core/l10n/translation";

class MockOrderLine {
    constructor(data, order) {
        this.data = data;
        this.order = order;
        this.id = data.id || Math.random();
        this.full_product_name = data.product_id ? data.product_id[1] : data.product_name;
        this.qty = data.qty;
        this.price = data.price_unit;
        this.discount = data.discount || 0;
        this.price_unit = data.price_unit;
        this.price_subtotal = data.price_subtotal || (data.price_unit * data.qty);
        this.price_subtotal_incl = data.price_subtotal_incl || (data.price_unit * data.qty);
        this.currency = order.currency;
        this.product_id = {
            id: data.product_id ? data.product_id[0] : 0,
            display_name: this.full_product_name,
            uom_id: { name: _t("Units") }
        };
    }
    getQuantityStr() {
        return { unitPart: Math.floor(this.qty).toString(), decimalPart: (this.qty % 1).toFixed(2).split(".")[1], decimalPoint: "." };
    }
}

class MockOrder {
    constructor(data) {
        this.data = data;
        this.company = { name: data.company_name, vat: data.company_vat, logo: data.logo };
        this.currency = { id: 0, symbol: data.currency_symbol || "€", format: (v) => v + " " + (data.currency_symbol || "€") };
        this.amount_total = data.amount_total;
        this.amount_return = data.amount_return;
        this.amount_tax = data.amount_tax;
        this.pos_reference = data.pos_reference;
        this.ticket_code = data.ticket_code;
        this.date_order = data.date_order;
        this.lines = (data.lines || []).map(l => new MockOrderLine(l, this));
        this.orderlines = this.lines;
    }
    getCashierName() { return ""; }
}

export class PosReceiptClientAction extends Component {
    static components = { OrderReceipt };
    static template = xml`
        <div class="o_pos_receipt_client_action h-100 w-100 d-flex flex-column align-items-center justify-content-center bg-view">
             <div class="o_loader" t-if="state.loading"><p class="h4">Generando ticket...</p></div>
             <div t-if="state.order" t-ref="receipt" class="pos-receipt-container" style="position: absolute; left: -9999px; width: 300px;">
                <OrderReceipt order="state.order" />
            </div>
            <div t-if="!state.loading" class="text-center p-5">
                <h2 class="fw-bold mb-3">Impresión realizada</h2>
                <button class="btn btn-primary" t-on-click="closeAction">Cerrar</button>
            </div>
        </div>
    `;

    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.state = useState({ loading: true, order: null });
        this.receiptRef = useRef("receipt");

        onMounted(async () => {
             const orderId = this.props.action.params.order_id;
             try {
                const orderData = await this.orm.call("pos.order", "get_order_receipt_data", [orderId]);
                this.state.order = new MockOrder(orderData);
                await new Promise(r => setTimeout(r, 800));
                await this.printReceipt();
             } finally {
                this.state.loading = false;
             }
        });
    }

    closeAction() {
        const next = this.props.action.params.next_action;
        if (next) this.actionService.doAction(next);
        else this.actionService.doAction({type: 'ir.actions.act_window_close'});
    }

    async printReceipt() {
        if (!this.receiptRef.el) return;
        const receiptEl = this.receiptRef.el.querySelector('.pos-receipt');
        if (!receiptEl) return;
        
        const iframe = document.createElement('iframe');
        iframe.style.position = 'fixed'; iframe.style.left = '-2000px';
        document.body.appendChild(iframe);
        const doc = iframe.contentDocument;
        document.querySelectorAll('link[rel="stylesheet"], style').forEach(l => doc.head.appendChild(l.cloneNode(true)));
        doc.body.innerHTML = `<div class="pos-receipt-print-wrapper">${receiptEl.outerHTML}</div>`;
        
        setTimeout(() => {
            iframe.contentWindow.print();
            setTimeout(() => iframe.remove(), 5000);
        }, 500);
    }
}

registry.category("actions").add("pos_conventional.print_receipt_client", PosReceiptClientAction);
