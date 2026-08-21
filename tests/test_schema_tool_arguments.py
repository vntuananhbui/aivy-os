from __future__ import annotations

from ai.research.tools.schema import create_schema


def test_create_schema_accepts_native_structured_arrays() -> None:
    payload = {
        "tables_json": [
            {
                "table_id": "vietnam_companies",
                "attributes": ["Công ty", "Mã cổ phiếu", "Giá hiện tại"],
                "primary_key": ["Mã cổ phiếu"],
                "column_desc": {
                    "Giá hiện tại": {
                        "type": "float",
                        "desc": "Giá bằng VND tại thời điểm tra cứu",
                    }
                },
                "seed_entities": ["VIC", "VHM", "VCB"],
            }
        ],
        "relations_json": [],
    }

    parsed = create_schema.args_schema.model_validate(payload)

    assert isinstance(parsed.tables_json, list)
    assert parsed.tables_json[0]["table_id"] == "vietnam_companies"
    assert parsed.relations_json == []


def test_create_schema_keeps_legacy_json_string_compatibility() -> None:
    payload = {
        "tables_json": '[{"table_id":"companies","attributes":["ticker"]}]',
    }

    parsed = create_schema.args_schema.model_validate(payload)

    assert parsed.tables_json == [
        {"table_id": "companies", "attributes": ["ticker"]}
    ]


def test_create_schema_advertises_arrays_not_json_encoded_strings() -> None:
    properties = create_schema.args_schema.model_json_schema()["properties"]

    assert properties["tables_json"]["type"] == "array"
    relation_variants = properties["relations_json"]["anyOf"]
    assert {variant.get("type") for variant in relation_variants} == {"array", "null"}
