import { barcodeService as barcodeServiceDefinition } from "@barcodes/barcode_service";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useBus, useService } from "@web/core/utils/hooks";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { Component, onMounted, onWillUnmount, useRef, xml } from "@odoo/owl";

const BARCODE_EVENTS_ATTR = "barcode_events";
const MANAGED_DATASET_KEY = "posConventionalBarcodeScannerManaged";
const ORIGINAL_DATASET_KEY = "posConventionalBarcodeScannerOriginal";
const EDITABLE_SELECTOR = 'input, textarea, [contenteditable="true"]';

function isNodeWithin(node, container) {
    return node instanceof Node && container?.contains(node);
}

function isEditable(element) {
    return element?.matches?.(EDITABLE_SELECTOR);
}

function isSpecialKey(key, event) {
    return (
        !["Control", "Alt", "Meta"].includes(key) &&
        (key.length > 1 || event.ctrlKey || event.metaKey || event.altKey)
    );
}

function isEndCharacter(key) {
    return /(Enter|Tab)/.test(key);
}

function isNumericKey(key) {
    return key.length === 1 && key >= "0" && key <= "9";
}

function isNumericBarcode(barcode) {
    return typeof barcode === "string" && /^[0-9]+$/.test(barcode.trim());
}

function cleanBarcode(barcode) {
    return barcodeServiceDefinition.cleanBarcode(barcode);
}

function getBarcodeTimeout() {
    return barcodeServiceDefinition.maxTimeBetweenKeysInMs;
}

function captureEditableState(element) {
    if (!isEditable(element)) {
        return null;
    }
    if (element.matches('[contenteditable="true"]')) {
        return {
            element,
            html: element.innerHTML,
            text: element.textContent,
            type: "contenteditable",
        };
    }
    return {
        element,
        selectionEnd: element.selectionEnd,
        selectionStart: element.selectionStart,
        type: "input",
        value: element.value,
    };
}

function applyBufferedText(state, text) {
    if (!state?.element?.isConnected) {
        return;
    }
    if (state.type === "contenteditable") {
        state.element.textContent = `${state.text}${text}`;
        return;
    }
    const selectionStart = state.selectionStart ?? state.value.length;
    const selectionEnd = state.selectionEnd ?? selectionStart;
    state.element.value =
        state.value.slice(0, selectionStart) + text + state.value.slice(selectionEnd);
    const nextPosition = selectionStart + text.length;
    if (typeof state.element.setSelectionRange === "function") {
        state.element.setSelectionRange(nextPosition, nextPosition);
    }
    state.element.dispatchEvent(new Event("input", { bubbles: true }));
}

export class PosConventionalBarcodeScannerField extends Component {
    static props = { ...standardFieldProps };
    static supportedTypes = ["char"];
    static template = xml`<div t-ref="root" class="o_pos_conventional_barcode_scanner d-none"/>`;

    setup() {
        this.rootRef = useRef("root");
        this.barcodeService = useService("barcode");
        this.notification = useService("notification");
        useBus(this.barcodeService.bus, "barcode_scanned", this.onBarcodeScanned.bind(this));
        onMounted(() => this._mountBarcodeScope());
        onWillUnmount(() => this._unmountBarcodeScope());
    }

    _getOrderLinesSignature() {
        const lines = this.props.record?.data?.lines;
        const lineRecords = lines?.records || [];
        if (lineRecords.length) {
            return JSON.stringify(
                lineRecords.map((line) => ({
                    id: line.resId || line.id || null,
                    productId:
                        line.data?.product_id?.id ||
                        line.data?.product_id?.resId ||
                        (Array.isArray(line.data?.product_id) ? line.data.product_id[0] : null),
                    qty: line.data?.qty || 0,
                }))
            );
        }
        return JSON.stringify({
            currentIds: lines?.currentIds || [],
            amountTotal: this.props.record?.data?.amount_total || 0,
        });
    }

    _notifySuccessfulScan(barcode) {
        this.notification.add(_t("Código escaneado: %s", barcode), {
            type: "success",
            title: _t("Escáner"),
            sticky: false,
        });
    }

    _mountBarcodeScope() {
        this.formElement = this.rootRef.el?.closest(".o_form_view, .o_form_renderer");
        if (!this.formElement) {
            return;
        }
        this._onKeydownCapture = this._handleKeydownCapture.bind(this);
        this.formElement.addEventListener("keydown", this._onKeydownCapture, true);
        this._markEditableElements();
        this.observer = new MutationObserver(() => this._markEditableElements());
        this.observer.observe(this.formElement, { childList: true, subtree: true });
    }

