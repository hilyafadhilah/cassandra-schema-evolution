genbulk() {
  local gen="$1"; shift
  bash gen.sh "$gen" "$@"
}

runbulk() {
  local gen="$1"; shift
  mkdir -p out
  docker compose down -v
  docker compose up -d --wait
  nohup bash run_all.sh "$gen" "$@" > out/logs 2>&1 < /dev/null &
  echo $! > out/pid
}

cleanbulk() {
  rm -rf out/* data/*
}

watchbulk() {
  tail -f out/logs
}

killbulk() {
  if [ -f "out/pid" ]; then
    kill -- -"$(cat "out/pid")" 2>&1 || true
    rm -f "out/pid"
  fi
}

extractbulk() {
  local gen="$1"
  local out="$2"

  docker run --rm -it \
    -v "$PWD/out/$gen:/in" \
    -v "$PWD/results/$gen:/out" \
    -v "$PWD/extract.py:/app/extract.py" \
    py-scylla python -u /app/extract.py /in -o "/out/$out"
}

alias gb='genbulk'
alias rb='runbulk'
alias cb='cleanbulk'
alias wb='watchbulk'
alias kb='killbulk'
alias eb='extractbulk'