
import argparse
import json
import math
import os
import random
import queue
import re
import time
import nodriver as uc
import requests
import subprocess
import threading
import multiprocessing
import numpy as np
from pdf2image import convert_from_path
import pytesseract
from PIL import Image

from bs4 import BeautifulSoup as BS
from shared import *
from datetime import datetime, timedelta

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

"""
	What is a Barrel
	https://www.mlb.com/glossary/statcast/barrel

	General: >= 98 EVO && 26 <= LA <= 30
	99 EVO (25-31 LA)
	100 EVO (24-33 LA)
	101 EVO (23-34), 102 (22-35), 103 (21-36)
	116 (8-50)
"""

def barrelDefinition():
	barrel_threshold = {
		98: [26,30],
		99: [25,31],
	}
	evo = 100
	minLA, maxLA = 24, 33

	while evo <= 116:
		#print(evo, minLA, maxLA)
		barrel_threshold[evo] = [minLA, maxLA]
		minLA -= 1
		maxLA += 1
		evo += 1

	print(barrel_threshold)

def convertBPPTeam(team):
	team = team.lower()
	if team == "was":
		return "wsh"
	return team

def writeMostLikely(date):
	with open("static/mlb/schedule.json") as fh:
		schedule = json.load(fh)

	games = [x["game"] for x in schedule[date]]
	teamGame = {}
	for game in games:
		a,h = map(str, game.split(" @ "))
		teamGame[a] = game
		teamGame[h] = game

	url = "https://www.ballparkpal.com/Most-Likely.php"
	likely = nested_dict()

	soup = BS(open("static/bpp/likely.html"), "html.parser")
	for row in soup.select("#batterTable tr")[1:]:
		team = convertBPPTeam(row.select("td[data-column=team]")[0].text.lower())
		game = teamGame.get(team, "")
		player = parsePlayer(row.select("td[data-column=entity]")[0].text.lower())
		prob = parsePlayer(row.select("td[data-column=probability0]")[0].text.lower())
		odds = parsePlayer(row.select("td[data-column=book0]")[0].text.lower())
		likely[game][player]["implied"] = prob
		likely[game][player]["odds"] = odds

	with open("static/bpp/likely.json", "w") as fh:
		json.dump(likely, fh, indent=4)


def writeParkFactors(date):
	url = "https://www.ballparkpal.com/Park-Factors.php"
	factors = nested_dict()

	soup = BS(open("static/bpp/factors.html"), "html.parser")

	games = soup.select(f"td[data-column=Game]")
	arr = [("hr", "HomeRuns"), ("2b/3b", "DoublesTriples"), ("1b", "Singles"), ("r", "Runs")]
	teamGame = {}
	for prop, colName in arr:
		cols = soup.select(f"td[data-column={colName}]")
		seenGame = {}
		for game, col in zip(games, cols):
			roofClosed = len(game.select("img[src*=RoofClosed]")) > 0
			game = game.find("a", class_="gameLink").text.lower()
			words = [x for x in game.split(" ") if x]
			game = " ".join(words)
			a,h = map(str, game.split(" @ "))
			a = convertBPPTeam(a)
			h = convertBPPTeam(h)
			game = f"{a} @ {h}"
			seen = seenGame.get(game, False)
			if game in seenGame:
				game += "-gm2"
			else:
				seenGame[game] = True
				teamGame[a] = game
				teamGame[h] = game
			factors[game]["roof"] = roofClosed
			factors[game][prop] = col.text

	for rows in soup.select("#table_id tbody tr"):
		tds = rows.select("td")
		team = convertBPPTeam(tds[0].text.lower().strip())
		game = teamGame.get(team, "")
		player = parsePlayer(tds[1].text)

		i = 3
		for k in ["hr", "2b/3b", "1b"]:
			factor = tds[i].text
			factorColor = tds[i].get("style").split("; ")[1].split(": ")[-1]

			factors[game]["players"][player][k] = factor
			factors[game]["players"][player][k+"color"] = factorColor

	with open("static/bpp/factors.json", "w") as fh:
		json.dump(factors, fh, indent=4)

if __name__ == '__main__':
	parser = argparse.ArgumentParser()
	parser.add_argument("--date", "-d")
	parser.add_argument("--likely", action="store_true")
	parser.add_argument("--factors", action="store_true")
	parser.add_argument("--update", "-u", action="store_true")
	parser.add_argument("--commit", "-c", action="store_true")

	args = parser.parse_args()

	date = args.date
	if not date:
		date = str(datetime.now())[:10]

	if args.factors:
		writeParkFactors(date)

	if args.likely:
		writeMostLikely(date)

	if args.update:
		writeParkFactors(date)
		writeMostLikely(date)

	if args.commit:
		commitChanges()

	#barrelDefinition()