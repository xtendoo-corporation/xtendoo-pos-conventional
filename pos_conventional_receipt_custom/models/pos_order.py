from odoo import api, fields, models, _

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
