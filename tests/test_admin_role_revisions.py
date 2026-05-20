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


def create_user(db, username, email, role="admin", is_active=True):
    return crud_user.create_user(
        db,
        UserCreate(
            full_name=username.title(),
            email=email,
            username=username,
            password="secret123",
            role=role,
            is_active=is_active,
        ),
    )


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

    def test_soft_deleted_success_log_is_hidden_but_still_blocks_duplicate_hash(self):
        db = make_db()
        crud_transaksi.create_log_upload(
            db,
            nama_file="dataset.xlsx",
            jumlah_baris=10,
            status="Sukses",
            uploaded_by="admin",
            file_hash="abc123",
        )

        visible_before, total_before = crud_transaksi.get_log_uploads(
            db, page=1, per_page=10, include_deleted=False
        )
        self.assertEqual(total_before, 1)
        self.assertEqual(len(visible_before), 1)

        crud_transaksi.soft_delete_log_upload(db, log_id=visible_before[0].id)

        visible_after, total_after = crud_transaksi.get_log_uploads(
            db, page=1, per_page=10, include_deleted=False
        )
        self.assertEqual(total_after, 0)
        self.assertEqual(visible_after, [])
        self.assertIsNotNone(crud_transaksi.get_successful_upload_by_hash(db, "abc123"))

    def test_log_uploads_combine_filename_month_year_and_status_filters(self):
        db = make_db()
        log_a = LogUpload(
            tanggal="2026-05-19 10:00:00",
            nama_file="mei-sukses.xlsx",
            jumlah_baris=5,
            status="Sukses",
            uploaded_by="admin",
            file_hash="hash-a",
        )
        log_b = LogUpload(
            tanggal="2026-06-01 10:00:00",
            nama_file="mei-gagal.xlsx",
            jumlah_baris=0,
            status="Gagal",
            uploaded_by="admin",
            file_hash="hash-b",
        )
        db.add_all([log_a, log_b])
        db.commit()

        logs, total = crud_transaksi.get_log_uploads(
            db,
            page=1,
            per_page=10,
            search="mei",
            bulan="05",
            tahun="2026",
            status="Sukses",
        )

        self.assertEqual(total, 1)
        self.assertEqual(logs[0].nama_file, "mei-sukses.xlsx")

    def test_user_conflict_detection_reports_username_and_email(self):
        db = make_db()
        existing = create_user(db, "admin1", "admin1@example.com", role="admin")

        conflict = crud_user.get_user_conflicts(
            db,
            username="admin1",
            email="admin1@example.com",
            exclude_user_id=None,
        )

        self.assertEqual(conflict, {"username": True, "email": True})

        conflict_excluding_self = crud_user.get_user_conflicts(
            db,
            username="admin1",
            email="admin1@example.com",
            exclude_user_id=existing.id,
        )

        self.assertEqual(conflict_excluding_self, {"username": False, "email": False})

    def test_last_active_admin_guard_detects_deactivate_delete_or_demote(self):
        db = make_db()
        admin = create_user(db, "admin1", "admin1@example.com", role="admin", is_active=True)
        owner = create_user(db, "owner1", "owner1@example.com", role="owner", is_active=True)

        self.assertTrue(crud_user.is_last_active_admin(db, admin))
        self.assertFalse(crud_user.is_last_active_admin(db, owner))

        create_user(db, "admin2", "admin2@example.com", role="admin", is_active=True)
        self.assertFalse(crud_user.is_last_active_admin(db, admin))


if __name__ == "__main__":
    unittest.main()
