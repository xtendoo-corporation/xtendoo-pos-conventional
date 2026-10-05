from urllib.parse import parse_qs, urlsplit


def get_verifactu_qr_value(qr_image_url):
    """Return the AEAT validation URL encoded in a Veri*Factu QR image URL.

    Veri*Factu exposes the QR as an Odoo ``/report/barcode`` image URL whose
    ``value`` parameter carries the AEAT URL. Printers that render the QR
    natively (ESC/POS) need that raw value instead of the image.
    """
    if not qr_image_url:
        return ""
    values = parse_qs(urlsplit(qr_image_url).query).get("value")
    return values[0] if values else ""


def build_verifactu_receipt_values(invoice_name, is_simplified, qr_image_url):
    if not qr_image_url:
        return {}
    return {
        "invoice_name": invoice_name or "",
        "is_simplified": bool(is_simplified),
        "qr_code": qr_image_url,
        "qr_value": get_verifactu_qr_value(qr_image_url),
    }
