import os
import sys
import time
import json
import zipfile
import hashlib
import sqlite3
import argparse
from pathlib import Path
from datetime import datetime, timezone

BASE_DIR = Path(__file__).resolve().parent.parent
BACKUP_DIR = BASE_DIR / 'backups'

def calculate_sha256(filepath: Path) -> str:
    """Calculates SHA-256 hash of a file for integrity verification."""
    sha256 = hashlib.sha256()
    with open(filepath, 'rb') as f:
        while chunk := f.read(8192):
            sha256.update(chunk)
    return sha256.hexdigest()

def check_sqlite_integrity(db_path: Path) -> bool:
    """Runs SQLite PRAGMA integrity_check to verify database health."""
    if not db_path.exists():
        print(f"[WARNING] Database file {db_path} does not exist for integrity check.")
        return False
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute("PRAGMA integrity_check;")
        res = cursor.fetchone()
        conn.close()
        return res and res[0] == "ok"
    except Exception as e:
        print(f"[ERROR] Database integrity check failed: {str(e)}")
        return False

def create_backup(db_path: Path = None, uploads_dir: Path = None) -> dict:
    """Creates a timestamped backup archive of database and file uploads with integrity checksums."""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    archive_path = BACKUP_DIR / f"backup_{timestamp}.zip"
    manifest_path = BACKUP_DIR / f"backup_{timestamp}.json"

    db_path = db_path or (BASE_DIR / 'instance' / 'vendor_trust.db')
    if not db_path.exists():
        db_path = BASE_DIR / 'instance' / 'vendors.db'
    uploads_dir = uploads_dir or (BASE_DIR / 'uploads')

    print(f"--- Starting Enterprise Backup [{timestamp}] ---")
    
    # 1. Verify Database Integrity before backup
    if db_path.exists() and db_path.suffix == '.db':
        print(f"[1/4] Verifying database integrity ({db_path.name})...")
        if not check_sqlite_integrity(db_path):
            raise RuntimeError("Database integrity check failed prior to backup!")
        print("  -> Database integrity verified: OK")

    # 2. Package Database & Files into ZIP Archive
    print(f"[2/4] Archiving files into {archive_path.name}...")
    archived_files = []
    with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        if db_path.exists():
            zipf.write(db_path, arcname=f"database/{db_path.name}")
            archived_files.append(f"database/{db_path.name}")
            
        if uploads_dir.exists():
            for root, _, files in os.walk(uploads_dir):
                for file in files:
                    file_p = Path(root) / file
                    rel_p = file_p.relative_to(uploads_dir)
                    arc_name = f"uploads/{rel_p}"
                    zipf.write(file_p, arcname=arc_name)
                    archived_files.append(arc_name)

    # 3. Test Archive Integrity
    print("[3/4] Validating ZIP archive structural integrity...")
    with zipfile.ZipFile(archive_path, 'r') as zipf:
        corrupted_file = zipf.testzip()
        if corrupted_file is not None:
            raise RuntimeError(f"Corrupted file detected in backup archive: {corrupted_file}")
    print("  -> Archive structure verified: OK")

    # 4. Generate SHA-256 Checksum Manifest
    print("[4/4] Generating SHA-256 integrity manifest...")
    checksum = calculate_sha256(archive_path)
    manifest = {
        "timestamp": timestamp,
        "backup_archive": archive_path.name,
        "archive_size_bytes": archive_path.stat().st_size,
        "sha256_checksum": checksum,
        "included_files": archived_files,
        "created_at": datetime.now(timezone.utc).isoformat()
    }

    with open(manifest_path, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2)

    print(f"\n[SUCCESS] BACKUP COMPLETED SUCCESSFULLY!")
    print(f"   Archive:  {archive_path}")
    print(f"   Manifest: {manifest_path}")
    print(f"   SHA-256:  {checksum}")
    return manifest

