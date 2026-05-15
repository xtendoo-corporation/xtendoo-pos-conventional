import { describe, expect, test } from "@odoo/hoot";

import { buildPosOrdersListAction, posConventionalNewOrder } from "../src/js/pos_new_order_action";

describe.current.tags("headless");

describe("@pos_conventional_core/pos_new_order_action", () => {
    test("buildPosOrdersListAction keeps a base domain for the current config and activates the current-session filter by default", async () => {
        const action = await buildPosOrdersListAction({}, {
            config_id: 12,
            default_session_id: 82,
            previous_sale_total: 20,
        });

        expect(action.type).toBe("ir.actions.act_window");
        expect(action.res_model).toBe("pos.order");
        expect(action.target).toBe("main");
        expect(action.view_mode).toBe("list,form");
        expect(action.views).toEqual([[false, "list"], [false, "form"]]);
        expect(action.domain).toEqual([["config_id", "=", 12]]);
        expect(action.context.default_session_id).toBe(82);
        expect(action.context.default_config_id).toBe(12);
        expect(action.context.search_default_current_session).toBe(1);
        expect(action.context.previous_sale_total).toBe(20);
    });

    test("buildPosOrdersListAction keeps the base config domain even when there is no active session", async () => {
        const action = await buildPosOrdersListAction({}, {
            config_id: 12,
        });

        expect(action.domain).toEqual([["config_id", "=", 12]]);
        expect(action.context.default_session_id).toBe(false);
        expect(action.context.default_config_id).toBe(12);
        expect(action.context.search_default_current_session).toBe(0);
    });

    test("posConventionalNewOrder clears bypassPosLeave after opening the new order flow", async () => {
        const actions = [];
        window.bypassPosLeave = true;

        try {
            await posConventionalNewOrder(
                {
                    services: {
                        orm: {},
                        action: {
                            async doAction(action, options) {
                                actions.push({ action, options });
                            },
                        },
                    },
                },
                {
                    params: {
                        config_id: 12,
                        default_session_id: 82,
                        previous_sale_total: 20,
                    },
                }
            );

            expect(actions).toHaveLength(2);
            expect(window.bypassPosLeave).toBe(false);
        } finally {
            window.bypassPosLeave = false;
        }
    });
});


