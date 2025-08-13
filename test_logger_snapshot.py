# スナップショットテスト - ログフォーマット検証
# AC: ok/err を各2行出力し、フォーマット一致

import json
import sys
import os
from pathlib import Path

# プロジェクトルートをパスに追加
sys.path.append('.')

from app.logger import log_ok, log_err
from app.settings import settings


def test_snapshot_format():
    """スナップショットテスト: ログフォーマット一致確認"""
    
    print("🧪 JSONL ロガー スナップショットテスト開始")
    print("=" * 50)
    
    # 既存のログファイルサイズを記録
    log_file_path = Path(settings.logging.log_file)
    initial_size = log_file_path.stat().st_size if log_file_path.exists() else 0
    
    print(f"📁 ログファイル: {settings.logging.log_file}")
    print(f"📏 初期サイズ: {initial_size} bytes")
    
    # テストケース1: OK ログ（2行）
    print("\n📝 OK ログエントリの生成...")
    log_ok("user_msg", "command-center", "user", "Snapshot test message 1")
    log_ok("auto_tick", "lounge", "spectra", "Snapshot test message 2")
    
    # テストケース2: ERR ログ（2行）
    print("📝 ERR ログエントリの生成...")
    log_err("slash", "creation", "system", "Snapshot test error 1", "slash", "Snapshot error detail 1")
    log_err("plan", "development", "system", "Snapshot test error 2", "plan", "LLM call failed for snapshot test")
    
    # 新しく追加されたログエントリを読み取り
    with open(settings.logging.log_file, 'r', encoding='utf-8') as f:
        f.seek(initial_size)  # 初期サイズから読み始める
        new_lines = f.readlines()
    
    print(f"\n📊 新規生成エントリ数: {len(new_lines)}")
    
    # フォーマット検証
    required_keys = ["ts", "event_type", "channel", "actor", "payload_summary", "result", "error_stage", "error_detail"]
    ok_count = 0
    err_count = 0
    
    for i, line in enumerate(new_lines, 1):
        line = line.strip()
        if not line:
            continue
            
        try:
            # JSON パース
            log_entry = json.loads(line)
            
            # 必須キーの存在確認
            for key in required_keys:
                if key not in log_entry:
                    raise ValueError(f"Missing required key: {key}")
            
            # 結果の検証
            result = log_entry["result"]
            if result not in ["ok", "error"]:
                raise ValueError(f"Invalid result value: {result}")
            
            # OK/ERRの構造検証
            if result == "ok":
                if log_entry["error_stage"] is not None or log_entry["error_detail"] is not None:
                    raise ValueError("OK entry should have null error fields")
                ok_count += 1
            elif result == "error":
                if log_entry["error_stage"] is None or log_entry["error_detail"] is None:
                    raise ValueError("Error entry should have non-null error fields")
                err_count += 1
            
            # タイムスタンプ形式の検証（JST +09:00）
            if not log_entry["ts"].endswith("+09:00"):
                raise ValueError(f"Invalid timezone in timestamp: {log_entry['ts']}")
            
            print(f"✅ エントリ {i}: Valid {result} format")
            
        except (json.JSONDecodeError, ValueError) as e:
            print(f"❌ エントリ {i}: Format error - {e}")
            return False
    
    # カウント検証
    if ok_count != 2:
        print(f"❌ OK エントリ数が不正: expected=2, actual={ok_count}")
        return False
    
    if err_count != 2:
        print(f"❌ ERR エントリ数が不正: expected=2, actual={err_count}")
        return False
    
    print("\n📋 スナップショット結果:")
    print(f"   ✅ OK エントリ: {ok_count}行（期待値: 2行）")
    print(f"   ✅ ERR エントリ: {err_count}行（期待値: 2行）")
    print(f"   ✅ 全エントリがJSONL形式に準拠")
    print(f"   ✅ 全エントリが必須キースキーマに準拠")
    print(f"   ✅ タイムスタンプがJST（+09:00）形式")
    
    return True


if __name__ == "__main__":
    success = test_snapshot_format()
    
    if success:
        print("\n🎉 スナップショットテスト成功: 全フォーマット一致")
        print("AC条件達成: ok/err を各2行出力し、フォーマット一致")
    else:
        print("\n💥 スナップショットテスト失敗: フォーマット不一致")
        sys.exit(1)