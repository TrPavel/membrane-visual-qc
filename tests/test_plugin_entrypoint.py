import membrane_vqc


def test_plugin_entrypoint_is_safe_without_pymol():
    membrane_vqc.__init_plugin__()
