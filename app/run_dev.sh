#!/bin/bash

# 스크립트 파일이 위치한 디렉토리의 상위 디렉토리(프로젝트 루트)로 이동
cd "$(dirname "$0")/.."

# 가상환경 활성화
source ~/venvs/trading/bin/activate

# uvicorn으로 app.main:app 실행 (reload 옵션 포함)
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
