from pathlib import Path
from streamlit.web.server.server import Server
from streamlit.web.server.starlette import create_starlette_app
server = Server(str(Path(__file__).resolve().parent.parent / "app.py"), False)
app = create_starlette_app(server._runtime)
