"""
app.py — FINREG AI Assistant

A small Flask app that lets you chat with your fintech knowledge-graph data
(companies.csv, regulations.csv, relationships.csv) in natural language.

The assistant can:
  - answer questions about companies, regulations, and their relationships,
    grounded in the live contents of the three CSVs
  - add, edit, or delete rows in any of the three tables when you ask it to,
    by calling tools (function calling) that actually write the CSV files —
    not just describe the change in text

Setup:
    pip install flask anthropic pandas
    export ANTHROPIC_API_KEY=sk-ant-...
    python app.py

Then open http://localhost:5000
Put companies.csv / regulations.csv / relationships.csv in the same folder
as this file (create empty ones with headers if you're starting fresh).
"""

import os
import uuid
import pandas as pd
from pathlib import Path
from flask import Flask, request, jsonify, render_template_string
import anthropic

DATA_DIR = Path(__file__).parent
COMPANIES_CSV = DATA_DIR / "companies.csv"
REGULATIONS_CSV = DATA_DIR / "regulations.csv"
RELATIONSHIPS_CSV = DATA_DIR / "relationships.csv"

MODEL = "claude-sonnet-5"

client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env
app = Flask(__name__)

# In-memory chat histories, keyed by session id. Swap for a real store
# (Redis, a DB) if you need this to survive restarts or scale past one process.
SESSIONS = {}

TABLES = {
    "companies": COMPANIES_CSV,
    "regulations": REGULATIONS_CSV,
    "relationships": RELATIONSHIPS_CSV,
}


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def _load(path: Path) -> pd.DataFrame:
    if path.exists():
        return pd.read_csv(path)
    return pd.DataFrame()


def _save(df: pd.DataFrame, path: Path) -> None:
    df.to_csv(path, index=False)


def _next_id(df: pd.DataFrame) -> int:
    if df.empty or "id" not in df.columns:
        return 1
    return int(pd.to_numeric(df["id"], errors="coerce").max()) + 1


def data_snapshot() -> str:
    """Compact text snapshot of all three tables, given to Claude as context
    on every turn so it always reasons from the live data, not stale memory."""
    parts = []
    for name, path in TABLES.items():
        df = _load(path)
        parts.append(f"### {name}.csv ({len(df)} rows)\n{df.to_csv(index=False)}")
    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# Tools Claude can call to read/change the data
# ---------------------------------------------------------------------------

TOOLS = [
    {
        "name": "add_row",
        "description": (
            "Add a new row to one of the three tables (companies, regulations, "
            "relationships). Omit 'id' for companies/regulations to auto-assign "
            "the next id."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "table": {"type": "string", "enum": list(TABLES.keys())},
                "row": {"type": "object", "description": "Column name -> value for the new row."},
            },
            "required": ["table", "row"],
        },
    },
    {
        "name": "update_row",
        "description": (
            "Update one or more fields of an existing row. For companies/regulations, "
            "match by 'id'. For relationships, match by 'source' and 'target'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "table": {"type": "string", "enum": list(TABLES.keys())},
                "match": {"type": "object", "description": "Column/value pairs identifying the row to update."},
                "updates": {"type": "object", "description": "Column/value pairs to set."},
            },
            "required": ["table", "match", "updates"],
        },
    },
    {
        "name": "delete_row",
        "description": "Delete row(s) matching the given column/value pairs from a table.",
        "input_schema": {
            "type": "object",
            "properties": {
                "table": {"type": "string", "enum": list(TABLES.keys())},
                "match": {"type": "object", "description": "Column/value pairs identifying the row(s) to delete."},
            },
            "required": ["table", "match"],
        },
    },
    {
        "name": "query_table",
        "description": (
            "Return the full current contents of one table as CSV text, in case you "
            "need to double-check current values before editing or answering."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"table": {"type": "string", "enum": list(TABLES.keys())}},
            "required": ["table"],
        },
    },
]


def _match_mask(df: pd.DataFrame, match: dict) -> pd.Series:
    mask = pd.Series([True] * len(df))
    for col, val in match.items():
        if col not in df.columns:
            raise ValueError(f"Unknown column '{col}'")
        mask &= df[col].astype(str) == str(val)
    return mask


