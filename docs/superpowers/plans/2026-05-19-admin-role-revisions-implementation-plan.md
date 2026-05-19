# Admin Role Revisions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Mengimplementasikan revisi role admin untuk upload data, kelola data, riwayat log upload, dan manajemen akun sesuai spec desain yang sudah disetujui.

**Architecture:** Backend menjadi sumber kebenaran untuk filter, search, pagination, total count, validasi akun, soft delete log, dan perhitungan `total_harga`. Frontend admin hanya mengirim state UI ke endpoint backend dan merender response yang sudah terstruktur. Perubahan dilakukan incremental dengan test backend terlebih dahulu, lalu wiring UI admin.

**Tech Stack:** FastAPI, SQLAlchemy, SQLite, Alembic, Pydantic, unittest/pytest-compatible tests, Vite, Tailwind CDN, DaisyUI, vanilla JavaScript.

---

## Scope Check

Spec mencakup backend dan frontend admin, tetapi semua perubahan berada dalam satu workflow role admin dan saling bergantung pada kontrak API yang sama. Karena itu plan ini tetap satu dokumen dengan task backend lebih dulu, lalu task frontend.

## File Structure

Backend repo: `C:\Users\ashila pe\Desktop\dashboard_bi_ta\dashboard_pelampung\backend`

- Modify: `app/models/transaksi.py`
  - Menambah field soft delete pada `LogUpload`.
- Modify: `app/schemas/transaksi.py`
  - Menambah schema create manual transaksi, response list log upload, dan response filter options.
- Modify: `app/crud/crud_transaksi.py`
  - Menambah search/filter transaksi, create manual, recompute total, upload blank-row reporting, log filter, dan soft delete.
- Modify: `app/api/v1/endpoints/transaksi.py`
  - Menambah endpoint create manual, filter options, log list response baru, dan soft delete log.
- Modify: `app/crud/crud_user.py`
  - Menambah helper count admin aktif dan conflict detection username/email.
- Modify: `app/api/v1/endpoints/users.py`
  - Menambah duplicate message spesifik, validasi role update, dan guard minimal satu admin aktif.
- Create: `alembic/versions/20260519_0002_add_is_deleted_to_log_upload.py`
  - Migration untuk `log_upload.is_deleted`.
- Modify: `tests/test_excel_upload.py`
  - Mengubah ekspektasi upload dengan blank row.
- Create: `tests/test_admin_role_revisions.py`
  - Test backend untuk transaksi manual, filter transaksi, filter log, soft delete log, dan guard akun admin.
- Modify: `tests/test_migration_files.py`
  - Menambah assertion migration `is_deleted`.

Frontend repo: `C:\Users\ashila pe\Desktop\dashboard_bi_ta\dashboard_pelampung\frontend`

- Modify: `admin/upload.html`
  - Tombol dan modal Tambahkan Data, upload memakai `apiFetch`, feedback blank rows.
- Modify: `admin/kelola.html`
  - Total data dinamis, search field baru, dropdown bulan/tahun/wilayah, reset filter, pagination berdasarkan backend.
- Modify: `admin/log.html`
  - Search nama file, filter bulan/tahun/status, pagination response baru, soft delete log.
- Modify: `admin/akun.html`
  - Toast sukses/gagal, reset form setelah submit, error duplicate spesifik, hilangkan pagination hardcoded.

---

### Task 1: Backend Tests untuk Transaksi Manual dan Filter Kelola Data

**Files:**
- Create: `tests/test_admin_role_revisions.py`
- Modify later: `app/schemas/transaksi.py`
- Modify later: `app/crud/crud_transaksi.py`
- Modify later: `app/api/v1/endpoints/transaksi.py`

- [ ] **Step 1: Tulis test failing untuk create transaksi manual dan total_harga**

Tambahkan file `tests/test_admin_role_revisions.py` dengan fondasi test berikut:

```python
import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.crud import crud_transaksi, crud_user
from app.db.database import Base
from app.models.transaksi import LogUpload, Transaksi
from app.schemas.transaksi import TransaksiManualCreate, TransaksiUpdate
from app.schemas.user import UserCreate, UserUpdate


def make_db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()


def make_transaksi(**overrides):
    data = {
        "nomor_po": "PO-001",
        "tanggal_po": "2026-05-19",
        "id_pelanggan": "C-001",
        "nama_pelanggan": "Toko Rezeki",
        "wilayah": "Jawa",
        "provinsi": "Jawa Barat",
        "kota": "Bandung",
        "id_produk": "P-001",
        "nama_model": "Pelampung A",
        "kategori": "Premium",
        "qty": 2,
        "harga_satuan": 15000,
        "modal_unit": 7000,
    }
    data.update(overrides)
    return data


class AdminRoleRevisionTests(unittest.TestCase):
    def test_create_manual_transaksi_computes_total_harga(self):
        db = make_db()
        transaksi_in = TransaksiManualCreate(**make_transaksi(qty=3, harga_satuan=12500))

        row = crud_transaksi.create_manual_transaksi(db, transaksi_in)

        self.assertEqual(row.total_harga, 37500)
        self.assertEqual(db.query(Transaksi).count(), 1)
```

- [ ] **Step 2: Jalankan test dan pastikan gagal karena schema/function belum ada**

Run:

```powershell
.\venv\Scripts\python.exe -m pytest tests\test_admin_role_revisions.py::AdminRoleRevisionTests::test_create_manual_transaksi_computes_total_harga -v
```

Expected: FAIL dengan pesan import error untuk `TransaksiManualCreate` atau attribute error untuk `create_manual_transaksi`.

- [ ] **Step 3: Tulis test failing untuk update transaksi recompute total_harga**

Tambahkan test ini ke class `AdminRoleRevisionTests`:

```python
    def test_update_transaksi_recomputes_total_harga_when_qty_or_price_changes(self):
        db = make_db()
        row = Transaksi(**make_transaksi(qty=2, harga_satuan=10000, total_harga=20000))
        db.add(row)
        db.commit()
        db.refresh(row)

        updated = crud_transaksi.update_transaksi(
            db,
            db_transaksi=row,
            transaksi_in=TransaksiUpdate(qty=5, harga_satuan=12000),
        )

        self.assertEqual(updated.qty, 5)
        self.assertEqual(updated.harga_satuan, 12000)
        self.assertEqual(updated.total_harga, 60000)
```

- [ ] **Step 4: Jalankan test dan pastikan gagal karena total_harga belum dihitung ulang backend**

Run:

```powershell
.\venv\Scripts\python.exe -m pytest tests\test_admin_role_revisions.py::AdminRoleRevisionTests::test_update_transaksi_recomputes_total_harga_when_qty_or_price_changes -v
```

Expected: FAIL dengan nilai `total_harga` masih `20000` atau tidak sesuai `60000`.

- [ ] **Step 5: Tulis test failing untuk search dan filter Kelola Data**

Tambahkan test ini:

```python
    def test_transaksi_list_combines_search_month_year_and_wilayah_filters(self):
        db = make_db()
        rows = [
            make_transaksi(
                nomor_po="PO-001",
                tanggal_po="2026-05-01",
                nama_pelanggan="Toko Maju",
                wilayah="Jawa",
                kota="Bandung",
                nama_model="Pelampung Super",
                kategori="Premium",
                total_harga=30000,
            ),
            make_transaksi(
                nomor_po="PO-002",
                tanggal_po="2026-06-01",
                nama_pelanggan="Toko Maju",
                wilayah="Jawa",
                kota="Bandung",
                nama_model="Pelampung Super",
                kategori="Premium",
                total_harga=30000,
            ),
            make_transaksi(
                nomor_po="PO-003",
                tanggal_po="2026-05-02",
                nama_pelanggan="Toko Lain",
                wilayah="Sumatera",
                kota="Medan",
                nama_model="Model B",
                kategori="Ekonomis",
                total_harga=30000,
            ),
        ]
        for data in rows:
            db.add(Transaksi(**data))
        db.commit()

        data, total = crud_transaksi.get_transaksi_list(
            db,
            page=1,
            per_page=15,
            search="super",
            wilayah="Jawa",
            bulan="05",
            tahun="2026",
        )

        self.assertEqual(total, 1)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0].nomor_po, "PO-001")
```

