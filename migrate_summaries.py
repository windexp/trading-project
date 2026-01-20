#!/usr/bin/env python3
"""
YouTube Summary 파일 마이그레이션 스크립트
기존 JSON 파일에서 메타 파일을 생성합니다.
"""

import sys
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from app.services.market_analysis.youtube_summary import get_youtube_summary_service

def main():
    print("=" * 60)
    print("YouTube Summary 파일 마이그레이션")
    print("=" * 60)
    print()
    
    service = get_youtube_summary_service()
    
    print("기존 JSON 파일에서 메타 파일을 생성합니다...")
    print()
    
    migrated = service.migrate_to_meta_files()
    
    print()
    print("=" * 60)
    print(f"✅ 완료: {migrated}개의 메타 파일이 생성되었습니다.")
    print("=" * 60)

if __name__ == "__main__":
    main()
