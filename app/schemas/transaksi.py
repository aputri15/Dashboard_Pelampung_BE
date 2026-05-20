from pydantic import BaseModel
from typing import Optional, List

class TransaksiBase(BaseModel):
    nomor_po: str
    tanggal_po: str
    id_pelanggan: Optional[str] = None
    nama_pelanggan: str
    wilayah: str
    provinsi: Optional[str] = None
    kota: Optional[str] = None
    id_produk: Optional[str] = None
    nama_model: str
    kategori: Optional[str] = None
    qty: int
    harga_satuan: float
    total_harga: float
    modal_unit: Optional[float] = None

class TransaksiCreate(TransaksiBase):
    pass

class TransaksiManualCreate(BaseModel):
    nomor_po: str
    tanggal_po: str
    id_pelanggan: str
    nama_pelanggan: str
    wilayah: str
    provinsi: str
    kota: str
    id_produk: str
    nama_model: str
    kategori: str
    qty: int
    harga_satuan: float
    modal_unit: float

class TransaksiUpdate(BaseModel):
    nomor_po: Optional[str] = None
    tanggal_po: Optional[str] = None
    nama_pelanggan: Optional[str] = None
    wilayah: Optional[str] = None
    provinsi: Optional[str] = None
    kota: Optional[str] = None
    nama_model: Optional[str] = None
    kategori: Optional[str] = None
    qty: Optional[int] = None
    harga_satuan: Optional[float] = None
    total_harga: Optional[float] = None
    modal_unit: Optional[float] = None

class TransaksiResponse(TransaksiBase):
    id: int
    class Config:
        from_attributes = True

class LogUploadResponse(BaseModel):
    id: int
    tanggal: str
    nama_file: str
    jumlah_baris: int
    status: str
    uploaded_by: str
    class Config:
        from_attributes = True

class TransaksiListResponse(BaseModel):
    data: List[TransaksiResponse]
    total: int
    page: int
    per_page: int

class TransaksiFilterOptionsResponse(BaseModel):
    bulan: List[str]
    tahun: List[str]
    wilayah: List[str]
