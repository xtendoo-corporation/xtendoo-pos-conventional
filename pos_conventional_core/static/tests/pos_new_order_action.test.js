import { describe, expect, test } from "@odoo/hoot";

import { buildPosOrdersListAction } from "../src/js/pos_new_order_action";

describe.current.tags("headless");

describe("@pos_conventional_core/pos_new_order_action", () => {
    test("buildPosOrdersListAction keeps the list filtered by all sessions of the same config", async () => {
        const orm = {
            async searchRead(model, domain, fields, kwargs) {
                expect(model).toBe("pos.session");
                expect(domain).toEqual([["config_id", "=", 12]]);
                expect(fields).toEqual(["id"]);
                expect(kwargs).toBe(undefined);
                return [{ id: 81 }, { id: 82 }];
            },
        };

        const action = await buildPosOrdersListAction(orm, {
            config_id: 12,
            default_session_id: 82,
            previous_sale_total: 20,
        });

        expect(action.type).toBe("ir.actions.act_window");
        expect(action.res_model).toBe("pos.order");
        expect(action.target).toBe("main");
        expect(action.view_mode).toBe("list,form");
        expect(action.views).toEqual([[false, "list"], [false, "form"]]);
        expect(action.domain).toEqual([["session_id", "in", [81, 82]]]);
        expect(action.context.default_session_id).toBe(82);
        expect(action.context.previous_sale_total).toBe(20);
    });

    test("buildPosOrdersListAction falls back to the current session if loading config sessions fails", async () => {
        const orm = {
            async searchRead() {
                throw new Error("RPC error");
            },
        };

        const action = await buildPosOrdersListAction(orm, {
            config_id: 12,
            default_session_id: 82,
        });

        expect(action.domain).toEqual([["session_id", "=", 82]]);
        expect(action.context.default_session_id).toBe(82);
    });
});


