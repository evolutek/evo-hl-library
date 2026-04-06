import pydantic

from evo_lib.config import ConfigJSON5Parser, ConfigObject, ConfigPydanticSchema


def test_json5_parser_and_pydantic_schema():
    parser = ConfigJSON5Parser()

    class MyRobotConfig(pydantic.BaseModel):
        name: str

    class MyGlobalConfig(pydantic.BaseModel):
        robot: MyRobotConfig
        sensor_ids: list[int]

    document = '''
    {
        robot: {
            name: "PAL", // The robot name
        },
        sensor_ids: [1, 2, 3]
    }
    '''

    raw_config = parser.parse_string(document)

    schema = ConfigPydanticSchema(MyGlobalConfig)
    my_global_config: MyGlobalConfig = schema.validate(raw_config)

    assert my_global_config.robot.name == "PAL"
    assert my_global_config.sensor_ids == [1, 2, 3]


def test_config_object_key_path():
    parser = ConfigJSON5Parser()
    raw = parser._transform_raw_config({"a": {"b": {"c": 42}}})

    assert isinstance(raw, ConfigObject)
    inner = raw["a"]["b"]
    assert isinstance(inner, ConfigObject)
    assert inner._get_key_path("c") == "a.b.c"
    assert inner.get_int("c") == 42