- [ ] **Step 6: Jalankan test transaksi baru sebagai failing suite**

Run:

```powershell
.\venv\Scripts\python.exe -m pytest tests\test_admin_role_revisions.py -v
```

Expected: FAIL pada schema/function baru dan filter `tahun` karena belum diimplementasikan.

- [ ] **Step 7: Commit test failing**

```powershell
git add tests\test_admin_role_revisions.py
git commit -m "test: cover admin transaksi revisions"
```

---

### Task 2: Implementasi Backend Transaksi Manual dan Filter Kelola Data

**Files:**
- Modify: `app/schemas/transaksi.py`
- Modify: `app/crud/crud_transaksi.py`
- Modify: `app/api/v1/endpoints/transaksi.py`
- Test: `tests/test_admin_role_revisions.py`

- [ ] **Step 1: Tambahkan schema transaksi manual dan filter options**

Edit `app/schemas/transaksi.py`. Tambahkan class berikut setelah `TransaksiCreate`:

```python
class TransaksiManualCreate(BaseModel):
    nomor_po: str
    tanggal_po: str
    id_pelanggan: str
    nama_pelanggan: str
    wilayah: str
    provinsi: str
    kota: str
    id_produk: str
    nama_model: str
    kategori: str
    qty: int
    harga_satuan: float
    modal_unit: float
```

Tambahkan class berikut di bagian bawah file:

```python
class TransaksiFilterOptionsResponse(BaseModel):
    bulan: List[str]
    tahun: List[str]
    wilayah: List[str]
```

- [ ] **Step 2: Implement helper bulan/tahun dan create manual di CRUD**

Edit `app/crud/crud_transaksi.py`. Ubah signature `get_transaksi_list` menjadi:

```python
def get_transaksi_list(
    db: Session,
    page: int = 1,
    per_page: int = 15,
    search: str = None,
    wilayah: str = None,
    bulan: str = None,
    tahun: str = None,
) -> Tuple[List[Transaksi], int]:
```

Ganti isi search/filter pada function tersebut dengan blok ini:

```python
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                Transaksi.nama_pelanggan.ilike(search_term),
                Transaksi.kategori.ilike(search_term),
                Transaksi.nama_model.ilike(search_term),
                Transaksi.kota.ilike(search_term),
            )
        )

    if wilayah and wilayah != "Semua":
        query = query.filter(Transaksi.wilayah == wilayah)

    if tahun and tahun != "Semua":
        query = query.filter(Transaksi.tanggal_po.like(f"{tahun}-%"))

    if bulan and bulan != "Semua":
        bulan_value = str(bulan).zfill(2)
        query = query.filter(func.substr(Transaksi.tanggal_po, 6, 2) == bulan_value)
```

Tambahkan function baru setelah `create_transaksi`:

```python
def create_manual_transaksi(db: Session, transaksi_in) -> Transaksi:
    data = transaksi_in.model_dump()
    data["total_harga"] = float(data["qty"]) * float(data["harga_satuan"])
    db_transaksi = Transaksi(**data)
    db.add(db_transaksi)
    db.commit()
    db.refresh(db_transaksi)
    return db_transaksi
```

Ubah `update_transaksi` agar menghitung ulang total:

```python
def update_transaksi(db: Session, db_transaksi: Transaksi, transaksi_in: TransaksiUpdate) -> Transaksi:
    update_data = transaksi_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_transaksi, field, value)
    if "qty" in update_data or "harga_satuan" in update_data:
        qty = db_transaksi.qty or 0
        harga_satuan = db_transaksi.harga_satuan or 0
        db_transaksi.total_harga = float(qty) * float(harga_satuan)
    db.add(db_transaksi)
    db.commit()
    db.refresh(db_transaksi)
    return db_transaksi
```

Tambahkan filter options:

```python
def get_transaksi_filter_options(db: Session) -> dict:
    dates = db.query(Transaksi.tanggal_po).distinct().all()
    bulan_set = set()
    tahun_set = set()
    for (tanggal,) in dates:
        if tanggal and len(tanggal) >= 7 and "-" in tanggal:
            tahun_set.add(tanggal[:4])
            bulan_set.add(tanggal[5:7])

    wilayah = db.query(Transaksi.wilayah).distinct().all()
    wilayah_list = sorted([row[0] for row in wilayah if row[0]])

    return {
        "bulan": sorted(bulan_set),
        "tahun": sorted(tahun_set),
        "wilayah": wilayah_list,
    }
```

- [ ] **Step 3: Tambahkan endpoint create manual dan filter options**

Edit import schema di `app/api/v1/endpoints/transaksi.py`:

```python
from app.schemas.transaksi import (
    TransaksiCreate, TransaksiManualCreate, TransaksiUpdate, TransaksiResponse,
    TransaksiListResponse, LogUploadResponse, TransaksiFilterOptionsResponse,
)
```

Tambahkan parameter `tahun` pada `read_transaksi` dan pass ke CRUD:

```python
    tahun: Optional[str] = None,
```

```python
        db, page=page, per_page=per_page, search=search, wilayah=wilayah, bulan=bulan, tahun=tahun
```

Tambahkan endpoint ini sebelum `@router.get("/{transaksi_id}")`:

```python
@router.post("/", response_model=TransaksiResponse)
def create_manual_transaksi(
    transaksi_in: TransaksiManualCreate,
    db: Session = Depends(deps.get_db),
    current_user=Depends(deps.get_current_active_admin),
) -> Any:
    """Create one transaksi row manually from admin Upload Data page."""
    return crud_transaksi.create_manual_transaksi(db, transaksi_in=transaksi_in)


@router.get("/filter-options", response_model=TransaksiFilterOptionsResponse)
def read_transaksi_filter_options(
    db: Session = Depends(deps.get_db),
    current_user=Depends(deps.get_current_active_admin),
) -> Any:
    """Get filter options for admin Kelola Data page."""
    return crud_transaksi.get_transaksi_filter_options(db)
```

- [ ] **Step 4: Jalankan test transaksi dan pastikan pass**

Run:

```powershell
.\venv\Scripts\python.exe -m pytest tests\test_admin_role_revisions.py::AdminRoleRevisionTests::test_create_manual_transaksi_computes_total_harga tests\test_admin_role_revisions.py::AdminRoleRevisionTests::test_update_transaksi_recomputes_total_harga_when_qty_or_price_changes tests\test_admin_role_revisions.py::AdminRoleRevisionTests::test_transaksi_list_combines_search_month_year_and_wilayah_filters -v
```

Expected: 3 PASS.

- [ ] **Step 5: Commit implementasi transaksi**

```powershell
git add app\schemas\transaksi.py app\crud\crud_transaksi.py app\api\v1\endpoints\transaksi.py
git commit -m "feat: add admin transaksi filters and manual create"
```

---

### Task 3: Backend Tests untuk Blank Rows Upload dan Soft Delete Log

**Files:**
- Modify: `tests/test_excel_upload.py`
- Modify: `tests/test_admin_role_revisions.py`
- Modify: `tests/test_migration_files.py`
- Create later: `alembic/versions/20260519_0002_add_is_deleted_to_log_upload.py`
- Modify later: `app/models/transaksi.py`
- Modify later: `app/crud/crud_transaksi.py`
- Modify later: `app/api/v1/endpoints/transaksi.py`

- [ ] **Step 1: Ubah test blank row upload menjadi ekspektasi reporting**

Di `tests/test_excel_upload.py`, ganti isi `test_success_summary_counts_transaction_rows_not_blank_sheet_rows` dengan:

```python
    def test_success_summary_counts_transaction_rows_and_reports_blank_rows(self):
        db = make_db()
        second_row = VALID_ROW.copy()
        second_row[0] = "PO-202501-002"
        blank_row = [None] * len(HEADERS)
        content = make_workbook_bytes([("MASTER2025", [HEADERS, VALID_ROW, blank_row, second_row])])

        result = process_excel_upload(db, content, "blank-tail.xlsx", "admin")

        self.assertTrue(result["success"])
        self.assertEqual(result["total_rows"], 2)
        self.assertEqual(result["processed_rows"], 2)
        self.assertEqual(result["inserted_rows"], 2)
        self.assertEqual(result["skipped_rows"], 1)
        self.assertEqual(result["blank_row_count"], 1)
        self.assertEqual(result["blank_rows"], [3])
        self.assertIn("Baris kosong dilewati: 3", result["message"])
```

