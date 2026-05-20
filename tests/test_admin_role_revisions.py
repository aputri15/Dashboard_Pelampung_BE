import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.crud import crud_transaksi, crud_user
from app.db.database import Base
from app.models.transaksi import LogUpload, Transaksi
from app.schemas.transaksi import TransaksiManualCreate, TransaksiUpdate
from app.schemas.user import UserCreate, UserUpdate


def make_db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()


def make_transaksi(**overrides):
    data = {
        "nomor_po": "PO-001",
        "tanggal_po": "2026-05-19",
        "id_pelanggan": "C-001",
        "nama_pelanggan": "Toko Rezeki",
        "wilayah": "Jawa",
        "provinsi": "Jawa Barat",
        "kota": "Bandung",
        "id_produk": "P-001",
        "nama_model": "Pelampung A",
        "kategori": "Premium",
        "qty": 2,
        "harga_satuan": 15000,
        "modal_unit": 7000,
    }
    data.update(overrides)
    return data


class AdminRoleRevisionTests(unittest.TestCase):
    def test_create_manual_transaksi_computes_total_harga(self):
        db = make_db()
        transaksi_in = TransaksiManualCreate(**make_transaksi(qty=3, harga_satuan=12500))

        row = crud_transaksi.create_manual_transaksi(db, transaksi_in)

        self.assertEqual(row.total_harga, 37500)
        self.assertEqual(db.query(Transaksi).count(), 1)

    def test_update_transaksi_recomputes_total_harga_when_qty_or_price_changes(self):
        db = make_db()
        row = Transaksi(**make_transaksi(qty=2, harga_satuan=10000, total_harga=20000))
        db.add(row)
        db.commit()
        db.refresh(row)

        updated = crud_transaksi.update_transaksi(
            db,
            db_transaksi=row,
            transaksi_in=TransaksiUpdate(qty=5, harga_satuan=12000),
        )

        self.assertEqual(updated.qty, 5)
        self.assertEqual(updated.harga_satuan, 12000)
        self.assertEqual(updated.total_harga, 60000)

    def test_transaksi_list_combines_search_month_year_and_wilayah_filters(self):
        db = make_db()
        rows = [
            make_transaksi(
                nomor_po="PO-001",
                tanggal_po="2026-05-01",
                nama_pelanggan="Toko Maju",
                wilayah="Jawa",
                kota="Bandung",
                nama_model="Pelampung Super",
                kategori="Premium",
                total_harga=30000,
            ),
            make_transaksi(
                nomor_po="PO-002",
                tanggal_po="2026-06-01",
                nama_pelanggan="Toko Maju",
                wilayah="Jawa",
                kota="Bandung",
                nama_model="Pelampung Super",
                kategori="Premium",
                total_harga=30000,
            ),
            make_transaksi(
                nomor_po="PO-003",
                tanggal_po="2026-05-02",
                nama_pelanggan="Toko Lain",
                wilayah="Sumatera",
                kota="Medan",
                nama_model="Model B",
                kategori="Ekonomis",
                total_harga=30000,
            ),
        ]
        for data in rows:
            db.add(Transaksi(**data))
        db.commit()

        data, total = crud_transaksi.get_transaksi_list(
            db,
            page=1,
            per_page=15,
            search="super",
            wilayah="Jawa",
            bulan="05",
            tahun="2026",
        )

        self.assertEqual(total, 1)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0].nomor_po, "PO-001")


if __name__ == "__main__":
    unittest.main()
