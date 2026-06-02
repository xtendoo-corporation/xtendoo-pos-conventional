from odoo import api, models
from odoo.fields import Domain


class ReportPointOfSaleReportSaledetails(models.AbstractModel):
    _inherit = 'report.point_of_sale.report_saledetails'

    def _prepare_get_sale_details_args_kwargs(self, data):
        args, kwargs = super()._prepare_get_sale_details_args_kwargs(data)
        kwargs['pos_order_ids'] = data.get('pos_order_ids', [])
        return args, kwargs

    def _get_domain(self, date_start=False, date_stop=False, config_ids=False, session_ids=False, **kwargs):
        pos_order_ids = kwargs.get('pos_order_ids', [])

        # Remove custom kwargs before passing to super to avoid TypeError
        clean_kwargs = {k: v for k, v in kwargs.items() if k not in ['pos_order_ids']}

        # Get the base domain (with date filters)
        domain = super()._get_domain(date_start, date_stop, config_ids, session_ids, **clean_kwargs)

        # If specific orders selected, add as additional filter (AND with dates)
        if pos_order_ids:
            domain = domain & Domain('id', 'in', pos_order_ids)

        return domain

    @api.model
    def get_sale_details(self, date_start=False, date_stop=False, config_ids=False, session_ids=False, **kwargs):
        # Save wizard dates before super() can overwrite them with session data
        wizard_date_start = date_start
        wizard_date_stop = date_stop

        res = super().get_sale_details(date_start, date_stop, config_ids, session_ids, **kwargs)

        domain = self._get_domain(date_start, date_stop, config_ids, session_ids, **kwargs)
        orders = self.env['pos.order'].search(domain, order='date_order asc')

        employee_sales_data = {}
        for order in orders:
            for line in order.lines:
                employees = line.employee_ids
                if not employees:
                    continue

                try:
                    line_total = float(line.price_subtotal or 0.0)
                except Exception:
                    line_total = float(
                        (line.qty or 0.0)
                        * (line.price_unit or 0.0)
                        * (1.0 - (line.discount or 0.0) / 100.0)
                    )

                amount_per_employee = line_total / len(employees)
                product_name = (
                    line.full_product_name
                    or (line.product_id.display_name if line.product_id else '')
                )
                date_order = (
                    order.date_order.strftime('%d/%m/%Y %H:%M')
                    if order.date_order else ''
                )

                for employee in employees:
                    if employee.id not in employee_sales_data:
                        employee_sales_data[employee.id] = {
                            'employee_name': employee.name,
                            'lines': [],
                            'total_amount': 0.0,
                        }
                    employee_sales_data[employee.id]['lines'].append({
                        'order_name': order.name or '',
                        'product_name': product_name,
                        'date': date_order,
                        'line_total': line_total,
                        'employee_amount': amount_per_employee,
                    })
                    employee_sales_data[employee.id]['total_amount'] += amount_per_employee

        employee_sales_grouped = list(employee_sales_data.values())
        employee_sales_grouped.sort(key=lambda x: x['employee_name'])

        pos_order_names = []
        if kwargs.get('pos_order_ids'):
            pos_order_names = [o.name for o in orders]

        res['employee_sales_grouped'] = employee_sales_grouped
        res['pos_order_names'] = pos_order_names

        # Restore wizard dates so the template always renders them (super() may overwrite with session dates)
        if wizard_date_start:
            res['date_start'] = wizard_date_start
        if wizard_date_stop:
            res['date_stop'] = wizard_date_stop

        return res
