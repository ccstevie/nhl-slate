import chromedriver_autoinstaller
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options as ChromeOptions
import requests
import pandas as pd
from datetime import date, timedelta
from functools import reduce
import os
import urllib3

chromedriver_autoinstaller.install()

def getGames():
    url = 'https://www.rotowire.com/hockey/nhl-lineups.php'
    options = ChromeOptions()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--start-maximized')
    driver = webdriver.Chrome(options=options)

    driver.get(url)
    
    # return values
    matchups = []
    path = '/html/body/div/div/main/div[3]'
    lineups = driver.find_element(By.CLASS_NAME, 'lineups').find_elements(By.CLASS_NAME, 'lineup')
    for index, lineup in enumerate(lineups[:-1]):
        if index == 3 or index == 5 or index == len(lineups[:-1])-1:
            continue
        awayTeam = lineup.find_element(By.XPATH, f'{path}/div[{index+1}]/div[2]/div[2]/a[1]').text
        homeTeam = lineup.find_element(By.XPATH, f'{path}/div[{index+1}]/div[2]/div[2]/a[2]').text
        awayTeam = awayTeam.split(' (')[0]
        homeTeam = homeTeam.split(' (')[0]
        matchups.append((awayTeam, homeTeam))

    driver.quit()

    return matchups

today = date.today()
start = today - timedelta(days=30)

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
url = f"https://www.naturalstattrick.com/teamtable.php?fromseason=20242025&thruseason=20242025&stype=2&sit=5v5&score=all&rate=n&team=all&loc=B&gpf=410&fd={start}&td={today}"
# Fetch the HTML content with SSL verification disabled
req = requests.get(url, verify=False)

# Parse the table from the HTML response instead of making a new request
df = pd.read_html(req.text, header=0, index_col=0, na_values=["-"])[0]

cf = df.sort_values(by="CF%", ascending=False, ignore_index=True)
cf.index += 1
cf.reset_index(inplace=True)
cf = cf.rename(columns = {"index":"CF%"})
cf = cf[["Team", "CF%"]]

gf = df.sort_values(by="GF%", ascending=False, ignore_index=True)
gf.index += 1
gf.reset_index(inplace=True)
gf = gf.rename(columns = {"index":"GF%"})
gf = gf[["Team", "GF%"]]

xgf = df.sort_values(by="xGF%", ascending=False, ignore_index=True)
xgf.index += 1
xgf.reset_index(inplace=True)
xgf = xgf.rename(columns = {"index":"xGF%"})
xgf = xgf[["Team", "xGF%"]]

hdcf = df.sort_values(by="HDCF%", ascending=False, ignore_index=True)
hdcf.index += 1
hdcf.reset_index(inplace=True)
hdcf = hdcf.rename(columns = {"index":"HDCF%"})
hdcf = hdcf[["Team", "HDCF%"]]

sh = df.sort_values(by="SH%", ascending=False, ignore_index=True)
sh.index += 1
sh.reset_index(inplace=True)
sh = sh.rename(columns = {"index":"SH%"})
sh = sh[["Team", "SH%"]]

dfs = [cf, gf, xgf, hdcf, sh]
final_df = reduce(lambda  left,right: pd.merge(left,right,on=['Team'],
                                            how='outer'), dfs)

matchups = getGames()

res = pd.DataFrame()

for away, home in matchups:
    away_df = final_df[final_df["Team"].str.contains(away)]
    home_df = final_df[final_df["Team"].str.contains(home)]
    matchup_df = pd.concat([away_df, home_df], ignore_index=True)
    res = pd.concat([res, matchup_df], ignore_index=True)


output_dir = os.path.join(os.path.dirname(__file__), "..", "public")
output_file = os.path.join(output_dir, "result.csv")

with open(output_file, 'w') as f:
    for col in res.columns.values:
        f.write(col + ",")
    f.write("\n")
    
    i = 0
    for col in res.values:
        for row in col:
            f.write(str(row) + ",")
        if i % 2 == 0:
            f.write("\n")
        else:
            f.write("\n\n")
        i += 1