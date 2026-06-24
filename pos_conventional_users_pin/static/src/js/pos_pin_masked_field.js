/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { CharField, charField } from "@web/views/fields/char/char_field";

export class PosPinMaskedField extends CharField {
    static template = "pos_conventional_users_pin.PosPinMaskedField";
}

export const posPinMaskedField = {
    ...charField,
    component: PosPinMaskedField,
    displayName: _t("PIN enmascarado"),
};

registry.category("fields").add("pos_pin_masked", posPinMaskedField);
