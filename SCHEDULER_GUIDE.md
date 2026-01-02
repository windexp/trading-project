# 전략 스케줄러 및 로그 시스템 가이드

## 최근 업데이트

### 개선사항 (2025-12-29)
1. **코드 리팩토링**: `_get_broker` 함수를 공통 유틸리티로 통일
2. **로그 시스템 개선**: 
   - 매일 자정 로그 파일 로테이션
   - 최근 31일간의 로그 자동 보관
   - 파일명에 날짜 추가 (예: `trading.log.2025-12-29`)
3. **로그 뷰어 추가**: 웹 UI에서 로그 파일 조회 가능

## 개요
모든 등록된 활성 전략에 대해 매일 오후 6시(KST)에 자동으로 daily routine을 실행하는 스케줄러가 추가되었습니다.

## 주요 기능

### 1. 자동 스케줄링
- **실행 시간**: 매일 오후 6시 (한국 시간)
- **대상**: `ACTIVE` 상태의 모든 전략
- **자동 시작**: FastAPI 애플리케이션 시작 시 스케줄러가 자동으로 시작됩니다

### 2. 지원하는 전략
- **InfBuy** (무한매수 전략)
- **VR** (가치평균 전략)

### 3. 동작 방식
1. 매일 오후 6시에 스케줄러가 트리거됩니다
2. DB에서 `status = ACTIVE`인 모든 전략을 조회합니다
3. 각 전략에 대해:
   - 해당 계정의 브로커를 초기화합니다
   - 전략 인스턴스를 생성합니다
   - `execute_daily_routine()` 메서드를 실행합니다
4. 하나의 전략이 실패해도 다른 전략은 계속 실행됩니다

## 로그 시스템

### 로그 설정
- **위치**: `logs/trading.log`
- **로테이션**: 매일 자정 (midnight)
- **보관 기간**: 최근 31일
- **파일 형식**: `trading.log`, `trading.log.2025-12-29`, `trading.log.2025-12-28`, ...
- **인코딩**: UTF-8

### 로그 레벨
- **INFO**: 일반 정보 (전략 실행, 주문 등)
- **WARNING**: 경고 (일부 실패, 재시도 등)
- **ERROR**: 에러 (실행 실패, API 오류 등)

### 웹 UI에서 로그 보기

1. **로그 뷰 접근**:
   - 헤더의 "Logs" 버튼 클릭
   
2. **기능**:
   - 로그 파일 목록 조회 (최근 50개)
   - 파일 크기 및 수정 날짜 표시
   - 실시간 로그 내용 조회 (마지막 100/500/1000/5000줄)
   - 줄바꿈 토글
   - 클립보드 복사
   - 로그 파일 다운로드

### API 엔드포인트

#### 로그 파일 목록 조회
```bash
GET /api/v1/logs/files?limit=50
```

**응답 예시:**
```json
[
  {
    "name": "trading.log",
    "path": "logs/trading.log",
    "size": 1048576,
    "modified": 1735459200.0,
    "modified_date": "2025-12-29 18:00:00",
    "size_mb": 1.0
  },
  {
    "name": "trading.log.2025-12-28",
    "path": "logs/trading.log.2025-12-28",
    "size": 2097152,
    "modified": 1735372800.0,
    "modified_date": "2025-12-28 18:00:00",
    "size_mb": 2.0
  }
]
```

#### 로그 내용 조회
```bash
GET /api/v1/logs/content?filename=trading.log&lines=1000
```

**파라미터:**
- `filename`: 로그 파일명 (기본값: `trading.log`)
- `lines`: 읽을 줄 수 (1-10000, 기본값: 1000)

## 코드 구조 개선

### 공통 브로커 유틸리티
`_get_broker` 함수를 공통 모듈로 통합하여 코드 중복을 제거했습니다.

**위치**: `app/services/broker/utils.py`

```python
from app.services.broker.utils import get_broker

# 사용 예시
broker = get_broker(account_name="12345678-01", db=db_session)
```

### 파일 구조
```
app/
├── core/
│   └── logging_config.py          # 로깅 설정 및 유틸리티
├── services/
│   ├── broker/
│   │   └── utils.py               # 공통 브로커 유틸리티
│   └── scheduler.py               # 스케줄러 서비스
├── api/v1/endpoints/
│   ├── logs.py                    # 로그 API
│   └── strategies.py              # 전략 API
└── static/
    └── js/
        └── logs.js                 # 로그 뷰어 JavaScript
```

## API 엔드포인트

## 전략 API 엔드포인트

### 모든 전략 즉시 실행 (테스트용)
```bash
POST /api/v1/strategies/execute-all-daily-routines
```

**응답 예시:**
```json
{
  "message": "All daily routines executed successfully",
  "executed_at": "2025-12-29T18:00:00"
}
```

