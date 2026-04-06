from evo_lib.argtypes import (
    ARGTYPE_TO_ID,
    ARGTYPE_TO_NAME,
    ID_TO_ARGTYPE,
    NAME_TO_ARGTYPE,
    ArgTypes,
)


def test_argtype_lookup_tables_are_dicts():
    assert isinstance(ARGTYPE_TO_ID, dict)
    assert isinstance(ARGTYPE_TO_NAME, dict)


def test_argtype_id_round_trip():
    for argtype_id, argtype_cls in enumerate(ID_TO_ARGTYPE):
        assert ARGTYPE_TO_ID[argtype_cls] == argtype_id


def test_argtype_name_round_trip():
    for name, argtype_cls in NAME_TO_ARGTYPE.items():
        assert NAME_TO_ARGTYPE[ARGTYPE_TO_NAME[argtype_cls]] == argtype_cls
