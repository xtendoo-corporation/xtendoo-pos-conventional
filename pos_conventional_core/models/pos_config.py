from odoo import fields, models, api
from odoo.tools.translate import _


class PosConfig(models.Model):
    _inherit = "pos.config"

    pos_non_touch = fields.Boolean(
        string="POS no táctil",
        default=False,
        help="Activa un modo de punto de venta optimizado para equipos sin pantalla táctil.",
    )

    default_partner_id = fields.Many2one(
        "res.partner",
        string="Cliente por Defecto",
        help="Cliente que se asignará automáticamente a los nuevos pedidos POS creados desde el backend.",
        domain="[('customer_rank', '>', 0)]",
    )

    allow_draft_orders = fields.Boolean(
        string="Permitir ventas en borrador",
        default=False,
        help="Si está marcado, se permite salir de un pedido en borrador sin finalizar el pago.",
    )

    pos_force_employee_login_after_order = fields.Boolean(
        string="Pedir PIN del usuario",
        default=False,
        help=(
            "Si está activo, pedirá el PIN del usuario después de cada venta y "
            "cambiará el usuario de la sesión. Definido aquí como base (False) "
            "porque pos_order_list_controller.js lee este campo siempre, "
            "instale o no pos_conventional_users_pin -- sin este stub, la "
            "lectura lanza KeyError en el servidor (RPC_ERROR visible en "
            "consola) cuando ese módulo no está instalado. "
            "pos_conventional_users_pin sigue siendo quien le da uso real."
        ),
    )

    pos_print_receipt_without_preview = fields.Boolean(
        string="Imprimir tickets sin previsualización",
        help=(
            "Cuando la impresión automática está activa, carga el ticket en segundo "
            "plano para lanzar la impresión sin abrir la vista previa del informe."
        ),
    )

    def _get_or_create_non_touch_session(self):
        self.ensure_one()

        if self.current_session_id:
            return self.current_session_id

        res = self._check_before_creating_new_session()
        if res:
            return res

        return self.env["pos.session"].with_context(skip_auto_open=True).create(
            {
                "user_id": self.env.uid,
                "config_id": self.id,
            }
        )


    def _get_non_touch_opening_action(self, session):
        """Stub base: sin acción especial de apertura por defecto.

        pos_conventional_session_management (que depende de este módulo, no
        al revés) sobreescribe este método con el popup real cuando está
        instalado. Si solo está pos_conventional_core, open_ui() ya trata un
        valor falsy como "sin acción" y cae al flujo táctil estándar de
        Odoo -- no borrar este stub sin más, un intento anterior de
        "limpiarlo" ya rompió open_ui() cuando session_management no está
        instalado (AttributeError: 'pos.config' object has no attribute
        '_get_non_touch_opening_action').
        """
        return False

    def open_ui(self):
        """
        Override del método open_ui para interceptar la apertura
        cuando pos_non_touch está activo.
        """
        self.ensure_one()

        if self.pos_non_touch:
            session = self._get_or_create_non_touch_session()
            if isinstance(session, dict):
                return session

            if session.state == "opening_control":
                action = self._get_non_touch_opening_action(session)
                if action:
                    return action

            if session.state in ["opened", "closing_control"]:
                return self._redirect_to_pos_orders(session)

        return super(PosConfig, self).open_ui()

    def _redirect_to_pos_orders(self, session):
        self.ensure_one()
        action = self.env.ref("point_of_sale.action_pos_pos_form").sudo().read()[0]
        action["domain"] = [("config_id", "=", session.config_id.id)]
        action["context"] = {
            "default_session_id": session.id,
            "default_config_id": session.config_id.id,
            "search_default_current_session": 1,
        }
        return action
