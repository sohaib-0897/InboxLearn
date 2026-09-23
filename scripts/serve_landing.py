"""Simple HTTP server to preview the InboxLearn landing page locally."""
import http.server
import socketserver
import webbrowser
import sys
from pathlib import Path

PORT = 3000

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(Path(__file__).parent.parent / "landing"), **kwargs)

def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else PORT
    with socketserver.TCPServer(("", port), Handler) as httpd:
        url = f"http://localhost:{port}"
        print(f"\n=======================================================")
        print(f"  INBOXLEARN LANDING PAGE SERVER")
        print(f"  Serving 'landing/' at: {url}")
        print(f"  Press Ctrl+C to stop.")
        print(f"=======================================================\n")
        try:
            webbrowser.open(url)
        except Exception:
            pass
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down landing page server.")

if __name__ == "__main__":
    main()
