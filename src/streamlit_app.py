import streamlit as st
import fitz
import yfinance as yf
import pandas as pd
import io
from datetime import datetime
import pytz

# --- PLOTLY ---
try:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    PLOTLY_AVAILABLE = True
except:
    PLOTLY_AVAILABLE = False

st.set_page_config(page_title="GLOBAL TREND ANALYST", layout="wide")

# --- CACHE ---
@st.cache_data(ttl=300)
def get_stock_history(ticker, period):
    return yf.Ticker(ticker).history(period=period)

@st.cache_data(ttl=300)
def get_stock_info(ticker):
    return yf.Ticker(ticker).info

@st.cache_data(ttl=3600)
def get_high_performers():
    tickers = [
        "AAPL","MSFT","TSLA","NVDA","META","GOOG","AMZN",
        "RELIANCE.NS","TCS.NS","INFY.NS","HDFCBANK.NS"
    ]
    perf=[]
    for t in tickers:
        try:
            h=yf.Ticker(t).history(period="5d")
            if not h.empty:
                c=((h['Close'].iloc[-1]-h['Close'].iloc[0])/h['Close'].iloc[0])*100
                perf.append((t,c))
        except:
            continue
    return sorted(perf,key=lambda x:x[1],reverse=True)[:10]

# --- CURRENCY ---
def get_currency_symbol(info):
    currency = info.get("currency", "")
    symbol_map = {
        "INR": "₹","USD": "$","EUR": "€","GBP": "£",
        "JPY": "¥","CNY": "¥","AUD": "A$","HKD": "HK$"
    }
    return symbol_map.get(currency, currency)

# --- MARKET STATUS ---
def get_market_status(open_time, close_time, tz_str, breaks=None):
    tz = pytz.timezone(tz_str)
    now = datetime.now(tz).time()
    open_t = datetime.strptime(open_time,"%H:%M").time()
    close_t = datetime.strptime(close_time,"%H:%M").time()

    if breaks:
        for b_start,b_end in breaks:
            if datetime.strptime(b_start,"%H:%M").time() <= now <= datetime.strptime(b_end,"%H:%M").time():
                return "🟡 Break"

    return "🟢 Open" if open_t <= now <= close_t else "🔴 Closed"

# --- DOWNLOAD ---
def convert_to_csv(df):
    return df.to_csv().encode('utf-8')

# --- TREND ---
def generate_trend_summary(df):
    try:
        change=((df['Close'].iloc[-1]-df['Close'].iloc[0])/df['Close'].iloc[0])*100
        vol=df['Close'].pct_change().std()*100
        if change>10: t="strong bullish"
        elif change>3: t="moderate bullish"
        elif change<-10: t="strong bearish"
        elif change<-3: t="moderate bearish"
        else: t="sideways"
        return f"{t} | Change {round(change,2)}% | Volatility {round(vol,2)}%"
    except:
        return "Trend unavailable"

# --- SIGNAL ---
def generate_signal(d):
    try:
        score = 0
        pe = d.get("pe")
        de = d.get("de")
        eps = d.get("eps")

        if pe:
            if pe < 15: score += 2
            elif pe < 30: score += 1
            else: score -= 1

        if de:
            if de < 1: score += 1
            elif de > 2: score -= 1

        if eps:
            if eps > 0: score += 1
            else: score -= 2

        if score >= 3:
            return "🟢 BUY"
        elif score >= 1:
            return "🟡 HOLD"
        else:
            return "🔴 SELL"

    except:
        return "N/A"

# --- NEW: SENTENCE-LEVEL RISK CLASSIFIER ---
def classify_sentence_risk(sentence):
    s = sentence.lower()

    if any(x in s for x in [
        "no fraud", "no litigation", "not material",
        "no significant", "no material weakness"
    ]):
        return 0, None

    if any(x in s for x in [
        "fraud", "investigation", "forensic", "regulatory action"
    ]):
        return 3, "High Risk Event"

    if any(x in s for x in [
        "material weakness", "going concern", "qualified opinion"
    ]):
        return 2, "Moderate Risk"

    if any(x in s for x in [
        "litigation", "legal proceedings", "contingent liability"
    ]):
        return 1, "Low Risk"

    return 0, None

