/** @odoo-module **/

import { registry } from "@web/core/registry";
import { formView } from "@web/views/form/form_view";
import { PosConventionalOrderFormController } from "@pos_conventional_core/js/pos_order_form_core_controller";
import { useService } from "@web/core/utils/hooks";
import { onMounted, onWillUnmount } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";

export class PosOrderBarcodeFormController extends PosConventionalOrderFormController {
    setup() {
        super.setup();
        this.orm = useService("orm");
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

        onMounted(() => {
            document.addEventListener("keydown", this.boundKeydownHandler, true);

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
            if (this.barcodeTimeout) clearTimeout(this.barcodeTimeout);
            if (this.manualLineFocusCleanupTimeout) clearTimeout(this.manualLineFocusCleanupTimeout);
            this.manualLineFocusCleanupObserver?.disconnect();
            this.manualLineFocusCleanupObserver = null;
            this.blurFocusTarget?.remove();
            this.blurFocusTarget = null;
        });
    }

    _onDocClick(ev) {
        super._onDocClick(ev);
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

    _isEditableTarget(target) {
        const tag = target && target.tagName ? target.tagName.toLowerCase() : null;
        return (
            tag === "input" ||
            tag === "textarea" ||
            tag === "select" ||
            !!(target && target.isContentEditable)
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

    onKeyDown(ev) {
        try {
            const target = ev.target || document.activeElement;
            if (this._isEditableTarget(target)) {
                if (this._isFocusInsideOrderLines(target)) {
                    this._stopManualLineFocusCleanup();
                }
                return;
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

             await this.addProductToLines(result.product, result.line_vals, record);
        } catch (error) {
            console.error("Error al procesar código de barras:", error);
        } finally {
            this.isProcessing = false;
        }
    }

    async _prepareOrderForBarcodeScan() {
        const record = this.model.root;

        if (!record) {
            this.notification.add(
                _t("No se puede identificar el pedido actual para procesar el barcode escaneado."),
                { type: "warning", title: _t("Pedido no disponible") }
            );
            return null;
        }

        this._blurActiveElement({ immediate: true });
        return record;
    }

    async _shouldAddBarcodeLineLocally(record) {
        if (!record || record.isNew || !record.resId) {
            return true;
        }

        if (typeof record.isDirty === "function") {
            try {
                return !!(await record.isDirty());
            } catch (error) {
                console.warn("No se pudo determinar si el pedido POS tiene cambios pendientes:", error);
            }
        }

        return !!record.dirty;
    }

    async addProductToLines(product, lineVals, record = this.model.root) {
        if (await this._shouldAddBarcodeLineLocally(record)) {
            await this.addLineLocally(record, product, lineVals);
            return;
        }

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
        const lines = this._getOrderLinesList(record);
        if (!lines || typeof lines.addNewRecord !== "function") {
            this.notification.add(
                _t("No se pudieron preparar las líneas del pedido para añadir el producto escaneado."),
                { type: "warning", title: _t("Líneas no disponibles") }
            );
            return null;
        }

        const qtyToAdd = lineVals.qty || 1.0;
        const existingLine = (lines.records || []).find(
            (line) => this._getRelationalValueId(line.data.product_id) === product.id
        );

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

        const newLine = await lines.addNewRecord({ mode: "edit", position: "bottom" });
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

}

export const posOrderBarcodeFormView = {
    ...formView,
    Controller: PosOrderBarcodeFormController,
};

registry.category("views").add("pos_order_barcode_form", posOrderBarcodeFormView);
