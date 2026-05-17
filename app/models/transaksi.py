from sqlalchemy import Column, Integer, String, Float, Text
from app.db.database import Base

class Transaksi(Base):
    __tablename__ = "transaksi"
    id = Column(Integer, primary_key=True, index=True)
    nomor_po = Column(String, index=True)
    tanggal_po = Column(String)
    id_pelanggan = Column(String)
    nama_pelanggan = Column(String)
    wilayah = Column(String, index=True)
    provinsi = Column(String)
    kota = Column(String)
    id_produk = Column(String)
    nama_model = Column(String)
    kategori = Column(String)
    qty = Column(Integer)
    harga_satuan = Column(Float)
    total_harga = Column(Float)
    modal_unit = Column(Float)

class LogUpload(Base):
    __tablename__ = "log_upload"
    id = Column(Integer, primary_key=True, index=True)
    tanggal = Column(String)
    nama_file = Column(String)
    jumlah_baris = Column(Integer)
    status = Column(String)
    uploaded_by = Column(String)
    file_hash = Column(String, nullable=True, index=True)