# --- AI SUMMARY ---
def generate_audit_summary(detected, total_score, opinion):
    try:
        if not detected:
            return "The audit report does not indicate significant risk factors. The financial statements appear stable, and no major red flags such as fraud, litigation, or control weaknesses were identified."

        risk_types = list(set([r[0] for r in detected]))

        summary = f"The audit findings highlight {', '.join(risk_types)}. "

        if total_score >= 4:
            summary += "These risks collectively indicate a high-risk financial position requiring careful evaluation. "
        elif total_score >= 2:
            summary += "These factors suggest moderate risk and warrant cautious interpretation. "
        else:
            summary += "The identified risks are limited and may not significantly impact overall financial reliability. "

        if "qualified" in opinion.lower() or "adverse" in opinion.lower():
            summary += "Additionally, the audit opinion raises concerns about the accuracy or completeness of financial statements."

        return summary.strip()
    except:
        return "Unable to generate audit summary."

# --- LAYOUT ---
l,c,r=st.columns([1,2,1])

# LEFT PANEL
with l:
    st.markdown("### 🕒 Global Market Timings")
    markets = [
        ("🇮🇳 NSE","09:15","15:30","Asia/Kolkata",None),
        ("🇺🇸 NYSE","09:30","16:00","US/Eastern",None),
        ("🇺🇸 NASDAQ","09:30","16:00","US/Eastern",None),
        ("🇬🇧 LSE","08:00","16:30","Europe/London",None),
        ("🇪🇺 Euronext","09:00","17:30","Europe/Paris",None),
        ("🇯🇵 TSE","09:00","15:00","Asia/Tokyo",[("11:30","12:30")]),
        ("🇨🇳 SSE","09:30","15:00","Asia/Shanghai",[("11:30","13:00")]),
        ("🇭🇰 HKEX","09:30","16:00","Asia/Hong_Kong",[("12:00","13:00")]),
        ("🇦🇺 ASX","10:00","16:00","Australia/Sydney",None),
    ]

    for name, open_t, close_t, tz, breaks in markets:
        status = get_market_status(open_t, close_t, tz, breaks)
        st.markdown(f"<b>{name}</b> {open_t}-{close_t} {status}", unsafe_allow_html=True)

# CENTER PANEL
with c:
    st.title("📊 Global Trend Analyst")

    ticker=st.text_input("Enter Ticker","RELIANCE.NS").upper()
    b1,b2=st.columns(2)

    if "data" not in st.session_state:
        st.session_state.data=None

    if b1.button("RUN ANALYSIS"):
        h=get_stock_history(ticker,"1d")
        i=get_stock_info(ticker)
        if not h.empty:
            st.session_state.data={
                "price":h['Close'].iloc[-1],
                "symbol":get_currency_symbol(i),
                "eps":i.get("trailingEps"),
                "pe":i.get("trailingPE"),
                "de":i.get("debtToEquity")
            }

    if b2.button("SHOW TREND"):
        h=get_stock_history(ticker,"6mo")
        if not h.empty:
            st.line_chart(h['Close'])

    if st.session_state.data:
        d=st.session_state.data
        st.metric("Price", f"{d['symbol']} {round(d['price'],2)}")

    # --- DOCUMENT AUDITOR (FIXED INDENTATION ONLY) ---
    st.markdown("### 📄 Document Auditor")
    f = st.file_uploader("Upload Annual Report (PDF)")

    if f:
        with st.spinner("Auditing massive report..."):
            file_bytes = f.read()
            doc = fitz.open(stream=io.BytesIO(file_bytes), filetype="pdf")

            snippets = []
            total_score = 0

            MAX_PAGES = 30
            pages = []

            for i, page in enumerate(doc):
                if i >= MAX_PAGES:
                    break
                pages.append(page.get_text())
# RIGHT PANEL
with r:
    st.markdown("### 📈 High Performers")

    if st.button("🔄 Refresh"):
        get_high_performers.clear()
        st.rerun()

    for s,c_ in get_high_performers():
        st.write(f"{s} {'🟢' if c_>0 else '🔴'} {round(c_,2)}%")