- [ ] **Step 2: Tambahkan test soft delete log dan duplicate protection**

Tambahkan test ini ke `AdminRoleRevisionTests`:

```python
    def test_soft_deleted_success_log_is_hidden_but_still_blocks_duplicate_hash(self):
        db = make_db()
        crud_transaksi.create_log_upload(
            db,
            nama_file="dataset.xlsx",
            jumlah_baris=10,
            status="Sukses",
            uploaded_by="admin",
            file_hash="abc123",
        )

        visible_before, total_before = crud_transaksi.get_log_uploads(
            db, page=1, per_page=10, include_deleted=False
        )
        self.assertEqual(total_before, 1)
        self.assertEqual(len(visible_before), 1)

        crud_transaksi.soft_delete_log_upload(db, log_id=visible_before[0].id)

        visible_after, total_after = crud_transaksi.get_log_uploads(
            db, page=1, per_page=10, include_deleted=False
        )
        self.assertEqual(total_after, 0)
        self.assertEqual(visible_after, [])
        self.assertIsNotNone(crud_transaksi.get_successful_upload_by_hash(db, "abc123"))
```

- [ ] **Step 3: Tambahkan test filter log upload**

Tambahkan test ini:

```python
    def test_log_uploads_combine_filename_month_year_and_status_filters(self):
        db = make_db()
        log_a = LogUpload(
            tanggal="2026-05-19 10:00:00",
            nama_file="mei-sukses.xlsx",
            jumlah_baris=5,
            status="Sukses",
            uploaded_by="admin",
            file_hash="hash-a",
        )
        log_b = LogUpload(
            tanggal="2026-06-01 10:00:00",
            nama_file="mei-gagal.xlsx",
            jumlah_baris=0,
            status="Gagal",
            uploaded_by="admin",
            file_hash="hash-b",
        )
        db.add_all([log_a, log_b])
        db.commit()

        logs, total = crud_transaksi.get_log_uploads(
            db,
            page=1,
            per_page=10,
            search="mei",
            bulan="05",
            tahun="2026",
            status="Sukses",
        )

        self.assertEqual(total, 1)
        self.assertEqual(logs[0].nama_file, "mei-sukses.xlsx")
```

- [ ] **Step 4: Tambahkan assertion migration is_deleted**

Di `tests/test_migration_files.py`, tambahkan test berikut:

```python
    def test_alembic_log_upload_soft_delete_migration_is_declared(self):
        versions_dir = ROOT / "alembic" / "versions"
        migrations = list(versions_dir.glob("*add_is_deleted_to_log_upload.py"))
        self.assertEqual(len(migrations), 1)

        migration = migrations[0].read_text(encoding="utf-8")
        self.assertIn("is_deleted", migration)
        self.assertIn("log_upload", migration)
```

- [ ] **Step 5: Jalankan test dan pastikan gagal**

Run:

```powershell
.\venv\Scripts\python.exe -m pytest tests\test_excel_upload.py::ExcelUploadTests::test_success_summary_counts_transaction_rows_and_reports_blank_rows tests\test_admin_role_revisions.py::AdminRoleRevisionTests::test_soft_deleted_success_log_is_hidden_but_still_blocks_duplicate_hash tests\test_admin_role_revisions.py::AdminRoleRevisionTests::test_log_uploads_combine_filename_month_year_and_status_filters tests\test_migration_files.py::MigrationFileTests::test_alembic_log_upload_soft_delete_migration_is_declared -v
```

Expected: FAIL karena response upload belum punya `processed_rows`, log CRUD belum punya pagination/filter/soft delete, dan migration belum ada.

- [ ] **Step 6: Commit test failing**

```powershell
git add tests\test_excel_upload.py tests\test_admin_role_revisions.py tests\test_migration_files.py
git commit -m "test: cover upload blank rows and log soft delete"
```

---

### Task 4: Implementasi Blank Rows Upload, Log Filter, dan Soft Delete Log

**Files:**
- Modify: `app/models/transaksi.py`
- Modify: `app/schemas/transaksi.py`
- Modify: `app/crud/crud_transaksi.py`
- Modify: `app/api/v1/endpoints/transaksi.py`
- Create: `alembic/versions/20260519_0002_add_is_deleted_to_log_upload.py`
- Test: `tests/test_excel_upload.py`
- Test: `tests/test_admin_role_revisions.py`
- Test: `tests/test_migration_files.py`

- [ ] **Step 1: Tambahkan field model is_deleted**

Edit import di `app/models/transaksi.py`:

```python
from sqlalchemy import Column, Integer, String, Float, Text, Boolean
```

Tambahkan field ke class `LogUpload`:

```python
    is_deleted = Column(Boolean(), default=False, nullable=False)
```

- [ ] **Step 2: Tambahkan migration is_deleted**

Buat file `alembic/versions/20260519_0002_add_is_deleted_to_log_upload.py`:

```python
"""add is_deleted to log_upload

Revision ID: 20260519_0002
Revises: 20260518_0001
Create Date: 2026-05-19
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision: str = "20260519_0002"
down_revision: Union[str, None] = "20260518_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(table_name: str) -> bool:
    return inspect(op.get_bind()).has_table(table_name)


def _has_column(table_name: str, column_name: str) -> bool:
    columns = inspect(op.get_bind()).get_columns(table_name)
    return column_name in {column["name"] for column in columns}


def upgrade() -> None:
    if not _has_table("log_upload"):
        return

    if not _has_column("log_upload", "is_deleted"):
        with op.batch_alter_table("log_upload") as batch_op:
            batch_op.add_column(
                sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false())
            )


def downgrade() -> None:
    if not _has_table("log_upload"):
        return

    if _has_column("log_upload", "is_deleted"):
        with op.batch_alter_table("log_upload") as batch_op:
            batch_op.drop_column("is_deleted")
```

- [ ] **Step 3: Tambahkan schema list response log dan filter options log**

Edit `app/schemas/transaksi.py`. Tambahkan setelah `LogUploadResponse`:

```python
class LogUploadListResponse(BaseModel):
    data: List[LogUploadResponse]
    total: int
    page: int
    per_page: int


class LogUploadFilterOptionsResponse(BaseModel):
    bulan: List[str]
    tahun: List[str]
    status: List[str]
```

- [ ] **Step 4: Update ensure log columns**

Di `app/crud/crud_transaksi.py`, ganti nama `ensure_log_upload_file_hash_column` menjadi `ensure_log_upload_columns` dan gunakan isi berikut:

```python
def ensure_log_upload_columns(db: Session) -> None:
    bind = db.get_bind()
    inspector = inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("log_upload")}
    with bind.begin() as connection:
        if "file_hash" not in columns:
            connection.execute(text("ALTER TABLE log_upload ADD COLUMN file_hash VARCHAR"))
        if "is_deleted" not in columns:
            connection.execute(text("ALTER TABLE log_upload ADD COLUMN is_deleted BOOLEAN NOT NULL DEFAULT 0"))
        connection.execute(
            text("CREATE INDEX IF NOT EXISTS ix_log_upload_file_hash ON log_upload (file_hash)")
        )
        connection.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS ux_log_upload_success_file_hash "
                "ON log_upload (file_hash) "
                "WHERE file_hash IS NOT NULL AND status IN ('Sukses', 'Berhasil')"
            )
        )
```

Ganti semua pemanggilan `ensure_log_upload_file_hash_column(db)` menjadi:

```python
ensure_log_upload_columns(db)
```

- [ ] **Step 5: Update get_log_uploads menjadi filterable dan paginated**

Ganti function `get_log_uploads` di `app/crud/crud_transaksi.py` dengan:

