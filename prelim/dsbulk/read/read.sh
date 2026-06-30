SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )

mkdir -p "$SCRIPT_DIR/out"

docker run --rm -it --network ta \
  -v "$SCRIPT_DIR/read.py:/app/read.py" \
  -v "$SCRIPT_DIR/out:/app/out" \
  -v "$SCRIPT_DIR/data:/app/in" \
  py-scylla python -u /app/read.py /app/in \
  --contact-points scylla1 scylla2 scylla3 \
  --keyspace test_keyspace \
  --output-file /app/out/results.csv \
  "$@"