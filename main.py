# ==========================================
# PREOPEN MOMENTUM SCANNER - FINAL VERSION
# ==========================================
#
# INSTALL REQUIRED LIBRARIES:
#
# pip install pandas yfinance schedule openpyxl requests nsepython
#
# ==========================================

import pandas as pd
import yfinance as yf
import schedule
import time
import requests
import holidays


import datetime
from nsepython import *


# ==========================================
# TELEGRAM SETTINGS
# ==========================================

BOT_TOKEN = "8667626238:AAE04TszgZDIZkqyiFS7cAn_uEYZuJ3OlRI"
CHAT_ID = "8610840272"

# ==========================================
# SEND TELEGRAM MESSAGE
# ==========================================


def send_telegram(message):

    try:

        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

        payload = {
            "chat_id": CHAT_ID,
            "text": message
        }

        response = requests.post(url, data=payload)

        print("Telegram Status:", response.status_code)

    except Exception as e:

        print("Telegram Error:", e)

# ==========================================
# FETCH NSE PREOPEN DATA
# ==========================================


def fetch_preopen_data():

    print("\n===================================")
    print("FETCHING NSE PREOPEN DATA")
    print("===================================")

    try:

        # IMPORTANT
        # ALL = Full market
        # Not only NIFTY50

        data = nse_preopen("ALL")

        if data is None:

            print("No data received")

            return pd.DataFrame()

        # SAFE CONVERSION

        if isinstance(data, pd.DataFrame):

            df = data.copy()

        else:

            df = pd.DataFrame(data)

        print("\n===================================")
        print("AVAILABLE COLUMNS")
        print("===================================")

        print(df.columns.tolist())

        print("\n===================================")
        print("RAW SAMPLE DATA")
        print("===================================")

        print(df.head())

        print("\nTotal Stocks:", len(df))

        # ==========================================
        # BUILD FINAL DATAFRAME
        # ==========================================

        final_df = pd.DataFrame()

        # SYMBOL

        final_df["Symbol"] = df.get("symbol", "")

        # PRICE

        final_df["Price"] = pd.to_numeric(
            df.get("lastPrice", 0),
            errors="coerce"
        )

        # % CHANGE

        final_df["%Change"] = pd.to_numeric(
            df.get("pChange", 0),
            errors="coerce"
        )

        # QUANTITY

        if "finalQuantity" in df.columns:

            final_df["Qty"] = pd.to_numeric(
                df.get("finalQuantity", 0),
                errors="coerce"
            )

        elif "totalTradedVolume" in df.columns:

            final_df["Qty"] = pd.to_numeric(
                df.get("totalTradedVolume", 0),
                errors="coerce"
            )

        else:

            final_df["Qty"] = 0

        # VALUE / TURNOVER

        if "totalTurnover" in df.columns:

            final_df["Value"] = pd.to_numeric(
                df.get("totalTurnover", 0),
                errors="coerce"
            )

        else:

            final_df["Value"] = (
                final_df["Price"] *
                final_df["Qty"]
            )

        # CLEAN NAN

        final_df = final_df.fillna(0)

        # ROUNDING

        final_df["Price"] = final_df["Price"].round(2)

        final_df["%Change"] = final_df["%Change"].round(2)

        final_df["Value"] = final_df["Value"].round(2)

        print("\n===================================")
        print("FINAL PREOPEN DATA")
        print("===================================")

        print(final_df.head())

        return final_df

    except Exception as e:

        print("FETCH PREOPEN ERROR:", e)

        return pd.DataFrame()

# ==========================================
# APPLY PREOPEN FILTERS
# ==========================================


def apply_preopen_filters(df):

    print("\n===================================")
    print("APPLYING PREOPEN FILTERS")
    print("===================================")

    if df.empty:

        print("Dataframe Empty")

        return df

    print("Before Filters:", len(df))

    # MAIN FILTERS

    filtered = df[
        (df["%Change"] > 2) &
        (df["Qty"] > 50000) &
        (df["Value"] > 10000000) &
        (df["Price"] > 20)
    ]

    print("After Filters:", len(filtered))

    # TEST MODE

    if filtered.empty:

        print("\nNo stocks passed filters.")

        print("\nUsing Top 10 Stocks For Testing")

        filtered = df.head(10)

    print("\n===================================")
    print("FILTERED STOCKS")
    print("===================================")

    print(filtered)

    return filtered

# ==========================================
# PROCESS STOCK
# ==========================================


