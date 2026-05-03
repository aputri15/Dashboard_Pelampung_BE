from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models.transaksi import Transaksi

def calculate_regional_profitability(db: Session, bulan: str = None):
    """
    Rumus Profitabilitas Regional:
    - Revenue = SUM(total_harga)
    - COGS (Harga Pokok Produksi) = SUM(qty * modal_unit)
    - Estimasi TLC (Total Logistics Cost) per unit: 
      Jawa = 1000, Sumatera = 2500, Kalimantan = 3000, lainnya = 2000
    - Gross Profit = Revenue - COGS - TLC
    - GPM (%) = (Gross Profit / Revenue) * 100
    """
    query = db.query(
        Transaksi.wilayah,
        func.sum(Transaksi.total_harga).label("revenue"),
        func.sum(Transaksi.qty).label("volume"),
        func.sum(Transaksi.qty * Transaksi.modal_unit).label("cogs")
    )
    
    if bulan and bulan != "Semua Bulan":
        # Filter by YYYY-MM format prefix match on tanggal_po
        query = query.filter(Transaksi.tanggal_po.like(f"{bulan}%"))
        
    results = query.group_by(Transaksi.wilayah).all()
    
    data_per_wilayah = []
    total_revenue = 0
    total_tlc = 0
    total_gross_profit = 0
    total_volume = 0
    
    # Biaya logistik estimasi jika tidak ada di DB
    tlc_map = {"Jawa": 1000, "Sumatera": 2500, "Kalimantan": 3000}
    
    for row in results:
        wilayah = row.wilayah or "Lainnya"
        revenue = row.revenue or 0
        volume = row.volume or 0
        cogs = row.cogs or 0
        
        # Hitung TLC
        tlc_per_unit = tlc_map.get(wilayah, 2000)
        tlc = volume * tlc_per_unit
        
        # Hitung Profit
        gross_profit = revenue - cogs - tlc
        gpm = (gross_profit / revenue * 100) if revenue > 0 else 0
        
        data_per_wilayah.append({
            "wilayah": wilayah,
            "revenue": revenue,
            "tlc": tlc,
            "gross_profit": gross_profit,
            "gpm_percent": gpm,
            "volume": volume
        })
        
        total_revenue += revenue
        total_tlc += tlc
        total_gross_profit += gross_profit
        total_volume += volume
        
    avg_gpm = (total_gross_profit / total_revenue * 100) if total_revenue > 0 else 0
    
    # Also compute GPM trend per month (for the GPM trend chart)
    gpm_trend_query = db.query(
        Transaksi.tanggal_po,
        func.sum(Transaksi.total_harga).label("revenue"),
        func.sum(Transaksi.qty).label("volume"),
        func.sum(Transaksi.qty * Transaksi.modal_unit).label("cogs"),
        Transaksi.wilayah
    )
    
    if bulan and bulan != "Semua Bulan":
        gpm_trend_query = gpm_trend_query.filter(Transaksi.tanggal_po.like(f"{bulan}%"))
    
    gpm_trend_results = gpm_trend_query.group_by(Transaksi.tanggal_po, Transaksi.wilayah).all()
    
    # Aggregate by month
    monthly_aggregates = {}
    for row in gpm_trend_results:
        if not row.tanggal_po or len(row.tanggal_po) < 7:
            continue
        month_key = row.tanggal_po[:7]
        if month_key not in monthly_aggregates:
            monthly_aggregates[month_key] = {"revenue": 0, "cogs": 0, "volume": 0, "tlc": 0}
        
        w = row.wilayah or "Lainnya"
        vol = row.volume or 0
        rev = row.revenue or 0
        cogs_val = row.cogs or 0
        tlc_val = vol * tlc_map.get(w, 2000)
        
        monthly_aggregates[month_key]["revenue"] += rev
        monthly_aggregates[month_key]["cogs"] += cogs_val
        monthly_aggregates[month_key]["volume"] += vol
        monthly_aggregates[month_key]["tlc"] += tlc_val
    
    bulan_names = {
        "01": "Jan", "02": "Feb", "03": "Mar", "04": "Apr",
        "05": "Mei", "06": "Jun", "07": "Jul", "08": "Agt",
        "09": "Sep", "10": "Okt", "11": "Nov", "12": "Des"
    }
    
    gpm_trend = []
    for month_key in sorted(monthly_aggregates.keys()):
        agg = monthly_aggregates[month_key]
        profit = agg["revenue"] - agg["cogs"] - agg["tlc"]
        gpm = (profit / agg["revenue"] * 100) if agg["revenue"] > 0 else 0
        mm = month_key.split("-")[1] if "-" in month_key else ""
        label = bulan_names.get(mm, month_key)
        gpm_trend.append({"bulan": label, "gpm": round(gpm, 2)})
    
    # GPM per wilayah for detail cards
    gpm_per_wilayah = {}
    for item in data_per_wilayah:
        gpm_per_wilayah[item["wilayah"]] = round(item["gpm_percent"], 1)
    
    return {
        "kpi": {
            "total_revenue": total_revenue,
            "total_tlc": total_tlc,
            "total_gross_profit": total_gross_profit,
            "avg_gpm_percent": avg_gpm,
            "total_volume": total_volume
        },
        "regional_data": data_per_wilayah,
        "gpm_trend": gpm_trend,
        "gpm_per_wilayah": gpm_per_wilayah
    }