```python
def get_log_uploads(
    db: Session,
    page: int = 1,
    per_page: int = 50,
    search: str = None,
    bulan: str = None,
    tahun: str = None,
    status: str = None,
    include_deleted: bool = False,
) -> Tuple[List[LogUpload], int]:
    ensure_log_upload_columns(db)
    query = db.query(LogUpload)

    if not include_deleted:
        query = query.filter(LogUpload.is_deleted == False)  # noqa: E712

    if search:
        query = query.filter(LogUpload.nama_file.ilike(f"%{search}%"))

    if tahun and tahun != "Semua":
        query = query.filter(LogUpload.tanggal.like(f"{tahun}-%"))

    if bulan and bulan != "Semua":
        bulan_value = str(bulan).zfill(2)
        query = query.filter(func.substr(LogUpload.tanggal, 6, 2) == bulan_value)

    if status and status != "Semua":
        query = query.filter(LogUpload.status == status)

    total = query.count()
    skip = (page - 1) * per_page
    logs = query.order_by(LogUpload.id.desc()).offset(skip).limit(per_page).all()
    return logs, total
```

Tambahkan function:

```python
def get_log_upload_filter_options(db: Session) -> dict:
    ensure_log_upload_columns(db)
    rows = db.query(LogUpload.tanggal, LogUpload.status).filter(LogUpload.is_deleted == False).all()  # noqa: E712
    bulan_set = set()
    tahun_set = set()
    status_set = set()
    for tanggal, status in rows:
        if tanggal and len(tanggal) >= 7 and "-" in tanggal:
            tahun_set.add(tanggal[:4])
            bulan_set.add(tanggal[5:7])
        if status:
            status_set.add(status)
    return {
        "bulan": sorted(bulan_set),
        "tahun": sorted(tahun_set),
        "status": sorted(status_set),
    }


def soft_delete_log_upload(db: Session, log_id: int) -> Optional[LogUpload]:
    ensure_log_upload_columns(db)
    log = db.query(LogUpload).filter(LogUpload.id == log_id).first()
    if log:
        log.is_deleted = True
        db.add(log)
        db.commit()
        db.refresh(log)
    return log
```

- [ ] **Step 6: Update blank row reporting pada process_excel_upload**

Di `process_excel_upload`, setelah `blank_row_count = 0`, tambahkan:

```python
        blank_rows = []
```

Saat menemukan baris kosong, ubah blok menjadi:

```python
            if all(_is_empty(value) for value in row_data.values()):
                blank_row_count += 1
                blank_rows.append(row_idx)
                continue
```

Pada semua response sukses, tambahkan:

```python
            "processed_rows": total_data_rows,
            "blank_row_count": blank_row_count,
            "blank_rows": blank_rows,
```

Ganti `message` sukses dengan:

```python
        message = f"Berhasil mengimpor {inserted} dari {total_data_rows} baris."
        if blank_row_count:
            message += f" Baris kosong dilewati: {', '.join(str(row) for row in blank_rows)}."
```

Lalu return sukses memakai:

```python
            "message": message,
```

- [ ] **Step 7: Update endpoint log uploads**

Edit import di `app/api/v1/endpoints/transaksi.py`:

```python
    TransaksiListResponse, LogUploadResponse, LogUploadListResponse,
    LogUploadFilterOptionsResponse, TransaksiFilterOptionsResponse,
```

Ganti endpoint `read_log_uploads`:

```python
@router.get("/log/uploads", response_model=LogUploadListResponse)
def read_log_uploads(
    db: Session = Depends(deps.get_db),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    search: Optional[str] = None,
    bulan: Optional[str] = None,
    tahun: Optional[str] = None,
    status: Optional[str] = None,
    current_user=Depends(deps.get_current_active_admin),
) -> Any:
    """Get paginated upload log entries with filters (admin only)."""
    data, total = crud_transaksi.get_log_uploads(
        db,
        page=page,
        per_page=per_page,
        search=search,
        bulan=bulan,
        tahun=tahun,
        status=status,
    )
    return {"data": data, "total": total, "page": page, "per_page": per_page}
```

Tambahkan endpoint filter options:

```python
@router.get("/log/upload-filter-options", response_model=LogUploadFilterOptionsResponse)
def read_log_upload_filter_options(
    db: Session = Depends(deps.get_db),
    current_user=Depends(deps.get_current_active_admin),
) -> Any:
    """Get filter options for upload log page."""
    return crud_transaksi.get_log_upload_filter_options(db)
```

Ganti delete log:

```python
    log = crud_transaksi.soft_delete_log_upload(db, log_id=log_id)
```

- [ ] **Step 8: Jalankan test upload/log/migration**

Run:

```powershell
.\venv\Scripts\python.exe -m pytest tests\test_excel_upload.py tests\test_admin_role_revisions.py tests\test_migration_files.py -v
```

Expected: PASS untuk test yang sudah ada dan test baru.

- [ ] **Step 9: Commit implementasi upload/log**

```powershell
git add app\models\transaksi.py app\schemas\transaksi.py app\crud\crud_transaksi.py app\api\v1\endpoints\transaksi.py alembic\versions\20260519_0002_add_is_deleted_to_log_upload.py tests\test_excel_upload.py tests\test_admin_role_revisions.py tests\test_migration_files.py
git commit -m "feat: report blank upload rows and soft delete logs"
```

---

### Task 5: Backend Tests untuk Manajemen Akun

**Files:**
- Modify: `tests/test_admin_role_revisions.py`
- Modify later: `app/crud/crud_user.py`
- Modify later: `app/api/v1/endpoints/users.py`

- [ ] **Step 1: Tambahkan helper user pada test**

Tambahkan helper ini ke `tests/test_admin_role_revisions.py` setelah `make_transaksi`:

```python
def create_user(db, username, email, role="admin", is_active=True):
    return crud_user.create_user(
        db,
        UserCreate(
            full_name=username.title(),
            email=email,
            username=username,
            password="secret123",
            role=role,
            is_active=is_active,
        ),
    )
```

- [ ] **Step 2: Tambahkan test conflict username/email**

Tambahkan test ini:

```python
    def test_user_conflict_detection_reports_username_and_email(self):
        db = make_db()
        existing = create_user(db, "admin1", "admin1@example.com", role="admin")

        conflict = crud_user.get_user_conflicts(
            db,
            username="admin1",
            email="admin1@example.com",
            exclude_user_id=None,
        )

        self.assertEqual(conflict, {"username": True, "email": True})

        conflict_excluding_self = crud_user.get_user_conflicts(
            db,
            username="admin1",
            email="admin1@example.com",
            exclude_user_id=existing.id,
        )

        self.assertEqual(conflict_excluding_self, {"username": False, "email": False})
```

- [ ] **Step 3: Tambahkan test guard admin aktif terakhir**

Tambahkan test ini:

```python
    def test_last_active_admin_guard_detects_deactivate_delete_or_demote(self):
        db = make_db()
        admin = create_user(db, "admin1", "admin1@example.com", role="admin", is_active=True)
        owner = create_user(db, "owner1", "owner1@example.com", role="owner", is_active=True)

        self.assertTrue(crud_user.is_last_active_admin(db, admin))
        self.assertFalse(crud_user.is_last_active_admin(db, owner))

        create_user(db, "admin2", "admin2@example.com", role="admin", is_active=True)
        self.assertFalse(crud_user.is_last_active_admin(db, admin))
```

- [ ] **Step 4: Jalankan test dan pastikan gagal**

Run:

```powershell
.\venv\Scripts\python.exe -m pytest tests\test_admin_role_revisions.py::AdminRoleRevisionTests::test_user_conflict_detection_reports_username_and_email tests\test_admin_role_revisions.py::AdminRoleRevisionTests::test_last_active_admin_guard_detects_deactivate_delete_or_demote -v
```

Expected: FAIL karena `get_user_conflicts` dan `is_last_active_admin` belum ada.

- [ ] **Step 5: Commit test failing**

```powershell
git add tests\test_admin_role_revisions.py
git commit -m "test: cover admin account safeguards"
```

---

### Task 6: Implementasi Validasi Manajemen Akun Backend

