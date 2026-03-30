from odoo import api, fields, models, _

class PosSession(models.Model):
    _inherit = "pos.session"

    def _get_captured_payments_domain(self):
        """
        Excluye pagos de pedidos vinculados a sale.order (Albarán) del cálculo del balance.
        """
        # IDs de pedidos vinculados
        linked_order_ids = self.order_ids.filtered(lambda o: hasattr(o, 'linked_sale_order_id') and o.linked_sale_order_id).ids
        
        # Obtener dominio original
        domain = super()._get_captured_payments_domain()
        
        if linked_order_ids:
            domain.append(("pos_order_id", "not in", linked_order_ids))
            
        return domain

    def _get_closed_orders(self):
        """
        Excluye pedidos vinculados a sale.order del proceso de cierre contable de la sesión.
        """
        orders = super()._get_closed_orders()
        return orders.filtered(lambda o: not (hasattr(o, 'linked_sale_order_id') and o.linked_sale_order_id))
