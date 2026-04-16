/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { PosOrderListController } from "@pos_conventional_core/js/pos_order_list_controller";

const superActionMenuItems = Object.getOwnPropertyDescriptor(
    PosOrderListController.prototype,
    "actionMenuItems"
);

patch(PosOrderListController.prototype, {
    async onOpenConventionalReturns() {
        const sessionId = this.currentSessionId || this.activeSessionId;
        if (!sessionId) {
            return;
        }
        const action = await this.model.orm.call(
            "pos.order",
            "action_open_conventional_returns",
            [],
            {
                context: {
                    ...(this.props.context || {}),
                    default_session_id: sessionId,
                    session_id: sessionId,
                },
            }
        );
        return this.actionService.doAction(action);
    },

    get actionMenuItems() {
        const items = superActionMenuItems?.get
            ? superActionMenuItems.get.call(this)
            : { action: [] };

        if (!this.state.showCloseButton) {
            return items;
        }

        items.action = items.action || [];
        if (!items.action.find((item) => item.key === "conventional_returns")) {
            items.action.push({
                key: "conventional_returns",
                description: "Devolución",
                icon: "fa fa-undo",
                callback: () => this.onOpenConventionalReturns(),
                sequence: 95,
            });
        }
        return items;
    },
});

