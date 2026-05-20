from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from sqlalchemy.orm import Session
from app.api import deps
from app.crud import crud_transaksi
from app.schemas.transaksi import (
    TransaksiCreate, TransaksiManualCreate, TransaksiUpdate, TransaksiResponse,
    TransaksiListResponse, LogUploadResponse, TransaksiFilterOptionsResponse,
)

router = APIRouter()


# ==================== TRANSAKSI ENDPOINTS ====================

@router.get("/", response_model=TransaksiListResponse)
def read_transaksi(
    db: Session = Depends(deps.get_db),
    page: int = Query(1, ge=1),
    per_page: int = Query(15, ge=1, le=100),
    search: Optional[str] = None,
    wilayah: Optional[str] = None,
    bulan: Optional[str] = None,
    tahun: Optional[str] = None,
    current_user=Depends(deps.get_current_user),
) -> Any:
    """Get paginated transaksi data with optional search and filters."""
    data, total = crud_transaksi.get_transaksi_list(
        db, page=page, per_page=per_page, search=search, wilayah=wilayah, bulan=bulan, tahun=tahun
    )
    return {"data": data, "total": total, "page": page, "per_page": per_page}


@router.get("/stats")
def get_stats(
    db: Session = Depends(deps.get_db),
    current_user=Depends(deps.get_current_user),
) -> Any:
    """Get summary statistics of transaksi data."""
    return crud_transaksi.get_transaksi_stats(db)


@router.get("/wilayah", response_model=List[str])
def get_wilayah(
    db: Session = Depends(deps.get_db),
    current_user=Depends(deps.get_current_user),
) -> Any:
    """Get distinct wilayah values for filter dropdowns."""
    return crud_transaksi.get_all_wilayah(db)


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


@router.get("/{transaksi_id}", response_model=TransaksiResponse)
def read_transaksi_by_id(
    transaksi_id: int,
    db: Session = Depends(deps.get_db),
    current_user=Depends(deps.get_current_user),
) -> Any:
    """Get a single transaksi by ID."""
    t = crud_transaksi.get_transaksi(db, transaksi_id=transaksi_id)
    if not t:
        raise HTTPException(status_code=404, detail="Transaksi not found")
    return t


@router.put("/{transaksi_id}", response_model=TransaksiResponse)
def update_transaksi(
    transaksi_id: int,
    transaksi_in: TransaksiUpdate,
    db: Session = Depends(deps.get_db),
    current_user=Depends(deps.get_current_active_admin),
) -> Any:
    """Update a transaksi record (admin only)."""
    t = crud_transaksi.get_transaksi(db, transaksi_id=transaksi_id)
    if not t:
        raise HTTPException(status_code=404, detail="Transaksi not found")
    return crud_transaksi.update_transaksi(db, db_transaksi=t, transaksi_in=transaksi_in)


@router.delete("/{transaksi_id}", response_model=TransaksiResponse)
def delete_transaksi(
    transaksi_id: int,
    db: Session = Depends(deps.get_db),
    current_user=Depends(deps.get_current_active_admin),
) -> Any:
    """Delete a single transaksi record (admin only)."""
    t = crud_transaksi.get_transaksi(db, transaksi_id=transaksi_id)
    if not t:
        raise HTTPException(status_code=404, detail="Transaksi not found")
    return crud_transaksi.delete_transaksi(db, transaksi_id=transaksi_id)


@router.delete("/")
def delete_all_transaksi(
    db: Session = Depends(deps.get_db),
    current_user=Depends(deps.get_current_active_admin),
) -> Any:
    """Delete all transaksi records (admin only). Use with caution."""
    count = crud_transaksi.delete_all_transaksi(db)
    return {"message": f"Berhasil menghapus {count} data transaksi.", "deleted_count": count}


# ==================== UPLOAD ENDPOINT ====================

@router.post("/upload")
async def upload_excel(
    file: UploadFile = File(...),
    db: Session = Depends(deps.get_db),
    current_user=Depends(deps.get_current_active_admin),
) -> Any:
    """
    Upload an Excel (.xlsx) file to bulk-insert transaksi data.
    Automatically parses headers, validates, and inserts rows.
    Creates a log entry in log_upload table.
    """
    # Validate file extension
    if not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(status_code=400, detail="Hanya file Excel (.xlsx) yang diizinkan.")

    # Validate file size (max 10MB)
    contents = await file.read()
    if len(contents) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Ukuran file melebihi batas 10MB.")

    result = crud_transaksi.process_excel_upload(
        db=db,
        file_content=contents,
        filename=file.filename,
        uploaded_by=current_user.username,
    )

    status_code = 200 if result["success"] else 422
    return result


# ==================== LOG UPLOAD ENDPOINTS ====================

@router.get("/log/uploads", response_model=List[LogUploadResponse])
def read_log_uploads(
    db: Session = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 50,
    current_user=Depends(deps.get_current_active_admin),
) -> Any:
    """Get all upload log entries (admin only)."""
    return crud_transaksi.get_log_uploads(db, skip=skip, limit=limit)


@router.delete("/log/uploads/{log_id}")
def delete_log_entry(
    log_id: int,
    db: Session = Depends(deps.get_db),
    current_user=Depends(deps.get_current_active_admin),
) -> Any:
    """Delete a specific log entry (admin only)."""
    log = crud_transaksi.delete_log_upload(db, log_id=log_id)
    if not log:
        raise HTTPException(status_code=404, detail="Log not found")
    return {"message": "Log berhasil dihapus."}