def restore_backup(backup_archive: Path, target_db_dir: Path = None, target_uploads_dir: Path = None) -> bool:
    """Restores database and file uploads from backup archive after validating SHA-256 checksum and structure."""
    if not backup_archive.exists():
        manifest_p = BACKUP_DIR / f"{backup_archive.stem}.json"
        if not backup_archive.is_absolute():
            backup_archive = BACKUP_DIR / backup_archive
    else:
        manifest_p = backup_archive.parent / f"{backup_archive.stem}.json"

    if not backup_archive.exists():
        raise FileNotFoundError(f"Backup archive not found at {backup_archive}")

    print(f"--- Starting Restore Process [{backup_archive.name}] ---")

    # 1. Verify Manifest and SHA-256 Checksum
    if manifest_p.exists():
        print("[1/4] Verifying SHA-256 checksum manifest...")
        with open(manifest_p, 'r', encoding='utf-8') as f:
            manifest = json.load(f)
        current_checksum = calculate_sha256(backup_archive)
        if current_checksum != manifest.get("sha256_checksum"):
            raise ValueError(f"Checksum mismatch! Expected {manifest.get('sha256_checksum')}, got {current_checksum}")
        print("  -> SHA-256 Checksum Verification: PASSED")

    # 2. Test ZIP Integrity
    print("[2/4] Testing ZIP archive structural integrity...")
    with zipfile.ZipFile(backup_archive, 'r') as zipf:
        corrupted = zipf.testzip()
        if corrupted:
            raise RuntimeError(f"Corrupted file detected in archive: {corrupted}")
    print("  -> Archive Structure Verification: PASSED")

    # 3. Extract Files to Target Locations
    target_db_dir = target_db_dir or (BASE_DIR / 'instance')
    target_uploads_dir = target_uploads_dir or (BASE_DIR / 'uploads')
    target_db_dir.mkdir(parents=True, exist_ok=True)
    target_uploads_dir.mkdir(parents=True, exist_ok=True)

    print("[3/4] Restoring database and file uploads...")
    with zipfile.ZipFile(backup_archive, 'r') as zipf:
        for member in zipf.namelist():
            if member.startswith("database/"):
                db_filename = Path(member).name
                dest_path = target_db_dir / db_filename
                with zipf.open(member) as src, open(dest_path, 'wb') as dst:
                    dst.write(src.read())
                print(f"  -> Restored Database: {dest_path}")
            elif member.startswith("uploads/"):
                rel_path = member.replace("uploads/", "", 1)
                if rel_path:
                    dest_path = target_uploads_dir / rel_path
                    dest_path.parent.mkdir(parents=True, exist_ok=True)
                    with zipf.open(member) as src, open(dest_path, 'wb') as dst:
                        dst.write(src.read())

    # 4. Verify Restored Database Health
    print("[4/4] Validating restored database integrity...")
    for db_file in target_db_dir.glob("*.db"):
        if check_sqlite_integrity(db_file):
            print(f"  -> Restored Database Health ({db_file.name}): OK")

    print(f"\n[SUCCESS] RESTORE COMPLETED SUCCESSFULLY from {backup_archive.name}!")
    return True

def verify_backup(backup_archive: Path) -> bool:
    """Verifies SHA-256 checksum and structure of a backup without restoring."""
    if not backup_archive.is_absolute():
        backup_archive = BACKUP_DIR / backup_archive
    manifest_p = backup_archive.parent / f"{backup_archive.stem}.json"
    
    print(f"--- Verifying Backup Archive [{backup_archive.name}] ---")
    if manifest_p.exists():
        with open(manifest_p, 'r', encoding='utf-8') as f:
            manifest = json.load(f)
        current_checksum = calculate_sha256(backup_archive)
        if current_checksum != manifest.get("sha256_checksum"):
            print("[ERROR] Verification FAILED: Checksum mismatch.")
            return False
        print("  -> SHA-256 Checksum: PASSED")
    
    with zipfile.ZipFile(backup_archive, 'r') as zipf:
        if zipf.testzip() is not None:
            print("[ERROR] Verification FAILED: Corrupted ZIP archive.")
            return False
        print("  -> Structural Integrity: PASSED")

    print(f"[SUCCESS] Backup Verification PASSED for {backup_archive.name}!")
    return True

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Centralized Database & Files Backup / Restore Utility")
    parser.add_argument('action', choices=['backup', 'restore', 'verify'], help="Action to execute")
    parser.add_argument('--file', help="Backup zip archive filename for restore or verify action")

    args = parser.parse_args()

    if args.action == 'backup':
        create_backup()
    elif args.action == 'restore':
        if not args.file:
            print("[ERROR] Please specify --file <backup_zip_filename> for restore action.")
            sys.exit(1)
        restore_backup(Path(args.file))
    elif args.action == 'verify':
        if not args.file:
            print("[ERROR] Please specify --file <backup_zip_filename> for verify action.")
            sys.exit(1)
        verify_backup(Path(args.file))
