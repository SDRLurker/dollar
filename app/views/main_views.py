from flask import Blueprint, render_template
import yfinance as yf
import json
import datetime
from json import JSONEncoder
import pickle
import traceback
import pandas as pd


def get_ticker_hist(symbol, period):
    obj = yf.Ticker(symbol)

    # Yahoo Finance historical data
    hist_df = obj.history(
        period=period,
        auto_adjust=False
    )

    if hist_df.empty:
        raise RuntimeError(f"{symbol}: Yahoo Finance returned empty data")

    # 현재가
    try:
        last_price = float(obj.fast_info["last_price"])
    except Exception:
        # fast_info 실패 시 history의 마지막 종가 사용
        last_price = float(hist_df["Close"].iloc[-1])

    last_close = float(hist_df["Close"].iloc[-1])

    # 장중 현재가가 마지막 historical close와 다르면
    # 현재 장중 데이터를 마지막 row에 추가
    if abs(last_close - last_price) > 0.1:

        # timezone-aware 현재 시각
        now = datetime.datetime.now(datetime.timezone.utc)

        # 기존 데이터가 timezone-aware라면 같은 timezone 사용
        if getattr(hist_df.index, "tz", None) is not None:
            now = now.astimezone(hist_df.index.tz)

        # 현재 장중 OHLC
        try:
            day_open = float(obj.fast_info["open"])
        except Exception:
            day_open = last_price

        try:
            day_high = float(obj.fast_info["day_high"])
        except Exception:
            day_high = last_price

        try:
            day_low = float(obj.fast_info["day_low"])
        except Exception:
            day_low = last_price

        new_row = pd.DataFrame(
            {
                "Open": [day_open],
                "High": [day_high],
                "Low": [day_low],
                "Close": [last_price],
                "Adj Close": [last_price],
                "Volume": [0],
                "Dividends": [0],
                "Stock Splits": [0],
            },
            index=pd.DatetimeIndex([now], name=hist_df.index.name)
        )

        hist_df = pd.concat([hist_df, new_row])

    return hist_df


def get_ticker_values(hist):
    if hist.empty:
        raise RuntimeError("Empty historical data")

    low = float(hist["Low"].min())
    high = float(hist["High"].max())
    mid = (high + low) / 2.0
    close = float(hist["Close"].iloc[-1])

    values_dic = {
        "low": low,
        "high": high,
        "mid": mid,
        "close": close,
        "is_buy": bool(close < mid)
    }

    return values_dic


def get_gap(usdkrw, dxy):
    gap_dic = {}

    if dxy.get("high", 0) and usdkrw.get("low", 0):
        gap_dic["high"] = (
            dxy.get("high", 0)
            / usdkrw.get("low", 0)
            * 100.0
        )

    if dxy.get("low", 0) and usdkrw.get("high", 0):
        gap_dic["low"] = (
            dxy.get("low", 0)
            / usdkrw.get("high", 0)
            * 100.0
        )

    if dxy.get("close", 0) and usdkrw.get("close", 0):
        close = gap_dic["close"] = (
            dxy.get("close", 0)
            / usdkrw.get("close", 0)
            * 100.0
        )
    else:
        close = 0

    if dxy.get("mid", 0) and usdkrw.get("mid", 0):
        mid = gap_dic["mid"] = (
            dxy.get("mid", 0)
            / usdkrw.get("mid", 0)
            * 100.0
        )

        hgap = gap_dic["high"] - mid
        lgap = mid - gap_dic["low"]

        if hgap > lgap:
            gap_dic["low"] = mid - hgap
        else:
            gap_dic["high"] = mid + lgap

    gap_dic["is_buy"] = bool(close > gap_dic.get("mid", 0))

    return gap_dic


def get_proper_usdkrw(dxy, gap_rate, usdkrw):
    proper_dic = {}

    mid = 0
    usdkrw_close = usdkrw.get("close", 0)

    if dxy.get("close", 0) and gap_rate.get("mid", 0):
        mid = (
            dxy.get("close", 0)
            / gap_rate.get("mid", 0)
            * 100.0
        )
        proper_dic["mid"] = mid

    if dxy.get("high", 0) and gap_rate.get("low", 0):
        proper_dic["high"] = (
            dxy.get("high", 0)
            / gap_rate.get("low", 0)
            * 100.0
        )
        hgap = proper_dic["high"] - mid
    else:
        hgap = 0

    if dxy.get("low", 0) and gap_rate.get("high", 0):
        proper_dic["low"] = (
            dxy.get("low", 0)
            / gap_rate.get("high", 0)
            * 100.0
        )
        lgap = mid - proper_dic["low"]
    else:
        lgap = 0

    if usdkrw_close:
        proper_dic["close"] = usdkrw_close

    if mid and usdkrw_close:
        proper_dic["is_buy"] = bool(usdkrw_close < mid)

        if hgap > lgap:
            proper_dic["low"] = mid - hgap
        else:
            proper_dic["high"] = mid + lgap

    return proper_dic


bp = Blueprint("main", __name__, url_prefix="/")


class DateTimeEncoder(JSONEncoder):

    def default(self, obj):
        if isinstance(obj, (datetime.date, datetime.datetime)):
            return obj.isoformat()

        return super().default(obj)


def get_dollar_dic(period):

    usdkrw = get_ticker_values(
        get_ticker_hist("KRW=X", period)
    )

    dxy = get_ticker_values(
        get_ticker_hist("DX-Y.NYB", period)
    )

    gap = get_gap(usdkrw, dxy)

    proper = get_proper_usdkrw(
        dxy,
        gap,
        usdkrw
    )

    dollar_dic = {
        "usdkrw": usdkrw,
        "dxy": dxy,
        "gap": gap,
        "proper": proper,
        "created": datetime.datetime.now(),
    }

    return dollar_dic


@bp.route("/dollar/<period>", methods=("GET",))
def get_dollar_json(period):

    try:
        with open(f"{period}.pkl", "rb") as f:
            dollar_dic = pickle.load(f)

    except Exception:
        traceback.print_exc()
        dollar_dic = get_dollar_dic(period)

    return json.dumps(
        dollar_dic,
        indent=4,
        cls=DateTimeEncoder
    )


@bp.route("/dollar/<period>", methods=("POST",))
def post_dollar_json(period):

    dollar_dic = get_dollar_dic(period)

    with open(f"{period}.pkl", "wb") as f:
        pickle.dump(dollar_dic, f)

    now = datetime.datetime.now()

    result_dic = {
        "created": dollar_dic.get("created", now)
    }

    return json.dumps(
        result_dic,
        indent=4,
        cls=DateTimeEncoder
    )


@bp.route("/")
def index():
    return render_template("index.html")
