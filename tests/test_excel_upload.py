import io
import unittest

import openpyxl
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.crud.crud_transaksi import process_excel_upload
from app.db.database import Base
from app.models.transaksi import Transaksi


HEADERS = [
    "Nomor_PO",
    "Tanggal_PO",
    "ID_Pelanggan",
    "Nama_Pelanggan",
    "Wilayah",
    "Provinsi",
    "Kota",
    "ID_Produk",
    "Nama_Model",
    "Kategori",
    "Qty",
    "Harga_Satuan",
    "Total_Harga",
    "Modal_Unit",
]

VALID_ROW = [
    "PO-202501-001",
    "2025-01-22",
    "CU-SM-0007",
    "Toko Rezeki Pancing",
    "Sumatera",
    "Sumatera Utara",
    "Medan",
    "JK3",
    "Jantung",
    "kkk",
    7000,
    80,
    560000,
    35,
]


def make_db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()


def make_workbook_bytes(sheets):
    wb = openpyxl.Workbook()
    first = True
    for sheet_name, rows in sheets:
        if first:
            ws = wb.active
            ws.title = sheet_name
            first = False
        else:
            ws = wb.create_sheet(sheet_name)
        for row in rows:
            ws.append(row)
    stream = io.BytesIO()
    wb.save(stream)
    return stream.getvalue()


class ExcelUploadTests(unittest.TestCase):
    def test_reads_master_sheet_not_template(self):
        db = make_db()
        content = make_workbook_bytes(
            [
                ("TEMPLATE", [HEADERS, ["PO-yyyymm-001", "dd/mm/yyyy", None, None]]),
                ("MASTER2025", [HEADERS, VALID_ROW]),
            ]
        )

        result = process_excel_upload(db, content, "rekap.xlsx", "admin")

        self.assertTrue(result["success"])
        self.assertEqual(result["inserted_rows"], 1)
        self.assertEqual(db.query(Transaksi).count(), 1)
        row = db.query(Transaksi).one()
        self.assertEqual(row.nama_pelanggan, "Toko Rezeki Pancing")

    def test_rejects_missing_or_ambiguous_master_sheet(self):
        missing_db = make_db()
        missing_content = make_workbook_bytes([("TEMPLATE", [HEADERS, VALID_ROW])])

        missing_result = process_excel_upload(missing_db, missing_content, "missing.xlsx", "admin")

        self.assertFalse(missing_result["success"])
        self.assertIn("MASTER", missing_result["message"])
        self.assertEqual(missing_db.query(Transaksi).count(), 0)

        ambiguous_db = make_db()
        ambiguous_content = make_workbook_bytes(
            [
                ("MASTER2025", [HEADERS, VALID_ROW]),
                ("MASTER2026", [HEADERS, VALID_ROW]),
            ]
        )

        ambiguous_result = process_excel_upload(ambiguous_db, ambiguous_content, "ambiguous.xlsx", "admin")

        self.assertFalse(ambiguous_result["success"])
        self.assertIn("lebih dari satu", ambiguous_result["message"].lower())
        self.assertEqual(ambiguous_db.query(Transaksi).count(), 0)

    def test_rejects_lowercase_master_sheet_name(self):
        db = make_db()
        content = make_workbook_bytes([("master2025", [HEADERS, VALID_ROW])])

        result = process_excel_upload(db, content, "lowercase.xlsx", "admin")

        self.assertFalse(result["success"])
        self.assertIn("MASTER", result["message"])
        self.assertEqual(db.query(Transaksi).count(), 0)

    def test_rejects_missing_required_header(self):
        db = make_db()
        headers_without_modal = [h for h in HEADERS if h != "Modal_Unit"]
        row_without_modal = VALID_ROW[:-1]
        content = make_workbook_bytes([("MASTER2025", [headers_without_modal, row_without_modal])])

        result = process_excel_upload(db, content, "missing-header.xlsx", "admin")

        self.assertFalse(result["success"])
        self.assertIn("modal_unit", " ".join(result["errors"]))
        self.assertEqual(db.query(Transaksi).count(), 0)

    def test_invalid_row_fails_whole_upload_and_groups_empty_columns(self):
        db = make_db()
        bad_row = VALID_ROW.copy()
        bad_row[7] = None
        bad_row[13] = None
        content = make_workbook_bytes([("MASTER2025", [HEADERS, VALID_ROW, bad_row])])

        result = process_excel_upload(db, content, "bad-row.xlsx", "admin")

        self.assertFalse(result["success"])
        self.assertEqual(db.query(Transaksi).count(), 0)
        row_3_errors = [err for err in result["errors"] if "Baris 3" in err]
        self.assertEqual(len(row_3_errors), 1)
        self.assertIn("id_produk", row_3_errors[0])
        self.assertIn("modal_unit", row_3_errors[0])

    def test_computes_empty_total_harga(self):
        db = make_db()
        row = VALID_ROW.copy()
        row[12] = None
        content = make_workbook_bytes([("MASTER2025", [HEADERS, row])])

        result = process_excel_upload(db, content, "computed-total.xlsx", "admin")

        self.assertTrue(result["success"])
        imported = db.query(Transaksi).one()
        self.assertEqual(imported.total_harga, 560000)

    def test_rejects_conflicting_total_harga(self):
        db = make_db()
        row = VALID_ROW.copy()
        row[12] = 123
        content = make_workbook_bytes([("MASTER2025", [HEADERS, row])])

        result = process_excel_upload(db, content, "conflict-total.xlsx", "admin")

        self.assertFalse(result["success"])
        self.assertIn("total_harga", " ".join(result["errors"]))
        self.assertEqual(db.query(Transaksi).count(), 0)

    def test_duplicate_exact_successful_file_rejected_but_failed_file_allowed(self):
        db = make_db()
        content = make_workbook_bytes([("MASTER2025", [HEADERS, VALID_ROW])])

        first = process_excel_upload(db, content, "same.xlsx", "admin")
        second = process_excel_upload(db, content, "renamed.xlsx", "admin")

        self.assertTrue(first["success"])
        self.assertFalse(second["success"])
        self.assertIn("sudah pernah diupload", second["message"])
        self.assertEqual(db.query(Transaksi).count(), 1)

        bad_row = VALID_ROW.copy()
        bad_row[7] = None
        bad_content = make_workbook_bytes([("MASTER2025", [HEADERS, bad_row])])

        failed_first = process_excel_upload(db, bad_content, "bad.xlsx", "admin")
        failed_second = process_excel_upload(db, bad_content, "bad.xlsx", "admin")

        self.assertFalse(failed_first["success"])
        self.assertFalse(failed_second["success"])
        self.assertIn("id_produk", " ".join(failed_second["errors"]))
        self.assertEqual(db.query(Transaksi).count(), 1)


if __name__ == "__main__":
    unittest.main()
