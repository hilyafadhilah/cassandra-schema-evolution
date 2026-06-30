SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASEDIR="$SCRIPT_DIR/data/"

DATA_DIR=$1
shift

for input_dir in $(ls "$BASEDIR/$DATA_DIR"); do
  DIR="$DATA_DIR/$input_dir"
  echo "[+] Processing input: $DIR"

  for i in {1..5}; do
    echo "[+] Run #$i"
    echo

    bash $SCRIPT_DIR/run.sh "$DIR" "$@"

    echo
    echo "[+] Completed run #$i for input: $DIR"

    sleep 5
  done
done