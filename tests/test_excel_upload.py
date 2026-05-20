import io
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

import openpyxl
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.crud import crud_transaksi
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


def make_file_db(db_path):
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False, "timeout": 15},
    )
    Base.metadata.create_all(bind=engine)
    return engine, sessionmaker(bind=engine)


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

    def test_parses_indonesian_thousand_separators(self):
        db = make_db()
        row = VALID_ROW.copy()
        row[10] = "2"
        row[11] = "1.000"
        row[12] = "2.000"
        row[13] = "12.500"
        content = make_workbook_bytes([("MASTER2025", [HEADERS, row])])

        result = process_excel_upload(db, content, "rupiah-format.xlsx", "admin")

        self.assertTrue(result["success"])
        imported = db.query(Transaksi).one()
        self.assertEqual(imported.qty, 2)
        self.assertEqual(imported.harga_satuan, 1000)
        self.assertEqual(imported.total_harga, 2000)
        self.assertEqual(imported.modal_unit, 12500)

    def test_parses_indonesian_decimal_and_multi_group_values(self):
        db = make_db()
        row = VALID_ROW.copy()
        row[10] = 1
        row[11] = "1.234.567"
        row[12] = None
        row[13] = "1.000,50"
        content = make_workbook_bytes([("MASTER2025", [HEADERS, row])])

        result = process_excel_upload(db, content, "rupiah-big.xlsx", "admin")

        self.assertTrue(result["success"])
        imported = db.query(Transaksi).one()
        self.assertEqual(imported.harga_satuan, 1234567)
        self.assertEqual(imported.total_harga, 1234567)
        self.assertEqual(imported.modal_unit, 1000.5)

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

    def test_success_summary_counts_transaction_rows_and_reports_blank_rows(self):
        db = make_db()
        second_row = VALID_ROW.copy()
        second_row[0] = "PO-202501-002"
        blank_row = [None] * len(HEADERS)
        content = make_workbook_bytes([("MASTER2025", [HEADERS, VALID_ROW, blank_row, second_row])])

        result = process_excel_upload(db, content, "blank-tail.xlsx", "admin")

        self.assertTrue(result["success"])
        self.assertEqual(result["total_rows"], 2)
        self.assertEqual(result["processed_rows"], 2)
        self.assertEqual(result["inserted_rows"], 2)
        self.assertEqual(result["skipped_rows"], 1)
        self.assertEqual(result["blank_row_count"], 1)
        self.assertEqual(result["blank_rows"], [3])
        self.assertIn("Baris kosong dilewati: 3", result["message"])

    def test_concurrent_duplicate_upload_rolls_back_losing_insert(self):
        content = make_workbook_bytes([("MASTER2025", [HEADERS, VALID_ROW])])

        with tempfile.TemporaryDirectory() as tmpdir:
            engine, SessionLocal = make_file_db(Path(tmpdir) / "race.db")
            barrier = threading.Barrier(2)
            original_get_successful_upload_by_hash = crud_transaksi.get_successful_upload_by_hash
            results = []
            errors = []
            lock = threading.Lock()

            def racing_duplicate_check(db, file_hash):
                result = original_get_successful_upload_by_hash(db, file_hash)
                barrier.wait(timeout=10)
                return result

            def upload_worker(filename):
                db = SessionLocal()
                try:
                    result = crud_transaksi.process_excel_upload(db, content, filename, "admin")
                    with lock:
                        results.append(result)
                except Exception as exc:
                    with lock:
                        errors.append(exc)
                finally:
                    db.close()

            with mock.patch(
                "app.crud.crud_transaksi.get_successful_upload_by_hash",
                side_effect=racing_duplicate_check,
            ):
                threads = [
                    threading.Thread(target=upload_worker, args=("race-1.xlsx",)),
                    threading.Thread(target=upload_worker, args=("race-2.xlsx",)),
                ]
                for thread in threads:
                    thread.start()
                for thread in threads:
                    thread.join(timeout=15)

            try:
                self.assertFalse(any(thread.is_alive() for thread in threads))
                self.assertEqual(errors, [])
                self.assertEqual(len(results), 2)
                successes = [result for result in results if result["success"]]
                failures = [result for result in results if not result["success"]]
                self.assertEqual(len(successes), 1)
                self.assertEqual(len(failures), 1)
                self.assertIn("sudah pernah diupload", failures[0]["message"])

                check_db = SessionLocal()
                try:
                    self.assertEqual(check_db.query(Transaksi).count(), 1)
                finally:
                    check_db.close()
            finally:
                engine.dispose()


if __name__ == "__main__":
    unittest.main()
