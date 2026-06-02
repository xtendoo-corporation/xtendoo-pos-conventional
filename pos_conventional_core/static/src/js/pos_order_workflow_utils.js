/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";

export function getOrderLinesList(record) {
    return record?.data?.lines || null;
}

export function getOrderLineRecords(record) {
    return getOrderLinesList(record)?.records || [];
}

export function getOrderPaymentsList(record) {
    return record?.data?.payment_ids || null;
}

export function getOrderPaymentRecords(record) {
    return getOrderPaymentsList(record)?.records || [];
}

export function getRelationalValueId(value) {
    if (!value) {
        return false;
    }
    if (typeof value === "number") {
        return value;
    }
    if (Array.isArray(value)) {
        return value[0] || false;
    }
    if (typeof value === "object") {
        return value.id || value.resId || false;
    }
    return false;
}

export function hasRealProductLines(record) {
    const lines = getOrderLinesList(record);
    const lineRecords = getOrderLineRecords(record);

    if (lineRecords.length) {
        return lineRecords.some((line) => {
            if (line?.data?.display_type) {
                return false;
            }
            return !!getRelationalValueId(line?.data?.product_id);
        });
    }

    return (lines?.currentIds?.length || 0) > 0;
}

export function isZeroAmount(amountTotal, epsilon = 0.00001) {
    return Math.abs(amountTotal || 0) < epsilon;
}

export function hasRecordedPayments(record, epsilon = 0.00001) {
    const paymentRecords = getOrderPaymentRecords(record);

    if (paymentRecords.length) {
        return paymentRecords.some((payment) => Math.abs(payment?.data?.amount || 0) > epsilon);
    }

    const paymentIds = getOrderPaymentsList(record)?.currentIds || [];
    if (paymentIds.length) {
        return true;
    }

    return Math.abs(record?.data?.amount_paid || 0) > epsilon;
}

export function shouldBlockDraftOrderLeave(record) {
    return !!(
        record &&
        record.data &&
        record.data.state === "draft" &&
        hasRealProductLines(record) &&
        !hasRecordedPayments(record)
    );
}

export function playErrorBeep() {
    try {
        const ctx = new (window.AudioContext || window.webkitAudioContext)();
        const oscillator = ctx.createOscillator();
        const gainNode = ctx.createGain();
        oscillator.connect(gainNode);
        gainNode.connect(ctx.destination);
        oscillator.type = "square";
        oscillator.frequency.setValueAtTime(380, ctx.currentTime);
        oscillator.frequency.setValueAtTime(280, ctx.currentTime + 0.15);
        gainNode.gain.setValueAtTime(0.25, ctx.currentTime);
        gainNode.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.35);
        oscillator.start(ctx.currentTime);
        oscillator.stop(ctx.currentTime + 0.35);
    } catch {
        // Fallback silencioso si Web Audio API no está disponible
    }
}

export function notifyInvalidOrderForPayment(record, notification) {
    if (!hasRealProductLines(record)) {
        playErrorBeep();
        notification.add(
            _t("No se puede cobrar un pedido sin líneas. Añada productos al pedido."),
            { type: "warning", title: _t("Pedido vacío"), sticky: false }
        );
        return false;
    }

    return true;
}

export function activateNavigationBypass(record = null, timeout = 10000) {
    window.bypassPosLeave = true;
    setTimeout(() => {
        if (!record?.resId) {
            window.bypassPosLeave = false;
            return;
        }
        if (
            window.location.hash.includes("model=pos.order") &&
            window.location.hash.includes(`id=${record.resId}`)
        ) {
            window.bypassPosLeave = false;
        }
    }, timeout);
}

export function clearNavigationBypass() {
    window.bypassPosLeave = false;
}

export async function loadPaymentMethods(orm, fieldData) {
    if (!fieldData?.currentIds?.length) {
        return [];
    }

    const ids = fieldData.currentIds;
    try {
        const methods = await orm.read("pos.payment.method", ids, ["name"]);
        const methodsById = new Map(methods.map((method) => [method.id, method]));
        return ids
            .map((id) => methodsById.get(id))
            .filter(Boolean)
            .map((method) => ({
                id: method.id,
                name: method.name,
            }));
    } catch (error) {
        console.error("Error al leer nombres de métodos de pago:", error);
        return ids.map((id) => ({ id, name: "Metodo " + id }));
    }
}

export async function payOrderWithMethod({ record, methodId, orm, action, notification, logger = console }) {
    if (!notifyInvalidOrderForPayment(record, notification)) {
        return { success: false, reason: "invalid_order" };
    }

    const saved = await record.save();
    if (!saved && !record.resId) {
        return { success: false, reason: "save_failed" };
    }

    const orderId = record.resId;
    if (!orderId) {
        logger.error("No se pudo obtener el ID del pedido.");
        return { success: false, reason: "missing_order_id" };
    }

    try {
        activateNavigationBypass(record);
        const actionResult = await orm.call(
            "pos.order",
            "action_pos_convention_pay_with_method",
            [orderId, methodId]
        );

        if (actionResult) {
            await action.doAction(actionResult);
            return { success: true, action: actionResult };
        }

        clearNavigationBypass();
        await record.load();
        return { success: false, reason: "missing_action" };
    } catch (error) {
        clearNavigationBypass();
        logger.error("Error al procesar pago:", error);
        return { success: false, reason: "rpc_error", error };
    }
}

