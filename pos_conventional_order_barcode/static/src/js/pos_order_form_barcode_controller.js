/** @odoo-module **/

import { registry } from "@web/core/registry";
import { formView } from "@web/views/form/form_view";
import { FormController } from "@web/views/form/form_controller";
import { useService } from "@web/core/utils/hooks";
import { onMounted, onWillUnmount } from "@odoo/owl";
import { openUrlInHiddenPrintIframe } from "@pos_conventional_core/js/pos_print_iframe";

export class PosOrderBarcodeFormController extends FormController {
    setup() {
        super.setup();
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.barcodeBuffer = "";
        this.lastKeyTime = 0;
        this.barcodeTimeout = null;
        this.maxTimeBetweenKeys = 150;
        this.minBarcodeLength = 3;
        this.isProcessing = false;
        this.boundKeydownHandler = this.onKeyDown.bind(this);

        onMounted(() => {
            document.addEventListener("keydown", this.boundKeydownHandler, true);
        });

        onWillUnmount(() => {
            document.removeEventListener("keydown", this.boundKeydownHandler, true);
            if (this.barcodeTimeout) clearTimeout(this.barcodeTimeout);
        });
    }

    onKeyDown(ev) {
        try {
            const target = ev.target || document.activeElement;
            const tag = target && target.tagName ? target.tagName.toLowerCase() : null;
            if (tag === 'input' || tag === 'textarea' || tag === 'select' || (target && target.isContentEditable)) return;
        } catch (err) {}

        const now = Date.now();
        const timeDiff = now - this.lastKeyTime;

        if (["Shift", "Control", "Alt", "Meta", "CapsLock", "Escape"].includes(ev.key)) return;
        if (ev.key.length > 1 && ev.key !== "Enter" && ev.key !== "Tab") return;

        if (ev.key === "Enter" || ev.key === "Tab") {
            if (this.barcodeTimeout) {
                clearTimeout(this.barcodeTimeout);
                this.barcodeTimeout = null;
            }
            if (this.barcodeBuffer.length >= this.minBarcodeLength) {
                ev.preventDefault();
                ev.stopPropagation();
                const barcode = this.barcodeBuffer;
                this.barcodeBuffer = "";
                this.lastKeyTime = 0;
                this.processBarcode(barcode);
                return false;
            }
            this.barcodeBuffer = "";
            this.lastKeyTime = 0;
            return;
        }

        if (this.lastKeyTime > 0 && timeDiff > this.maxTimeBetweenKeys) this.barcodeBuffer = "";
        this.barcodeBuffer += ev.key;
        this.lastKeyTime = now;

        if (this.barcodeBuffer.length >= 1) {
            ev.preventDefault();
            ev.stopPropagation();
        }

        if (this.barcodeTimeout) clearTimeout(this.barcodeTimeout);
        this.barcodeTimeout = setTimeout(() => {
            if (this.barcodeBuffer.length >= this.minBarcodeLength) {
                const barcode = this.barcodeBuffer;
                this.barcodeBuffer = "";
                this.lastKeyTime = 0;
                this.processBarcode(barcode);
            } else {
                this.barcodeBuffer = "";
                this.lastKeyTime = 0;
            }
        }, this.maxTimeBetweenKeys + 50);

        return false;
    }

    async processBarcode(barcode) {
        if (this.isProcessing) return;
        barcode = barcode.trim();
        if (!barcode || barcode.length < this.minBarcodeLength) return;
        this.isProcessing = true;

        try {
            const record = this.model.root;
            const pricelistId = record.data.pricelist_id ? record.data.pricelist_id[0] : false;
            const fiscalPositionId = record.data.fiscal_position_id ? record.data.fiscal_position_id[0] : false;
            const partnerId = record.data.partner_id ? record.data.partner_id[0] : false;

            const result = await this.orm.call("pos.order", "get_product_line_data_by_barcode", [], {
                barcode: barcode,
                pricelist_id: pricelistId,
                fiscal_position_id: fiscalPositionId,
                partner_id: partnerId,
            });

            if (!result.success) {
                this.notification.add(result.message, { type: "warning", title: "Producto no encontrado" });
                return;
            }

            await this.addProductToLines(result.product, result.line_vals);
        } catch (error) {
            console.error("Error al procesar código de barras:", error);
        } finally {
            this.isProcessing = false;
        }
    }

    async addProductToLines(product, lineVals) {
        const record = this.model.root;
        if (record.isNew) {
            try {
                await record.save();
            } catch (error) {
                this.notification.add("Debe guardar el pedido antes de escanear productos.", { type: "warning" });
                return;
            }
        }
        const orderId = record.resId;
        if (!orderId) return;
        await this.addLineViaRPC(orderId, product, lineVals);
    }

    async addLineViaRPC(orderId, product, lineVals) {
        try {
            const result = await this.orm.call("pos.order", "add_product_by_barcode", [orderId], { product_id: product.id });
            if (result.success) {
                this.notification.add(result.message, { type: "success" });
                await this.model.root.load();
            } else {
                this.notification.add(result.message, { type: "warning" });
            }
        } catch (error) {
            console.error("Error al añadir línea:", error);
        }
    }
}

export const posOrderBarcodeFormView = {
    ...formView,
    Controller: PosOrderBarcodeFormController,
};

registry.category("views").add("pos_order_barcode_form", posOrderBarcodeFormView);
