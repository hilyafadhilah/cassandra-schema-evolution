runtest() {
  local evol="$1"; shift
  mkdir -p "$evol/out"
  nohup bash run.sh "$evol" "$@" > "$evol/out/logs" 2>&1 < /dev/null &
  echo $! > "$evol/out/pid"

  export TEST_EVOL="$evol"
}

cleantest() {
  local evol="${1:-$TEST_EVOL}"
  rm -rf "$evol/out"/*
}

watchtest() {
  local evol="${1:-$TEST_EVOL}"
  tail -f "$evol/out/logs"
}

killtest() {
  local evol="${1:-$TEST_EVOL}"
  if [ -f "$evol/out/pid" ]; then
    kill -- -"$(cat "$evol/out/pid")" 2>&1 || true
    rm -f "$evol/out/pid"
  fi
}

settest() {
  export TEST_EVOL="$1"
}

alias rt='runtest'
alias ct='cleantest'
alias wt='watchtest'
alias kt='killtest'
alias st='settest'