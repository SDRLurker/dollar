from flask import Blueprint
import yfinance as yf
import json

def get_ticker_hist(symbol, period):
    df = yf.Ticker(symbol)
    hist = df.history(period=period, auto_adjust=False)
    return hist

def get_ticker_values(hist):
    low = hist['Low'].min()
    high = hist['High'].max()
    mid = (high + low) / 2.0
    close = hist['Close'].iloc[-1]
    values_dic = {
      "low": low,      
      "high": high,      
      "mid" : mid,
      "close" : close,
      "is_buy" : bool(close < mid)
    }
    return values_dic

def get_gap(usdkrw, dxy):
    gap_dic = {}
    mid = dxy.get("mid", 0) / usdkrw.get("mid", 0) * 100.0
    close = dxy.get("close", 0) / usdkrw.get("close", 0) * 100.0
    if dxy.get("mid", 0) and usdkrw.get("mid", 0):
        gap_dic["mid"] = mid
    if dxy.get("close", 0) and usdkrw.get("close", 0):
        gap_dic["close"] = close
    gap_dic["is_buy"] = bool(close > mid)
    return gap_dic

def get_proper_usdkrw(dxy, gap_rate, usdkrw):
    proper_dic = {}
    value = 0
    if dxy.get("close", 0) and gap_rate.get("mid", 0):
        value = dxy.get("close", 0) / gap_rate.get("mid", 0) * 100.0
        usdkrw_close = usdkrw.get("close",0)
        proper_dic = {
          "value" : value,
          "close" : usdkrw_close,
          "is_buy" : bool(usdkrw_close < value)
        }
    return proper_dic

bp = Blueprint('main', __name__, url_prefix='/')

@bp.route('/dollar/<period>')
def get_dollar_json(period):
    usdkrw = get_ticker_values( get_ticker_hist("KRW=X", period) )
    dxy = get_ticker_values( get_ticker_hist("DX-Y.NYB", period) )
    gap = get_gap(usdkrw, dxy)
    proper = get_proper_usdkrw(dxy, gap, usdkrw)
    dollar_dic = {
        'usdkrw': usdkrw,
        'dxy': dxy,
        'gap': gap,
        'proper': proper
    }
    return json.dumps(dollar_dic, indent = 4)

@bp.route('/')
def index():
    return 'dollar index'