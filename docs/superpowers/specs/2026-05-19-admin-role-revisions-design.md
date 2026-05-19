# Desain Revisi Role Admin

Tanggal: 2026-05-19
Status: Desain disetujui, menunggu rencana implementasi

## Konteks

Role admin saat ini mengelola empat halaman:

- Upload Data
- Kelola Data
- Riwayat Log Upload
- Manajemen Akun

Revisi yang diminta berfokus pada peningkatan pengecekan data oleh admin, perilaku search dan filter, feedback upload, input transaksi manual, pesan error akun, dan pembersihan log upload yang tetap aman.

Snapshot data saat eksplorasi:

- `transaksi`: 2782 baris
- `log_upload`: 17 baris
- `users`: akun admin dan owner, termasuk contoh akun aktif dan nonaktif

Karena jumlah transaksi bisa terus bertambah, filter, search, pagination, dan total data harus ditangani backend sebagai sumber kebenaran. Frontend mengirim state filter ke API dan merender hasil dari API.

## Tujuan

1. Membuat total data, search, filter, dan pagination pada Kelola Data akurat sesuai filter aktif.
2. Menambahkan input transaksi manual satu baris dari halaman Upload Data melalui modal "Tambahkan Data".
3. Mengizinkan upload Excel melewati baris kosong, melaporkannya dengan jelas, dan tetap memasukkan baris valid.
4. Menambahkan search dan filter kombinasi pada Riwayat Log Upload.
5. Memperbaiki feedback duplicate username/email dan perilaku reset form pada Manajemen Akun.
6. Menjaga integritas akun dengan validasi role saat update dan memastikan selalu ada minimal satu admin aktif.
7. Mengizinkan admin menyembunyikan log upload dari daftar tanpa merusak proteksi duplicate upload.

## Bukan Scope

- Migrasi frontend ke framework baru.
- Rewrite besar layout admin.
- Mengganti SQLite atau mengubah model autentikasi.
- Membangun ulang analytics dashboard owner.

## Pendekatan

Gunakan implementasi incremental berbasis backend.

Backend menjadi pemilik search, filter, pagination, total count, validasi, dan keamanan duplicate upload. Frontend menambahkan kontrol UI dan modal, memanggil endpoint yang ditingkatkan, lalu menampilkan pesan sukses atau error yang jelas.

Pendekatan ini mencegah total data dan pagination yang menyesatkan saat data bertambah, sambil menjaga perubahan tetap sesuai scope revisi admin.

## Desain Backend

### Listing Transaksi

Tingkatkan `GET /api/v1/transaksi/` dengan filter kombinasi:

- `search`
- `bulan`
- `tahun`
- `wilayah`
- `page`
- `per_page`

Search hanya cocok ke field:

- `nama_pelanggan`
- `kategori`
- `nama_model`
- `kota`

Response tetap memuat:

- `data`
- `total`
- `page`
- `per_page`

`total` harus merepresentasikan total hasil setelah filter aktif, bukan total seluruh tabel.

### Tambah Transaksi Manual

Tambahkan `POST /api/v1/transaksi/` untuk form "Tambahkan Data" pada halaman Upload Data.

Form mengirim satu baris transaksi. Backend memvalidasi field wajib dan menghitung:

```text
total_harga = qty * harga_satuan
```

Backend tidak bergantung pada `total_harga` dari frontend untuk tambah transaksi manual.

### Update Transaksi

Perbarui `PUT /api/v1/transaksi/{transaksi_id}` agar backend menghitung ulang `total_harga` ketika `qty` atau `harga_satuan` berubah.

### Upload Excel

Perilaku upload Excel untuk baris kosong diubah:

- Baris kosong dilewati.
- Baris valid dimasukkan ke database.
- Jumlah baris kosong dan nomor barisnya dikembalikan ke frontend.
- Upload tetap sukses jika satu-satunya masalah adalah baris kosong.

Response upload harus memuat:

- `success`
- `total_rows`
- `processed_rows`
- `inserted_rows`
- `skipped_rows`
- `blank_row_count`
- `blank_rows`
- `errors`
- `message`

Pesan untuk admin harus menjelaskan berapa baris valid yang masuk, berapa baris kosong yang dilewati, dan nomor baris Excel mana yang dilewati.

### Log Upload

Tingkatkan `GET /api/v1/transaksi/log/uploads` dengan:

- `search` berdasarkan `nama_file`
- `bulan`
- `tahun`
- `status`
- parameter pagination

Response harus memuat:

- `data`
- `total`
- `page` atau `skip`
- `per_page` atau `limit`

### Soft Delete Log Upload

Menghapus log upload dilakukan sebagai soft delete. Log hilang dari daftar riwayat yang terlihat, tetapi tetap tersedia untuk pengecekan duplicate upload.

Field model yang disarankan:

- `is_deleted: bool = false`

Alternatif yang juga bisa diterima:

- `hidden_at: datetime | null`

Listing log yang terlihat memfilter log yang sudah dihapus. Deteksi duplicate file tetap memeriksa upload sukses berdasarkan `file_hash`, termasuk log yang sudah disembunyikan.

Dengan desain ini admin bisa membersihkan tampilan tabel log tanpa membuat dataset yang sama bisa di-upload ulang.

### Manajemen User

Flow create dan update user mengembalikan pesan duplicate yang spesifik:

- Username sudah digunakan
- Email sudah digunakan
- Username dan email sudah digunakan, jika keduanya konflik

Validasi role di backend berlaku untuk create dan update:

- role yang diizinkan: `admin`, `owner`

Backend harus mencegah aksi yang membuat sistem tidak memiliki admin aktif. Ini mencakup:

