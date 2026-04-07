from odoo import api, fields, models, _
from odoo.exceptions import UserError

class PosOrder(models.Model):
    _inherit = "pos.order"

    def get_factura_report_url(self):
        """
        Devuelve la URL del informe de factura simplificada para este pedido.
        """
        self.ensure_one()
        if not self.account_move:
            return False

        report_xmlid = "pos_conventional_receipt_custom.report_factura_simplificada_80mm"
        return f"/report/html/{report_xmlid}/{self.account_move.id}"

    def action_print_factura_simplificada(self):
        self.ensure_one()
        if not self.account_move:
            return
        return self.env.ref("pos_conventional_receipt_custom.action_factura_simplificada_80mm").report_action(self.account_move)

    def action_send_email(self):
        """
        Envía el ticket de compra por correo electrónico al cliente.
        """
        self.ensure_one()
        if not self.account_move:
            raise UserError(_("Este pedido no tiene una factura asociada para enviar."))

        if not self.partner_id:
            raise UserError(_("Debe seleccionar un cliente para enviar el correo."))

        if not self.partner_id.email:
            raise UserError(_("El cliente '%s' no tiene email configurado.") % self.partner_id.name)

        template = self.env.ref("pos_conventional_receipt_custom.email_template_pos_receipt", raise_if_not_found=False)
        if not template:
            raise UserError(_("No se encontró la plantilla de email para el ticket POS."))

        return {
            "type": "ir.actions.act_window",
            "res_model": "mail.compose.message",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_model": "account.move",
                "default_res_ids": [self.account_move.id],
                "default_template_id": template.id,
                "default_composition_mode": "comment",
                "force_email": True,
            },
        }

    @api.model
    def get_order_receipt_data(self, order_id):
        """
        Extensión del ticket 80mm con datos adicionales de empresa y detalles de impuestos.

        Este método es invocado por pos_conventional_core.get_order_receipt_data a través
        de la cadena super(). Devuelve ÚNICAMENTE los campos adicionales que core mergeará
        sobre los datos base que ya construye. No se llama a super() aquí porque el siguiente
        en la cadena sería el pos.order base, que no define este método.
        """
        order = self.browse(order_id)
        if not order.exists():
            return {}

        return {
            "company": {
                "phone": order.company_id.phone or "",
                "email": order.company_id.email or "",
                "address": order.company_id.partner_id._display_address(without_company=True),
            },
            "tax_details": order._get_receipt_tax_details(),
        }

    def _get_receipt_tax_details(self):
        self.ensure_one()
        tax_details = []
        # Agrupar impuestos por nombre/base
        for line in self.lines:
            taxes = line.tax_ids_after_fiscal_position.compute_all(
                line.price_unit * (1 - (line.discount or 0.0) / 100.0),
                self.currency_id, line.qty, line.product_id, self.partner_id)
            for tax in taxes['taxes']:
                existing = next((t for t in tax_details if t['id'] == tax['id']), None)
                if existing:
                    existing['amount'] += tax['amount']
                    existing['base'] += tax['base']
                else:
                    tax_details.append({
                        'id': tax['id'],
                        'name': tax['name'],
                        'amount': tax['amount'],
                        'base': tax['base'],
                    })
        return tax_details
