SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )

mkdir -p "$SCRIPT_DIR/results"

KEYSPACE="prelim"
RESULT_FILE="result-$(date +%Y%m%d-%H%M%S).csv"

docker run --rm -it --network ta \
  -v "$SCRIPT_DIR/read.py:/app/read.py" \
  -v "$SCRIPT_DIR/results:/app/results" \
  -v "$SCRIPT_DIR/data:/app/in" \
  py-scylla python -u /app/read.py /app/in \
  --contact-points scylla1 scylla2 scylla3 \
  --keyspace $KEYSPACE \
  --output-file /app/results/$RESULT_FILE \
  "$@"