from odoo import api, models


class ReportSaleDetailsExtended(models.AbstractModel):
    _inherit = "report.point_of_sale.report_saledetails"

    @api.model
    def get_sale_details(
        self, date_start=False, date_stop=False, config_ids=False, session_ids=False, **kwargs
    ):
        result = super().get_sale_details(
            date_start, date_stop, config_ids, session_ids, **kwargs
        )

        linked_domain = [("linked_sale_order_id", "!=", False)]

        if session_ids:
            linked_domain.append(("session_id", "in", session_ids))
        else:
            date_start_dt, date_stop_dt = self._get_date_start_and_date_stop(
                date_start, date_stop
            )
            linked_domain.append(("date_order", ">=", date_start_dt))
            linked_domain.append(("date_order", "<=", date_stop_dt))
            if config_ids:
                linked_domain.append(("config_id", "in", config_ids))

        linked_orders = self.env["pos.order"].search(linked_domain)

        result["customer_account"] = {
            "total": sum(order.amount_total for order in linked_orders),
            "count": len(linked_orders),
            "orders": [
                {
                    "pos_order_name": order.name,
                    "sale_order_name": order.linked_sale_order_id.name
                    if order.linked_sale_order_id
                    else "N/A",
                    "partner_name": order.partner_id.name
                    if order.partner_id
                    else "Cliente genérico",
                    "amount_total": order.amount_total,
                    "date_order": order.date_order,
                }
                for order in linked_orders
            ],
        }
        return result

