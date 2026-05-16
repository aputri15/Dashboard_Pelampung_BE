from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models.transaksi import Transaksi

def extract_month_from_date(date_str):
    if not date_str: return "Unknown"
    return date_str[:7]

def month_key_to_label(month_key):
    bulan_names = {
        "01": "Jan", "02": "Feb", "03": "Mar", "04": "Apr",
        "05": "Mei", "06": "Jun", "07": "Jul", "08": "Agu",
        "09": "Sep", "10": "Okt", "11": "Nov", "12": "Des"
    }
    if not month_key or len(month_key) < 7:
        return month_key or "Unknown"
    mm = month_key.split("-")[1] if "-" in month_key else ""
    return bulan_names.get(mm, month_key)


def calculate_internal_sukabumi(db: Session, kapasitas_ideal: int = 1000):
    """
    Evaluasi Logistik INTERNAL (Sukabumi):
    - Sewa Mobil Rp 800.000/trip per bulan.
    - SELALU menampilkan data 12 bulan penuh (kebal filter bulan).
    - Hanya dipengaruhi oleh slider kapasitas.
    """
    FIXED_COST_SUKABUMI = 800000
    
    q_sukabumi = db.query(
        Transaksi.tanggal_po,
        func.sum(Transaksi.qty).label("volume"),
        func.sum(Transaksi.total_harga).label("revenue")
    ).filter(
        Transaksi.kota.isnot(None),
        func.lower(Transaksi.kota).like("%sukabumi%")
    ).group_by(Transaksi.tanggal_po).all()
    
    sukabumi_monthly = {}
    for row in q_sukabumi:
        qty = row.volume or 0
        revenue = row.revenue or 0
        if qty <= 0: continue
        bln = extract_month_from_date(row.tanggal_po)
        if bln not in sukabumi_monthly:
            sukabumi_monthly[bln] = {"qty": 0, "revenue": 0}
        sukabumi_monthly[bln]["qty"] += qty
        sukabumi_monthly[bln]["revenue"] += revenue

    sukabumi_chart = []
    total_kebocoran_ytd = 0
    
    for bln in sorted(sukabumi_monthly.keys()):
        d = sukabumi_monthly[bln]
        utilization = (d["qty"] / kapasitas_ideal) * 100
        cost_aktual = FIXED_COST_SUKABUMI / d["qty"]
        kebocoran = 0
        if utilization < 100:
            kebocoran = FIXED_COST_SUKABUMI * (1 - (d["qty"] / kapasitas_ideal))
        if kebocoran < 0: kebocoran = 0
        
        avg_harga = d["revenue"] / d["qty"]
        lcr = (cost_aktual / (avg_harga * 1000)) * 100 if avg_harga > 0 else 0
        
        sukabumi_chart.append({
            "bulan": month_key_to_label(bln),
            "utilization": utilization,
            "cost_per_unit": cost_aktual,
            "kebocoran": kebocoran,
            "lcr": lcr
        })
        total_kebocoran_ytd += kebocoran

    return {
        "kpi_kebocoran_ytd": total_kebocoran_ytd,
        "sukabumi_chart": sukabumi_chart
    }


def calculate_eksternal_cod(db: Session, bulan: str = None, kapasitas_ideal: int = 1000):
    """
    Evaluasi Logistik EKSTERNAL (COD Luar Sukabumi):
    - Dipengaruhi oleh filter bulan DAN slider kapasitas.
    - Menghasilkan: KPI Eksternal, Grafik COD, Tabel Gabungan.
    """
    FIXED_COST_SUKABUMI = 800000

    query = db.query(
        Transaksi.tanggal_po,
        Transaksi.wilayah,
        Transaksi.kota,
        func.sum(Transaksi.qty).label("volume"),
        func.sum(Transaksi.total_harga).label("revenue")
    ).filter(Transaksi.kota.isnot(None))
    
    if bulan and bulan != "Semua Bulan":
        query = query.filter(Transaksi.tanggal_po.ilike(f"{bulan}%"))
        
    results = query.group_by(Transaksi.tanggal_po, Transaksi.wilayah, Transaksi.kota).all()
    
    kota_data = {}
    
    for row in results:
        w = row.wilayah or "Lainnya"
        k = row.kota or "Unknown"
        qty = row.volume or 0
        revenue = row.revenue or 0
        
        if qty <= 0: continue
            
        key_kota = f"{w}|{k}"
        if key_kota not in kota_data:
            kota_data[key_kota] = {"qty": 0, "revenue": 0, "is_sukabumi": "sukabumi" in k.lower(), "wilayah": w, "kota": k}
        kota_data[key_kota]["qty"] += qty
        kota_data[key_kota]["revenue"] += revenue

    external_chart = []
    tabel_data = []
    total_lcr_external = 0
    count_external = 0
    rute_termahal = {"kota": "-", "lcr": 0}
    
    for key, d in kota_data.items():
        w = d["wilayah"]
        k = d["kota"]
        qty = d["qty"]
        revenue = d["revenue"]
        avg_harga = revenue / qty
        
        if d["is_sukabumi"]:
            skema = "Sewa Mobil (Owner)"
            cost_per_unit = FIXED_COST_SUKABUMI / qty
            lcr = (cost_per_unit / (avg_harga * 1000)) * 100 if avg_harga > 0 else 0
            utilization = (qty / kapasitas_ideal) * 100
            kebocoran = FIXED_COST_SUKABUMI * (1 - (qty / kapasitas_ideal)) if utilization < 100 else 0
            if kebocoran < 0: kebocoran = 0
            status = "Optimal" if utilization >= 80 else "Under-utilized"
        else:
            skema = "COD (Pelanggan)"
            base_ongkir = 10000 + (len(k) * 2000)
            cost_per_unit = base_ongkir
            lcr = (cost_per_unit / (avg_harga * 1000)) * 100 if avg_harga > 0 else 0
            utilization = 100 
            kebocoran = 0
            status = "Sehat" if lcr <= 15 else ("Rawan" if lcr <= 25 else "Bahaya (Batal Beli)")
            
            external_chart.append({
                "kota": k,
                "qty": qty,
                "lcr": lcr
            })
            
            total_lcr_external += lcr
            count_external += 1
            if lcr > rute_termahal["lcr"]:
                rute_termahal = {"kota": k, "lcr": lcr}
                
        tabel_data.append({
            "wilayah": w,
            "kota": k,
            "skema": skema,
            "qty": qty,
            "kapasitas": kapasitas_ideal if d["is_sukabumi"] else "-",
            "cost_per_unit": cost_per_unit,
            "lcr": lcr,
            "kebocoran": kebocoran,
            "status": status
        })
        
    avg_lcr_external = (total_lcr_external / count_external) if count_external > 0 else 0

    external_chart.sort(key=lambda x: x["qty"], reverse=True)
    external_chart = external_chart[:10]

    tabel_data.sort(key=lambda x: x["lcr"], reverse=True)

    return {
        "kpi": {
            "avg_lcr_external": avg_lcr_external,
            "rute_termahal": rute_termahal["kota"],
            "lcr_rute_termahal": rute_termahal["lcr"]
        },
        "external_chart": external_chart,
        "tabel_data": tabel_data
    }
