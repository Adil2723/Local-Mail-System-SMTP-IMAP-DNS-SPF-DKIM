#!/usr/bin/env bash

set -o pipefail

cd "$HOME/computer-networks-project" || exit 1

umask 077

N="${1:-}"

ROOT="$PWD/captures/04_performance_tests"

ENGINE="$ROOT/benchmark_engine.py"

if [ ! -s "$ENGINE" ]; then
    echo "FAIL: Benchmark engine missing. Complete Test 03 first."
    exit 1
fi

case "$N" in

    04|05|06)
        CONDITION="100ms_RTT"
        MODE="delay"
        RTT=100
        DELAY=50
        RUN=$((10#$N - 3))
        ;;

    07|08|09)
        CONDITION="200ms_RTT"
        MODE="delay"
        RTT=200
        DELAY=100
        RUN=$((10#$N - 6))
        ;;

    10|11|12)
        CONDITION="2Percent_Loss"
        MODE="loss"
        RTT=0
        RUN=$((10#$N - 9))
        ;;

    13|14|15)
        CONDITION="1Mbps_Bandwidth"
        MODE="bandwidth"
        RTT=0
        RUN=$((10#$N - 12))
        ;;

    *)
        echo "Usage: bash run-performance.sh 04-15"
        exit 1
        ;;

esac

PREVIOUS=$(printf '%02d' "$((10#$N - 1))")

if ! grep -q "PERFORMANCE TEST $PREVIOUS RESULT: PASSED" \
    "$ROOT"/Test-"$PREVIOUS"_*/Terminal_Log.txt 2>/dev/null; then

    echo "FAIL: Previous Test $PREVIOUS is not confirmed as passed."
    exit 1

fi

if grep -q "PERFORMANCE TEST $N RESULT: PASSED" \
    "$ROOT"/Test-"$N"_*/Terminal_Log.txt 2>/dev/null; then

    echo "Test $N has already passed. Do not repeat unnecessarily."
    exit 0

fi

STAMP=$(date +%Y%m%d-%H%M%S)

DIR="$ROOT/Test-${N}_${CONDITION}_Run-${RUN}_${STAMP}"

mkdir -p "$DIR"

LOG="$DIR/Terminal_Log.txt"

(
set -e
set -o pipefail

R1_APPLIED=0
R2_APPLIED=0
IF1=""
IF2=""
START_UTC=""

cleanup() {

    STATUS=$?

    trap - EXIT

    set +e

    echo "===== SAVING FINAL NETWORK STATISTICS ====="

    if [ -n "$IF1" ] && [ -n "$IF2" ]; then
        {
            echo "R1:"
            ./run-cn12.sh exec -T r1 tc -s qdisc show dev "$IF1"
            echo "R2:"
            ./run-cn12.sh exec -T r2 tc -s qdisc show dev "$IF2"
        } > "$DIR/Traffic_Control_Final.txt"
    fi

    echo "===== RESTORING NORMAL NETWORK ====="

    if [ "$R1_APPLIED" -eq 1 ]; then
        ./run-cn12.sh exec -T r1 tc qdisc del dev "$IF1" root || STATUS=1
    fi

    if [ "$R2_APPLIED" -eq 1 ]; then
        ./run-cn12.sh exec -T r2 tc qdisc del dev "$IF2" root || STATUS=1
    fi

    for ROUTER in r1 r2; do

        QDISC=$(./run-cn12.sh exec -T "$ROUTER" tc qdisc show)

        if [ "$?" -ne 0 ]; then
            STATUS=1
            continue
        fi

        echo "$ROUTER:"
        printf '%s\n' "$QDISC"

        if printf '%s\n' "$QDISC" | grep -Eq 'qdisc (netem|tbf) '; then
            echo "WARNING: Network impairment remains on $ROUTER"
            STATUS=1
        fi

    done

    if [ -n "$START_UTC" ]; then

        ./run-cn12.sh logs --since="$START_UTC" mail-alpha \
        > "$DIR/Postfix_Alpha.txt" 2>&1 || STATUS=1

        ./run-cn12.sh logs --since="$START_UTC" mail-beta \
        > "$DIR/Postfix_Beta.txt" 2>&1 || STATUS=1

    fi

    if [ "$STATUS" -eq 0 ]; then
        echo "PASS: Normal network restored"
    fi

    exit "$STATUS"
}

trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

echo "========================================"
echo "PERFORMANCE TEST $N"
echo "Condition: $CONDITION"
echo "Run: $RUN of 3"
echo "Messages: 1000"
echo "========================================"

date

echo "===== STARTING COMPLETE PROJECT ====="

sudo systemctl start docker

./run-cn12.sh up -d --no-build

sleep 10

echo "===== VERIFYING ALL CONTAINERS ====="

for SERVICE in r1 r2 dns client-alpha client-beta mail-alpha mail-beta; do

    ID=$(./run-cn12.sh ps -q "$SERVICE")

    test -n "$ID"

    test "$(docker inspect --format '{{.State.Status}}' "$ID")" = "running"

    echo "PASS: $SERVICE running"

done

echo "===== IDENTIFYING ROUTER INTERFACES ====="

IF1=$(./run-cn12.sh exec -T r1 ip -o -4 addr show | awk '$4=="10.10.0.11/24"{print $2}')

IF2=$(./run-cn12.sh exec -T r2 ip -o -4 addr show | awk '$4=="10.10.0.12/24"{print $2}')

test -n "$IF1"
test -n "$IF2"

echo "R1 core interface: $IF1"
echo "R2 core interface: $IF2"

echo "===== CHECKING EXISTING NETWORK CONDITIONS ====="

for ROUTER in r1 r2; do

    QDISC=$(./run-cn12.sh exec -T "$ROUTER" tc qdisc show)

    printf '%s\n' "$QDISC"

    if printf '%s\n' "$QDISC" | grep -Eq 'qdisc (netem|tbf) '; then
        echo "FAIL: Existing network impairment detected"
        exit 1
    fi

done

echo "===== CHECKING INITIAL MAIL QUEUES ====="

for SERVICE in mail-alpha mail-beta; do

    QUEUE=$(./run-cn12.sh exec -T "$SERVICE" postqueue -p)

    printf '%s\n' "$QUEUE"

    printf '%s\n' "$QUEUE" | grep -F 'Mail queue is empty'

done

echo "===== CHECKING AVAILABLE STORAGE ====="

df -h .

./run-cn12.sh exec -T mail-beta df -h /home/adil/Maildir

echo "===== APPLYING NETWORK CONDITION ====="

case "$MODE" in

    delay)

        ./run-cn12.sh exec -T r1 tc qdisc add dev "$IF1" root netem delay "${DELAY}ms"

        R1_APPLIED=1

        ./run-cn12.sh exec -T r2 tc qdisc add dev "$IF2" root netem delay "${DELAY}ms"

        R2_APPLIED=1

        echo "PASS: ${RTT}ms additional RTT configured"

        ;;

    loss)

        ./run-cn12.sh exec -T r1 tc qdisc add dev "$IF1" root netem loss 2%

        R1_APPLIED=1

        echo "PASS: 2% forward-path random packet loss configured"

        ;;

    bandwidth)

        ./run-cn12.sh exec -T r1 tc qdisc add dev "$IF1" root tbf rate 1mbit burst 16kb latency 400ms

        R1_APPLIED=1

        ./run-cn12.sh exec -T r2 tc qdisc add dev "$IF2" root tbf rate 1mbit burst 16kb latency 400ms

        R2_APPLIED=1

        echo "PASS: 1 Mbps bandwidth limit configured in both directions"

        ;;

esac

echo "===== VERIFYING TRAFFIC CONTROL ====="

{
    echo "R1:"
    ./run-cn12.sh exec -T r1 tc -s qdisc show dev "$IF1"

    echo "R2:"
    ./run-cn12.sh exec -T r2 tc -s qdisc show dev "$IF2"

} | tee "$DIR/Traffic_Control_Initial.txt"

echo "===== MEASURING NETWORK RTT ====="

ALPHA_ID=$(./run-cn12.sh ps -q mail-alpha)

docker run --rm --pull never \
--network "container:$ALPHA_ID" \
--entrypoint ping cn12-nettools:local \
-c 20 -i 0.5 -W 3 10.10.2.10 \
| tee "$DIR/Network_RTT.txt"

echo "===== CHECKING SMTP WORKLOAD GENERATOR ====="

SOURCE=$(./run-cn12.sh exec -T mail-alpha sh -c 'command -v smtp-source || find /usr -type f -name smtp-source -print -quit')

test -n "$SOURCE"

echo "SMTP generator: $SOURCE"

echo "===== EXECUTING BENCHMARK ====="

START_UTC=$(date -u +%Y-%m-%dT%H:%M:%SZ)

python3 "$ENGINE" "$DIR" "$SOURCE" "Test-$N" "$CONDITION" "$RTT"

echo "===== FINAL CONTAINER STATUS ====="

./run-cn12.sh ps

echo "===== BENCHMARK EXECUTION COMPLETED ====="

) 2>&1 | tee "$LOG"

RESULT=$?

if [ "$RESULT" -eq 0 ]; then

    echo "PERFORMANCE TEST $N RESULT: PASSED" | tee -a "$LOG"

else

    echo "PERFORMANCE TEST $N RESULT: FAILED" | tee -a "$LOG"

fi

echo "===== SAVED EVIDENCE ====="

ls -lh "$DIR"

echo "Evidence directory: $DIR"

exit "$RESULT"
