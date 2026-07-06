from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models.transaksi import Transaksi
from app.crud.analytics_evaluasi_logistik import build_tlc_map


def calculate_regional_profitability(db: Session, bulan: str = None):
    """
    Rumus Profitabilitas Regional:
    - Revenue = SUM(total_harga)
    - HPP (Harga Pokok Penjualan) = SUM(qty * modal_unit)          [Rumus 3]
    - TLC (Total Landed Cost) per unit: dihitung dari build_tlc_map()
      berdasarkan data riil Master_Logistik + berat produk, BUKAN lagi
      hardcoded {"Jawa": 15, "Sumatera": 30, "Kalimantan": 40, default: 20}.
      Konsisten dengan modul Evaluasi Logistik dan Product-Region Fit.       [Rumus 4]
    - Gross Profit = Revenue - HPP - TLC                                    [Rumus 2/6]
    - GPM (%) = (Gross Profit / Revenue) * 100                              [Rumus 7]
    """
    query = db.query(
        Transaksi.wilayah,
        func.sum(Transaksi.total_harga).label("revenue"),
        func.sum(Transaksi.qty).label("volume"),
        func.sum(Transaksi.qty * Transaksi.modal_unit).label("hpp")
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

    # --- PERBAIKAN: tlc_map sekarang dari data riil, bukan hardcoded ---
    tlc_map = build_tlc_map(db)

    for row in results:
        wilayah = row.wilayah or "Lainnya"
        revenue = row.revenue or 0
        volume = row.volume or 0
        hpp = row.hpp or 0

        # Hitung TLC — fallback pakai __DEFAULT__ (rata-rata tertimbang
        # semua wilayah yang ada datanya), bukan angka 20 yang tanpa dasar.
        tlc_per_unit = tlc_map.get(wilayah, tlc_map.get("__DEFAULT__", 0))
        tlc = volume * tlc_per_unit

        # Hitung Profit
        gross_profit = revenue - hpp - tlc
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
        func.sum(Transaksi.qty * Transaksi.modal_unit).label("hpp"),
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
            monthly_aggregates[month_key] = {"revenue": 0, "hpp": 0, "volume": 0, "tlc": 0}

        w = row.wilayah or "Lainnya"
        vol = row.volume or 0
        rev = row.revenue or 0
        hpp_val = row.hpp or 0
        # --- PERBAIKAN: pakai tlc_map dinamis yang sama, bukan hardcoded ---
        tlc_val = vol * tlc_map.get(w, tlc_map.get("__DEFAULT__", 0))

        monthly_aggregates[month_key]["revenue"] += rev
        monthly_aggregates[month_key]["hpp"] += hpp_val
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
        profit = agg["revenue"] - agg["hpp"] - agg["tlc"]
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