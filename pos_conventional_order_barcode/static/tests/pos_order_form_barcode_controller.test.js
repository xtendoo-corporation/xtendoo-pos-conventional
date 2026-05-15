import { describe, expect, test } from "@odoo/hoot";

import { PosOrderBarcodeFormController } from "@pos_conventional_order_barcode/js/pos_order_form_barcode_controller";

describe.current.tags("headless");

describe("@pos_conventional_order_barcode/barcode_controller", () => {
    function makeController() {
        const notifications = [];
        const controller = Object.create(PosOrderBarcodeFormController.prototype);
        controller.notification = {
            add(message, options) {
                notifications.push({ message, options });
            },
        };
        controller._blurActiveElement = () => {};
        controller.notifications = notifications;
        return controller;
    }

    test("addLineLocally accumulates quantity for repeated scans in a new order", async () => {
        const controller = makeController();
        const existingLine = {
            data: {
                product_id: { id: 11 },
                qty: 2,
            },
            async update(vals) {
                this.data = {
                    ...this.data,
                    ...vals,
                };
            },
        };
        const record = {
            data: {
                lines: {
                    records: [existingLine],
                    async addNewRecord() {
                        throw new Error("No debe crear una línea nueva al escanear el mismo producto");
                    },
                },
            },
        };
        const product = { id: 11, display_name: "Producto Barcode Test" };
        const lineVals = { qty: 1 };

        const line = await controller.addLineLocally(record, product, lineVals);

        expect(line).toBe(existingLine);
        expect(existingLine.data.qty).toBe(3);
        expect(controller.notifications).toHaveLength(1);
        expect(controller.notifications[0].options.type).toBe("success");
    });

    test("addLineLocally also accumulates quantity when the product many2one stores resId", async () => {
        const controller = makeController();
        const existingLine = {
            data: {
                product_id: { resId: 11, display_name: "Producto Barcode Test" },
                qty: 2,
            },
            async update(vals) {
                this.data = {
                    ...this.data,
                    ...vals,
                };
            },
        };
        const record = {
            data: {
                lines: {
                    records: [existingLine],
                    async addNewRecord() {
                        throw new Error("No debe crear una línea nueva cuando resId coincide");
                    },
                },
            },
        };

        const line = await controller.addLineLocally(
            record,
            { id: 11, display_name: "Producto Barcode Test" },
            { qty: 1 }
        );

        expect(line).toBe(existingLine);
        expect(existingLine.data.qty).toBe(3);
        expect(controller.notifications).toHaveLength(1);
        expect(controller.notifications[0].options.type).toBe("success");
    });

    test("addLineLocally creates a new line with barcode values in a new order", async () => {
        const controller = makeController();
        const newLine = {
            data: {},
            async update(vals) {
                this.data = {
                    ...this.data,
                    ...vals,
                };
            },
        };
        let addNewRecordCalls = 0;
        const record = {
            data: {
                lines: {
                    records: [],
                    async addNewRecord({ mode, position }) {
                        addNewRecordCalls++;
                        expect(mode).toBe("edit");
                        expect(position).toBe("bottom");
                        return newLine;
                    },
                },
            },
        };
        const product = { id: 22, display_name: "Producto Nuevo" };
        const lineVals = {
            full_product_name: "Producto Nuevo",
            qty: 2,
            price_unit: 14.5,
            discount: 5,
        };

        const line = await controller.addLineLocally(record, product, lineVals);

        expect(line).toBe(newLine);
        expect(addNewRecordCalls).toBe(1);
        expect(newLine.data.product_id).toEqual({
            id: 22,
            display_name: "Producto Nuevo",
        });
        expect(newLine.data.full_product_name).toBe("Producto Nuevo");
        expect(newLine.data.qty).toBe(2);
        expect(newLine.data.price_unit).toBe(14.5);
        expect(newLine.data.discount).toBe(5);
        expect(controller.notifications).toHaveLength(1);
        expect(controller.notifications[0].options.type).toBe("success");
    });

    test("addLineLocally warns when the order lines one2many is not available", async () => {
        const controller = makeController();
        const record = { data: {} };

        const line = await controller.addLineLocally(
            record,
            { id: 77, display_name: "Producto sin líneas" },
            { qty: 1, price_unit: 2.5 }
        );

        expect(line).toBe(null);
        expect(controller.notifications).toHaveLength(1);
        expect(controller.notifications[0].options.type).toBe("warning");
    });

    test("processBarcode blurs focus, resolves the barcode and then adds the product without saving a new order", async () => {
        const controller = makeController();
        const product = { id: 33, display_name: "Producto Local" };
        const lineVals = { qty: 1, price_unit: 9.99, discount: 0, full_product_name: "Producto Local" };
        const callOrder = [];
        const record = {
            isNew: true,
            resId: 91,
            data: {
                pricelist_id: false,
                fiscal_position_id: false,
                partner_id: false,
            },
            async save() {
                throw new Error("No debería guardar un pedido nuevo antes de escanear");
            },
        };
        controller.model = { root: record };
        controller.minBarcodeLength = 3;
        controller.isProcessing = false;
        controller._blurActiveElement = () => {
            callOrder.push("blur");
        };
        controller.orm = {
            async call(model, method, args, kwargs) {
                callOrder.push("lookup");
                expect(model).toBe("pos.order");
                expect(method).toBe("get_product_line_data_by_barcode");
                expect(args).toEqual([]);
                expect(kwargs.barcode).toBe("123456");
                return { success: true, product, line_vals: lineVals };
            },
        };
        controller.addProductToLines = async (currentProduct, currentLineVals, currentRecord) => {
            callOrder.push("add");
            expect(currentProduct).toBe(product);
            expect(currentLineVals).toBe(lineVals);
            expect(currentRecord).toBe(record);
        };

        await controller.processBarcode("123456");

        expect(callOrder).toEqual(["blur", "lookup", "add"]);
        expect(controller.isProcessing).toBe(false);
    });

    test("addProductToLines adds the scanned product locally on an unsaved order", async () => {
        const controller = makeController();
        const product = { id: 41, display_name: "Producto Nuevo Local" };
        const lineVals = { qty: 1, price_unit: 12.0, discount: 0.0 };
        const record = {
            isNew: true,
            resId: false,
            data: {
                lines: {
                    records: [],
                    async addNewRecord() {
                        return {
                            data: {},
                            async update(vals) {
                                this.data = { ...this.data, ...vals };
                            },
                        };
                    },
                },
            },
        };
        controller.model = { root: record };
        controller.addLineViaRPC = async () => {
            throw new Error("No debería usar RPC en un pedido no guardado");
        };

        await controller.addProductToLines(product, lineVals);

        expect(controller.notifications).toHaveLength(1);
        expect(controller.notifications[0].options.type).toBe("success");
    });

    test("addProductToLines keeps using local lines when a saved order has pending changes", async () => {
        const controller = makeController();
        const product = { id: 43, display_name: "Producto Dirty" };
        const lineVals = { qty: 1, price_unit: 13.0, discount: 0.0 };
        const record = {
            isNew: false,
            resId: 145,
            async isDirty() {
                return true;
            },
            data: {
                lines: {
                    records: [],
                    async addNewRecord() {
                        return {
                            data: {},
                            async update(vals) {
                                this.data = { ...this.data, ...vals };
                            },
                        };
                    },
                },
            },
        };
        controller.model = { root: record };
        controller.addLineViaRPC = async () => {
            throw new Error("No debería usar RPC si el pedido tiene cambios pendientes");
        };

        await controller.addProductToLines(product, lineVals);

        expect(controller.notifications).toHaveLength(1);
        expect(controller.notifications[0].options.type).toBe("success");
    });

    test("addProductToLines adds the scanned product through RPC on an already saved order", async () => {
        const controller = makeController();
        const product = { id: 44, display_name: "Producto RPC" };
        const lineVals = { qty: 1, price_unit: 15.0, discount: 0.0 };
        let rpcCalls = 0;
        controller.model = {
            root: {
                isNew: false,
                resId: 108,
                async isDirty() {
                    return false;
                },
            },
        };
        controller.addLineViaRPC = async (orderId, currentProduct, currentLineVals) => {
            rpcCalls++;
            expect(orderId).toBe(108);
            expect(currentProduct).toBe(product);
            expect(currentLineVals).toBe(lineVals);
        };

        await controller.addProductToLines(product, lineVals);

        expect(rpcCalls).toBe(1);
    });


    test("addLineViaRPC reloads, saves the order and clears focus after adding the scanned product", async () => {
        const controller = makeController();
        const product = { id: 55, display_name: "Producto Guardado" };
        const lineVals = { qty: 1, price_unit: 7.5, discount: 0.0 };
        const callOrder = [];

        controller.orm = {
            async call(model, method, args, kwargs) {
                callOrder.push("rpc");
                expect(model).toBe("pos.order");
                expect(method).toBe("add_product_by_barcode");
                expect(args).toEqual([205]);
                expect(kwargs).toEqual({
                    product_id: 55,
                    line_vals: lineVals,
                });
                return {
                    success: true,
                    message: "Añadido: Producto Guardado",
                };
            },
        };
        controller.model = {
            root: {
                async load() {
                    callOrder.push("load");
                },
                async save() {
                    callOrder.push("save");
                },
            },
        };
        controller._blurActiveElement = ({ immediate } = {}) => {
            callOrder.push(immediate ? "blur-immediate" : "blur-delayed");
        };

        await controller.addLineViaRPC(205, product, lineVals);

        expect(callOrder).toEqual(["rpc", "load", "blur-immediate", "save", "blur-delayed"]);
        expect(controller.notifications).toHaveLength(1);
        expect(controller.notifications[0].options.type).toBe("success");
    });

    test("_blurActiveElement removes focus from generic focusable elements in the editable line", async () => {
        const controller = Object.create(PosOrderBarcodeFormController.prototype);
        controller.blurFocusTarget = null;
        const focusedButton = document.createElement("button");
        focusedButton.type = "button";
        focusedButton.textContent = "focusable";
        document.body.appendChild(focusedButton);
        focusedButton.focus();

        expect(document.activeElement).toBe(focusedButton);

        controller._blurActiveElement({ immediate: true });

        expect(document.activeElement).not.toBe(focusedButton);
        controller.blurFocusTarget?.remove();
        focusedButton.remove();
    });

    test("_tryCleanupManualLineFocus blurs manual focus inside the lines one2many row", async () => {
        const controller = Object.create(PosOrderBarcodeFormController.prototype);
        controller.manualLineFocusCleanupTimeout = null;
        controller.manualLineFocusCleanupAttempts = 0;
        controller.manualLineFocusCleanupObserver = {
            disconnect() {},
        };
        let blurCalls = 0;
        controller._blurActiveElement = ({ immediate } = {}) => {
            expect(immediate).toBe(true);
            blurCalls++;
        };

        const field = document.createElement("div");
        field.className = "o_field_widget";
        field.setAttribute("name", "lines");
        field.innerHTML = `
            <table>
                <tbody>
                    <tr class="o_data_row">
                        <td><button type="button">Producto</button></td>
                    </tr>
                </tbody>
            </table>
        `;
        document.body.appendChild(field);
        const focusable = field.querySelector("button");
        focusable.focus();

        controller._tryCleanupManualLineFocus();

        expect(blurCalls).toBe(1);
        field.remove();
    });

    function expectManualTypingAllowedInLines({ inputAttributes = {}, key = "1" } = {}) {
        const controller = makeController();
        controller.barcodeBuffer = "";
        controller.lastKeyTime = 0;
        controller.maxTimeBetweenKeys = 150;
        controller.minBarcodeLength = 3;
        let cleanupCalls = 0;
        controller._stopManualLineFocusCleanup = () => {
            cleanupCalls++;
        };
        let blurCalls = 0;
        controller._blurActiveElement = ({ immediate } = {}) => {
            expect(immediate).toBe(true);
            blurCalls++;
        };

        const field = document.createElement("div");
        field.className = "o_field_widget";
        field.setAttribute("name", "lines");
        const input = document.createElement("input");
        Object.entries(inputAttributes).forEach(([attribute, value]) => {
            input.setAttribute(attribute, value);
        });
        field.appendChild(input);
        document.body.appendChild(field);

        let prevented = false;
        let stopped = false;
        const ev = {
            key,
            target: input,
            preventDefault() {
                prevented = true;
            },
            stopPropagation() {
                stopped = true;
            },
        };

        controller.onKeyDown(ev);

        expect(cleanupCalls).toBe(1);
        expect(blurCalls).toBe(0);
        expect(prevented).toBe(false);
        expect(stopped).toBe(false);
        expect(controller.barcodeBuffer).toBe("");
        field.remove();
    }

    test("onKeyDown allows manual typing in the product input inside lines", async () => {
        expectManualTypingAllowedInLines({
            inputAttributes: {
                name: "product_id",
                placeholder: "Código o producto",
            },
            key: "7",
        });
    });

    test("onKeyDown allows manual typing in the qty input inside lines", async () => {
        expectManualTypingAllowedInLines({
            inputAttributes: {
                name: "qty",
                inputmode: "decimal",
            },
            key: "3",
        });
    });

    test("onKeyDown allows manual typing in the discount input inside lines", async () => {
        expectManualTypingAllowedInLines({
            inputAttributes: {
                name: "discount",
                inputmode: "decimal",
            },
            key: "5",
        });
    });

    test("onKeyDown preserves manual line editing for product, qty and discount inputs", async () => {
        const editableLineInputs = [
            {
                inputAttributes: {
                    name: "product_id",
                    placeholder: "Código o producto",
                },
                key: "7",
            },
            {
                inputAttributes: {
                    name: "qty",
                    inputmode: "decimal",
                },
                key: "3",
            },
            {
                inputAttributes: {
                    name: "discount",
                    inputmode: "decimal",
                },
                key: "5",
            },
        ];

        editableLineInputs.forEach((inputSpec) => {
            expectManualTypingAllowedInLines(inputSpec);
        });
    });

    test("onKeyDown still buffers barcode keys on non-editable targets inside lines", async () => {
        const controller = makeController();
        controller.barcodeBuffer = "";
        controller.lastKeyTime = 0;
        controller.maxTimeBetweenKeys = 150;
        controller.minBarcodeLength = 3;
        controller._stopManualLineFocusCleanup = () => {
            throw new Error("No debe limpiar foco si el target no es editable");
        };

        const field = document.createElement("div");
        field.className = "o_field_widget";
        field.setAttribute("name", "lines");
        const button = document.createElement("button");
        button.type = "button";
        field.appendChild(button);
        document.body.appendChild(field);

        let prevented = false;
        let stopped = false;
        const ev = {
            key: "1",
            target: button,
            preventDefault() {
                prevented = true;
            },
            stopPropagation() {
                stopped = true;
            },
        };

        controller.onKeyDown(ev);

        expect(prevented).toBe(true);
        expect(stopped).toBe(true);
        expect(controller.barcodeBuffer).toBe("1");
        field.remove();
    });

    test("onKeyDown still ignores editable targets outside lines", async () => {
        const controller = makeController();
        controller.barcodeBuffer = "";
        controller.lastKeyTime = 0;

        const input = document.createElement("input");
        document.body.appendChild(input);

        const ev = {
            key: "1",
            target: input,
            preventDefault() {
                throw new Error("No debería prevenir el evento fuera de lines");
            },
            stopPropagation() {
                throw new Error("No debería parar el evento fuera de lines");
            },
        };

        controller.onKeyDown(ev);

        expect(controller.barcodeBuffer).toBe("");
        input.remove();
    });
});

