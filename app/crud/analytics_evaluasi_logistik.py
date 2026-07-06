from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models.transaksi import Transaksi

# ============================================================================
# REFERENSI STATIS — DATA MASTER LOGISTIK
# Sumber: spreadsheet Master_Logistik (belum ada tabel tersendiri di database,
# disimpan sebagai konstanta acuan karena keterbatasan waktu integrasi —
# lihat catatan limitasi penelitian di Bab 5).
# ============================================================================
MASTER_LOGISTIK = {
    "Jakarta Barat":  {"satuan": "per_pengiriman", "estimasi_biaya": 150000},
    "Jakarta Pusat":  {"satuan": "per_pengiriman", "estimasi_biaya": 50000},
    "Jakarta Timur":  {"satuan": "per_pengiriman", "estimasi_biaya": 150000},
    "Tanggerang":     {"satuan": "per_pengiriman", "estimasi_biaya": 150000},
    "Bandung":        {"satuan": "per_karung", "estimasi_biaya": 35000},
    "Banjarmasin":    {"satuan": "per_karung", "estimasi_biaya": 100000},
    "Majalengka":     {"satuan": "per_karung", "estimasi_biaya": 60000},
    "Makassar":       {"satuan": "per_karung", "estimasi_biaya": 130000},
    "Lubuk Linggau":  {"satuan": "kosong", "estimasi_biaya": 0},
    "Medan":          {"satuan": "kosong", "estimasi_biaya": 0},
    "Palembang":      {"satuan": "kosong", "estimasi_biaya": 0},
    "Tabalong":       {"satuan": "kosong", "estimasi_biaya": 0},
    # Sukabumi TIDAK dimasukkan -> skema Fixed Cost (owner),
    # dihitung terpisah di calculate_internal_sukabumi().
}

# Referensi berat per produk (gram), dari spreadsheet Master_Produk (105 varian).
# Key = id_produk (Tipe_ID), sama dengan kolom Transaksi.id_produk.
# Dipakai untuk hitung rata-rata berat TERTIMBANG per kota berdasarkan
# produk yang BENAR-BENAR terjual di kota tsb (bukan rata-rata generik).
BERAT_PRODUK_GRAM = {
    # Bulat
    "BK3": 2.40, "BK2": 3.10, "BK1": 4.00, "B00": 5.53, "B01": 7.50, "B02": 9.97,
    "B03": 14.84, "B04": 19.87, "B05": 27.62, "B06": 37.24, "B07": 50.94, "B08": 67.72,
    # Lonjong
    "LK3": 2.41, "LK2": 3.11, "LK1": 4.01, "L00": 5.13, "L01": 6.96, "L02": 9.80,
    "L03": 14.36, "L04": 20.24, "L05": 27.62, "L06": 34.66, "L07": 43.71, "L08": 54.25,
    # Jantung
    "JK3": 2.41, "JK2": 3.11, "JK1": 4.01, "J00": 5.13, "J01": 6.96, "J02": 9.99,
    "J03": 13.89, "J04": 18.78, "J05": 24.43, "J06": 32.85, "J07": 43.05, "J08": 53.45,
    # Gangsing
    "GK3": 2.40, "GK2": 3.40, "GK1": 4.75, "G00": 7.04, "G01": 9.39, "G02": 13.13,
    "G03": 17.85, "G04": 23.65, "G05": 29.03, "G06": 37.04, "G07": 46.45, "G08": 57.38,
    # Telor
    "TK3": 2.40, "TK2": 3.10, "TK1": 4.00, "T00": 5.53, "T01": 7.50, "T02": 9.97,
    "T03": 14.84, "T04": 19.87, "T05": 27.62, "T06": 37.24, "T07": 50.94, "T08": 67.72,
    # Starlet Bulat
    "SB00": 10.06, "SB01": 14.00, "SB02": 18.94, "SB03": 28.69, "SB04": 38.74,
    "SB05": 54.25, "SB06": 73.48, "SB07": 100.88, "SB08": 134.44,
    # Starlet Lonjong
    "SL00": 9.26, "SL01": 12.92, "SL02": 18.61, "SL03": 27.72, "SL04": 39.48,
    "SL05": 54.25, "SL06": 68.33, "SL07": 86.43, "SL08": 107.50,
    # Starlet Jantung
    "SJ00": 9.26, "SJ01": 12.92, "SJ02": 18.97, "SJ03": 26.78, "SJ04": 36.57,
    "SJ05": 47.86, "SJ06": 64.70, "SJ07": 85.10, "SJ08": 105.89,
    # Starlet Gangsing
    "SG00": 13.08, "SG01": 17.77, "SG02": 25.26, "SG03": 34.70, "SG04": 46.30,
    "SG05": 57.06, "SG06": 73.08, "SG07": 91.91, "SG08": 113.75,
    # Starlet Telor
    "ST00": 10.06, "ST01": 14.00, "ST02": 18.94, "ST03": 28.69, "ST04": 38.74,
    "ST05": 54.25, "ST06": 73.48, "ST07": 100.88, "ST08": 134.44,
}

