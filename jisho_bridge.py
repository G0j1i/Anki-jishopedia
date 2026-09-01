import json
import urllib.request
import urllib.parse
import threading
from aqt import mw
from aqt.gui_hooks import webview_did_receive_js_message


class JishoBridge:
    """Minimal JS ↔ Python transport bridge for Jisho API.
    
    Protocol:
        JS: pycmd("jisho:" + JSON.stringify({action, request_id, query}))
        Python: background HTTP → mw.taskman.run_on_main → JS callback
        JS: window.__jisho_resolve(request_id, envelope)
    
    Responsibilities: transport only. No caching, normalization, or rendering.
    """
    
    def __init__(self):
        webview_did_receive_js_message.append(self._handle_js_message)

    def _handle_js_message(self, handled, message, context):
        # Only handle Jisho messages
        if not message.startswith("jisho:"):
            return handled

        try:
            payload = json.loads(message[6:])  # remove "jisho:" prefix
            action = payload.get("action")
            request_id = payload.get("request_id")
            query = payload.get("query")

            if action != "lookup" or not request_id or not query:
                return handled

            # Offload HTTP to background thread
            threading.Thread(
                target=self._fetch_jisho,
                args=(context, request_id, query),
                daemon=True
            ).start()

            # Claimed this message; do not pass further
            return (True, None)

        except Exception as e:
            print(f"Jisho bridge parse error: {e}")
            return handled

    def _fetch_jisho(self, context, request_id, query):
        """Background HTTP request to Jisho API."""
        url = f"https://jisho.org/api/v1/search/words?keyword={urllib.parse.quote(query, safe='')}"
        ok = False
        data = None
        error = None

        try:
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read().decode())
                ok = True
        except Exception as e:
            error = str(e)
            print(f"Jisho fetch error: {error}")

        envelope = {"ok": ok, "data": data, "error": error}

        # Schedule result back on Anki's main thread
        mw.taskman.run_on_main(
            lambda: self._send_result(context, request_id, envelope)
        )

    def _send_result(self, context, request_id, envelope):
        """Called on main thread; injects result into WebView."""
        try:
            js = json.dumps(envelope)
            context.web.eval(
                f"window.__jisho_resolve("
                f"{json.dumps(request_id)}, "
                f"{js}"
                f");"
            )
        except Exception as e:
            print(f"Jisho bridge response error: {e}")