**Files:**
- Modify: `app/crud/crud_user.py`
- Modify: `app/api/v1/endpoints/users.py`
- Test: `tests/test_admin_role_revisions.py`

- [ ] **Step 1: Tambahkan helper conflict dan last active admin**

Edit `app/crud/crud_user.py`. Tambahkan function berikut setelah `get_user`:

```python
def get_user_conflicts(
    db: Session,
    username: Optional[str],
    email: Optional[str],
    exclude_user_id: Optional[int] = None,
) -> dict:
    query = db.query(User)
    if exclude_user_id is not None:
        query = query.filter(User.id != exclude_user_id)

    username_exists = False
    email_exists = False

    if username:
        username_exists = query.filter(User.username == username).first() is not None

    query = db.query(User)
    if exclude_user_id is not None:
        query = query.filter(User.id != exclude_user_id)

    if email:
        email_exists = query.filter(User.email == email).first() is not None

    return {"username": username_exists, "email": email_exists}


def is_last_active_admin(db: Session, db_user: User) -> bool:
    if db_user.role != "admin" or not db_user.is_active:
        return False
    active_admin_count = (
        db.query(User)
        .filter(User.role == "admin")
        .filter(User.is_active == True)  # noqa: E712
        .count()
    )
    return active_admin_count <= 1
```

- [ ] **Step 2: Tambahkan message formatter di users endpoint**

Edit `app/api/v1/endpoints/users.py`. Tambahkan helper setelah router:

```python
def _duplicate_message(conflicts: dict) -> str:
    if conflicts.get("username") and conflicts.get("email"):
        return "Tidak berhasil, username dan email telah digunakan."
    if conflicts.get("username"):
        return "Tidak berhasil, username telah digunakan."
    if conflicts.get("email"):
        return "Tidak berhasil, email telah digunakan."
    return "Tidak berhasil, data akun telah digunakan."
```

- [ ] **Step 3: Update create_user endpoint**

Ganti isi awal `create_user` di `app/api/v1/endpoints/users.py` dengan:

```python
    conflicts = crud_user.get_user_conflicts(
        db,
        username=user_in.username,
        email=user_in.email,
        exclude_user_id=None,
    )
    if conflicts["username"] or conflicts["email"]:
        raise HTTPException(status_code=400, detail=_duplicate_message(conflicts))
    if user_in.role not in ["admin", "owner"]:
        raise HTTPException(status_code=400, detail="Role hanya boleh admin atau owner.")
```

- [ ] **Step 4: Update update_user endpoint**

Di `update_user`, setelah user ditemukan, tambahkan:

```python
    if user_in.role is not None and user_in.role not in ["admin", "owner"]:
        raise HTTPException(status_code=400, detail="Role hanya boleh admin atau owner.")

    conflicts = crud_user.get_user_conflicts(
        db,
        username=user_in.username,
        email=user_in.email,
        exclude_user_id=user_id,
    )
    if conflicts["username"] or conflicts["email"]:
        raise HTTPException(status_code=400, detail=_duplicate_message(conflicts))

    if crud_user.is_last_active_admin(db, user):
        demoting_last_admin = user_in.role is not None and user_in.role != "admin"
        deactivating_last_admin = user_in.is_active is False
        if demoting_last_admin or deactivating_last_admin:
            raise HTTPException(
                status_code=400,
                detail="Tidak berhasil, sistem harus memiliki minimal satu admin aktif.",
            )
```

Hapus blok lama yang memeriksa username/email satu per satu agar tidak ada pesan ganda yang berbeda format.

- [ ] **Step 5: Update delete_user endpoint**

Di `delete_user`, sebelum `return crud_user.delete_user(...)`, tambahkan:

```python
    if crud_user.is_last_active_admin(db, user):
        raise HTTPException(
            status_code=400,
            detail="Tidak berhasil, sistem harus memiliki minimal satu admin aktif.",
        )
```

- [ ] **Step 6: Jalankan test akun**

Run:

```powershell
.\venv\Scripts\python.exe -m pytest tests\test_admin_role_revisions.py::AdminRoleRevisionTests::test_user_conflict_detection_reports_username_and_email tests\test_admin_role_revisions.py::AdminRoleRevisionTests::test_last_active_admin_guard_detects_deactivate_delete_or_demote -v
```

Expected: PASS.

- [ ] **Step 7: Jalankan full backend test suite**

Run:

```powershell
.\venv\Scripts\python.exe -m pytest tests -v
```

Expected: PASS.

- [ ] **Step 8: Commit implementasi user safeguards**

```powershell
git add app\crud\crud_user.py app\api\v1\endpoints\users.py tests\test_admin_role_revisions.py
git commit -m "feat: harden admin account management"
```

---

### Task 7: Frontend Upload Data - Tambahkan Data dan Blank Row Feedback

**Files:**
- Modify: `C:\Users\ashila pe\Desktop\dashboard_bi_ta\dashboard_pelampung\frontend\admin\upload.html`
- Depends on backend Tasks 2 and 4.

- [ ] **Step 1: Tambahkan tombol Tambahkan Data pada header Upload Data**

Di `admin/upload.html`, ubah header dalam `<div class="mb-8">` menjadi layout flex:

```html
<div class="mb-8 flex flex-col sm:flex-row sm:items-end sm:justify-between gap-4">
  <div>
    <h2 class="text-2xl font-bold text-textMain tracking-tight">Upload Data Transaksi</h2>
    <p class="text-textSub mt-1">Upload file Excel data transaksi bulanan ke sistem database.</p>
  </div>
  <button id="btnOpenManualAdd"
    class="inline-flex items-center justify-center gap-2 px-5 py-2.5 bg-[#4A90D9] text-white rounded-xl hover:brightness-95 shadow-md shadow-[#4A90D9]/20 font-semibold transition-all">
    <i data-lucide="plus" class="w-5 h-5"></i>
    <span>Tambahkan Data</span>
  </button>
</div>
```

- [ ] **Step 2: Tambahkan modal form transaksi manual**

Tambahkan modal ini sebelum `<script>` utama:

```html
<dialog id="modal_manual_add" class="modal modal-bottom sm:modal-middle">
  <div class="modal-box glass-panel p-0 max-w-4xl overflow-hidden">
    <div class="p-6 border-b border-borderMain">
      <h3 class="font-bold text-xl text-textMain">Tambahkan Data Transaksi</h3>
      <p class="text-textSub text-sm mt-1">Masukkan satu baris transaksi yang belum masuk dari dataset.</p>
    </div>
    <form id="manualAddForm" class="p-6 grid grid-cols-1 md:grid-cols-2 gap-4">
      <input id="manual_nomor_po" class="w-full px-3 py-2 bg-bgMain border border-borderMain rounded-lg text-sm" placeholder="Nomor PO" required>
      <input id="manual_tanggal_po" type="date" class="w-full px-3 py-2 bg-bgMain border border-borderMain rounded-lg text-sm" required>
      <input id="manual_id_pelanggan" class="w-full px-3 py-2 bg-bgMain border border-borderMain rounded-lg text-sm" placeholder="ID Pelanggan" required>
      <input id="manual_nama_pelanggan" class="w-full px-3 py-2 bg-bgMain border border-borderMain rounded-lg text-sm" placeholder="Nama Pelanggan" required>
      <input id="manual_wilayah" class="w-full px-3 py-2 bg-bgMain border border-borderMain rounded-lg text-sm" placeholder="Wilayah" required>
      <input id="manual_provinsi" class="w-full px-3 py-2 bg-bgMain border border-borderMain rounded-lg text-sm" placeholder="Provinsi" required>
      <input id="manual_kota" class="w-full px-3 py-2 bg-bgMain border border-borderMain rounded-lg text-sm" placeholder="Kota" required>
      <input id="manual_id_produk" class="w-full px-3 py-2 bg-bgMain border border-borderMain rounded-lg text-sm" placeholder="ID Produk" required>
      <input id="manual_nama_model" class="w-full px-3 py-2 bg-bgMain border border-borderMain rounded-lg text-sm" placeholder="Nama Model" required>
      <input id="manual_kategori" class="w-full px-3 py-2 bg-bgMain border border-borderMain rounded-lg text-sm" placeholder="Kategori" required>
      <input id="manual_qty" type="number" min="1" class="w-full px-3 py-2 bg-bgMain border border-borderMain rounded-lg text-sm" placeholder="Qty" required>
      <input id="manual_harga_satuan" type="number" min="0" class="w-full px-3 py-2 bg-bgMain border border-borderMain rounded-lg text-sm" placeholder="Harga Satuan" required>
      <input id="manual_modal_unit" type="number" min="0" class="w-full px-3 py-2 bg-bgMain border border-borderMain rounded-lg text-sm md:col-span-2" placeholder="Modal Unit" required>
    </form>
    <div class="bg-bgMain/80 p-6 flex justify-end gap-3 border-t border-borderMain">
      <button type="button" id="btnCancelManualAdd" class="btn btn-ghost hover:bg-surface text-textSub px-6 rounded-xl">Batal</button>
      <button type="button" id="btnSubmitManualAdd" class="btn bg-[#4A90D9] text-white border-transparent hover:brightness-95 px-8 rounded-xl">Simpan Data</button>
    </div>
  </div>
  <form method="dialog" class="modal-backdrop">
    <button>Tutup</button>
  </form>
</dialog>
```