# Fallback kalau ada id_produk yang tidak ditemukan di dictionary di atas
# (misal data baru/typo) -> pakai rata-rata seluruh 105 varian.
AVG_BERAT_PRODUK_GRAM = sum(BERAT_PRODUK_GRAM.values()) / len(BERAT_PRODUK_GRAM)

# Asumsi kapasitas berat 1 karung logistik (dalam gram).
# >>> TODO: konfirmasi angka ini ke owner UMKM sebelum sidang jika sempat.
#     Jika tidak sempat, sebutkan sebagai asumsi di metodologi. <<<
KAPASITAS_KARUNG_GRAM = 30000  # asumsi 30 kg

FIXED_COST_SUKABUMI = 800000


def extract_month_from_date(date_str):
    if not date_str:
        return "Unknown"
    return date_str[:7]


def month_key_to_label(month_key):
    bulan_names = {
        "01": "Jan", "02": "Feb", "03": "Mar", "04": "Apr",
        "05": "Mei", "06": "Jun", "07": "Jul", "08": "Agt",
        "09": "Sep", "10": "Okt", "11": "Nov", "12": "Des"
    }
    if not month_key or len(month_key) < 7:
        return month_key or "Unknown"
    mm = month_key.split("-")[1] if "-" in month_key else ""
    return bulan_names.get(mm, month_key)


# ============================================================================
# PERHITUNGAN TLC DINAMIS — dari data transaksi riil
# ============================================================================

def get_avg_qty_per_po_by_kota(db: Session) -> dict:
    """
    Rata-rata qty per PO (pengiriman) per kota.
    Dipakai untuk konversi TLC satuan 'per_pengiriman' -> per unit.
    """
    results = db.query(
        Transaksi.kota,
        func.sum(Transaksi.qty).label("total_qty"),
        func.count(func.distinct(Transaksi.nomor_po)).label("jumlah_po")
    ).filter(Transaksi.kota.isnot(None)).group_by(Transaksi.kota).all()

    data = {}
    for row in results:
        if row.jumlah_po and row.jumlah_po > 0:
            data[row.kota] = row.total_qty / row.jumlah_po
    return data


def get_avg_berat_per_kota(db: Session) -> dict:
    """
    Rata-rata berat produk (gram) TERTIMBANG (weighted by qty), per kota,
    berdasarkan id_produk yang BENAR-BENAR terjual di kota tersebut.
    Menggantikan pendekatan rata-rata generik AVG_BERAT_PRODUK_GRAM.
    """
    results = db.query(
        Transaksi.kota,
        Transaksi.id_produk,
        func.sum(Transaksi.qty).label("qty")
    ).filter(
        Transaksi.kota.isnot(None),
        Transaksi.id_produk.isnot(None)
    ).group_by(Transaksi.kota, Transaksi.id_produk).all()

    akumulasi = {}  # kota -> {"weighted_sum_gram": x, "total_qty": y}
    produk_tak_dikenali = set()

    for row in results:
        berat = BERAT_PRODUK_GRAM.get(row.id_produk)
        if berat is None:
            # id_produk tidak ada di referensi -> pakai fallback rata-rata global
            berat = AVG_BERAT_PRODUK_GRAM
            produk_tak_dikenali.add(row.id_produk)

        qty = row.qty or 0
        if row.kota not in akumulasi:
            akumulasi[row.kota] = {"weighted_sum_gram": 0.0, "total_qty": 0}
        akumulasi[row.kota]["weighted_sum_gram"] += berat * qty
        akumulasi[row.kota]["total_qty"] += qty

    if produk_tak_dikenali:
        # Tidak menghentikan proses, tapi baris ini berguna untuk debugging
        # kalau ada id_produk baru yang belum masuk BERAT_PRODUK_GRAM.
        print(f"[PERINGATAN] id_produk tidak dikenali (pakai fallback rata-rata): {produk_tak_dikenali}")

    avg_berat_per_kota = {}
    for kota, acc in akumulasi.items():
        if acc["total_qty"] > 0:
            avg_berat_per_kota[kota] = acc["weighted_sum_gram"] / acc["total_qty"]
    return avg_berat_per_kota


