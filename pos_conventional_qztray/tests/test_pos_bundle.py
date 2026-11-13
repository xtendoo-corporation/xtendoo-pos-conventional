import re

from odoo.tests import TransactionCase, tagged
from odoo.tools import file_open

POS_BUNDLE = "point_of_sale._assets_pos"
# @modulo/ruta -> /modulo/static/src/ruta.js (convención de los módulos del TPV)
IMPORT = re.compile(r"""from\s+["']@(pos_conventional_\w+)/([^"']+)["']""")


@tagged("post_install", "-at_install")
class TestPosBundleDependencies(TransactionCase):
    """Todo módulo JS que un fichero del TPV importa tiene que estar también
    en el bundle del TPV, y antes que quien lo importa.

    Si falta, el cargador de módulos de Odoo no lo resuelve y el TPV escribe
    "modules needed by other modules but have not been defined" en la consola
    en cada arranque, dejando sin aplicar el parche que lo necesitaba.
    """

    def test_imports_of_pos_conventional_files_are_in_the_pos_bundle(self):
        files, _external = self.env["ir.qweb"]._get_asset_content(POS_BUNDLE)
        urls = [asset["url"] for asset in files]
        own = [url for url in urls if url.startswith("/pos_conventional_") and url.endswith(".js")]
        self.assertTrue(own, "El bundle del TPV no contiene ficheros pos_conventional_*")

        for url in own:
            with file_open(url.lstrip("/"), "r") as handle:
                source = handle.read()
            for module, path in IMPORT.findall(source):
                needed = f"/{module}/static/src/{path}.js"
                with self.subTest(file=url, needs=needed):
                    self.assertIn(needed, urls, f"{url} importa {needed}, que no está en {POS_BUNDLE}")
                    self.assertLess(urls.index(needed), urls.index(url), "La dependencia debe cargarse antes")
