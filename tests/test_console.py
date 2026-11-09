"""HTTP contract and security tests against a controlled Ollama stub."""
import importlib.util
import json
from pathlib import Path
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib import request, error

spec = importlib.util.spec_from_file_location("atlas", Path(__file__).resolve().parents[1] / "console/server.py")
atlas = importlib.util.module_from_spec(spec)
spec.loader.exec_module(atlas)
MODEL = {"name": "test:small", "digest": "test-digest", "size": 1234}


class OllamaStub(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def reply(self, data):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def do_GET(self):
        self.reply({"/api/version": {"version": "test"}, "/api/tags": {"models": [MODEL]},
                    "/api/ps": {"models": [MODEL] if self.server.loaded else []}}[self.path])

    def do_POST(self):
        data = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        self.server.requests.append((self.path, data))
        if self.path == "/api/show":
            return self.reply({"capabilities": ["completion"], **self.server.model_info})
        if self.path == "/api/generate":
            self.server.loaded = data["keep_alive"] != 0
            return self.reply({"done": True})
        if self.path == "/api/chat":
            self.send_response(200)
            self.end_headers()
            self.server.gate.wait(5)
            if self.server.fail:
                self.wfile.write(b'{"error":"test failure"}\n')
                return
            for chunk in [{"message": {"content": "hello "}}, {"message": {"content": "world"}},
                          {"done": True, "eval_count": 2, "eval_duration": 1_000_000_000, "total_duration": 2_000_000_000}]:
                self.wfile.write(json.dumps(chunk).encode() + b"\n")


class ConsoleTests(unittest.TestCase):
    def setUp(self):
        self.stub = ThreadingHTTPServer(("127.0.0.1", 0), OllamaStub)
        self.stub.requests, self.stub.loaded, self.stub.fail = [], False, False
        self.stub.model_info = {}
        self.stub.gate = threading.Event()
        self.stub.gate.set()
        threading.Thread(target=self.stub.serve_forever, daemon=True).start()
        self.controller = atlas.Controller()
        self.controller.endpoint = f"http://127.0.0.1:{self.stub.server_port}"
        self.server = atlas.Server(0, self.controller)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.server.server_port}"
        self.opener = request.build_opener(request.ProxyHandler({}))

    def tearDown(self):
        self.stub.gate.set()
        deadline = time.monotonic() + 3
        while self.controller.active and time.monotonic() < deadline:
            time.sleep(.01)
        for server in (self.server, self.stub):
            server.shutdown()
            server.server_close()

    def call(self, path, body=None, headers=None, token=True):
        actual_headers = {"Content-Type": "application/json"}
        if token:
            actual_headers["X-Atlas-Token"] = self.controller.token
        actual_headers.update(headers or {})
        data = None if body is None else json.dumps(body).encode()
        req = request.Request(self.url + path, data=data, headers=actual_headers)
        try:
            response = self.opener.open(req, timeout=5)
        except error.HTTPError as exc:
            response = exc
        with response:
            raw = response.read()
            parsed = json.loads(raw) if response.headers.get_content_type() == "application/json" else raw
            return response.status, parsed

    def job(self, action, **kwargs):
        code, result = self.call("/api/actions/" + action, {"model": MODEL["name"], **kwargs})
        self.assertEqual(code, 202, result)
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            _, result = self.call("/api/jobs/" + result["id"])
            if result["state"] != "running":
                return result
            time.sleep(.01)
        self.fail("Job did not finish")

    def test_read_status_does_not_load_model(self):
        code, result = self.call("/api/status")
        self.assertEqual(code, 200)
        self.assertTrue(result["online"])
        self.assertEqual(result["models"], [MODEL])
        self.assertEqual(result["loaded"], [])
        self.assertEqual(self.stub.requests, [])

    def test_origin_host_and_token_are_required(self):
        for headers, token in [({"Origin": "https://evil.example"}, True),
                               ({"Host": "evil.example"}, True),
                               ({"Sec-Fetch-Site": "cross-site"}, True), ({}, False)]:
            code, _ = self.call("/api/actions/load", {"model": MODEL["name"]}, headers, token)
            self.assertEqual(code, 403)
        self.assertEqual(self.call("/api/session", headers={"Host": "evil.example"})[0], 403)
        self.assertEqual(self.stub.requests, [])

    def test_static_files_are_allowlisted(self):
        self.assertEqual(self.call("/")[0], 200)
        for path in ("/../README.md", "/.git/config", "/server.py", "/work/console/ollama.log"):
            self.assertEqual(self.call(path)[0], 404)

    def test_link_navigation_opens_page_but_not_api(self):
        headers = {"Sec-Fetch-Site": "cross-site", "Sec-Fetch-Mode": "navigate"}
        self.assertEqual(self.call("/", headers=headers)[0], 200)
        self.assertEqual(self.call("/api/session", headers=headers)[0], 403)

    def test_invalid_request_cannot_invoke_command_or_download(self):
        for body in (["wrong"], {"model": "not-installed"}, {"model": MODEL["name"], "context": "8192"}):
            self.assertEqual(self.call("/api/actions/load", body)[0], 400)
        self.assertEqual(self.call("/api/actions/pull", {"model": "new"})[0], 404)
        self.assertEqual(self.call("/api/actions/chat", {"model": MODEL["name"], "prompt": " "})[0], 400)
        self.assertEqual(self.call("/api/actions/chat", {"prompt": "x" * 50000})[0], 413)
        self.assertEqual(self.stub.requests, [])

    def test_real_load_and_unload_requests(self):
        self.assertEqual(self.job("load", context=4096)["state"], "done")
        self.assertEqual(self.call("/api/status")[1]["loaded"], [MODEL])
        self.assertEqual(self.stub.requests[-1][1]["options"]["num_ctx"], 4096)
        self.assertEqual(self.job("unload")["state"], "done")
        self.assertEqual(self.call("/api/status")[1]["loaded"], [])
        self.assertEqual(self.stub.requests[-1][1]["keep_alive"], 0)

    def test_streamed_chat_and_statistics(self):
        result = self.job("chat", prompt="hi")
        self.assertEqual(result["state"], "done")
        self.assertEqual(result["content"], "hello world")
        self.assertEqual(result["metrics"]["tokens_per_second"], 2)
        payload = self.stub.requests[-1][1]
        self.assertEqual(payload["messages"], [{"role": "user", "content": "hi"}])
        self.assertNotIn("think", payload)

    def test_busy_model_cannot_be_unloaded_or_server_closed(self):
        self.stub.gate.clear()
        self.assertEqual(self.call("/api/actions/chat", {"model": MODEL["name"], "prompt": "hi"})[0], 202)
        self.assertEqual(self.call("/api/actions/unload", {"model": MODEL["name"]})[0], 409)
        self.assertEqual(self.call("/api/exit", {})[0], 409)

    def test_upstream_error_is_not_reported_as_success(self):
        self.stub.fail = True
        result = self.job("chat", prompt="hi")
        self.assertEqual(result["state"], "error")
        self.assertIn("test failure", result["message"])

    def test_cloud_model_cannot_receive_a_prompt(self):
        self.stub.model_info = {"remote_host": "https://example.com", "remote_model": "remote"}
        code, result = self.call("/api/actions/chat", {"model": MODEL["name"], "prompt": "private prompt"})
        self.assertEqual(code, 400)
        self.assertIn("云端模型", result["error"])
        self.assertEqual([path for path, _ in self.stub.requests], ["/api/show"])

    def test_external_service_cannot_be_stopped(self):
        result = self.job("stop")
        self.assertEqual(result["state"], "error")
        self.assertTrue(self.call("/api/status")[1]["online"])


if __name__ == "__main__":
    unittest.main()
