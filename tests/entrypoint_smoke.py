"""Start the real runner using an isolated mock Secret API and ephemeral TLS keys.

No real Kubernetes configuration, credentials, clouds or controller are used.
Host networking is for the container to reach this test's loopback API server.
"""

import argparse
import base64
import http.server
import json
import os
import pathlib
import socket
import ssl
import subprocess
import tempfile
import threading
import time
import urllib.parse
import uuid


def run(engine, *arguments, **kwargs):
    return subprocess.run([engine, *arguments], check=True, text=True, **kwargs)


def test_entrypoint(engine, image, uid, explicit_user):
    with tempfile.TemporaryDirectory(prefix="runner-tls-") as temporary:
        directory = pathlib.Path(temporary)
        directory.chmod(0o755)
        key = directory / "key.pem"
        cert = directory / "cert.pem"
        # Runner v0.16.3 parses PKCS#1 RSA keys, not PKCS#8. These keys are dummy,
        # short-lived test fixtures and never leave the test machine.
        subprocess.run(["openssl", "genrsa", "-traditional", "-out", str(key), "2048"],
                       check=True, capture_output=True)
        subprocess.run([
            "openssl", "req", "-new", "-x509", "-key", str(key), "-out", str(cert),
            "-days", "1", "-subj", "/CN=localhost",
            "-addext", "subjectAltName=DNS:localhost,IP:127.0.0.1",
            "-addext", "extendedKeyUsage=serverAuth,clientAuth",
        ], check=True, capture_output=True)
        data = {name: base64.b64encode(path.read_bytes()).decode() for name, path in
                (("ca.crt", cert), ("ca.key", key), ("tls.crt", cert), ("tls.key", key))}
        secret_path = "/api/v1/namespaces/rock-smoke/secrets/smoke-tls"
        requested = threading.Event()

        class API(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                path = urllib.parse.urlsplit(self.path).path
                responses = {
                    "/api": {"kind": "APIVersions", "apiVersion": "v1", "versions": ["v1"]},
                    "/apis": {"kind": "APIGroupList", "apiVersion": "v1", "groups": []},
                    "/api/v1": {
                        "kind": "APIResourceList", "apiVersion": "v1", "groupVersion": "v1",
                        "resources": [{"name": "secrets", "singularName": "secret",
                                       "namespaced": True, "kind": "Secret", "verbs": ["get"]}],
                    },
                    secret_path: {
                        "kind": "Secret", "apiVersion": "v1",
                        "metadata": {"name": "smoke-tls", "namespace": "rock-smoke"}, "data": data,
                    },
                }
                if path == secret_path:
                    requested.set()
                payload = json.dumps(responses.get(path, {"kind": "Status", "code": 404})).encode()
                self.send_response(200 if path in responses else 404)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, *args):
                pass

        api = http.server.ThreadingHTTPServer(("127.0.0.1", 0), API)
        thread = threading.Thread(target=api.serve_forever, daemon=True)
        thread.start()
        kubeconfig = directory / "kubeconfig"
        kubeconfig.write_text(json.dumps({
            "apiVersion": "v1", "kind": "Config",
            "clusters": [{"name": "smoke", "cluster": {"server": f"http://127.0.0.1:{api.server_port}"}}],
            "users": [{"name": "smoke", "user": {}}],
            "contexts": [{"name": "smoke", "context": {"cluster": "smoke", "user": "smoke"}}],
            "current-context": "smoke",
        }))
        kubeconfig.chmod(0o644)
        with socket.socket() as available:
            available.bind(("127.0.0.1", 0))
            port = available.getsockname()[1]
        name = "rock-smoke-" + uuid.uuid4().hex
        arguments = [
            "run", "-d", "--name", name, "--network", "host", "--read-only",
            "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
            "--tmpfs", "/tmp:rw,nosuid,nodev,mode=1777",
            "--tmpfs", f"/home/runner:rw,nosuid,nodev,uid={uid},gid={uid},mode=0700",
            "--mount", f"type=bind,source={kubeconfig},target=/test-kubeconfig,readonly",
            "-e", "KUBECONFIG=/test-kubeconfig", "-e", "POD_NAMESPACE=rock-smoke",
            "-e", "POD_NAME=smoke-runner",
        ]
        if explicit_user:
            arguments.extend(["--user", f"{uid}:{uid}"])
        arguments.extend([image, "--grpc-port", str(port), "--tls-secret-name", "smoke-tls",
                          "--grpc-max-message-size", "4"])
        try:
            run(engine, *arguments, capture_output=True)
            context = ssl.create_default_context(cafile=str(cert))
            context.load_cert_chain(str(cert), str(key))
            context.set_alpn_protocols(["h2"])
            deadline = time.monotonic() + 30
            while True:
                try:
                    with (
                        socket.create_connection(("127.0.0.1", port), timeout=1) as connection,
                        context.wrap_socket(connection, server_hostname="localhost") as tls,
                    ):
                        assert tls.selected_alpn_protocol() == "h2", "Runner did not negotiate HTTP/2"
                    break
                except (OSError, ssl.SSLError):
                    if time.monotonic() >= deadline:
                        raise
                    time.sleep(0.2)
            assert requested.is_set(), "Runner did not request the configured TLS Secret"
            actual_uid = run(engine, "exec", name, "id", "-u", capture_output=True).stdout.strip()
            assert actual_uid == str(uid), f"Unexpected runtime UID: {actual_uid}"
            # Allow Pebble's startup change to finish before testing shutdown.
            time.sleep(2)
            run(engine, "stop", "--time", "15", name, capture_output=True)
            code = run(engine, "inspect", "--format", "{{.State.ExitCode}}", name,
                       capture_output=True).stdout.strip()
            assert code == "0", f"Supervisor exited with {code}"
            logs = run(engine, "logs", name, capture_output=True)
            assert "Starting the runner" in logs.stdout + logs.stderr, "Runner logs were not forwarded"
            print(f"Entrypoint, Secret lookup, mTLS/HTTP2 and shutdown passed at UID {uid}")
        finally:
            subprocess.run([engine, "logs", name], check=False)
            subprocess.run([engine, "rm", "-f", name], check=False, capture_output=True)
            api.shutdown()
            api.server_close()
            thread.join()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", default=os.environ.get("CONTAINER_ENGINE", "docker"))
    parser.add_argument("image")
    options = parser.parse_args()
    test_entrypoint(options.engine, options.image, 65532, True)
    test_entrypoint(options.engine, options.image, 584792, False)
