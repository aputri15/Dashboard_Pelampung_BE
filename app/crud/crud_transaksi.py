from typing import Optional, List, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import or_, func
from app.models.transaksi import Transaksi, LogUpload
from app.schemas.transaksi import TransaksiCreate, TransaksiUpdate
from datetime import datetime
import io

# ==================== TRANSAKSI CRUD ====================

def get_transaksi(db: Session, transaksi_id: int) -> Optional[Transaksi]:
    return db.query(Transaksi).filter(Transaksi.id == transaksi_id).first()

def get_transaksi_list(
    db: Session,
    page: int = 1,
    per_page: int = 15,
    search: str = None,
    wilayah: str = None,
    bulan: str = None,
) -> Tuple[List[Transaksi], int]:
    """Get paginated and filtered transaksi list."""
    query = db.query(Transaksi)

    # Search filter
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                Transaksi.nomor_po.ilike(search_term),
                Transaksi.nama_pelanggan.ilike(search_term),
                Transaksi.nama_model.ilike(search_term),
                Transaksi.kota.ilike(search_term),
                Transaksi.wilayah.ilike(search_term),
            )
        )

    # Wilayah filter
    if wilayah and wilayah != "Semua":
        query = query.filter(Transaksi.wilayah == wilayah)

    # Bulan filter (format: "2025-01")
    if bulan and bulan != "Semua":
        query = query.filter(Transaksi.tanggal_po.like(f"{bulan}%"))

    total = query.count()
    skip = (page - 1) * per_page
    data = query.order_by(Transaksi.id.desc()).offset(skip).limit(per_page).all()

    return data, total

def get_all_wilayah(db: Session) -> List[str]:
    """Get distinct wilayah values for filter dropdown."""
    results = db.query(Transaksi.wilayah).distinct().all()
    return [r[0] for r in results if r[0]]

def create_transaksi(db: Session, transaksi_in: TransaksiCreate) -> Transaksi:
    db_transaksi = Transaksi(**transaksi_in.model_dump())
    db.add(db_transaksi)
    db.commit()
    db.refresh(db_transaksi)
    return db_transaksi

def update_transaksi(db: Session, db_transaksi: Transaksi, transaksi_in: TransaksiUpdate) -> Transaksi:
    update_data = transaksi_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_transaksi, field, value)
    db.add(db_transaksi)
    db.commit()
    db.refresh(db_transaksi)
    return db_transaksi

def delete_transaksi(db: Session, transaksi_id: int) -> Transaksi:
    db_transaksi = db.query(Transaksi).filter(Transaksi.id == transaksi_id).first()
    if db_transaksi:
        db.delete(db_transaksi)
        db.commit()
    return db_transaksi

def delete_all_transaksi(db: Session) -> int:
    """Delete all transaksi records. Returns count of deleted rows."""
    count = db.query(Transaksi).count()
    db.query(Transaksi).delete()
    db.commit()
    return count

def get_transaksi_stats(db: Session) -> dict:
    """Get summary statistics for transaksi data."""
    total_rows = db.query(Transaksi).count()
    total_revenue = db.query(func.sum(Transaksi.total_harga)).scalar() or 0
    total_qty = db.query(func.sum(Transaksi.qty)).scalar() or 0
    unique_customers = db.query(func.count(func.distinct(Transaksi.nama_pelanggan))).scalar() or 0
    return {
        "total_rows": total_rows,
        "total_revenue": total_revenue,
        "total_qty": total_qty,
        "unique_customers": unique_customers,
    }


# ==================== LOG UPLOAD CRUD ====================

def get_log_uploads(db: Session, skip: int = 0, limit: int = 50) -> List[LogUpload]:
    return db.query(LogUpload).order_by(LogUpload.id.desc()).offset(skip).limit(limit).all()

def get_log_upload_count(db: Session) -> int:
    return db.query(LogUpload).count()

