gen_prel() {
  local gen="$1"; shift
  bash gen.sh "$gen" "$@"
}

run_prel() {
  local gen="$1"; shift
  mkdir -p out
  docker compose down -v
  docker compose up -d --wait
  nohup bash run.sh "$gen" "$@" > out/logs 2>&1 < /dev/null &
  echo $! > out/pid
}

clean_prel() {
  rm -rf out/* data/*
}

watch_prel() {
  tail -f out/logs
}

kill_prel() {
  if [ -f "out/pid" ]; then
    kill -- -"$(cat "out/pid")" 2>&1 || true
    rm -f "out/pid"
  fi
}

extract_prel() {
  local gen="$1"
  local out="$2"

  docker run --rm -it \
    -v "$PWD/out/$gen:/in" \
    -v "$PWD/results/$gen:/out" \
    -v "$PWD/extract.py:/app/extract.py" \
    py-scylla python -u /app/extract.py /in -o "/out/$out"
}

alias gpr='gen_prel'
alias rpr='run_prel'
alias cpr='clean_prel'
alias wpr='watch_prel'
alias kpr='kill_prel'
alias epr='extract_prel'