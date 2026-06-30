SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASEDIR="$SCRIPT_DIR/.."

DATA_DIR="$SCRIPT_DIR/data"
OUT_DIR="$SCRIPT_DIR/out"

rm -rf "$DATA_DIR" "$OUT_DIR"
mkdir -p "$DATA_DIR" "$OUT_DIR"

bash "$BASEDIR/gen.sh" p-N \
  --num-partitions 100 --partition-row-counts 1000 \
  --column-counts 1 3 5 7 10 12 15 17 20 \
  --pk-text

mv "$BASEDIR/data/pn"/* "$DATA_DIR/"

KEYSPACE="test_keyspace"

echo
echo "----------------------------------------"
echo "Creating keyspace $KEYSPACE"
docker compose exec -T scylla1 cqlsh -e \
  "DROP KEYSPACE IF EXISTS $KEYSPACE; CREATE KEYSPACE $KEYSPACE WITH REPLICATION = { 'class': 'NetworkTopologyStrategy', 'datacenter1': 3 };";

echo "----------------------------------------"
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
