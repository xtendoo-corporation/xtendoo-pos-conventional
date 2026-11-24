import "@pos_conventional_barcode_scanner/js/pos_conventional_barcode_scanner_field";

import { beforeEach, destroy, expect, test } from "@odoo/hoot";
import { animationFrame } from "@odoo/hoot-mock";
import { contains, defineModels, fields, models, mountView, patchWithCleanup } from "@web/../tests/web_test_helpers";
import { PosDataService } from "@point_of_sale/app/services/data_service";
import { posService } from "@point_of_sale/app/services/pos_store";
import { contextualUtilsService } from "@point_of_sale/app/services/contextual_utils_service";
import { barcodeService } from "@barcodes/barcode_service";
import { defineMailModels } from "@mail/../tests/mail_test_helpers";

class SaleOrder extends models.Model {
    name = fields.Char({ string: "Reference" });
    partner_name = fields.Char({ string: "Customer" });
    _barcode_scanned = fields.Char({ string: "Barcode Scanned" });

    _records = [{ id: 1, name: "POS/0001", partner_name: "Cliente Barcode", _barcode_scanned: "" }];
}

// mail está instalado (point_of_sale depende de él) y su servicio consulta discuss.channel.
defineMailModels();
defineModels([SaleOrder]);

beforeEach(() => {
    // El bundle del backend incluye el servicio «pos_data» de point_of_sale y los que
    // dependen de él («pos», utilidades contextuales): al arrancar consultan pos.config y
    // el almacenamiento del TPV, y eso no es lo que se prueba aquí.
    patchWithCleanup(PosDataService, {
        async start() {
            return {};
        },
    });
    patchWithCleanup(posService, {
        async start() {
            return {};
        },
    });
    patchWithCleanup(contextualUtilsService, {
        start() {
            return {};
        },
    });
    patchWithCleanup(barcodeService, {
        maxTimeBetweenKeysInMs: 0,
    });
});

test("scanner widget enables barcode capture on regular editable fields inside the pos order form", async () => {
    const view = await mountView({
        type: "form",
        resModel: "sale.order",
        resId: 1,
        arch: /* xml */ `
            <form>
                <field name="name"/>
                <field name="partner_name"/>
                <field name="_barcode_scanned" widget="pos_conventional_barcode_scanner"/>
            </form>
        `,
    });

    const onBarcodeScanned = (event) => {
        expect.step(event.detail.barcode);
    };
    view.env.services.barcode.bus.addEventListener("barcode_scanned", onBarcodeScanned);

    const internalInput = document.querySelector(".o_field_widget[name=partner_name] input");

    expect(".o_field_widget[name=partner_name] input").toHaveAttribute("barcode_events", "true");

    await contains(".o_field_widget[name=partner_name] input").focus();
    view.env.services.barcode.bus.trigger("barcode_scanned", {
        barcode: "SCAN001",
        target: internalInput,
    });
    await animationFrame();

    expect.verifySteps(["SCAN001"]);
    expect(".o_field_widget[name=partner_name] input").toBeFocused();

    view.env.services.barcode.bus.removeEventListener("barcode_scanned", onBarcodeScanned);
});

test("scanner widget only updates the record for events coming from its form", async () => {
    const view = await mountView({
        type: "form",
        resModel: "sale.order",
        resId: 1,
        arch: /* xml */ `
            <form>
                <field name="name"/>
                <field name="partner_name"/>
                <field name="_barcode_scanned" widget="pos_conventional_barcode_scanner"/>
            </form>
        `,
    });

    const internalInput = document.querySelector(".o_field_widget[name=partner_name] input");
    const externalInput = document.createElement("input");
    document.body.append(externalInput);

    view.env.services.barcode.bus.trigger("barcode_scanned", {
        barcode: "OUTSIDE",
        target: externalInput,
    });
    await animationFrame();
    expect(view.model.root.data._barcode_scanned).toBe("");

    view.env.services.barcode.bus.trigger("barcode_scanned", {
        barcode: "5012345678900",
        target: internalInput,
    });
    await animationFrame();
    expect(view.model.root.data._barcode_scanned).toBe("5012345678900");

    view.env.services.barcode.bus.trigger("barcode_scanned", {
        barcode: "",
        target: internalInput,
    });
    await animationFrame();
    expect(view.model.root.data._barcode_scanned).toBe("DIRECT001");

    externalInput.remove();
});

test("scanner widget restores managed barcode_events attributes on unmount", async () => {
    const view = await mountView({
        type: "form",
        resModel: "sale.order",
        resId: 1,
        arch: /* xml */ `
            <form>
                <field name="name"/>
                <field name="partner_name"/>
                <field name="_barcode_scanned" widget="pos_conventional_barcode_scanner"/>
            </form>
        `,
    });

    const formElement = document.querySelector(".o_form_view, .o_form_renderer");
    const managedInput = document.querySelector(".o_field_widget[name=partner_name] input");
    const preconfiguredInput = document.createElement("input");
    preconfiguredInput.setAttribute("barcode_events", "false");
    formElement.append(preconfiguredInput);
    await animationFrame();

    expect(managedInput.getAttribute("barcode_events")).toBe("true");
    expect(preconfiguredInput.getAttribute("barcode_events")).toBe("true");

    destroy(view);
    await animationFrame();

    expect(managedInput.getAttribute("barcode_events")).toBe(null);
    expect(preconfiguredInput.getAttribute("barcode_events")).toBe("false");
});

