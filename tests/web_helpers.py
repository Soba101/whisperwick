"""Shared bits for the web play tests: a cookie-keeping client and a game fixture body."""

import http.client
import json
import threading
import time

from helpers import SCENARIO
from test_play import LookClient

from whisperwick import llm_cli, web_play
from whisperwick.scenario import load_scenario

SC = load_scenario(SCENARIO)


class Client:
    """One 'browser': keeps its cookies. http.client, because urllib looks up system proxies."""

    def __init__(self, port):
        self.port, self.cookies = port, {}

    def request(self, path, body=None, headers=None):
        head = dict(headers or {})
        if self.cookies:
            head["Cookie"] = "; ".join(f"{k}={v}" for k, v in self.cookies.items())
        data = None
        if body is not None:
            data, head["Content-Type"] = json.dumps(body), "application/json"
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        conn.request("POST" if body is not None else "GET", path, data, head)
        r = conn.getresponse()
        payload = r.read()
        for line in r.headers.get_all("Set-Cookie") or []:
            name, _, rest = line.partition("=")
            self.cookies[name] = rest.split(";")[0]
        self.last = r
        conn.close()
        return r.status, payload

    def state(self, since=0):
        return json.loads(self.request(f"/state?since={since}")[1])

    def until(self, test):
        for _ in range(100):
            s = self.state()
            if test(s):
                return s
            time.sleep(0.1)
        raise AssertionError("timed out")


def patch_model(monkeypatch, client_class=LookClient):
    """No .env, no network: a fake model."""
    monkeypatch.setattr(llm_cli.settings, "llm_base_url", lambda: "http://x")
    monkeypatch.setattr(llm_cli.settings, "llm_model", lambda: "m")
    monkeypatch.setattr(llm_cli, "make_client", lambda server, url, model: client_class())


def game_server(tmp_path, minutes, **options):
    """Start a server (port 0). Games start when a client opens the page."""
    server, manager = web_play.start(
        SC, SCENARIO, lambda n: str(tmp_path / f"w{n}.db"), None, minutes, 0, **options
    )
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, manager


def shut(server, manager):
    for thread in manager.close_all():
        thread.join(timeout=5)
    server.shutdown()
    server.server_close()
