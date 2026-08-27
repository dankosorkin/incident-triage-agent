"""Provider-agnostic tool definitions for the agent's tool-calling
loop. OpenAI and Anthropic expect the same JSON Schema wrapped
differently, so tools are defined once here and converted per
provider rather than duplicated.
"""

from dataclasses import dataclass
from pathlib import Path

SCHEMA_SQL = Path(__file__).resolve().parent.parent / "sql" / "schema.sql"


@dataclass
class ToolSpec:
    name: str
    description: str
    parameters: dict

    def to_openai(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    def to_anthropic(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.parameters,
        }


SQL_TOOL = ToolSpec(
    name="sql_tool",
    description=(
        "Run a read-only SQL SELECT query against the incidents table to answer "
        "questions about structured incident data: counts, filtering by severity, "
        "service, status, or date, who resolved an incident, and how long it took. "
        "Use this for questions with a factual, countable, or filterable answer.\n\n"
        "Table schema:\n"
        f"{SCHEMA_SQL.read_text()}"
    ),
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "A read-only SQL SELECT query against the incidents table.",
            },
        },
        "required": ["query"],
    },
)

RAG_TOOL = ToolSpec(
    name="rag_tool",
    description=(
        "Search incident postmortems and troubleshooting runbooks for procedural "
        "or narrative information: what happened during a specific incident, root "
        "causes, or how to investigate and resolve a type of problem. Use this for "
        "'what should I do about X' or 'why did X happen' questions.\n\n"
        "Formulate the query as a generic description of the problem or procedure. "
        "Do not include specific service names or incident IDs in the query text -- "
        "this biases semantic search toward incidents mentioning that name, away "
        "from the general troubleshooting guide that usually answers the question."
    ),
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": (
                    "A generic search query describing the problem or procedure, "
                    "without specific service names or incident IDs."
                ),
            },
            "top_k": {
                "type": "integer",
                "description": "Number of results to return.",
                "default": 5,
            },
        },
        "required": ["query"],
    },
)

TOOLS = [SQL_TOOL, RAG_TOOL]
