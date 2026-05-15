import { describe, expect, test } from "@odoo/hoot";

import { buildOpeningOrdersListAction } from "../src/js/opening_popup";

describe.current.tags("headless");

describe("@pos_conventional_session_management/opening_popup", () => {
    test("buildOpeningOrdersListAction keeps a base domain for the opened config and activates the opened-session filter by default", () => {
        const action = buildOpeningOrdersListAction(42, 7);

        expect(action.type).toBe("ir.actions.act_window");
        expect(action.res_model).toBe("pos.order");
        expect(action.target).toBe("main");
        expect(action.view_mode).toBe("list,form");
        expect(action.views).toEqual([[false, "list"], [false, "form"]]);
        expect(action.domain).toEqual([["config_id", "=", 7]]);
        expect(action.context.default_session_id).toBe(42);
        expect(action.context.default_config_id).toBe(7);
        expect(action.context.search_default_current_session).toBe(1);
    });

    test("buildOpeningOrdersListAction keeps the base config domain when there is no valid session", () => {
        const action = buildOpeningOrdersListAction(null, 7);

        expect(action.domain).toEqual([["config_id", "=", 7]]);
        expect(action.context.default_session_id).toBe(false);
        expect(action.context.default_config_id).toBe(7);
        expect(action.context.search_default_current_session).toBe(0);
    });
});

