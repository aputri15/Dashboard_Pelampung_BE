# Admin Role Revisions Design

Date: 2026-05-19
Status: Approved design, pending implementation plan

## Context

The admin role currently manages four pages:

- Upload Data
- Kelola Data
- Riwayat Log Upload
- Manajemen Akun

The requested revisions focus on improving admin data checks, search and filter behavior, upload feedback, manual transaction entry, account error messages, and safe log cleanup.

Current data snapshot during discovery:

- `transaksi`: 2782 rows
- `log_upload`: 17 rows
- `users`: admin and owner accounts, including active and inactive examples

Because transaction volume can grow, filtering, search, pagination, and totals should be handled by the backend as the source of truth. The frontend should send filter state to the API and render API results.

## Goals

1. Make Kelola Data totals, search, filters, and pagination accurate for the active filter set.
2. Add manual one-row transaction input from Upload Data through a "Tambahkan Data" modal.
3. Allow Excel uploads to skip blank rows, report them clearly, and insert valid rows.
4. Add search and combined filters to Riwayat Log Upload.
5. Improve Manajemen Akun duplicate username/email feedback and form reset behavior.
6. Protect account integrity by validating roles on update and preserving at least one active admin.
7. Allow admin to remove upload logs from the visible list without breaking duplicate upload protection.

## Non-Goals

- Full frontend framework migration.
- Large admin layout rewrite.
- Replacing SQLite or changing the authentication model.
- Rebuilding owner dashboard analytics.

## Approach

Use a backend-first incremental implementation.

The backend will own search, filters, pagination, total counts, validation, and duplicate-upload safety. The frontend will add controls and modals, call the enhanced endpoints, and display clear success or error messages.

This avoids misleading totals and pagination when data grows, while keeping the implementation scoped to the requested admin revisions.

## Backend Design

### Transaksi Listing

Enhance `GET /api/v1/transaksi/` with combined filters:

- `search`
- `bulan`
- `tahun`
- `wilayah`
- `page`
- `per_page`

Search will match only:

- `nama_pelanggan`
- `kategori`
- `nama_model`
- `kota`

The response will continue to include:

- `data`
- `total`
- `page`
- `per_page`

`total` must represent the filtered total, not the whole table.

### Manual Transaction Create

Add `POST /api/v1/transaksi/` for the Upload Data "Tambahkan Data" form.

The form will submit one transaction row. The backend validates required fields and computes:

```text
total_harga = qty * harga_satuan
```

The backend will not rely on a frontend-provided `total_harga` for manual create.

### Transaction Update

Update `PUT /api/v1/transaksi/{transaksi_id}` so backend recomputes `total_harga` when either `qty` or `harga_satuan` changes.

### Excel Upload

Excel upload behavior will change for blank rows:

- Blank rows are skipped.
- Valid rows are inserted.
- Blank row count and row numbers are returned to the frontend.
- Upload remains successful if the only issue is blank rows.

The upload response should include:

- `success`
- `total_rows`
- `processed_rows`
- `inserted_rows`
- `skipped_rows`
- `blank_row_count`
- `blank_rows`
- `errors`
- `message`

The user-facing message should explain how many valid rows were inserted, how many blank rows were skipped, and which Excel row numbers were skipped.

### Upload Logs

Enhance `GET /api/v1/transaksi/log/uploads` with:

- `search` by `nama_file`
- `bulan`
- `tahun`
- `status`
- pagination parameters

The response should include:

- `data`
- `total`
- `page` or `skip`
- `per_page` or `limit`

### Soft Delete Upload Logs

Deleting an upload log will be a soft delete. The log disappears from the visible history, but remains available to duplicate-upload checks.

Suggested model field:

- `is_deleted: bool = false`

Alternative acceptable field:

- `hidden_at: datetime | null`

Visible log listing filters out deleted logs. Duplicate file detection still checks successful uploads by `file_hash`, including hidden logs.

This allows admins to clean the visible log table without allowing duplicate dataset uploads.

### User Management

Create and update user flows will return specific duplicate messages:

- Username already used
- Email already used
- Username and email already used, if both conflict

Backend role validation applies to both create and update:

- allowed roles: `admin`, `owner`

Backend must prevent actions that leave the system with zero active admin accounts. This includes:

- deleting the last active admin
- deactivating the last active admin
- changing the last active admin's role to owner

Deleting oneself is already blocked and remains blocked.

