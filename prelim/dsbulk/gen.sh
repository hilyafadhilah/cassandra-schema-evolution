SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )

SCRIPT_NAME="$1"
shift

docker run --rm -it \
  -v "$SCRIPT_DIR/gen:/app" \
  -v "$SCRIPT_DIR/data:/app/data" \
  py-scylla python -u /app/$SCRIPT_NAME.py "$@"