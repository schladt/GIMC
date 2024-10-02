from app import create_app, db
from app.models import *
import sys

app = create_app()

if __name__ == "__main__":
    # get the first argument
    if len(sys.argv) > 2:
        interface = sys.argv[1]
        port = sys.argv[2]
    else:
        # exit
        print("Usage: python run.py <interface address> <port>")
        sys.exit(1)

    app.run(debug=True, host=interface, port=port, threaded=True)