def get_volume_per_kota(db: Session) -> dict:
    """Total qty per kota (+ wilayahnya), dipakai sebagai bobot weighted average."""
    results = db.query(
        Transaksi.kota,
        Transaksi.wilayah,
        func.sum(Transaksi.qty).label("total_qty")
    ).filter(Transaksi.kota.isnot(None)).group_by(Transaksi.kota, Transaksi.wilayah).all()

    data = {}
    for row in results:
        data[row.kota] = {"wilayah": row.wilayah or "Lainnya", "qty": row.total_qty or 0}
    return data


def hitung_tlc_per_unit_kota(kota: str, avg_qty_per_po: dict, avg_berat_per_kota: dict) -> float:
    """
    Konversi Estimasi_Biaya (Master_Logistik) -> TLC per unit,
    tergantung Satuan_Biaya kota tersebut:
      - per_karung     -> dibagi estimasi jumlah unit per karung, dihitung
                          dari berat RIIL produk yang terjual di kota tsb
      - per_pengiriman -> dibagi rata-rata qty per PO ke kota tsb
      - kosong         -> 0 (diakui sebagai limitasi penelitian)
    """
    info = MASTER_LOGISTIK.get(kota)
    if not info or info["satuan"] == "kosong":
        return 0.0

    biaya = info["estimasi_biaya"]

    if info["satuan"] == "per_karung":
        # Pakai berat riil kota ini kalau ada datanya; fallback ke rata-rata
        # global cuma kalau kota tsb belum pernah ada transaksi sama sekali.
        berat_kota = avg_berat_per_kota.get(kota, AVG_BERAT_PRODUK_GRAM)
        unit_per_karung = KAPASITAS_KARUNG_GRAM / berat_kota
        return biaya / unit_per_karung

    if info["satuan"] == "per_pengiriman":
        avg_qty = avg_qty_per_po.get(kota)
        if not avg_qty or avg_qty <= 0:
            return 0.0
        return biaya / avg_qty

    return 0.0


def build_tlc_map(db: Session) -> dict:
    """
    Bangun TLC per unit per WILAYAH (Jawa/Sumatera/Kalimantan/dst),
    dengan weighted average by volume antar kota dalam satu wilayah.

    Menggantikan tlc_map hardcoded lama (15/30/40/20) yang tidak
    berdasar. Hasil fungsi ini otomatis berubah mengikuti data
    transaksi yang ter-upload di sistem.

    Key khusus "__DEFAULT__" berisi weighted average dari SEMUA wilayah
    yang punya data -> dipakai sbg fallback untuk wilayah yang tidak
    dikenali / tidak ada datanya sama sekali, MENGGANTIKAN angka 20
    yang sebelumnya tidak berdasar.
    """
    avg_qty_per_po = get_avg_qty_per_po_by_kota(db)
    avg_berat_per_kota = get_avg_berat_per_kota(db)
    volume_per_kota = get_volume_per_kota(db)

    akumulasi_wilayah = {}  # wilayah -> {"weighted_sum": x, "total_qty": y}

    for kota, info in volume_per_kota.items():
        info_logistik = MASTER_LOGISTIK.get(kota)
        if not info_logistik or info_logistik["satuan"] == "kosong":
            continue
        wilayah = info["wilayah"]
        qty = info["qty"]
        tlc_unit_kota = hitung_tlc_per_unit_kota(kota, avg_qty_per_po, avg_berat_per_kota)

        if wilayah not in akumulasi_wilayah:
            akumulasi_wilayah[wilayah] = {"weighted_sum": 0.0, "total_qty": 0}
        akumulasi_wilayah[wilayah]["weighted_sum"] += tlc_unit_kota * qty
        akumulasi_wilayah[wilayah]["total_qty"] += qty

    tlc_map = {}
    total_weighted_sum_all = 0.0
    total_qty_all = 0

    for wilayah, acc in akumulasi_wilayah.items():
        if acc["total_qty"] > 0:
            tlc_map[wilayah] = round(acc["weighted_sum"] / acc["total_qty"], 2)
            total_weighted_sum_all += acc["weighted_sum"]
            total_qty_all += acc["total_qty"]

    # Fallback yang defensible: rata-rata tertimbang SEMUA wilayah yang ada
    # datanya (bukan angka tetap seperti 20 yang lama, tanpa dasar).
    if total_qty_all > 0:
        tlc_map["__DEFAULT__"] = round(total_weighted_sum_all / total_qty_all, 2)
    else:
        tlc_map["__DEFAULT__"] = 0.0

    return tlc_map


# ============================================================================
# EVALUASI LOGISTIK INTERNAL (SUKABUMI) — tidak berubah dari versi lama
# ============================================================================

