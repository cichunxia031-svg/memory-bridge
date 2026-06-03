"""
Summer 的记忆桥 MCP Server + 管理面板
4 个 MCP 工具：read / write / search / delete
REST API + 前端管理页面
"""

import sqlite3
import os
import json
from fastmcp import FastMCP
from starlette.applications import Starlette
from starlette.routing import Route, Mount
from starlette.responses import HTMLResponse, JSONResponse
from starlette.requests import Request

# --- 配置 ---
DB_DIR = os.environ.get("DB_DIR", os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(DB_DIR, "memory.db")
PASSWORD = os.environ.get("PASSWORD", "")

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


@mcp.tool()
def update_memory(id: int, content: str = "", tags: str = "") -> str:
    """更新一条记忆。id: 记忆编号；content: 新内容(可选)；tags: 新标签(可选)"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    existing = conn.execute("SELECT * FROM memories WHERE id = ?", (id,)).fetchone()
    if not existing:
        conn.close()
        return f"没有找到 #{id}。"

    new_content = content if content else existing['content']
    new_tags = tags if tags else existing['tags']
    conn.execute(
        "UPDATE memories SET content = ?, tags = ? WHERE id = ?",
        (new_content, new_tags, id)
    )
    conn.commit()
    conn.close()
    return f"已更新记忆 #{id}。"


# --- REST API ---
def check_auth(request: Request) -> bool:
    if not PASSWORD:
        return True
    auth = request.headers.get("X-Password", "")
    return auth == PASSWORD


async def api_memories(request: Request):
    if not check_auth(request):
        return JSONResponse({"error": "需要密码"}, status_code=401)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    if request.method == "GET":
        tag = request.query_params.get("tag", "")
        if tag:
            rows = conn.execute(
                "SELECT id, content, tags, created_at FROM memories WHERE tags LIKE ? ORDER BY created_at DESC",
                (f"%{tag}%",)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, content, tags, created_at FROM memories ORDER BY created_at DESC"
            ).fetchall()
        conn.close()
        return JSONResponse([dict(r) for r in rows])

    elif request.method == "POST":
        body = await request.json()
        content = body.get("content", "")
        tags = body.get("tags", "")
        if not content:
            conn.close()
            return JSONResponse({"error": "内容不能为空"}, status_code=400)
        cur = conn.execute(
            "INSERT INTO memories (content, tags) VALUES (?, ?)",
            (content, tags)
        )
        memory_id = cur.lastrowid
        conn.commit()
        conn.close()
        return JSONResponse({"id": memory_id, "message": "已记住"})


async def api_memory_detail(request: Request):
    if not check_auth(request):
        return JSONResponse({"error": "需要密码"}, status_code=401)

    memory_id = request.path_params["memory_id"]
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    if request.method == "PUT":
        body = await request.json()
        existing = conn.execute("SELECT * FROM memories WHERE id = ?", (memory_id,)).fetchone()
        if not existing:
            conn.close()
            return JSONResponse({"error": "记忆不存在"}, status_code=404)
        new_content = body.get("content", existing["content"])
        new_tags = body.get("tags", existing["tags"])
        conn.execute(
            "UPDATE memories SET content = ?, tags = ? WHERE id = ?",
            (new_content, new_tags, memory_id)
        )
        conn.commit()
        conn.close()
        return JSONResponse({"message": "已更新"})

    elif request.method == "DELETE":
        cur = conn.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
        conn.commit()
        deleted = cur.rowcount
        conn.close()
        if deleted:
            return JSONResponse({"message": "已删除"})
        else:
            return JSONResponse({"error": "记忆不存在"}, status_code=404)


async def api_search(request: Request):
    if not check_auth(request):
        return JSONResponse({"error": "需要密码"}, status_code=401)

    q = request.query_params.get("q", "")
    if not q:
        return JSONResponse([])

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT id, content, tags, created_at FROM memories WHERE content LIKE ? OR tags LIKE ? ORDER BY created_at DESC",
        (f"%{q}%", f"%{q}%")
    ).fetchall()
    conn.close()
    return JSONResponse([dict(r) for r in rows])


async def api_tags(request: Request):
    if not check_auth(request):
        return JSONResponse({"error": "需要密码"}, status_code=401)

    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("SELECT DISTINCT tags FROM memories WHERE tags != ''").fetchall()
    conn.close()

    tag_set = set()
    for row in rows:
        for tag in row[0].split(","):
            tag = tag.strip()
            if tag:
                tag_set.add(tag)
    return JSONResponse(sorted(tag_set))


async def index(request: Request):
    html_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "index.html")
    with open(html_path, "r", encoding="utf-8") as f:
        html = f.read()
    return HTMLResponse(html)


# --- 组合应用 ---
mcp_app = mcp.http_app(path="/mcp", transport="streamable-http")

routes = [
    Route("/", index, methods=["GET"]),
    Route("/api/memories", api_memories, methods=["GET", "POST"]),
    Route("/api/memories/search", api_search, methods=["GET"]),
    Route("/api/memories/tags", api_tags, methods=["GET"]),
    Route("/api/memories/{memory_id:int}", api_memory_detail, methods=["PUT", "DELETE"]),
    Mount("/", app=mcp_app),
]

app = Starlette(routes=routes)

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", "8080"))
    uvicorn.run(app, host="0.0.0.0", port=port)
