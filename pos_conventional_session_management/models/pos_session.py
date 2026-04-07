import logging

from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)


class PosSession(models.Model):
    _inherit = "pos.session"

    # ── Helper ────────────────────────────────────────────────────────────

    def _cancel_empty_draft_orders(self):
        """Cancela pedidos POS en borrador vacíos (sin líneas) para sesiones no táctiles.

        En el flujo convencional no táctil se navega a un formulario vacío después
        de cada venta, lo que crea un pos.order en borrador sin líneas. Ese pedido
        bloquea el cierre porque _cannot_close_session() lo detecta como "draft".
        Este helper se llama en post_closing_cash_details Y en close_session_from_ui
        para cubrir los dos caminos (OWL popup y wizard Python).
        """
        self.ensure_one()
        _logger.debug(
            "_cancel_empty_draft_orders — sesión #%s (%s) non_touch=%s",
            self.id, self.name, self.config_id.pos_non_touch,
        )

        if not self.config_id.pos_non_touch:
            return False

        empty_draft = self.env["pos.order"].search([
            ("session_id", "=", self.id),
            ("state", "=", "draft"),
            ("lines", "=", False),
        ])
        if empty_draft:
            _logger.debug(
                "_cancel_empty_draft_orders — cancelando %s pedido(s) vacío(s): %s",
                len(empty_draft), empty_draft.mapped("name"),
            )
            empty_draft.write({"state": "cancel"})
            return True

        return False

    # ── Override: post_closing_cash_details ───────────────────────────────

    def post_closing_cash_details(self, counted_cash):
        """Override para cancelar pedidos vacíos ANTES de la comprobación de cierre.

        El OWL popup (ClosingPopup.confirm) llama a este método ANTES que a
        close_session_from_ui. Sin este override, _cannot_close_session() encuentra
        el pedido vacío en borrador y devuelve {successful: False}.
        """
        self.ensure_one()
        _logger.debug(
            "post_closing_cash_details — sesión #%s state=%s counted_cash=%s",
            self.id, self.state, counted_cash,
        )
        self._cancel_empty_draft_orders()
        result = super().post_closing_cash_details(counted_cash)
        _logger.debug("post_closing_cash_details — resultado: %s", result)
        return result

    # ── Override: close_session_from_ui ──────────────────────────────────

    def close_session_from_ui(self, bank_payment_method_diff_pairs=None):
        """Override para POS no táctil: cancela pedidos en borrador vacíos antes de cerrar."""
        self.ensure_one()
        _logger.debug(
            "close_session_from_ui — sesión #%s state=%s bank_diffs=%s",
            self.id, self.state, bank_payment_method_diff_pairs,
        )
        self._cancel_empty_draft_orders()
        result = super().close_session_from_ui(bank_payment_method_diff_pairs)
        _logger.debug("close_session_from_ui — resultado: %s", result)
        return result

    # ── Dedicated method for the non-touch closing popup ─────────────────

    def get_closing_control_data_non_touch(self):
        """Return closing control data extended with currency fields.

        This method is called exclusively by the non-touch ClosingPopup JS
        component. Using a separate RPC call avoids polluting the standard
        get_closing_control_data return value.
        """
        self.ensure_one()
        data = self.get_closing_control_data()
        data["currency_id"] = self.currency_id.id
        data["currency_name"] = self.currency_id.name
        data["currency_symbol"] = self.currency_id.symbol
        return data

    # ── Override: create ─────────────────────────────────────────────────

    @api.model_create_multi
    def create(self, vals_list):
        """Hereda el saldo final de la última sesión cerrada como saldo inicial.

        Se aplica a todos los terminales no táctiles (pos_non_touch=True)
        independientemente de si tienen control de caja activo, para que el
        efectivo del cierre anterior siempre se proponga como apertura.
        """
        for vals in vals_list:
            if "config_id" in vals and "cash_register_balance_start" not in vals:
                config = self.env["pos.config"].browse(vals["config_id"])
                if getattr(config, "pos_non_touch", False):
                    last_session = self.search(
                        [("config_id", "=", config.id), ("state", "=", "closed")],
                        order="id desc",
                        limit=1,
                    )
                    if last_session:
                        vals["cash_register_balance_start"] = (
                            last_session.cash_register_balance_end_real
                        )
        return super().create(vals_list)

    # ── Override: action_pos_session_open ────────────────────────────────

    def action_pos_session_open(self):
        """Intercepta la apertura de sesión para mostrar el popup OWL en modo no táctil."""
        if self.env.context.get("skip_auto_open"):
            return True

        non_touch_sessions = self.filtered(
            lambda s: getattr(s.config_id, "pos_non_touch", False) and s.state == "opening_control"
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
