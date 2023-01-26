from flask import Blueprint, render_template
import yfinance as yf
import json
import datetime
from json import JSONEncoder
import pickle
import traceback

def get_ticker_hist(symbol, period):
    obj = yf.Ticker(symbol)
    hist_df = obj.history(period=period, auto_adjust=False)
    if abs(hist_df['Close'].iloc[-1] - obj.fast_info['last_price']) > 0.1:
        hist_df = hist_df.reset_index()
        new_row = {
          'Date' : datetime.datetime.now(),
          'Open' : obj.info['regularMarketOpen'],
          'High' : obj.info['regularMarketDayHigh'],
          'Low' : obj.info['regularMarketDayLow'],
          'Close' : obj.info['regularMarketPrice'],
          'Adj Close' : obj.info['regularMarketPrice'],
          'Volume' : 0,
          'Dividends' : 0,
          'Volume' : 0
        }
        hist_df = hist_df.append(new_row,ignore_index=True)
        hist_df = hist_df.set_index('Date')
    return hist_df

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
    if dxy.get("high", 0) and usdkrw.get("low", 0):
        gap_dic["high"] = dxy.get("high", 0) / usdkrw.get("low", 0) * 100.0
    if dxy.get("low", 0) and usdkrw.get("high", 0):
        gap_dic["low"] = dxy.get("low", 0) / usdkrw.get("high", 0) * 100.0
    if dxy.get("close", 0) and usdkrw.get("close", 0):
        close = gap_dic["close"] = dxy.get("close", 0) / usdkrw.get("close", 0) * 100.0
    if dxy.get("mid", 0) and usdkrw.get("mid", 0):
        mid = gap_dic["mid"] = dxy.get("mid", 0) / usdkrw.get("mid", 0) * 100.0
        hgap = gap_dic["high"] - mid
        lgap = mid - gap_dic["low"]
        if hgap > lgap:
            gap_dic["low"] = mid - hgap
        else:
            gap_dic["high"] = mid + lgap
    gap_dic["is_buy"] = bool(close > mid)
    return gap_dic

def get_proper_usdkrw(dxy, gap_rate, usdkrw):
    proper_dic = {}
    mid = 0
    if dxy.get("close", 0) and gap_rate.get("mid", 0):
        mid = dxy.get("close", 0) / gap_rate.get("mid", 0) * 100.0
        proper_dic["mid"] = mid
    if dxy.get("high", 0) and gap_rate.get("low", 0):
        proper_dic["high"] = dxy.get("high", 0) / gap_rate.get("low", 0) * 100.0
        hgap = proper_dic["high"] - mid
    if dxy.get("low", 0) and gap_rate.get("high", 0):
        proper_dic["low"] = dxy.get("low", 0) / gap_rate.get("high", 0) * 100.0
        lgap = mid - proper_dic["low"]
    if usdkrw.get("close", 0):
        usdkrw_close = usdkrw.get("close", 0)
        proper_dic["close"] = usdkrw_close
    if mid and usdkrw_close:
        proper_dic["is_buy"] = bool(usdkrw_close < mid)
        if hgap > lgap:
            proper_dic["low"] = mid - hgap
        else:
            proper_dic["high"] = mid + lgap
    return proper_dic

bp = Blueprint('main', __name__, url_prefix='/')

# subclass JSONEncoder
class DateTimeEncoder(JSONEncoder):
        #Override the default method
        def default(self, obj):
            if isinstance(obj, (datetime.date, datetime.datetime)):
                return obj.isoformat()

def get_dollar_dic(period):
    usdkrw = get_ticker_values( get_ticker_hist("KRW=X", period) )
    dxy = get_ticker_values( get_ticker_hist("DX-Y.NYB", period) )
    gap = get_gap(usdkrw, dxy)
    proper = get_proper_usdkrw(dxy, gap, usdkrw)
    dollar_dic = {
        'usdkrw': usdkrw,
        'dxy': dxy,
        'gap': gap,
        'proper': proper,
        'created': datetime.datetime.now(),
    }
    return dollar_dic

@bp.route('/dollar/<period>', methods=('GET', ))
def get_dollar_json(period):
    try:
        dollar_dic = pickle.load(open('%s.pkl' % period, 'rb'))
    except:
        traceback.print_exc()
        dollar_dic = get_dollar_dic(period)
    return json.dumps(dollar_dic, indent = 4, cls=DateTimeEncoder)

@bp.route('/dollar/<period>', methods=('POST', ))
def post_dollar_json(period):
    dollar_dic = get_dollar_dic(period)
    pickle.dump(dollar_dic, open('%s.pkl' % period, 'wb'))
    now = datetime.datetime.now()
    result_dic = {'created':dollar_dic.get('created', now)}
    return json.dumps(result_dic, indent = 4, cls=DateTimeEncoder)

@bp.route('/')
def index():
    return render_template('index.html')
