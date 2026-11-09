"""Model Atlas local controller. Python 3.10+, standard library only."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib import error, request

ROOT = Path(__file__).resolve().parents[1]
ASSETS = Path(__file__).resolve().parent
MAX_BODY = 48_000
CONTEXTS = (4096, 8192, 16384, 32768, 65536)


class Problem(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def user_environment(name):
    value = os.environ.get(name)
    if not value and os.name == "nt":
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
                value = winreg.QueryValueEx(key, name)[0]
        except OSError:
            pass
    return value


def find_ollama():
    candidates = [shutil.which("ollama"), r"D:\Software\Ollama\ollama.exe",
                  str(Path.home() / "AppData/Local/Programs/Ollama/ollama.exe")]
    return next((p for p in candidates if p and Path(p).is_file()), None)


class Controller:
    def __init__(self, ollama_path=None, models_dir=None):
        self.ollama_path = ollama_path or find_ollama()
        self.models_dir = models_dir or user_environment("OLLAMA_MODELS")
        self.endpoint = "http://127.0.0.1:11434"
        self.token = secrets.token_urlsafe(32)
        self.opener = request.build_opener(request.ProxyHandler({}))
        self.lock = threading.RLock()
        self.process = None
        self.jobs = {}
        self.active = None
        self.closing = False
        self.gpu_cache = (0, [])

    def call(self, path, payload=None, timeout=3):
        data = None if payload is None else json.dumps(payload).encode()
        req = request.Request(self.endpoint + path, data=data,
                              headers={"Content-Type": "application/json"})
        try:
            with self.opener.open(req, timeout=timeout) as response:
                return json.load(response)
        except error.HTTPError as exc:
            try:
                message = json.loads(exc.read()).get("error", str(exc.code))
            except (ValueError, OSError):
                message = f"HTTP {exc.code}"
            raise Problem("Ollama：" + str(message), 502) from exc
        except (error.URLError, TimeoutError, ConnectionError, OSError) as exc:
            raise Problem("无法连接 Ollama，请先启动服务；若正在加载，请稍后刷新。", 503) from exc

    def owned(self):
        return self.process is not None and self.process.poll() is None

    def gpu(self):
        now = time.monotonic()
        if now - self.gpu_cache[0] < 10:
            return self.gpu_cache[1]
        rows = []
        executable = shutil.which("nvidia-smi")
        if executable:
            try:
                result = subprocess.run(
                    [executable, "--query-gpu=name,memory.used,memory.total,utilization.gpu",
                     "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=2,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
                for line in result.stdout.splitlines() if result.returncode == 0 else []:
                    name, used, total, utilization = [v.strip() for v in line.rsplit(",", 3)]
                    rows.append(dict(name=name, used_mb=int(used), total_mb=int(total),
                                     utilization=int(utilization)))
            except (OSError, ValueError, subprocess.TimeoutExpired):
                pass
        self.gpu_cache = (now, rows)
        return rows

    def status(self):
        result = dict(online=False, version=None, models=[], loaded=[], error=None,
                      can_start=bool(self.ollama_path), managed=self.owned(), gpu=self.gpu())
        try:
            result["version"] = self.call("/api/version")["version"]
            result["online"] = True
            result["models"] = self.call("/api/tags").get("models", [])
            result["loaded"] = self.call("/api/ps").get("models", [])
        except Problem as exc:
            result["error"] = str(exc)
        with self.lock:
            result["active_job"] = dict(self.jobs[self.active]) if self.active else None
        return result

    def start_service(self):
        try:
            self.call("/api/version", timeout=1)
            return "Ollama 已经在线。"
        except Problem:
            pass
        if not self.ollama_path or not Path(self.ollama_path).is_file():
            raise Problem("找不到 Ollama。先安装，或用 -OllamaPath 指定 ollama.exe。")
        runtime = ROOT / "work/console"
        runtime.mkdir(parents=True, exist_ok=True)
        env = dict(os.environ, OLLAMA_HOST="127.0.0.1:11434")
        if self.models_dir:
            env["OLLAMA_MODELS"] = self.models_dir
        with (runtime / "ollama.log").open("ab") as log:
            self.process = subprocess.Popen([self.ollama_path, "serve"], env=env,
                stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        for _ in range(60):
            if self.process.poll() is not None:
                raise Problem("Ollama 启动失败，请查看 work/console/ollama.log。", 502)
            try:
                self.call("/api/version", timeout=1)
                return "Ollama 已启动，可以选择模型。"
            except Problem:
                time.sleep(0.5)
        self.stop_service()
        raise Problem("启动超时，请查看 work/console/ollama.log。", 504)

    def stop_service(self):
        if not self.owned():
            raise Problem("此服务由其他程序启动，请从 Ollama 托盘菜单退出。", 409)
        # Only terminate the live Popen child owned by this controller and its runners.
        if os.name == "nt":
            result = subprocess.run(["taskkill", "/PID", str(self.process.pid), "/T", "/F"],
                capture_output=True, timeout=15, creationflags=subprocess.CREATE_NO_WINDOW)
            if result.returncode and self.process.poll() is None:
                raise Problem("停止服务失败，请查看 Ollama 进程状态。", 502)
        else:
            self.process.terminate()
        self.process.wait(timeout=15)
        self.process = None
        return "Ollama 已停止，模型文件仍在硬盘上。"

    def submit(self, action, body):
        if action not in {"start", "stop", "load", "unload", "chat"}:
            raise Problem("未知操作。", 404)
        model, prompt, context = body.get("model"), body.get("prompt", ""), body.get("context", 8192)
        if action == "chat" and (not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 12000):
            raise Problem("请输入 1–12000 字的测试问题。")
        if action in {"load", "unload", "chat"}:
            if not isinstance(model, str) or len(model) > 256:
                raise Problem("请选择一个已安装模型。")
            names = {m["name"] for m in self.call("/api/tags").get("models", [])}
            if model not in names:
                raise Problem("模型尚未安装，请从列表选择。")
            if type(context) is not int or context not in CONTEXTS:
                raise Problem("上下文长度不受支持。")
            info = self.call("/api/show", {"model": model}, timeout=10)
            if info.get("remote_host") or info.get("remote_model"):
                raise Problem("这是云端模型，本控制台只支持在本机运行的模型。")
        with self.lock:
            if self.active or self.closing:
                raise Problem("已有操作正在进行，请等待完成。", 409)
            while len(self.jobs) >= 8:
                self.jobs.pop(next(iter(self.jobs)))
            job_id = secrets.token_hex(8)
            job = dict(id=job_id, action=action, model=model, state="running", started=time.time(),
                       phase="准备中", content="", message="", metrics=None)
            self.jobs[job_id] = job
            self.active = job_id
        threading.Thread(target=self.run_job, args=(job_id, model, prompt, context), daemon=True).start()
        return dict(job)

    def update(self, job_id, **values):
        with self.lock:
            self.jobs[job_id].update(values)

    def chat(self, job_id, model, prompt, context):
        payload = dict(model=model, messages=[dict(role="user", content=prompt)], stream=True,
                       keep_alive="10m", options=dict(num_ctx=context, num_predict=1024))
        # Discover thinking controls so ordinary/non-thinking models remain compatible.
        info = self.call("/api/show", {"model": model}, timeout=10)
        if "thinking" in info.get("capabilities", []):
            payload["think"] = False
        req = request.Request(self.endpoint + "/api/chat", data=json.dumps(payload).encode(),
                              headers={"Content-Type": "application/json"})
        self.update(job_id, phase="加载模型 / 处理问题")
        deadline = time.monotonic() + 600
        text = ""
        with self.opener.open(req, timeout=600) as response:
            for line in response:
                if time.monotonic() > deadline:
                    raise Problem("本次测试超过 10 分钟，请缩短问题或换用较小模型。", 504)
                chunk = json.loads(line)
                if chunk.get("error"):
                    raise Problem("Ollama：" + str(chunk["error"]), 502)
                text += chunk.get("message", {}).get("content", "")
                if len(text) > 100_000:
                    raise Problem("回答超过控制台的显示上限。")
                self.update(job_id, content=text, phase="正在生成" if text else "正在处理")
                if chunk.get("done"):
                    duration = chunk.get("eval_duration", 0)
                    metrics = dict(seconds=round(chunk.get("total_duration", 0) / 1e9, 2),
                        tokens=chunk.get("eval_count", 0),
                        tokens_per_second=round(chunk.get("eval_count", 0) * 1e9 / duration, 2) if duration else None,
                        truncated=chunk.get("done_reason") == "length")
                    self.update(job_id, metrics=metrics)
                    if not text.strip():
                        raise Problem("模型未返回正文；可能已用完输出预算，请换一个短问题重试。", 502)
                    return "回答已完成。" if not metrics["truncated"] else "已达到 1024 token 上限，可缩短问题后再试。"
        raise Problem("连接提前结束，没有收到完整回答。", 502)

    def run_job(self, job_id, model, prompt, context):
        action = self.jobs[job_id]["action"]
        try:
            if action == "start":
                self.update(job_id, phase="启动服务")
                message = self.start_service()
            elif action == "stop":
                self.update(job_id, phase="停止服务")
                message = self.stop_service()
            elif action in {"load", "unload"}:
                self.update(job_id, phase="加载模型" if action == "load" else "释放模型内存")
                result = self.call("/api/generate", dict(model=model, stream=False,
                    keep_alive="10m" if action == "load" else 0,
                    options=dict(num_ctx=context)), timeout=600)
                if not result.get("done"):
                    raise Problem("Ollama 未确认操作完成。", 502)
                message = "模型已加载，空闲 10 分钟后释放。" if action == "load" else "模型已卸载，硬盘文件保留。"
            else:
                message = self.chat(job_id, model, prompt, context)
            self.update(job_id, state="done", phase="已完成", message=message)
        except Exception as exc:
            message = str(exc) if isinstance(exc, Problem) else "操作失败或超时，请检查 Ollama 状态后重试。"
            self.update(job_id, state="error", phase="未完成", message=message)
        finally:
            with self.lock:
                self.jobs[job_id]["finished"] = time.time()
                self.active = None


class Server(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, port, controller):
        self.controller = controller
        super().__init__(("127.0.0.1", port), Handler)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass  # Do not persist prompts, responses, or session tokens.

    def send(self, status, body, content_type="application/json; charset=utf-8"):
        data = json.dumps(body, ensure_ascii=False).encode() if isinstance(body, dict) else body
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'")
        self.end_headers()
        try:
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass

    def guard(self, mutation=False, navigation=False):
        port = self.server.server_port
        host = self.headers.get("Host", "")
        if host not in {f"127.0.0.1:{port}", f"localhost:{port}"}:
            raise Problem("不允许的主机名。", 403)
        origin = self.headers.get("Origin")
        if origin and origin != "http://" + host:
            raise Problem("不允许跨站请求。", 403)
        if self.headers.get("Sec-Fetch-Site") == "cross-site" and not navigation:
            raise Problem("不允许跨站请求。", 403)
        if mutation:
            token = self.headers.get("X-Atlas-Token", "")
            if not secrets.compare_digest(token, self.server.controller.token):
                raise Problem("会话已失效，请刷新控制台。", 403)
            if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
                raise Problem("请求必须使用 JSON。", 415)

    def do_GET(self):
        try:
            path = self.path.split("?", 1)[0]
            self.guard(navigation=path == "/" and self.headers.get("Sec-Fetch-Mode") == "navigate")
            ctrl = self.server.controller
            if path == "/api/health":
                return self.send(200, dict(app="model-atlas", project=hashlib.sha256(str(ROOT).encode()).hexdigest()[:16]))
            if path == "/api/session":
                return self.send(200, dict(token=ctrl.token))
            if path == "/api/status":
                return self.send(200, ctrl.status())
            if path.startswith("/api/jobs/"):
                with ctrl.lock:
                    job = ctrl.jobs.get(path.removeprefix("/api/jobs/"))
                    if not job:
                        raise Problem("操作记录已过期。", 404)
                    return self.send(200, dict(job))
            assets = {"/": ("index.html", "text/html; charset=utf-8"),
                      "/app.js": ("app.js", "text/javascript; charset=utf-8"),
                      "/style.css": ("style.css", "text/css; charset=utf-8")}
            if path not in assets:
                raise Problem("页面不存在。", 404)
            filename, content_type = assets[path]
            self.send(200, (ASSETS / filename).read_bytes(), content_type)
        except Problem as exc:
            self.send(exc.status, dict(error=str(exc)))

    def do_POST(self):
        try:
            self.guard(mutation=True)
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                raise Problem("无效的请求长度。")
            if not 0 < length <= MAX_BODY:
                raise Problem("请求过大或为空。", 413)
            self.connection.settimeout(10)
            try:
                body = json.loads(self.rfile.read(length))
            except (ValueError, TimeoutError):
                raise Problem("无法读取 JSON 请求。")
            if not isinstance(body, dict):
                raise Problem("请求必须是 JSON 对象。")
            ctrl = self.server.controller
            if self.path == "/api/exit":
                with ctrl.lock:
                    if ctrl.active or ctrl.closing:
                        raise Problem("请等待当前操作完成后退出。", 409)
                    ctrl.closing = True
                self.send(200, dict(message="控制台正在退出。"))
                threading.Thread(target=self.server.shutdown, daemon=True).start()
                return
            if not self.path.startswith("/api/actions/"):
                raise Problem("接口不存在。", 404)
            self.send(202, ctrl.submit(self.path.removeprefix("/api/actions/"), body))
        except Problem as exc:
            self.send(exc.status, dict(error=str(exc)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=18765)
    parser.add_argument("--ollama-path")
    parser.add_argument("--models-dir")
    args = parser.parse_args()
    controller = Controller(args.ollama_path, args.models_dir)
    server = Server(args.port, controller)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        if controller.owned():
            controller.stop_service()


if __name__ == "__main__":
    main()
