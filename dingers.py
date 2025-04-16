import argparse
import json
import math
import os
import random
import requests
import queue
import re
import time
import nodriver as uc
import subprocess
import threading
import multiprocessing
from pdf2image import convert_from_path
import pytesseract
from PIL import Image

from bs4 import BeautifulSoup as BS
from shared import *
from datetime import datetime, timedelta

q = queue.Queue()
locks = {}
for book in ["fd", "dk", "cz", "espn", "mgm", "kambi", "b365"]:
	locks[book] = threading.Lock()
#lock = threading.Lock()

def devig(evData, player="", ou="575/-900", finalOdds=630, prop="hr", dinger=False, book=""):
	impliedOver = impliedUnder = 0
	over = int(ou.split("/")[0])
	if over > 0:
		impliedOver = 100 / (over+100)
	else:
		impliedOver = -1*over / (-1*over+100)

	bet = 100
	profit = finalOdds / 100 * bet
	if finalOdds < 0:
		profit = 100 * bet / (finalOdds * -1)

	if "/" not in ou:
		u = 1.07 - impliedOver
		if u >= 1:
			#print(player, ou, finalOdds, impliedOver)
			return
		if over > 0:
			under = int((100*u) / (-1+u))
		else:
			under = int((100 - 100*u) / u)
	else:
		under = int(ou.split("/")[1])

	if under > 0:
		impliedUnder = 100 / (under+100)
	else:
		impliedUnder = -1*under / (-1*under+100)

	x = impliedOver
	y = impliedUnder
	while round(x+y, 8) != 1.0:
		k = math.log(2) / math.log(2 / (x+y))
		x = x**k
		y = y**k

	dec = 1 / x
	if dec >= 2:
		fairVal = round((dec - 1)  * 100)
	else:
		fairVal = round(-100 / (dec - 1))
	#fairVal = round((1 / x - 1)  * 100)
	implied = round(x*100, 2)
	#ev = round(x * (finalOdds - fairVal), 1)

	#multiplicative 
	mult = impliedOver / (impliedOver + impliedUnder)
	add = impliedOver - (impliedOver+impliedUnder-1) / 2

	evs = []
	for method in [x, mult, add]:
		ev = method * profit + (1-method) * -1 * bet
		ev = round(ev, 1)
		evs.append(ev)

	ev = min(evs)

	if dinger:
		# 70% conversion * 40% (2.1 HR/game = 2.1*$5/$25)
		fairVal = min(x, mult, add)
		x = 0.2856
		# 80% conversion * 42% (2.1 HR/game = 2.1*$5/$25)
		x = .336

		# for DK, 70% * (32 HR/tue = $32 / $20)
		#x = 1.12
		# for DK No Sweat, 70% * $10/ $20 bet
		x = 0.7
		ev = ((100 * (finalOdds / 100 + 1)) * fairVal - 100 + (100 * x))
		ev = round(ev, 1)

	evData.setdefault(player, {})
	if book:
		evData[player][f"{book}_ev"] = ev
		evData[player][f"{book}_fairVal"] = fairVal
		evData[player][f"{book}_implied"] = implied
	else:
		evData[player][f"fairVal"] = fairVal
		evData[player][f"implied"] = implied
		evData[player][f"ev"] = ev