def calculate_internal_sukabumi(db: Session, kapasitas_ideal: int = 1000):
    """
    Evaluasi Logistik INTERNAL (Sukabumi):
    - Sewa Mobil Rp 800.000/trip per bulan.
    - SELALU menampilkan data 12 bulan penuh (kebal filter bulan).
    - Hanya dipengaruhi oleh slider kapasitas.
    """
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
        if qty <= 0:
            continue
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
        if kebocoran < 0:
            kebocoran = 0

        avg_harga = d["revenue"] / d["qty"]
        lcr = (cost_aktual / avg_harga) * 100 if avg_harga > 0 else 0

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


# ============================================================================
# EVALUASI LOGISTIK EKSTERNAL (COD LUAR SUKABUMI) — TLC kini dari build_tlc_map
# ============================================================================

def calculate_eksternal_cod(db: Session, bulan: str = None, kapasitas_ideal: int = 1000):
    """
    Evaluasi Logistik EKSTERNAL (COD Luar Sukabumi):
    - Dipengaruhi oleh filter bulan DAN slider kapasitas.
    - cost_per_unit (COD) dihitung PER KOTA (bukan per wilayah), sesuai
      teori LCR: "diterapkan pada tingkat kota... agar beban biaya
      logistik dapat dilihat secara rinci sesuai area pengiriman".
    - Kota tanpa data ongkir (Estimasi_Biaya = 0 / satuan "-") TIDAK diberi
      angka 0, melainkan status "Data ongkir belum tersedia" dan di-exclude dari
      avg_lcr_external & rute_termahal -- sesuai teori:
      "sistem tidak akan menggunakan angka perkiraan, melainkan
      menampilkan status data ongkir belum tersedia".
    """
    avg_qty_per_po = get_avg_qty_per_po_by_kota(db)
    avg_berat_per_kota = get_avg_berat_per_kota(db)

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
        if qty <= 0:
            continue

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
            lcr = (cost_per_unit / avg_harga) * 100 if avg_harga > 0 else 0
            utilization = (qty / kapasitas_ideal) * 100
            kebocoran = FIXED_COST_SUKABUMI * (1 - (qty / kapasitas_ideal)) if utilization < 100 else 0
            if kebocoran < 0:
                kebocoran = 0
            status = "Optimal" if utilization >= 80 else "Under-utilized"

            tabel_data.append({
                "wilayah": w, "kota": k, "skema": skema, "qty": qty,
                "kapasitas": kapasitas_ideal, "cost_per_unit": cost_per_unit,
                "lcr": lcr, "kebocoran": kebocoran, "status": status
            })
            continue

        skema = "COD (Pelanggan)"
        info_logistik = MASTER_LOGISTIK.get(k)
        data_tersedia = bool(info_logistik) and info_logistik["satuan"] != "kosong"

        if not data_tersedia:
            # --- Sesuai teori LCR: TIDAK pakai angka perkiraan ---
            tabel_data.append({
                "wilayah": w, "kota": k, "skema": skema, "qty": qty,
                "kapasitas": "-", "cost_per_unit": None,
                "lcr": None, "kebocoran": 0,
                "status": "Data ongkir belum tersedia"
            })
            continue  # tidak masuk external_chart, avg_lcr_external, rute_termahal

        # --- PERBAIKAN: cost_per_unit dihitung PER KOTA, bukan per wilayah ---
        cost_per_unit = hitung_tlc_per_unit_kota(k, avg_qty_per_po, avg_berat_per_kota)
        lcr = (cost_per_unit / avg_harga) * 100 if avg_harga > 0 else 0
        status = "Sehat" if lcr <= 15 else ("Rawan" if lcr <= 25 else "Bahaya")

        external_chart.append({"kota": k, "qty": qty, "lcr": lcr})
        total_lcr_external += lcr
        count_external += 1
        if lcr > rute_termahal["lcr"]:
            rute_termahal = {"kota": k, "lcr": lcr}

        tabel_data.append({
            "wilayah": w, "kota": k, "skema": skema, "qty": qty,
            "kapasitas": "-", "cost_per_unit": cost_per_unit,
            "lcr": lcr, "kebocoran": 0, "status": status
        })

    avg_lcr_external = (total_lcr_external / count_external) if count_external > 0 else 0

    external_chart.sort(key=lambda x: x["qty"], reverse=True)
    external_chart = external_chart[:10]
    # None (data tidak tersedia) ditaruh di akhir saat sort by lcr
    tabel_data.sort(key=lambda x: (x["lcr"] is None, x["lcr"] if x["lcr"] is not None else 0), reverse=True)

    return {
        "kpi": {
            "avg_lcr_external": avg_lcr_external,
            "rute_termahal": rute_termahal["kota"],
            "lcr_rute_termahal": rute_termahal["lcr"]
        },
        "external_chart": external_chart,
        "tabel_data": tabel_data
    }