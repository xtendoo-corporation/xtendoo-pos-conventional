/** @odoo-module **/

import { ProductLabelSectionAndNoteField } from "@account/components/product_label_section_and_note_field/product_label_section_and_note_field";
import { patch } from "@web/core/utils/patch";

patch(ProductLabelSectionAndNoteField.prototype, {
    get showLabelVisibilityToggler() {
        if (this.props.record.resModel === "pos.order.line") {
            return false;
        }
        return super.showLabelVisibilityToggler;
    },

    /**
     * En pos.order.line, la tecla Enter debe seguir el flujo normal del many2one
     * para permitir buscar/seleccionar productos por código o barcode.
     *
     * El comportamiento estándar del widget combinado usa Enter para abrir el
     * campo de descripción cuando no hay etiqueta. En el one2many de POS esto
     * rompe la selección rápida desde teclado, por lo que delegamos al comportamiento
     * base sin interceptar el evento.
     *
     * @param {KeyboardEvent} ev
     */
    onM2oInputKeydown(ev) {
        if (this.props.record.resModel === "pos.order.line") {
            return;
        }
        return super.onM2oInputKeydown(ev);
    },
});

