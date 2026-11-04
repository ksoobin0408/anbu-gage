from pathlib import Path
from urllib.parse import parse_qsl, urlencode
from streamlit.web.server.server import Server
from streamlit.web.server.starlette import create_starlette_app

server = Server(str(Path(__file__).resolve().parent.parent / "app.py"), False)
streamlit_app = create_starlette_app(server._runtime)

async def app(scope, receive, send):
    if scope["type"] in ("http", "websocket"):
        scope = dict(scope)
        params = parse_qsl(scope.get("query_string", b"").decode(), keep_blank_values=True)
        path = next((v for k, v in params if k == "__st_path"), "")
        scope["path"] = "/" + path.lstrip("/")
        scope["raw_path"] = scope["path"].encode()
        scope["query_string"] = urlencode([(k, v) for k, v in params if k != "__st_path"]).encode()
    await streamlit_app(scope, receive, send)
