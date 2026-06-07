# Research Funding Assistant

## 🎯 Overview
Asistente inteligente que analiza grupos de investigación y encuentra 
oportunidades de financiación en Horizon Europe 2026-2027.

Input: URL de un grupo de investigación
Output: Top 10 opportunities ranked + detalles completos + link a PDF oficial

## 🚀 Features
- Extracción automática de perfil desde web del grupo
- Clasificación en 10 sectores (AI, Health, Mobility, etc.)
- Ranking inteligente de 386 calls Horizon Europe
- 3 vistas: Quick (top 10) + By Sector (top 5 + top 3) + Full List (todas)
- Panel lateral con datos críticos (deadline, eligibility, scope)
- Detail page con link directo al PDF oficial

## 📋 Tech Stack
Backend: Python 3.12 + FastAPI + Claude Haiku/Sonnet API
Frontend: React/HTML
Database: Índice JSON (471 calls Horizon Europe)
Deployment: Railway

## 🏃 Quick Start

### Locally
```bash
git clone <repo>
cd funding-mvp
python -m venv venv
venv\Scripts\activate  # Windows
source venv/bin/activate  # macOS/Linux
pip install -r requirements.txt
cp .env.example .env
# Edit .env con tu ANTHROPIC_API_KEY
python -m uvicorn api:app --reload --port 8000
# Abre frontend.html en navegador
```

### Online (Railway)
Visita: https://tu-app.railway.app

## 🔧 API Endpoints

### POST /analyze
```json
{
  "url": "https://ging.github.io/",
  "detail_level": "full"  // quick, sectors, all
}
```

Response: Perfil + Top 10 + By Sector + Full List

### GET /health
Response: `{"status": "ok"}`

## 📁 Project Structure

```
funding-mvp/
├── fetcher.py       # Web scraping
├── profiler.py      # Claude profile generation
├── sector_mapping.py # 10-sector classification
├── matcher.py       # Ranking engine
├── calls_index.py   # 471 calls indexing
├── api.py           # FastAPI server
├── logger.py        # Structured logging
├── frontend.html    # React UI (all-in-one)
├── calls_index.json # Indexed calls (generated)
├── profiles/        # Cached research profiles
├── logs/            # Application logs
├── requirements.txt
├── .env.example
└── SECURITY_REPORT.md
```

## 🔐 Security

* API key en variables de entorno (no hardcoded)
* CORS configurado
* Error messages sin detalles internos
* Ver SECURITY_REPORT.md para más

## 🚀 Deployment (Railway)

1. Push a GitHub
2. Conecta repo en Railway dashboard
3. Añade secret: ANTHROPIC_API_KEY
4. Deploy automático

Railway ejecuta: `python -m uvicorn api:app --host 0.0.0.0 --port 8080`

## 📊 Example Workflow

1. User introduce: https://ging.github.io/
2. Sistema extrae: perfil de 15 campos
3. Clasifica sector: DIGITAL_TECH (+ secundarios)
4. Rankea: 386 calls → top 10
5. Muestra:
   * Quick View: Top 10 visual
   * By Sector: Top 5 primary + top 3 secundarios
   * Full List: Todas 386 ordenadas
6. User clickea call → detail page con:
   * Todos los detalles
   * Link "Ver documento oficial"
   * Acceso al PDF en Horizon Portal

## 🎯 Next Steps (v1.1)

* [ ] Scraping del PDF para enriquecer datos
* [ ] Dashboard personalizado desde PDF
* [ ] Email alerts para nuevas calls
* [ ] Historial de búsquedas
* [ ] Colaboración entre grupos

## 📝 License
MIT

## 👤 Author
Pedro

## 📧 Support
Issues: GitHub Issues
