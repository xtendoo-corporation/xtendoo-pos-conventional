from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)

class PosOrder(models.Model):
    _inherit = "pos.order"

    available_payment_method_ids = fields.Many2many(
        "pos.payment.method",
        compute="_compute_available_payment_methods",
        string="Métodos de pago disponibles",
        help="Métodos de pago configurados para el punto de venta de esta sesión",
    )

    @api.depends("session_id.config_id.payment_method_ids")
    def _compute_available_payment_methods(self):
        for order in self:
            if order.session_id and order.session_id.config_id:
                order.available_payment_method_ids = order.session_id.config_id.payment_method_ids
            else:
                order.available_payment_method_ids = False

    def get_payment_popup_data(self):
        """
        Devuelve los datos necesarios para el popup de pago avanzado.
        """
        self.ensure_one()
        # Forzar recálculo
        self._compute_amounts()
        
        methods = []
        for pm in self.config_id.payment_method_ids:
            methods.append({
                'id': pm.id,
                'name': pm.name,
                'type': pm.type,
                'icon': "fa-money" if pm.journal_id.type == "cash" else "fa-credit-card",
            })

        payments = []
        for p in self.payment_ids:
            payments.append({
                'id': p.id,
                'payment_method_id': p.payment_method_id.id,
                'payment_method_name': p.payment_method_id.name,
                'amount': p.amount,
            })

        return {
            'order_id': self.id,
            'amount_total': self.amount_total,
            'amount_paid': self.amount_paid,
            'amount_due': self.amount_total - self.amount_paid,
            'currency_symbol': self.currency_id.symbol,
            'available_methods': methods,
            'payments': payments,
        }

    def action_register_payments_and_validate(self, payments, print_invoice=False):
        """
        Registra múltiples pagos y valida el pedido.
        """
        self.ensure_one()
        if self.state != 'draft':
            return {'success': False, 'message': _("El pedido ya no está en borrador.")}

        # 1. Eliminar pagos existentes para evitar duplicados si se re-intenta
        self.payment_ids.unlink()

        # 2. Registrar nuevos pagos
        for p in payments:
            self.add_payment({
                'pos_order_id': self.id,
                'amount': p['amount'],
                'payment_method_id': p['payment_method_id'],
            })

        # 3. Comprobar cambio si sobra dinero (efectivo)
        amount_paid = sum(self.payment_ids.mapped('amount'))
        if amount_paid > self.amount_total:
            change = amount_paid - self.amount_total
            cash_method = self.config_id.payment_method_ids.filtered(lambda m: m.is_cash_count)[:1]
            if cash_method:
                self.add_payment({
                    'pos_order_id': self.id,
                    'amount': -change,
                    'payment_method_id': cash_method.id,
                    'is_change': True,
                })

        # 4. Validar y facturar
        return {'success': True, 'action': self.action_validate_and_invoice()}

    def action_pos_convention_pay_with_method(self, method_id):
        """
        Pago rápido con un solo método (el importe total pendiente).
        """
        self.ensure_one()
        due = self.amount_total - self.amount_paid
        if due <= 0:
            return self.action_validate_and_invoice()

        self.add_payment({
            'pos_order_id': self.id,
            'amount': due,
            'payment_method_id': method_id,
        })
        
        return self.action_validate_and_invoice()
