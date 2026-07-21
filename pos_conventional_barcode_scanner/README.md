# POS Conventional Barcode Scanner

Módulo para Odoo 19 que adapta el enfoque de `xtendoo_sale_barcode_scanner` al formulario backend de `pos.order` dentro de POS Conventional.

## Qué hace

- captura el escaneo desde el formulario backend del pedido POS
- solo actúa cuando la entrada es **numérica** (los códigos de barras son numéricos): si se
  teclea texto no numérico, no se intercepta ni se intenta buscar código de barras, de modo
  que las búsquedas manuales rápidas no se confunden con un escaneo
- evita que el texto del lector ensucie inputs editables mientras se procesa el barcode
- añade una línea nueva o incrementa la cantidad de una ya existente
- respeta el flujo y la tarificación del pedido POS convencional

## Dependencias

- `pos_conventional_core`
- `barcodes`

## Notas

- Está pensado como alternativa basada en el patrón del módulo de ventas.
- Si se quiere usar este enfoque como único escáner en backend, conviene no activar simultáneamente otros módulos que capturen el barcode con una estrategia distinta sobre el mismo formulario.