def create_log_upload(
    db: Session,
    nama_file: str,
    jumlah_baris: int,
    status: str,
    uploaded_by: str,
) -> LogUpload:
    log = LogUpload(
        tanggal=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        nama_file=nama_file,
        jumlah_baris=jumlah_baris,
        status=status,
        uploaded_by=uploaded_by,
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return log

def delete_log_upload(db: Session, log_id: int) -> Optional[LogUpload]:
    log = db.query(LogUpload).filter(LogUpload.id == log_id).first()
    if log:
        db.delete(log)
        db.commit()
    return log


# ==================== EXCEL UPLOAD PROCESSING ====================

# Column name mapping: expected DB field -> possible Excel header variations
COLUMN_MAP = {
    "nomor_po": ["nomor po", "no po", "nomor_po", "no_po", "po number", "po"],
    "tanggal_po": ["tanggal po", "tanggal_po", "tanggal", "tgl po", "tgl_po", "date"],
    "id_pelanggan": ["id pelanggan", "id_pelanggan", "customer id", "id customer"],
    "nama_pelanggan": ["nama pelanggan", "nama_pelanggan", "pelanggan", "customer", "customer name"],
    "wilayah": ["wilayah", "region", "area"],
    "provinsi": ["provinsi", "province"],
    "kota": ["kota", "city", "kabupaten"],
    "id_produk": ["id produk", "id_produk", "product id", "kode produk"],
    "nama_model": ["nama model", "nama_model", "model", "produk", "product", "nama produk"],
    "kategori": ["kategori", "category", "jenis"],
    "qty": ["qty", "quantity", "jumlah", "kuantitas"],
    "harga_satuan": ["harga satuan", "harga_satuan", "unit price", "harga", "price"],
    "total_harga": ["total harga", "total_harga", "total", "subtotal", "total price"],
    "modal_unit": ["modal unit", "modal_unit", "modal", "cost", "harga modal"],
}

REQUIRED_FIELDS = ["nomor_po", "tanggal_po", "nama_pelanggan", "nama_model", "qty", "harga_satuan", "total_harga", "kota"]

def _match_column(header: str) -> Optional[str]:
    """Match an Excel header to a DB field name using the COLUMN_MAP."""
    header_lower = header.strip().lower()
    for field, aliases in COLUMN_MAP.items():
        if header_lower in aliases:
            return field
    return None

def process_excel_upload(db: Session, file_content: bytes, filename: str, uploaded_by: str) -> dict:
    """
    Parse an uploaded Excel file and insert rows into the transaksi table.
    Returns a dict with status info: { success, total_rows, inserted_rows, errors, message }
    """
    try:
        import openpyxl
    except ImportError:
        return {"success": False, "total_rows": 0, "inserted_rows": 0, "errors": ["openpyxl not installed"], "message": "Server error: openpyxl library not available."}

    try:
        wb = openpyxl.load_workbook(io.BytesIO(file_content), read_only=True, data_only=True)
        
        # Cari sheet yang memuat data transaksi (bukan master data)
        target_ws = None
        
        # Prioritas 1: Cari sheet yang mengandung kata 'MASTER' atau format bulanan
        for sheet_name in wb.sheetnames:
            sn_upper = sheet_name.upper()
            if "MASTER" in sn_upper or "TRANSAKSI" in sn_upper:
                target_ws = wb[sheet_name]
                break
                
        # Prioritas 2: Cek sheet mana yang memiliki header transaksi yang benar
        if not target_ws:
            for sheet_name in wb.sheetnames:
                ws_test = wb[sheet_name]
                # Ambil baris pertama sebagai header
                first_row = next(ws_test.iter_rows(min_row=1, max_row=1, values_only=True), None)
                if not first_row:
                    continue
                # Hitung berapa banyak kolom wajib yang cocok
                matched_required = sum(1 for h in first_row if h and _match_column(str(h)) in REQUIRED_FIELDS)
                if matched_required >= 4: # Jika lebih dari 4 kolom cocok, asumsikan ini sheet transaksi
                    target_ws = ws_test
                    break
        
        # Fallback ke active sheet jika tidak ditemukan
        ws = target_ws if target_ws else wb.active

        rows = list(ws.iter_rows(values_only=True))
        if len(rows) < 2:
            create_log_upload(db, filename, 0, "Gagal", uploaded_by)
            return {"success": False, "total_rows": 0, "inserted_rows": 0, "errors": ["File kosong atau hanya memiliki header."], "message": "File tidak mengandung data."}

        # Map headers
        raw_headers = [str(h).strip() if h else "" for h in rows[0]]
        mapped_headers = {}
        for idx, h in enumerate(raw_headers):
            field = _match_column(h)
            if field:
                mapped_headers[idx] = field

        # Check required fields
        mapped_fields = set(mapped_headers.values())
        missing = [f for f in REQUIRED_FIELDS if f not in mapped_fields]
        if missing:
            create_log_upload(db, filename, 0, "Gagal", uploaded_by)
            return {
                "success": False,
                "total_rows": len(rows) - 1,
                "inserted_rows": 0,
                "errors": [f"Kolom wajib tidak ditemukan: {', '.join(missing)}"],
                "message": f"Kolom wajib tidak ditemukan dalam file.",
            }

        data_rows = rows[1:]
        inserted = 0
        errors = []

        for row_idx, row in enumerate(data_rows, start=2):
            try:
                row_data = {}
                for col_idx, field in mapped_headers.items():
                    val = row[col_idx] if col_idx < len(row) else None
                    row_data[field] = val

                # Type coercion
                for f in ["qty"]:
                    if row_data.get(f) is not None:
                        row_data[f] = int(float(row_data[f]))
                for f in ["harga_satuan", "total_harga", "modal_unit"]:
                    if row_data.get(f) is not None:
                        row_data[f] = float(row_data[f])

                # Convert date to string if needed
                if row_data.get("tanggal_po") and not isinstance(row_data["tanggal_po"], str):
                    row_data["tanggal_po"] = str(row_data["tanggal_po"])

                # Ensure strings
                for f in ["nomor_po", "nama_pelanggan", "nama_model", "wilayah", "provinsi", "kota", "id_pelanggan", "id_produk", "kategori"]:
                    if row_data.get(f) is not None:
                        row_data[f] = str(row_data[f])

                # Validate required
                skip_row = False
                for rf in REQUIRED_FIELDS:
                    if not row_data.get(rf):
                        errors.append(f"Baris {row_idx}: kolom '{rf}' kosong.")
                        skip_row = True
                        break
                if skip_row:
                    continue

                db_transaksi = Transaksi(**{k: v for k, v in row_data.items() if v is not None})
                db.add(db_transaksi)
                inserted += 1

            except Exception as e:
                errors.append(f"Baris {row_idx}: {str(e)}")

        db.commit()
        
        status = "Sukses" if inserted > 0 and len(errors) == 0 else ("Berhasil" if inserted > 0 else "Gagal")
        create_log_upload(db, filename, inserted, status, uploaded_by)

        return {
            "success": inserted > 0,
            "total_rows": len(data_rows),
            "inserted_rows": inserted,
            "errors": errors[:20],  # Limit error messages
            "message": f"Berhasil mengimpor {inserted} dari {len(data_rows)} baris data." if inserted > 0 else "Tidak ada data yang berhasil diimpor.",
        }

    except Exception as e:
        create_log_upload(db, filename, 0, "Gagal", uploaded_by)
        return {"success": False, "total_rows": 0, "inserted_rows": 0, "errors": [str(e)], "message": f"Error saat memproses file: {str(e)}"}
