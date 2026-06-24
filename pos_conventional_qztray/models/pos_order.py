from odoo import models


class PosOrder(models.Model):
    _inherit = "pos.order"

    def _pos_conventional_qztray_enrich_print_action(self, action):
        self.ensure_one()
        if not isinstance(action, dict):
            return action
        if action.get("tag") not in (
            "pos_conventional_print_receipt_client",
            "pos_conventional_print_receipt_window",
        ):
            return action

        params = dict(action.get("params") or {})
        params["use_qztray"] = bool(
            self.config_id.iface_print_auto
            and self.config_id.pos_print_receipt_with_qztray
        )
        original_report_name = "pos_conventional_receipt_custom.report_factura_simplificada_80mm"
        params.setdefault("report_name", original_report_name)
        if params["use_qztray"]:
            params["printer_report_name"] = original_report_name
            params["report_name"] = "pos_conventional_qztray.report_pos_order_80mm_qztray"
            params["report_res_id"] = self.id
        action["params"] = params
        if params["use_qztray"] and action.get("tag") == "pos_conventional_print_receipt_window":
            action["tag"] = "pos_conventional_print_receipt_qztray_window"
        return action

    def _get_post_validation_action(self):
        action = super()._get_post_validation_action()
        return self._pos_conventional_qztray_enrich_print_action(action)
