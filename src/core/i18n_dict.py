"""Screen texts in three languages. Source language = Tetum (the texts written in the code).

Each line:  Tetum ¦ English ¦ Indonesia.  Matching ignores leading/trailing spaces (they are kept);
long texts and HTML snippets are also replaced inside bigger strings (longest first).
Keep lines in sync with the code: a Tetum text that is missing here simply stays in Tetum.
"""
from __future__ import annotations

RAW = """
Dashboard ¦ Dashboard ¦ Dasbor
Estudante ¦ Students ¦ Mahasiswa
Prezensa ¦ Attendance ¦ Kehadiran
Analiza ¦ Analytics ¦ Analitik
Relatóriu ¦ Reports ¦ Laporan
Konfigurasaun ¦ Settings ¦ Pengaturan
Check-in Estudante ¦ Student Check-in ¦ Check-in Mahasiswa
Monitorizasaun Prezensa Estudante ¦ Student Attendance Monitoring ¦ Pemantauan Kehadiran Mahasiswa
Prezente ¦ Present ¦ Hadir
Falta ¦ Absent ¦ Tidak Hadir
Atrazu ¦ Late ¦ Terlambat
Ativu ¦ Active ¦ Aktif
ATIVU ¦ ACTIVE ¦ AKTIF
HAPARA ¦ PAUSED ¦ DIJEDA
Diak ¦ Good ¦ Baik
Média ¦ Medium ¦ Sedang
Ki'ik ¦ Low ¦ Rendah
Aas ¦ High ¦ Tinggi
Tama ¦ Attended ¦ Hadir
Total ¦ Total ¦ Total
Total Estudante ¦ Total Students ¦ Total Mahasiswa
Hatudu  ¦ Showing  ¦ Menampilkan 
 to'o  ¦  to  ¦  sampai 
 husi  ¦  of  ¦  dari 
 husi estudante  ¦  of  ¦  dari 
. Esporta inklui ema hotu. ¦ . The export includes everyone. ¦ . Ekspor mencakup semua orang.
estudante ¦ students ¦ mahasiswa
rejistu ¦ records ¦ catatan
Admin ¦ Admin ¦ Admin
 (UTC+ ¦  (UTC+ ¦  (UTC+
Sistema Ativu ¦ System Online ¦ Sistem Aktif
Pipeline la ativu ¦ Pipeline offline ¦ Pipeline nonaktif
Atualiza ikus:  ¦ Last updated:  ¦ Terakhir diperbarui: 
Spark kalkula iha  ¦ Computed by Spark at  ¦ Dihitung Spark pada 
 · pájina atualiza  ¦  · page refreshed  ¦  · halaman diperbarui 
Vizaun jerál prezensa estudante ¦ Overview of student attendance ¦ Ringkasan kehadiran mahasiswa
Tendénsia Prezensa (Loron 7 Ikus) ¦ Attendance Trend (Last 7 Days) ¦ Tren Kehadiran (7 Hari Terakhir)
Tendénsia Prezensa ¦ Attendance Trend ¦ Tren Kehadiran
Status Prezensa ¦ Attendance Status ¦ Status Kehadiran
Prezensa Tuir Klase ¦ Attendance by Class ¦ Kehadiran per Kelas
Estudante 5 ho Prezensa Kiik Liu ¦ Top 5 Students (Lowest Attendance) ¦ 5 Mahasiswa dengan Kehadiran Terendah
Estudante ho Prezensa Kiik ¦ Students with Low Attendance ¦ Mahasiswa dengan Kehadiran Rendah
Seidauk iha data prezensa. ¦ No attendance data yet. ¦ Belum ada data kehadiran.
Seidauk iha enkontru klase iha loron 7 ikus ne'e. ¦ No class meetings in the last 7 days yet. ¦ Belum ada pertemuan kelas dalam 7 hari terakhir.
Seidauk iha enkontru klase iha períodu ne'e. ¦ No class meetings in this period yet. ¦ Belum ada pertemuan kelas pada periode ini.
 alerta posível prezensa tau-malu (titip absen) iha loron 7 ikus. ¦  possible proxy-attendance alert(s) in the last 7 days. ¦  kemungkinan peringatan absen titipan dalam 7 hari terakhir.
Haree alerta sira ¦ Review alerts ¦ Lihat peringatan
Taxa Prezensa ¦ Attendance Rate ¦ Tingkat Kehadiran
Taxa prezensa ¦ Attendance rate ¦ Tingkat kehadiran
Taxa ¦ Rate ¦ Tingkat
Naran ¦ Name ¦ Nama
Klase ¦ Class ¦ Kelas
Analiza padraun no informasaun prezensa ¦ Analyze attendance patterns and insights ¦ Analisis pola dan wawasan kehadiran
Detesaun prezensa tau-malu (titip absen) ¦ Proxy attendance detection ¦ Deteksi absen titipan
Padraun ne'ebé Spark hetan iha stream check-in. Ne'e sinál atu revee, la’os prova: konfirma ho estudante sira molok foti asaun. ¦ Patterns found by Spark in the check-in stream. They are signals to review, not proof: check with the students involved before taking action. ¦ Pola yang ditemukan Spark pada aliran check-in. Ini sinyal untuk ditinjau, bukan bukti: konfirmasi dengan mahasiswa terkait sebelum bertindak.
La hetan padraun suspeitu iha seleisaun ne'e. ¦ No suspicious patterns found in this selection. ¦ Tidak ada pola mencurigakan pada pilihan ini.
Nível ¦ Severity ¦ Tingkat
Padraun ¦ Pattern ¦ Pola
Saida Spark hetan ¦ What Spark found ¦ Temuan Spark
NIM involvidu ¦ NIMs involved ¦ NIM terkait
Aparellu / IP ¦ Device / IP ¦ Perangkat / IP
Haree ikus ¦ Last seen ¦ Terakhir terlihat
Telemovel ida, estudante barak ¦ One phone, several students ¦ Satu ponsel, beberapa mahasiswa
Estudante barak husi IP ida ¦ Many students from one IP ¦ Banyak mahasiswa dari satu IP
Check-in lais tuir malu ¦ Back-to-back check-ins ¦ Check-in beruntun
Tebak NIM ¦ Guessing NIMs ¦ Menebak NIM
Iha klase rua hamutuk ¦ In two classes at once ¦ Di dua kelas sekaligus
Aparellu ne'e uza ona atu check-in estudante seluk iha klase ne'e. Estudante ida-idak tenke check-in ho nia telemovel rasik. ¦ This device was already used to check in another student for this class. Each student must check in from their own phone. ¦ Perangkat ini sudah dipakai untuk check-in mahasiswa lain di kelas ini. Setiap mahasiswa harus check-in dari ponselnya sendiri.
Rejistu Prezensa ¦ Attendance Records ¦ Catatan Kehadiran
Haree no jere data prezensa ¦ View and manage attendance data ¦ Lihat dan kelola data kehadiran
Naran Estudante ¦ Student Name ¦ Nama Mahasiswa
Matéria ¦ Subject ¦ Mata Kuliah
Data ¦ Date ¦ Tanggal
Oras ¦ Time ¦ Waktu
Status ¦ Status ¦ Status
Klase Hotu ¦ All Classes ¦ Semua Kelas
Matéria Hotu ¦ All Subjects ¦ Semua Mata Kuliah
Status Hotu ¦ All Status ¦ Semua Status
Departamentu hotu ¦ All departments ¦ Semua departemen
Hotu ¦ All ¦ Semua
Importa Data ¦ Import Data ¦ Impor Data
Esporta ¦ Export ¦ Ekspor
Períodu data ¦ Date range ¦ Rentang tanggal
Hili data hahú no data remata. ¦ Pick both a start and an end date. ¦ Pilih tanggal mulai dan tanggal akhir.
La iha rejistu prezensa ba seleisaun ne'e. ¦ No attendance records for this selection. ¦ Tidak ada catatan kehadiran untuk pilihan ini.
Detallu rejistu & korreisaun ¦ Record details & correction ¦ Detail catatan & koreksi
Rejistu ¦ Record ¦ Catatan
Hili rejistu ida ¦ Choose a record ¦ Pilih satu catatan
Estudante ¦ Student ¦ Mahasiswa
Oras tama ¦ Checked in ¦ Waktu masuk
Aumenta husi ¦ Added by ¦ Ditambahkan oleh
Enderesu IP ¦ IP address ¦ Alamat IP
Hamoos rejistu ¦ Delete record ¦ Hapus catatan
Rejistu hamoos ona ¦ Record deleted ¦ Catatan dihapus
Importa data prezensa ¦ Import attendance data ¦ Impor data kehadiran
Upload CSV ho kolona **student_id, class, subject, date, time, status** (oras opsionál; status Present ka Late). Kada liña tama ba enkontru ho klase, matéria no data ne'ebá. ¦ Upload a CSV with the columns **student_id, class, subject, date, time, status** (time is optional; status is Present or Late). Each row is added to the meeting of that class, subject and date. ¦ Unggah CSV dengan kolom **student_id, class, subject, date, time, status** (waktu opsional; status Present atau Late). Setiap baris ditambahkan ke pertemuan kelas, mata kuliah, dan tanggal tersebut.
Download modelu CSV ¦ Download CSV template ¦ Unduh templat CSV
Fixeiru CSV ¦ CSV file ¦ Berkas CSV
Hetan liña  ¦ Found rows:  ¦ Baris ditemukan: 
Importa ¦ Import ¦ Impor
Rejistu  ¦ Records  ¦ Catatan 
 importa ona. ¦  imported. ¦  diimpor.
 importa ona ¦  imported ¦  diimpor
Liña  ¦ Line  ¦ Baris 
 la tama: ¦  skipped: ¦  dilewati:
Kolona la iha:  ¦ Missing column(s):  ¦ Kolom tidak ada: 
. Presiza:  ¦ . Required:  ¦ . Wajib: 
 (oras opsionál). ¦  (time is optional). ¦  (waktu opsional).
: Falta kalkula automátiku, la presiza importa. ¦ : Absent is calculated automatically, nothing to import. ¦ : Tidak Hadir dihitung otomatis, tidak perlu diimpor.
: status tenke Prezente (Present) ka Atrazu (Late). ¦ : status must be Present or Late. ¦ : status harus Present atau Late.
: data ' ¦ : date ' ¦ : tanggal '
' la forma YYYY-MM-DD. ¦ ' is not YYYY-MM-DD. ¦ ' bukan format YYYY-MM-DD.
: la iha enkontru ba  ¦ : no meeting for  ¦ : tidak ada pertemuan untuk 
: oras ' ¦ : time ' ¦ : waktu '
' la forma HH:MM. ¦ ' is not HH:MM. ¦ ' bukan format HH:MM.
: estudante  ¦ : student  ¦ : mahasiswa 
 la iha iha lista estudante. ¦  is not in the student list. ¦  tidak ada dalam daftar mahasiswa.
Estudante ¦ Student ¦ Mahasiswa
Aumenta Estudante ¦ Add Student ¦ Tambah Mahasiswa
Aumenta estudante ¦ Add student ¦ Tambah mahasiswa
Edita Estudante ¦ Edit Student ¦ Ubah Mahasiswa
Detallu Estudante ¦ Student details ¦ Detail Mahasiswa
Jere data estudante ¦ Manage student data ¦ Kelola data mahasiswa
Buka tuir naran ka ID... ¦ Search by name or ID... ¦ Cari berdasarkan nama atau ID...
Emél ¦ Email ¦ Email
Emél:  ¦ Email:  ¦ Email: 
Asaun ¦ Action ¦ Aksi
Naran kompletu * ¦ Full name * ¦ Nama lengkap *
ID Estudante (NIM) * ¦ Student ID (NIM) * ¦ ID Mahasiswa (NIM) *
ID Estudante (NIM) ¦ Student ID (NIM) ¦ ID Mahasiswa (NIM)
Sexu ¦ Gender ¦ Jenis kelamin
Mane ¦ Male ¦ Laki-laki
Feto ¦ Female ¦ Perempuan
Fakuldade ¦ Faculty ¦ Fakultas
Departamentu ¦ Department ¦ Departemen
Turno ¦ Cohort ¦ Angkatan
ez. CS ¦ e.g. CS ¦ mis. CS
ez. 2024 ¦ e.g. 2024 ¦ mis. 2024
naran@example.com ¦ name@example.com ¦ nama@example.com
Rai mudansa ¦ Save changes ¦ Simpan perubahan
 aumenta ona ¦  added ¦  ditambahkan
 aumenta ona ( ¦  added ( ¦  ditambahkan (
Estudante atualiza ona ¦ Student updated ¦ Mahasiswa diperbarui
Klase ne'ebé tama ¦ Classes attended ¦ Kelas yang dihadiri
Seidauk iha prezensa ne'ebé rejista. ¦ No attendance recorded yet. ¦ Belum ada kehadiran tercatat.
Oras Tama ¦ Checked in ¦ Waktu Masuk
Hili estudante atu haree ka edita ¦ Choose a student to view or edit ¦ Pilih mahasiswa untuk dilihat atau diubah
Haree ¦ View ¦ Lihat
Edita ¦ Edit ¦ Ubah
Seidauk iha estudante. Uza <b>Aumenta Estudante</b> atu rejista dahuluk. ¦ No students yet. Use <b>Add Student</b> to register the first one. ¦ Belum ada mahasiswa. Gunakan <b>Tambah Mahasiswa</b> untuk mendaftarkan yang pertama.
La iha data ¦ No data ¦ Tidak ada data
Relatóriu Prezensa ¦ Attendance Reports ¦ Laporan Kehadiran
Relatóriu Prezensa -  ¦ Attendance Report -  ¦ Laporan Kehadiran - 
Kria no esporta relatóriu prezensa ¦ Generate and export attendance reports ¦ Buat dan ekspor laporan kehadiran
Kria Relatóriu ¦ Generate Report ¦ Buat Laporan
Filtru muda ona - klik **Kria Relatóriu** atu atualiza relatóriu. ¦ Filters changed - click **Generate Report** to update the report. ¦ Filter berubah - klik **Buat Laporan** untuk memperbarui laporan.
Rezumu Relatóriu ¦ Report Summary ¦ Ringkasan Laporan
Vista Relatóriu ¦ Report Preview ¦ Pratinjau Laporan
Seidauk iha data relatóriu. ¦ No report data yet. ¦ Belum ada data laporan.
Esporta PDF ¦ Export PDF ¦ Ekspor PDF
Esporta Excel ¦ Export Excel ¦ Ekspor Excel
Rezumu ¦ Summary ¦ Ringkasan
Valór ¦ Value ¦ Nilai
Total estudante:  ¦ Total students:  ¦ Total mahasiswa: 
 &nbsp;|&nbsp; Prezente:  ¦  &nbsp;|&nbsp; Present:  ¦  &nbsp;|&nbsp; Hadir: 
 &nbsp;|&nbsp; Falta:  ¦  &nbsp;|&nbsp; Absent:  ¦  &nbsp;|&nbsp; Tidak Hadir: 
 &nbsp;|&nbsp; Atrazu:  ¦  &nbsp;|&nbsp; Late:  ¦  &nbsp;|&nbsp; Terlambat: 
 &nbsp;|&nbsp; Taxa prezensa:  ¦  &nbsp;|&nbsp; Attendance rate:  ¦  &nbsp;|&nbsp; Tingkat kehadiran: 
La iha data prezensa ba seleisaun ne'e. ¦ No attendance data for this selection. ¦ Tidak ada data kehadiran untuk pilihan ini.
Relatóriu ¦ Report ¦ Laporan
Estudante ¦ Students ¦ Mahasiswa
Konfigurasaun sistema ¦ System configuration ¦ Konfigurasi sistem
Jerál ¦ General ¦ Umum
Database ¦ Database ¦ Basis data
Konfigurasaun Jerál ¦ General Settings ¦ Pengaturan Umum
Naran Sistema ¦ System Name ¦ Nama Sistem
Tinan Akadémiku ¦ Academic Year ¦ Tahun Akademik
Status Prezensa Default ¦ Default Attendance Status ¦ Status Kehadiran Default
Status ne'ebé hili uluk bainhira aumenta estudante ba enkontru ho liman. ¦ Pre-selected status when you add a student to a meeting by hand. ¦ Status yang dipilih awal saat menambah mahasiswa ke pertemuan secara manual.
Lian ¦ Language ¦ Bahasa
Rai Konfigurasaun ¦ Save Settings ¦ Simpan Pengaturan
Konfigurasaun rai ona ¦ Settings saved ¦ Pengaturan disimpan
Informasaun Database ¦ Database Information ¦ Informasi Basis Data
Informasaun Sistema ¦ System Information ¦ Informasi Sistem
Tipu ¦ Type ¦ Tipe
Fixeiru ¦ File ¦ Berkas
Boot ¦ Size ¦ Ukuran
Fatin ¦ Location ¦ Lokasi
lokál ¦ local ¦ lokal
Konekta ¦ Connected ¦ Terhubung
La konekta ¦ Not connected ¦ Tidak terhubung
Versaun ¦ Version ¦ Versi
Atualiza Ikus ¦ Last Update ¦ Pembaruan Terakhir
Zona oras ¦ Time zone ¦ Zona waktu
Dezenvolvedór ¦ Developer ¦ Pengembang
Grupo 1 · DIT 2026 ¦ Group 1 · DIT 2026 ¦ Kelompok 1 · DIT 2026
Matéria kria hamutuk ho kursu iha tab **Klase**. Lista ne'e hatudu saida mak iha to'o agora. ¦ A subject is created together with its course on the **Classes** tab. This list shows what exists so far. ¦ Mata kuliah dibuat bersama kursusnya di tab **Kelas**. Daftar ini menampilkan yang sudah ada.
Seidauk iha matéria. ¦ No subjects yet. ¦ Belum ada mata kuliah.
Enkontru ¦ Meetings ¦ Pertemuan
Enkontru dahuluk ¦ First meeting ¦ Pertemuan pertama
Enkontru ikus ¦ Last meeting ¦ Pertemuan terakhir
Backup ¦ Backup ¦ Cadangan
Download kópia data. Rai backup iha fatin seguru: ne'e iha naran no NIM estudante. ¦ Download a copy of your data. Keep backups somewhere safe: they contain student names and NIMs. ¦ Unduh salinan data. Simpan cadangan di tempat aman: berisi nama dan NIM mahasiswa.
Download database prezensa ¦ Download attendance database ¦ Unduh basis data kehadiran
Download lista estudante (CSV) ¦ Download student list (CSV) ¦ Unduh daftar mahasiswa (CSV)
Pipeline streaming (Kafka + Spark) ¦ Streaming pipeline (Kafka + Spark) ¦ Pipeline streaming (Kafka + Spark)
Dezativa ¦ Disabled ¦ Dinonaktifkan
Koneksaun Kafka ¦ Kafka connection ¦ Koneksi Kafka
La ativu ¦ Offline ¦ Nonaktif
Evento iha outbox ¦ Events in outbox ¦ Event di outbox
 hein) ¦  waiting) ¦  menunggu)
Rezultadu Spark ¦ Spark output ¦ Hasil Spark
Topiku Kafka ¦ Kafka topic ¦ Topik Kafka
Hahú Kafka & Spark ¦ Start Kafka & Spark ¦ Mulai Kafka & Spark
Hahú Kafka no Spark iha background... ¦ Starting Kafka and Spark in the background... ¦ Memulai Kafka dan Spark di latar belakang...
Para Kafka & Spark ¦ Stop Kafka & Spark ¦ Hentikan Kafka & Spark
Dashboard para atualiza to'o ita hahú fali. Check-in kontinua servisu no prosesa bainhira pipeline fila fali. La iha data ne'ebé hamoos. ¦ The dashboard stops updating until you start them again. Check-ins keep working and are processed when the pipeline is back. No data is deleted. ¦ Dasbor berhenti diperbarui sampai Anda menyalakannya lagi. Check-in tetap berjalan dan diproses saat pipeline kembali. Tidak ada data yang dihapus.
Para agora ¦ Stop now ¦ Hentikan sekarang
Hapara container sira... ¦ Stopping containers... ¦ Menghentikan container...
Haruka fali evento hotu ba Kafka ¦ Resend all events to Kafka ¦ Kirim ulang semua event ke Kafka
Haruka fali hotu ¦ Resend everything ¦ Kirim ulang semuanya
 hein hodi haruka ba Kafka. ¦  waiting to be sent to Kafka. ¦  menunggu dikirim ke Kafka.
Evento  ¦ Events  ¦ Event 
Haruka  ¦ Sending  ¦ Mengirim 
La ativu ·  ¦ Offline ·  ¦ Nonaktif · 
Seidauk iha ¦ None yet ¦ Belum ada
hein evento dahuluk ¦ waiting for first events ¦ menunggu event pertama
 evento · kalkula iha  ¦  events · computed in  ¦  event · dihitung dalam 
 evento · topiku <code> ¦  events · topic <code> ¦  event · topik <code>
 · heartbeat  ¦  · heartbeat  ¦  · heartbeat 
 segundu liu ona ¦  s ago ¦  dtk lalu
 minutu liu ona ¦  min ago ¦  mnt lalu
 oras liu ona ¦  h ago ¦  jam lalu
nunka ¦ never ¦ tidak pernah
 Check-in rai durante ne'e no prosesa bainhira Spark ativu. ¦  Check-ins are saved meanwhile and processed once Spark is up. ¦  Check-in tetap disimpan dan diproses saat Spark aktif.
 Jere pipeline iha **Konfigurasaun**. ¦  Manage the pipeline on **Settings**. ¦  Kelola pipeline di **Pengaturan**.
⏳ Kafka ativu; Spark seidauk hahú ho kompletu (hahú dahuluk download konektór Kafka no presiza minutu 1-2). ¦ ⏳ Kafka is running; Spark is still starting (the first start downloads its Kafka connector and warms up, about 1-2 minutes). ¦ ⏳ Kafka berjalan; Spark masih mulai (start pertama mengunduh konektor Kafka, sekitar 1-2 menit).
Klase & Link ¦ Classes & Links ¦ Kelas & Tautan
Orariu semestre no sesaun úniku, ida-idak ho QR rasik ¦ Semester schedules and one-off sessions, each with its own QR code ¦ Jadwal semester dan sesi tunggal, masing-masing dengan QR sendiri
Kursu semestre ¦ Semester courses ¦ Kursus semester
📅 Kursu semestre ¦ 📅 Semester courses ¦ 📅 Kursus semester
🔗 Sesaun úniku ¦ 🔗 Single sessions ¦ 🔗 Sesi tunggal
Sesaun úniku foun ¦ New single session ¦ Sesi tunggal baru
Ba enkontru ida de'it, ez. klase kompensasaun ka seminár. ¦ For one meeting only, e.g. a make-up class or a seminar. ¦ Untuk satu pertemuan saja, mis. kelas pengganti atau seminar.
Naran matéria/kursu * ¦ Course name * ¦ Nama mata kuliah/kursus *
Klase / grupu * ¦ Class / group * ¦ Kelas / grup *
ez. Big Data ¦ e.g. Big Data Analytics ¦ mis. Big Data Analytics
ez. Data Mining ¦ e.g. Data Mining ¦ mis. Data Mining
ez. CS-2024-A ¦ e.g. CS-2024-A ¦ mis. CS-2024-A
ez. Dr. Maria Soares ¦ e.g. Dr. Maria Soares ¦ mis. Dr. Maria Soares
ez. Lab 2 ¦ e.g. Lab 2 ¦ mis. Lab 2
Dosente ¦ Lecturer ¦ Dosen
Sala ¦ Room ¦ Ruang
Hahú ¦ Start ¦ Mulai
Remata ¦ End ¦ Selesai
Atrazu depois (minutu) ¦ Late after (min) ¦ Terlambat setelah (menit)
Atrazu depois ¦ Late after ¦ Terlambat setelah
Limita ba departamentu ¦ Restrict to departments ¦ Batasi ke departemen
Simu de'it durante oras klase ¦ Only accept during class time ¦ Hanya terima saat jam kelas
Check-in loke minutu  ¦ Check-in opens  ¦ Check-in dibuka 
 molok hahú no taka iha oras remata. ¦  min before the start time and closes at the end time. ¦  menit sebelum mulai dan ditutup saat jam selesai.
 molok enkontru kada no taka iha oras remata. ¦  min before each meeting and closes at its end time. ¦  menit sebelum tiap pertemuan dan ditutup saat jam selesai.
Kria klase & halo link ¦ Create class & generate link ¦ Buat kelas & tautan
Klase kria ona. Fahe link ne'e:  ¦ Class created. Share this link:  ¦ Kelas dibuat. Bagikan tautan ini: 
Aumenta estudante ho liman (NIM) ¦ Add student manually (NIM) ¦ Tambah mahasiswa manual (NIM)
Aumenta estudante ho liman ¦ Add a student manually ¦ Tambah mahasiswa manual
Aumenta ba enkontru ¦ Add to meeting ¦ Tambah ke pertemuan
Aumenta ¦ Add ¦ Tambah
Konfirma NIM - la hetan iha lista estudante. ¦ Confirm your NIM - not found in student list. ¦ Konfirmasi NIM - tidak ada dalam daftar mahasiswa.
NIM la hetan iha lista estudante. ¦ NIM not found in the student list. ¦ NIM tidak ada dalam daftar mahasiswa.
Kódigu klase & link check-in ¦ Class code & check-in link ¦ Kode kelas & tautan check-in
Kódigu klase & link permanente (semestre tomak) ¦ Class code & permanent link (whole semester) ¦ Kode kelas & tautan permanen (satu semester)
Kódigu klase ¦ Class code ¦ Kode kelas
<span>Kódigu klase</span> ¦ <span>Class code</span> ¦ <span>Kode kelas</span>
Link ka QR de'it mak estudante uza atu halo check-in. ¦ Students use the link or QR code to check in. ¦ Mahasiswa memakai tautan atau kode QR untuk check-in.
Estudante uza link ka scan QR atu halo check-in. ¦ Students use the link or scan the QR code to check in. ¦ Mahasiswa memakai tautan atau memindai QR untuk check-in.
La iha limite oras ¦ No time limit ¦ Tanpa batas waktu
Taka link ¦ Close link ¦ Tutup tautan
Loke fali link ¦ Reopen link ¦ Buka kembali tautan
Link foun ¦ New link ¦ Tautan baru
Link tuan la servisu tan ¦ Old link stops working ¦ Tautan lama tidak berfungsi lagi
Link/QR tuan la servisu tan ¦ Old link/QR stops working ¦ Tautan/QR lama tidak berfungsi lagi
Loke pájina ¦ Open page ¦ Buka halaman
Hamoos ¦ Delete ¦ Hapus
Konfirma hamoos ¦ Confirm delete ¦ Konfirmasi hapus
Hamoos klase ne'e no rejistu prezensa hotu. ¦ Deletes this class and all its attendance records. ¦ Menghapus kelas ini dan semua catatan kehadirannya.
Hamoos kursu, enkontru hotu no rejistu prezensa hotu. ¦ Deletes the course, all its meetings and all their attendance records. ¦ Menghapus kursus, semua pertemuan, dan semua catatan kehadirannya.
Scan atu check-in ¦ Scan to check in ¦ Pindai untuk check-in
Download QR ¦ Download QR ¦ Unduh QR
Download CSV ¦ Download CSV ¦ Unduh CSV
Seidauk check-in ( ¦ Not yet checked in ( ¦ Belum check-in (
Prezente ( ¦ Present ( ¦ Hadir (
Seidauk iha check-in. ¦ No check-ins yet. ¦ Belum ada check-in.
Seidauk iha sesaun úniku. Kria ida iha leten. ¦ No single sessions yet. Create one above. ¦ Belum ada sesi tunggal. Buat satu di atas.
Buka klase ¦ Search classes ¦ Cari kelas
Kursu, klase, dosente... ¦ Course, class, lecturer... ¦ Kursus, kelas, dosen...
 prezente · kódigu  ¦  present · code  ¦  hadir · kode 
 · kódigu  ¦  · code  ¦  · kode 
La iha klase ne'ebé kompatível ho filtru. ¦ No classes match the filter. ¦ Tidak ada kelas yang cocok dengan filter.
Link ba ` ¦ Links point to ` ¦ Tautan mengarah ke `
`. Telemovel estudante tenke iha Wi-Fi hanesan ho komputadór ne'e (define PUBLIC_BASE_URL atu uza domíniu públiku). ¦ `. Students' phones must be on the same Wi-Fi as this computer (set PUBLIC_BASE_URL to use a public domain instead). ¦ `. Ponsel mahasiswa harus berada di Wi-Fi yang sama dengan komputer ini (atur PUBLIC_BASE_URL untuk memakai domain publik).
Loke ¦ Open ¦ Buka
Tuir mai ¦ Upcoming ¦ Akan datang
Taka ¦ Closed ¦ Ditutup
Kansela ¦ Cancelled ¦ Dibatalkan
Kursu semestre foun ¦ New semester course ¦ Kursus semester baru
Define orariu semana dala ida de'it. Enkontru hotu iha semestre kria automátiku; check-in loke minutu  ¦ Set the weekly schedule once. Every meeting of the semester is created automatically; check-in opens  ¦ Atur jadwal mingguan sekali. Semua pertemuan semester dibuat otomatis; check-in dibuka 
Loron semana * ¦ Days of the week * ¦ Hari dalam seminggu *
Semestre hahú ¦ Semester starts ¦ Semester mulai
Semestre remata ¦ Semester ends ¦ Semester selesai
Kria orariu semestre ¦ Create semester schedule ¦ Buat jadwal semester
Kria enkontru hotu... ¦ Creating all meetings... ¦ Membuat semua pertemuan...
: enkontru  ¦ :  meetings  ¦ :  pertemuan 
 kria ona ( ¦  created ( ¦  dibuat (
). QR ida ba semestre tomak. ¦ ). One QR for the whole semester. ¦ ). Satu QR untuk satu semester.
Orariu ¦ Schedule ¦ Jadwal
Semestre ¦ Semester ¦ Semester
 hala'o /  ¦  held /  ¦  berlangsung / 
Agora / tuir mai ¦ Current / next ¦ Sekarang / berikutnya
Hapara kursu ¦ Pause course ¦ Jeda kursus
Hapara check-in ba enkontru hotu ¦ Stops check-in for all meetings ¦ Menghentikan check-in untuk semua pertemuan
Kontinua kursu ¦ Resume course ¦ Lanjutkan kursus
QR hanesan ba enkontru hotu ¦ Same QR every meeting ¦ QR sama untuk semua pertemuan
Bazeia ba enkontru ** ¦ Based on ** ¦ Berdasarkan **
Bazeia ba enkontru **  ¦ Based on **  ¦ Berdasarkan ** 
** ne'ebé hala'o ona (enkontru kansela la konta). Atrazu konta nu'udar tama no hatudu separadu. ¦ ** meeting(s) held so far (cancelled meetings are not counted). Late counts as attended and is shown separately. ¦ ** pertemuan sudah berlangsung (pertemuan dibatalkan tidak dihitung). Terlambat dihitung hadir dan ditampilkan terpisah.
Seidauk iha enkontru ne'ebé hala'o. ¦ No meeting has taken place yet. ¦ Belum ada pertemuan berlangsung.
Tuir oras ¦ On time ¦ Tepat waktu
Dep. ¦ Dept ¦ Dep.
Download relatóriu nota (CSV) ¦ Download grade report (CSV) ¦ Unduh laporan nilai (CSV)
Loron ¦ Day ¦ Hari
Enkontru ¦ Meeting ¦ Pertemuan
Enkontru kansela ona ¦ Meeting cancelled ¦ Pertemuan dibatalkan
Kansela enkontru ¦ Cancel meeting ¦ Batalkan pertemuan
Kansela enkontru (ez. feriadu) ¦ Cancel a meeting (e.g. holiday) ¦ Batalkan pertemuan (mis. libur)
La iha enkontru tuir mai ¦ No upcoming meeting ¦ Tidak ada pertemuan berikutnya
Enkontru kansela la konta iha nota prezensa. La bele fila fali. ¦ A cancelled meeting is not counted in the attendance grade. This cannot be undone. ¦ Pertemuan yang dibatalkan tidak dihitung dalam nilai kehadiran. Tidak dapat dibatalkan kembali.
Download log check-in (CSV) ¦ Download check-in log (CSV) ¦ Unduh log check-in (CSV)
Data enkontru ¦ Meeting date ¦ Tanggal pertemuan
Klase hahú ¦ Class starts ¦ Kelas mulai
Check-in iha ¦ Checked in at ¦ Check-in pada
Seidauk iha kursu semestre. Kria dahuluk iha leten. ¦ No semester course yet. Create the first one above. ¦ Belum ada kursus semester. Buat yang pertama di atas.
 · enkontru  ¦  · meeting  ¦  · pertemuan 
📊 Nota prezensa ¦ 📊 Attendance grade ¦ 📊 Nilai kehadiran
🕒 Log check-in (data & oras) ¦ 🕒 Check-in log (date & time) ¦ 🕒 Log check-in (tanggal & waktu)
🗓️ Enkontru ¦ 🗓️ Meetings ¦ 🗓️ Pertemuan
 course(s) ¦  course(s) ¦  kursus
Check-in loke iha  ¦ Check-in opens at  ¦ Check-in dibuka pada 
Check-in remata iha  ¦ Check-in ended at  ¦ Check-in berakhir pada 
Check-in ba klase ne'e remata iha  ¦ Check-in for this class ended at  ¦ Check-in untuk kelas ini berakhir pada 
Check-in seidauk loke ¦ Check-in not open ¦ Check-in belum dibuka
Check-in ona ¦ Already checked in ¦ Sudah check-in
Check-in estudante ¦ Student check-in ¦ Check-in mahasiswa
Check-in prezensa ¦ Attendance check-in ¦ Check-in kehadiran
Susesu ¦ Success ¦ Berhasil
Ita-nia prezensa rejista nu'udar  ¦ Your attendance is recorded as  ¦ Kehadiran Anda tercatat sebagai 
Konfirma ita-nia NIM ¦ Confirm your NIM ¦ Konfirmasi NIM Anda
NIM ne'e la hetan iha lista estudante. Verifika no koko fali, ka kontaktu ita-nia dosente. ¦ We could not find this NIM in the student list. Check it and try again, or contact your lecturer. ¦ NIM ini tidak ditemukan dalam daftar mahasiswa. Periksa dan coba lagi, atau hubungi dosen Anda.
La rejista ¦ Not recorded ¦ Tidak tercatat
Link la válidu ¦ Link not valid ¦ Tautan tidak valid
Link prezensa ne'e la válidu ka troka ona. Husu link foun ba ita-nia dosente. ¦ This attendance link is invalid or has been replaced. Ask your lecturer for the current link. ¦ Tautan kehadiran ini tidak valid atau sudah diganti. Minta tautan terbaru ke dosen Anda.
Prepara check-in ba aparellu ne'e... Se mensajen ne'e kontinua, permite cookies ba sítiu ne'e iha browser no karrega fali pájina. ¦ Preparing check-in for this device... If this message stays, allow cookies for this site in your browser and reload the page. ¦ Menyiapkan check-in untuk perangkat ini... Jika pesan ini tetap muncul, izinkan cookie untuk situs ini di browser lalu muat ulang halaman.
Admin taka ona link klase ne'e. ¦ This class link has been closed by the admin. ¦ Tautan kelas ini sudah ditutup oleh admin.
Enkontru ne'e kansela ona. ¦ This meeting was cancelled. ¦ Pertemuan ini dibatalkan.
Enkontru tuir mai ¦ Next meeting ¦ Pertemuan berikutnya
Semestre remata ona ¦ Semester finished ¦ Semester selesai
Enkontru hotu iha kursu ne'e remata ona. ¦ All meetings of this course are over. ¦ Semua pertemuan kursus ini sudah selesai.
Hakerek ita-nia NIM iha ne'e ¦ Type your NIM here ¦ Ketik NIM Anda di sini
Check-in  ✓ ¦ Check in  ✓ ¦ Check-in  ✓
Verifika ita-nia NIM... ¦ Checking your NIM... ¦ Memeriksa NIM Anda...
Bem-vindu! ¦ Welcome! ¦ Selamat datang!
Scan kódigu QR ne'ebé dosente hatudu. ¦ Scan the QR code shown by your lecturer. ¦ Pindai kode QR yang ditampilkan dosen Anda.
Kódigu klase la hetan. Verifika ho dosente. ¦ Class code not found. Check the code with your lecturer. ¦ Kode kelas tidak ditemukan. Periksa dengan dosen Anda.
Kontinua → ¦ Continue → ¦ Lanjut →
📘 Enkontru  ¦ 📘 Meeting  ¦ 📘 Pertemuan 
Favór hatama ita-nia NIM. ¦ Please enter your NIM. ¦ Silakan masukkan NIM Anda.
Ita check-in ona iha  ¦ You already checked in at  ¦ Anda sudah check-in pada 
Ita check-in ona. ¦ You already checked in. ¦ Anda sudah check-in.
Klase ne'e ba estudante  ¦ This class is for  ¦ Kelas ini untuk mahasiswa 
 de'it. ¦  students only. ¦  saja.
Tuir oras to'o <b> ¦ On time for <b> ¦ Tepat waktu untuk <b>
<b>Atrazu</b> check-in agora ¦ <b>Late</b> check-ins now ¦ Check-in <b>terlambat</b> sekarang
Taka iha <b> ¦ Closes in <b> ¦ Ditutup dalam <b>
<b>Taka ona</b> ¦ <b>Closed</b> ¦ <b>Ditutup</b>
Fakuldade ¦ Faculty ¦ Fakultas
Oras check-in ¦ Check-in time ¦ Waktu check-in
Segunda ¦ Monday ¦ Senin
Tersa ¦ Tuesday ¦ Selasa
Kuarta ¦ Wednesday ¦ Rabu
Kinta ¦ Thursday ¦ Kamis
Sexta ¦ Friday ¦ Jumat
Sábadu ¦ Saturday ¦ Sabtu
Domingu ¦ Sunday ¦ Minggu
Naran kursu no naran klase obrigatóriu. ¦ Course name and class name are required. ¦ Nama kursus dan nama kelas wajib diisi.
Hili loron semana ida ka liu. ¦ Choose at least one day of the week. ¦ Pilih minimal satu hari dalam seminggu.
Oras remata tenke depois oras hahú. ¦ End time must be after start time. ¦ Jam selesai harus setelah jam mulai.
Data remata semestre tenke depois data hahú. ¦ The semester end date must be after the start date. ¦ Tanggal akhir semester harus setelah tanggal mulai.
La iha enkontru iha loron ne'ebé hili entre data sira ne'e. ¦ No meeting falls on the chosen days between those dates. ¦ Tidak ada pertemuan pada hari yang dipilih di antara tanggal tersebut.
Ne'e sei kria enkontru  ¦ That would create  ¦ Ini akan membuat 
; favór hili períodu badak liu. ¦  meetings; please choose a shorter period. ¦  pertemuan; pilih periode yang lebih singkat.
Naran sistema labele mamuk. ¦ System name cannot be empty. ¦ Nama sistem tidak boleh kosong.
Tinan akadémiku labele mamuk. ¦ Academic year cannot be empty. ¦ Tahun akademik tidak boleh kosong.
Status prezensa default tenke Prezente ka Atrazu. ¦ Default attendance status must be Present or Late. ¦ Status kehadiran default harus Hadir atau Terlambat.
Lian la apoiu. ¦ Unsupported language. ¦ Bahasa tidak didukung.
Naran uzuáriu obrigatóriu. ¦ Username is required. ¦ Nama pengguna wajib diisi.
"""

def _parse() -> dict[str, tuple[str, str]]:
    out: dict[str, tuple[str, str]] = {}
    for line in RAW.strip("\n").split("\n"):
        parts = line.split(" ¦ ")
        if len(parts) != 3:
            continue
        out.setdefault(parts[0], (parts[1], parts[2]))  # first line wins
    return out


# Tetum text -> (English, Indonesia). Keys keep their own spaces so word fragments of f-strings match exactly.
DICT = _parse()
