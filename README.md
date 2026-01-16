# Dollar Miner

다중 매매 전략을 지원하는 자동 매매 시스템으로, 전략 관리 및 모니터링을 위한 웹 대시보드를 제공합니다.

## 🚀 주요 기능

- 다중 매매 전략
  - VR (Value Rebalancing): 변동성 밴드 기반의 동적 리밸런싱
  - InfBuy (Infinite Buy): 체계적 분할 매수 및 자동 익절
- 웹 대시보드
  - 실시간 시세 모니터링
  - 전략 생성/편집/관리
  - 스냅샷 히스토리 및 주문 추적
  - 대시보드용 인터랙티브 UI
- Discord 연동
  - Webhook: 일일 체결 요약 알림 (매일 오전 7시)
  - Bot: 주식 조회 및 AI 대화 기능
  - Gemini AI 기반 투자 관련 질의응답
- YouTube 연동
  - 투자 관련 채널 RSS 모니터링
  - Gemini AI 기반 동영상 요약
- 브로커 연동
  - 한국투자증권 API 지원 (해외/국내)
  - 확장 가능한 브로커 아키텍처
- 고급 기능
  - 백그라운드 일일 자동 실행
  - 스냅샷 기반 상태 관리
  - 주문 동기화 및 트래킹
  - 휴장/시장 폐장 감지
  - 위험 파라미터 설정 가능

## 🛠️ 기술 스택

- **백엔드**: FastAPI, SQLAlchemy, Alembic, Pydantic
- **프론트엔드**: Bootstrap 5, 순수 JavaScript
- **인프라**: Docker & Docker Compose, SQLite
- **AI**: Google Gemini API
- **Python**: 3.11+

## 📦 빠른 시작 (Quick Start)

