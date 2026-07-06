from typing import Any, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.api import deps

from app.crud.analytics_profitabilitas import calculate_regional_profitability
from app.crud.analytics_product_fit import calculate_product_region_fit

from app.crud.analytics_evaluasi_logistik import calculate_internal_sukabumi, calculate_eksternal_cod
from app.models.transaksi import Transaksi

router = APIRouter()

@router.get("/filters")
def get_filter_options(
    db: Session = Depends(deps.get_db),
    current_user = Depends(deps.get_current_user)
) -> Any:
    """Return all distinct filter values for dropdowns (models, months, wilayah, kota)."""
    # Distinct nama_model
    models = db.query(Transaksi.nama_model).distinct().all()
    model_list = sorted([m[0] for m in models if m[0]])
    
    # Distinct months from tanggal_po (format: YYYY-MM)
    dates = db.query(Transaksi.tanggal_po).distinct().all()
    month_set = set()
    for d in dates:
        if d[0] and len(d[0]) >= 7:
            month_set.add(d[0][:7])
    month_list = sorted(month_set)
    
    # Map YYYY-MM to Indonesian month names
    bulan_names = {
        "01": "Januari", "02": "Februari", "03": "Maret", "04": "April",
        "05": "Mei", "06": "Juni", "07": "Juli", "08": "Agustus",
        "09": "September", "10": "Oktober", "11": "November", "12": "Desember"
    }
    months_with_labels = []
    for m in month_list:
        if "-" in m:
            yyyy, mm = m.split("-")[0], m.split("-")[1]
            label = f"{bulan_names.get(mm, mm)} {yyyy}"
        else:
            label = m
        months_with_labels.append({"value": m, "label": label})
    
    # Distinct wilayah
    wilayah = db.query(Transaksi.wilayah).distinct().all()
    wilayah_list = sorted([w[0] for w in wilayah if w[0]])
    
    # Distinct kota
    kota = db.query(Transaksi.kota).distinct().all()
    kota_list = sorted([k[0] for k in kota if k[0]])
    
    return {
        "models": model_list,
        "months": months_with_labels,
        "wilayah": wilayah_list,
        "kota": kota_list
    }

@router.get("/profitabilitas")
def get_regional_profitability(
    db: Session = Depends(deps.get_db),
    bulan: Optional[str] = None,
    current_user = Depends(deps.get_current_user)
) -> Any:
    """Endpoint untuk Chart Profitabilitas Regional."""
    return calculate_regional_profitability(db, bulan)

@router.get("/product-fit")
def get_product_region_fit(
    db: Session = Depends(deps.get_db),
    wilayah: Optional[str] = None,
    bulan: Optional[str] = None,
    current_user = Depends(deps.get_current_user)
) -> Any:
    """Endpoint untuk Chart Product-Region Fit."""
    return calculate_product_region_fit(db, wilayah, bulan=bulan)



@router.get("/evaluasi-logistik/internal")
def get_evaluasi_internal(
    db: Session = Depends(deps.get_db),
    kapasitas: int = Query(100000, ge=1),
    current_user = Depends(deps.get_current_user)
) -> Any:
    """Endpoint Evaluasi Logistik Internal (Sukabumi). Kebal terhadap filter bulan."""
    return calculate_internal_sukabumi(db, kapasitas)

@router.get("/evaluasi-logistik/eksternal")
def get_evaluasi_eksternal(
    db: Session = Depends(deps.get_db),
    bulan: Optional[str] = None,
    kapasitas: int = Query(100000, ge=1),
    current_user = Depends(deps.get_current_user)
) -> Any:
    """Endpoint Evaluasi Logistik Eksternal (KPI COD, Grafik COD, Tabel Gabungan)."""
    return calculate_eksternal_cod(db, bulan, kapasitas)
