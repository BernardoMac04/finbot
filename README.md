# FinBot — Análise de Ações Brasileiras com IA

Dashboard interativo para análise técnica de ações da B3 com análise em português gerada pelo Claude.

## Estrutura

```
finbot/
├── data/fetcher.py          → busca OHLCV via yfinance + cotação via Brapi/yfinance
├── analysis/indicators.py   → RSI, MACD, Bollinger Bands, SMA, EMA, ATR, OBV
├── ai/analyst.py            → análise e chat em português via Claude (Anthropic)
├── dashboard/app.py         → interface Streamlit com gráficos Plotly
├── tests/test_indicators.py → testes unitários dos indicadores
├── requirements.txt
└── .env.example
```

## Setup

```bash
# 1. Instalar dependências
pip install -r requirements.txt

# 2. Configurar variáveis de ambiente
cp .env.example .env
# Edite .env e adicione sua ANTHROPIC_API_KEY

# 3. Rodar testes
pytest tests/ -v

# 4. Subir o dashboard
streamlit run dashboard/app.py
```

## Variáveis de ambiente

| Variável           | Obrigatório | Descrição                              |
|--------------------|-------------|----------------------------------------|
| `ANTHROPIC_API_KEY`| Sim         | Chave da API Anthropic (claude.ai)     |
| `BRAPI_TOKEN`      | Não         | Token Brapi para cotações (brapi.dev)  |

## API pública

```python
from data.fetcher import fetch_ohlcv, fetch_quote
from analysis.indicators import add_indicators, get_signals
from ai.analyst import analyze, StockChat

df = fetch_ohlcv("PETR4", period="3mo", interval="1d")
df = add_indicators(df)
signals = get_signals(df)
quote = fetch_quote("PETR4")

report = analyze("PETR4", quote, signals)
print(report)

chat = StockChat("PETR4", context={"quote": quote, "signals": signals})
print(chat.chat("Qual é a tendência de curto prazo?"))
```