- menghapus admin aktif terakhir
- menonaktifkan admin aktif terakhir
- mengubah role admin aktif terakhir menjadi owner

Menghapus akun sendiri sudah diblokir dan tetap diblokir.

## Desain Frontend

### Halaman Upload Data

Tambahkan tombol "Tambahkan Data" pada halaman Upload Data.

Tombol membuka modal berisi form transaksi lengkap untuk satu baris. Field wajib:

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

`total_harga` dihitung oleh backend. UI boleh menampilkan preview hasil hitung, tetapi bukan sumber kebenaran.

Setelah submit manual berhasil:

- tutup atau reset modal
- kosongkan field form
- tampilkan notifikasi sukses

Setelah upload Excel:

- tampilkan jumlah baris yang masuk database
- tampilkan jumlah baris kosong yang dilewati
- tampilkan nomor baris Excel yang kosong
- tampilkan total baris yang diproses

Request upload harus memakai perilaku auth yang konsisten agar token refresh tetap sejalan dengan request API lain.

### Halaman Kelola Data

Tambahkan ringkasan total data yang mengikuti filter aktif.

Placeholder search:

```text
Cari pelanggan, kategori, model, kota...
```

Tambahkan dropdown terpisah:

- Bulan
- Tahun
- Wilayah

Search dan semua filter harus bisa dipadukan. Pagination memakai `total` hasil filter dari backend.

Tambahkan kontrol reset filter agar admin cepat kembali ke tampilan semua data.

### Halaman Riwayat Log Upload

Tambahkan:

- search berdasarkan nama file
- dropdown bulan
- dropdown tahun
- dropdown status dengan opsi `Semua`, `Sukses`, `Gagal`
- pagination dan tampilan total hasil filter

Search dan semua filter harus bisa dipadukan.

Aksi hapus log menyembunyikan log melalui soft delete backend. Log sukses yang disembunyikan tetap melindungi sistem dari duplicate upload.

### Halaman Manajemen Akun

Perilaku toast:

- toast sukses: hijau
- toast gagal: merah

Pesan duplicate saat create dan update harus spesifik:

- `Tidak berhasil, username telah digunakan.`
- `Tidak berhasil, email telah digunakan.`
- `Tidak berhasil, username dan email telah digunakan.`

Form modal Tambah Akun direset setelah submit, baik create berhasil maupun gagal.

Footer pagination user yang masih hardcoded harus dibuat benar atau dihapus sampai pagination asli diimplementasikan.

## Alur Data

### Upload Dengan Baris Kosong

1. Admin mengupload Excel.
2. Backend memvalidasi sheet dan header.
3. Backend melewati baris yang sepenuhnya kosong dan mencatat nomor baris Excel-nya.
4. Backend memasukkan baris transaksi yang valid.
5. Backend membuat log upload dengan `file_hash`.
6. Frontend menampilkan hasil upload, termasuk detail baris kosong.
7. Admin bisa memakai "Tambahkan Data" untuk memasukkan baris yang hilang secara manual.

### Tambah Data Manual

1. Admin membuka "Tambahkan Data".
2. Admin mengisi satu baris transaksi.
3. Frontend mengirim data ke `POST /api/v1/transaksi/`.
4. Backend memvalidasi dan menghitung `total_harga`.
5. Frontend menampilkan sukses dan me-refresh count yang relevan jika diperlukan.

### Soft Delete Log

1. Admin menekan hapus pada baris log.
2. Backend menandai log sebagai hidden/deleted.
3. Log tidak lagi muncul di riwayat.
4. Pengecekan duplicate upload tetap menyertakan log sukses yang disembunyikan.

## Error Handling

- Error validasi upload menampilkan alasan dan detail baris yang jelas.
- Upload dengan baris kosong menjadi sukses dengan detail warning, bukan gagal.
- Duplicate username/email menampilkan notifikasi merah dengan pesan spesifik.
- Gagal memuat data menampilkan pesan gagal eksplisit, bukan state tabel kosong palsu.
- Validasi backend tetap menjadi sumber kebenaran walaupun validasi frontend dilewati.

## Rencana Testing

Test backend:

- Upload Excel sukses dengan baris valid dan baris kosong yang dilewati.
- Response upload Excel memuat jumlah dan nomor baris kosong.
- Tambah transaksi manual menghitung `total_harga`.
- Update transaksi menghitung ulang `total_harga` saat qty atau harga berubah.
- Search transaksi hanya cocok ke pelanggan, kategori, model, dan kota.
- Filter transaksi menggabungkan bulan, tahun, wilayah, dan search.
- Search/filter log upload menggabungkan filename, bulan, tahun, dan status.
- Log upload sukses yang di-soft-delete tetap aktif untuk duplicate detection.
- Duplicate username/email saat create dan update mengembalikan pesan spesifik.
- Update role menolak role selain `admin` dan `owner`.
- Backend mencegah penghapusan, penonaktifan, atau demosi admin aktif terakhir.

Verifikasi frontend:

- `npm run build`
- Cek manual di browser untuk empat halaman admin:
  - Upload Data
  - Kelola Data
  - Riwayat Log Upload
  - Manajemen Akun

## Keputusan Final

Tidak ada keputusan produk yang masih terbuka. Pilihan yang sudah disetujui:

- Implementasi backend-first.
- Baris kosong pada upload dilewati dan dilaporkan.
- Manual "Tambahkan Data" memakai form transaksi lengkap satu baris.
- Filter Kelola Data memakai dropdown bulan, tahun, dan wilayah yang terpisah.
- Filter Log Upload memakai dropdown bulan, tahun, dan status yang terpisah.
- Hapus log upload memakai soft delete.
- Backend memvalidasi role saat update dan menjaga minimal satu admin aktif.
