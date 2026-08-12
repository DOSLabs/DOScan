import os
import shutil
import socket
import socketserver
import struct
import subprocess
import threading
import time
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = ROOT / ".github" / "scripts" / "retry-public-http.sh"


class ResetThenSuccessHandler(socketserver.BaseRequestHandler):
    attempts = 0

    def handle(self):
        type(self).attempts += 1
        self.request.recv(4096)

        if type(self).attempts == 1:
            self.request.setsockopt(
                socket.SOL_SOCKET,
                socket.SO_LINGER,
                struct.pack("ii", 1, 0),
            )
            return

        body = b'{"status":"SERVING"}'
        self.request.sendall(
            b"HTTP/1.1 200 OK\r\n"
            + f"Content-Length: {len(body)}\r\n".encode()
            + b"Connection: close\r\n\r\n"
            + body
        )


class HangingHandler(socketserver.BaseRequestHandler):
    def handle(self):
        self.request.recv(4096)
        time.sleep(3)


class ThreadingTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    daemon_threads = True


class RetryPublicHttpTests(unittest.TestCase):
    def test_retries_connection_reset_until_public_endpoint_is_ready(self):
        ResetThenSuccessHandler.attempts = 0
        server = socketserver.TCPServer(("127.0.0.1", 0), ResetThenSuccessHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        try:
            result = subprocess.run(
                [
                    self.bash_path(),
                    SCRIPT_PATH.as_posix(),
                    f"http://127.0.0.1:{server.server_address[1]}/health",
                ],
                capture_output=True,
                env={
                    **os.environ,
                    "PUBLIC_HTTP_RETRY_DELAY_SECONDS": "0",
                },
                text=True,
                timeout=15,
            )
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual('{"status":"SERVING"}', result.stdout)
        self.assertEqual(2, ResetThenSuccessHandler.attempts)

    def test_bounds_total_time_when_public_endpoint_never_responds(self):
        server = ThreadingTCPServer(("127.0.0.1", 0), HangingHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        try:
            started_at = time.monotonic()
            result = subprocess.run(
                [
                    self.bash_path(),
                    SCRIPT_PATH.as_posix(),
                    f"http://127.0.0.1:{server.server_address[1]}/health",
                ],
                capture_output=True,
                env={
                    **os.environ,
                    "PUBLIC_HTTP_MAX_TIME_SECONDS": "1",
                    "PUBLIC_HTTP_RETRY_COUNT": "0",
                    "PUBLIC_HTTP_RETRY_DELAY_SECONDS": "0",
                    "PUBLIC_HTTP_RETRY_MAX_TIME_SECONDS": "2",
                },
                text=True,
                timeout=8,
            )
            elapsed = time.monotonic() - started_at
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

        self.assertNotEqual(0, result.returncode)
        self.assertLess(elapsed, 2)

    @staticmethod
    def bash_path():
        configured = os.environ.get("BASH_EXE")
        if configured:
            return configured
        if os.name == "nt":
            git_bash = Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "Git/bin/bash.exe"
            if git_bash.is_file():
                return str(git_bash)
        return shutil.which("bash") or "bash"


if __name__ == "__main__":
    unittest.main()