def process_stock(stock, row):

    try:

        print(f"\nProcessing: {stock}")

        ticker = stock + ".NS"

        # DOWNLOAD HISTORICAL DATA

        hist = yf.download(
            ticker,
            period="3mo",
            interval="1d",
            progress=False,
            auto_adjust=True,
            threads=False
        )

        if hist.empty:

            print(f"{stock} : Empty historical data")

            return None

        if len(hist) < 25:

            print(f"{stock} : Not enough candles")

            return None

        # ==========================================
        # CALCULATIONS
        # ==========================================

        hist["20DMA"] = (
            hist["Close"]
            .rolling(20)
            .mean()
        )

        hist["AvgVol20"] = (
            hist["Volume"]
            .rolling(20)
            .mean()
        )

        latest = hist.iloc[-1]

        # SAFE VALUE EXTRACTION

        close_price = latest["Close"]

        dma20 = latest["20DMA"]

        avg_vol = latest["AvgVol20"]

        latest_vol = latest["Volume"]

        # FIX SERIES ISSUE

        if hasattr(close_price, "iloc"):
            close_price = close_price.iloc[0]

        if hasattr(dma20, "iloc"):
            dma20 = dma20.iloc[0]

        if hasattr(avg_vol, "iloc"):
            avg_vol = avg_vol.iloc[0]

        if hasattr(latest_vol, "iloc"):
            latest_vol = latest_vol.iloc[0]

        # CONVERT TO FLOAT

        close_price = float(close_price)

        dma20 = float(dma20)

        avg_vol = float(avg_vol)

        latest_vol = float(latest_vol)

        print(
            f"{stock} | "
            f"Close={close_price:.2f} | "
            f"DMA20={dma20:.2f} | "
            f"AvgVol={avg_vol:.0f} | "
            f"LastVol={latest_vol:.0f}"
        )

        # ==========================================
        # FINAL CONDITIONS
        # ==========================================

        if (
            close_price > dma20 and
            latest_vol > (2 * avg_vol)
        ):

            relative_vol = round(
                latest_vol / avg_vol,
                2
            )

            # SCORING MODEL

            score = (
                row["%Change"] * 0.4
                +
                relative_vol * 0.3
                +
                (row["Value"] / 10000000) * 0.3
            )

            print(f"{stock} PASSED")

            return {

                "Symbol": stock,

                # REAL PREOPEN PRICE
                "PreOpenPrice": round(row["Price"], 2),

                # YESTERDAY CLOSE
                "PrevClose": round(close_price, 2),

                "%Change": row["%Change"],

                "Qty": int(row["Qty"]),

                "Value(Cr)": round(
                    row["Value"] / 10000000,
                    2
                ),

                "20DMA": round(dma20, 2),

                "AvgVol20": int(avg_vol),

                "LastVolume": int(latest_vol),

                "RVOL": relative_vol,

                "Score": round(score, 2)
            }

        else:

            print(f"{stock} FAILED FINAL CONDITIONS")

    except Exception as e:

        print(f"PROCESS ERROR in {stock}: {e}")

    return None


# ==========================================
# CHECK MARKET HOLIDAY / WEEKEND
# ==========================================

def is_market_open_day():

    today = datetime.datetime.now()

    # WEEKEND CHECK

    if today.weekday() >= 5:

        print("\n===================================")
        print("MARKET CLOSED - WEEKEND")
        print("===================================")

        return False

    # INDIA HOLIDAYS

    india_holidays = holidays.India()

    if today.date() in india_holidays:

        print("\n===================================")
        print("MARKET HOLIDAY")
        print("===================================")

        print(india_holidays.get(today.date()))

        return False

    return True

# ==========================================
# MAIN SCANNER
# ==========================================


def run_scanner():

    print("\n\n")
    print("===================================")
    print("RUNNING PREOPEN MOMENTUM SCANNER")
    print("===================================")

    # CHECK MARKET OPEN DAY

    if not is_market_open_day():

        return

    try:

        # STEP 1
        # FETCH PREOPEN DATA

        df = fetch_preopen_data()

        if df.empty:

            print("No preopen data found")

            send_telegram(
                "No NSE preopen data available."
            )

            return

        # STEP 2
        # APPLY FILTERS

        filtered = apply_preopen_filters(df)

        if filtered.empty:

            print("No filtered stocks")

            send_telegram(
                "No stocks passed filters."
            )

            return

        # STEP 3
        # PROCESS STOCKS

        results = []

        for _, row in filtered.iterrows():

            stock = row["Symbol"]

            result = process_stock(stock, row)

            if result:

                results.append(result)

        # STEP 4
        # CREATE FINAL DATAFRAME

        final_df = pd.DataFrame(results)

        if final_df.empty:

            print("\nNO FINAL STOCKS FOUND")

            send_telegram(
                "No final momentum stocks found."
            )

            return

        # STEP 5
        # SORT BY SCORE

        final_df = final_df.sort_values(
            by="Score",
            ascending=False
        )

        print("\n===================================")
        print("FINAL RESULTS")
        print("===================================")

        print(final_df)

        # STEP 6
        # EXPORT TO EXCEL

        # filename = (
        #    f"PreOpen_Momentum_"
        #    f"{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
       # )

       # final_df.to_excel(
       #     filename,
         #   index=False
       # )

        # print("\nExcel Saved:", filename)

        # STEP 7
        # TELEGRAM ALERT

        top5 = final_df.head(5)

        msg = "🔥 PREOPEN MOMENTUM STOCKS 🔥\n\n"

        for _, row in top5.iterrows():

            msg += (
                f"{row['Symbol']}\n"
                f"Gap: {row['%Change']}%\n"
                f"RVOL: {row['RVOL']}\n"
                f"Score: {row['Score']}\n\n"
            )

        send_telegram(msg)

        print("\nTelegram Alert Sent")

    except Exception as e:

        print("MAIN SCANNER ERROR:", e)

# ==========================================
# RUN IMMEDIATELY FOR TESTING
# ==========================================


# run_scanner()

# ==========================================
# DAILY AUTOMATION
# ==========================================

schedule.every().day.at("03:40").do(run_scanner)

print("\nWaiting for daily 03:40 AM schedule...")

while True:

    schedule.run_pending()

    time.sleep(1)
