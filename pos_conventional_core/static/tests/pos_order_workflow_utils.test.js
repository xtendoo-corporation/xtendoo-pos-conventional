import { describe, expect, test } from "@odoo/hoot";

import {
    activateNavigationBypass,
    clearNavigationBypass,
    getRelationalValueId,
    hasRecordedPayments,
    hasRealProductLines,
    isZeroAmount,
    loadPaymentMethods,
    notifyInvalidOrderForPayment,
    payOrderWithMethod,
    shouldBlockDraftOrderLeave,
} from "../src/js/pos_order_workflow_utils";

describe.current.tags("headless");

describe("@pos_conventional_core/order_workflow_utils", () => {
    test("getRelationalValueId supports number, array and object values", async () => {
        expect(getRelationalValueId(7)).toBe(7);
        expect(getRelationalValueId([8, "x"])).toBe(8);
        expect(getRelationalValueId({ id: 9 })).toBe(9);
        expect(getRelationalValueId({ resId: 10 })).toBe(10);
        expect(getRelationalValueId(false)).toBe(false);
    });

    test("hasRealProductLines ignores notes and sections", async () => {
        const emptyRecord = {
            data: {
                lines: {
                    records: [
                        { data: { display_type: "line_note", product_id: false } },
                    ],
                },
            },
        };
        const productRecord = {
            data: {
                lines: {
                    records: [
                        { data: { display_type: "line_note", product_id: false } },
                        { data: { display_type: false, product_id: { id: 44 } } },
                    ],
                },
            },
        };

        expect(hasRealProductLines(emptyRecord)).toBe(false);
        expect(hasRealProductLines(productRecord)).toBe(true);
    });

    test("isZeroAmount allows negative totals but blocks zeros", async () => {
        expect(isZeroAmount(0)).toBe(true);
        expect(isZeroAmount(0.000001)).toBe(true);
        expect(isZeroAmount(-15)).toBe(false);
        expect(isZeroAmount(20)).toBe(false);
    });

    test("hasRecordedPayments detects payment records and amount_paid", async () => {
        expect(
            hasRecordedPayments({
                data: {
                    amount_paid: 0,
                    payment_ids: {
                        records: [{ data: { amount: 10 } }],
                    },
                },
            })
        ).toBe(true);

        expect(
            hasRecordedPayments({
                data: {
                    amount_paid: 12,
                    payment_ids: {
                        records: [],
                        currentIds: [],
                    },
                },
            })
        ).toBe(true);

        expect(
            hasRecordedPayments({
                data: {
                    amount_paid: 0,
                    payment_ids: {
                        records: [],
                        currentIds: [],
                    },
                },
            })
        ).toBe(false);
    });

    test("shouldBlockDraftOrderLeave only blocks draft orders with product lines and no payment", async () => {
        expect(
            shouldBlockDraftOrderLeave({
                data: {
                    state: "draft",
                    amount_paid: 0,
                    lines: {
                        records: [{ data: { display_type: false, product_id: { id: 5 } } }],
                    },
                    payment_ids: {
                        records: [],
                        currentIds: [],
                    },
                },
            })
        ).toBe(true);

        expect(
            shouldBlockDraftOrderLeave({
                data: {
                    state: "draft",
                    amount_paid: 10,
                    lines: {
                        records: [{ data: { display_type: false, product_id: { id: 5 } } }],
                    },
                    payment_ids: {
                        records: [{ data: { amount: 10 } }],
                        currentIds: [1],
                    },
                },
            })
        ).toBe(false);
    });

    test("loadPaymentMethods returns empty array when field has no ids", async () => {
        const result = await loadPaymentMethods({}, null);
        expect(result).toEqual([]);
    });

    test("loadPaymentMethods reads server names and keeps ids", async () => {
        const orm = {
            async read(model, ids, fields) {
                expect(model).toBe("pos.payment.method");
                expect(ids).toEqual([3, 4]);
                expect(fields).toEqual(["name"]);
                return [
                    { id: 3, name: "Cash" },
                    { id: 4, name: "Card" },
                ];
            },
        };

        const result = await loadPaymentMethods(orm, { currentIds: [3, 4] });
        expect(result).toEqual([
            { id: 3, name: "Cash" },
            { id: 4, name: "Card" },
        ]);
    });

    test("notifyInvalidOrderForPayment warns when order has no real lines", async () => {
        const notifications = [];
        const notification = {
            add(message, options) {
                notifications.push({ message, options });
            },
        };

        const valid = notifyInvalidOrderForPayment(
            {
                data: {
                    amount_total: 12,
                    lines: { records: [{ data: { display_type: "line_note", product_id: false } }] },
                },
            },
            notification
        );

        expect(valid).toBe(false);
        expect(notifications).toHaveLength(1);
        expect(notifications[0].options.title).toBe("Pedido vacío");
    });

    test("notifyInvalidOrderForPayment warns when total is zero", async () => {
        const notifications = [];
        const notification = {
            add(message, options) {
                notifications.push({ message, options });
            },
        };

        const valid = notifyInvalidOrderForPayment(
            {
                data: {
                    amount_total: 0,
                    lines: { records: [{ data: { display_type: false, product_id: { id: 5 } } }] },
                },
            },
            notification
        );

        expect(valid).toBe(false);
        expect(notifications).toHaveLength(1);
        expect(notifications[0].options.title).toBe("Importe inválido");
    });

    test("notifyInvalidOrderForPayment accepts negative totals with product lines", async () => {
        const notifications = [];
        const notification = {
            add(message, options) {
                notifications.push({ message, options });
            },
        };

        const valid = notifyInvalidOrderForPayment(
            {
                data: {
                    amount_total: -15,
                    lines: { records: [{ data: { display_type: false, product_id: { id: 5 } } }] },
                },
            },
            notification
        );

        expect(valid).toBe(true);
        expect(notifications).toHaveLength(0);
    });

    test("activateNavigationBypass and clearNavigationBypass toggle the global flag", async () => {
        window.bypassPosLeave = false;
        activateNavigationBypass(null, 5);
        expect(window.bypassPosLeave).toBe(true);
        clearNavigationBypass();
        expect(window.bypassPosLeave).toBe(false);
    });

    test("payOrderWithMethod stops before RPC when order is invalid", async () => {
        const notifications = [];
        const record = {
            data: {
                amount_total: 0,
                lines: { records: [] },
            },
            async save() {
                throw new Error("No debería intentar guardar un pedido inválido");
            },
        };

        const result = await payOrderWithMethod({
            record,
            methodId: 7,
            orm: {},
            action: {},
            notification: {
                add(message, options) {
                    notifications.push({ message, options });
                },
            },
        });

        expect(result.success).toBe(false);
        expect(result.reason).toBe("invalid_order");
        expect(notifications).toHaveLength(1);
    });

    test("payOrderWithMethod saves, triggers RPC and executes the returned action", async () => {
        const callOrder = [];
        const record = {
            resId: 22,
            data: {
                amount_total: 35,
                lines: {
                    records: [{ data: { display_type: false, product_id: { id: 11 } } }],
                },
            },
            async save() {
                callOrder.push("save");
                return true;
            },
            async load() {
                callOrder.push("load");
            },
        };
        const orm = {
            async call(model, method, args) {
                callOrder.push("rpc");
                expect(model).toBe("pos.order");
                expect(method).toBe("action_pos_convention_pay_with_method");
                expect(args).toEqual([22, 4]);
                return { type: "ir.actions.client", tag: "pos_conventional_new_order" };
            },
        };
        const action = {
            async doAction(serverAction) {
                callOrder.push("action");
                expect(serverAction.tag).toBe("pos_conventional_new_order");
            },
        };

        const result = await payOrderWithMethod({
            record,
            methodId: 4,
            orm,
            action,
            notification: { add() {} },
        });

        expect(result.success).toBe(true);
        expect(callOrder).toEqual(["save", "rpc", "action"]);
        clearNavigationBypass();
    });

    test("payOrderWithMethod reloads the order and clears bypass when server returns no action", async () => {
        const callOrder = [];
        const record = {
            resId: 23,
            data: {
                amount_total: 40,
                lines: {
                    records: [{ data: { display_type: false, product_id: { id: 12 } } }],
                },
            },
            async save() {
                callOrder.push("save");
                return true;
            },
            async load() {
                callOrder.push("load");
            },
        };

        const result = await payOrderWithMethod({
            record,
            methodId: 8,
            orm: {
                async call() {
                    callOrder.push("rpc");
                    return false;
                },
            },
            action: {
                async doAction() {
                    throw new Error("No debería ejecutar acción si el servidor no devuelve ninguna");
                },
            },
            notification: { add() {} },
        });

        expect(result.success).toBe(false);
        expect(result.reason).toBe("missing_action");
        expect(callOrder).toEqual(["save", "rpc", "load"]);
        expect(window.bypassPosLeave).toBe(false);
    });
});

