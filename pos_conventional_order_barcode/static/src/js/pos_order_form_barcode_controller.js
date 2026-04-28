/** @odoo-module **/

import { registry } from "@web/core/registry";
import { formView } from "@web/views/form/form_view";
import { FormController } from "@web/views/form/form_controller";
import { useService } from "@web/core/utils/hooks";
import { onMounted, onWillUnmount, useSubEnv } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";

export class PosOrderBarcodeFormController extends FormController {
    setup() {
        super.setup();
        useSubEnv({
            config: {
                ...this.env.config,
                beforeLeave: async () => {
                    if (window.bypassPosLeave) {
                        return true;
                    }
                    return await this.model.root.save();
                },
            },
        });

        this.orm = useService("orm");
        this.notification = useService("notification");
        this.barcodeBuffer = "";
        this.lastKeyTime = 0;
        this.barcodeTimeout = null;
        this.maxTimeBetweenKeys = 150;
        this.minBarcodeLength = 3;
        this.isProcessing = false;
        this.boundKeydownHandler = this.onKeyDown.bind(this);
        this.boundPaymentButtonClickHandler = this._onPaymentButtonClick.bind(this);
        this.boundDocClickHandler = this._onDocClick.bind(this);

        onMounted(() => {
            document.addEventListener("keydown", this.boundKeydownHandler, true);
            // Capturar clicks en el botón "Pago" antes de que Odoo los procese
            document.addEventListener("click", this.boundPaymentButtonClickHandler, true);
            document.addEventListener("click", this.boundDocClickHandler, true);
        });

        onWillUnmount(() => {
            document.removeEventListener("keydown", this.boundKeydownHandler, true);
            document.removeEventListener("click", this.boundPaymentButtonClickHandler, true);
            document.removeEventListener("click", this.boundDocClickHandler, true);
            if (this.barcodeTimeout) clearTimeout(this.barcodeTimeout);
        });
    }

    _onDocClick(ev) {
        if (ev.target.closest('button[name="action_open_stock_forecast"]')) {
            window.bypassPosLeave = true;
            setTimeout(() => { window.bypassPosLeave = false; }, 2000);
        }
    }

    /**
     * Intercepta el botón "Pago" (action_open_payment_popup) en fase de captura.
     * Si el pedido tiene importe cero o no tiene líneas, bloquea la acción,
     * reproduce el pitido de error y muestra una notificación de aviso.
     */
    _onPaymentButtonClick(ev) {
        const btn = ev.target.closest('button[name="action_open_payment_popup"]');
        if (!btn) return;

        const record = this.model.root;
        const amountTotal = record.data.amount_total || 0;
        const linesCount = record.data.lines?.currentIds?.length || 0;

        if (linesCount === 0 || amountTotal <= 0) {
            ev.preventDefault();
            ev.stopImmediatePropagation();
            this._playErrorBeep();
            this.notification.add(
                _t("No se puede cobrar un pedido sin productos o con importe cero."),
                { type: "warning", title: _t("Importe inválido"), sticky: false }
            );
        }
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
                this._playErrorBeep();
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

    _playErrorBeep() {
        try {
            const ctx = new (window.AudioContext || window.webkitAudioContext)();
            const oscillator = ctx.createOscillator();
            const gainNode = ctx.createGain();
            oscillator.connect(gainNode);
            gainNode.connect(ctx.destination);
            oscillator.type = "square";
            oscillator.frequency.setValueAtTime(380, ctx.currentTime);
            oscillator.frequency.setValueAtTime(280, ctx.currentTime + 0.15);
            gainNode.gain.setValueAtTime(0.25, ctx.currentTime);
            gainNode.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.35);
            oscillator.start(ctx.currentTime);
            oscillator.stop(ctx.currentTime + 0.35);
        } catch (e) {
            // Fallback silencioso si Web Audio API no está disponible
        }
    }

    async addProductToLines(product, lineVals) {
        const record = this.model.root;
        if (record.isNew) {
            await this.addLineLocally(record, product, lineVals);
            try {
                await record.save();
            } catch (error) {
                console.error("Error al guardar el pedido tras escanear el producto:", error);
                this.notification.add(
                    _t("La línea se añadió al pedido, pero no se pudo guardar automáticamente. Revise los datos obligatorios y guarde manualmente."),
                    { type: "warning" }
                );
            }
            return;
        }
        const orderId = record.resId;
        if (!orderId) return;
        await this.addLineViaRPC(orderId, product);
    }

    async addLineLocally(record, product, lineVals) {
        const lines = record.data.lines;
        if (!lines) {
            return;
        }

        const qtyToAdd = lineVals.qty || 1.0;
        const existingLine = lines.records.find((line) => line.data.product_id?.id === product.id);

        if (existingLine) {
            const newQty = (existingLine.data.qty || 0) + qtyToAdd;
            await existingLine.update({ qty: newQty });
            this.notification.add(
                _t("Cantidad actualizada: %(qty)s x %(product)s", {
                    qty: newQty,
                    product: product.display_name,
                }),
                { type: "success" }
            );
            return existingLine;
        }

        const newLine = await lines.addNewRecord({ position: "bottom" });
        await newLine.update({
            product_id: {
                id: product.id,
                display_name: product.display_name,
            },
        });
        await newLine.update({
            full_product_name: lineVals.full_product_name || product.display_name,
            qty: qtyToAdd,
            price_unit: lineVals.price_unit,
            discount: lineVals.discount || 0.0,
        });

        this.notification.add(_t("Añadido: %s", product.display_name), { type: "success" });
        return newLine;
    }

    async addLineViaRPC(orderId, product) {
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

    async beforeLeave({ forceLeave } = {}) {
        if (window.bypassPosLeave) {
            window.bypassPosLeave = false;
            return super.beforeLeave(...arguments);
        }

        const record = this.model.root;
        
        // Ensure record exists and we are not forcing leave (e.g. error redirect)
        if (record && record.data && record.data.state === 'draft' && !forceLeave) {
            this._playErrorBeep();
            this.notification.add(
                _t("No puedes salir de un pedido que no ha sido pagado. Por favor, finaliza el pago, cancélalo o elimínalo antes de salir."),
                { 
                    type: "warning", 
                    title: _t("Pedido no pagado"), 
                    sticky: false,
                    autocloseDelay: 10000
                }
            );
            return false;
        }

        return super.beforeLeave(...arguments);
    }
}

export const posOrderBarcodeFormView = {
    ...formView,
    Controller: PosOrderBarcodeFormController,
};

registry.category("views").add("pos_order_barcode_form", posOrderBarcodeFormView);
