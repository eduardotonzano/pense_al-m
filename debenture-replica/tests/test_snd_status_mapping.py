from debenture_search.parsers.snd_parser import SndParser


def test_registered_status_is_active():
    assert SndParser.infer_debenture_status("Registrado") == "active"


def test_registered_status_with_spaces_is_active():
    assert SndParser.infer_debenture_status("  Registrado  ") == "active"


def test_inactive_status_is_not_confused_with_active():
    assert SndParser.infer_debenture_status("Inativa") == "inactive"