    _unmountBarcodeScope() {
        if (this.observer) {
            this.observer.disconnect();
            this.observer = null;
        }
        if (this.formElement && this._onKeydownCapture) {
            this.formElement.removeEventListener("keydown", this._onKeydownCapture, true);
            this._onKeydownCapture = null;
        }
        this._clearPendingBarcodeCapture();
        if (!this.formElement) {
            return;
        }
        for (const element of this.formElement.querySelectorAll(EDITABLE_SELECTOR)) {
            if (!element.dataset[MANAGED_DATASET_KEY]) {
                continue;
            }
            const originalValue = element.dataset[ORIGINAL_DATASET_KEY];
            if (originalValue === "__none__") {
                element.removeAttribute(BARCODE_EVENTS_ATTR);
            } else {
                element.setAttribute(BARCODE_EVENTS_ATTR, originalValue);
            }
            delete element.dataset[MANAGED_DATASET_KEY];
            delete element.dataset[ORIGINAL_DATASET_KEY];
        }
    }

    _markEditableElements() {
        for (const element of this.formElement.querySelectorAll(EDITABLE_SELECTOR)) {
            if (element.dataset[MANAGED_DATASET_KEY]) {
                continue;
            }
            element.dataset[MANAGED_DATASET_KEY] = "1";
            element.dataset[ORIGINAL_DATASET_KEY] =
                element.getAttribute(BARCODE_EVENTS_ATTR) ?? "__none__";
            element.setAttribute(BARCODE_EVENTS_ATTR, "true");
        }
    }

    _clearPendingBarcodeCapture() {
        if (this.pendingBarcodeCapture?.timeoutId) {
            clearTimeout(this.pendingBarcodeCapture.timeoutId);
        }
        this.pendingBarcodeCapture = null;
    }

    _isBarcodeSequence(rawBarcode) {
        return cleanBarcode(rawBarcode).length >= 3;
    }

    _finalizePendingBarcodeCapture() {
        const pendingBarcodeCapture = this.pendingBarcodeCapture;
        this._clearPendingBarcodeCapture();
        if (!pendingBarcodeCapture || this._isBarcodeSequence(pendingBarcodeCapture.rawBarcode)) {
            return;
        }
        applyBufferedText(
            pendingBarcodeCapture.snapshot,
            cleanBarcode(pendingBarcodeCapture.rawBarcode)
        );
    }

    _refreshPendingBarcodeCaptureTimeout() {
        if (!this.pendingBarcodeCapture) {
            return;
        }
        if (this.pendingBarcodeCapture.timeoutId) {
            clearTimeout(this.pendingBarcodeCapture.timeoutId);
        }
        this.pendingBarcodeCapture.timeoutId = setTimeout(
            () => this._finalizePendingBarcodeCapture(),
            getBarcodeTimeout()
        );
    }

    _flushBufferedBarcodeAsText(capture) {
        if (capture.timeoutId) {
            clearTimeout(capture.timeoutId);
            capture.timeoutId = null;
        }
        if (capture.rawBarcode) {
            applyBufferedText(capture.snapshot, cleanBarcode(capture.rawBarcode));
        }
        capture.rawBarcode = "";
        capture.snapshot = null;
    }

    _handleKeydownCapture(event) {
        const target = event.target;
        if (!isNodeWithin(target, this.formElement) || !isEditable(target) || !event.key) {
            return;
        }
        const endCharacter = isEndCharacter(event.key);
        if (isSpecialKey(event.key, event) && !endCharacter) {
            return;
        }

        if (!this.pendingBarcodeCapture && endCharacter) {
            return;
        }

        const now = Date.now();
        const isNewSequence =
            !this.pendingBarcodeCapture ||
            this.pendingBarcodeCapture.target !== target ||
            now - this.pendingBarcodeCapture.lastEventAt > getBarcodeTimeout();

        if (isNewSequence) {
            this._finalizePendingBarcodeCapture();
            if (endCharacter) {
                return;
            }
            this.pendingBarcodeCapture = {
                rawBarcode: "",
                snapshot: captureEditableState(target),
                target,
                poisoned: false,
            };
        }

        const capture = this.pendingBarcodeCapture;
        if (!capture) {
            return;
        }

        capture.lastEventAt = now;

        if (capture.poisoned) {
            return;
        }

        if (!endCharacter && !isNumericKey(event.key)) {
            capture.poisoned = true;
            this._flushBufferedBarcodeAsText(capture);
            return;
        }

        if (!endCharacter) {
            event.preventDefault();
            capture.rawBarcode += event.key;
            this._refreshPendingBarcodeCaptureTimeout();
            return;
        }

        if (!this._isBarcodeSequence(capture.rawBarcode)) {
            this._finalizePendingBarcodeCapture();
            return;
        }

        event.preventDefault();
        this._clearPendingBarcodeCapture();
    }

    async onBarcodeScanned(event) {
        const { barcode, target } = event.detail;
        if (!barcode || !isNodeWithin(target, this.formElement)) {
            return;
        }
        if (!isNumericBarcode(barcode)) {
            return;
        }
        this._clearPendingBarcodeCapture();
        const previousLinesSignature = this._getOrderLinesSignature();
        await this.props.record.update({ [this.props.name]: barcode });
        const nextLinesSignature = this._getOrderLinesSignature();
        if (previousLinesSignature !== nextLinesSignature) {
            this._notifySuccessfulScan(barcode);
        }
    }
}

registry.category("fields").add("pos_conventional_barcode_scanner", {
    component: PosConventionalBarcodeScannerField,
});
