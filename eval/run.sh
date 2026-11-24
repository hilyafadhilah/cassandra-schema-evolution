#! /bin/bash

set -e

SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
TIMESTAMP=$(date +"%Y-%m-%dT%H-%M-%S")

EVOL_NAME="$1"
shift

OUTPUT_DIR="$SCRIPT_DIR/$EVOL_NAME/out"

DATA_DIR="$OUTPUT_DIR/data"
mkdir -p "$DATA_DIR"

docker run --rm -i \
  -v "$SCRIPT_DIR/lib:/app/test/lib" \
  -v "$SCRIPT_DIR/$EVOL_NAME/$EVOL_NAME.py:/app/test/$EVOL_NAME/$EVOL_NAME.py" \
  -v "$SCRIPT_DIR/$EVOL_NAME/in.yml:/app/test/$EVOL_NAME/in.yml" \
  -v "$DATA_DIR:/out" \
  -w /app \
  py-scylla \
  python -u -m "test.$EVOL_NAME.$EVOL_NAME" -o /out "$@"


echo


dsbulk() {
  local cmd="$1"
  local keyspace="$2"
  local tblname="$3"
  local url="$4"
  local work_dir="$5"
  shift 5

  echo "[test run.sh] dsbulk $cmd"
  echo "  • table = $tblname"
  echo "  • url   = $url"
  echo "  • work  = $work_dir"
  echo

  if [ "$cmd" = "unload" ]; then
    rm    -rf "$url"
    mkdir -p  "$url"
  fi

  docker run --rm \
    --network ta \
    -v "$work_dir:/work" \
    -v "$url:/$cmd" \
    dsbulk $cmd \
    -h scylla1,scylla2,scylla3 \
    -k $keyspace \
    -t $tblname \
    -url /$cmd \
    -cl LOCAL_QUORUM \
    -escape '\"' \
    "$@"

  echo
  echo "  ✔ dsbulk $cmd completed"
  echo
}

load_cql() {
  local keyspace="$1"
  local cql_file="$2"
  shift 2

  echo "[test run.sh] loading cql: $cql_file"

  docker compose exec -T scylla1 cqlsh \
    -k $keyspace "$@" < $cql_file

  echo "  ✔ cql loaded"
  echo
}


save_snapshot() {
  local keyspace="$1"
  local snapshot_name="$2"
  local nodes=(scylla1 scylla2 scylla3)

  echo "[test run.sh] saving snapshot: $snapshot_name"

  for node in "${nodes[@]}"; do
    docker compose exec -T "$node" nodetool clearsnapshot \
      -t "$snapshot_name" "$keyspace"
    docker compose exec -T "$node" nodetool snapshot \
      -t "$snapshot_name" "$keyspace"
  done

  echo "  ✔ snapshot saved"
  echo
}


restore_snapshot() {
  local snapshot_name="$1"
  local keyspace="$2"
  local cql_dir="$3"
  shift 3

  local tblnames=("$@")

  echo "[test run.sh] restoring snapshot: $snapshot_name"
  echo "  > recreate schema"

  echo "  > load cql: $cql_dir/cleanup.cql"
  docker compose exec -T scylla1 cqlsh \
    -k $keyspace < $cql_dir/cleanup.cql
  echo "  ✔ schema cleaned"

  echo "  > load cql: $cql_dir/startup.cql"
  docker compose exec -T scylla1 cqlsh \
    -k $keyspace < $cql_dir/startup.cql
  echo "  ✔ schema recreated"

  echo "  > copy snapshot files and refresh"

  local nodes=(scylla1 scylla2 scylla3)
  for tblname in "${tblnames[@]}"; do
    uuid=$(docker compose exec -T ${nodes[0]} cqlsh -e \
      "SELECT id FROM system_schema.tables WHERE keyspace_name='$keyspace' AND table_name='$tblname';" \
      | grep -oE '[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}' | head -1 | tr -d -)

    for node in "${nodes[@]}"; do
      docker compose exec -T $node bash -c "
        KS=$keyspace; TBL=$tblname; TAG=$snapshot_name
        live=/var/lib/scylla/data/\$KS/\$TBL-$uuid/upload
        snap=\$(ls -d /var/lib/scylla/data/\$KS/\$TBL-*/snapshots/\$TAG 2>/dev/null | head -1)
        mkdir -p \"\$live\"
        [ -n \"\$snap\" ] && cp \"\$snap\"/* \"\$live\"/ && nodetool refresh \$KS \$TBL
      "
    done
  done

  echo "  ✔ snapshot restored"
  echo
}


WORK_DIR="$OUTPUT_DIR/work/$TIMESTAMP"
mkdir -p "$WORK_DIR"

for subcase in "$DATA_DIR"/*; do
  subcase=$(basename "$subcase")

  if [ -d "$DATA_DIR/$subcase" ]; then
    echo " ===== Subcase: $subcase ====="
    echo

    docker compose down -v

    docker compose up -d --wait

    keyspace=$(echo "test_${EVOL_NAME}_${subcase}" | tr '[:upper:]' '[:lower:]')

    docker compose exec -T scylla1 cqlsh -e \
      "CREATE KEYSPACE IF NOT EXISTS $keyspace WITH REPLICATION = { 'class': 'NetworkTopologyStrategy', 'datacenter1': 3 }";

    echo "[test run.sh] created keyspace $keyspace"
    echo

    init_dir="$DATA_DIR/$subcase/init"
    load_cql $keyspace "$init_dir/startup.cql"

    tblnames=()

    for tblname in "$init_dir"/*; do
      if [ ! -d "$tblname" ]; then
        continue
      fi

      tblname=$(basename "$tblname")
      tblnames+=("$tblname")

      mkdir -p "$WORK_DIR/$subcase/init/$tblname"
      dsbulk load \
        $keyspace $tblname \
        "$DATA_DIR/$subcase/init/$tblname" \
        "$WORK_DIR/$subcase/init/$tblname" \
        --connector.csv.maxCharsPerColumn -1
    done

    for i in {1..5}; do
      for tblname in "${tblnames[@]}"; do
        dsbulk unload \
          $keyspace $tblname \
          "$WORK_DIR/$subcase/init/$tblname/unload" \
          "$WORK_DIR/$subcase/init/$tblname"
      done
    done

    snapshot="snapshot_$subcase"
    save_snapshot $keyspace $snapshot

    for i in {1..5}; do
      echo
      echo " ===== $subcase #$i ====="
      echo

      for evol_dir in "$DATA_DIR/$subcase"/*; do
        evol=$(basename "$evol_dir")

        if [ "$evol" = "init" ]; then
          continue
        fi

        restore_snapshot $snapshot $keyspace "$init_dir" "${tblnames[@]}"

        load_cql $keyspace "$evol_dir/startup.cql"

        for tblname in "$evol_dir"/*; do
          if [ ! -d "$tblname" ]; then
            continue
          fi

          tblname=$(basename "$tblname")

          evol_workdir="$WORK_DIR/$subcase/$evol"
          mkdir -p "$evol_workdir/$tblname"

          dsbulk load \
            $keyspace $tblname \
            "$evol_dir/$tblname" \
            "$evol_workdir/$tblname" \
            --schema.allowMissingFields true \
            --connector.csv.maxCharsPerColumn -1
        done

        load_cql $keyspace "$evol_dir/cleanup.cql"
      done
    done

    load_cql $keyspace "$init_dir/cleanup.cql"

    docker compose exec -T scylla1 cqlsh -e \
      "DROP KEYSPACE IF EXISTS $keyspace";
  fi
done

echo
echo " ===== Test completed ====="
echo