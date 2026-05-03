from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models.transaksi import Transaksi

def calculate_luce(db: Session, model: str = None):
    """
    Rumus LUCE (Logistics Unit Cost Efficiency) & LCR:
    - Menganalisis efisiensi biaya logistik per kota.
    - LCR (%) = (Biaya Logistik per Unit / Harga Jual) * 100
    - Harga Jual Rata-rata = SUM(total_harga) / SUM(qty)
    - MOQ (Minimum Order Quantity) = Asumsi Cost Fixed / (Harga Jual - Modal - Logistik)
    """
    query = db.query(
        Transaksi.kota,
        Transaksi.nama_model,
        func.sum(Transaksi.total_harga).label("revenue"),
        func.sum(Transaksi.qty).label("volume"),
        func.sum(Transaksi.qty * Transaksi.modal_unit).label("cogs")
    ).filter(Transaksi.kota.isnot(None))
    
    if model and model != "Semua Model":
        query = query.filter(Transaksi.nama_model == model)
        
    results = query.group_by(Transaksi.kota, Transaksi.nama_model).all()
    
    # Asumsi fixed cost pengiriman untuk hitung MOQ (misal Rp 800.000 per trip, rata2)
    FIXED_TRIP_COST = 800000 
    
    luce_data = []
    
    for row in results:
        kota = row.kota
        nama_model = row.nama_model
        revenue = row.revenue or 0
        volume = row.volume or 0
        cogs = row.cogs or 0
        
        if volume == 0:
            continue
            
        avg_harga_jual = revenue / volume
        avg_modal = cogs / volume
        
        # Simulasi biaya logistik per kota: kita sesuaikan agar logis dengan harga jual (~Rp 300 - Rp 500)
        # Menggunakan estimasi yang jauh lebih kecil misal Rp 15 - Rp 40 per unit
        biaya_log_per_unit = 15 + (len(kota) * 1) 
        
        lcr = (biaya_log_per_unit / avg_harga_jual * 100) if avg_harga_jual > 0 else 0
        
        profit_per_unit = avg_harga_jual - avg_modal - biaya_log_per_unit
        
        # Asumsi fixed cost disesuaikan dengan profit baru (misal Rp 20.000 per trip untuk perhitungan mock)
        FIXED_TRIP_COST = 20000 
        if profit_per_unit > 0:
            moq = int(FIXED_TRIP_COST / profit_per_unit)
        else:
            moq = 0 # Rugi, tidak ada MOQ yang bisa nutup
            
        luce_data.append({
            "kota": kota,
            "nama_model": nama_model,
            "harga_jual": avg_harga_jual,
            "biaya_log_unit": biaya_log_per_unit,
            "lcr_percent": lcr,
            "min_order": moq,
            "penanggung": "Owner" if lcr < 15 else "Pelanggan" # Contoh rule bisnis
        })
        
    luce_data.sort(key=lambda x: x["lcr_percent"])
    return luce_data
