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

# --- AI SUMMARY (UNCHANGED) ---
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

# LEFT PANEL (UNCHANGED)
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

        st.markdown(f"""
        <div style="padding:14px;margin-bottom:12px;border-radius:16px;background:rgba(17,25,40,0.85);backdrop-filter:blur(12px);border:1px solid rgba(59,130,246,0.15);box-shadow:0 4px 20px rgba(0,0,0,0.25);">
            <b>{name}</b><br>
            <span style="color:#9CA3AF;font-size:12px;">{open_t} – {close_t}</span><br>
            <span style="font-size:13px;font-weight:600;">{status}</span>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("""
    <div style="font-size:12px;color:#9CA3AF;background:rgba(17,25,40,0.6);padding:10px;border-radius:10px;border:1px solid #1E293B;">
    <b>⚖️ Disclaimer</b><br>
    This tool is for educational purposes only and does not constitute financial advice. 
    All signals (Buy/Sell/Hold) are algorithmic and may be inaccurate. 
    Market data may be delayed.
    </div>
    """, unsafe_allow_html=True)

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
            delta=h['Close'].diff()
            gain=delta.clip(lower=0)
            loss=-delta.clip(upper=0)
            rs=gain.rolling(14).mean()/loss.rolling(14).mean()
            h['RSI']=100-(100/(1+rs))

            ema12=h['Close'].ewm(span=12).mean()
            ema26=h['Close'].ewm(span=26).mean()
            h['MACD']=ema12-ema26
            h['Signal']=h['MACD'].ewm(span=9).mean()

            if PLOTLY_AVAILABLE:
                fig=make_subplots(rows=3,cols=1,shared_xaxes=True,row_heights=[0.6,0.2,0.2])
                fig.add_trace(go.Candlestick(x=h.index,open=h['Open'],high=h['High'],low=h['Low'],close=h['Close']),row=1,col=1)
                fig.add_trace(go.Scatter(x=h.index,y=h['RSI']),row=2,col=1)
                fig.add_hline(y=70,row=2,col=1)
                fig.add_hline(y=30,row=2,col=1)
                fig.add_trace(go.Scatter(x=h.index,y=h['MACD']),row=3,col=1)
                fig.add_trace(go.Scatter(x=h.index,y=h['Signal']),row=3,col=1)
                fig.update_layout(template="plotly_dark",height=700)
                st.plotly_chart(fig,use_container_width=True)
            else:
                st.error("Install plotly")

            st.markdown("### 📊 Trend Analysis")
            st.info(generate_trend_summary(h))

            csv = convert_to_csv(h)
            st.download_button("📥 Download Financial Data (CSV)",csv,f"{ticker}_financial_data.csv","text/csv")

    if st.session_state.data:
        d=st.session_state.data
        st.metric("Price", f"{d['symbol']} {round(d['price'],2)}")
        st.metric("EPS",d["eps"] or "N/A")
        st.metric("P/E",round(d["pe"],2) if d["pe"] else "N/A")
        st.metric("Debt/Eq",round(d["de"],2) if d["de"] else "N/A")
        st.markdown(generate_signal(d))

    st.markdown("### 📄 Document Auditor")
    f=st.file_uploader("Upload Annual Report (PDF)")

    if f:
        doc=fitz.open(stream=io.BytesIO(f.read()))
        pages=[p.get_text() for p in doc]

        snippets=[]
        total_score=0

        # --- NEW SENTENCE-BASED ANALYSIS ---
        for i, page in enumerate(pages):
            sentences = page.split(".")
            for sentence in sentences:
                score, label = classify_sentence_risk(sentence)
                if score > 0:
                    snippets.append((label, i+1, sentence.strip()))
                    total_score += score

        full_text = " ".join(pages).lower()

        if "true and fair view" in full_text:
            op="Unqualified"
        elif "qualified opinion" in full_text:
            op="Qualified"
        else:
            op="Unclear"

        verdict="🟢 GOOD" if total_score<=1 else "🟡 CAUTION" if total_score<=3 else "🔴 HIGH RISK"

        c1,c2=st.columns(2)
        c1.metric("Audit Opinion",op)
        c2.metric("Risk Score",total_score)

        st.markdown(f"### Final Verdict: {verdict}")

        summary = generate_audit_summary(snippets,total_score,op)
        st.markdown("### 🧠 Audit Insight")
        st.info(summary)

        if snippets:
            for k,p,t in snippets:
                st.write(f"{k} (Page {p})")
                st.caption(t)

# RIGHT PANEL
with r:
    st.markdown("### 📈 High Performers")

    if st.button("🔄 Refresh"):
        get_high_performers.clear()
        st.rerun()

    for s,c_ in get_high_performers():
        st.write(f"{s} {'🟢' if c_>0 else '🔴'} {round(c_,2)}%")
