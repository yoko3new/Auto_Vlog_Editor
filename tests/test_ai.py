from types import SimpleNamespace

from vlogii.ai import Director
from vlogii.models import Review


def test_json_schema_keeps_strict_local_validation_without_legacy_sdk_conversion(tmp_path):
    seen = {}

    def generate(**kwargs):
        seen.update(kwargs)
        return SimpleNamespace(
            text='{"clip_id":"one","summary":"A real clip","highlights":[],"speech":[]}',
            usage_metadata=None,
        )

    director = Director.__new__(Director)
    director.client = SimpleNamespace(models=SimpleNamespace(generate_content=generate))
    director.model = "test"
    director.evidence = tmp_path
    assert director._generate(["review"], Review, "test").clip_id == "one"
    config = seen["config"]
    assert config.response_schema is None
    assert config.response_json_schema["additionalProperties"] is False


def test_provider_schema_translates_literal_without_losing_local_strictness():
    from vlogii.ai import provider_schema
    from vlogii.models import Plan

    schema = provider_schema(Plan)
    assert "schema_version" not in schema["properties"]
    assert Plan.model_fields["schema_version"].default == 1
    assert schema["additionalProperties"] is False


def test_schema_normalization_preserves_title_property_and_local_bounds():
    from vlogii.ai import provider_schema
    from vlogii.models import Plan

    schema = provider_schema(Plan)
    assert schema["properties"]["title"]["type"] == "string"
    assert "title" in schema["required"]
    assert "maxItems" not in schema["properties"]["segments"]
    assert Plan.model_json_schema()["properties"]["segments"]["maxItems"] == 200
