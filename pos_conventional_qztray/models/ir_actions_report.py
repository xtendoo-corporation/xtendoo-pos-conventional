from odoo import models


class IrActionsReport(models.Model):
    _inherit = "ir.actions.report"

    def print_action_for_report_name(self, report_name):
        if report_name == "pos_conventional_qztray.report_factura_simplificada_80mm_standard_qztray":
            report_name = "pos_conventional_receipt_custom.report_factura_simplificada_80mm"
        return super().print_action_for_report_name(report_name)