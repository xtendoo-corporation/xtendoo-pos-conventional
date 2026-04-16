# pos_conventional_returns

Módulo para Odoo 19 que añade un acceso rápido de **Devolución** en la lista backend de pedidos de TPV convencional.

## Funcionalidad

- Añade la opción **Devolución** al menú de acciones de la lista de pedidos del TPV convencional.
- Abre una lista de pedidos de la misma caja (`pos.config`) que la sesión activa.
- Permite buscar por cliente y por referencia del pedido usando la búsqueda estándar de `pos.order`.
- Permite devolver directamente un pedido desde la lista reutilizando la lógica nativa `refund()` de Odoo.

## Notas técnicas

- El flujo de devolución se crea en la sesión actual abierta de la misma caja, siguiendo el comportamiento estándar de `point_of_sale`.
- La acción está pensada para el entorno backend no táctil (`pos_conventional_core`).