def run_tool(name: str, tool_input: dict) -> str:
    table = tool_input.get("table")
    if table not in TABLES:
        return f"Error: unknown table '{table}'"
    path = TABLES[table]
    df = _load(path)

    try:
        if name == "add_row":
            row = dict(tool_input["row"])
            if table in ("companies", "regulations") and "id" not in row:
                row["id"] = _next_id(df)
            df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
            _save(df, path)
            return f"Added row to {table}: {row}"

        if name == "update_row":
            mask = _match_mask(df, tool_input["match"])
            if not mask.any():
                return f"No matching row found in {table} for {tool_input['match']}"
            for col, val in tool_input["updates"].items():
                df.loc[mask, col] = val
            _save(df, path)
            return f"Updated {int(mask.sum())} row(s) in {table}."

        if name == "delete_row":
            mask = _match_mask(df, tool_input["match"])
            n = int(mask.sum())
            if n == 0:
                return f"No matching row found in {table} for {tool_input['match']}"
            df = df.loc[~mask].reset_index(drop=True)
            _save(df, path)
            return f"Deleted {n} row(s) from {table}."

        if name == "query_table":
            return df.to_csv(index=False) or f"{table} is empty."

    except Exception as exc:  # keep the conversation alive even on a bad tool call
        return f"Error running {name} on {table}: {exc}"

    return f"Unknown tool '{name}'"


# ---------------------------------------------------------------------------
# Claude conversation loop
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are the FINREG data assistant. You help the user understand and \
maintain a small fintech knowledge graph made of three tables: companies, regulations, \
and relationships (edges between companies).

Ground every factual answer in the CURRENT DATA snapshot below, not on anything you \
inferred earlier in the conversation — the data may have changed since then. If the \
user asks you to add, edit, or remove something, use the add_row / update_row / \
delete_row tools rather than just describing the change in words. Call query_table \
first if you need to confirm current values before editing. After any tool calls, \
briefly confirm in plain language what you changed.

CURRENT DATA:
{data}
"""


def ask_claude(session_id: str, user_message: str) -> str:
    history = SESSIONS.setdefault(session_id, [])
    history.append({"role": "user", "content": user_message})

    while True:
        response = client.messages.create(
            model=MODEL,
            max_tokens=1500,
            system=SYSTEM_PROMPT.format(data=data_snapshot()),
            tools=TOOLS,
            messages=history,
        )

        history.append({"role": "assistant", "content": response.content})

        if response.stop_reason != "tool_use":
            return "".join(block.text for block in response.content if block.type == "text")

        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                result = run_tool(block.name, block.input)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result,
                })
        history.append({"role": "user", "content": tool_results})
        # loop again so Claude sees the tool results (and the freshly-rewritten
        # data snapshot, in case it just edited something) before it replies


# ---------------------------------------------------------------------------
# Flask routes
# ---------------------------------------------------------------------------

PAGE = """
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>FINREG AI Assistant</title>
  <style>
    body { font-family: system-ui, sans-serif; max-width: 720px; margin: 40px auto; }
    #log { border: 1px solid #ddd; border-radius: 8px; padding: 16px; height: 420px;
           overflow-y: auto; margin-bottom: 12px; background: #fafafa; }
    .msg { margin-bottom: 14px; white-space: pre-wrap; }
    .user { color: #111; font-weight: 600; }
    .assistant { color: #1a5; }
    form { display: flex; gap: 8px; }
    input[type=text] { flex: 1; padding: 10px; font-size: 15px; }
    button { padding: 10px 16px; }
  </style>
</head>
<body>
  <h2>FINREG AI Assistant</h2>
  <p>Ask about companies, regulations, relationships — or tell it to add/edit/remove data.</p>
  <div id="log"></div>
  <form id="f">
    <input id="msg" type="text" autocomplete="off" placeholder="e.g. Add a new regulation about open banking..." />
    <button type="submit">Send</button>
  </form>
  <script>
    const sessionId = crypto.randomUUID();
    const log = document.getElementById('log');
    const form = document.getElementById('f');
    const input = document.getElementById('msg');

    function append(role, text) {
      const div = document.createElement('div');
      div.className = 'msg ' + role;
      div.textContent = (role === 'user' ? 'You: ' : 'Claude: ') + text;
      log.appendChild(div);
      log.scrollTop = log.scrollHeight;
    }

    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      const text = input.value.trim();
      if (!text) return;
      append('user', text);
      input.value = '';
      const res = await fetch('/chat', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({session_id: sessionId, message: text})
      });
      const data = await res.json();
      append('assistant', data.reply || data.error || '(no response)');
    });
  </script>
</body>
</html>
"""


@app.route("/")
def index():
    return render_template_string(PAGE)


@app.route("/chat", methods=["POST"])
def chat():
    payload = request.get_json(force=True) or {}
    session_id = payload.get("session_id") or str(uuid.uuid4())
    message = (payload.get("message") or "").strip()
    if not message:
        return jsonify({"error": "message is required"}), 400
    try:
        reply = ask_claude(session_id, message)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500
    return jsonify({"session_id": session_id, "reply": reply})


if __name__ == "__main__":
    app.run(debug=True, port=5000)
