from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models.transaksi import Transaksi
import re

BULAN_NAMES = {
    "01": "Januari", "02": "Februari", "03": "Maret", "04": "April",
    "05": "Mei", "06": "Juni", "07": "Juli", "08": "Agustus",
    "09": "September", "10": "Oktober", "11": "November", "12": "Desember"
}

def extract_month_from_date(date_str):
    """Extract YYYY-MM from date string."""
    if not date_str: return "Unknown"
    return date_str[:7]  # Asumsi YYYY-MM

def month_key_to_label(month_key):
    """Convert YYYY-MM to readable month name."""
    if not month_key or len(month_key) < 7:
        return month_key or "Unknown"
    mm = month_key.split("-")[1] if "-" in month_key else ""
    return BULAN_NAMES.get(mm, month_key)

def calculate_kebocoran_margin(db: Session, target_kota: str = "Sukabumi", kapasitas_ideal: int = 1000):
    """
    Rumus Kebocoran Margin:
    - Fokus pada pengiriman ke kota tertentu (default Sukabumi).
    - Fixed Cost Owner per trip = Rp 800.000.
    - Qty Aktual = SUM(qty) per bulan.
    - Utilization = (Qty Aktual / Kapasitas Ideal) * 100
    - Cost Aktual per unit = Fixed Cost / Qty Aktual
    - Cost Target per unit = Fixed Cost / Kapasitas Ideal
    - Total Kebocoran = (Cost Aktual - Cost Target) * Qty Aktual
    """
    query = db.query(
        Transaksi.tanggal_po,
        func.sum(Transaksi.qty).label("volume")
    ).filter(Transaksi.kota.ilike(f"%{target_kota}%"))
    
    results = query.group_by(Transaksi.tanggal_po).all()
    
    # Kelompokkan per bulan
    monthly_data = {}
    for row in results:
        bln = extract_month_from_date(row.tanggal_po)
        monthly_data[bln] = monthly_data.get(bln, 0) + (row.volume or 0)
        
    FIXED_COST = 800000
    
    kebocoran_data = []
    total_kebocoran_year = 0
    total_utilization = 0
    max_kebocoran = 0
    bulan_terbesar = "-"
    
    for bln in sorted(monthly_data.keys()):
        qty = monthly_data[bln]
        if qty == 0: continue
            
        utilization = (qty / kapasitas_ideal * 100)
        cost_aktual = FIXED_COST / qty
        cost_target = FIXED_COST / kapasitas_ideal
        
        # Kebocoran terjadi jika cost aktual > cost target (utilization < 100%)
        kebocoran = 0
        if cost_aktual > cost_target:
            kebocoran = (cost_aktual - cost_target) * qty
            
        kebocoran_data.append({
            "bulan": month_key_to_label(bln),
            "bulan_key": bln,
            "qty_aktual": qty,
            "kapasitas_ideal": kapasitas_ideal,
            "utilization": utilization,
            "cost_aktual": cost_aktual,
            "cost_target": cost_target,
            "total_kebocoran": kebocoran
        })
        
        total_kebocoran_year += kebocoran
        total_utilization += utilization
        if kebocoran > max_kebocoran:
            max_kebocoran = kebocoran
            bulan_terbesar = month_key_to_label(bln)
            
    avg_utilization = (total_utilization / len(kebocoran_data)) if kebocoran_data else 0
    
    # Sort by bulan_key (YYYY-MM)
    kebocoran_data.sort(key=lambda x: x["bulan_key"])
    
    return {
        "kpi": {
            "total_kebocoran_tahun": total_kebocoran_year,
            "rata_utilization": avg_utilization,
            "bulan_terbesar": bulan_terbesar
        },
        "monthly_data": kebocoran_data
    }
