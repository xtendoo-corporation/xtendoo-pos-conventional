const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const { join } = require("node:path");
const { test } = require("node:test");
const vm = require("node:vm");

const source = readFileSync(
    join(__dirname, "../src/js/pos_receipt_qztray_patch.js"),
    "utf8"
).replace(/^import .*;\r?$/gm, "");

function makeRuntime({ failure, failPrint = false, missingQz = false } = {}) {
    const notifications = [];
    const warnings = [];
    const prints = [];
    const actions = [];
    const categories = new Map();
    class PosReceiptClientAction {}
    const qz = {
        security: {
            setCertificatePromise() {},
            setSignatureAlgorithm() {},
            setSignaturePromise() {},
        },
        websocket: {
            isActive: () => false,
            async connect() {
                if (failure && !failPrint) {
                    throw failure;
                }
            },
        },
        printers: { find: async (name) => name },
        configs: { create: (printer) => ({ printer }) },
        async print(...args) {
            if (failure && failPrint) {
                throw failure;
            }
            prints.push(args);
        },
    };
    const env = {
        services: {
            notification: { add: (...args) => notifications.push(args) },
            orm: {
                async call(model, method) {
                    if (method === "print_action_for_report_name") {
                        return { id: 1, action: "server", backend: "qztray", printer_name: "Ticket" };
                    }
                    assert.equal(method, "get_qz_tray_data");
                    return ["ticket-data"];
                },
            },
            action: { doAction: (...args) => actions.push(args) },
        },
    };
    const context = vm.createContext({
        _t: (message) => message,
        patch: (target, methods) => Object.assign(target, methods),
        registry: {
            category(name) {
                if (!categories.has(name)) {
                    categories.set(name, new Map());
                }
                const entries = categories.get(name);
                return {
                    contains: (key) => entries.has(key),
                    get: (key) => entries.get(key),
                    add: (key, value) => entries.set(key, value),
                };
            },
        },
        useService: (name) => env.services[name],
        PosReceiptClientAction,
        console: { log() {}, warn: (...args) => warnings.push(args) },
        window: { qz: missingQz ? undefined : qz, focus() {} },
        qz,
    });
    vm.runInContext(source, context);
    async function run(path) {
        const params = { use_qztray: true, order_id: 12, print_original_receipt: path === "original" };
        if (path === "window") {
            params.next_action = { type: "ir.actions.act_window_close" };
            await categories.get("actions").get("pos_conventional_print_receipt_qztray_window")(
                env, { params }
            );
        } else {
            const action = Object.create(PosReceiptClientAction.prototype);
            Object.assign(action, {
                env, orm: env.services.orm, notification: env.services.notification,
                props: { action: { params } },
            });
            await action._printReportBackground(12);
            await new Promise(setImmediate);
        }
    }
    return { notifications, warnings, prints, actions, run, context, env, categories };
}

for (const path of ["background", "original", "window"]) {
    for (const failure of [
        new Error("Unable to establish connection with QZ"),
        new Error("Printer unavailable"),
    ]) {
        test(`${path}: ${failure.message} is logged without a popup`, async () => {
            const runtime = makeRuntime({ failure, failPrint: failure.message === "Printer unavailable" });
            await runtime.run(path);
            assert.equal(runtime.notifications.length, 0);
            assert.equal(runtime.warnings.length, 1);
            assert.equal(runtime.warnings[0][1], failure);
            assert.equal(runtime.prints.length, 0);
            assert.equal(runtime.actions.length, path === "window" ? 1 : 0);
        });
    }

    test("repeated QZ failures do not accumulate popups", async () => {
        const runtime = makeRuntime({ failure: new Error("Unable to establish connection with QZ") });
        for (let attempt = 0; attempt < 3; attempt++) {
            await runtime.run("window");
        }
        assert.equal(runtime.notifications.length, 0);
        assert.equal(runtime.warnings.length, 3);
        assert.equal(runtime.actions.length, 3);
    });

    test("browser printing errors still notify the user", async () => {
        const runtime = makeRuntime();
        runtime.context.URL = URL;
        runtime.context.window.location = { origin: "https://odoo.example.test" };
        runtime.context.document = {
            body: { appendChild() {} },
            createElement() {
                return {
                    style: {},
                    remove() {},
                    set src(value) {
                        queueMicrotask(() => this.onerror());
                    },
                };
            },
        };
        await runtime.categories.get("actions").get("pos_conventional_print_receipt_window")(
            runtime.env, { params: { use_qztray: false, move_id: 12 } }
        );
        assert.equal(runtime.notifications.length, 1);
        assert.equal(runtime.notifications[0][1].type, "danger");
    });
    test(`${path}: missing QZ does not create a popup`, async () => {
        const runtime = makeRuntime({ missingQz: true });
        await runtime.run(path);
        assert.equal(runtime.notifications.length, 0);
        assert.equal(runtime.warnings.length, 1);
        assert.equal(runtime.prints.length, 0);
    });
    test(`${path}: available QZ still prints`, async () => {
        const runtime = makeRuntime();
        await runtime.run(path);
        assert.equal(runtime.prints.length, 1);
        assert.equal(runtime.warnings.length, 0);
        assert.equal(runtime.notifications.length, 0);
    });
}
