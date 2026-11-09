Xtendoo pos conventional

## Avisos de impresión QZ Tray

Los fallos de impresión QZ Tray se registran mediante `console.warn`, sin
notificaciones emergentes, tanto en el backend como en el TPV. Los intentos de
impresión y la navegación posterior se mantienen. Esto permite utilizar puestos
de consulta sin QZ Tray, pero también elimina el aviso visual en los puestos que
imprimen: si no sale el ticket, debe comprobarse QZ Tray y la consola del navegador.
Los avisos de error de impresión normal del navegador no cambian.

Pruebas focalizadas, sin dependencias adicionales:

```bash
node --test pos_conventional_qztray/static/tests/print_notifications.test.cjs
```

## Documentación técnica

- Fuente canónica: `DOCUMENTACION_TECNICA_POS_CONVENTIONAL.md`
- Exportación: `./exportar_documentacion_pos_conventional.sh`
- Artefactos generados: `DOCUMENTACION_TECNICA_POS_CONVENTIONAL.docx` y `DOCUMENTACION_TECNICA_POS_CONVENTIONAL.pdf`

## Informe de tests

- Fuente canónica: `INFORME_TESTS_POS_CONVENTIONAL.md`
- Exportación: `./exportar_informe_tests_pos_conventional.sh`
- Artefactos generados: `INFORME_TESTS_POS_CONVENTIONAL.docx` y `INFORME_TESTS_POS_CONVENTIONAL.pdf`
