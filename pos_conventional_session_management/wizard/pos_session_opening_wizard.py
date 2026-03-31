from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class PosSessionOpeningWizard(models.TransientModel):
    _name = 'pos.session.opening.wizard'
    _description = 'Wizard para apertura de sesión POS no táctil'

    session_id = fields.Many2one('pos.session', string='Sesión', required=True, readonly=True)
    user_id = fields.Many2one('res.users', string='Usuario', required=True, readonly=True,
                              default=lambda self: self.env.user)
    cash_register_balance_start = fields.Float(
        string='Caja de apertura',
        digits=(16, 2),
        default=0.0
    )
    opening_notes = fields.Text(
        string='Nota de apertura',
    )
    currency_id = fields.Many2one('res.currency', related='session_id.currency_id', readonly=True)
    cash_control = fields.Boolean(related='session_id.cash_control', readonly=True)
    pending_order_count = fields.Integer(
        string='Pedidos pendientes',
        compute='_compute_pending_order_count'
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        session_id = res.get('session_id') or self.env.context.get('default_session_id') or self.env.context.get('active_id')
        if session_id:
            session = self.env['pos.session'].browse(session_id)
            if session.exists():
                if 'cash_register_balance_start' in fields_list:
                    res['cash_register_balance_start'] = session.cash_register_balance_start
        return res

    @api.depends('session_id')
    def _compute_pending_order_count(self):
        for wizard in self:
            if wizard.session_id and wizard.session_id.config_id:
                orders = self.env['pos.order'].search([
                    ('config_id', '=', wizard.session_id.config_id.id),
                    ('state', '=', 'draft'),
                ])
                wizard.pending_order_count = len(orders.filtered(lambda o: o.lines))
            else:
                wizard.pending_order_count = 0

    def action_validate_and_open(self):
        self.ensure_one()
        self._open_session_backend()
        return self._return_to_backend()

    def action_open_cash_calculator(self):
        self.ensure_one()
        # Note: We can expand this to link to the cash calculator if needed
        # but for now we follow the structure.
        return {
            'name': _('Calculadora de Efectivo'),
            'type': 'ir.actions.act_window',
            'res_model': 'pos.cash.calculator.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                **self.env.context,
                # Link to a potential field in calculator if we add it
            },
        }

    def _validate_user_pin(self, vals=None):
        if vals:
            session_id = vals["session_id"]
            user_id = vals["user_id"]
            pos_pin = vals["pos_pin"]
        else:
            self.ensure_one()
            session_id = self.session_id
            user_id = self.user_id
            pos_pin = getattr(self, "pos_pin", None)

        if not self.env.user.has_group("point_of_sale.group_pos_user"):
            raise UserError(_("No tiene permisos para abrir una sesión de Punto de Venta."))

        user = self.env["res.users"].search(
            [("pos_pin", "=", pos_pin), ("id", "=", user_id.id)], limit=1
        )
        if not user:
            raise ValidationError(
                _(
                    "PIN incorrecto para el usuario %s. Por favor, verifique su PIN e intente nuevamente."
                )
                % user_id.name
            )

        if session_id and session_id.user_id != user:
            session_id.sudo().write({"user_id": user.id})

        return user

    def _open_session_backend(self):
        self.ensure_one()
        session = self.session_id
        if session.state != "opening_control":
            raise UserError(_("Esta sesión ya no está en estado de apertura."))
        values = {
            'state': 'opened',
            'start_at': fields.Datetime.now(),
        }
        if session.cash_control:
            values['cash_register_balance_start'] = self.cash_register_balance_start
        if self.opening_notes:
            values['opening_notes'] = self.opening_notes
        session.write(values)
        return True

    def _return_to_backend(self):
        self.ensure_one()
        config_sessions = self.env["pos.session"].search([
            ("config_id", "=", self.session_id.config_id.id)
        ])
        action = self.env.ref("point_of_sale.action_pos_pos_form").read()[0]
        action["domain"] = [("session_id", "in", config_sessions.ids)]
        action["context"] = {
            "default_session_id": self.session_id.id,
        }
        return action
