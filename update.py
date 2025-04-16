
import requests


if __name__ == "__main__":
	base = "https://api.github.com/repos/zhecht/playerprops/contents/static"
	url = f"{base}/mlb/schedule.json"
	response = requests.get(url, headers={"Accept": "application/vnd.github.v3.raw"})
	schedule = response.json()

	with open(f"static/mlb/schedule.json", "w") as fh:
		json.dump(schedule, fh, indent=4)

	for key in ["bvp", "leftOrRight", "ph", "roster"]:
		url = f"{base}/baseballreference/{key}.json"
		response = requests.get(url, headers={"Accept": "application/vnd.github.v3.raw"})
		j = response.json()
		with open(f"static/baseballreference/{key}.json", "w") as fh:
			json.dump(j, fh, indent=4)