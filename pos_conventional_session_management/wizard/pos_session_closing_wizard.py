from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import float_is_zero


class PosSessionClosingWizard(models.TransientModel):
    _name = "pos.session.closing.wizard"
    _description = "Wizard para cierre de sesión POS no táctil"

    session_id = fields.Many2one(
        "pos.session", string="Sesión", required=True, readonly=True
    )
    cash_register_balance_end_real = fields.Float(
        string="Recuento de efectivo",
        help="Cantidad total de dinero en efectivo contado al cerrar la caja",
        default=0.0,
    )
    currency_id = fields.Many2one(
        "res.currency", related="session_id.currency_id", readonly=True
    )
    cash_control = fields.Boolean(related="session_id.cash_control", readonly=True)
    cash_register_balance_start = fields.Monetary(
        string="Dinero inicial",
        related="session_id.cash_register_balance_start",
        readonly=True,
    )
    cash_register_balance_end = fields.Monetary(
        string="Dinero teórico",
        related="session_id.cash_register_balance_end",
        readonly=True,
        help="Dinero inicial + ventas en efectivo - devoluciones",
    )
    cash_register_difference = fields.Monetary(
        string="Diferencia",
        compute="_compute_difference",
        store=True,
        help="Diferencia entre dinero contado y dinero teórico",
    )
    closing_note = fields.Text(
        string="Motivo del cierre",
        help="Nota opcional explicando el motivo del cierre de la sesión",
    )
    state = fields.Selection(
        [("input", "Entrada"), ("confirmation", "Confirmación")],
        default="input",
        string="Estado",
    )

    # Campos para mostrar resumen de la sesión
    total_payments = fields.Monetary(
        string="Total de pagos", compute="_compute_session_totals", readonly=True
    )
    cash_in_out_total = fields.Monetary(
        string="Entradas/Salidas de efectivo",
        compute="_compute_session_totals",
        readonly=True,
    )
    payment_method_line_ids = fields.One2many(
        comodel_name="pos.session.closing.payment.line",
        inverse_name="wizard_id",
        string="Líneas de métodos de pago",
    )
    cash_in_out_line_ids = fields.Many2many(
        comodel_name="account.bank.statement.line",
        compute="_compute_cash_in_out_lines",
        string="Movimientos de caja",
        readonly=True,
    )

    @api.depends("session_id")
    def _compute_session_totals(self):
        for wizard in self:
            total = 0.0
            for payment in wizard.session_id.order_ids.mapped("payment_ids"):
                total += payment.amount

            wizard.total_payments = total
            wizard.cash_in_out_total = sum(wizard.session_id.statement_line_ids.mapped('amount'))

    @api.depends("cash_register_balance_end_real", "cash_register_balance_end")
    def _compute_difference(self):
        for wizard in self:
            wizard.cash_register_difference = (
                wizard.cash_register_balance_end_real - wizard.cash_register_balance_end
            )

    @api.depends("session_id")
    def _compute_cash_in_out_lines(self):
        for wizard in self:
            lines = wizard.session_id.statement_line_ids.sorted(lambda l: (l.date or fields.Date.today(), l.id))
            wizard.cash_in_out_line_ids = [(6, 0, lines.ids)]

    @api.model_create_multi
    def create(self, vals_list):
        wizards = super().create(vals_list)
        for wizard in wizards:
            if wizard.session_id and wizard.session_id.config_id:
                payment_methods = wizard.session_id.config_id.payment_method_ids
                lines_vals = []
                for method in payment_methods:
                    total_expected = sum(
                        payment.amount
                        for payment in wizard.session_id.order_ids.mapped("payment_ids")
                        if payment.payment_method_id == method
                    )
                    if total_expected > 0 or method.is_cash_count:
                        lines_vals.append((0, 0, {
                            'payment_method_id': method.id,
                            'amount_expected': total_expected,
                            'amount_counted': total_expected,
                        }))
                if lines_vals:
                    wizard.write({'payment_method_line_ids': lines_vals})
        return wizards

    def action_close_session(self):
        self.ensure_one()
        session = self.session_id
        print(
            f"\n[CERRAR CAJA][WIZARD] action_close_session"
            f" — wizard #{self.id} sesión #{session.id}"
            f" state_wizard={self.state} state_session={session.state}"
            f" cash_control={session.cash_control}"
        )

        if session.state == "closed":
            print("[CERRAR CAJA][WIZARD]   → BLOQUEADO: sesión ya cerrada")
            raise UserError(_("Esta sesión ya está cerrada."))
        if session.state not in ["opened", "closing_control"]:
            print(f"[CERRAR CAJA][WIZARD]   → BLOQUEADO: estado inválido '{session.state}'")
            raise UserError(_("Solo puedes cerrar sesiones en estado abierto o en proceso de cierre."))

        # 0. Cancelar pedidos en borrador vacíos (sin líneas) para que no bloqueen el cierre
        empty_draft_orders = self.env["pos.order"].search([
            ("session_id", "=", session.id),
            ("state", "=", "draft"),
            ("lines", "=", False),
        ])
        print(f"[CERRAR CAJA][WIZARD]   paso 0: pedidos vacíos en borrador = {len(empty_draft_orders)}")
        if empty_draft_orders:
            empty_draft_orders.write({"state": "cancel"})
            print(f"[CERRAR CAJA][WIZARD]   paso 0: cancelados {empty_draft_orders.mapped('name')}")

        # Verificar que no queden pedidos en borrador CON líneas (no cerrados)
        real_draft_orders = self.env["pos.order"].search([
            ("session_id", "=", session.id),
            ("state", "=", "draft"),
        ])
        if real_draft_orders:
            print(f"[CERRAR CAJA][WIZARD]   → BLOQUEADO: pedidos con líneas en borrador: {real_draft_orders.mapped('name')}")
            raise UserError(_(
                "No puedes cerrar la caja mientras hay pedidos en borrador sin completar. "
                "Por favor, finaliza o cancela los pedidos pendientes antes de cerrar."
            ))

        # 1. Registrar efectivo contado (solo si hay control de caja)
        if session.cash_control:
            print(f"[CERRAR CAJA][WIZARD]   paso 1: post_closing_cash_details({self.cash_register_balance_end_real})")
            result = session.post_closing_cash_details(self.cash_register_balance_end_real)
            print(f"[CERRAR CAJA][WIZARD]   paso 1 result: {result}")
            if not result.get("successful"):
                raise UserError(result.get("message", _("Error al registrar el efectivo.")))

            diff = self.cash_register_balance_end_real - session.cash_register_balance_end
            print(f"[CERRAR CAJA][WIZARD]   paso 1: diff={diff} wizard.state={self.state}")
            if self.state == "input" and not float_is_zero(diff, precision_rounding=self.currency_id.rounding):
                self.write({"state": "confirmation"})
                print("[CERRAR CAJA][WIZARD]   → abriendo confirmación de diferencia")
                return {
                    "type": "ir.actions.act_window",
                    "res_model": "pos.session.closing.wizard",
                    "view_mode": "form",
                    "res_id": self.id,
                    "target": "new",
                }

        # 2. Mover sesión a estado de cierre y guardar nota
        if session.state == "opened":
            print(f"[CERRAR CAJA][WIZARD]   paso 2: update_closing_control_state_session('{self.closing_note or ''}')")
            session.update_closing_control_state_session(self.closing_note or "")

        # 3. Construir diferencias de métodos de pago bancarios
        bank_diffs = [
            [line.payment_method_id.id, line.difference]
            for line in self.payment_method_line_ids
            if not line.is_cash and not float_is_zero(line.difference, precision_rounding=self.currency_id.rounding)
        ]
        print(f"[CERRAR CAJA][WIZARD]   paso 3: bank_diffs={bank_diffs}")

        # 4. Cerrar la sesión usando el mismo método que el popup OWL
        print("[CERRAR CAJA][WIZARD]   paso 4: close_session_from_ui...")
        close_result = session.close_session_from_ui(bank_diffs)
        print(f"[CERRAR CAJA][WIZARD]   paso 4 result: {close_result}")
        if not close_result.get("successful"):
            raise UserError(close_result.get("message", _("Error al cerrar la sesión.")))

        # 5. Navegar al kanban de POS
        print("[CERRAR CAJA][WIZARD]   paso 5: sesión cerrada → devolviendo acción kanban")
        return {
            "type": "ir.actions.act_window",
            "name": _("Punto de Venta"),
            "res_model": "pos.config",
            "view_mode": "kanban,list",
            "target": "main",
        }

    def action_print_daily_report(self):
        self.ensure_one()
        data = {
            "date_start": False,
            "date_stop": False,
            "config_ids": self.session_id.config_id.ids,
            "session_ids": self.session_id.ids,
        }
        return self.env.ref("point_of_sale.sale_details_report").report_action([], data=data)

    def action_open_cash_calculator(self):
        self.ensure_one()
        calculator_wizard = self.env["pos.cash.calculator.wizard"].create({
            "parent_model": self._name,
            "parent_res_id": self.id,
            "currency_id": self.currency_id.id,
        })
        return {
            "name": _("Monedas/billetes"),
            "type": "ir.actions.act_window",
            "res_model": "pos.cash.calculator.wizard",
            "view_mode": "form",
            "res_id": calculator_wizard.id,
            "target": "new",
            "context": self.env.context,
        }