- [ ] **Step 3: Tambahkan JS submit manual**

Di script `upload.html`, tambahkan setelah deklarasi `let selectedFile = null;`:

```javascript
    const manualModal = document.getElementById('modal_manual_add');
    const manualForm = document.getElementById('manualAddForm');

    function resetManualForm() {
      manualForm.reset();
    }

    function getManualPayload() {
      return {
        nomor_po: document.getElementById('manual_nomor_po').value.trim(),
        tanggal_po: document.getElementById('manual_tanggal_po').value,
        id_pelanggan: document.getElementById('manual_id_pelanggan').value.trim(),
        nama_pelanggan: document.getElementById('manual_nama_pelanggan').value.trim(),
        wilayah: document.getElementById('manual_wilayah').value.trim(),
        provinsi: document.getElementById('manual_provinsi').value.trim(),
        kota: document.getElementById('manual_kota').value.trim(),
        id_produk: document.getElementById('manual_id_produk').value.trim(),
        nama_model: document.getElementById('manual_nama_model').value.trim(),
        kategori: document.getElementById('manual_kategori').value.trim(),
        qty: parseInt(document.getElementById('manual_qty').value, 10),
        harga_satuan: parseFloat(document.getElementById('manual_harga_satuan').value),
        modal_unit: parseFloat(document.getElementById('manual_modal_unit').value),
      };
    }

    function showUploadResult(type, title, message, lines = []) {
      uploadResult.classList.remove('hidden');
      const isSuccess = type === 'success';
      resultAlert.className = `p-4 rounded-xl border flex items-start gap-3 ${isSuccess ? 'bg-success/10 border-success/20 text-success' : 'bg-danger/10 border-danger/20 text-danger'}`;
      resultIcon.innerHTML = `<i data-lucide="${isSuccess ? 'check-circle' : 'alert-triangle'}" class="w-5 h-5"></i>`;
      resultTitle.textContent = title;
      resultMessage.textContent = message;
      errorList.innerHTML = lines.map(line => `<div>${line}</div>`).join('');
      lucide.createIcons();
    }

    document.getElementById('btnOpenManualAdd').addEventListener('click', () => {
      resetManualForm();
      manualModal.showModal();
    });

    document.getElementById('btnCancelManualAdd').addEventListener('click', () => {
      resetManualForm();
      manualModal.close();
    });

    document.getElementById('btnSubmitManualAdd').addEventListener('click', async () => {
      if (!manualForm.reportValidity()) return;
      const res = await apiFetch('/transaksi/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(getManualPayload())
      });
      if (res && res.ok) {
        resetManualForm();
        manualModal.close();
        showUploadResult('success', 'Data Berhasil Ditambahkan', 'Satu baris transaksi berhasil dimasukkan ke database.');
      } else {
        const err = await res?.json();
        showUploadResult('error', 'Data Gagal Ditambahkan', err?.detail || 'Periksa kembali field transaksi.');
      }
    });
```

- [ ] **Step 4: Ubah upload fetch agar memakai apiFetch**

Ganti blok fetch upload manual:

```javascript
        const token = localStorage.getItem('access_token');
        // We bypass apiFetch here because we need to send FormData without Content-Type header (browser sets it with boundary)
        const res = await fetch('http://127.0.0.1:8000/api/v1/transaksi/upload', {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${token}`
          },
          body: formData
        });
```

dengan:

```javascript
        const res = await apiFetch('/transaksi/upload', {
          method: 'POST',
          body: formData
        });
```

- [ ] **Step 5: Update feedback upload sukses dengan blank rows**

Di blok `if (res.ok && data.success)`, ganti `resultMessage.textContent = data.message;` dengan:

```javascript
          resultMessage.textContent = data.message;

          const detailLines = [];
          if (typeof data.inserted_rows === 'number') detailLines.push(`Data masuk database: ${data.inserted_rows} baris`);
          if (typeof data.processed_rows === 'number') detailLines.push(`Total data diproses: ${data.processed_rows} baris`);
          if (data.blank_row_count > 0) {
            detailLines.push(`Baris kosong dilewati: ${data.blank_row_count} baris`);
            detailLines.push(`Nomor baris kosong: ${data.blank_rows.join(', ')}`);
          }
          errorList.innerHTML = detailLines.map(line => `<div>${line}</div>`).join('');
```

- [ ] **Step 6: Build frontend**

Run dari `C:\Users\ashila pe\Desktop\dashboard_bi_ta\dashboard_pelampung\frontend`:

```powershell
npm run build
```

Expected: build selesai tanpa error Vite.

- [ ] **Step 7: Commit frontend upload**

```powershell
git add admin\upload.html
git commit -m "feat: add manual transaction entry on upload page"
```

---

### Task 8: Frontend Kelola Data - Total, Search, Filter, Pagination

**Files:**
- Modify: `C:\Users\ashila pe\Desktop\dashboard_bi_ta\dashboard_pelampung\frontend\admin\kelola.html`
- Depends on backend Task 2.

- [ ] **Step 1: Tambahkan filter controls dan total summary**

Di `admin/kelola.html`, dalam filter panel, ganti isi `<div class="flex items-center gap-3">` dengan:

```html
<div class="grid grid-cols-1 lg:grid-cols-[1fr_auto_auto_auto_auto] gap-3 items-center">
  <div class="relative">
    <i data-lucide="search" class="w-5 h-5 text-textMuted absolute left-4 top-1/2 -translate-y-1/2"></i>
    <input type="text" id="searchInput" placeholder="Cari pelanggan, kategori, model, kota..."
      class="w-full pl-12 pr-4 py-3 bg-bgMain border border-borderMain rounded-xl text-sm text-textMain focus:ring-2 focus:ring-[#2BAE8E] focus:outline-none transition-all">
  </div>
  <select id="filterBulan" class="px-4 py-3 bg-bgMain border border-borderMain rounded-xl text-sm text-textMain">
    <option value="">Semua Bulan</option>
  </select>
  <select id="filterTahun" class="px-4 py-3 bg-bgMain border border-borderMain rounded-xl text-sm text-textMain">
    <option value="">Semua Tahun</option>
  </select>
  <select id="filterWilayah" class="px-4 py-3 bg-bgMain border border-borderMain rounded-xl text-sm text-textMain">
    <option value="">Semua Wilayah</option>
  </select>
  <button onclick="resetFilters()"
    class="px-4 py-3 rounded-xl border border-borderMain text-textSub hover:bg-bgMain hover:text-textMain transition-colors text-sm font-medium">
    Reset
  </button>
</div>
<div id="totalDataSummary" class="mt-3 text-sm text-textSub">Total: 0 data</div>
```

- [ ] **Step 2: Tambahkan state filter dan formatter bulan**

Di script, setelah `let currentEditId = null;`, tambahkan:

```javascript
    const bulanLabels = {
      '01': 'Januari', '02': 'Februari', '03': 'Maret', '04': 'April',
      '05': 'Mei', '06': 'Juni', '07': 'Juli', '08': 'Agustus',
      '09': 'September', '10': 'Oktober', '11': 'November', '12': 'Desember'
    };
