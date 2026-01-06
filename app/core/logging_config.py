"""
로깅 설정
- 콘솔과 파일에 로그 출력
- 월별 로그 파일 로테이션
- 분리된 로그: trading.log, broker.log, strategy.log
"""
import logging
from logging.handlers import TimedRotatingFileHandler
import os
from pathlib import Path
from datetime import time
import pytz


def setup_logging():
    """로깅 설정을 초기화합니다."""
    
    # 로그 디렉토리 생성
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    # 루트 로거 설정
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    # 기존 핸들러 제거 (중복 방지)
    root_logger.handlers.clear()
    
    # 포맷터 설정 (KST 타임존)
    kst = pytz.timezone('Asia/Seoul')
    
    class KSTFormatter(logging.Formatter):
        def formatTime(self, record, datefmt=None):
            dt = logging.Formatter.converter(record.created)
            from datetime import datetime
            dt_kst = datetime.fromtimestamp(record.created, kst)
            if datefmt:
                return dt_kst.strftime(datefmt)
            return dt_kst.isoformat()
    
    formatter = KSTFormatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # 콘솔 핸들러
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # KST 기준 자정 설정
    kst_midnight = time(0, 0, 0)
    
    # 메인 파일 핸들러 (trading.log - 전체 로그)
    main_handler = TimedRotatingFileHandler(
        filename=log_dir / "trading.log",
        when='midnight',
        interval=1,
        backupCount=31,
        encoding='utf-8',
        atTime=kst_midnight
    )
    main_handler.setLevel(logging.INFO)
    main_handler.setFormatter(formatter)
    main_handler.suffix = "%Y-%m-%d"
    root_logger.addHandler(main_handler)
    
    # Broker 로거 설정
    broker_logger = logging.getLogger('app.services.broker')
    broker_handler = TimedRotatingFileHandler(
        filename=log_dir / "broker.log",
        when='midnight',
        interval=1,
        backupCount=31,
        encoding='utf-8',
        atTime=kst_midnight
    )
    broker_handler.setLevel(logging.INFO)
    broker_handler.setFormatter(formatter)
    broker_handler.suffix = "%Y-%m-%d"
    broker_logger.addHandler(broker_handler)
    
    # Strategy 로거 설정
    strategy_logger = logging.getLogger('app.services.strategies')
    strategy_logger.setLevel(logging.DEBUG)  # 로거 레벨도 DEBUG로 명시
    strategy_logger.propagate = False  # 루트 로거로 전파하지 않음
    strategy_handler = TimedRotatingFileHandler(
        filename=log_dir / "strategy.log",
        when='midnight',
        interval=1,
        backupCount=31,
        encoding='utf-8',
        atTime=kst_midnight
    )
    strategy_handler.setLevel(logging.DEBUG)
    strategy_handler.setFormatter(formatter)
    strategy_handler.suffix = "%Y-%m-%d"
    strategy_logger.addHandler(strategy_handler)
    
    # 특정 로거의 레벨 조정 (선택사항)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('sqlalchemy').setLevel(logging.WARNING)
    logging.getLogger('apscheduler').setLevel(logging.INFO)
    
    logging.info("=" * 80)
    logging.info("Logging system initialized")
    logging.info(f"Main log: {(log_dir / 'trading.log').absolute()}")
    logging.info(f"Broker log: {(log_dir / 'broker.log').absolute()}")
    logging.info(f"Strategy log: {(log_dir / 'strategy.log').absolute()}")
    logging.info(f"Log rotation: Daily, keeping 31 days")
    logging.info("=" * 80)


def get_log_files(limit: int = 100):
    """
    로그 파일 목록을 반환합니다.
    현재 로그 파일을 상단에, 날짜별로 그룹화된 백업 파일들을 하단에 배치합니다.
    
    Args:
        limit: 반환할 최대 파일 개수
        
    Returns:
        List[dict]: 로그 파일 정보 리스트
    """
    log_dir = Path("logs")
    if not log_dir.exists():
        return []
    
    current_logs = []  # 현재 로그 파일 (날짜 없음)
    backup_logs = {}   # 백업 로그 파일 (날짜별로 그룹화)
    
    # 로그 타입 우선순위 (trading > broker > strategy)
    log_type_order = {'trading': 0, 'broker': 1, 'strategy': 2}
    
    for log_file in log_dir.glob("*.log*"):
        stat = log_file.stat()
        file_info = {
            "name": log_file.name,
            "path": str(log_file),
            "size": stat.st_size,
            "modified": stat.st_mtime
        }
        
        # 날짜가 붙은 백업 파일인지 확인 (예: trading.log.2025-12-30)
        # suffixes가 ['.log']만 있으면 현재 로그, ['.log', '.날짜']면 백업 로그
        if len(log_file.suffixes) == 1 and log_file.suffixes[0] == '.log':
            # 현재 로그 파일
            log_type = log_file.stem  # 'trading', 'broker', 'strategy'
            file_info['sort_key'] = log_type_order.get(log_type, 999)
            current_logs.append(file_info)
        else:
            # 백업 로그 파일 - 날짜 추출
            parts = log_file.name.split('.')  # ['trading', 'log', '2025-12-30']
            if len(parts) >= 3:
                log_type = parts[0]  # 'trading'
                date_str = parts[-1]  # '2025-12-30'
                
                if date_str not in backup_logs:
                    backup_logs[date_str] = []
                
                file_info['log_type'] = log_type
                file_info['date'] = date_str
                file_info['sort_key'] = log_type_order.get(log_type, 999)
                backup_logs[date_str].append(file_info)
    
    # 현재 로그: 타입순 정렬 (trading, broker, strategy)
    current_logs.sort(key=lambda x: x.get('sort_key', 999))
    
    # 백업 로그: 날짜별로 정렬하고, 각 날짜 내에서 타입순 정렬
    sorted_backup_logs = []
    for date_str in sorted(backup_logs.keys(), reverse=True):  # 날짜 최신순
        date_group = backup_logs[date_str]
        date_group.sort(key=lambda x: x.get('sort_key', 999))  # 타입순
        sorted_backup_logs.extend(date_group)
    
    # 현재 로그를 상단에, 백업 로그를 하단에 배치
    log_files = current_logs + sorted_backup_logs
    
    return log_files[:limit]


def read_log_file(filename: str, lines: int = 1000):
    """
    로그 파일의 마지막 N줄을 읽습니다.
    
    Args:
        filename: 로그 파일명
        lines: 읽을 줄 수
        
    Returns:
        str: 로그 내용
    """
    log_file = Path("logs") / filename
    
    if not log_file.exists():
        raise FileNotFoundError(f"Log file not found: {filename}")
    
    # 파일이 너무 크면 마지막 N줄만 읽기
    with open(log_file, 'r', encoding='utf-8') as f:
        all_lines = f.readlines()
        return ''.join(all_lines[-lines:])
