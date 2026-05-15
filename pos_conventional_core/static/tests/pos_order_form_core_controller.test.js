import { describe, expect, test } from "@odoo/hoot";

import { PosConventionalOrderFormController } from "../src/js/pos_order_form_core_controller";
import { FormController } from "@web/views/form/form_controller";

describe.current.tags("headless");

describe("@pos_conventional_core/order_form_core_controller", () => {
    function makeController() {
        const notifications = [];
        const controller = Object.create(PosConventionalOrderFormController.prototype);
        controller.notification = {
            add(message, options) {
                notifications.push({ message, options });
            },
        };
        controller.notifications = notifications;
        return controller;
    }

    test("_hasProductLines only returns true when there is at least one real product line", async () => {
        const controller = makeController();
        const record = {
            data: {
                lines: {
                    records: [
                        {
                            data: {
                                display_type: "line_section",
                                product_id: false,
                            },
                        },
                        {
                            data: {
                                display_type: false,
                                product_id: { id: 44, display_name: "Producto RPC" },
                            },
                        },
                    ],
                },
            },
        };

        expect(controller._hasProductLines(record)).toBe(true);
    });

    test("beforeLeave allows leaving draft orders without product lines", async () => {
        const controller = makeController();
        controller.model = {
            root: {
                data: {
                    state: "draft",
                    lines: {
                        records: [
                            {
                                data: {
                                    display_type: "line_note",
                                    product_id: false,
                                },
                            },
                        ],
                    },
                },
            },
        };
        controller._playErrorBeep = () => {
            throw new Error("No debería sonar si no hay líneas de producto");
        };

        const originalBeforeLeave = FormController.prototype.beforeLeave;
        FormController.prototype.beforeLeave = async () => "super-before-leave";

        try {
            const result = await controller.beforeLeave({});
            expect(result).toBe("super-before-leave");
            expect(controller.notifications).toHaveLength(0);
        } finally {
            FormController.prototype.beforeLeave = originalBeforeLeave;
        }
    });

    test("beforeLeave blocks leaving draft orders with product lines and no payment", async () => {
        const controller = makeController();
        controller.model = {
            root: {
                data: {
                    state: "draft",
                    amount_paid: 0,
                    lines: {
                        records: [
                            {
                                data: {
                                    display_type: false,
                                    product_id: { id: 55, display_name: "Producto bloqueante" },
                                },
                            },
                        ],
                    },
                    payment_ids: {
                        records: [],
                        currentIds: [],
                    },
                },
            },
        };
        let notified = 0;
        controller._notifyBlockedOrderLeave = () => {
            notified++;
        };

        const originalBeforeLeave = FormController.prototype.beforeLeave;
        FormController.prototype.beforeLeave = async () => {
            throw new Error("No debería delegar a super cuando el pedido tiene productos");
        };

        try {
            const result = await controller.beforeLeave({});
            expect(result).toBe(false);
            expect(notified).toBe(1);
        } finally {
            FormController.prototype.beforeLeave = originalBeforeLeave;
        }
    });

    test("beforeLeave allows leaving draft orders with product lines when a payment is already registered", async () => {
        const controller = makeController();
        controller.model = {
            root: {
                data: {
                    state: "draft",
                    amount_paid: 15,
                    lines: {
                        records: [
                            {
                                data: {
                                    display_type: false,
                                    product_id: { id: 77, display_name: "Producto con pago" },
                                },
                            },
                        ],
                    },
                    payment_ids: {
                        records: [
                            {
                                data: {
                                    amount: 15,
                                },
                            },
                        ],
                        currentIds: [1],
                    },
                },
            },
        };
        controller._notifyBlockedOrderLeave = () => {
            throw new Error("No debería bloquear si ya hay pago registrado");
        };

        const originalBeforeLeave = FormController.prototype.beforeLeave;
        FormController.prototype.beforeLeave = async () => "super-before-leave";

        try {
            const result = await controller.beforeLeave({});
            expect(result).toBe("super-before-leave");
            expect(controller.notifications).toHaveLength(0);
        } finally {
            FormController.prototype.beforeLeave = originalBeforeLeave;
        }
    });

    test("_onPaymentButtonClick allows cancel to activate the navigation bypass", async () => {
        const controller = makeController();
        const record = {
            resId: 88,
            data: {
                amount_total: 0,
                lines: {
                    records: [],
                    currentIds: [],
                },
            },
        };
        controller.model = { root: record };
        let bypassCalls = 0;
        controller._activateNavigationBypass = (currentRecord) => {
            bypassCalls++;
            expect(currentRecord).toBe(record);
        };

        const button = document.createElement("button");
        button.name = "action_cancel_and_delete_order";
        document.body.appendChild(button);

        let prevented = false;
        let stopped = false;
        controller._onPaymentButtonClick({
            target: button,
            preventDefault() {
                prevented = true;
            },
            stopImmediatePropagation() {
                stopped = true;
            },
        });

        expect(bypassCalls).toBe(1);
        expect(prevented).toBe(false);
        expect(stopped).toBe(false);
        button.remove();
    });

    test("_onPaymentButtonClick blocks empty or zero-total orders", async () => {
        const controller = makeController();
        controller.model = {
            root: {
                data: {
                    amount_total: 0,
                    lines: {
                        records: [],
                        currentIds: [],
                    },
                },
            },
        };
        let beepCalls = 0;
        controller._playErrorBeep = () => {
            beepCalls++;
        };

        const button = document.createElement("button");
        button.name = "action_open_payment_popup";
        document.body.appendChild(button);

        let prevented = false;
        let stopped = false;
        controller._onPaymentButtonClick({
            target: button,
            preventDefault() {
                prevented = true;
            },
            stopImmediatePropagation() {
                stopped = true;
            },
        });

        expect(prevented).toBe(true);
        expect(stopped).toBe(true);
        expect(beepCalls).toBe(1);
        expect(controller.notifications).toHaveLength(1);
        expect(controller.notifications[0].options.title).toBe("Importe inválido");
        button.remove();
    });

    test("_onPaymentButtonClick activates bypass for valid orders", async () => {
        const controller = makeController();
        const record = {
            resId: 109,
            data: {
                amount_total: 50,
                lines: {
                    records: [
                        {
                            data: {
                                display_type: false,
                                product_id: { id: 5, display_name: "Producto válido" },
                            },
                        },
                    ],
                    currentIds: [1],
                },
            },
        };
        controller.model = { root: record };
        let bypassCalls = 0;
        controller._activateNavigationBypass = (currentRecord) => {
            bypassCalls++;
            expect(currentRecord).toBe(record);
        };

        const button = document.createElement("button");
        button.name = "action_open_payment_popup";
        document.body.appendChild(button);

        controller._onPaymentButtonClick({
            target: button,
            preventDefault() {
                throw new Error("No debería bloquear un pedido válido");
            },
            stopImmediatePropagation() {
                throw new Error("No debería bloquear un pedido válido");
            },
        });

        expect(bypassCalls).toBe(1);
        expect(controller.notifications).toHaveLength(0);
        button.remove();
    });

    test("_onDocClick activates bypass for stock forecast navigation", async () => {
        const controller = makeController();
        const record = { resId: 201 };
        controller.model = { root: record };
        let bypassArgs = null;
        controller._activateNavigationBypass = (currentRecord, timeout) => {
            bypassArgs = { currentRecord, timeout };
        };

        const button = document.createElement("button");
        button.name = "action_open_stock_forecast";
        document.body.appendChild(button);

        controller._onDocClick({ target: button });

        expect(bypassArgs).toEqual({ currentRecord: record, timeout: 2000 });
        button.remove();
    });
});