```

- [ ] **Step 3: Tambahkan load filter options**

Tambahkan function sebelum `fetchData()`:

```javascript
    async function loadFilterOptions() {
      const res = await apiFetch('/transaksi/filter-options');
      if (!res || !res.ok) return;
      const options = await res.json();

      const bulanSelect = document.getElementById('filterBulan');
      options.bulan.forEach(bulan => {
        const opt = document.createElement('option');
        opt.value = bulan;
        opt.textContent = bulanLabels[bulan] || bulan;
        bulanSelect.appendChild(opt);
      });

      const tahunSelect = document.getElementById('filterTahun');
      options.tahun.forEach(tahun => {
        const opt = document.createElement('option');
        opt.value = tahun;
        opt.textContent = tahun;
        tahunSelect.appendChild(opt);
      });

      const wilayahSelect = document.getElementById('filterWilayah');
      options.wilayah.forEach(wilayah => {
        const opt = document.createElement('option');
        opt.value = wilayah;
        opt.textContent = wilayah;
        wilayahSelect.appendChild(opt);
      });
    }
```

- [ ] **Step 4: Update URL fetchData**

Dalam `fetchData`, ganti URL construction dengan:

```javascript
      const search = document.getElementById('searchInput').value;
      const bulan = document.getElementById('filterBulan').value;
      const tahun = document.getElementById('filterTahun').value;
      const wilayah = document.getElementById('filterWilayah').value;

      const params = new URLSearchParams({ page: currentPage, per_page: perPage });
      if (search) params.set('search', search);
      if (bulan) params.set('bulan', bulan);
      if (tahun) params.set('tahun', tahun);
      if (wilayah) params.set('wilayah', wilayah);

      const res = await apiFetch(`/transaksi/?${params.toString()}`);
```

Setelah `const { data, total, page } = await res.json();`, tambahkan:

```javascript
      document.getElementById('totalDataSummary').textContent = `Total: ${total.toLocaleString('id-ID')} data`;
```

- [ ] **Step 5: Tambahkan reset dan event listeners filter**

Tambahkan function:

```javascript
    function resetFilters() {
      document.getElementById('searchInput').value = '';
      document.getElementById('filterBulan').value = '';
      document.getElementById('filterTahun').value = '';
      document.getElementById('filterWilayah').value = '';
      currentPage = 1;
      fetchData();
    }
```

Tambahkan listener:

```javascript
    ['filterBulan', 'filterTahun', 'filterWilayah'].forEach(id => {
      document.getElementById(id).addEventListener('change', () => {
        currentPage = 1;
        fetchData();
      });
    });
```

Ubah init dari:

```javascript
    fetchData();
```

menjadi:

```javascript
    loadFilterOptions().then(fetchData);
```

- [ ] **Step 6: Build frontend**

Run:

```powershell
npm run build
```

Expected: build selesai tanpa error Vite.

- [ ] **Step 7: Commit frontend kelola**

```powershell
git add admin\kelola.html
git commit -m "feat: add admin transaksi filters"
```

---

### Task 9: Frontend Riwayat Log Upload - Search, Filter, Pagination, Soft Delete

**Files:**
- Modify: `C:\Users\ashila pe\Desktop\dashboard_bi_ta\dashboard_pelampung\frontend\admin\log.html`
- Depends on backend Task 4.

- [ ] **Step 1: Tambahkan filter controls pada halaman log**

Di `admin/log.html`, setelah header dan sebelum tabel, tambahkan panel:

```html
<div class="glass-panel p-3 sm:p-4 mb-6">
  <div class="grid grid-cols-1 lg:grid-cols-[1fr_auto_auto_auto_auto] gap-3 items-center">
    <div class="relative">
      <i data-lucide="search" class="w-5 h-5 text-textMuted absolute left-4 top-1/2 -translate-y-1/2"></i>
      <input type="text" id="searchLog" placeholder="Cari nama file..."
        class="w-full pl-12 pr-4 py-3 bg-bgMain border border-borderMain rounded-xl text-sm text-textMain focus:ring-2 focus:ring-[#F5821F] focus:outline-none transition-all">
    </div>
    <select id="filterLogBulan" class="px-4 py-3 bg-bgMain border border-borderMain rounded-xl text-sm text-textMain">
      <option value="">Semua Bulan</option>
    </select>
    <select id="filterLogTahun" class="px-4 py-3 bg-bgMain border border-borderMain rounded-xl text-sm text-textMain">
      <option value="">Semua Tahun</option>
    </select>
    <select id="filterLogStatus" class="px-4 py-3 bg-bgMain border border-borderMain rounded-xl text-sm text-textMain">
      <option value="">Semua Status</option>
      <option value="Sukses">Sukses</option>
      <option value="Gagal">Gagal</option>
    </select>
    <button onclick="resetLogFilters()"
      class="px-4 py-3 rounded-xl border border-borderMain text-textSub hover:bg-bgMain hover:text-textMain transition-colors text-sm font-medium">
      Reset
    </button>
  </div>
  <div id="logTotalSummary" class="mt-3 text-sm text-textSub">Total: 0 log</div>
</div>
```

Tambahkan pagination di bawah tabel:

```html
<div class="p-5 border-t border-borderMain flex items-center justify-between text-sm text-textSub bg-bgMain/50">
  <div id="logPaginationInfo">Menampilkan 0 log</div>
  <div class="flex gap-1">
    <button id="btnLogPrev" class="px-3 py-1.5 rounded-lg border border-borderMain text-textSub hover:bg-bgMain transition-all text-sm font-medium">Sebelumnya</button>
    <span id="logPageIndicator" class="px-4 py-1.5 rounded-lg bg-[#F5821F] text-white text-sm font-bold pointer-events-none">1</span>
    <button id="btnLogNext" class="px-3 py-1.5 rounded-lg border border-borderMain text-textSub hover:bg-bgMain transition-all text-sm font-medium">Selanjutnya</button>
  </div>
</div>
```

- [ ] **Step 2: Tambahkan state dan load filter options**

Di script, tambahkan:

```javascript
    let currentLogPage = 1;
    const logsPerPage = 15;
    let logSearchTimer = null;
    const bulanLabels = {
      '01': 'Januari', '02': 'Februari', '03': 'Maret', '04': 'April',
      '05': 'Mei', '06': 'Juni', '07': 'Juli', '08': 'Agustus',
      '09': 'September', '10': 'Oktober', '11': 'November', '12': 'Desember'
    };

    async function loadLogFilterOptions() {
      const res = await apiFetch('/transaksi/log/upload-filter-options');
      if (!res || !res.ok) return;
      const options = await res.json();

      const bulanSelect = document.getElementById('filterLogBulan');
      options.bulan.forEach(bulan => {
        const opt = document.createElement('option');
        opt.value = bulan;
        opt.textContent = bulanLabels[bulan] || bulan;
        bulanSelect.appendChild(opt);
      });

      const tahunSelect = document.getElementById('filterLogTahun');
      options.tahun.forEach(tahun => {
        const opt = document.createElement('option');
        opt.value = tahun;
        opt.textContent = tahun;
        tahunSelect.appendChild(opt);
      });
    }
```

- [ ] **Step 3: Update loadLogs untuk response paginated**

Ganti awal `loadLogs` setelah loading state dengan:

```javascript
      const params = new URLSearchParams({ page: currentLogPage, per_page: logsPerPage });
      const search = document.getElementById('searchLog').value;
      const bulan = document.getElementById('filterLogBulan').value;
      const tahun = document.getElementById('filterLogTahun').value;
      const status = document.getElementById('filterLogStatus').value;
      if (search) params.set('search', search);
      if (bulan) params.set('bulan', bulan);
      if (tahun) params.set('tahun', tahun);
      if (status) params.set('status', status);

      const res = await apiFetch(`/transaksi/log/uploads?${params.toString()}`);
```

Ganti parsing:

```javascript
      const logs = await res.json();