### 특정 전략 즉시 실행 (테스트용)
```bash
POST /api/v1/strategies/{strategy_name}/execute-routine
```

**응답 예시:**
```json
{
  "message": "Strategy MyStrategy daily routine executed successfully",
  "strategy_name": "MyStrategy",
  "strategy_code": "InfBuy",
  "executed_at": "2025-12-29T18:00:00"
}
```

## 로그 확인

스케줄러는 자세한 로그를 생성합니다:

```
================================================================================
🕐 Starting Daily Strategy Routine - 2025-12-29 18:00:00.000000+09:00
================================================================================
Found 2 active strategy(s)
--------------------------------------------------------------------------------
▶️  Executing strategy: MyInfBuy (InfBuy)
    Account: 12345678-01
--------------------------------------------------------------------------------
🚀 Starting InfBuy Routine for MyInfBuy (SOXL)
  ✓ Current Price: 45.23
...
✅ Strategy MyInfBuy completed successfully
--------------------------------------------------------------------------------
▶️  Executing strategy: MyVR (VR)
    Account: 87654321-01
--------------------------------------------------------------------------------
🚀 Starting VR Routine for MyVR (TQQQ)
  ✓ Current Price: 78.91
...
✅ Strategy MyVR completed successfully
================================================================================
✅ Daily Strategy Routine Completed
================================================================================
```

## 전략 상태 관리

### 전략 활성화
```bash
POST /api/v1/strategies/{strategy_name}/activate
```
전략을 활성화하면 다음 스케줄 실행 시(또는 즉시 실행 시) 포함됩니다.

### 전략 비활성화
```bash
POST /api/v1/strategies/{strategy_name}/deactivate
```
전략을 일시 정지하면 스케줄러가 해당 전략을 건너뜁니다.

## 주의사항

1. **전략 상태**: `ACTIVE` 상태인 전략만 실행됩니다
2. **계정 정보**: 전략에 연결된 계정이 DB에 존재하고 올바른 API 키를 가지고 있어야 합니다
3. **에러 처리**: 한 전략이 실패해도 다른 전략들은 계속 실행됩니다
4. **시간대**: 모든 시간은 한국 시간(KST, Asia/Seoul)을 기준으로 합니다

## 수동 테스트

개발 및 테스트 목적으로 스케줄을 기다리지 않고 즉시 실행할 수 있습니다:

```bash
# 모든 활성 전략 실행
curl -X POST http://localhost:8000/api/v1/strategies/execute-all-daily-routines

# 특정 전략만 실행
curl -X POST http://localhost:8000/api/v1/strategies/MyStrategy/execute-routine
```

## 파일 구조

- `app/services/scheduler.py` - 스케줄러 서비스 구현
- `app/main.py` - 스케줄러 라이프사이클 관리
- `app/api/v1/endpoints/strategies.py` - 수동 실행 API 엔드포인트

## 문제 해결

### 스케줄러가 작동하지 않는 경우
1. 애플리케이션 시작 로그에서 "✅ Strategy scheduler started" 메시지를 확인하세요
2. `apscheduler` 패키지가 설치되어 있는지 확인하세요: `pip install apscheduler>=3.10.0`
3. 로그 파일(`logs/trading.log`)을 확인하여 에러 메시지를 확인하세요

### 특정 전략이 실행되지 않는 경우
1. 전략의 `status`가 `ACTIVE`인지 확인하세요
2. 전략에 연결된 계정이 존재하는지 확인하세요
3. 계정의 API 키가 올바른지 확인하세요

### 로그가 보이지 않는 경우
1. `logs/` 디렉토리가 존재하는지 확인하세요 (자동 생성됨)
2. 파일 쓰기 권한이 있는지 확인하세요
3. 웹 UI에서 로그 뷰로 이동하여 로그 파일 목록을 확인하세요

### 로그 파일이 너무 큰 경우
- 로그는 자동으로 매일 로테이션되며 31일 이상된 파일은 자동 삭제됩니다
- 수동으로 오래된 로그를 삭제하려면: `rm logs/trading.log.2025-11-*`

## 개발자 가이드

### 로그 추가하기
```python
import logging

logger = logging.getLogger(__name__)

# 사용 예시
logger.info("전략 실행 시작")
logger.warning("일부 주문 실패")
logger.error("API 호출 실패", exc_info=True)
```

### 브로커 가져오기
```python
from app.services.broker.utils import get_broker

broker = get_broker(account_name, db)
if not broker:
    logger.error(f"Failed to get broker for {account_name}")
    return
```

### 로그 관련 함수
```python
from app.core.logging_config import get_log_files, read_log_file

# 로그 파일 목록
files = get_log_files(limit=50)

# 로그 내용 읽기
content = read_log_file('trading.log', lines=1000)
```