def writeCircaMain(date):
	if not date:
		date = str(datetime.now())[:10]
	with open("static/mlb/schedule.json") as fh:
		schedule = json.load(fh)

	games = [x["game"] for x in schedule[date]]
	teamGame = {}
	for game in games:
		a,h = map(str, game.split(" @ "))
		teamGame[a] = game
		teamGame[h] = game

	dt = datetime.now().strftime("%Y-%-m-%-d")
	file = f"/mnt/c/Users/zhech/Downloads/MLB - {dt}.pdf"
	if not os.path.exists("/mnt/c/Users"):
		file = f"/Users/zackhecht/Downloads/MLB - {dt}.pdf"
	pages = convert_from_path(file)
	data = nested_dict()

	#pages = [pages[0]]

	for pageIdx, page in enumerate(pages):
		page.save("out.png", "PNG")
		img = Image.open("out.png")
		bottom, top = 1930, 480
		if pageIdx == 1:
			top = 500
		#w,h = img.size
		# l,t,r,b

		if pageIdx == 1:
			teams_img = img.crop((270,top,500,bottom))
			text = pytesseract.image_to_string(teams_img).split("\n")
			text = [x for x in text if x]

			rfi_img = img.crop((1480,top,1580,bottom))
			rfi_text = pytesseract.image_to_string(rfi_img).split("\n")
			rfi_text = [x.replace("EVEN", "+100") for x in rfi_text if x]

			for i in range(0, len(text), 2):
				try:
					game = f"{convertMGMTeam(text[i])} @ {convertMGMTeam(text[i+1])}"
				except:
					break
				data[game]["rfi"] = f"{rfi_text[i]}/{rfi_text[i+1]}"
			continue

		playersImg = img.crop((320,top,530,bottom))
		text = pytesseract.image_to_string(playersImg).split("\n")
		text = [x for x in text]
		playersImg.save("out-player.png", "PNG")
		print(text)

		mlImg = img.crop((715,top,820,bottom))
		ml_text = pytesseract.image_to_string(mlImg).split("\n")
		ml_text = [x for x in ml_text]
		mls = []
		for r in ml_text:
			if not r:
				mls.append("")
			mls.append(r)
		#mlImg.save("out-ml.png", "PNG")

		add = 0
		totals = []
		f5_totals = []
		for i in range(len(mls) // 2):
			total_img = img.crop((820,top+add+5,970,top+97+add-5))
			f5_total_img = img.crop((1310,top+add+5,1420,top+97+add-5))
			#total_img.save(f"out-total-{i}.png", "PNG")
			total_text = [x for x in pytesseract.image_to_string(total_img).split("\n") if x.replace("\x0c", "")]
			f5_total_text = [x for x in pytesseract.image_to_string(f5_total_img).split("\n") if x.replace("\x0c", "")]
			add += 97
			if not total_text or not total_text[0] or not total_text[1]:
				totals.extend([None, None])
			else:
				line_text = total_text[0] if " " in total_text[0] else total_text[1]
				line = str(float(line_text.split(" ")[0].replace("W,", "9.5").replace("Th", "7.5").replace("h", ".5").replace("%", ".5")))
				ou = total_text[0].split(" ")[-1]+"/"+total_text[1].split(" ")[-1]
				totals.append((line,ou.replace("EVEN", "+100")))
				totals.append((line,ou.replace("EVEN", "+100")))

			if not f5_total_text or not f5_total_text[0] or not f5_total_text[1]:
				f5_totals.extend([None, None])
			else:
				line_text = f5_total_text[0] if " " in f5_total_text[0] else f5_total_text[1]
				line = str(float(line_text.split(" ")[0].replace("W,", "9.5").replace("Th", "7.5").replace("h", ".5").replace("%", ".5")))
				ou = f5_total_text[0].split(" ")[-1]+"/"+f5_total_text[1].split(" ")[-1]
				f5_totals.append((line,ou.replace("EVEN", "+100")))
				f5_totals.append((line,ou.replace("EVEN", "+100")))

		spread_ou_img = img.crop((970,top,1130,bottom))
		spread_ou_text = pytesseract.image_to_string(spread_ou_img).split("\n")
		spread_ou_text = [x.replace("4 ", ".5 ").replace("%", ".5").replace("+", "") for x in spread_ou_text]
		spreads = []
		for r in spread_ou_text:
			if not r:
				spreads.append("")
			spreads.append(r)

		f5_ml_img = img.crop((1215,top,1310,bottom))
		f5_ml_text = pytesseract.image_to_string(f5_ml_img).split("\n")
		f5_ml_text = [x.replace("EVEN", "+100") for x in f5_ml_text]
		f5_ml = []
		for r in f5_ml_text:
			if not r:
				f5_ml.append("")
			f5_ml.append(r)

		#f5_sp_img = img.crop((1470,top,1550,bottom))
		f5_sp_img = img.crop((1450,top,1580,bottom))
		f5_sp_text = pytesseract.image_to_string(f5_sp_img).split("\n")
		f5_sp_text = [x.replace("EVEN", "+100").replace("“", "-") for x in f5_sp_text]
		f5_sp = []
		for r in f5_sp_text:
			if not r:
				f5_sp.append("")
			f5_sp.append(r)
		f5_sp_img.save("out-f5sp.png", "PNG")

		games = []
		for i in range(0, len(text), 2):
			try:
				game = f"{convertMGMTeam(text[i])} @ {convertMGMTeam(text[i+1])}"
			except:
				break
			if mls[i]:
				ou = mls[i]+"/"+mls[i+1]
				data[game]["ml"] = ou.replace("EVEN", "+100")

			if totals[i]:
				data[game]["total"][totals[i][0]] = totals[i][1]

			if f5_totals[i]:
				data[game]["f5_total"][f5_totals[i][0]] = f5_totals[i][1]

			if spreads[i]:
				line = spreads[i].split(" ")[0]
				ou = spreads[i].split(" ")[-1]+"/"+spreads[i+1].split(" ")[-1]
				data[game]["spread"][line] = ou.replace("EVEN", "+100")
			if f5_ml[i]:
				data[game]["f5_ml"] = f"{f5_ml[i]}/{f5_ml[i+1]}".replace("EVEN", "+100")

			if f5_sp[i]:
				line = "0.5" if f5_sp[i].startswith("+") else "-0.5"
				ou = f"""{f5_sp[i].split(" ")[-1]}/{f5_sp[i+1].split(" ")[-1]}"""
				data[game]["f5_spread"][line] = ou.replace("4-", "-").replace("EVEN", "+100")

	with open("static/mlb/circa-main.json", "w") as fh:
		json.dump(data, fh, indent=4)

def writeCirca(date):
	if not date:
		date = str(datetime.now())[:10]
	with open("static/mlb/schedule.json") as fh:
		schedule = json.load(fh)
	with open("static/baseballreference/roster.json") as fh:
		roster = json.load(fh)
	playerRoster = {}
	for team in roster:
		for player in roster[team]:
			playerRoster[player] = team

	writeHistorical(date, book="circa")

	games = [x["game"] for x in schedule[date]]
	teamGame = {}
	for game in games:
		a,h = map(str, game.split(" @ "))
		teamGame[a] = game
		teamGame[h] = game

	dt = datetime.now().strftime("%Y-%-m-%-d")
	file = f"/mnt/c/Users/zhech/Downloads/MLB Props - {dt}.pdf"
	if os.path.exists(f"/Users/zackhecht"):
		file = f"/Users/zackhecht/Downloads/MLB Props - {dt}.pdf"
	pages = convert_from_path(file)
	data = nested_dict()

	#pages = [pages[0]]

	for pageIdx, page in enumerate(pages):
		page.save("out.png", "PNG")
		img = Image.open("out.png")
		bottom = 2200
		top = 400
		#w,h = img.size
		# l,t,r,b
		playersImg = img.crop((0,top,400,bottom))
		text = pytesseract.image_to_string(playersImg).split("\n")

		players = []
		for player in text:
			if "(" not in player:
				continue
			team = convertMLBTeam(player.split(")")[0].split("(")[-1])
			player = parsePlayer(player.lower().split(" (")[0])
			#print(player, team)
			game = teamGame.get(team, "")
			players.append((player, game))

		# strikeouts
		#i = img.crop((770,1230,1035,1320))
		#print(pytesseract.image_to_string(i).split("\n"))

		oversImg = img.crop((540,top,600,bottom))
		undersImg = img.crop((670,top,760,bottom))
		oversArr = pytesseract.image_to_string(oversImg).split("\n")
		undersArr = pytesseract.image_to_string(undersImg).split("\n")
		overs = []
		for over in oversArr:
			o = re.search(r"\d{3,4}", over)
			if not o:
				continue
			overs.append(over)
		unders = []
		for under in undersArr:
			o = re.search(r"\d{3,4}", under)
			if not o:
				continue
			elif "-" not in under:
				under = "-"+under
			unders.append(under)
		
		for p,o,u in zip(players, overs, unders):
			data[p[-1]]["hr"][p[0]] = f"{o}/{u}"


		if False and pageIdx == 0:

			boxW,boxH = 264,76
			l,r = 770,1034
			for c in range(3):
				l = 770
				t = 375
				if c == 1:
					l,r = 1050,1310
				elif c == 2:
					l,r = 1330,1590

				for row in range(7):
					boxH = 76 if row == 0 else 70
					box = img.crop((l,t,r,t+boxH))
					box.save(f"out-{row}.png", "PNG")
					w,h = box.size

					i = box.crop((0,0,w,25))
					team = pytesseract.image_to_string(i).split("\n")
					team = convertMGMTeam(team[0])
					game = teamGame.get(team, "")

					i = box.crop((70,25,207,h))
					#i.save(f"out-{row}.png", "PNG")
					line = pytesseract.image_to_string(i).split("\n")
					line = [x for x in line if x.replace("\x0c", "")]
					print(team, line)
					if not line:
						t += h+3
						continue
					line = line[-1].replace("%", ".5").replace("h", ".5")

					i = box.crop((207,30,w,h))
					odds = pytesseract.image_to_string(i).split("\n")

					if len(odds) < 2:
						t += h+3
						continue
					o,u = odds[0],odds[1]
					if len(o) == 4 and o[0] in ["4", "7"]:
						o = "-"+o[1:]
					if len(u) == 4 and u[0] in ["4", "7"]:
						u = "-"+u[1:]

					p = "away_total" if game.startswith(team) else "home_total"
					data[game][p][line] = f"{o}/{u}".replace("EVEN", "+100").replace("~", "-").replace(",", "")

					t += h+3
			continue
			# strikeouts
			l,r,t = 770,1032,1313
			boxW = r-l
			boxT = t
			boxL = l
			for c in range(3):
				boxT = t
				if c == 1:
					boxL = 1050
				elif c == 2:
					boxL = 1328

				for i in range(10):
					#print(boxL, boxT, boxL+boxW, boxT+boxH)
					box = img.crop((boxL,boxT,boxL+boxW,boxT+boxH))
					box.save(f"out-{i}.png", "PNG")
					w,h = box.size
					x = box.crop((w-110,40,w-60,h))
					ou = box.crop((w-60,40,w,h))
					

					player_img = box.crop((0,0,w,40)) # l,t,r,b
					player = pytesseract.image_to_string(player_img).split("\n")[0]
					line = pytesseract.image_to_string(x).split("\n")
					line = str(float(line[0][0].replace("T", "7")) + 0.5)
					team = convertMLBTeam(player.split(")")[0].split("(")[-1])
					if team == "art":
						team = "ari"
					elif team == "nyn":
						team = "nym"
					elif team == "nil":
						team = "mil"
					game = teamGame.get(team, "")
					player = parsePlayer(player.lower().split(" (")[0])
					ous = pytesseract.image_to_string(ou).split("\n")

					#print(player, ous)
					o = ous[0].replace("EVEN", "+100")
					u = ous[1].replace("EVEN", "+100")

					if len(o) == 4 and o[0] in ["4", "7"]:
						o = "-"+o[1:]

					if o.startswith("+") and not u.startswith("-") and not u.startswith("+"):
						u = f"-{u}"

					data[game]["k"][player][line] = f"{o}/{u}".replace("\u201c", "-").replace(",", "")
					boxT += h+2

	with open("static/mlb/circa-props.json", "w") as fh:
		json.dump(data, fh, indent=4)

def mergeCirca():
	with open("static/mlb/circa-props.json") as fh:
		circa = json.load(fh)
	with open("static/mlb/circa-main.json") as fh:
		circaMain = json.load(fh)

	for game in circa:
		for prop in circa[game]:
			for player in circa[game][prop]:
				circaMain.setdefault(game, {})
				circaMain[game].setdefault(prop, {})
				circaMain[game][prop][player] = circa[game][prop][player]

	with open("static/mlb/circa-props") as fh:
		lines = fh.read().split("\n")
	if lines[0] == date:
		for row in lines[1:]:
			cols = row.split(",")
			game, prop, player = cols[0], cols[1], cols[2]
			circaMain[game].setdefault(prop, {})
			if prop == "hr":
				circaMain[game][prop][player] = cols[-1]
			else:
				circaMain[game][prop].setdefault(player, {})
				circaMain[game][prop][player][cols[3]] = cols[-1]

	with open("static/mlb/circa.json", "w") as fh:
		json.dump(circaMain, fh, indent=4)
		

async def getESPNLinks(date):
	try:
		browser = await uc.start(no_sandbox=True)
	except:
		return
	url = "https://espnbet.com/sport/baseball/organization/united-states/competition/mlb"
	page = await browser.get(url)
	await page.wait_for(selector="article")
	html = await page.get_content()

	games = {}
	soup = BS(html, "html.parser")
	for article in soup.select("article"):
		if not article.find("h3") or " @ " not in article.find("h3").text:
			continue
		if date == str(datetime.now())[:10] and "Today" not in article.text:
			continue
		elif date != str(datetime.now())[:10] and datetime.strftime(datetime.strptime(date, "%Y-%m-%d"), "%b %d") not in article.text:
			continue

		away, home = map(str, article.find("h3").text.split(" @ "))
		eventId = article.find("div").find("div").get("id").split("|")[1]
		away, home = convertMLBTeam(away), convertMLBTeam(home)
		game = f"{away} @ {home}"
		games[game] = f"{url}/event/{eventId}/section/player_props"

	browser.stop()
	return games

def runESPN(rosters):
	uc.loop().run_until_complete(writeESPN(rosters))

async def writeESPN(rosters):
	book = "espn"
	try:
		browser = await uc.start(no_sandbox=True)
	except:
		return
	while True:
		data = nested_dict()
		(game, url) = q.get()
		if url is None:
			q.task_done()
			break

		playerMap = {}
		away, home = map(str, game.split(" @ "))
		for team in [away, home]:
			for player in rosters.get(team, {}):
				last = player.split(" ")
				p = player[0][0]+". "+last[-1]
				playerMap[p] = player

		page = await browser.get(url)
		try:
			await page.wait_for(selector="div[data-testid='away-team-card']")
		except:
			q.task_done()
			continue
		html = await page.get_content()
		soup = BS(html, "html.parser")

		for detail in soup.find_all("details"):
			if not detail.text.startswith("Player Total Home Runs Hit"):
				continue
			for article in detail.find_all("article"):
				if not article.find("header"):
					continue
				player = parsePlayer(article.find("header").text)
				last = player.split(" ")
				p = player[0][0]+". "+last[-1]
				player = playerMap.get(p, player)

				over = article.find("button").find_all("span")[-1].text
				under = article.find_all("button")[-1].find_all("span")[-1].text
				if "0.5" in over or "0.5" in under:
					continue
				data[game][player][book] = over+"/"+under

		try:
			updateData(book, data)
		except:
			print("espn fail", data)
		q.task_done()
	browser.stop()

async def write365(loop):
	book = "365"

	writeHistorical(str(datetime.now())[:10], book)

	try:
		browser = await uc.start(no_sandbox=True)
	except:
		return
	url = "https://www.oh.bet365.com/?_h=uvJ7Snn5ImZN352O9l7rPQ%3D%3D&btsffd=1#/AC/B16/C20525425/D43/E160301/F43/N2/"
	page = await browser.get(url)

	try:
		await page.wait_for(selector=".srb-MarketSelectionButton-selected")	
	except:
		return
	reject = await page.query_selector(".ccm-CookieConsentPopup_Reject")
	if reject:
		await reject.mouse_click()

	if True:
		for c in ["src-FixtureSubGroup_Closed"]:
			divs = await page.query_selector_all("."+c)

			for div in divs:
				await div.scroll_into_view()
				await div.mouse_click()
				#time.sleep(round(random.uniform(0.9, 1.25), 2))
				time.sleep(round(random.uniform(0.4, 0.9), 2))

	while True:
		players = await page.query_selector_all(".gl-Participant_General")
		data = nested_dict()
		for player in players:
			game = player.parent.parent.parent.parent.children[0].children[0].children[0].text
			game = convertMLBTeam(game.split(" @ ")[0])+" @ "+convertMLBTeam(game.split(" @ ")[-1])

			attrs = player.attributes
			labelIdx = attrs.index("aria-label")
			label = attrs[labelIdx+1].lower().strip()

			player = parsePlayer(label.split("  0.5")[0].replace("over ", "").replace("under ", ""))
			odds = label.split(" ")[-1]
			
			data.setdefault(game, {})
			data[game].setdefault(player, {})

			if label.startswith("over"):
				data[game][player][book] = odds
			else:
				data[game][player][book] += "/"+odds

		with open("static/dingers/updated_b365", "w") as fh:
			fh.write(str(datetime.now()))
		with open("static/dingers/b365.json", "w") as fh:
			json.dump(data, fh, indent=4)

		if not loop:
			break

	browser.stop()
	
async def writeDK(date, loop, night):
	book = "dk"
	try:
		browser = await uc.start(no_sandbox=True)
	except:
		return
	url = "https://sportsbook.draftkings.com/leagues/baseball/mlb?category=batter-props&subcategory=home-runs"
	page = await browser.get(url)
	#time.sleep(5)
	try:
		await page.wait_for(selector=".sportsbook-event-accordion__wrapper")
	except:
		print("element not found")
		return

	while True:
		data = nested_dict()
		gameDivs = await page.query_selector_all(".sportsbook-event-accordion__wrapper")
		for gameDiv in gameDivs:
			game = gameDiv.children[0].children[1].text_all
			if " @ " not in game and " at " not in game:
				continue
			away, home = map(str, game.replace(" at ", " @ ").split(" @ "))
			game = f"{convertMLBTeam(away)} @ {convertMLBTeam(home)}"

			odds = await gameDiv.query_selector_all("button[data-testid='sb-selection-picker__selection-0']")
			for oIdx, odd in enumerate(odds):
				player = parsePlayer(odd.parent.parent.parent.parent.parent.children[0].text.split(" (")[0])
				ou = odd.text_all.split(" ")[-1]
				if ou.endswith("+"):
					continue
				data[game][player][book] = ou


		with open("static/dingers/updated_dk", "w") as fh:
			fh.write(str(datetime.now()))
		with open("static/dingers/dk.json", "w") as fh:
			json.dump(data, fh, indent=4)

		writeHistorical(date, book)

		if not loop:
			break

		if night:
			time.sleep(60 * 10)
		else:
			time.sleep(10)

	browser.stop()

async def getMGMLinks(date):
	try:
		browser = await uc.start(no_sandbox=True)
	except:
		return
	url = "https://sports.mi.betmgm.com/en/sports/baseball-23/betting/usa-9/mlb-75"
	page = await browser.get(url)
	await page.wait_for(selector="ms-prematch-timer")
	html = await page.get_content()

	games = {}
	soup = BS(html, "html.parser")
	for t in soup.select("ms-prematch-timer"):
		if "Today" in t.text or "Starting" in t.text:
			d = str(datetime.now())[:10]
		elif "Tomorrow" in t.text:
			d = str(datetime.now() + timedelta(days=1))[:10]
		else:
			m,d,y = map(int, t.text.split(" ")[0].split("/"))
			d = f"20{y}-{m:02}-{d:02}"

		if d != date:
			continue

		parent = t.find_previous("ms-six-pack-event")
		if not parent:
			continue
		a = parent.find("a")
		teams = parent.select(".participant")
		away, home = convertMGMMLBTeam(teams[0].text.strip()), convertMGMMLBTeam(teams[1].text.strip())
		game = f"{away} @ {home}"
		games[game] = "https://sports.betmgm.com"+a.get("href")

	browser.stop()
	return games

def runMGM():
	uc.loop().run_until_complete(writeMGM())

async def writeMGM():
	book = "mgm"
	try:
		browser = await uc.start(no_sandbox=True)
	except:
		return
	while True:
		data = nested_dict()

		(game, url) = q.get()
		if url is None:
			q.task_done()
			break

		page = await browser.get(url)
		try:
			await page.wait_for(selector=".event-details-pills-list")
		except:
			q.task_done()
			continue

		#show = await page.query_selector(".option-group-column:nth-of-type(2) .option-panel .show-more-less-button")
		#if show:
		#	await show.click()
		
		foundPanel = None
		panels = await page.query_selector_all(".option-panel")
		for panel in panels:
			if "Batter home runs" in panel.text_all:
				up = await panel.query_selector("svg[title=theme-up]")
				if not up:
					up = await panel.query_selector(".clickable")
					await up.click()

				show = await panel.query_selector(".show-more-less-button")
				if show and show.text_all == "Show More":
					await show.click()
					await show.scroll_into_view()
					time.sleep(0.75)
				foundPanel = panel
				break

		if not foundPanel:
			q.task_done()
			continue
		else:
			html = await page.get_content()
			soup = BS(html, "html.parser")

		panel = None
		players = []
		odds = []
		for p in soup.select(".option-panel"):
			if "Batter home runs" in p.text:
				players = p.select(".attribute-key")
				odds = p.select("ms-option")
				break

		#players = panel.select(".attribute-key")
		#odds = panel.select("ms-option")

		for i, player in enumerate(players):
			player = parsePlayer(player.text.strip().split(" (")[0])
			over = odds[i*2].select(".value")
			under = odds[i*2+1].select(".value")
			if not over:
				continue
			ou = over[0].text
			if under:
				ou += "/"+under[0].text

			data[game][player][book] = ou

		try:
			updateData(book, data)
		except:
			print(data)
			pass
		q.task_done()

	browser.stop()

def updateData(book, data):
	file = f"static/dingers/{book}.json"
	with locks[book]:
		d = {}
		if os.path.exists(file):
			with open(file) as fh:
				d = json.load(fh)
		d.update(data)
		with open(file, "w") as fh:
			json.dump(d, fh, indent=4)

async def writeBR(date):
	url = "https://mi.betrivers.com/?page=sportsbook&group=1000093616&type=playerprops"
	try:
		browser = await uc.start(no_sandbox=True)
	except:
		return
	page = await browser.get(url)

	res = {}
	await page.wait_for(selector="article")
	articles = await page.query_selector_all("article")

	for article in articles:
		if "live" in article.text_all.lower():
			continue
		await article.scroll_into_view()
		if "Show more" in article.text_all:
			spans = await article.query_selector_all("span")
			for span in spans:
				if span.text == "Show more":
					await span.scroll_into_view()
					await span.parent.mouse_click()
					time.sleep(0.2)
					break

	time.sleep(10)
	html = await page.get_content()
	soup = BS(html, "lxml")

	with open("out.html", "w") as fh:
		fh.write(html)
		
	browser.stop()
	return res

def writeHistory():
	with open("static/baseballreference/roster.json") as fh:
		roster = json.load(fh)

	with open("static/dingers/odds_historical.json") as fh:
		oddsHist = json.load(fh)

	bookData = nested_dict()
	for date, games in oddsHist.items():
		for game in games:
			a,h = map(str, game.split(" @ "))
			for player, books in oddsHist[date][game].items():
				team = ""
				if player in roster[a]:
					team = a
				elif player in roster[h]:
					team = h

				for book, odds in books.items():
					bookData[player][book][date] = odds

	for book in ["b365", "circa", "cz", "dk", "espn", "fd", "mgm", "pn"]:
		with open(f"static/dingers/{book}_historical.json") as fh:
			hist = json.load(fh)

		for date, games in hist.items():
			for game in games:
				a,h = map(str, game.split(" @ "))
				for player in hist[date][game]:
					bookData[player][book][date] = hist[date][game][player]["close"]

	with open("static/dingers/history.json", "w") as fh:
		json.dump(bookData, fh, indent=4)


async def getFDLinks(date):
	try:
		browser = await uc.start(no_sandbox=True)
	except:
		return
	url = "https://mi.sportsbook.fanduel.com/navigation/mlb"
	page = await browser.get(url)
	await page.wait_for(selector="span[role=link]")

	html = await page.get_content()
	soup = BS(html, "lxml")
	links = soup.select("span[role=link]")

	for link in links:
		if link.text == "More wagers":
			t = link.find_previous("a").parent.find("time")
			url = link.find_previous("a").get("href")
			game = " ".join(url.split("/")[-1].split("-")[:-1])
			away, home = map(str, game.split(" @ "))
			game = f"{convertMLBTeam(away)} @ {convertMLBTeam(home)}"
			games[game] = f"https://mi.sportsbook.fanduel.com{url}?tab=batter-props"

	browser.stop()
	return games

def runFD():
	uc.loop().run_until_complete(writeFD())

async def writeFDFromBuilder(date, loop, night):
	book = "fd"

	with open(f"static/mlb/schedule.json") as fh:
		schedule = json.load(fh)

	if date not in schedule:
		print("Date not in schedule")
		return

	games = [x["game"] for x in schedule[date]]
	teamMap = {}
	for game in games:
		for t in game.split(" @ "):
			teamMap[t] = game

	url = "https://sportsbook.fanduel.com/navigation/mlb?tab=parlay-builder"
	try:
		browser = await uc.start(no_sandbox=True)
	except:
		return
	page = await browser.get(url)
	time.sleep(0.5)
	try:
		await page.wait_for(selector="div[role=button][aria-selected=true]")
	except:
		print("tab not found")
		return
	tab = await page.query_selector("div[role=button][aria-selected=true]")
	if tab.text == "Parlay Builder":
		arrow = await page.query_selector("div[data-testid=ArrowAction]")
		await arrow.click()
		await page.wait_for(selector="div[aria-label='Show more']")
		mores = await page.query_selector_all("div[aria-label='Show more']")
		for more in mores:
			await more.click()
		time.sleep(1)
	else:
		print("parlay builder not found")
		return

	while True:
		html = await page.get_content()

		gameStarted = {}
		for gameData in schedule[date]:
			dt = datetime.strptime(gameData["start"], "%I:%M %p")
			dt = int(dt.strftime("%H%M"))
			gameStarted[gameData["game"]] = int(datetime.now().strftime("%H%M")) > dt

		writeHistorical(date, book, gameStarted)
		writeFDFromBuilderHTML(html, teamMap, date, gameStarted)
		if not loop:
			break
		
		if night:
			time.sleep(60 * 10)
		else:
			time.sleep(10)

	browser.stop()

def writeFDFromBuilderHTML(html, teamMap, date, gameStarted):
	soup = BS(html, "html.parser")
	btns = soup.select("div[role=button]")

	data = nested_dict()
	dingerData = nested_dict()
	currGame = ""
	for btn in btns:
		label = btn.get("aria-label")
		if not label:
			continue
		if not label.startswith("To Hit A Home Run"):
			continue
		player = parsePlayer(label.split(", ")[1])
		odds = label.split(" ")[-1]
		try:
			team = btn.parent.parent.parent.find_all("img")[1]

			if "/team/" not in team.get("src"):
				continue
			team = convertMLBTeam(team.get("src").split("/")[-1].replace(".png", "").replace("_", " "))
			game = teamMap.get(team, currGame)
		except:
			game = currGame

		if "unavailable" in odds:
			continue

		currGame = game
		if date == str(datetime.now())[:10] and gameStarted[game]:
			continue
		dingerData[game][player]["fd"] = odds
		data[game]["hr"][player] = odds

	with open("static/dingers/updated_fd", "w") as fh:
		fh.write(str(datetime.now()))
	with open("static/dingers/fd.json", "w") as fh:
		json.dump(dingerData, fh, indent=4)

async def writeFD():
	book = "fd"
	try:
		browser = await uc.start(no_sandbox=True)
	except:
		return

	while True:
		data = nested_dict()

		(game, url) = q.get()
		if url is None:
			q.task_done()
			break

		page = await browser.get(url)
		await page.wait_for(selector="div[role=button][aria-selected=true]")

		tab = await page.query_selector("div[role=button][aria-selected=true]")
		if tab.text != "Batter Props":
			q.task_done()
			continue

		el = await page.query_selector("div[aria-label='Show more']")
		if el:
			await el.click()

		btns = await page.query_selector_all("div[role=button]")
		for btn in btns:
			try:
				labelIdx = btn.attributes.index("aria-label")
			except:
				continue
			labelSplit = btn.attributes[labelIdx+1].lower().split(", ")
			if "selection unavailable" in labelSplit[-1] or labelSplit[0].startswith("tab ") or len(labelSplit) <= 1:
				continue

			player = parsePlayer(labelSplit[1])

			data[game][player][book] = labelSplit[-1]

		updateData(book, data)
		q.task_done()

	browser.stop()

async def writeCZ(date, token=None):
	book = "cz"
	outfile = "outDingersCZ"
	if False and not token:
		await writeCZToken()

	with open("token") as fh:
		token = fh.read()

	writeHistorical(date, book)

	url = "https://api.americanwagering.com/regions/us/locations/mi/brands/czr/sb/v3/sports/baseball/events/schedule?competitionIds=04f90892-3afa-4e84-acce-5b89f151063d"
	os.system(f"curl -s '{url}' --compressed -H 'User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:122.0) Gecko/20100101 Firefox/122.0' -H 'Accept: */*' -H 'Accept-Language: en-US,en;q=0.5' -H 'Accept-Encoding: gzip, deflate, br' -H 'Referer: https://sportsbook.caesars.com/' -H 'content-type: application/json' -H 'X-Unique-Device-Id: 8478f41a-e3db-46b4-ab46-1ac1a65ba18b' -H 'X-Platform: cordova-desktop' -H 'X-App-Version: 7.13.2' -H 'x-aws-waf-token: {token}' -H 'Origin: https://sportsbook.caesars.com' -H 'Connection: keep-alive' -H 'Sec-Fetch-Dest: empty' -H 'Sec-Fetch-Mode: cors' -H 'Sec-Fetch-Site: cross-site' -H 'TE: trailers' -o {outfile}")
	try:
		with open(outfile) as fh:
			data = json.load(fh)
	except:
		await writeCZToken()
		with open("token") as fh:
			token = fh.read()
		os.system(f"curl -s '{url}' --compressed -H 'User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:122.0) Gecko/20100101 Firefox/122.0' -H 'Accept: */*' -H 'Accept-Language: en-US,en;q=0.5' -H 'Accept-Encoding: gzip, deflate, br' -H 'Referer: https://sportsbook.caesars.com/' -H 'content-type: application/json' -H 'X-Unique-Device-Id: 8478f41a-e3db-46b4-ab46-1ac1a65ba18b' -H 'X-Platform: cordova-desktop' -H 'X-App-Version: 7.13.2' -H 'x-aws-waf-token: {token}' -H 'Origin: https://sportsbook.caesars.com' -H 'Connection: keep-alive' -H 'Sec-Fetch-Dest: empty' -H 'Sec-Fetch-Mode: cors' -H 'Sec-Fetch-Site: cross-site' -H 'TE: trailers' -o {outfile}")

	with open(outfile) as fh:
		data = json.load(fh)

	games = []
	for event in data["competitions"][0]["events"]:
		if str(datetime.strptime(event["startTime"], "%Y-%m-%dT%H:%M:%SZ") - timedelta(hours=4))[:10] != date:
			continue
			pass
		games.append(event["id"])

	res = nested_dict()
	for gameId in games:
		url = f"https://api.americanwagering.com/regions/us/locations/mi/brands/czr/sb/v3/events/{gameId}"
		os.system(f"curl -s '{url}' --compressed -H 'User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:122.0) Gecko/20100101 Firefox/122.0' -H 'Accept: */*' -H 'Accept-Language: en-US,en;q=0.5' -H 'Accept-Encoding: gzip, deflate, br' -H 'Referer: https://sportsbook.caesars.com/' -H 'content-type: application/json' -H 'X-Unique-Device-Id: 8478f41a-e3db-46b4-ab46-1ac1a65ba18b' -H 'X-Platform: cordova-desktop' -H 'X-App-Version: 7.13.2' -H 'x-aws-waf-token: {token}' -H 'Origin: https://sportsbook.caesars.com' -H 'Connection: keep-alive' -H 'Sec-Fetch-Dest: empty' -H 'Sec-Fetch-Mode: cors' -H 'Sec-Fetch-Site: cross-site' -H 'TE: trailers' -o {outfile}")

		with open(outfile) as fh:
			data = json.load(fh)

		game = data["name"].lower().replace("|", "").replace(" at ", " @ ")
		if "@" not in game:
			continue
		away, home = map(str, game.split(" @ "))
		game = f"{convertMLBTeam(away)} @ {convertMLBTeam(home)}"
		
		for market in data["markets"]:
			if "name" not in market or market["active"] == False:
				continue
			prop = market["name"].lower().replace("|", "").split(" (")[0]
			if prop != "player to hit a home run":
				continue

			for selection in market["selections"]:
				try:
					ou = str(selection["price"]["a"])
				except:
					continue
				player = parsePlayer(selection["name"].replace("|", ""))
				res[game][player][book] = ou

	with open("static/dingers/updated_cz", "w") as fh:
		fh.write(str(datetime.now()))
	updateData(book, res)

def parsePinnacle(res, games, gameId, retry, debug):
	outfile = "mlboutPN"
	game = games[gameId]

	url = 'curl -s "https://guest.api.arcadia.pinnacle.com/0.1/matchups/'+str(gameId)+'/related" --compressed -H "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/116.0" -H "Accept: application/json" -H "Accept-Language: en-US,en;q=0.5" -H "Referer: https://www.pinnacle.com/" -H "Content-Type: application/json" -H "X-API-Key: CmX2KcMrXuFmNg6YFbmTxE0y9CIrOi0R" -H "X-Device-UUID: 66ac2815-a68dc902-a5052c0c-c60f3d05" -H "Origin: https://www.pinnacle.com" -H "Connection: keep-alive" -H "Sec-Fetch-Dest: empty" -H "Sec-Fetch-Mode: cors" -H "Sec-Fetch-Site: same-site" -H "Pragma: no-cache" -H "Cache-Control: no-cache" -H "TE: trailers" -o mlboutPN'

	time.sleep(0.3)
	os.system(url)
	try:
		with open(outfile) as fh:
			related = json.load(fh)
	except:
		retry.append(gameId)
		return

	relatedData = {}
	for row in related:
		if type(row) is str:
			continue
		if row.get("periods") and row["periods"][0]["status"] == "closed":
			continue
		if "special" in row:
			prop = row["units"].lower()

			if prop == "homeruns":
				prop = "hr"
			else:
				continue

			over = row["participants"][0]["id"]
			under = row["participants"][1]["id"]
			if row["participants"][0]["name"] == "Under":
				over, under = under, over
			player = parsePlayer(row["special"]["description"].split(" (")[0])
			relatedData[row["id"]] = {
				"player": player,
				"prop": prop,
				"over": over,
				"under": under
			}

	if debug:
		with open("t", "w") as fh:
			json.dump(relatedData, fh, indent=4)

		with open("t2", "w") as fh:
			json.dump(related, fh, indent=4)

	url = 'curl -s "https://guest.api.arcadia.pinnacle.com/0.1/matchups/'+str(gameId)+'/markets/related/straight" --compressed -H "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/116.0" -H "Accept: application/json" -H "Accept-Language: en-US,en;q=0.5" -H "Referer: https://www.pinnacle.com/" -H "Content-Type: application/json" -H "X-API-Key: CmX2KcMrXuFmNg6YFbmTxE0y9CIrOi0R" -H "X-Device-UUID: 66ac2815-a68dc902-a5052c0c-c60f3d05" -H "Origin: https://www.pinnacle.com" -H "Connection: keep-alive" -H "Sec-Fetch-Dest: empty" -H "Sec-Fetch-Mode: cors" -H "Sec-Fetch-Site: same-site" -H "Pragma: no-cache" -H "Cache-Control: no-cache" -H "TE: trailers" -o mlboutPN'

	time.sleep(0.3)
	os.system(url)
	try:
		with open(outfile) as fh:
			data = json.load(fh)
	except:
		retry.append(gameId)
		return

	if debug:
		with open("t3", "w") as fh:
			json.dump(data, fh, indent=4)

	res[game] = {}

	for row in data:
		if type(row) is str:
			continue
		prop = row["type"]
		keys = row["key"].split(";")

		prefix = ""

		overId = underId = 0
		player = ""
		if keys[1] == "1":
			prefix = "f5_"
		elif keys[1] == "3" and row["key"] != "s;3;ou;0.5":
			continue

		if row["matchupId"] != int(gameId):
			if row["matchupId"] not in relatedData:
				continue
			player = relatedData[row["matchupId"]]["player"]
			prop = relatedData[row["matchupId"]]["prop"]
			overId = relatedData[row["matchupId"]]["over"]
			underId = relatedData[row["matchupId"]]["under"]
		else:
			if prop == "moneyline":
				prop = f"{prefix}ml"
			elif prop == "spread":
				prop = f"{prefix}spread"
			elif prop == "total" and row["key"] == "s;3;ou;0.5":
				prop = "rfi"
			elif prop == "total":
				prop = f"{prefix}total"
			elif prop == "team_total":
				awayHome = row['side']
				prop = f"{prefix}{awayHome}_total"

		if debug:
			print(prop, row["matchupId"], keys)

		prices = row["prices"]
		switched = 0
		if overId:
			try:
				ou = f"{prices[0]['price']}/{prices[1]['price']}"
			except:
				continue
			if prices[0]["participantId"] == underId:
				ou = f"{prices[1]['price']}/{prices[0]['price']}"
				switched = 1

			if prop not in res[game]:
				res[game][prop] = {}
			if player not in res[game][prop]:
				res[game][prop][player] = {}

			if "points" in prices[0] and prop not in []:
				handicap = str(float(prices[switched]["points"]))
				res[game][prop][player][handicap] = ou
			else:
				res[game][prop][player] = ou
		else:
			ou = f"{prices[0]['price']}/{prices[1]['price']}"
			if prices[0]["designation"] in ["home", "under"]:
				ou = f"{prices[1]['price']}/{prices[0]['price']}"
				switched = 1

			if "points" in prices[0] and prop != "rfi":
				handicap = str(float(prices[switched]["points"]))
				if prop not in res[game]:
					res[game][prop] = {}

				res[game][prop][handicap] = ou
			else:
				res[game][prop] = ou

def writePinnacle(date, debug=False):

	if not date:
		date = str(datetime.now())[:10]

	url = "https://www.pinnacle.com/en/baseball/mlb/matchups#period:0"

	url = 'curl -s "https://guest.api.arcadia.pinnacle.com/0.1/leagues/246/matchups?brandId=0" --compressed -H "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/116.0" -H "Accept: application/json" -H "Accept-Language: en-US,en;q=0.5" -H "Referer: https://www.pinnacle.com/" -H "Content-Type: application/json" -H "X-API-Key: CmX2KcMrXuFmNg6YFbmTxE0y9CIrOi0R" -H "X-Device-UUID: 66ac2815-a68dc902-a5052c0c-c60f3d05" -H "Origin: https://www.pinnacle.com" -H "Connection: keep-alive" -H "Sec-Fetch-Dest: empty" -H "Sec-Fetch-Mode: cors" -H "Sec-Fetch-Site: same-site" -H "Pragma: no-cache" -H "Cache-Control: no-cache" -o mlboutPN'

	os.system(url)
	outfile = f"mlboutPN"
	with open(outfile) as fh:
		data = json.load(fh)

	writeHistorical(date, "pn")

	games = {}
	seenGames = {}
	for row in data:
		if type(row) is str:
			continue
		if str(datetime.strptime(row["startTime"], "%Y-%m-%dT%H:%M:%SZ") - timedelta(hours=4))[:10] != date:
			continue
			pass
		if row["type"] == "matchup" and not row["parent"]:
			player1 = row["participants"][0]["name"].lower()
			player2 = row["participants"][1]["name"].lower()
			game = f"{player2} @ {player1}".replace("g1 ", "").replace("g2 ", "")
			if "home runs" in game:
				continue

			a,h = map(str, game.split(" @ "))
			team = f"{convertMLBTeam(a)} @ {convertMLBTeam(h)}"
			#team = convertFDTeam(game)
			if team in seenGames:
				#continue
				pass
			seenGames[team] = True
			games[str(row["id"])] = team

	res = {}
	#games = {'1606945742': 'nym @ mia'}	
	retry = []
	for gameId in games:
		parsePinnacle(res, games, gameId, retry, debug)

	for gameId in retry:
		parsePinnacle(res, games, gameId, retry, debug)

	with open("static/dingers/updated_pn", "w") as fh:
		fh.write(str(datetime.now()))

	data = nested_dict()
	for game in res:
		if "hr" in res[game]:
			for player in res[game]["hr"]:
				data[game][player]["pn"] = res[game]["hr"][player]["0.5"]

	with open("static/dingers/pn.json", "w") as fh:
		json.dump(data, fh, indent=4)

def writeKambi(date):
	book = "kambi"
	outfile = "outDailyKambi"

	url = "https://eu-offering-api.kambicdn.com/offering/v2018/pivuslarl-lbr/listView/baseball/mlb/all/all/matches.json?lang=en_US&market=US"
	os.system(f"curl -s \"{url}\" -o {outfile}")
	
	with open(outfile) as fh:
		j = json.load(fh)

	data = nested_dict()
	writeHistorical(date, book)

	eventIds = {}
	for event in j["events"]:
		game = event["event"]["name"].lower()
		if " vs " in game:
			away, home = map(str, game.split(" vs "))
		else:
			away, home = map(str, game.split(" @ "))
		game = f"{convertMLBTeam(away)} @ {convertMLBTeam(home)}"
		if game in eventIds:
			continue
			#pass
		eventIds[game] = event["event"]["id"]

	for game in eventIds:
		eventId = eventIds[game]
		teamIds = {}
		
		time.sleep(0.3)
		url = f"https://eu-offering-api.kambicdn.com/offering/v2018/pivuslarl-lbr/betoffer/event/{eventId}.json"
		os.system(f"curl -s \"{url}\" -o {outfile}")

		with open(outfile) as fh:
			j = json.load(fh)

		for betOffer in j["betOffers"]:
			label = betOffer["criterion"]["label"].lower()
			#print(label)
			if not teamIds and "Handicap" in label:
				for row in betOffer["outcomes"]:
					team = convertMLBTeam(row["label"].lower())
					#teamIds[row["participantId"]] = team
					#data[team] = {}
			elif "to hit a home run" in label:
				player = strip_accents(betOffer["outcomes"][0]["participant"])
				try:
					last, first = map(str, player.lower().split(", "))
					player = f"{first} {last}"
				except:
					player = player.lower()
				player = parsePlayer(player)
				over = betOffer["outcomes"][0]["oddsAmerican"]
				under = betOffer["outcomes"][1]["oddsAmerican"]
				data[game][player][book] = f"{over}/{under}"

	updateData(book, data)

def parseESPN(espnLines):
	with open("baseballreference/roster.json") as fh:
		roster = json.load(fh)

	with open(f"mlb/espn.json") as fh:
		espn = json.load(fh)

	players = {}
	for team in roster:
		players[team] = {}
		for player in roster[team]:
			first = player.split(" ")[0][0]
			last = player.split(" ")[-1]
			players[team][f"{first} {last}"] = player

	for game in espn:
		espnLines[game] = {}
		for prop in espn[game]:
			if prop == "hr":
				espnLines[game][prop] = {}
				away, home = map(str, game.split(" @ "))
				for p in espn[game][prop]:
					if p not in players[away] and p not in players[home]:
						continue
					if p in players[away]:
						player = players[away][p]
					else:
						player = players[home][p]
					
					if type(espn[game][prop][p]) is str:
						espnLines[game][prop][player] = espn[game][prop][p]
					else:
						espnLines[game][prop][player] = espn[game][prop][p].copy()

def writeEV(date, dinger, silent=False):
	if not date:
		date = str(datetime.now())[:10]

	data = {}
	updated = {}
	for book in ["fd", "espn", "dk", "cz", "b365", "mgm", "pn"]:
		path = f"static/dingers/{book}.json"
		if os.path.exists(path):
			with open(path) as fh:
				d = json.load(fh)
			merge_dicts(data, d)

		upd = f"static/dingers/updated_{book}"
		if os.path.exists(upd):
			with open(upd) as fh:
				j = fh.read()
			updated[book] = j
		else:
			updated[book] = ""

	with open("static/mlb/circa.json") as fh:
		circaLines = json.load(fh)

	for game in circaLines:
		if "hr" not in circaLines[game]:
			continue
		for player in circaLines[game]["hr"]:
			data.setdefault(game, {})
			data[game].setdefault(player, {})
			data[game][player]["circa"] = circaLines[game]["hr"][player]

	with open("out", "w") as fh:
		json.dump(data, fh, indent=4)

	with open("updated.json", "w") as fh:
		json.dump(updated, fh, indent=4)

	with open(f"static/dingers/odds.json", "w") as fh:
		json.dump(data, fh, indent=4)

	with open(f"static/dingers/odds_historical.json") as fh:
		data_hist = json.load(fh)
	data_hist.setdefault(date, {})
	data_hist[date].update(data)
	with open(f"static/dingers/odds_historical.json", "w") as fh:
		json.dump(data_hist, fh, indent=4)

	with open(f"static/baseballreference/bvp.json") as fh:
		bvpData = json.load(fh)

	with open(f"static/baseballreference/ph.json") as fh:
		ph = json.load(fh)

	with open(f"static/baseballreference/roster.json") as fh:
		roster = json.load(fh)

	with open(f"static/baseballreference/leftOrRight.json") as fh:
		leftOrRight = json.load(fh)

	with open(f"static/mlb/schedule.json") as fh:
		schedule = json.load(fh)

	with open(f"static/mlb/weather.json") as fh:
		weather = json.load(fh)

	with open(f"static/mlb/lineups.json") as fh:
		lineups = json.load(fh)

	gameTimes = {}
	gameStarted = {}
	for gameData in schedule[date]:
		if gameData["start"] == "LIVE":
			gameStarted[gameData["game"]] = True
		else:
			dt = datetime.strptime(gameData["start"], "%I:%M %p")
			dt = int(dt.strftime("%H%M"))
			gameTimes[gameData["game"]] = dt
			gameStarted[gameData["game"]] = int(datetime.now().strftime("%H%M")) > dt

	evData = {}

	for game in data:
		if not game:
			continue
		away, home = map(str, game.split(" @ "))
		if game not in gameTimes:
			continue
		gameStart = gameTimes[game]
		gameWeather = weather.get(game, {})
		awayStats = {}
		homeStats = {}

		if date == str(datetime.now())[:10] and gameStarted[game]:
			continue
			pass

		if os.path.exists(f"splits/mlb/{away}.json"):
			with open(f"splits/mlb/{away}.json") as fh:
				awayStats = json.load(fh)
		if os.path.exists(f"splits/mlb/{home}.json"):
			with open(f"splits/mlb/{home}.json") as fh:
				homeStats = json.load(fh)

		for player in data[game]:
			opp = away
			team = home
			playerStats = {}
			if player in roster.get(away, {}):
				opp = home
				team = away
				playerStats = awayStats.get(player, {})
			elif player in roster.get(home, {}):
				playerStats = homeStats.get(player, {})
			else:
				continue

			bvp = pitcher = ""
			try:
				pitcher = lineups[opp]["pitcher"]
				pitcherLR = leftOrRight[opp].get(pitcher, "")
				bvpStats = bvpData[team][player+' v '+pitcher]
				bvp = f"{bvpStats['h']}-{bvpStats['ab']}, {bvpStats['hr']} HR"
			except:
				pass

			try:
				order = lineups[team]["batters"].index(player)+1
			except:
				order = "-"

			try:
				hrs = [(i, x) for i, x in enumerate(playerStats["hr"]) if x]
				lastHR = len(playerStats["hr"]) - hrs[-1][0]
				lastHR = f"{lastHR} Games"
			except:
				lastHR = ""

			avgOver = []
			avgUnder = []
			highest = 0
			evBook = ""
			books = data[game][player].keys()

			if "fd" not in books:
				#continue
				pass
			oddsArr = []
			for book in books:
				odds = data[game][player][book]
				oddsArr.append(odds)
				over = odds.split("/")[0]
				#print(book, over)
				highest = max(highest, int(over))
				if highest == int(over):
					evBook = book
				avgOver.append(convertImpOdds(int(over)))
				if "/" in odds and book not in ["kambi", "espn"]:
				#if "/" in odds and book not in ["kambi", "pn"]:
				#if "/" in odds:
					avgUnder.append(convertImpOdds(int(odds.split("/")[-1])))

			if avgOver:
				avgOver = float(sum(avgOver) / len(avgOver))
				avgOver = convertAmericanFromImplied(avgOver)
			else:
				avgOver = "-"
			if avgUnder:
				avgUnder = float(sum(avgUnder) / len(avgUnder))
				avgUnder = convertAmericanFromImplied(avgUnder)
			else:
				avgUnder = "-"

			ou = f"{avgOver}/{avgUnder}"
			if ou == "-/-" or ou.startswith("-/") or ou.startswith("0/"):
				continue

			if ou.endswith("/-") or ou.endswith("/0"):
				ou = ou.split("/")[0]

			devig(evData, player, ou, highest)
			if "dk" in books:
				#if evBook == "dk" and player in evData:
				#	evData[player]["dk_ev"] = evData[player]["ev"]
				#else:
				devig(evData, player, ou, int(data[game][player]["dk"]), book="dk-sweat", dinger=True)
				devig(evData, player, ou, int(data[game][player]["dk"]), book="dk")
				pass
			if "espn" in books:
				devig(evData, player, ou, int(data[game][player]["espn"].split("/")[0]), book="espn")
				o = int(data[game][player]["espn"].split("/")[0])
				o = convertAmericanOdds(1 + (convertDecOdds(o) - 1) * 1.50)
				devig(evData, player, ou, o, book="espn-50")

				if "circa" in books:
					devig(evData, player, data[game][player]["circa"], o, book="espn-50-vs-circa")

			if "mgm" in books:
				devig(evData, player, ou, int(data[game][player]["mgm"].split("/")[0]), book="mgm")
				devig(evData, player, ou, int(data[game][player]["mgm"].split("/")[0]), book="mgm-sweat", dinger=True)
				o = int(data[game][player]["mgm"].split("/")[0])
				o = convertAmericanOdds(1 + (convertDecOdds(o) - 1) * 1.20)
				devig(evData, player, ou, o, book="mgm-20")

				if "circa" in books:
					devig(evData, player, data[game][player]["circa"], o, book="mgm-20-vs-circa")
			if "fd" in books:
				devig(evData, player, ou, int(data[game][player]["fd"]), book="fd")
				fd = int(data[game][player]["fd"])
				fd = convertAmericanOdds(1 + (convertDecOdds(fd) - 1) * 1.50)
				devig(evData, player, ou, fd, book="fd-50")
			if "circa" in books:
				devig(evData, player, data[game][player]["circa"], highest, book="vs-circa")
			if "pn" in books:
				devig(evData, player, data[game][player]["pn"], highest, book="vs-pn")
			if "pn" in books and "circa" in books:
				pn = data[game][player]["pn"]
				circa = data[game][player]["circa"]
				sharpOver = [convertImpOdds(int(pn.split("/")[0])), convertImpOdds(int(circa.split("/")[0]))]
				sharpOver = float(sum(sharpOver) / len(sharpOver))
				sharpOver = convertAmericanFromImplied(sharpOver)

				sharpUnder = [convertImpOdds(int(pn.split("/")[1])), convertImpOdds(int(circa.split("/")[1]))]
				sharpUnder = float(sum(sharpUnder) / len(sharpUnder))
				sharpUnder = convertAmericanFromImplied(sharpUnder)
				devig(evData, player, f"{sharpOver}/{sharpUnder}", highest, book="vs-sharp")
			if "365" in books:
				devig(evData, player, data[game][player]["365"], highest, book="vs-365")

			if player not in evData:
				continue
			elif evData[player]["ev"] > 0 and not silent:
				print(f"{player} {evBook} +{highest}, FV={evData[player]['fairVal']}")

			try:
				j = ph[team][player]["2024"]
				pinchHit = f"{j['ph']} PH / {j['g']} G"
			except:
				pinchHit = ""
			
			evData[player]["id"] = f"{game}-{player}"
			evData[player]["player"] = player
			evData[player]["pitcher"] = "" if not pitcher else f"{pitcher} ({pitcherLR})"
			evData[player]["game"] = game
			evData[player]["team"] = team
			evData[player]["weather"] = gameWeather
			evData[player]["book"] = evBook
			evData[player]["line"] = highest
			evData[player]["ou"] = ou
			evData[player]["prop"] = "hr"
			evData[player]["bvp"] = bvp
			evData[player]["lastHR"] = lastHR
			evData[player]["ph"] = pinchHit
			evData[player]["order"] = order
			evData[player]["start"] = gameStart
			evData[player]["bookOdds"] = {b: o for b, o in zip(books, oddsArr)}

	with open("static/dingers/ev.json", "w") as fh:
		json.dump(evData, fh, indent=4)

	with open("static/dingers/evArr.json", "w") as fh:
		json.dump(
			{"updated": updated, "data": [value for key, value in evData.items()]},
			fh,
			indent=4
		)

def printEV():
	with open(f"static/dingers/ev.json") as fh:
		evData = json.load(fh)

	l = ["EV (AVG)", "EV (365)", "Game", "Player", "IN", "FD", "AVG", "bet365", "DK", "MGM", "CZ", "Kambi"]
	output = "\t".join(l) + "\n"
	for row in sorted(evData.items(), key=lambda item: item[1]["ev"], reverse=True):
		l = [row[-1]["ev"], "", row[-1]["game"].upper(), row[0].title(), ""]
		for book in ["fd", "avg", "365", "dk", "mgm", "cz", "kambi"]:
			if book in row[-1]["bookOdds"]:
				l.append(f"'{row[-1]['bookOdds'][book]}")
			else:
				l.append("")
		output += "\t".join([str(x) for x in l]) + "\n"

	with open("static/dingers/ev.csv", "w") as fh:
		fh.write(output)

sharedData = {}
def runThread(book):
	uc.loop().run_until_complete(writeOne(book))

async def writeWeather(date):
	try:
		browser = await uc.start(no_sandbox=True)
	except:
		return
	url = f"https://swishanalytics.com/mlb/weather?date={date}"
	page = await browser.get(url)

	await page.wait_for(selector=".weather-overview-table")
	html = await page.get_content()
	soup = BS(html, "html.parser")

	weather = nested_dict()
	for row in soup.select(".weatherClick"):
		tds = row.select("small")
		game = tds[1].text.lower().strip().replace("\u00a0", " ").replace("  ", " ").replace("az", "ari").replace("cws", "chw")
		wind = tds[2].text
		gameId = row.get("id")
		weather[game]["wind"] = wind.replace("\u00a0", " ").replace("  ", " ").strip()

		extra = soup.find("div", id=f"{gameId}Row")
		time, stadium = map(str, soup.find("div", id=f"{gameId}Row").select(".desktop-hide")[0].text.split(" | "))
		weather[game]["time"] = time
		weather[game]["stadium"] = stadium
		for row in extra.find("tbody").find_all("tr"):
			hdr = row.find("td").text.lower()
			tds = row.select(".gametime-hour small")
			if not tds:
				tds = row.select(".gametime-hour")
			
			weather[game][hdr] = [x.text.strip().replace("\u00b0", "") for x in tds][1]
			if hdr == "wind dir":
				transform = row.find("img").get("style").split("; ")[-1]
				weather[game]["transform"] = [x.get("style").split("; ")[-1] for x in row.select(".gametime-hour img:nth-of-type(1)")][1]


	with open("static/mlb/weather.json", "w") as fh:
		json.dump(weather, fh, indent=4)

def writeLineups(date):
	if not date:
		date = str(datetime.now())[:10]

	with open(f"static/baseballreference/leftOrRight.json") as fh:
		leftOrRight = json.load(fh)

	url = f"https://www.mlb.com/starting-lineups/{date}"
	result = subprocess.run(["curl", url], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

	soup = BS(result.stdout, "html.parser")

	pitchers = {}
	for table in soup.find_all("div", class_="starting-lineups__matchup"):
		player = parsePlayer(table.find("a").text.strip())

	data = {}
	for table in soup.select(".starting-lineups__matchup"):
		for idx, which in enumerate(["away", "home"]):
			try:
				team = table.find("div", class_=f"starting-lineups__teams--{which}-head").text.strip().split(" ")[0].lower().replace("az", "ari").replace("cws", "chw")
			except:
				continue

			if team in data:
				continue

			pitcher = parsePlayer(table.find_all("div", class_="starting-lineups__pitcher-name")[idx].text.strip())
			try:
				leftRight = "L" if table.find_all("span", class_="starting-lineups__pitcher-pitch-hand")[idx].text == "LHP" else "R"
			except:
				leftRight = ""
			leftOrRight[team][pitcher] = leftRight
			data[team] = {"pitcher": pitcher, "batters": []}
			for player in table.find("ol", class_=f"starting-lineups__team--{which}").find_all("li"):
				try:
					player = parsePlayer(player.find("a").text.strip())
				except:
					player = parsePlayer(player.text)

				data[team]["batters"].append(player)

	#for row in plays:
	#	if row[-1] in data and len(data[row[-1]]) > 1:
	#		if row[0] not in data[row[-1]]:
	#			print(row[0], "SITTING!!")

	with open(f"static/mlb/lineups.json", "w") as fh:
		json.dump(data, fh, indent=4)

	with open(f"static/baseballreference/leftOrRight.json", "w") as fh:
		json.dump(leftOrRight, fh, indent=4)

async def writeOne(book):
	#with open(f"dailyev/odds.json") as fh:
	#	data = json.load(fh)
	data = nested_dict()

	try:
		browser = await uc.start(no_sandbox=True)
	except:
		return
	if book == "fd":
		await writeFD(data, browser)
	elif book == "dk":
		await writeDK(data, browser)
	elif book == "mgm":
		await writeMGM(data, browser)
	elif book == "espn":
		await writeESPN(data, browser)
	elif book == "kambi":
		writeKambi(data)

	browser.stop()

	if True:
		with locks[book]:
			old = {}
			if os.path.exists(f"static/dingers/{book}.json"):
				with open(f"static/dingers/{book}.json") as fh:
					old = json.load(fh)
			old.update(data)
			with open(f"static/dingers/{book}.json", "w") as fh:
				json.dump(old, fh, indent=4)

def runThreads(book, date, games, totThreads):
	threads = []
	schedule_url = "https://raw.githubusercontent.com/zhecht/playerprops/main/static/baseballreference/roster.json"
	response = requests.get(schedule_url)
	roster = response.json()

	writeHistorical(date, book)

	for _ in range(totThreads):
		if book == "mgm":
			thread = threading.Thread(target=runMGM, args=())
		elif book == "espn":
			thread = threading.Thread(target=runESPN, args=(roster,))
		elif book == "fd":
			thread = threading.Thread(target=runFD, args=())
		thread.start()
		threads.append(thread)

	for game in games:
		url = games[game]
		q.put((game,url))

	q.join()

	with open(f"static/dingers/updated_{book}", "w") as fh:
		fh.write(str(datetime.now()))

	for _ in range(totThreads):
		q.put((None,None))
	for thread in threads:
		thread.join()

def writeOdds():
	with open(f"mlb/bet365.json") as fh:
		bet365Lines = json.load(fh)

	with open(f"mlb/kambi.json") as fh:
		kambiLines = json.load(fh)

	with open(f"mlb/pinnacle.json") as fh:
		pnLines = json.load(fh)

	with open(f"mlb/mgm.json") as fh:
		mgmLines = json.load(fh)

	with open(f"mlb/fanduel.json") as fh:
		fdLines = json.load(fh)

	with open(f"mlb/draftkings.json") as fh:
		dkLines = json.load(fh)

	with open(f"mlb/caesars.json") as fh:
		czLines = json.load(fh)

	with open(f"mlb/espn.json") as fh:
		espnLines = json.load(fh)

	lines = {
		"pn": pnLines,
		"kambi": kambiLines,
		"mgm": mgmLines,
		"fd": fdLines,
		"dk": dkLines,
		"cz": czLines,
		"espn": espnLines,
		"365": bet365Lines
	}

	data = nested_dict()
	for book in lines:
		d = lines[book]
		for game in d:
			if "hr" in d[game]:
				for player in d[game]["hr"]:
					if book in ["fd", "cz", "kambi"]:
						data[game][player][book] = d[game]["hr"][player]
					elif "0.5" in d[game]["hr"][player]:
						data[game][player][book] = d[game]["hr"][player]["0.5"]

	with open("dailyev/odds.json", "w") as fh:
		json.dump(data, fh, indent=4)

if __name__ == '__main__':
	parser = argparse.ArgumentParser()
	parser.add_argument("--sport")
	parser.add_argument("--token")
	parser.add_argument("--commit", action="store_true")
	parser.add_argument("--tmrw", action="store_true")
	parser.add_argument("--date", "-d")
	parser.add_argument("--print", "-p", action="store_true")
	parser.add_argument("--update", "-u", action="store_true")
	parser.add_argument("--bvp", action="store_true")
	parser.add_argument("--bet365", action="store_true")
	parser.add_argument("--b365", action="store_true")
	parser.add_argument("--espn", action="store_true")
	parser.add_argument("--cz", action="store_true")
	parser.add_argument("--dk", action="store_true")
	parser.add_argument("--br", action="store_true")
	parser.add_argument("--fd", action="store_true")
	parser.add_argument("--pn", action="store_true")
	parser.add_argument("--mgm", action="store_true")
	parser.add_argument("--kambi", action="store_true")
	parser.add_argument("--feed", action="store_true")
	parser.add_argument("--keep", action="store_true")
	parser.add_argument("--ev", action="store_true")
	parser.add_argument("--loop", action="store_true")
	parser.add_argument("--lineups", action="store_true")
	parser.add_argument("--weather", action="store_true")
	parser.add_argument("--dinger", action="store_true")
	parser.add_argument("--threads", type=int, default=5)
	parser.add_argument("--scrape", action="store_true")
	parser.add_argument("--clear", action="store_true")
	parser.add_argument("--stats", action="store_true")
	parser.add_argument("--night", action="store_true")
	parser.add_argument("--history", action="store_true")
	parser.add_argument("--circa", action="store_true")
	parser.add_argument("--circa-props", action="store_true")
	parser.add_argument("--circa-main", action="store_true")
	parser.add_argument("--merge-circa", action="store_true")

	args = parser.parse_args()

	if args.clear:
		for book in ["fd", "espn", "dk", "cz", "b365", "mgm", "pn", "circa"]:
			path = f"static/dingers/{book}.json"
			with open(path, "w") as fh:
				json.dump({}, fh)
		with open("static/dingers/odds.json", "w") as fh:
			json.dump({}, fh)
		with open("static/mlb/circa.json", "w") as fh:
			json.dump({}, fh)

	games = {}
	date = args.date
	if args.tmrw:
		date = str(datetime.now() + timedelta(days=1))[:10]
	elif not date:
		date = str(datetime.now())[:10]

	if args.bvp:
		uc.loop().run_until_complete(writeBVP(date))

	if args.history:
		writeHistory()

	if args.feed:
		uc.loop().run_until_complete(writeFeed(args.date, args.loop))
	elif args.fd:
		#games = uc.loop().run_until_complete(getFDLinks(date))
		#games["mil @ nyy"] = "https://mi.sportsbook.fanduel.com/baseball/mlb/milwaukee-brewers-@-new-york-yankees-34146634?tab=batter-props"
		#runThreads("fd", games, min(args.threads, len(games)))
		uc.loop().run_until_complete(writeFDFromBuilder(date, args.loop, args.night))
	elif args.mgm:
		games = uc.loop().run_until_complete(getMGMLinks(date))
		#games['det @ lad'] = 'https://sports.mi.betmgm.com/en/sports/events/detroit-tigers-at-los-angeles-dodgers-17081448'
		runThreads("mgm", date, games, min(args.threads, len(games)))
	elif args.dk:
		uc.loop().run_until_complete(writeDK(date, args.loop, args.night))
	elif args.br:
		uc.loop().run_until_complete(writeBR(date))
	elif args.bet365 or args.b365:
		uc.loop().run_until_complete(write365(args.loop))
	elif args.espn:
		games = uc.loop().run_until_complete(getESPNLinks(date))
		#games['mil @ nyy'] = 'https://espnbet.com/sport/baseball/organization/united-states/competition/mlb/event/b353fbf4-02ef-409b-8327-58fb3b0b1fa9/section/player_props'
		runThreads("espn", date, games, min(args.threads, len(games)))
	
	if args.cz:
		uc.loop().run_until_complete(writeCZ(date, args.token))
	if args.kambi:
		writeKambi(date)
	if args.pn:
		writePinnacle(date)
		pass
	if args.circa_props:
		writeCirca(date)
	if args.circa_main:
		writeCircaMain(date)
	if args.circa:
		writeCirca(date)
		writeCircaMain(date)
		mergeCirca()
		exit()
	if args.merge_circa:
		mergeCirca()
		exit()

	if args.weather:
		uc.loop().run_until_complete(writeWeather(date))

	if args.lineups:
		writeLineups(date)

	if args.update:

		while True:
			if args.ev:
				writeEV(date, args.dinger)
			if args.print:
				printEV()
			#for book in ["weather", "lineups", "cz", "dk", "bet365", "fd", "espn", "mgm"]:
			for book in ["weather", "lineups", "cz", "bet365", "espn", "mgm", "pn"]:
			#for book in ["espn", "mgm"]:
				subprocess.Popen(["python", "dingers.py", f"--{book}", "-d", date])

			if not args.loop:
				break

			# every 5m
			if args.night:
				time.sleep(60 * 30)
			else:
				time.sleep(60 * 5)
			print(datetime.now())
			if args.ev:
				writeEV(date, args.dinger)
			if args.print:
				printEV()

			if args.commit:
				commitChanges()

		"""
		uc.loop().run_until_complete(writeWeather(date))
		writeLineups(args.date)
		uc.loop().run_until_complete(writeCZ(date, args.token))
		print("kambi")
		writeKambi(date)
		print("dk")
		uc.loop().run_until_complete(writeOne("dk"))
		print("365")
		uc.loop().run_until_complete(writeOne("365"))
		"""

	if args.commit and args.loop:
		while True:
			if args.ev:
				writeEV(date, args.dinger, silent=True)
			if args.print:
				printEV()
			try:
				commitChanges()
			except:
				if os.path.exists("/mnt/c/Users/zhech/Documents/lines/.git/index.lock"):
					os.system("rm /mnt/c/Users/zhech/Documents/lines/.git/index.lock")
				pass

			if args.night:
				time.sleep(60 * 10)
			else:
				time.sleep(5)

	if args.ev:
		writeEV(date, args.dinger)
	if args.print:
		printEV()

	if args.stats:
		writeStatsPage(date)

	if args.scrape:
		writeOdds()

	if args.commit:
		commitChanges()

	if False:
		data = nested_dict()
		with open("static/mlb/circa-props") as fh:
			lines = fh.read().split("\n")
		if lines[0] == date:
			for row in lines[1:]:
				cols = row.split(",")
				game, prop, player = cols[0], cols[1], cols[2]
				if prop == "hr":
					data[game][prop][player] = cols[-1]
				else:
					data[game][prop][player][cols[3]] = cols[-1]
			
			with open("static/mlb/circa.json", "w") as fh:
				json.dump(data, fh, indent=4)