```

dengan:

```javascript
      const payload = await res.json();
      const logs = payload.data;
      const total = payload.total;
      const page = payload.page;

      document.getElementById('logTotalSummary').textContent = `Total: ${total.toLocaleString('id-ID')} log`;
      document.getElementById('logPaginationInfo').innerHTML = `Menampilkan <span class="text-textMain font-medium">${logs.length > 0 ? (page - 1) * logsPerPage + 1 : 0}-${(page - 1) * logsPerPage + logs.length}</span> dari <span class="text-textMain font-medium">${total}</span> log`;
      document.getElementById('logPageIndicator').textContent = page;
      document.getElementById('btnLogPrev').disabled = page <= 1;
      document.getElementById('btnLogNext').disabled = page * logsPerPage >= total;
```

- [ ] **Step 4: Tambahkan reset dan event listeners**

Tambahkan function:

```javascript
    function resetLogFilters() {
      document.getElementById('searchLog').value = '';
      document.getElementById('filterLogBulan').value = '';
      document.getElementById('filterLogTahun').value = '';
      document.getElementById('filterLogStatus').value = '';
      currentLogPage = 1;
      loadLogs();
    }
```

Tambahkan listener sebelum init:

```javascript
    document.getElementById('searchLog').addEventListener('input', () => {
      clearTimeout(logSearchTimer);
      logSearchTimer = setTimeout(() => { currentLogPage = 1; loadLogs(); }, 400);
    });
    ['filterLogBulan', 'filterLogTahun', 'filterLogStatus'].forEach(id => {
      document.getElementById(id).addEventListener('change', () => {
        currentLogPage = 1;
        loadLogs();
      });
    });
    document.getElementById('btnLogPrev').addEventListener('click', () => {
      if (currentLogPage > 1) { currentLogPage--; loadLogs(); }
    });
    document.getElementById('btnLogNext').addEventListener('click', () => {
      currentLogPage++;
      loadLogs();
    });
```

Ubah init:

```javascript
    loadLogFilterOptions().then(loadLogs);
```

- [ ] **Step 5: Build frontend**

Run:

```powershell
npm run build
```

Expected: build selesai tanpa error Vite.

- [ ] **Step 6: Commit frontend log**

```powershell
git add admin\log.html
git commit -m "feat: add upload log filters"
```

---

### Task 10: Frontend Manajemen Akun - Toast Error, Reset Form, Pagination Footer

**Files:**
- Modify: `C:\Users\ashila pe\Desktop\dashboard_bi_ta\dashboard_pelampung\frontend\admin\akun.html`
- Depends on backend Task 6.

- [ ] **Step 1: Ubah showToast agar mendukung tipe sukses/gagal**

Ganti function `showToast(message)` dengan:

```javascript
    function showToast(message, type = 'success') {
      const toast = document.getElementById('toast');
      const toastMessage = document.getElementById('toast-message');
      const panel = toast.querySelector('.glass-panel');
      const iconBox = toast.querySelector('.w-10.h-10');
      const icon = iconBox.querySelector('i');

      const isSuccess = type === 'success';
      toastMessage.textContent = message;
      panel.classList.toggle('border-l-success', isSuccess);
      panel.classList.toggle('border-l-danger', !isSuccess);
      iconBox.className = `w-10 h-10 rounded-full ${isSuccess ? 'bg-success/20 text-success' : 'bg-danger/20 text-danger'} flex items-center justify-center`;
      icon.setAttribute('data-lucide', isSuccess ? 'check' : 'x');

      toast.classList.remove('translate-y-32', 'opacity-0');
      toast.classList.add('translate-y-0', 'opacity-100');
      lucide.createIcons();
      setTimeout(() => {
        toast.classList.remove('translate-y-0', 'opacity-100');
        toast.classList.add('translate-y-32', 'opacity-0');
      }, 4000);
    }
```

- [ ] **Step 2: Reset form tambah akun setelah submit sukses atau gagal**

Di handler `btnCreateUser`, tambahkan helper lokal:

```javascript
      const resetCreateForm = () => {
        inputs.forEach(i => i.value = '');
        const adminRole = box.querySelector('input[name="role_add"][value="admin"]');
        if (adminRole) adminRole.checked = true;
      };
```

Ganti blok sukses menjadi:

```javascript
      if (res && res.ok) {
        modal_tambah.close();
        resetCreateForm();
        showToast('Akun baru berhasil ditambahkan!', 'success');
        loadUsers();
      } else {
        const err = await res?.json();
        resetCreateForm();
        showToast(err?.detail || 'Tidak berhasil, akun gagal ditambahkan.', 'error');
      }
```

- [ ] **Step 3: Update toast error pada edit/delete**

Di blok gagal edit user, ganti:

```javascript
        showToast(err?.detail || 'Gagal menyimpan perubahan');
```

dengan:

```javascript
        showToast(err?.detail || 'Tidak berhasil, perubahan gagal disimpan.', 'error');
```

Di blok sukses edit, pastikan:

```javascript
        showToast('Perubahan profil berhasil disimpan!', 'success');
```

Di blok gagal delete, ganti:

```javascript
        showToast(err?.detail || 'Gagal menghapus akun');
```

dengan:

```javascript
        showToast(err?.detail || 'Tidak berhasil, akun gagal dihapus.', 'error');
```

- [ ] **Step 4: Hapus footer pagination hardcoded**

Ganti seluruh div pagination hardcoded di bawah tabel dengan:

```html
<div class="p-5 border-t border-borderMain text-sm text-textSub bg-bgMain/50">
  <span id="usersCountInfo">Menampilkan 0 pengguna</span>
</div>
```

Di akhir `loadUsers`, setelah render rows dan `lucide.createIcons();`, tambahkan:

```javascript
      document.getElementById('usersCountInfo').textContent = `Menampilkan ${users.length.toLocaleString('id-ID')} pengguna`;
```

Pada kondisi `users.length === 0` sebelum return, tambahkan:

```javascript
        document.getElementById('usersCountInfo').textContent = 'Menampilkan 0 pengguna';
```

- [ ] **Step 5: Build frontend**

Run:

```powershell
npm run build
```

Expected: build selesai tanpa error Vite.

- [ ] **Step 6: Commit frontend akun**

```powershell
git add admin\akun.html
git commit -m "fix: improve admin account feedback"
```

---

### Task 11: Final Verification

**Files:**
- Verify backend repo.
- Verify frontend repo.

- [ ] **Step 1: Jalankan semua test backend**

Run dari backend:

```powershell
.\venv\Scripts\python.exe -m pytest tests -v
```

Expected: semua test PASS.

- [ ] **Step 2: Jalankan build frontend**

Run dari frontend:

```powershell
npm run build
```

Expected: build selesai tanpa error Vite.

- [ ] **Step 3: Cek status Git backend dan frontend**

Run dari backend:

```powershell
git status --short
```

Expected: output kosong.

Run dari frontend:

```powershell
git status --short
```

Expected: output kosong.

- [ ] **Step 4: Manual browser check admin pages**

Start backend:

```powershell
.\venv\Scripts\python.exe -m uvicorn main:app --reload
```

Start frontend:

```powershell
npm run dev -- --host 127.0.0.1 --port 5173
```

Manual check:

- Login admin.
- `admin/upload.html`: upload `.xlsx` dengan satu blank row; response menampilkan blank row; tombol Tambahkan Data membuka modal dan bisa submit satu transaksi.
- `admin/kelola.html`: search pelanggan/kategori/model/kota bekerja; filter bulan/tahun/wilayah bisa digabung; total dan pagination mengikuti filter.
- `admin/log.html`: search nama file bekerja; filter bulan/tahun/status bisa digabung; delete log menyembunyikan row.
- `admin/akun.html`: duplicate username/email memunculkan toast merah; form tambah reset setelah gagal; last active admin tidak bisa dinonaktifkan/didemote/dihapus.

- [ ] **Step 5: Catat hasil verifikasi**

Buat catatan final untuk user berisi:

```text
Backend tests: PASS
Frontend build: PASS
Manual check: halaman yang berhasil dicek
Catatan risiko: jika ada verifikasi manual yang tidak bisa dijalankan
```
