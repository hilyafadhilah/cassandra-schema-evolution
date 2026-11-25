SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

GEN_DIR="$SCRIPT_DIR/data/$1"
OUT_DIR="$SCRIPT_DIR/out/$1"
shift

KEYSPACE="prelim"

# load-unload logic for each table

run() {
  local load_dir="$1"
  local out_dir="$2"

  local tblname=$(cat "$load_dir/tblname.txt")

  docker compose exec -T scylla1 cqlsh \
    -k $KEYSPACE < $load_dir/init.cql

  docker run --rm \
    --network ta \
    -v "$out_dir:/work" \
    -v "$load_dir:/load" \
    dsbulk load \
    -h scylla1,scylla2,scylla3 \
    -k $KEYSPACE \
    -t $tblname \
    -url /load \
    -cl LOCAL_QUORUM \
    "$@"

  rm -rf $out_dir/unload

  docker run --rm \
    --network ta \
    -v "$out_dir:/work" \
    -v "$out_dir/unload:/unload" \
    dsbulk unload \
    -h scylla1,scylla2,scylla3 \
    -k $KEYSPACE \
    -t $tblname \
    -url "/unload" \
    -cl LOCAL_QUORUM \
    "$@"

  docker compose exec -T scylla1 cqlsh \
    -k $KEYSPACE < $load_dir/cleanup.cql
}

# main logic: load & unload for each input dir, repeat 5 times

docker compose exec -T scylla1 cqlsh -e \
  "CREATE KEYSPACE IF NOT EXISTS $KEYSPACE WITH REPLICATION = { 'class': 'NetworkTopologyStrategy', 'datacenter1': 3 }";

for load_dir in "$GEN_DIR"/*; do
  out_dir="$OUT_DIR/$(basename $load_dir)"

  echo "[+] Processing input: $load_dir"
  echo "    → output = $out_dir"
  echo

  for i in {1..5}; do
    echo "[+] Run #$i"
    echo

    run "$load_dir" "$out_dir" "$@"

    echo
    echo "[✔] Completed run #$i for input: $load_dir"
    echo "    → output = $out_dir"
    echo

    sleep 5
  done
done