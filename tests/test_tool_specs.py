from app.agent.tool_specs import RAG_TOOL, SQL_TOOL, TOOLS, ToolSpec


def test_to_openai_wraps_in_function_type():
    result = SQL_TOOL.to_openai()
    assert result["type"] == "function"
    assert result["function"]["name"] == "sql_tool"
    assert result["function"]["parameters"] == SQL_TOOL.parameters


def test_to_anthropic_uses_input_schema_not_parameters():
    result = SQL_TOOL.to_anthropic()
    assert result["name"] == "sql_tool"
    assert result["input_schema"] == SQL_TOOL.parameters
    assert "parameters" not in result
    assert "type" not in result


def test_both_formats_carry_the_same_description():
    assert SQL_TOOL.to_openai()["function"]["description"] == SQL_TOOL.to_anthropic()["description"]


def test_sql_tool_description_embeds_table_schema():
    assert "CREATE TABLE incidents" in SQL_TOOL.description


def test_sql_tool_description_clarifies_closed_status():
    assert "closed" in SQL_TOOL.description
    assert "terminal" in SQL_TOOL.description


def test_rag_tool_description_warns_against_service_names_in_query():
    assert "service name" in RAG_TOOL.description.lower()


def test_rag_tool_requires_query_but_not_top_k():
    assert RAG_TOOL.parameters["required"] == ["query"]
    assert "top_k" in RAG_TOOL.parameters["properties"]


def test_tools_list_contains_both():
    names = {t.name for t in TOOLS}
    assert names == {"sql_tool", "rag_tool"}


def test_toolspec_is_a_plain_dataclass_round_trip():
    spec = ToolSpec(name="x", description="d", parameters={"type": "object"})
    assert spec.to_openai()["function"]["name"] == "x"
    assert spec.to_anthropic()["input_schema"] == {"type": "object"}
