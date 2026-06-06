import html
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

import streamlit as st

# Injeta Streamlit Cloud secrets no os.environ para que analyst.py
# (que usa os.getenv) funcione tanto local quanto no Cloud.
try:
    for _k, _v in st.secrets.items():
        if _k not in os.environ:
            os.environ[_k] = str(_v)
except Exception:
    pass

import plotly.graph_objects as go
from plotly.subplots import make_subplots

from data.fetcher import fetch_ohlcv, fetch_quote
from analysis.indicators import add_indicators, get_signals
from ai.analyst import analyze, StockChat

st.set_page_config(
    page_title="FinBot — Ações BR",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Global CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
.metric-card {
    background: #1A1D24;
    border-radius: 10px;
    padding: 18px 20px;
    border-left: 4px solid #00D4AA;
    margin-bottom: 8px;
    min-height: 90px;
}
.metric-label {
    color: #888;
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    margin: 0 0 6px 0;
}
.metric-value {
    color: #FAFAFA;
    font-size: 1.45rem;
    font-weight: 700;
    margin: 0;
    line-height: 1.2;
}
.metric-delta-up  { color: #00c853; font-size: 0.88rem; margin: 5px 0 0 0; }
.metric-delta-dn  { color: #ff1744; font-size: 0.88rem; margin: 5px 0 0 0; }
.metric-delta-neu { color: #888;    font-size: 0.88rem; margin: 5px 0 0 0; }

.badge-alta   { background:#00c853; color:#000; padding:3px 11px; border-radius:12px; font-size:0.72rem; font-weight:700; }
.badge-baixa  { background:#ff1744; color:#fff; padding:3px 11px; border-radius:12px; font-size:0.72rem; font-weight:700; }
.badge-neutro { background:#ffd600; color:#000; padding:3px 11px; border-radius:12px; font-size:0.72rem; font-weight:700; }

.signal-card {
    background: #1A1D24;
    border-radius: 8px;
    padding: 14px 16px;
    margin-bottom: 10px;
    border: 1px solid #2A2D34;
}
.footer {
    text-align: center;
    color: #555;
    font-size: 0.73rem;
    padding: 28px 0 8px 0;
    border-top: 1px solid #2A2D34;
    margin-top: 36px;
    line-height: 1.8;
}
</style>
""", unsafe_allow_html=True)

APP_VERSION = "1.1.0"
FAVORITES   = ["PETR4", "VALE3", "ITUB4", "BBDC4", "WEGE3"]

SIGNAL_BADGE = {
    "alta":   '<span class="badge-alta">ALTA</span>',
    "baixa":  '<span class="badge-baixa">BAIXA</span>',
    "neutro": '<span class="badge-neutro">NEUTRO</span>',
}

INDICATOR_INFO = {
    "rsi":            "Índice de Força Relativa (0-100). Acima de 70 = sobrecomprado, abaixo de 30 = sobrevendido.",
    "macd":           "Convergência/Divergência de Médias. Quando MACD cruza acima da linha de sinal = tendência de alta.",
    "bollinger":      "Bandas de volatilidade. Preço próximo à banda inferior = possível suporte. Banda superior = resistência.",
    "medias_moveis":  "SMA20 e SMA50 mostram a tendência. Preço acima das médias = tendência de alta.",
    "ema_cruzamento": "EMA9 e EMA21. Quando EMA9 cruza acima da EMA21 = sinal de alta (golden cross).",
    "volatilidade":   "Average True Range. Mede a volatilidade do ativo. Quanto maior, mais volátil.",
}


# ── UI helpers ────────────────────────────────────────────────────────────────

def _metric_card(label: str, value: str, delta: str = "", delta_up: bool | None = None) -> str:
    if delta_up is True:
        delta_html = f'<p class="metric-delta-up">↑ {delta}</p>'
        border = "#00c853"
    elif delta_up is False:
        delta_html = f'<p class="metric-delta-dn">↓ {delta}</p>'
        border = "#ff1744"
    else:
        delta_html = f'<p class="metric-delta-neu">{delta}</p>' if delta else ""
        border = "#00D4AA"
    return (
        f'<div class="metric-card" style="border-left-color:{border}">'
        f'<p class="metric-label">{label}</p>'
        f'<p class="metric-value">{value}</p>'
        f'{delta_html}</div>'
    )


def _rsi_bar(value) -> str:
    try:
        v = float(value)
    except (ValueError, TypeError):
        return ""
    color = "#ff1744" if v >= 70 else ("#00c853" if v <= 30 else "#ffd600")
    zone  = "Sobrecomprado" if v >= 70 else ("Sobrevendido" if v <= 30 else "Neutro")
    return (
        '<div style="margin:10px 0 4px 0;">'
        '<div style="display:flex;justify-content:space-between;font-size:0.76rem;color:#888;margin-bottom:5px;">'
        f'<span>0 — Sobrevendido (30)</span>'
        f'<span style="color:{color};font-weight:700;">{v:.1f} — {zone}</span>'
        f'<span>Sobrecomprado (70) — 100</span>'
        '</div>'
        '<div style="background:#2A2D34;border-radius:5px;height:10px;overflow:hidden;position:relative;">'
        f'<div style="background:{color};width:{v}%;height:100%;border-radius:5px;"></div>'
        '<div style="position:absolute;top:0;left:30%;width:1px;height:100%;background:#555;"></div>'
        '<div style="position:absolute;top:0;left:70%;width:1px;height:100%;background:#555;"></div>'
        '</div></div>'
    )


def _sentiment_gauge(bull: int, bear: int, total: int) -> go.Figure:
    score = (bull / total * 100) if total > 0 else 50
    color = "#00c853" if score > 60 else ("#ff1744" if score < 40 else "#ffd600")
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=score,
        number={"suffix": "%", "font": {"size": 26, "color": "#FAFAFA"}},
        gauge={
            "axis": {"range": [0, 100], "tickcolor": "#555", "tickfont": {"color": "#888", "size": 9}},
            "bar": {"color": color, "thickness": 0.28},
            "bgcolor": "#1A1D24",
            "borderwidth": 0,
            "steps": [
                {"range": [0,  33], "color": "rgba(255,23,68,0.12)"},
                {"range": [33, 67], "color": "rgba(255,214,0,0.08)"},
                {"range": [67,100], "color": "rgba(0,200,83,0.12)"},
            ],
            "threshold": {"line": {"color": color, "width": 3}, "thickness": 0.75, "value": score},
        },
        title={"text": "Sentimento Geral", "font": {"size": 12, "color": "#888"}},
    ))
    fig.update_layout(
        height=200,
        margin=dict(l=20, r=20, t=50, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"color": "#FAFAFA"},
    )
    return fig


def _load_data(ticker: str, period: str, interval: str) -> tuple:
    df = fetch_ohlcv(ticker, period, interval)
    df = add_indicators(df)
    quote   = fetch_quote(ticker)
    signals = get_signals(df)
    return df, quote, signals


def _build_chart(df, ticker: str, show_bb: bool, show_sma: bool, show_ema: bool):
    fig = make_subplots(
        rows=4, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.08,
        row_heights=[0.50, 0.14, 0.18, 0.18],
        subplot_titles=[f"{ticker} — Candlestick", "Volume", "RSI (14)", "MACD"],
    )

    # Candlestick
    fig.add_trace(
        go.Candlestick(
            x=df.index,
            open=df["open"], high=df["high"],
            low=df["low"],  close=df["close"],
            name="OHLC",
            increasing_line_color="#00e676", increasing_fillcolor="#00c853",
            decreasing_line_color="#ff5252", decreasing_fillcolor="#ff1744",
        ),
        row=1, col=1,
    )

    # Bollinger Bands
    if show_bb:
        for col_name, color, dash, fill in [
            ("bb_upper", "rgba(0,212,170,0.5)",  "dot",   None),
            ("bb_mid",   "rgba(0,212,170,0.85)", "solid", None),
            ("bb_lower", "rgba(0,212,170,0.5)",  "dot",   "tonexty"),
        ]:
            kw = {"fillcolor": "rgba(0,212,170,0.04)"} if fill else {}
            fig.add_trace(
                go.Scatter(
                    x=df.index, y=df[col_name],
                    name=col_name.replace("_", " ").upper(),
                    line=dict(color=color, width=1, dash=dash),
                    fill=fill, **kw,
                ),
                row=1, col=1,
            )

    # SMAs
    if show_sma:
        for p, color in [(20, "#ff9800"), (50, "#ce93d8"), (200, "#42a5f5")]:
            col_n = f"sma_{p}"
            if col_n in df.columns:
                fig.add_trace(
                    go.Scatter(x=df.index, y=df[col_n], name=f"SMA {p}",
                               line=dict(color=color, width=1.5)),
                    row=1, col=1,
                )

    # EMAs + crossover annotations
    if show_ema:
        for span, color in [(9, "#f48fb1"), (21, "#80deea")]:
            col_n = f"ema_{span}"
            if col_n in df.columns:
                fig.add_trace(
                    go.Scatter(x=df.index, y=df[col_n], name=f"EMA {span}",
                               line=dict(color=color, width=1.5, dash="dash")),
                    row=1, col=1,
                )

        if "ema_9" in df.columns and "ema_21" in df.columns:
            diff = df["ema_9"] - df["ema_21"]
            prev = diff.shift(1)
            for idx in list(df.index[(prev < 0) & (diff >= 0)])[-5:]:
                fig.add_annotation(
                    x=idx, y=float(df.loc[idx, "low"]) * 0.993,
                    text="▲", showarrow=False,
                    font=dict(color="#00e676", size=14),
                    xref="x", yref="y",
                )
            for idx in list(df.index[(prev >= 0) & (diff < 0)])[-5:]:
                fig.add_annotation(
                    x=idx, y=float(df.loc[idx, "high"]) * 1.007,
                    text="▼", showarrow=False,
                    font=dict(color="#ff5252", size=14),
                    xref="x", yref="y",
                )

    # Volume
    bar_colors = ["#00c853" if c >= o else "#ff1744"
                  for c, o in zip(df["close"], df["open"])]
    fig.add_trace(
        go.Bar(x=df.index, y=df["volume"], name="Volume",
               marker_color=bar_colors, opacity=0.75),
        row=2, col=1,
    )

    # RSI
    fig.add_trace(
        go.Scatter(x=df.index, y=df["rsi"], name="RSI",
                   line=dict(color="#ffd600", width=1.8),
                   fill="tozeroy", fillcolor="rgba(255,214,0,0.04)"),
        row=3, col=1,
    )
    for level, color in [(70, "rgba(255,23,68,0.5)"), (30, "rgba(0,200,83,0.5)")]:
        fig.add_hline(y=level, line_dash="dot", line_color=color, row=3, col=1)
    fig.add_hrect(y0=30, y1=70, fillcolor="rgba(255,214,0,0.03)", row=3, col=1)

    # MACD
    hist_colors = ["#00c853" if v >= 0 else "#ff1744"
                   for v in df["macd_hist"].fillna(0)]
    fig.add_trace(
        go.Bar(x=df.index, y=df["macd_hist"], name="Histograma",
               marker_color=hist_colors, opacity=0.85),
        row=4, col=1,
    )
    fig.add_trace(
        go.Scatter(x=df.index, y=df["macd"], name="MACD",
                   line=dict(color="#42a5f5", width=1.8)),
        row=4, col=1,
    )
    fig.add_trace(
        go.Scatter(x=df.index, y=df["macd_signal"], name="Sinal",
                   line=dict(color="#ff9800", width=1.8)),
        row=4, col=1,
    )

    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="#0E1117",
        plot_bgcolor="#0E1117",
        height=860,
        showlegend=True,
        legend=dict(orientation="h", yanchor="top", y=-0.15,
                    xanchor="center", x=0.5, font_size=11,
                    bgcolor="rgba(0,0,0,0)"),
        xaxis_rangeslider_visible=False,
        margin=dict(l=0, r=10, t=30, b=0),
        font=dict(color="#FAFAFA"),
    )
    for r, title in [(1, "Preço (R$)"), (2, "Volume"), (3, "RSI"), (4, "MACD")]:
        fig.update_yaxes(title_text=title, row=r, col=1,
                         gridcolor="#1A1D24", zerolinecolor="#2A2D34")
    fig.update_xaxes(gridcolor="#1A1D24")
    return fig


# ── Session state defaults ────────────────────────────────────────────────────

for key, default in [
    ("df", None), ("quote", None), ("signals", None),
    ("analysis", None), ("chat", None), ("messages", []),
    ("loaded_ticker", None), ("last_update", None),
    ("ticker_input", "PETR4"),
]:
    if key not in st.session_state:
        st.session_state[key] = default


# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("## 📈 FinBot")
    st.caption("Análise de Ações Brasileiras com IA")
    st.divider()

    st.markdown("**Favoritos**")
    fav_cols = st.columns(3)
    for i, t in enumerate(FAVORITES):
        with fav_cols[i % 3]:
            is_active = st.session_state.get("ticker_input", "") == t
            if st.button(
                t,
                key=f"fav_{t}",
                use_container_width=True,
                type="primary" if is_active else "secondary",
            ):
                st.session_state.ticker_input = t
                st.rerun()

    st.divider()

    ticker_input = st.text_input(
        "Ticker (ex: PETR4, VALE3)",
        key="ticker_input",
    ).upper().strip()

    period   = st.selectbox("Período",   ["1mo", "3mo", "6mo", "1y", "2y", "5y"], index=1)
    interval = st.selectbox("Intervalo", ["1d", "1wk", "1mo"], index=0)

    st.divider()
    st.markdown("**Indicadores no gráfico**")
    show_bb  = st.checkbox("Bollinger Bands",                value=True)
    show_sma = st.checkbox("Médias Simples (SMA 20/50/200)", value=True)
    show_ema = st.checkbox("Médias Exponenciais (EMA 9/21)", value=False)

    st.divider()
    analyze_btn = st.button("🔍 Analisar",        type="primary",   use_container_width=True)
    refresh_btn = st.button("🔄 Atualizar Dados", type="secondary", use_container_width=True,
                            disabled=(st.session_state.loaded_ticker is None))

    if st.session_state.loaded_ticker:
        st.caption(f"Ativo: **{st.session_state.loaded_ticker}**")
    if st.session_state.last_update:
        st.caption(f"Última atualização: {st.session_state.last_update}")


# ── Header ────────────────────────────────────────────────────────────────────

ticker_label  = f"— {st.session_state.loaded_ticker}" if st.session_state.loaded_ticker else ""
update_label  = f"· Atualizado às {st.session_state.last_update}" if st.session_state.last_update else ""

st.markdown(f"""
<div style="display:flex;align-items:center;gap:14px;padding:4px 0 20px 0;
            border-bottom:1px solid #1A1D24;margin-bottom:20px;">
    <span style="font-size:2.8rem;line-height:1;">📈</span>
    <div>
        <h1 style="margin:0;font-size:2.1rem;font-weight:800;
                   background:linear-gradient(90deg,#00D4AA,#0099CC);
                   -webkit-background-clip:text;-webkit-text-fill-color:transparent;line-height:1.2;">
            FinBot {ticker_label}
        </h1>
        <p style="margin:0;color:#666;font-size:0.83rem;">
            Análise técnica e IA para ações brasileiras {update_label}
        </p>
    </div>
</div>
""", unsafe_allow_html=True)


# ── Data loading ──────────────────────────────────────────────────────────────

def _do_load(ticker: str, period: str, interval: str) -> None:
    with st.spinner(f"Carregando dados de {ticker}..."):
        try:
            df, quote, signals = _load_data(ticker, period, interval)
            st.session_state.df             = df
            st.session_state.quote          = quote
            st.session_state.signals        = signals
            st.session_state.loaded_ticker  = ticker
            st.session_state.last_update    = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            st.session_state.analysis       = None
            st.session_state.chat           = StockChat(ticker, {"quote": quote, "signals": signals})
            st.session_state.messages       = []
        except Exception as exc:
            st.error(f"Erro ao carregar dados: {exc}")
            st.stop()

if analyze_btn:
    _do_load(ticker_input, period, interval)

if refresh_btn and st.session_state.loaded_ticker:
    _do_load(st.session_state.loaded_ticker, period, interval)
    st.rerun()

# ── Empty state ───────────────────────────────────────────────────────────────

if st.session_state.df is None:
    st.info("👈 Selecione um favorito ou digite o ticker na barra lateral e clique em **Analisar**.")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("**📊 Gráficos interativos**\n\nCandlestick com Bollinger Bands, SMA e EMA. RSI e MACD em painéis separados.")
    with c2:
        st.markdown("**🤖 Análise com IA**\n\nAnálise completa em português via Groq (`llama-3.3-70b-versatile`).")
    with c3:
        st.markdown("**💬 Chat interativo**\n\nPerguntas sobre o ativo com histórico de conversa mantido pela IA.")
    st.stop()

df      = st.session_state.df
quote   = st.session_state.quote
signals = st.session_state.signals
ticker  = st.session_state.loaded_ticker

# ── Metrics row ───────────────────────────────────────────────────────────────

price      = quote.get("price")      or 0.0
change     = quote.get("change")     or 0.0
change_pct = quote.get("change_pct") or 0.0
rsi_raw    = signals.get("rsi", {}).get("value", None)
atr_pct    = signals.get("volatilidade", {}).get("value", "—")

all_sigs  = [v.get("signal") for v in signals.values() if "signal" in v]
bull      = all_sigs.count("alta")
bear      = all_sigs.count("baixa")
total_sig = len(all_sigs)
sentiment = "ALTA" if bull > bear else ("BAIXA" if bear > bull else "NEUTRO")

try:
    rsi_f     = float(rsi_raw)
    rsi_str   = f"{rsi_f:.1f}"
    rsi_zone  = "Sobrecomprado" if rsi_f >= 70 else ("Sobrevendido" if rsi_f <= 30 else "Neutro")
except (TypeError, ValueError):
    rsi_f, rsi_str, rsi_zone = None, "—", ""

c1, c2, c3, c4, c5 = st.columns(5)
pct_up = float(change_pct) > 0
pct_dn = float(change_pct) < 0
with c1:
    st.markdown(_metric_card("Preço Atual", f"R$ {float(price):.2f}",
                              f"{float(change_pct):+.2f}%",
                              True if pct_up else (False if pct_dn else None)),
                unsafe_allow_html=True)
with c2:
    chg_up = float(change) > 0
    chg_dn = float(change) < 0
    st.markdown(_metric_card("Variação R$", f"R$ {float(change):+.2f}",
                              None, True if chg_up else (False if chg_dn else None)),
                unsafe_allow_html=True)
with c3:
    st.markdown(_metric_card("RSI (14)", rsi_str, rsi_zone), unsafe_allow_html=True)
with c4:
    st.markdown(_metric_card("Volatilidade ATR%", f"{atr_pct}%"), unsafe_allow_html=True)
with c5:
    s_up = sentiment == "ALTA"
    s_dn = sentiment == "BAIXA"
    st.markdown(_metric_card("Sentimento", sentiment,
                              f"{bull}↑  {bear}↓  de {total_sig} sinais",
                              True if s_up else (False if s_dn else None)),
                unsafe_allow_html=True)

st.divider()

# ── Chart ─────────────────────────────────────────────────────────────────────

fig = _build_chart(df, ticker, show_bb, show_sma, show_ema)
st.plotly_chart(fig, use_container_width=True)

st.divider()

# ── Tabs ──────────────────────────────────────────────────────────────────────

tab_signals, tab_ai, tab_chat = st.tabs(
    ["📊 Sinais Técnicos", "🤖 Análise IA (Groq)", "💬 Chat com IA"]
)

with tab_signals:
    if not signals:
        st.warning("Dados insuficientes para calcular sinais.")
    else:
        g_col, r_col = st.columns([1, 2])
        with g_col:
            st.plotly_chart(_sentiment_gauge(bull, bear, total_sig), use_container_width=True)
        with r_col:
            st.markdown("**RSI (14) — Posição no Range**")
            st.markdown(_rsi_bar(rsi_raw), unsafe_allow_html=True)
            st.markdown(
                f"**Contagem:** {bull} sinal(is) de alta · "
                f"{bear} de baixa · {total_sig - bull - bear} neutro(s)"
            )

        st.divider()

        cols = st.columns(3)
        for i, (ind, data) in enumerate(signals.items()):
            sig   = data.get("signal", "neutro")
            badge = SIGNAL_BADGE.get(sig, SIGNAL_BADGE["neutro"])
            val   = data.get("value")
            label = ind.upper().replace("_", " ")
            with cols[i % 3]:
                val_html = (
                    f'<div style="margin:4px 0;font-family:monospace;color:#00D4AA;font-size:0.85rem;">{html.escape(str(val))}</div>'
                    if val is not None else ""
                )
                reason_safe = html.escape(data.get("reason", ""))
                card_html = (
                    '<div class="signal-card">'
                    f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;">'
                    f'<strong style="font-size:0.84rem;">{label}</strong>{badge}'
                    f'</div>'
                    f'{val_html}'
                    f'<p style="color:#888;font-size:0.77rem;margin:0;">{reason_safe}</p>'
                    '</div>'
                )
                st.markdown(card_html, unsafe_allow_html=True)
                if ind in INDICATOR_INFO:
                    with st.expander("ℹ️ O que é isso?"):
                        st.caption(INDICATOR_INFO[ind])

with tab_ai:
    api_key_present = bool(os.getenv("GROQ_API_KEY"))
    if not api_key_present:
        st.warning("Configure `GROQ_API_KEY` no arquivo `.env` para usar a análise IA.")
    else:
        if st.session_state.analysis is None:
            if st.button("🤖 Gerar análise completa", type="primary"):
                with st.spinner("Groq está analisando..."):
                    try:
                        st.session_state.analysis = analyze(ticker, quote, signals)
                    except Exception as exc:
                        st.error(f"Erro na análise IA: {exc}")
        if st.session_state.analysis:
            st.markdown(st.session_state.analysis)

with tab_chat:
    api_key_present = bool(os.getenv("GROQ_API_KEY"))
    if not api_key_present:
        st.warning("Configure `GROQ_API_KEY` no arquivo `.env` para usar o chat.")
        st.stop()

    st.caption(
        f"Chat sobre **{ticker}** — {st.session_state.chat.message_count} mensagens enviadas. "
        "Use o botão abaixo para resetar."
    )
    if st.button("🔄 Resetar conversa"):
        st.session_state.chat.reset()
        st.session_state.messages = []
        st.rerun()

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if user_input := st.chat_input(f"Pergunte algo sobre {ticker}..."):
        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)
        with st.chat_message("assistant"):
            with st.spinner("Pensando..."):
                try:
                    reply = st.session_state.chat.chat(user_input)
                    st.markdown(reply)
                    st.session_state.messages.append({"role": "assistant", "content": reply})
                except Exception as exc:
                    st.error(f"Erro no chat: {exc}")


# ── Footer ────────────────────────────────────────────────────────────────────

st.markdown(f"""
<div class="footer">
    <p>⚠️ <strong>Disclaimer:</strong> As informações exibidas têm caráter exclusivamente informativo e educacional.
    Não constituem recomendação de investimento. Consulte um assessor financeiro certificado antes de tomar decisões de investimento.</p>
    <p>FinBot v{APP_VERSION} &nbsp;·&nbsp; Dados via yfinance / Brapi
    &nbsp;·&nbsp; IA via Groq (llama-3.3-70b-versatile)
    &nbsp;·&nbsp; {datetime.now().strftime("%d/%m/%Y %H:%M")}</p>
</div>
""", unsafe_allow_html=True)
