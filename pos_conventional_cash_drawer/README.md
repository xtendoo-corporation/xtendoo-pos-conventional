# POS Conventional Cash Drawer

Módulo puente para Odoo 19 que añade un botón **Abrir cajón** junto a los botones rápidos de métodos de pago del POS convencional.

## Dependencias

- `pos_conventional_payment_wizard`
- `xtendoo_cash_drawer`

## Qué hace

- Sustituye el widget de botones rápidos de pago por una versión extendida.
- Añade el botón **Abrir cajón** al lado de los métodos de pago.
- Abre automáticamente el cajón al validar un cobro con método de efectivo en el POS convencional, tanto en el wizard rápido como en el popup de registro de pagos.
- Abre el cajón al pulsar **Cash In/Out / Entrada-Salida de caja** en el TPV, reutilizando el bridge local.
- Reutiliza `pos.config.action_test_cash_drawer()` para mantener el mismo flujo del bridge local ya implementado en `xtendoo_cash_drawer`.

