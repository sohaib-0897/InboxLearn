"""Run the InboxLearn FastAPI inference and lifecycle server."""
import sys
import uvicorn
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from inboxlearn.api import create_app
from inboxlearn.service import InboxLearnService

def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    host = "127.0.0.1"
    print(f"\n=======================================================")
    print(f"  INBOXLEARN HIGH-PERFORMANCE INFERENCE API")
    print(f"  Listening at: http://{host}:{port}")
    print(f"  Documentation: http://{host}:{port}/docs")
    print(f"=======================================================\n")
    uvicorn.run("inboxlearn.api:app", host=host, port=port, log_level="info", reload=False)

if __name__ == "__main__":
    main()
