from odoo import api, models


class IrActionsReport(models.Model):
    _inherit = "ir.actions.report"

    @api.model
    def print_action_for_report_name(self, *args):
        report_name = args[0] if args else self.env.context.get("report_name")
        if report_name == "pos_conventional_qztray.report_factura_simplificada_80mm_standard_qztray":
            report_name = "pos_conventional_receipt_custom.report_factura_simplificada_80mm"
        return super().print_action_for_report_name(report_name)
