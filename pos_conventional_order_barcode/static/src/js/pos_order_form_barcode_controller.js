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
        this.blurFocusTarget = null;
        this.manualLineFocusCleanupTimeout = null;
        this.manualLineFocusCleanupObserver = null;
        this.manualLineFocusCleanupAttempts = 0;
        this.boundKeydownHandler = this.onKeyDown.bind(this);
        this.boundPaymentButtonClickHandler = this._onPaymentButtonClick.bind(this);
        this.boundDocClickHandler = this._onDocClick.bind(this);

        onMounted(() => {
            document.addEventListener("keydown", this.boundKeydownHandler, true);
            // Capturar clicks en el botón "Pago" antes de que Odoo los procese
            document.addEventListener("click", this.boundPaymentButtonClickHandler, true);
            document.addEventListener("click", this.boundDocClickHandler, true);

            // Quitar el foco automático si es un pedido nuevo
            if (this.model.root.isNew) {
                setTimeout(() => {
                    if (document.activeElement instanceof HTMLElement &&
                        (document.activeElement.tagName === 'INPUT' || document.activeElement.tagName === 'TEXTAREA')) {
                        document.activeElement.blur();
                    }
                }, 100);
            }
        });

        onWillUnmount(() => {
            document.removeEventListener("keydown", this.boundKeydownHandler, true);
            document.removeEventListener("click", this.boundPaymentButtonClickHandler, true);
            document.removeEventListener("click", this.boundDocClickHandler, true);
            if (this.barcodeTimeout) clearTimeout(this.barcodeTimeout);
            if (this.manualLineFocusCleanupTimeout) clearTimeout(this.manualLineFocusCleanupTimeout);
            this.manualLineFocusCleanupObserver?.disconnect();
            this.manualLineFocusCleanupObserver = null;
            this.blurFocusTarget?.remove();
            this.blurFocusTarget = null;
        });
    }

    _onDocClick(ev) {
        if (ev.target.closest('button[name="action_open_stock_forecast"]')) {
            window.bypassPosLeave = true;
            setTimeout(() => { window.bypassPosLeave = false; }, 2000);
        }

        if (this._isManualLineAddButton(ev.target)) {
            this._watchManualLineFocusCleanup();
        }
    }

    _isManualLineAddButton(target) {
        return !!target?.closest?.(
            ".o_field_widget[name='lines'] .o_field_x2many_list_row_add a, " +
            ".o_field_widget[name='lines'] .o_group_field_row_add a, " +
            "[name='lines'] .o_field_x2many_list_row_add a, " +
            "[name='lines'] .o_group_field_row_add a"
        );
    }

    _getOrderLinesFieldElement() {
        return document.querySelector(
            ".o_field_widget[name='lines'], [name='lines'].o_field_widget, [name='lines']"
        );
    }

    _isFocusInsideOrderLines(target) {
        const linesField = this._getOrderLinesFieldElement();
        return !!(
            linesField &&
            target instanceof HTMLElement &&
            linesField.contains(target)
        );
    }

    _watchManualLineFocusCleanup() {
        const linesField = this._getOrderLinesFieldElement();
        this.manualLineFocusCleanupAttempts = 0;

        if (this.manualLineFocusCleanupTimeout) {
            clearTimeout(this.manualLineFocusCleanupTimeout);
            this.manualLineFocusCleanupTimeout = null;
        }

        this.manualLineFocusCleanupObserver?.disconnect();
        this.manualLineFocusCleanupObserver = null;

        if (!linesField) {
            return;
        }

        this.manualLineFocusCleanupObserver = new MutationObserver(() => {
            this._queueManualLineFocusCleanupAttempt();
        });
        this.manualLineFocusCleanupObserver.observe(linesField, {
            childList: true,
            subtree: true,
            characterData: true,
        });

        this._queueManualLineFocusCleanupAttempt();
    }

    _queueManualLineFocusCleanupAttempt() {
        if (this.manualLineFocusCleanupTimeout) {
            clearTimeout(this.manualLineFocusCleanupTimeout);
        }
        this.manualLineFocusCleanupTimeout = setTimeout(() => {
            this.manualLineFocusCleanupTimeout = null;
            this._tryCleanupManualLineFocus();
        }, 120);
    }

    _tryCleanupManualLineFocus() {
        const linesField = this._getOrderLinesFieldElement();
        if (!linesField) {
            this._stopManualLineFocusCleanup();
            return;
        }

        const activeElement = document.activeElement;
        const autoCompleteOpen = !!document.querySelector(".o-autocomplete--dropdown-menu.show");
        const focusInsideLines = activeElement instanceof HTMLElement && linesField.contains(activeElement);

        if (autoCompleteOpen) {
            this._retryManualLineFocusCleanup();
            return;
        }

        if (!focusInsideLines) {
            this._stopManualLineFocusCleanup();
            return;
        }

        const activeRow = activeElement.closest?.("tr.o_data_row");
        if (!activeRow) {
            this._retryManualLineFocusCleanup();
            return;
        }

        this._blurActiveElement({ immediate: true });
        this._stopManualLineFocusCleanup();
    }

    _retryManualLineFocusCleanup() {
        this.manualLineFocusCleanupAttempts += 1;
        if (this.manualLineFocusCleanupAttempts >= 25) {
            this._stopManualLineFocusCleanup();
            return;
        }
        this._queueManualLineFocusCleanupAttempt();
    }

    _stopManualLineFocusCleanup() {
        if (this.manualLineFocusCleanupTimeout) {
            clearTimeout(this.manualLineFocusCleanupTimeout);
            this.manualLineFocusCleanupTimeout = null;
        }
        this.manualLineFocusCleanupObserver?.disconnect();
        this.manualLineFocusCleanupObserver = null;
        this.manualLineFocusCleanupAttempts = 0;
    }

    /**
     * Intercepta el botón "Pago" y otros botones de acción de pago.
     * Si el pedido tiene importe cero o no tiene líneas, bloquea la acción.
     * Si es válido, activa el bypass de navegación.
     */
    _onPaymentButtonClick(ev) {
        const btn = ev.target.closest('button[name^="action_pay_"], button[name="action_open_payment_popup"], button[name="action_pos_convention_pay_with_method"]');
        if (!btn) return;

        const record = this.model.root;
        const amountTotal = record.data.amount_total || 0;
        const linesCount = record.data.lines?.currentIds?.length || 0;

        // Si intentamos cobrar algo vacío, bloqueamos
        if (linesCount === 0 || amountTotal <= 0) {
            ev.preventDefault();
            ev.stopImmediatePropagation();
            this._playErrorBeep();
            this.notification.add(
                _t("No se puede cobrar un pedido sin productos o con importe cero."),
                { type: "warning", title: _t("Importe inválido"), sticky: false }
            );
            return;
        }

        // Si el pedido es válido y vamos a pagar, activamos el bypass de navegación
        // para permitir el cambio de pantalla fluido tras la validación.
        window.bypassPosLeave = true;
        // Limpiamos el bypass tras 10 segundos por seguridad si no se navegó
        setTimeout(() => {
            if (window.location.hash.includes('model=pos.order') && window.location.hash.includes('id=' + record.resId)) {
                window.bypassPosLeave = false;
            }
        }, 10000);
    }

    onKeyDown(ev) {
        try {
            const target = ev.target || document.activeElement;
            const tag = target && target.tagName ? target.tagName.toLowerCase() : null;
            const isEditableTarget = tag === 'input' || tag === 'textarea' || tag === 'select' || (target && target.isContentEditable);
            if (isEditableTarget) {
                if (this._isFocusInsideOrderLines(target)) {
                    this._stopManualLineFocusCleanup();
                    this._blurActiveElement({ immediate: true });
                } else {
                    return;
                }
            }
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
            const record = await this._prepareOrderForBarcodeScan();
            if (!record) {
                return;
            }

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

    async _prepareOrderForBarcodeScan() {
        const record = this.model.root;

        try {
            await record.save();
        } catch (error) {
            console.error("Error al guardar el pedido antes de procesar el barcode:", error);
            this.notification.add(
                _t("Debe guardar el pedido antes de escanear productos. Revise los datos obligatorios y vuelva a intentarlo."),
                { type: "warning", title: _t("Pedido no guardado") }
            );
            return null;
        }

        if (!record.resId) {
            this.notification.add(
                _t("No se puede identificar el pedido actual para procesar el barcode escaneado."),
                { type: "warning", title: _t("Pedido no disponible") }
            );
            return null;
        }

        this._blurActiveElement({ immediate: true });
        return record;
    }

    async addProductToLines(product, lineVals) {
        const record = this.model.root;
        const orderId = record.resId;
        if (!orderId) {
            this.notification.add(
                _t("No se puede identificar el pedido actual para añadir el producto escaneado."),
                { type: "warning", title: _t("Pedido no disponible") }
            );
            return;
        }

        await this.addLineViaRPC(orderId, product, lineVals);
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
            this._blurActiveElement();
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
        this._blurActiveElement();
        return newLine;
    }

    async addLineViaRPC(orderId, product, lineVals) {
        try {
            const result = await this.orm.call("pos.order", "add_product_by_barcode", [orderId], {
                product_id: product.id,
                line_vals: lineVals,
            });
            if (result.success) {
                this.notification.add(result.message, { type: "success" });
                await this._saveOrderAfterBarcodeLineChange();
            } else {
                this.notification.add(result.message, { type: "warning" });
            }
        } catch (error) {
            console.error("Error al añadir línea:", error);
        }
    }

    async _saveOrderAfterBarcodeLineChange() {
        await this.model.root.load();
        this._blurActiveElement({ immediate: true });

        try {
            await this.model.root.save();
        } catch (error) {
            console.error("Error al guardar el pedido tras añadir una línea por barcode:", error);
            this.notification.add(
                _t("La línea se añadió correctamente, pero no se pudo guardar el pedido automáticamente."),
                { type: "warning", title: _t("Pedido no guardado") }
            );
        }

        this._blurActiveElement();
    }

    _getBlurFocusTarget() {
        if (this.blurFocusTarget?.isConnected) {
            return this.blurFocusTarget;
        }

        const target = document.createElement("button");
        target.type = "button";
        target.tabIndex = -1;
        target.setAttribute("aria-hidden", "true");
        target.style.position = "fixed";
        target.style.left = "-9999px";
        target.style.top = "0";
        target.style.width = "1px";
        target.style.height = "1px";
        target.style.opacity = "0";
        target.style.pointerEvents = "none";
        document.body.appendChild(target);
        this.blurFocusTarget = target;
        return target;
    }

    _moveFocusOutOfEditableLine() {
        const blur = () => {
            const activeElement = document.activeElement;
            if (
                activeElement instanceof HTMLElement &&
                activeElement !== document.body &&
                activeElement !== document.documentElement &&
                activeElement !== this.blurFocusTarget
            ) {
                activeElement.blur?.();
            }

            this._getBlurFocusTarget().focus({ preventScroll: true });
            window.getSelection?.()?.removeAllRanges?.();
        };

        blur();
        setTimeout(blur, 0);
        setTimeout(blur, 50);
        setTimeout(blur, 150);
    }

    _blurActiveElement({ immediate = false } = {}) {
        const blur = () => this._moveFocusOutOfEditableLine();

        if (immediate) {
            blur();
            return;
        }

        setTimeout(blur, 100);
    }

    async beforeLeave({ forceLeave } = {}) {
        if (window.bypassPosLeave) {
            // No reseteamos inmediatamente a false aquí, ya que Odoo puede llamar
            // a beforeLeave varias veces durante una transición compleja.
            // El flag se limpia solo tras 2 segundos o al entrar en un pedido nuevo.
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
