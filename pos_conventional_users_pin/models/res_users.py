from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ResUsers(models.Model):
    _inherit = "res.users"

    pos_pin = fields.Char(
        string="PIN POS",
        help="PIN exclusivo para el punto de venta convencional.",
    )

    @api.constrains("pos_pin")
    def _check_pos_pin_unique(self):
        for record in self:
            if record.pos_pin:
                duplicate = self.env["res.users"].sudo().search(
                    [("pos_pin", "=", record.pos_pin), ("id", "!=", record.id)], limit=1
                )
                if duplicate:
                    raise ValidationError(
                        _(
                            "El PIN '%s' ya está en uso por el usuario '%s'. "
                            "Por favor, elija un PIN diferente."
                        )
                        % (record.pos_pin, duplicate.name)
                    )
