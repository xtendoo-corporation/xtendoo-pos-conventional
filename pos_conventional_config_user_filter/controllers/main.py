from odoo import http
from odoo.http import request
from odoo.addons.point_of_sale.controllers.main import PosController


class PosConfigUserFilterController(PosController):
    @http.route()
    def pos_web(self, config_id=False, from_backend=False, subpath=None, **k):
        user = request.env.user
        if not user._is_internal():
            return request.not_found()

        if config_id:
            pos_config = request.env["pos.config"].sudo().browse(int(config_id)).exists()
            if not user._can_access_pos_config(pos_config):
                return request.not_found()

        return super().pos_web(
            config_id=config_id,
            from_backend=from_backend,
            subpath=subpath,
            **k,
        )


