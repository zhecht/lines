

STATIC="https://raw.githubusercontent.com/zhecht/playerprops/main/static"

curl "${STATIC}/mlb/schedule.json" -o "static/mlb/schedule.json"

curl "${STATIC}/baseballreference/bvp.json" -o "static/baseballreference/bvp.json"
curl "${STATIC}/baseballreference/leftOrRight.json" -o "static/baseballreference/leftOrRight.json"
curl "${STATIC}/baseballreference/ph.json" -o "static/baseballreference/ph.json"
curl "${STATIC}/baseballreference/roster.json" -o "static/baseballreference/roster.json"
