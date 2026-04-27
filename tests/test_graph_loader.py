from enum import IntEnum

from evo_lib.argtypes import ArgTypes
from evo_lib.graph.graph import Node, NodeDefinition
from evo_lib.graph.loader import GraphLoader


class _DummyNode(Node):
    pass


class _Color(IntEnum):
    RED = 0
    GREEN = 1
    BLUE = 2


def _build_definition_with_inputs(*value_inputs):
    node_def = NodeDefinition(_DummyNode, "action/demo", "Demo")
    for name, argtype, default in value_inputs:
        node_def.add_value_input(name, argtype, default)
    return node_def


def test_export_enum_emits_values_as_name_to_value_mapping():
    node_def = _build_definition_with_inputs(("color", ArgTypes.Enum(_Color), _Color.RED))
    loader = GraphLoader()
    loader.register_node_type(node_def)

    exported = loader.export_node_types()
    vi = exported["nodes"]["action/demo"]["value_inputs"]["color"]

    assert vi["values"] == {"RED": 0, "GREEN": 1, "BLUE": 2}


def test_export_string_with_choices_emits_choices():
    node_def = _build_definition_with_inputs(
        ("side", ArgTypes.String(choices=["yellow", "blue"]), "yellow")
    )
    loader = GraphLoader()
    loader.register_node_type(node_def)

    exported = loader.export_node_types()
    vi = exported["nodes"]["action/demo"]["value_inputs"]["side"]

    assert vi["choices"] == ["yellow", "blue"]


def test_export_open_input_has_no_values_or_choices_key():
    node_def = _build_definition_with_inputs(("x", ArgTypes.F32(), 0.0))
    loader = GraphLoader()
    loader.register_node_type(node_def)

    exported = loader.export_node_types()
    vi = exported["nodes"]["action/demo"]["value_inputs"]["x"]

    assert "values" not in vi
    assert "choices" not in vi
