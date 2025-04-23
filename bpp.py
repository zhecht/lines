
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


def writeParkFactors():
	url = "https://www.ballparkpal.com/Park-Factors.php"
	factors = nested_dict()

	soup = BS(open("static/bpp/factors.html"), "html.parser")

	games = soup.select(f"td[data-column=Game]")
	arr = [("hr", "HomeRuns"), ("2b/3b", "DoublesTriples"), ("1b", "Singles"), ("r", "Runs")]
	teamGame = {}
	for prop, colName in arr:
		cols = soup.select(f"td[data-column={colName}]")
		for game, col in zip(games, cols):
			game = game.find("a", class_="gameLink").text.lower()
			words = [x for x in game.split(" ") if x]
			game = " ".join(words)
			a,h = map(str, game.split(" @ "))
			teamGame[a] = game
			teamGame[h] = game
			factors[game][prop] = col.text

	for rows in soup.select("#table_id tbody tr"):
		tds = rows.select("td")
		team = tds[0].text.lower()
		game = teamGame.get(team, "")
		player = parsePlayer(tds[1].text)
		factor = tds[3].text
		factorColor = tds[3].get("style").split("; ")[1].split(": ")[-1]

		#factors[game]["players"][player] = (factor, factorColor)
		factors[game]["players"][player] = f"{factor}-{factorColor}"

	with open("static/bpp/factors.json", "w") as fh:
		json.dump(factors, fh, indent=4)

if __name__ == '__main__':
	parser = argparse.ArgumentParser()

	args = parser.parse_args()

	writeParkFactors()