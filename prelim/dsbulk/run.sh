INPUT_DIR=$1
shift

SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
LOAD_DIR="$SCRIPT_DIR/data/$INPUT_DIR"
OUT_DIR="$SCRIPT_DIR/out/$INPUT_DIR"

docker compose exec -T scylla1 cqlsh -e \
  "CREATE KEYSPACE IF NOT EXISTS dsbulk WITH REPLICATION = { 'class': 'NetworkTopologyStrategy', 'datacenter1': 3 }";
docker compose exec -T scylla1 cqlsh \
  -k dsbulk < $LOAD_DIR/init.cql

TBLNAME=$(cat $LOAD_DIR/tblname.txt)

docker run --rm \
  --network ta \
  -v "$OUT_DIR:/work" \
  -v "$LOAD_DIR:/load" \
  dsbulk load \
  -h scylla1,scylla2,scylla3 \
  -k dsbulk \
  -t $TBLNAME \
  -url /load \
  -cl LOCAL_QUORUM \
  "$@"

rm -r $OUT_DIR/unload

docker run --rm \
  --network ta \
  -v "$OUT_DIR:/work" \
  -v "$OUT_DIR/unload:/unload" \
  dsbulk unload \
  -h scylla1,scylla2,scylla3 \
  -k dsbulk \
  -t $TBLNAME \
  -url "/unload" \
  -cl LOCAL_QUORUM \
  "$@"

docker compose exec -T scylla1 cqlsh \
  -k dsbulk < $LOAD_DIR/cleanup.cql