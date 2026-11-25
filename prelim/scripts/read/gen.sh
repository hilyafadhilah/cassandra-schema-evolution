SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PARENT_DIR="$SCRIPT_DIR/.."

DATA_DIR="$SCRIPT_DIR/data" # where to store generated data
OUT_DIR="$SCRIPT_DIR/out"   # where to store dsbulk output

# 1. generate data

rm -rf "$DATA_DIR" "$OUT_DIR"
mkdir -p "$DATA_DIR" "$OUT_DIR"

# NOTE: Hardcoded parameters for data generation. Adjust as needed.
docker run --rm -it \
  -v "$PARENT_DIR/gen:/app" \
  -v "$DATA_DIR:/app/data/pn" \
  py-scylla python -u -m app.pn \
  --num-partitions 100 --partition-row-counts 1000 \
  --column-counts 1 3 5 7 10 12 15 17 20 \
  --pk-text

# 2. intialize db

KEYSPACE="prelim"

echo
echo "----------------------------------------"

echo "Creating keyspace $KEYSPACE"
docker compose exec -T scylla1 cqlsh -e \
  "DROP KEYSPACE IF EXISTS $KEYSPACE; CREATE KEYSPACE $KEYSPACE WITH REPLICATION = { 'class': 'NetworkTopologyStrategy', 'datacenter1': 3 };";

echo "----------------------------------------"

# 3. load data

for input_dir in "$DATA_DIR"/*; do
  load_name=$(basename "$input_dir")
  echo "Loading data for $load_name"

  tblname=$(cat $input_dir/tblname.txt)
  echo "Using table name: $tblname"

  docker compose exec -T scylla1 cqlsh \
    -k $KEYSPACE < $input_dir/init.cql

  out_dir="$OUT_DIR/$load_name"

  docker run --rm \
    --network ta \
    -v "$out_dir:/work" \
    -v "$input_dir:/load" \
    dsbulk load \
    -h scylla1,scylla2,scylla3 \
    -k $KEYSPACE \
    -t $tblname \
    -url /load \
    -cl LOCAL_QUORUM \
    "$@"

  echo "Data loading for $load_name completed"
  echo "----------------------------------------"
done
