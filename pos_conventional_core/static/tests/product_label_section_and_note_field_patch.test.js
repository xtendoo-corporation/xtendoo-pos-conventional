import { describe, expect, test } from "@odoo/hoot";

import "../src/js/product_label_section_and_note_field_patch";

import { ProductLabelSectionAndNoteField } from "@account/components/product_label_section_and_note_field/product_label_section_and_note_field";

describe.current.tags("headless");

function makeField({
    resModel,
    readonly = false,
    columnIsProductAndLabel = true,
    label = "",
} = {}) {
    const field = Object.create(ProductLabelSectionAndNoteField.prototype);
    field.props = {
        readonly,
        record: { resModel },
    };
    field.columnIsProductAndLabel = { value: columnIsProductAndLabel };
    Object.defineProperty(field, "label", {
        configurable: true,
        get: () => label,
    });
    return field;
}

function makeEnterEvent() {
    return {
        key: "Enter",
        altKey: false,
        ctrlKey: false,
        metaKey: false,
        shiftKey: false,
        stopPropagation: () => expect.step("stopPropagation"),
        preventDefault: () => expect.step("preventDefault"),
    };
}

test("pos.order.line disables the label visibility toggler", () => {
    expect(makeField({ resModel: "pos.order.line" }).showLabelVisibilityToggler).toBe(false);
});

test("other models keep the standard label toggler behavior", () => {
    expect(makeField({ resModel: "sale.order.line" }).showLabelVisibilityToggler).toBe(true);
    expect(makeField({ resModel: "sale.order.line", label: "Etiqueta" }).showLabelVisibilityToggler).toBe(false);
    expect(makeField({ resModel: "sale.order.line", readonly: true }).showLabelVisibilityToggler).toBe(false);
    expect(
        makeField({ resModel: "sale.order.line", columnIsProductAndLabel: false }).showLabelVisibilityToggler
    ).toBe(false);
});

test("enter does not hijack the product selection flow on pos.order.line", () => {
    const field = makeField({ resModel: "pos.order.line" });
    field.switchLabelVisibility = () => expect.step("switchLabelVisibility");

    field.onM2oInputKeydown(makeEnterEvent());

    expect.verifySteps([]);
});

test("enter keeps the standard label toggle behavior on other models", () => {
    const field = makeField({ resModel: "sale.order.line" });
    field.switchLabelVisibility = () => expect.step("switchLabelVisibility");

    field.onM2oInputKeydown(makeEnterEvent());

    expect.verifySteps(["switchLabelVisibility", "stopPropagation", "preventDefault"]);
});