### 사전 요구사항
- Docker & Docker Compose
- Git
- 한국투자증권 API 키 ([발급 안내](https://apiportal.koreainvestment.com/))

### 1단계: 저장소 클론
```bash
git clone https://github.com/windexp/trading-project.git
cd trading-project
```

### 2단계: 환경 설정
```bash
# 환경변수 파일 복사
cp .env.example .env

# docker-compose 예제 복사
cp docker-compose.example.yml docker-compose.yml
```

### 3단계: .env 파일 설정
`.env` 파일을 열어 필수 항목을 설정합니다:

```env
# 필수 설정
SECRET_KEY="your_secret_key_here"

# 한국투자증권 API (필수)
ACCOUNTS='[{"name": "계정명", "broker": "KIS", "account_no": "XXXXXXXX-01", "app_key": "your_app_key", "app_secret": "your_app_secret"}]'

# Discord (선택)
DISCORD_WEBHOOK_URL='{"private": "webhook_url"}'
DISCORD_BOT_TOKEN="your_bot_token"
DISCORD_CHANNEL_ID='{"private": "channel_id"}'

# Gemini AI (선택 - 무료)
GEMINI_API_KEY="your_gemini_api_key"
```

### 4단계: 필요 파일/폴더 생성
```bash
# 빈 파일 및 폴더 생성
touch trading.db token_cache.json
mkdir -p logs data/youtube_summaries
```

### 5단계: Docker 네트워크 생성 (선택)
리버스 프록시를 사용하는 경우:
```bash
docker network create proxy_net
```

### 6단계: 컨테이너 실행
```bash
docker compose up -d
```

### 7단계: 접속 확인
- 웹 대시보드: `http://localhost:8000` (또는 설정한 포트)
- 로그 확인: `docker compose logs -f`

## 🐳 Docker 설정 상세

`docker-compose.example.yml`에 다양한 네트워크 구성 옵션이 설명되어 있습니다:

| 옵션 | 설명 | 사용 시나리오 |
|------|------|---------------|
| 포트 직접 노출 | `ports: "8000:8000"` | 단독 실행, 테스트 |
| 외부 네트워크 | `external: true` | Traefik, Nginx Proxy 연동 |
| 내부 네트워크 | `driver: bridge` | 다른 컨테이너와만 통신 |

### 개발 모드 실행
```bash
# docker-compose.yml에서 command를 개발 모드로 변경 후
docker compose up -d
```

## ⚙️ 상세 설정

### 브로커 설정 (ACCOUNTS)
```env
# 해외 주식 계정
{"name": "한투해외", "broker": "KIS", "account_no": "XXXXXXXX-01", ...}

# 국내 주식 계정  
{"name": "한투국내", "broker": "KIS_DOM", "account_no": "XXXXXXXX-01", ...}
```

### Discord 설정
1. [Discord Developer Portal](https://discord.com/developers/applications)에서 봇 생성
2. Bot Token과 Channel ID 획득
3. Webhook URL 생성 (서버 설정 → 연동 → 웹후크)

### Gemini API 설정 (무료)
1. [Google AI Studio](https://aistudio.google.com/app/apikey)에서 API 키 발급
2. `.env`의 `GEMINI_API_KEY`에 설정

## 📖 사용법

### 전략 생성 예시

VR 전략 (Value Rebalancing)
```json
{
  "name": "TQQQ-VR",
  "strategy_code": "VR",
  "account_name": "your_account",
  "base_params": {
    "ticker": "TQQQ",
    "initial_investment": 10000,
    "periodic_investment": 400,
    "buy_limit_rate": 2,
    "sell_limit_rate": 2,
    "g_factor": 13,
    "u_band": 15,
    "l_band": 15,
    "is_advanced": "N"
  }
}
```

InfBuy 전략 (Infinite Buy)
```json
{
  "name": "SOXL-InfBuy",
  "strategy_code": "InfBuy",
  "account_name": "your_account",
  "base_params": {
    "ticker": "SOXL",
    "initial_investment": 10000,
    "division": 20,
    "sell_gain": 20,
    "reinvestment_rate": 50
  }
}
```

### 전략 실행

웹 대시보드:
- 전략 상세에서 "Run Daily Routine" 클릭

API:
```bash
curl -X POST http://localhost:8000/api/v1/strategies/start/TQQQ-VR
```

## 📂 프로젝트 구조

```
trading-project/
├── app/
│   ├── api/v1/endpoints/      # API 엔드포인트
│   │   ├── accounts.py
│   │   ├── strategies.py
│   │   └── youtube.py
│   ├── core/                  # 설정 및 DB 초기화
│   │   ├── config.py
│   │   ├── database.py
│   │   └── init_db.py
│   ├── models/                # DB 모델
│   │   ├── account.py
│   │   ├── enums.py
│   │   └── schema.py
│   ├── services/              # 비즈니스 로직
│   │   ├── broker/            # 브로커 연동
│   │   │   ├── base.py
│   │   │   └── koreainvestment.py
│   │   ├── market_analysis/   # 시장 분석
│   │   │   └── youtube_analyzer.py
│   │   ├── strategies/        # 매매 전략
│   │   │   ├── base.py
│   │   │   ├── vr_strategy.py
│   │   │   └── inf_buy_strategy.py
│   │   ├── discord.py         # Discord Webhook
│   │   ├── discord_bot_service.py  # Discord Bot
│   │   └── scheduler.py       # 스케줄러
│   ├── static/                # 프론트엔드 (HTML/CSS/JS)
│   └── main.py                # 앱 진입점
├── alembic/                   # DB 마이그레이션
├── data/                      # 사용자 데이터
│   └── youtube_summaries/     # YouTube 요약
├── logs/                      # 로그 파일
├── docker-compose.yml
├── docker-compose.example.yml # Docker 설정 예제
├── Dockerfile
├── .env.example               # 환경변수 예제
├── requirements.txt
└── README.md
```

## 🔌 API 엔드포인트 (주요)

- `GET /api/v1/strategies/` - 전략 목록
- `POST /api/v1/strategies/` - 전략 생성
- `GET /api/v1/strategies/{name}` - 전략 상세
- `PUT /api/v1/strategies/{name}` - 전략 수정
- `DELETE /api/v1/strategies/{name}` - 전략 삭제
- `POST /api/v1/strategies/start/{name}` - 전략 실행
- `GET /api/v1/strategies/{name}/price` - 현재 가격 조회
- `POST /api/v1/strategies/{name}/activate` - 활성화
- `POST /api/v1/strategies/{name}/deactivate` - 비활성화

스냅샷 관련:
- `GET /api/v1/strategies/{name}/snapshots`
- `POST /api/v1/strategies/{name}/snapshots`
- `GET /api/v1/strategies/{name}/snapshots/{id}`
- `PUT /api/v1/strategies/{name}/snapshots/{id}`
- `DELETE /api/v1/strategies/{name}/snapshots/{id}`

계정 관련:
- `GET /api/v1/accounts/`
- `POST /api/v1/accounts/`

## 📊 전략 설명

VR (Value Rebalancing)
- 목표 가치(V)를 유지·증가시키며, 상·하단 밴드에 따라 매수/매도
- 주기적 투자(Periodic) 지원
- 고급 모드(Advanced) 옵션 존재

주요 파라미터:
- `g_factor`: V 증가율 제어
- `u_band`/`l_band`: 상/하 밴드 (%)
- `buy_limit_rate`/`sell_limit_rate`: 일별 거래 한도 (%/수량)

InfBuy (Infinite Buy)
- 초기 자금을 여러 단위로 분할하여 점진적 매수
- 목표 이익률에 도달하면 익절
- 이익의 일부를 재투자하여 복리 효과 추구
- 전 포지션 청산 시 전략 상태 리셋

주요 파라미터:
- `division`: 매수 단계 수
- `sell_gain`: 익절 목표(%) 
- `reinvestment_rate`: 이익 재투자 비율(%)

## 🔧 개발 가이드

테스트 실행:
```bash
python scripts/test_api_flow.py
python scripts/test_broker_api.py
```

마이그레이션:
```bash
alembic revision --autogenerate -m "메시지"
alembic upgrade head
alembic downgrade -1
```

브로커 추가 방법:
1. `app/services/broker/`에 새 브로커 클래스 추가
2. `BaseBroker` 상속 및 필수 메서드 구현:
   - `buy_order()`, `sell_order()`
   - `get_price()`, `get_transaction_history()`
   - 응답 파싱 함수들 구현
3. `_get_broker()` 업데이트

## 🚦 상태 및 로드맵

현재 상태: ✅ 운영 가능
- VR 전략 구현 완료
- InfBuy 전략 구현 완료
- 웹 대시보드 동작
- 주문 추적 및 동기화

향후 계획:
- 추가 브로커 연동
- 백테스팅 프레임워크
- 고급 분석·리포팅
- 모바일 앱
- 다중 계정 지원

## 🤝 기여

기여 환영합니다. PR을 열어주세요.

## 📝 라이선스

개인용 프로젝트입니다. 상용 이용 전 저장소 소유자와 협의하세요.

## ⚠️ 면책사항

교육 목적의 소프트웨어입니다. 투자 손실에 대해 책임지지 않으며, 감당할 수 없는 금액으로 거래하지 마십시오.

## 📧 문의

문제나 질문은 GitHub 이슈로 남겨주세요.

---

Built with ❤️ by windexp
