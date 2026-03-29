"""
Summer 的记忆桥 MCP Server
4 个工具：read_memory / write_memory / search_memory / delete_memory
"""

import sqlite3
import os
from fastmcp import FastMCP

# --- 配置 ---
DB_DIR = os.environ.get("DB_DIR", os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(DB_DIR, "memory.db")

# --- 初始化数据库 ---
def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content TEXT NOT NULL,
            tags TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_memories_created_at ON memories(created_at)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_memories_tags ON memories(tags)")
    conn.commit()
    conn.close()

init_db()

# --- MCP Server ---
mcp = FastMCP(
    "Memory Bridge",
    instructions="Eli 的外置记忆",
)


@mcp.tool()
def read_memory(count: int = 20, tag: str = "") -> str:
    """读取记忆。count: 条数(默认20)；tag: 按标签筛选(可选)"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    if tag:
        rows = conn.execute(
            "SELECT id, content, tags, created_at FROM memories WHERE tags LIKE ? ORDER BY created_at DESC LIMIT ?",
            (f"%{tag}%", count)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT id, content, tags, created_at FROM memories ORDER BY created_at DESC LIMIT ?",
            (count,)
        ).fetchall()
    conn.close()

    if not rows:
        return "没有找到记忆。"

    lines = []
    for r in rows:
        tag_part = f" [{r['tags']}]" if r['tags'] else ""
        lines.append(f"#{r['id']} [{r['created_at']}]{tag_part} {r['content']}")
    return "\n".join(lines)


@mcp.tool()
def write_memory(content: str, tags: str = "") -> str:
    """写入新记忆。content: 内容(必填，支持长文本)；tags: 标签，逗号分隔(可选)"""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.execute(
        "INSERT INTO memories (content, tags) VALUES (?, ?)",
        (content, tags)
    )
    memory_id = cur.lastrowid
    conn.commit()
    conn.close()
    return f"已记住。(id: {memory_id})"


@mcp.tool()
def search_memory(query: str) -> str:
    """搜索记忆。query: 关键词"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT id, content, tags, created_at FROM memories WHERE content LIKE ? OR tags LIKE ? ORDER BY created_at DESC LIMIT 20",
        (f"%{query}%", f"%{query}%")
    ).fetchall()
    conn.close()

    if not rows:
        return f"没有找到与「{query}」相关的记忆。"

    lines = []
    for r in rows:
        tag_part = f" [{r['tags']}]" if r['tags'] else ""
        lines.append(f"#{r['id']} [{r['created_at']}]{tag_part} {r['content']}")
    return "\n".join(lines)


@mcp.tool()
def delete_memory(id: int) -> str:
    """删除一条记忆。id: 记忆编号"""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.execute("DELETE FROM memories WHERE id = ?", (id,))
    conn.commit()
    deleted = cur.rowcount
    conn.close()

    if deleted:
        return f"已删除记忆 #{id}。"
    else:
        return f"没有找到 #{id}，可能已经删过了。"


# --- 启动 ---
app = mcp.http_app(path="/mcp", transport="sse")

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", "8765"))
    uvicorn.run(app, host="0.0.0.0", port=port)
