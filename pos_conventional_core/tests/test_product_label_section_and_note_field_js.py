# Copyright 2024 Xtendoo
# License OPL-1
import odoo.tests

from odoo.tests.common import HttpCase, TransactionCase, tagged


def unit_test_error_checker(message):
    return "[HOOT]" not in message


@tagged("pos_conventional_core", "-standard", "post_install", "-at_install")
class TestPosProductLabelSectionAndNoteFieldAssets(TransactionCase):
    """Verifica que el parche JS y su test se cargan en los bundles correctos."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.ref("web.layout").write(
            {
                "arch_db": (
                    '<t t-name="web.layout"><html><head><meta charset="utf-8"/>'
                    '<link/><script id="web.layout.odooscript"/><meta/>'
                    '<t t-esc="head"/></head><body><t t-out="0"/></body></html></t>'
                )
            }
        )

    def _get_asset_filenames(self, bundle_name):
        assets = self.env["ir.qweb"]._get_asset_content(bundle_name)[0]
        return {asset["filename"] for asset in assets if asset.get("filename")}

    def _assert_bundle_contains_suffix(self, bundle_name, expected_suffix, message):
        filenames = self._get_asset_filenames(bundle_name)
        self.assertTrue(
            any(filename.endswith(expected_suffix) for filename in filenames),
            message,
        )

    def test_backend_assets_include_product_field_patch(self):
        self._assert_bundle_contains_suffix(
            "web.assets_backend",
            "pos_conventional_core/static/src/js/product_label_section_and_note_field_patch.js",
            "El bundle backend debe incluir el parche del widget de producto.",
        )

    def test_backend_assets_include_order_form_core_controller(self):
        self._assert_bundle_contains_suffix(
            "web.assets_backend",
            "pos_conventional_core/static/src/js/pos_order_form_core_controller.js",
            "El bundle backend debe incluir el controlador base del formulario POS convencional.",
        )

    def test_backend_assets_include_order_workflow_utils(self):
        self._assert_bundle_contains_suffix(
            "web.assets_backend",
            "pos_conventional_core/static/src/js/pos_order_workflow_utils.js",
            "El bundle backend debe incluir el helper compartido del workflow POS convencional.",
        )

    def test_form_view_uses_core_js_class(self):
        view = self.env.ref("pos_conventional_core.view_pos_pos_form_inherit_pos_conventional_core")
        self.assertIn(
            'js_class="pos_conventional_order_form"',
            view.arch_db,
            "La vista base del formulario POS debe montar el controlador core para aplicar la guardia de salida.",
        )

    def test_unit_test_assets_include_product_field_patch_test(self):
        self._assert_bundle_contains_suffix(
            "web.assets_unit_tests",
            "pos_conventional_core/static/tests/product_label_section_and_note_field_patch.test.js",
            "El bundle de unit tests debe incluir el test frontend del parche.",
        )

    def test_unit_test_assets_include_order_form_core_controller_test(self):
        self._assert_bundle_contains_suffix(
            "web.assets_unit_tests",
            "pos_conventional_core/static/tests/pos_order_form_core_controller.test.js",
            "El bundle de unit tests debe incluir el test frontend del controlador base del formulario.",
        )

    def test_unit_test_assets_include_order_workflow_utils_test(self):
        self._assert_bundle_contains_suffix(
            "web.assets_unit_tests",
            "pos_conventional_core/static/tests/pos_order_workflow_utils.test.js",
            "El bundle de unit tests debe incluir el test frontend del helper compartido del workflow.",
        )


@tagged("pos_conventional_core", "-standard", "post_install", "-at_install")
class TestPosProductLabelSectionAndNoteFieldHoot(HttpCase):
    """Ejecuta el test HOOT que cubre el comportamiento del parche JS."""

    @staticmethod
    def _generate_hoot_hash(test_string):
        value = 0
        for character in test_string:
            value = (value << 5) - value + ord(character)
            value &= 0xFFFFFFFF
        return f"{value:08x}"

    @odoo.tests.no_retry
    def test_product_label_section_and_note_field_patch_hoot(self):
        suite = "@pos_conventional_core/product_label_section_and_note_field_patch"
        suite_hash = self._generate_hoot_hash(suite)
        self.browser_js(
            f"/web/tests?headless&loglevel=2&preset=desktop&timeout=15000&id={suite_hash}",
            "",
            "",
            login="admin",
            timeout=1800,
            success_signal="[HOOT] Test suite succeeded",
            error_checker=unit_test_error_checker,
        )