## Frontend Design

### Upload Data Page

Add a "Tambahkan Data" button on the Upload Data page.

The button opens a modal with a complete one-row transaction form. Required fields include:

- Nomor PO
- Tanggal PO
- ID Pelanggan
- Nama Pelanggan
- Wilayah
- Provinsi
- Kota
- ID Produk
- Nama Model
- Kategori
- Qty
- Harga Satuan
- Modal Unit

`total_harga` is computed by the backend. The UI may show a calculated preview, but it is not the source of truth.

After successful manual submit:

- close or reset the modal
- clear form fields
- show a success notification

After Excel upload:

- show inserted row count
- show skipped blank row count
- show skipped Excel row numbers
- show total processed rows

The upload request should use shared auth behavior so token refresh remains consistent with other API calls.

### Kelola Data Page

Add a total data summary that follows active filters.

Search placeholder:

```text
Cari pelanggan, kategori, model, kota...
```

Add separate dropdowns:

- Bulan
- Tahun
- Wilayah

Search and filters must be combinable. Pagination must use the filtered `total` from the backend.

Add a reset-filter control so admin can quickly return to all data.

### Riwayat Log Upload Page

Add:

- search by file name
- month dropdown
- year dropdown
- status dropdown with `Semua`, `Sukses`, `Gagal`
- pagination and filtered total display

Search and filters must be combinable.

The delete action hides logs through backend soft delete. Successful hidden logs still protect against duplicate uploads.

### Manajemen Akun Page

Toast behavior:

- success toast: green
- failed toast: red

Duplicate create and duplicate update messages must be specific:

- `Tidak berhasil, username telah digunakan.`
- `Tidak berhasil, email telah digunakan.`
- `Tidak berhasil, username dan email telah digunakan.`

The Tambah Akun modal form resets after a submit attempt, whether create succeeds or fails.

The hardcoded user pagination footer should either be made real or removed until real pagination is implemented.

## Data Flow

### Upload With Blank Rows

1. Admin uploads Excel.
2. Backend validates sheet and headers.
3. Backend skips fully blank rows and records their Excel row numbers.
4. Backend inserts valid transaction rows.
5. Backend creates an upload log with `file_hash`.
6. Frontend shows upload result, including blank row details.
7. Admin can use "Tambahkan Data" to manually add missing rows.

### Manual Add Data

1. Admin opens "Tambahkan Data".
2. Admin fills one transaction row.
3. Frontend submits to `POST /api/v1/transaksi/`.
4. Backend validates and computes `total_harga`.
5. Frontend shows success and refreshes relevant counts when needed.

### Log Soft Delete

1. Admin clicks delete on a log row.
2. Backend marks the log hidden/deleted.
3. Log no longer appears in history.
4. Duplicate upload checks still include hidden successful logs.

## Error Handling

- Upload validation errors show clear reasons and row details.
- Upload with blank rows is success with warning details, not failure.
- Duplicate username/email errors show red notification with specific message.
- Failed data loads show explicit failure messages instead of empty-table states.
- Backend validation errors remain authoritative even if frontend validation is bypassed.

## Testing Plan

Backend tests:

- Excel upload succeeds with valid rows and skipped blank rows.
- Excel upload response includes blank row count and row numbers.
- Manual transaction create computes `total_harga`.
- Transaction update recomputes `total_harga` when qty or price changes.
- Transaksi search matches only pelanggan, kategori, model, and kota.
- Transaksi filters combine bulan, tahun, wilayah, and search.
- Upload log search/filter combines filename, month, year, and status.
- Soft-deleted successful upload logs remain active for duplicate detection.
- Duplicate username/email create and update return specific messages.
- Role update rejects roles outside `admin` and `owner`.
- Backend prevents deleting, deactivating, or demoting the last active admin.

Frontend verification:

- `npm run build`
- Manual browser check for four admin pages:
  - Upload Data
  - Kelola Data
  - Riwayat Log Upload
  - Manajemen Akun

## Open Decisions

No open product decisions remain. The approved choices are:

- Backend-first implementation.
- Upload blank rows are skipped and reported.
- Manual "Tambahkan Data" uses a complete one-row transaction form.
- Kelola Data filters use separate month, year, and wilayah dropdowns.
- Log Upload filters use separate month, year, and status dropdowns.
- Upload log delete uses soft delete.
- Backend validates role update and preserves at least one active admin.
