from odoo import api, fields, models, _


class PosSession(models.Model):
    _inherit = "pos.session"

    # ── Helper ────────────────────────────────────────────────────────────

    def _cancel_empty_draft_orders(self):
        """Cancela pedidos POS en borrador vacíos (sin líneas) para sesiones no táctiles.

        En el flujo convencional no táctil se navega a un formulario vacío después
        de cada venta, lo que crea un pos.order en borrador sin líneas.  Ese pedido
        bloquea el cierre porque _cannot_close_session() lo detecta como "draft".
        Este helper se llama en post_closing_cash_details Y en close_session_from_ui
        para cubrir los dos caminos (OWL popup y wizard Python).
        """
        self.ensure_one()
        print(
            f"\n[CERRAR CAJA] _cancel_empty_draft_orders"
            f" — sesión #{self.id} ({self.name})"
            f" non_touch={self.config_id.pos_non_touch}"
        )

        if not self.config_id.pos_non_touch:
            print("[CERRAR CAJA]   → sesión TOUCH: no se cancelan borradores vacíos")
            return False

        empty_draft = self.env["pos.order"].search([
            ("session_id", "=", self.id),
            ("state", "=", "draft"),
            ("lines", "=", False),
        ])
        if empty_draft:
            print(
                f"[CERRAR CAJA]   → cancelando {len(empty_draft)} pedido(s) vacío(s):"
                f" {empty_draft.mapped('name')}"
            )
            empty_draft.write({"state": "cancel"})
            return True

        print("[CERRAR CAJA]   → no hay pedidos en borrador vacíos")
        return False

    # ── Override: post_closing_cash_details ───────────────────────────────

    def post_closing_cash_details(self, counted_cash):
        """Override para cancelar pedidos vacíos ANTES de la comprobación de cierre.

        *** Esta es la causa raíz del bug ***
        El OWL popup (ClosingPopup.confirm) llama a este método ANTES que a
        close_session_from_ui.  Sin este override, _cannot_close_session() encuentra
        el pedido vacío en borrador y devuelve {successful: False}, lo que hace que
        el popup muestre una notificación fugaz y el usuario percibe "no pasa nada".
        """
        self.ensure_one()
        print(
            f"\n[CERRAR CAJA] post_closing_cash_details"
            f" — sesión #{self.id} state={self.state}"
            f" cash_control={self.config_id.cash_control}"
            f" counted_cash={counted_cash}"
        )
        self._cancel_empty_draft_orders()
        result = super().post_closing_cash_details(counted_cash)
        print(f"[CERRAR CAJA]   → post_closing_cash_details result: {result}")
        return result

    # ── Override: close_session_from_ui ──────────────────────────────────

    def close_session_from_ui(self, bank_payment_method_diff_pairs=None):
        """Override para POS no táctil: cancela pedidos en borrador vacíos antes de cerrar."""
        self.ensure_one()
        print(
            f"\n[CERRAR CAJA] close_session_from_ui"
            f" — sesión #{self.id} state={self.state}"
            f" bank_diffs={bank_payment_method_diff_pairs}"
        )
        self._cancel_empty_draft_orders()
        result = super().close_session_from_ui(bank_payment_method_diff_pairs)
        print(f"[CERRAR CAJA]   → close_session_from_ui result: {result}")
        return result

    # ── Override: get_closing_control_data ───────────────────────────────

    def get_closing_control_data(self):
        """Override para añadir currency_id, currency_name y currency_symbol al resultado.

        El componente JS ClosingPopup usa currency_name (código ISO p.ej. 'EUR', 'USD')
        para formatear los importes con Intl.NumberFormat respetando la moneda de la empresa.
        """
        self.ensure_one()
        data = super().get_closing_control_data()
        data["currency_id"] = self.currency_id.id
        data["currency_name"] = self.currency_id.name          # p.ej. 'EUR', 'USD'
        data["currency_symbol"] = self.currency_id.symbol      # p.ej. '€', '$'
        return data

    # ── Override: create ─────────────────────────────────────────────────

    @api.model_create_multi
    def create(self, vals_list):
        """Hereda el saldo final de la última sesión cerrada como saldo inicial."""
        for vals in vals_list:
            if 'config_id' in vals and 'cash_register_balance_start' not in vals:
                config = self.env['pos.config'].browse(vals['config_id'])
                if config.cash_control:
                    last_session = self.search([
                        ('config_id', '=', config.id),
                        ('state', '=', 'closed')
                    ], order='id desc', limit=1)
                    if last_session:
                        vals['cash_register_balance_start'] = last_session.cash_register_balance_end_real
        return super().create(vals_list)

    # ── Override: action_pos_session_open ────────────────────────────────

    def action_pos_session_open(self):
        """Intercepta la apertura de sesión para mostrar el popup OWL en modo no táctil."""
        if self.env.context.get("skip_auto_open"):
            return True

        non_touch_sessions = self.filtered(
            lambda s: s.config_id.pos_non_touch and s.state == "opening_control"
        )

        if non_touch_sessions:
            return {
                "type": "ir.actions.client",
                "tag": "pos_conventional_opening_popup",
                "name": _("Control de apertura"),
                "target": "new",
                "context": {
                    "session_id": self.id,
                    "config_id": self.config_id.id,
                },
            }

        return super().action_pos_session_open()
