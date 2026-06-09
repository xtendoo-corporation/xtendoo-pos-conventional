from odoo import models, api

class PosConfig(models.Model):
    _inherit = 'pos.config'

    @api.model
    def _search(self, domain, offset=0, limit=None, order=None, **kwargs):
        if self._context.get('allow_all_pos'):
             return super(PosConfig, self.with_context(active_test=False).sudo())._search(
                 domain, offset=offset, limit=limit, order=order, **kwargs
             )
        return super()._search(domain, offset=offset, limit=limit, order=order, **kwargs)
