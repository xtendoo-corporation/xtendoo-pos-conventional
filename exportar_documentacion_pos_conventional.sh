#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC_MD="$ROOT_DIR/DOCUMENTACION_TECNICA_POS_CONVENTIONAL.md"
OUT_DOCX="$ROOT_DIR/DOCUMENTACION_TECNICA_POS_CONVENTIONAL.docx"
OUT_PDF="$ROOT_DIR/DOCUMENTACION_TECNICA_POS_CONVENTIONAL.pdf"
TMP_DOCX="$OUT_DOCX"

if ! command -v pandoc >/dev/null 2>&1; then
    echo "Error: pandoc no está instalado o no está en PATH." >&2
    exit 1
fi

if ! command -v libreoffice >/dev/null 2>&1; then
    echo "Error: libreoffice no está instalado o no está en PATH." >&2
    exit 1
fi

if [[ ! -f "$SRC_MD" ]]; then
    echo "Error: no existe el fichero fuente $SRC_MD" >&2
    exit 1
fi

pandoc \
    "$SRC_MD" \
    --from gfm \
    --standalone \
    --toc \
    --number-sections \
    -o "$TMP_DOCX"

libreoffice --headless --convert-to pdf --outdir "$ROOT_DIR" "$TMP_DOCX" >/tmp/pos_conv_doc_export.log 2>&1 || {
    cat /tmp/pos_conv_doc_export.log >&2
    exit 1
}

if [[ ! -f "$OUT_PDF" ]]; then
    echo "Error: no se generó el PDF esperado en $OUT_PDF" >&2
    exit 1
fi

echo "Generados correctamente:"
echo "- $OUT_DOCX"
echo "- $OUT_PDF"