test("scanner widget keeps the original field value while the barcode is processed", async () => {
    const view = await mountView({
        type: "form",
        resModel: "sale.order",
        resId: 1,
        arch: /* xml */ `
            <form>
                <field name="name"/>
                <field name="partner_name"/>
                <field name="_barcode_scanned" widget="pos_conventional_barcode_scanner"/>
            </form>
        `,
    });

    const internalInput = document.querySelector(".o_field_widget[name=partner_name] input");
    internalInput.value = "Cliente Barcode";

    for (const key of ["1", "2", "3", "4", "0", "0", "1", "Enter"]) {
        const event = new KeyboardEvent("keydown", { bubbles: true, cancelable: true, key });
        internalInput.dispatchEvent(event);
        expect(event.defaultPrevented).toBe(true);
    }
    expect(internalInput.value).toBe("Cliente Barcode");

    view.env.services.barcode.bus.trigger("barcode_scanned", {
        barcode: "1234001",
        target: internalInput,
    });
    await animationFrame();

    expect(internalInput.value).toBe("Cliente Barcode");
    expect(view.model.root.data._barcode_scanned).toBe("1234001");
});

test("scanner widget does not block browser paste shortcuts", async () => {
    await mountView({
        type: "form",
        resModel: "sale.order",
        resId: 1,
        arch: /* xml */ `
            <form>
                <field name="name"/>
                <field name="partner_name"/>
                <field name="_barcode_scanned" widget="pos_conventional_barcode_scanner"/>
            </form>
        `,
    });

    const internalInput = document.querySelector(".o_field_widget[name=partner_name] input");
    const event = new KeyboardEvent("keydown", {
        bubbles: true,
        cancelable: true,
        ctrlKey: true,
        key: "v",
    });
    internalInput.dispatchEvent(event);

    expect(event.defaultPrevented).toBe(false);
});

test("scanner widget does not require cleanBarcode on the started barcode service", async () => {
    const view = await mountView({
        type: "form",
        resModel: "sale.order",
        resId: 1,
        arch: /* xml */ `
            <form>
                <field name="name"/>
                <field name="partner_name"/>
                <field name="_barcode_scanned" widget="pos_conventional_barcode_scanner"/>
            </form>
        `,
    });

    const internalInput = document.querySelector(".o_field_widget[name=partner_name] input");

    expect(view.env.services.barcode.cleanBarcode).toBe(undefined);

    for (const key of ["1", "2", "3"]) {
        const event = new KeyboardEvent("keydown", { bubbles: true, cancelable: true, key });
        internalInput.dispatchEvent(event);
        expect(event.defaultPrevented).toBe(true);
    }

    view.env.services.barcode.bus.trigger("barcode_scanned", {
        barcode: "123",
        target: internalInput,
    });
    await animationFrame();

    expect(view.model.root.data._barcode_scanned).toBe("123");
});

test("scanner widget does not hijack non-numeric fast typing", async () => {
    await mountView({
        type: "form",
        resModel: "sale.order",
        resId: 1,
        arch: /* xml */ `
            <form>
                <field name="name"/>
                <field name="partner_name"/>
                <field name="_barcode_scanned" widget="pos_conventional_barcode_scanner"/>
            </form>
        `,
    });

    const internalInput = document.querySelector(".o_field_widget[name=partner_name] input");

    for (const key of ["a", "b", "c"]) {
        const event = new KeyboardEvent("keydown", { bubbles: true, cancelable: true, key });
        internalInput.dispatchEvent(event);
        expect(event.defaultPrevented).toBe(false);
    }
});

test("scanner widget restores buffered digits when a non-numeric key breaks the sequence", async () => {
    await mountView({
        type: "form",
        resModel: "sale.order",
        resId: 1,
        arch: /* xml */ `
            <form>
                <field name="name"/>
                <field name="partner_name"/>
                <field name="_barcode_scanned" widget="pos_conventional_barcode_scanner"/>
            </form>
        `,
    });

    const internalInput = document.querySelector(".o_field_widget[name=partner_name] input");
    internalInput.value = "";
    internalInput.setSelectionRange(0, 0);

    for (const key of ["1", "2"]) {
        const event = new KeyboardEvent("keydown", { bubbles: true, cancelable: true, key });
        internalInput.dispatchEvent(event);
        expect(event.defaultPrevented).toBe(true);
    }

    const breakingEvent = new KeyboardEvent("keydown", { bubbles: true, cancelable: true, key: "a" });
    internalInput.dispatchEvent(breakingEvent);

    expect(breakingEvent.defaultPrevented).toBe(false);
    expect(internalInput.value).toBe("12");
});

test("scanner widget ignores non-numeric barcode events", async () => {
    const view = await mountView({
        type: "form",
        resModel: "sale.order",
        resId: 1,
        arch: /* xml */ `
            <form>
                <field name="name"/>
                <field name="partner_name"/>
                <field name="_barcode_scanned" widget="pos_conventional_barcode_scanner"/>
            </form>
        `,
    });

    const internalInput = document.querySelector(".o_field_widget[name=partner_name] input");

    view.env.services.barcode.bus.trigger("barcode_scanned", {
        barcode: "ABC123",
        target: internalInput,
    });
    await animationFrame();
    expect(view.model.root.data._barcode_scanned).toBe("");

    view.env.services.barcode.bus.trigger("barcode_scanned", {
        barcode: "999",
        target: internalInput,
    });
    await animationFrame();
    expect(view.model.root.data._barcode_scanned).toBe("999");
});

