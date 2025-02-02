import socket
from http.server import BaseHTTPRequestHandler
from io import BytesIO


class HTTPRequest(BaseHTTPRequestHandler):
    def __init__(self, request_text):
        self.rfile = BytesIO(request_text)
        self.raw_requestline = self.rfile.readline()
        self.error_code = self.error_message = None
        self.parse_request()

    def send_error(self, code, message):
        self.error_code = code
        self.error_message = message


class HTTPServer:
    def __init__(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.conn = self.host = self.port = None
        self.bound = False

    @property
    def addresses(self):
        if self.host:
            return [self.host]

        addrs = set()
        try:
            for info in socket.getaddrinfo(socket.gethostname(), self.port,
                                           socket.AF_INET):
                addrs.add(info[4][0])
        except socket.gaierror:
            pass

        addrs.add("127.0.0.1")
        return sorted(addrs)

    @property
    def urls(self):
        for addr in self.addresses:
            yield "http://{0}:{1}/".format(addr, self.port)

    @property
    def url(self):
        return next(self.urls, None)

    def bind(self, host="127.0.0.1", port=0):
        try:
            self.socket.bind((host or "", port))
        except OSError:
            raise

        self.socket.listen(1)
        self.bound = True
        self.host, self.port = self.socket.getsockname()
        if self.host == "0.0.0.0":
            self.host = None

    def open(self, timeout=30):
        self.socket.settimeout(timeout)

        try:
            conn, addr = self.socket.accept()
            conn.settimeout(None)
        except socket.timeout as err:
            raise OSError("Socket accept timed out") from err

        try:
            req_data = conn.recv(1024)
        except OSError as err:
            raise OSError("Failed to read data from socket") from err

        req = HTTPRequest(req_data)
        if req.command not in ("GET", "HEAD"):
            conn.send(b"HTTP/1.1 501 Not Implemented\r\n")
            conn.close()
            raise OSError(f"Invalid request method: {req.command}")

        try:
            conn.send(b"HTTP/1.1 200 OK\r\n")
            conn.send(b"Server: Streamlink\r\n")
            conn.send(b"Content-Type: video/unknown\r\n")
            conn.send(b"\r\n")
        except OSError as err:
            raise OSError("Failed to write data to socket") from err

        # We don't want to send any data on HEAD requests.
        if req.command == "HEAD":
            conn.close()
            raise OSError

        self.conn = conn

        return req

    def write(self, data):
        if not self.conn:
            raise OSError("No connection")

        self.conn.sendall(data)

    def close(self, client_only=False):
        if self.conn:
            self.conn.close()

        if not client_only:
            try:
                self.socket.shutdown(2)
            except OSError:
                pass
            self.socket.close()
