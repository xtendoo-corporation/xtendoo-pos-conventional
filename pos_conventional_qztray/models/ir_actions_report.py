from odoo import api, models


class IrActionsReport(models.Model):
    _inherit = "ir.actions.report"

    @api.model
    def print_action_for_report_name(self, *args):
        report_name = args[0] if args else self.env.context.get("report_name")
        print(f"DEBUG QZ TRAY: Intentando imprimir reporte original: {report_name}")

        # Alias para asegurar que siempre usemos el reporte configurado de QZ Tray
        custom_report = "pos_conventional_qztray.report_pos_order_80mm_qztray"
        legacy_reports = [
            "pos_conventional_qztray.report_factura_simplificada_80mm_standard_qztray",
            "pos_conventional_receipt_custom.report_pos_order_80mm",
            "pos_conventional_receipt_custom.report_factura_simplificada_80mm",
            "point_of_sale.report_receipt",
            "point_of_sale.pos_invoice_report",
        ]

        if report_name in legacy_reports:
            print(f"DEBUG QZ TRAY: Redirigiendo {report_name} -> {custom_report}")
            report_name = custom_report

        res = super().print_action_for_report_name(report_name)
        print(f"DEBUG QZ TRAY: Reporte final: {report_name} | Action ID: {res.get('id') if isinstance(res, dict) else 'N/A'}")
        return res

    def get_qz_tray_data(self, res_ids, report_type="pdf", report_name="", data=None):
        print(f"DEBUG QZ TRAY: get_qz_tray_data llamado con report_name={report_name}")

        custom_report = "pos_conventional_qztray.report_pos_order_80mm_qztray"
        legacy_reports = [
            "pos_conventional_qztray.report_factura_simplificada_80mm_standard_qztray",
            "pos_conventional_receipt_custom.report_pos_order_80mm",
            "pos_conventional_receipt_custom.report_factura_simplificada_80mm",
            "point_of_sale.report_receipt",
            "point_of_sale.pos_invoice_report",
        ]

        if report_name in legacy_reports:
            print(f"DEBUG QZ TRAY: get_qz_tray_data REDIRIGIENDO {report_name} -> {custom_report}")
            report_name = custom_report

        return super().get_qz_tray_data(res_ids, report_type=report_type, report_name=report_name, data=data)
