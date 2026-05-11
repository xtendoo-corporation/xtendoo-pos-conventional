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
                    async addNewRecord({ position }) {
                        addNewRecordCalls++;
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

    test("addProductToLines uses local flow and saves the new order after barcode scans", async () => {
        const controller = makeController();
        const product = { id: 33, display_name: "Producto Local" };
        const lineVals = { qty: 1, price_unit: 9.99, discount: 0 };
        let localAddCalls = 0;
        let saveCalls = 0;
        const record = {
            isNew: true,
            data: {},
            async save() {
                saveCalls++;
            },
        };
        controller.model = { root: record };
        controller.addLineLocally = async (currentRecord, currentProduct, currentLineVals) => {
            localAddCalls++;
            expect(currentRecord).toBe(record);
            expect(currentProduct).toBe(product);
            expect(currentLineVals).toBe(lineVals);
        };

        await controller.addProductToLines(product, lineVals);

        expect(localAddCalls).toBe(1);
        expect(saveCalls).toBe(1);
    });
});

