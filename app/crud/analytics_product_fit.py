from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models.transaksi import Transaksi

def calculate_product_region_fit(db: Session, wilayah: str = None, model: str = None, bulan: str = None):
    """
    Rumus Product-Region Fit:
    - Mengidentifikasi produk paling menguntungkan per wilayah.
    - Volume = SUM(qty)
    - Revenue = SUM(total_harga)
    - COGS = SUM(qty * modal_unit)
    - Total Profit = Revenue - COGS - (Estimasi TLC)
    - GPM (%) = (Total Profit / Revenue) * 100
    - Status: Sehat (>30%), Waspada (15%-30%), Bahaya (<15%)
    """
    query = db.query(
        Transaksi.id_produk,
        Transaksi.nama_model,
        Transaksi.kategori,
        Transaksi.wilayah,
        func.sum(Transaksi.qty).label("volume"),
        func.sum(Transaksi.total_harga).label("revenue"),
        func.sum(Transaksi.qty * Transaksi.modal_unit).label("cogs")
    )
    
    if wilayah and wilayah != "Semua Wilayah":
        query = query.filter(Transaksi.wilayah == wilayah)
    if model and model != "Semua Model":
        query = query.filter(Transaksi.nama_model == model)
    if bulan and bulan != "Semua Bulan":
        query = query.filter(Transaksi.tanggal_po.like(f"%{bulan}%"))
        
    results = query.group_by(Transaksi.id_produk, Transaksi.nama_model, Transaksi.kategori, Transaksi.wilayah).all()
    
    tlc_map = {"Jawa": 1000, "Sumatera": 2500, "Kalimantan": 3000}
    
    product_fit_data = []
    
    for row in results:
        w = row.wilayah or "Lainnya"
        revenue = row.revenue or 0
        volume = row.volume or 0
        cogs = row.cogs or 0
        
        tlc_per_unit = tlc_map.get(w, 2000)
        tlc = volume * tlc_per_unit
        
        total_profit = revenue - cogs - tlc
        gpm = (total_profit / revenue * 100) if revenue > 0 else 0
        
        if gpm > 30:
            status = "Sehat"
        elif gpm >= 15:
            status = "Waspada"
        else:
            status = "Bahaya"
            
        product_fit_data.append({
            "id_produk": row.id_produk or "N/A",
            "nama_model": row.nama_model or "Unknown",
            "kategori": row.kategori or "Unknown",
            "wilayah": w,
            "volume": volume,
            "revenue": revenue,
            "total_profit": total_profit,
            "gpm_percent": gpm,
            "status": status
        })
        
    # Urutkan berdasarkan GPM tertinggi
    product_fit_data.sort(key=lambda x: x["gpm_percent"], reverse=True)
    
    return product_fit_data
