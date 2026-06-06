# FinBot — Status do Projeto

**Última atualização:** 2026-06-06

---

## Estrutura do projeto

```
finbot/
├── data/
│   ├── __init__.py
│   └── fetcher.py          fetch_ohlcv() e fetch_quote() — Brapi → yfinance fallback
├── analysis/
│   ├── __init__.py
│   └── indicators.py       RSI, MACD, Bollinger Bands, SMA 20/50/200, EMA 9/21, ATR, OBV
│                           + get_signals() com lógica alta/baixa/neutro
├── ai/
│   ├── __init__.py
│   └── analyst.py          analyze() e StockChat — Groq llama-3.3-70b-versatile
├── dashboard/
│   ├── __init__.py
│   └── app.py              Interface Streamlit completa (tema escuro, UI profissional)
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   └── test_indicators.py  18 testes unitários — todos passando
├── .streamlit/
│   ├── config.toml         Tema escuro personalizado (#00D4AA / #0E1117)
│   └── secrets.toml.example  Template para Streamlit Cloud
├── requirements.txt
├── .env                    ← local only, ignorado pelo git
├── .env.example
├── .gitignore
└── README.md
```

---

## O que está funcionando

| Funcionalidade | Status | Detalhe |
|---|---|---|
| Busca OHLCV | ✅ | `fetch_ohlcv()` via yfinance |
| Cotação atual | ✅ | `fetch_quote()` com fallback Brapi → yfinance |
| Indicadores técnicos | ✅ | RSI, MACD, BB, SMA, EMA, ATR, OBV |
| Sinais automáticos | ✅ | `get_signals()` retorna alta/baixa/neutro |
| Testes unitários | ✅ | 18/18 passando (`pytest tests/ -v`) |
| Dashboard Streamlit | ✅ | Roda em `http://localhost:8501` |
| Tema escuro | ✅ | `.streamlit/config.toml` com cor primária #00D4AA |
| Header com gradiente | ✅ | Logo + ticker + horário da última atualização |
| Metric cards | ✅ | Cards com borda verde/vermelho e setas ↑↓ |
| Gráfico candlestick | ✅ | 4 painéis: OHLC, Volume, RSI, MACD — fundo #0E1117 |
| Anotações no gráfico | ✅ | ▲▼ nos cruzamentos EMA 9/21 |
| Badges de sinais | ✅ | ALTA / BAIXA / NEUTRO coloridos |
| Barra de progresso RSI | ✅ | HTML customizado com zonas de sobrecompra/venda |
| Gauge de sentimento | ✅ | Plotly Indicator com gradiente verde/amarelo/vermelho |
| Favoritos na sidebar | ✅ | PETR4, VALE3, ITUB4, BBDC4, WEGE3 clicáveis |
| Botão atualizar dados | ✅ | Recarrega sem trocar o ticker |
| Análise IA | ✅ | Groq `llama-3.3-70b-versatile` em português |
| Chat interativo | ✅ | Histórico de conversa mantido na sessão |
| Rodapé com disclaimer | ✅ | Aviso legal + versão + data/hora |
| Compatibilidade Cloud | ✅ | `st.secrets` → `os.getenv` automático |

---

## Histórico de mudanças desta sessão (2026-06-06)

| Problema / Tarefa | Solução aplicada |
|---|---|
| Erro 429 com Gemini (`gemini-2.0-flash` em cache) | Limpeza do `__pycache__` + restart do Streamlit |
| Troca de provedor IA: Gemini → Groq | `ai/analyst.py` reescrito com `groq.Groq`; modelo `llama-3.3-70b-versatile` |
| `requirements.txt` com `google-genai` | Substituído por `groq>=0.12.0` |
| `.env` com `GEMINI_API_KEY` | Trocado para `GROQ_API_KEY=gsk_...` |
| `dashboard/app.py` verificando chave errada | `GEMINI_API_KEY` → `GROQ_API_KEY` em todos os lugares |
| `load_dotenv()` não carregava o `.env` no Streamlit | Adicionado `load_dotenv(caminho_absoluto)` com `__file__` no topo do `app.py` |
| Processos Streamlit com código antigo em memória | Identificados e encerrados via `Stop-Process` |
| Interface básica → UI profissional | Tema escuro, cards, gauge, badges, favoritos, footer |
| Deploy no Streamlit Cloud | `.gitignore`, `secrets.toml.example`, injeção de `st.secrets` no `os.environ` |
| Git não instalado | Arquivos preparados; git pendente de instalação |

---

## Próximos passos — Deploy

### 1. Instalar Git
Baixe em **git-scm.com/download/win** e instale com opções padrão.

### 2. Primeiro commit
```bash
cd "c:\Users\berna\OneDrive\Documentos\Projeto_Financeiro\finbot"
git init
git add .
git commit -m "feat: FinBot v1.0 — análise de ações com IA"
```

### 3. Criar repositório no GitHub
1. Acesse **github.com/new**
2. Nome sugerido: `finbot`
3. Repositório **público** (necessário para Streamlit Cloud grátis)
4. **Não** inicializar com README (já temos)

### 4. Push para o GitHub
```bash
git remote add origin https://github.com/SEU_USUARIO/finbot.git
git branch -M main
git push -u origin main
```

### 5. Deploy no Streamlit Cloud
1. Acesse **share.streamlit.io**
2. Conecte sua conta GitHub
3. Configure o deploy:
   - **Repository:** `SEU_USUARIO/finbot`
   - **Branch:** `main`
   - **Main file path:** `dashboard/app.py`
4. Em **Advanced settings → Secrets**, adicione:
   ```toml
   GROQ_API_KEY = "gsk_..."
   BRAPI_TOKEN = ""
   ```
5. Clique em **Deploy**

O app ficará disponível em `https://SEU_USUARIO-finbot.streamlit.app`

---

## Como rodar localmente

```bash
cd finbot

# Instalar dependências
pip install -r requirements.txt

# Rodar testes
pytest tests/ -v

# Subir o dashboard
streamlit run dashboard/app.py
```

Dashboard disponível em **http://localhost:8501**.

---

## Dependências principais

| Pacote | Versão mínima | Uso |
|---|---|---|
| `streamlit` | 1.40.0 | Interface web |
| `plotly` | 5.24.0 | Gráficos interativos |
| `yfinance` | 0.2.40 | Dados OHLCV |
| `groq` | 0.12.0 | IA (llama-3.3-70b-versatile) |
| `pandas` | 2.2.0 | Processamento de dados |
| `numpy` | 1.26.0 | Cálculo de indicadores |
| `requests` | 2.32.0 | API Brapi |
| `python-dotenv` | 1.0.0 | Variáveis de ambiente local |
| `pytest` | 8.3.0 | Testes unitários |
