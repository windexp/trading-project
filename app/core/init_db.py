import json
from sqlalchemy.orm import Session
from app.core.config import settings
from app.models.account import Account

def init_accounts(db: Session):
    """
    Initialize accounts from environment variables.
    """
    import copy
    import datetime
    try:
        accounts_data = json.loads(settings.ACCOUNTS)
        for acc_data in accounts_data:
            account_no = acc_data.get("account_no")
            if not account_no:
                continue

            # Check if exists
            existing = db.query(Account).filter(Account.account_no == account_no).first()
            if not existing:
                new_account = Account(
                    account_no=account_no,
                    broker=acc_data.get("broker", "KIS"),
                    app_key=acc_data.get("app_key"),
                    app_secret=acc_data.get("app_secret"),
                    account_name=acc_data.get("name", "Default")
                )
                db.add(new_account)
                print(f"✅ Initialized account: {account_no}")
            else:
                # Check for differences (excluding id, created_at, updated_at, is_active)
                diff_fields = []
                backup_data = copy.deepcopy({
                    "account_no": existing.account_no,
                    "account_name": existing.account_name,
                    "app_key": existing.app_key,
                    "app_secret": existing.app_secret,
                    "broker": getattr(existing, "broker", None)
                })
                # Compare and update fields
                for field in ["app_key", "app_secret", "account_name", "broker"]:
                    new_val = acc_data.get(field) if field != "account_name" else acc_data.get("name", "Default")
                    old_val = getattr(existing, field, None)
                    if new_val is not None and new_val != old_val:
                        diff_fields.append(field)
                        setattr(existing, field, new_val)

                # Mask account number for privacy (e.g., 73XXXXXX-01)
                if len(account_no) > 4:
                    masked = account_no[:2] + 'X' * (len(account_no)-4) + account_no[-3:]
                else:
                    masked = account_no

                if diff_fields:
                    # 백업 파일로 저장
                    backup_filename = f"account_backup_{masked}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                    with open(backup_filename, "w", encoding="utf-8") as f:
                        json.dump(backup_data, f, ensure_ascii=False, indent=2)
                    print(f"⚠️ Account {masked} updated fields: {diff_fields}. Previous data backed up to {backup_filename}")
                else:
                    print(f"🔄 No changes for account: {masked}")

        db.commit()
    except json.JSONDecodeError:
        print("⚠️ Failed to parse ACCOUNTS JSON string.")
    except Exception as e:
        print(f"❌ Error initializing accounts: {e}")
