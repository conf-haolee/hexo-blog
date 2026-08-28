"""HTTP client for the Workboard archive agent API."""

import json
import mimetypes
import uuid
from urllib import error, parse, request


class ArchiveClient:
    def __init__(self, base_url: str, token: str, agent_id: str, timeout: int = 30):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.agent_id = agent_id
        self.timeout = timeout

    def claim(self, lease_token: str | None = None) -> dict:
        payload = {"agentId": self.agent_id}
        if lease_token:
            payload["leaseToken"] = lease_token
        return self._json_request("POST", "/api/agent/jobs/claim", payload)

    def upload_file(self, todo_id, lease_token, relative_path, stream, size, sha256) -> dict:
        fields = {
            "relativePath": relative_path,
            "expectedSize": str(size),
            "expectedSha256": sha256,
        }
        return self._multipart_request("PUT", f"/api/agent/jobs/{todo_id}/files", lease_token, fields, stream, relative_path)

    def commit(self, todo_id, lease_token, manifest) -> dict:
        return self._json_request("POST", f"/api/agent/jobs/{todo_id}/commit", {"manifest": manifest}, lease_token)

    def finish(self, todo_id, lease_token) -> dict:
        return self._json_request("POST", f"/api/agent/jobs/{todo_id}/finish", {}, lease_token)

    def fail(self, todo_id, lease_token, error_message) -> dict:
        return self._json_request("POST", f"/api/agent/jobs/{todo_id}/fail", {"error": str(error_message)}, lease_token)

    def _json_request(self, method, path, payload, lease_token=None):
        data = json.dumps(payload).encode("utf-8")
        headers = self._headers(lease_token)
        headers["Content-Type"] = "application/json"
        return self._open(method, path, data, headers)

    def _multipart_request(self, method, path, lease_token, fields, stream, filename):
        boundary = f"workboard-{uuid.uuid4().hex}"
        body = bytearray()
        for name, value in fields.items():
            body.extend(f"--{boundary}\r\n".encode("ascii"))
            body.extend(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode("ascii"))
            body.extend(str(value).encode("utf-8"))
            body.extend(b"\r\n")
        content = stream.read()
        body.extend(f"--{boundary}\r\n".encode("ascii"))
        body.extend(
            (
                f'Content-Disposition: form-data; name="file"; filename="{parse.quote(str(filename))}"\r\n'
                f"Content-Type: {mimetypes.guess_type(str(filename))[0] or 'application/octet-stream'}\r\n\r\n"
            ).encode("ascii")
        )
        body.extend(content)
        body.extend(b"\r\n")
        body.extend(f"--{boundary}--\r\n".encode("ascii"))
        headers = self._headers(lease_token)
        headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
        return self._open(method, path, bytes(body), headers)

    def _headers(self, lease_token=None):
        headers = {
            "Authorization": f"Bearer {self.token}",
            "X-Workboard-Agent-Id": self.agent_id,
        }
        if lease_token:
            headers["X-Workboard-Lease-Token"] = lease_token
        return headers

    def _open(self, method, path, data, headers):
        url = f"{self.base_url}{path}"
        req = request.Request(url, data=data, headers=headers, method=method)
        try:
            with request.urlopen(req, timeout=self.timeout) as response:
                content = response.read()
        except error.HTTPError as exc:
            body = self._safe_error_body(exc)
            exc.close()
            raise RuntimeError(f"Workboard request failed with HTTP {exc.code}: {body}") from exc
        except error.URLError as exc:
            raise RuntimeError(f"Workboard request failed: {exc.reason}") from exc
        return json.loads(content.decode("utf-8") or "{}")

    def _safe_error_body(self, exc):
        try:
            body = exc.read().decode("utf-8", errors="replace")[:500]
        except OSError:
            return ""
        for secret in (self.token, f"Bearer {self.token}"):
            if secret:
                body = body.replace(secret, "[redacted]")
        return body
