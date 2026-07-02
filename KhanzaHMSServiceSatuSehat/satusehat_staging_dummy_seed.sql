/*
  SEED KHANZA -> ERPNEXT SATUSEHAT - DATA AKTIF: 2026/06/07/997001

  Kenapa pakai 997001?
  - frmUtama.java saat ini hardcoded berjalan pada range 2026-06-07.
  - Berarti Java memang memilih data aktif pada tanggal 2026-06-07.
  - Batch tanggal sebelumnya sudah pernah dipakai, jadi batch ini dibuat fresh.

  Tujuan:
  - Membuat hanya 2026/06/07/997001 yang berada pada tanggal 2026-06-07.
  - Mengisi source row untuk Encounter, Condition, Procedure, Observation TTV,
    CarePlan/diet, Radiologi, Lab PK, Lab MB, Resep/Obat/Dispense/Medication Statement,
    Questionnaire/Telaah Farmasi, mapping obat/vaksin/lab/lokasi/depo.
  - Mengisi data finance untuk simulasi dashboard audit:
    billing item, nota jalan, piutang, pembayaran piutang, margin obat,
    biaya lab, dan biaya radiologi.
  - Tidak memakai DELIMITER, PROCEDURE, atau transaction besar supaya tidak gagal diam-diam.
  - Reset cache satu_sehat_* khusus 997001 supaya test ulang tetap terkirim fresh.
  - Fungsi AllergyIntolerance juga butuh file cache/alergisatusehat.iyem.

  Cara pakai:
  1. Stop service Java Khanza SatuSehat.
  2. Jalankan file ini sebagai Execute SQL Script pada DB SIK/Khanza yang dipakai Java.
  3. Pastikan hasil SELECT akhir:
     ACTIVE_RALAN_HARUS_1 = 1
     ACTIVE_RALAN_FINAL_HARUS_CUMA_997001 hanya menampilkan 2026/06/07/997001.
  4. Jalankan service Java range 2026-06-07 s.d. 2026-06-07.
*/

SET NAMES latin1;

SET @SATUSEHAT_ORGANIZATION_ID = 'f16a1413-b20d-4f58-b14c-2bd8a9d3e989';
SET @SATUSEHAT_LOCATION_ID_U0003 = 'd88c8bd6-1a64-4966-a096-f3d4f024851a';
SET @SATUSEHAT_LOCATION_ID_INT = 'b3131b1e-50f7-4bc0-b6b7-1a8971fba6b2';

SET @NO_RAWAT = '2026/06/07/997001';
SET @NO_RAWAT_NUM = '20260607997001';
SET @TGL = '2026-06-07';
SET @JAM = '10:10:00';
SET @NO_REG = '997';
SET @NO_RESEP = '20260607997001';
SET @RAD_ORDER = 'R20260607997001';
SET @LAB_ORDER = 'PK997001';
SET @LABMB_ORDER = 'MB997001';
SET @BATCH_NO = 'B997001';
SET @FAKTUR_NO = 'F997001';
SET @MEDICATION_LOCAL_ID = LOWER(CONCAT(SUBSTRING(@NO_RAWAT_NUM, 1, 8), '-0000-4000-8000-', LPAD(@NO_REG, 12, '0')));

SET @RM = '000006';
SET @NIK_PASIEN = '9271060312000001';
SET @KD_DOKTER = 'D0000004';
SET @NIK_DOKTER = '3508162501870001';
SET @KD_POLI = 'U0003';


SET FOREIGN_KEY_CHECKS = 0;

/*
  Reset cache paling awal. Log "ada 1 data, tapi tidak ada yang siap POST"
  muncul saat baris di satu_sehat_encounter masih ada, sehingga frmUtama
  tidak pernah memanggil ApiSatuSehat.getRest() untuk Encounter.
*/
DELETE FROM satu_sehat_encounter WHERE no_rawat = @NO_RAWAT;

/* Sembunyikan data lain di tanggal test. Beberapa fungsi tidak cek status_bayar. */
UPDATE reg_periksa
SET
  tgl_registrasi = DATE_SUB(@TGL, INTERVAL 1 DAY),
  status_bayar = 'Belum Bayar'
WHERE tgl_registrasi = @TGL
  AND no_rawat <> @NO_RAWAT;


/* Guard tambahan: batch lama wajib mati. Kalau ini tidak berubah, berarti SQL tidak jalan di DB yang dipakai Java. */
UPDATE reg_periksa
SET status_bayar = 'Belum Bayar'
WHERE no_rawat LIKE '2026/06/01/940%'
   OR no_rawat LIKE '2026/06/01/950%'
   OR no_rawat LIKE '2026/06/01/960%'
   OR no_rawat LIKE '2026/06/01/970%'
   OR no_rawat LIKE '2026/06/01/980%'
   OR no_rawat LIKE '2026/06/01/990%'
   OR no_rawat LIKE '2026/06/01/991%'
   OR no_rawat LIKE '2026/06/01/970%'
   OR no_rawat LIKE '2026/06/02/940%'
   OR no_rawat LIKE '2026/06/02/950%'
   OR no_rawat LIKE '2026/06/02/960%'
   OR no_rawat LIKE '2026/06/02/970%'
   OR no_rawat LIKE '2026/06/02/980%'
   OR no_rawat LIKE '2026/06/02/990%'
   OR no_rawat LIKE '2026/06/02/991%'
   OR no_rawat LIKE '2026/06/03/940%'
   OR no_rawat LIKE '2026/06/03/950%'
   OR no_rawat LIKE '2026/06/03/960%'
   OR no_rawat LIKE '2026/06/03/970%'
   OR no_rawat LIKE '2026/06/03/980%'
   OR no_rawat LIKE '2026/06/03/990%'
   OR no_rawat LIKE '2026/06/03/991%'
   OR no_rawat LIKE '2026/06/04/992%'
   OR no_rawat LIKE '2026/06/05/993%'
   OR no_rawat LIKE '2026/06/06/994%'
   OR no_rawat LIKE '2026/06/06/995%'
   OR no_rawat LIKE '2026/06/06/996%';


/* Guard keras: pastikan batch lama mati dan batch aktif yang akan dipakai adalah 997001. */
UPDATE reg_periksa
SET status_bayar = 'Belum Bayar'
WHERE no_rawat IN (
  '2026/06/01/940001','2026/06/01/940002','2026/06/01/940003','2026/06/01/940004',
  '2026/06/01/940005','2026/06/01/940006','2026/06/01/940007','2026/06/01/940008',
  '2026/06/01/940009','2026/06/01/940010','2026/06/01/940011','2026/06/01/940012',
  '2026/06/01/940013','2026/06/01/950001','2026/06/01/980001',
  '2026/06/01/990001','2026/06/01/991001','2026/06/01/992001','2026/06/01/993001','2026/06/01/980001',
  '2026/06/02/940001','2026/06/02/950001','2026/06/02/960001',
  '2026/06/02/970001','2026/06/02/980001','2026/06/02/990001',
  '2026/06/02/991001','2026/06/02/992001','2026/06/02/993001','2026/06/03/991001','2026/06/04/992001',
  '2026/06/05/993001','2026/06/06/994001','2026/06/06/995001','2026/06/06/996001'
);


/* ============================================================
   1. Master pasien, dokter, lokasi, organisasi
   ============================================================ */

UPDATE pasien
SET
  nm_pasien = 'ARDIANTO PUTRA',
  no_ktp = @NIK_PASIEN,
  jk = 'L',
  tmp_lahir = 'JAYAPURA',
  tgl_lahir = '2000-12-03'
WHERE no_rkm_medis = @RM;

UPDATE pegawai
SET no_ktp = @NIK_DOKTER
WHERE nik = @KD_DOKTER;

UPDATE pegawai
SET no_ktp = '3313096403900009'
WHERE nik = 'D0000003';

UPDATE pegawai
SET no_ktp = '7209061211900001'
WHERE nik = '120000134';

INSERT INTO satu_sehat_mapping_departemen
  (dep_id, id_organisasi_satusehat)
VALUES
  ('RJ', @SATUSEHAT_ORGANIZATION_ID)
ON DUPLICATE KEY UPDATE
  id_organisasi_satusehat = VALUES(id_organisasi_satusehat);

INSERT INTO satu_sehat_mapping_lokasi_ralan
  (kd_poli, id_organisasi_satusehat, id_lokasi_satusehat, longitude, latitude, altittude)
VALUES
  (@KD_POLI, @SATUSEHAT_ORGANIZATION_ID, @SATUSEHAT_LOCATION_ID_U0003, '110.367075', '-7.795580', '0')
ON DUPLICATE KEY UPDATE
  id_organisasi_satusehat = VALUES(id_organisasi_satusehat),
  id_lokasi_satusehat = VALUES(id_lokasi_satusehat),
  longitude = VALUES(longitude),
  latitude = VALUES(latitude),
  altittude = VALUES(altittude);

UPDATE satu_sehat_mapping_lokasi_ralan
SET
  id_organisasi_satusehat = @SATUSEHAT_ORGANIZATION_ID,
  id_lokasi_satusehat = @SATUSEHAT_LOCATION_ID_INT,
  longitude = '110.367076',
  latitude = '-7.795581',
  altittude = '0'
WHERE kd_poli = 'INT';

SET @KD_PJ = COALESCE(
  (
    SELECT kd_pj
    FROM penjab
    WHERE kd_pj IN ('-', 'A09', 'BPJ', 'UMU')
    ORDER BY FIELD(kd_pj, '-', 'A09', 'BPJ', 'UMU')
    LIMIT 1
  ),
  (
    SELECT kd_pj
    FROM penjab
    ORDER BY kd_pj
    LIMIT 1
  )
);

SET @REK_PIUTANG = COALESCE(
  (
    SELECT kd_rek
    FROM rekening
    WHERE kd_rek IN ('112020', '111010')
    ORDER BY FIELD(kd_rek, '112020', '111010')
    LIMIT 1
  ),
  (SELECT kd_rek FROM rekening ORDER BY kd_rek LIMIT 1)
);

SET @REK_KONTRA = COALESCE(
  (
    SELECT kd_rek
    FROM rekening
    WHERE kd_rek IN ('117003', '117015', '117000')
    ORDER BY FIELD(kd_rek, '117003', '117015', '117000')
    LIMIT 1
  ),
  @REK_PIUTANG
);

SET @REK_DISKON_PIUTANG = COALESCE(
  (
    SELECT kd_rek
    FROM rekening
    WHERE kd_rek IN ('540103')
    LIMIT 1
  ),
  @REK_PIUTANG
);

SET @REK_TIDAK_TERBAYAR = COALESCE(
  (
    SELECT kd_rek
    FROM rekening
    WHERE kd_rek IN ('570102')
    LIMIT 1
  ),
  @REK_PIUTANG
);

/* ============================================================
   2. Bersihkan data target 997001 + cache/outbox lama
   ============================================================ */

/* Bersihkan source row target supaya rerun seed tidak menyisakan duplikasi. */
DELETE FROM satu_sehat_allergy_intolerance WHERE no_rawat = @NO_RAWAT;
DELETE FROM satu_sehat_careplan WHERE no_rawat = @NO_RAWAT;
DELETE FROM satu_sehat_clinicalimpression WHERE no_rawat = @NO_RAWAT;
DELETE FROM satu_sehat_condition WHERE no_rawat = @NO_RAWAT;
DELETE FROM satu_sehat_diet WHERE no_rawat = @NO_RAWAT;
DELETE FROM satu_sehat_immunization WHERE no_rawat = @NO_RAWAT;
DELETE FROM satu_sehat_procedure WHERE no_rawat = @NO_RAWAT;
DELETE FROM satu_sehat_encounter WHERE no_rawat = @NO_RAWAT;

DELETE FROM satu_sehat_observationttvsuhu WHERE no_rawat = @NO_RAWAT;
DELETE FROM satu_sehat_observationttvrespirasi WHERE no_rawat = @NO_RAWAT;
DELETE FROM satu_sehat_observationttvnadi WHERE no_rawat = @NO_RAWAT;
DELETE FROM satu_sehat_observationttvspo2 WHERE no_rawat = @NO_RAWAT;
DELETE FROM satu_sehat_observationttvgcs WHERE no_rawat = @NO_RAWAT;
DELETE FROM satu_sehat_observationttvkesadaran WHERE no_rawat = @NO_RAWAT;
DELETE FROM satu_sehat_observationttvtensi WHERE no_rawat = @NO_RAWAT;
DELETE FROM satu_sehat_observationttvtb WHERE no_rawat = @NO_RAWAT;
DELETE FROM satu_sehat_observationttvbb WHERE no_rawat = @NO_RAWAT;
DELETE FROM satu_sehat_observationttvlp WHERE no_rawat = @NO_RAWAT;

DELETE FROM satu_sehat_servicerequest_radiologi WHERE noorder = @RAD_ORDER;
DELETE FROM satu_sehat_specimen_radiologi WHERE noorder = @RAD_ORDER;
DELETE FROM satu_sehat_observation_radiologi WHERE noorder = @RAD_ORDER;
DELETE FROM satu_sehat_diagnosticreport_radiologi WHERE noorder = @RAD_ORDER;

DELETE FROM satu_sehat_servicerequest_lab WHERE noorder = @LAB_ORDER;
DELETE FROM satu_sehat_specimen_lab WHERE noorder = @LAB_ORDER;
DELETE FROM satu_sehat_observation_lab WHERE noorder = @LAB_ORDER;
DELETE FROM satu_sehat_diagnosticreport_lab WHERE noorder = @LAB_ORDER;

DELETE FROM satu_sehat_servicerequest_lab_mb WHERE noorder = @LABMB_ORDER;
DELETE FROM satu_sehat_specimen_lab_mb WHERE noorder = @LABMB_ORDER;
DELETE FROM satu_sehat_observation_lab_mb WHERE noorder = @LABMB_ORDER;
DELETE FROM satu_sehat_diagnosticreport_lab_mb WHERE noorder = @LABMB_ORDER;

DELETE FROM satu_sehat_medicationdispense WHERE no_rawat = @NO_RAWAT;
DELETE FROM satu_sehat_medicationrequest WHERE no_resep = @NO_RESEP;
DELETE FROM satu_sehat_medicationrequest_racikan WHERE no_resep = @NO_RESEP;
DELETE FROM satu_sehat_medicationstatement WHERE no_resep = @NO_RESEP;
DELETE FROM satu_sehat_medicationstatement_racikan WHERE no_resep = @NO_RESEP;
DELETE FROM satu_sehat_questionresponse_telaah_farmasi WHERE no_resep = @NO_RESEP;

DELETE FROM hasil_radiologi WHERE no_rawat = @NO_RAWAT;
DELETE FROM periksa_radiologi WHERE no_rawat = @NO_RAWAT;
DELETE FROM permintaan_pemeriksaan_radiologi WHERE noorder = @RAD_ORDER;
DELETE FROM permintaan_radiologi WHERE noorder = @RAD_ORDER OR no_rawat = @NO_RAWAT;

DELETE FROM detail_periksa_lab WHERE no_rawat = @NO_RAWAT;
DELETE FROM periksa_lab WHERE no_rawat = @NO_RAWAT;
DELETE FROM saran_kesan_lab WHERE no_rawat = @NO_RAWAT;
DELETE FROM permintaan_detail_permintaan_lab WHERE noorder = @LAB_ORDER;
DELETE FROM permintaan_detail_permintaan_labmb WHERE noorder = @LABMB_ORDER;
DELETE FROM permintaan_lab WHERE noorder = @LAB_ORDER OR no_rawat = @NO_RAWAT;
DELETE FROM permintaan_labmb WHERE noorder = @LABMB_ORDER OR no_rawat = @NO_RAWAT;

DELETE FROM aturan_pakai WHERE no_rawat = @NO_RAWAT;
DELETE FROM detail_pemberian_obat WHERE no_rawat = @NO_RAWAT;
DELETE FROM resep_dokter_racikan_detail WHERE no_resep = @NO_RESEP;
DELETE FROM resep_dokter_racikan WHERE no_resep = @NO_RESEP;
DELETE FROM resep_dokter WHERE no_resep = @NO_RESEP;
DELETE FROM telaah_farmasi WHERE no_resep = @NO_RESEP;
DELETE FROM resep_obat WHERE no_resep = @NO_RESEP OR no_rawat = @NO_RAWAT;

/*
  Bersihkan dummy obat SATUSEHAT batch lama.
  Fungsi medication() di frmUtama.java membaca semua row satu_sehat_mapping_obat,
  bukan hanya obat yang dipakai pada tanggal aktif. Kalau dummy SS20% lama masih
  ada, ERPNext menerima beberapa sync record Medication yang akhirnya menunjuk
  ke satu master Medication yang sama.
*/
DELETE FROM resep_dokter_racikan_detail WHERE kode_brng LIKE 'SS20%';
DELETE FROM resep_dokter WHERE kode_brng LIKE 'SS20%';
DELETE FROM aturan_pakai WHERE kode_brng LIKE 'SS20%';
DELETE FROM detail_pemberian_obat WHERE kode_brng LIKE 'SS20%';
DELETE FROM data_batch WHERE kode_brng LIKE 'SS20%';
DELETE FROM satu_sehat_mapping_vaksin WHERE kode_brng LIKE 'SS20%';
DELETE FROM satu_sehat_medication WHERE kode_brng LIKE 'SS20%';
DELETE FROM satu_sehat_mapping_obat WHERE kode_brng LIKE 'SS20%';
DELETE FROM databarang WHERE kode_brng LIKE 'SS20%';

DELETE FROM catatan_adime_gizi WHERE no_rawat = @NO_RAWAT;
DELETE FROM diagnosa_pasien WHERE no_rawat = @NO_RAWAT;
DELETE FROM prosedur_pasien WHERE no_rawat = @NO_RAWAT;
DELETE FROM pemeriksaan_ralan WHERE no_rawat = @NO_RAWAT;
DELETE FROM bayar_piutang WHERE no_rawat = @NO_RAWAT;
DELETE FROM piutang_pasien WHERE no_rawat = @NO_RAWAT;
DELETE FROM nota_jalan WHERE no_rawat = @NO_RAWAT;
DELETE FROM nota_inap WHERE no_rawat = @NO_RAWAT;
DELETE FROM billing WHERE no_rawat = @NO_RAWAT;

/* Fokuskan pengiriman ke satu data ini saja. */
UPDATE reg_periksa
SET status_bayar = 'Belum Bayar'
WHERE tgl_registrasi = @TGL
  AND status_lanjut = 'Ralan';

/* ============================================================
   3. Kunjungan utama -> Encounter
   ============================================================ */

INSERT INTO reg_periksa
  (no_reg, no_rawat, tgl_registrasi, jam_reg, kd_dokter, no_rkm_medis, kd_poli,
   p_jawab, almt_pj, hubunganpj, biaya_reg, stts, stts_daftar, status_lanjut,
   kd_pj, umurdaftar, sttsumur, status_bayar, status_poli)
VALUES
  (@NO_REG, @NO_RAWAT, @TGL, @JAM, @KD_DOKTER, @RM, @KD_POLI,
   'WINDIARTO', 'PAJANGAN BANTUL', 'AYAH', 10000, 'Belum', 'Lama', 'Ralan',
   @KD_PJ, 25, 'Th', 'Sudah Bayar', 'Lama')
ON DUPLICATE KEY UPDATE
  tgl_registrasi = VALUES(tgl_registrasi),
  jam_reg = VALUES(jam_reg),
  kd_dokter = VALUES(kd_dokter),
  no_rkm_medis = VALUES(no_rkm_medis),
  kd_poli = VALUES(kd_poli),
  stts = VALUES(stts),
  status_lanjut = VALUES(status_lanjut),
  status_bayar = VALUES(status_bayar);


/* Guard final setelah insert: cuma 997001 yang boleh Sudah Bayar pada tanggal test. */
UPDATE reg_periksa
SET status_bayar = 'Belum Bayar'
WHERE tgl_registrasi = @TGL
  AND status_lanjut = 'Ralan'
  AND no_rawat <> @NO_RAWAT;

UPDATE reg_periksa
SET status_bayar = 'Sudah Bayar'
WHERE no_rawat = @NO_RAWAT;

/* ============================================================
   4. Finance encounter -> billing, nota, piutang
   ============================================================ */

/*
  Nilai finance ini sengaja variatif untuk simulasi dashboard audit:
  - ada revenue klinis, lab, radiologi, obat
  - ada potongan
  - ada piutang belum lunas dan pembayaran sebagian
  - ada nilai tidak terbayar untuk indikator risiko
*/
INSERT INTO billing
  (noindex, no_rawat, tgl_byr, no, nm_perawatan, pemisah, biaya, jumlah, tambahan, totalbiaya, status)
VALUES
  (0, @NO_RAWAT, @TGL, 'No.Nota', CONCAT(': ', REPLACE(@TGL, '-', '/'), '/RJ', @NO_REG), '', 0, 0, 0, 0, '-'),
  (1, @NO_RAWAT, @TGL, 'Unit/Instansi', ': Poliklinik Penyakit Dalam', '', 0, 0, 0, 0, '-'),
  (2, @NO_RAWAT, @TGL, 'Tanggal & Jam', CONCAT(': ', @TGL, ' ', @JAM), '', 0, 0, 0, 0, '-'),
  (3, @NO_RAWAT, @TGL, 'No.RM', CONCAT(': ', @RM), '', 0, 0, 0, 0, '-'),
  (4, @NO_RAWAT, @TGL, 'Nama Pasien', ': ARDIANTO PUTRA (25Th)', '', 0, 0, 0, 0, '-'),
  (5, @NO_RAWAT, @TGL, 'Dokter', ': dr. Hilyatul Nadia', '', 0, 0, 0, 0, 'Dokter'),
  (6, @NO_RAWAT, @TGL, 'Registrasi', ':', '', 15000, 1, 0, 15000, 'Registrasi'),
  (7, @NO_RAWAT, @TGL, 'Tindakan', 'Pemeriksaan Poli Spesialis Audit', ':', 175000, 1, 0, 175000, 'Ralan Dokter'),
  (8, @NO_RAWAT, @TGL, 'Tindakan', 'Tindakan Observasi Febris', ':', 95000, 1, 0, 95000, 'Ralan Paramedis'),
  (9, @NO_RAWAT, @TGL, 'Radiologi', 'THORAX AP/PA', ':', 310000, 1, 0, 310000, 'Radiologi'),
  (10, @NO_RAWAT, @TGL, 'Laborat', 'Hemoglobin [Mass/volume] in Blood', ':', 125000, 1, 0, 125000, 'Laborat'),
  (11, @NO_RAWAT, @TGL, 'Obat & BHP', 'Paracetamol SATUSEHAT Audit', ':', 3400, 3, 1500, 11700, 'Obat'),
  (12, @NO_RAWAT, @TGL, 'Potongan Biaya', 'Diskon audit pasien', ':', -22000, 1, 0, -22000, 'Potongan'),
  (13, @NO_RAWAT, @TGL, 'Tagihan', 'Total Tagihan Audit', '', 0, 0, 0, 709700, 'Tagihan');

INSERT INTO nota_jalan
  (no_rawat, no_nota, tanggal, jam)
VALUES
  (@NO_RAWAT, CONCAT(REPLACE(@TGL, '-', '/'), '/RJ', @NO_REG), @TGL, ADDTIME(@JAM, '00:45:00'))
ON DUPLICATE KEY UPDATE
  no_nota = VALUES(no_nota),
  tanggal = VALUES(tanggal),
  jam = VALUES(jam);

INSERT INTO piutang_pasien
  (no_rawat, tgl_piutang, no_rkm_medis, status, totalpiutang, uangmuka, sisapiutang, tgltempo)
VALUES
  (@NO_RAWAT, @TGL, @RM, 'Belum Lunas', 709700, 250000, 429700, DATE_ADD(@TGL, INTERVAL 7 DAY))
ON DUPLICATE KEY UPDATE
  tgl_piutang = VALUES(tgl_piutang),
  no_rkm_medis = VALUES(no_rkm_medis),
  status = VALUES(status),
  totalpiutang = VALUES(totalpiutang),
  uangmuka = VALUES(uangmuka),
  sisapiutang = VALUES(sisapiutang),
  tgltempo = VALUES(tgltempo);

INSERT INTO bayar_piutang
  (tgl_bayar, no_rkm_medis, besar_cicilan, catatan, no_rawat, kd_rek, kd_rek_kontra,
   diskon_piutang, kd_rek_diskon_piutang, tidak_terbayar, kd_rek_tidak_terbayar)
SELECT
  DATE_ADD(@TGL, INTERVAL 1 DAY), @RM, 70000,
  'Pembayaran sebagian dummy audit finance', @NO_RAWAT,
  @REK_PIUTANG, @REK_KONTRA, 25000, @REK_DISKON_PIUTANG, 30000, @REK_TIDAK_TERBAYAR
WHERE @REK_PIUTANG IS NOT NULL
  AND @REK_KONTRA IS NOT NULL
  AND @REK_DISKON_PIUTANG IS NOT NULL
  AND @REK_TIDAK_TERBAYAR IS NOT NULL
ON DUPLICATE KEY UPDATE
  besar_cicilan = VALUES(besar_cicilan),
  catatan = VALUES(catatan),
  diskon_piutang = VALUES(diskon_piutang),
  tidak_terbayar = VALUES(tidak_terbayar);

/* ============================================================
   5. Pemeriksaan ralan -> Observation TTV + source umum
   ============================================================ */

INSERT INTO pemeriksaan_ralan
  (no_rawat, tgl_perawatan, jam_rawat, suhu_tubuh, tensi, nadi, respirasi,
   tinggi, berat, spo2, gcs, kesadaran, keluhan, pemeriksaan, alergi,
   lingkar_perut, rtl, penilaian, instruksi, evaluasi, nip)
VALUES
  (@NO_RAWAT, @TGL, ADDTIME(@JAM, '00:05:00'), '36.8', '120/80', '82', '20',
   '170', '65', '98', '456', 'Compos Mentis', 'Demam ringan sejak 2 hari',
   'Keadaan umum baik, tanda vital stabil', 'Gluten', '80',
   'Kontrol ulang bila keluhan memberat', 'Observasi febris',
   'Minum cukup dan istirahat', 'Membaik', @KD_DOKTER)
ON DUPLICATE KEY UPDATE
  suhu_tubuh = VALUES(suhu_tubuh),
  tensi = VALUES(tensi),
  nadi = VALUES(nadi),
  respirasi = VALUES(respirasi),
  tinggi = VALUES(tinggi),
  berat = VALUES(berat),
  spo2 = VALUES(spo2),
  gcs = VALUES(gcs),
  kesadaran = VALUES(kesadaran),
  keluhan = VALUES(keluhan),
  pemeriksaan = VALUES(pemeriksaan),
  alergi = VALUES(alergi),
  rtl = VALUES(rtl),
  penilaian = VALUES(penilaian),
  instruksi = VALUES(instruksi),
  evaluasi = VALUES(evaluasi),
  nip = VALUES(nip);

/* ============================================================
   5. Diagnosis dan prosedur -> Condition + Procedure
   ============================================================ */

INSERT INTO diagnosa_pasien
  (no_rawat, kd_penyakit, status, prioritas, status_penyakit)
VALUES
  (@NO_RAWAT, 'A01.0', 'Ralan', 1, 'Baru')
ON DUPLICATE KEY UPDATE
  prioritas = VALUES(prioritas),
  status_penyakit = VALUES(status_penyakit);

INSERT INTO prosedur_pasien
  (no_rawat, kode, status, prioritas, jumlah)
VALUES
  (@NO_RAWAT, '00.01', 'Ralan', 1, '1')
ON DUPLICATE KEY UPDATE
  prioritas = VALUES(prioritas),
  jumlah = VALUES(jumlah);

/* ============================================================
   6. Radiologi -> ServiceRequest, Observation, DiagnosticReport radiologi
   ============================================================ */

INSERT INTO satu_sehat_mapping_radiologi
  (kd_jenis_prw, code, system, display, sampel_code, sampel_system, sampel_display)
VALUES
  ('ICU.CTO-01', '24629-8', 'http://loinc.org', 'XR Chest AP', '119297000', 'http://snomed.info/sct', 'Blood specimen')
ON DUPLICATE KEY UPDATE
  code = VALUES(code),
  system = VALUES(system),
  display = VALUES(display),
  sampel_code = VALUES(sampel_code),
  sampel_system = VALUES(sampel_system),
  sampel_display = VALUES(sampel_display);

INSERT INTO permintaan_radiologi
  (noorder, no_rawat, tgl_permintaan, jam_permintaan, tgl_sampel, jam_sampel,
   tgl_hasil, jam_hasil, dokter_perujuk, status, informasi_tambahan, diagnosa_klinis)
VALUES
  (@RAD_ORDER, @NO_RAWAT, @TGL, ADDTIME(@JAM, '00:10:00'), @TGL, ADDTIME(@JAM, '00:20:00'),
   @TGL, ADDTIME(@JAM, '00:30:00'), @KD_DOKTER, 'ralan', '-', 'Febris')
ON DUPLICATE KEY UPDATE
  no_rawat = VALUES(no_rawat),
  tgl_permintaan = VALUES(tgl_permintaan),
  jam_permintaan = VALUES(jam_permintaan),
  tgl_sampel = VALUES(tgl_sampel),
  jam_sampel = VALUES(jam_sampel),
  tgl_hasil = VALUES(tgl_hasil),
  jam_hasil = VALUES(jam_hasil),
  dokter_perujuk = VALUES(dokter_perujuk),
  status = VALUES(status),
  diagnosa_klinis = VALUES(diagnosa_klinis);

INSERT INTO permintaan_pemeriksaan_radiologi
  (noorder, kd_jenis_prw, stts_bayar)
VALUES
  (@RAD_ORDER, 'ICU.CTO-01', 'Belum')
ON DUPLICATE KEY UPDATE
  stts_bayar = VALUES(stts_bayar);

INSERT INTO periksa_radiologi
  (no_rawat, nip, kd_jenis_prw, tgl_periksa, jam, dokter_perujuk,
   bagian_rs, bhp, tarif_perujuk, tarif_tindakan_dokter, tarif_tindakan_petugas,
   kso, menejemen, biaya, kd_dokter, status, proyeksi, kV, mAS, FFD, BSF,
   inak, jml_penyinaran, dosis)
VALUES
  (@NO_RAWAT, '120000134', 'ICU.CTO-01', @TGL, ADDTIME(@JAM, '00:30:00'), @KD_DOKTER,
   170000, 0, 40000, 55000, 10000,
   0, 0, 310000, @KD_DOKTER, 'Ralan', '', '', '', '', '', '', '', '')
ON DUPLICATE KEY UPDATE
  nip = VALUES(nip),
  dokter_perujuk = VALUES(dokter_perujuk),
  bagian_rs = VALUES(bagian_rs),
  bhp = VALUES(bhp),
  tarif_perujuk = VALUES(tarif_perujuk),
  tarif_tindakan_dokter = VALUES(tarif_tindakan_dokter),
  tarif_tindakan_petugas = VALUES(tarif_tindakan_petugas),
  kso = VALUES(kso),
  menejemen = VALUES(menejemen),
  biaya = VALUES(biaya),
  kd_dokter = VALUES(kd_dokter),
  status = VALUES(status);

INSERT INTO hasil_radiologi
  (no_rawat, tgl_periksa, jam, hasil)
VALUES
  (@NO_RAWAT, @TGL, ADDTIME(@JAM, '00:30:00'), 'Cor dan pulmo dalam batas normal. Tidak tampak infiltrat aktif.')
ON DUPLICATE KEY UPDATE
  hasil = VALUES(hasil);

/* ============================================================
   7. Obat, resep, telaah, dispense -> Medication*, QuestionnaireResponse
   ============================================================ */

SET @SOURCE_OBAT1 = (SELECT kode_brng FROM databarang WHERE kode_brng NOT LIKE 'SS%' ORDER BY kode_brng LIMIT 1);
SET @DUMMY_OBAT1 = CONCAT('SS', REPLACE(@TGL, '-', ''), @NO_REG);

INSERT INTO databarang
  (kode_brng, nama_brng, kode_satbesar, kode_sat, letak_barang, dasar, h_beli,
   ralan, kelas1, kelas2, kelas3, utama, vip, vvip, beliluar, jualbebas,
   karyawan, stokminimal, kdjns, isi, kapasitas, expire, status, kode_industri,
   kode_kategori, kode_golongan)
SELECT
  @DUMMY_OBAT1,
  CONCAT('Paracetamol SATUSEHAT Test ', @NO_REG),
  kode_satbesar,
  kode_sat,
  letak_barang,
  1500,
  1500,
  3400,
  3400,
  3400,
  3400,
  3400,
  3400,
  3400,
  3400,
  3400,
  3400,
  stokminimal,
  kdjns,
  isi,
  kapasitas,
  expire,
  '1',
  kode_industri,
  kode_kategori,
  kode_golongan
FROM databarang
WHERE kode_brng = @SOURCE_OBAT1
ON DUPLICATE KEY UPDATE
  nama_brng = VALUES(nama_brng),
  status = VALUES(status),
  dasar = VALUES(dasar),
  h_beli = VALUES(h_beli),
  ralan = VALUES(ralan),
  kelas1 = VALUES(kelas1),
  kelas2 = VALUES(kelas2),
  kelas3 = VALUES(kelas3),
  utama = VALUES(utama),
  vip = VALUES(vip),
  vvip = VALUES(vvip),
  beliluar = VALUES(beliluar),
  jualbebas = VALUES(jualbebas),
  karyawan = VALUES(karyawan),
  kode_satbesar = VALUES(kode_satbesar),
  kode_sat = VALUES(kode_sat),
  kdjns = VALUES(kdjns),
  kode_industri = VALUES(kode_industri),
  kode_kategori = VALUES(kode_kategori),
  kode_golongan = VALUES(kode_golongan);

SET @DUMMY_BANGSAL = COALESCE(
  (SELECT kd_bangsal FROM satu_sehat_mapping_lokasi_depo_farmasi ORDER BY kd_bangsal LIMIT 1),
  (SELECT kd_bangsal FROM bangsal ORDER BY kd_bangsal LIMIT 1)
);

SET @DUMMY_PETUGAS = COALESCE(
  (
    SELECT petugas.nip
    FROM petugas
    INNER JOIN pegawai ON pegawai.nik = petugas.nip
    WHERE petugas.nip IN ('120000134', 'D0000003', 'D0000004')
    ORDER BY FIELD(petugas.nip, '120000134', 'D0000004', 'D0000003')
    LIMIT 1
  ),
  (
    SELECT petugas.nip
    FROM petugas
    INNER JOIN pegawai ON pegawai.nik = petugas.nip
    ORDER BY petugas.nip
    LIMIT 1
  ),
  @KD_DOKTER
);

UPDATE pegawai
SET no_ktp = CASE
  WHEN no_ktp IS NULL OR no_ktp = '' OR no_ktp = '-' THEN @NIK_DOKTER
  ELSE no_ktp
END
WHERE nik = @DUMMY_PETUGAS;

SET @DUMMY_RACIK = COALESCE(
  (SELECT kd_racik FROM metode_racik ORDER BY kd_racik LIMIT 1),
  ''
);

INSERT INTO satu_sehat_mapping_obat
  (kode_brng, obat_code, obat_system, obat_display, form_code, form_system,
   form_display, numerator_code, numerator_system, denominator_code,
   denominator_system, route_code, route_system, route_display)
SELECT
  kode_brng,
  obat_code,
  'http://sys-ids.kemkes.go.id/kfa',
  obat_display,
  'BS066',
  'http://terminology.kemkes.go.id/CodeSystem/medication-form',
  'Tablet',
  'mg',
  'http://unitsofmeasure.org',
  'TAB',
  'http://terminology.hl7.org/CodeSystem/v3-orderableDrugForm',
  'O',
  'http://www.whocc.no/atc',
  'Oral'
FROM (
  SELECT @DUMMY_OBAT1 AS kode_brng, '93020730' AS obat_code, 'Paracetamol 500 mg Tablet (MERSIFARMA TIRMAKU MERCUSANA)' AS obat_display
) obat_seed
WHERE kode_brng IS NOT NULL
ON DUPLICATE KEY UPDATE
  obat_code = VALUES(obat_code),
  obat_system = VALUES(obat_system),
  obat_display = VALUES(obat_display),
  form_code = VALUES(form_code),
  form_system = VALUES(form_system),
  form_display = VALUES(form_display),
  numerator_code = VALUES(numerator_code),
  numerator_system = VALUES(numerator_system),
  denominator_code = VALUES(denominator_code),
  denominator_system = VALUES(denominator_system),
  route_code = VALUES(route_code),
  route_system = VALUES(route_system),
  route_display = VALUES(route_display);

INSERT INTO satu_sehat_medication
  (kode_brng, id_medication)
SELECT
  @DUMMY_OBAT1,
  @MEDICATION_LOCAL_ID
WHERE @DUMMY_OBAT1 IS NOT NULL
ON DUPLICATE KEY UPDATE
  id_medication = VALUES(id_medication);

INSERT INTO satu_sehat_mapping_vaksin
  (kode_brng, vaksin_code, vaksin_system, vaksin_display, route_code,
   route_system, route_display, dose_quantity_code, dose_quantity_system,
   dose_quantity_unit)
SELECT
  kode_brng,
  vaksin_code,
  'http://sys-ids.kemkes.go.id/kfa',
  vaksin_display,
  'P',
  'http://www.whocc.no/atc',
  'Parenteral',
  'mL',
  'http://unitsofmeasure.org',
  'mL'
FROM (
  SELECT @DUMMY_OBAT1 AS kode_brng, '93004956' AS vaksin_code, 'Vaksin SARS-COV-2 Inactivated 3 mcg/0,5 mL' AS vaksin_display
) vaksin_seed
WHERE kode_brng IS NOT NULL
ON DUPLICATE KEY UPDATE
  vaksin_code = VALUES(vaksin_code),
  vaksin_system = VALUES(vaksin_system),
  vaksin_display = VALUES(vaksin_display),
  route_code = VALUES(route_code),
  route_system = VALUES(route_system),
  route_display = VALUES(route_display),
  dose_quantity_code = VALUES(dose_quantity_code),
  dose_quantity_system = VALUES(dose_quantity_system),
  dose_quantity_unit = VALUES(dose_quantity_unit);

INSERT INTO satu_sehat_mapping_lokasi_depo_farmasi
  (kd_bangsal, id_organisasi_satusehat, id_lokasi_satusehat, longitude, latitude, altittude)
SELECT
  @DUMMY_BANGSAL,
  @SATUSEHAT_ORGANIZATION_ID,
  @SATUSEHAT_LOCATION_ID_INT,
  '110.367076',
  '-7.795581',
  '0'
WHERE @DUMMY_BANGSAL IS NOT NULL
ON DUPLICATE KEY UPDATE
  id_organisasi_satusehat = VALUES(id_organisasi_satusehat),
  id_lokasi_satusehat = VALUES(id_lokasi_satusehat),
  longitude = VALUES(longitude),
  latitude = VALUES(latitude),
  altittude = VALUES(altittude);

INSERT INTO resep_obat
  (no_resep, tgl_perawatan, jam, no_rawat, kd_dokter, tgl_peresepan,
   jam_peresepan, status, tgl_penyerahan, jam_penyerahan)
VALUES
  (@NO_RESEP, @TGL, ADDTIME(@JAM, '00:15:00'), @NO_RAWAT, @KD_DOKTER, @TGL,
   ADDTIME(@JAM, '00:15:00'), 'ralan', @TGL, ADDTIME(@JAM, '00:45:00'))
ON DUPLICATE KEY UPDATE
  tgl_perawatan = VALUES(tgl_perawatan),
  jam = VALUES(jam),
  no_rawat = VALUES(no_rawat),
  kd_dokter = VALUES(kd_dokter),
  tgl_peresepan = VALUES(tgl_peresepan),
  jam_peresepan = VALUES(jam_peresepan),
  tgl_penyerahan = VALUES(tgl_penyerahan),
  jam_penyerahan = VALUES(jam_penyerahan);

INSERT INTO telaah_farmasi
  (no_resep, resep_identifikasi_pasien, resep_ket_identifikasi_pasien,
   resep_tepat_obat, resep_ket_tepat_obat, resep_tepat_dosis,
   resep_ket_tepat_dosis, resep_tepat_cara_pemberian,
   resep_ket_tepat_cara_pemberian, resep_tepat_waktu_pemberian,
   resep_ket_tepat_waktu_pemberian, resep_ada_tidak_duplikasi_obat,
   resep_ket_ada_tidak_duplikasi_obat, resep_interaksi_obat,
   resep_ket_interaksi_obat, resep_kontra_indikasi_obat,
   resep_ket_kontra_indikasi_obat, obat_tepat_pasien, obat_tepat_obat,
   obat_tepat_dosis, obat_tepat_cara_pemberian, obat_tepat_waktu_pemberian, nip)
VALUES
  (@NO_RESEP, 'Ya', '', 'Ya', '', 'Ya', '', 'Ya', '', 'Ya', '', 'Tidak', '',
   'Tidak', '', 'Tidak', '', 'Ya', 'Ya', 'Ya', 'Ya', 'Ya', @DUMMY_PETUGAS)
ON DUPLICATE KEY UPDATE
  resep_identifikasi_pasien = VALUES(resep_identifikasi_pasien),
  resep_tepat_obat = VALUES(resep_tepat_obat),
  resep_tepat_dosis = VALUES(resep_tepat_dosis),
  resep_tepat_cara_pemberian = VALUES(resep_tepat_cara_pemberian),
  resep_tepat_waktu_pemberian = VALUES(resep_tepat_waktu_pemberian),
  resep_ada_tidak_duplikasi_obat = VALUES(resep_ada_tidak_duplikasi_obat),
  resep_interaksi_obat = VALUES(resep_interaksi_obat),
  resep_kontra_indikasi_obat = VALUES(resep_kontra_indikasi_obat),
  obat_tepat_pasien = VALUES(obat_tepat_pasien),
  obat_tepat_obat = VALUES(obat_tepat_obat),
  obat_tepat_dosis = VALUES(obat_tepat_dosis),
  obat_tepat_cara_pemberian = VALUES(obat_tepat_cara_pemberian),
  obat_tepat_waktu_pemberian = VALUES(obat_tepat_waktu_pemberian),
  nip = VALUES(nip);

INSERT INTO data_batch
  (no_batch, kode_brng, tgl_beli, tgl_kadaluarsa, asal, no_faktur, dasar,
   h_beli, ralan, kelas1, kelas2, kelas3, utama, vip, vvip, beliluar,
   jualbebas, karyawan, jumlahbeli, sisa)
SELECT
  @BATCH_NO, @DUMMY_OBAT1, '2026-01-01', '2027-12-31', 'Pengadaan', @FAKTUR_NO,
  1500, 1500, 3400, 3400, 3400, 3400, 3400, 3400, 3400, 3400, 3400, 3400, 100, 97
WHERE @DUMMY_OBAT1 IS NOT NULL
ON DUPLICATE KEY UPDATE
  tgl_kadaluarsa = VALUES(tgl_kadaluarsa),
  dasar = VALUES(dasar),
  h_beli = VALUES(h_beli),
  ralan = VALUES(ralan),
  kelas1 = VALUES(kelas1),
  kelas2 = VALUES(kelas2),
  kelas3 = VALUES(kelas3),
  utama = VALUES(utama),
  vip = VALUES(vip),
  vvip = VALUES(vvip),
  beliluar = VALUES(beliluar),
  jualbebas = VALUES(jualbebas),
  karyawan = VALUES(karyawan),
  jumlahbeli = VALUES(jumlahbeli),
  sisa = VALUES(sisa);

INSERT INTO detail_pemberian_obat
  (tgl_perawatan, jam, no_rawat, kode_brng, h_beli, biaya_obat, jml,
   embalase, tuslah, total, status, kd_bangsal, no_batch, no_faktur)
SELECT
  @TGL, ADDTIME(@JAM, '00:15:00'), @NO_RAWAT, @DUMMY_OBAT1, 1500, 3400, 3,
  700, 800, 11700, 'Ralan', @DUMMY_BANGSAL, @BATCH_NO, @FAKTUR_NO
WHERE @DUMMY_OBAT1 IS NOT NULL
  AND @DUMMY_BANGSAL IS NOT NULL
ON DUPLICATE KEY UPDATE
  h_beli = VALUES(h_beli),
  biaya_obat = VALUES(biaya_obat),
  jml = VALUES(jml),
  embalase = VALUES(embalase),
  tuslah = VALUES(tuslah),
  total = VALUES(total),
  no_batch = VALUES(no_batch),
  no_faktur = VALUES(no_faktur),
  kd_bangsal = VALUES(kd_bangsal);

INSERT INTO aturan_pakai
  (tgl_perawatan, jam, no_rawat, kode_brng, aturan)
SELECT
  @TGL, ADDTIME(@JAM, '00:15:00'), @NO_RAWAT, @DUMMY_OBAT1, '3x1'
WHERE @DUMMY_OBAT1 IS NOT NULL
ON DUPLICATE KEY UPDATE
  aturan = VALUES(aturan);

INSERT INTO resep_dokter
  (no_resep, kode_brng, jml, aturan_pakai)
SELECT
  @NO_RESEP, @DUMMY_OBAT1, 2, '3x1'
WHERE @DUMMY_OBAT1 IS NOT NULL
ON DUPLICATE KEY UPDATE
  jml = VALUES(jml),
  aturan_pakai = VALUES(aturan_pakai);

INSERT INTO resep_dokter_racikan
  (no_resep, no_racik, nama_racik, kd_racik, jml_dr, aturan_pakai, keterangan)
SELECT
  @NO_RESEP, '1', 'Racikan demam', @DUMMY_RACIK, 1, '3x1', 'Sesudah makan'
WHERE @DUMMY_OBAT1 IS NOT NULL
  AND @DUMMY_RACIK <> ''
ON DUPLICATE KEY UPDATE
  nama_racik = VALUES(nama_racik),
  kd_racik = VALUES(kd_racik),
  aturan_pakai = VALUES(aturan_pakai),
  keterangan = VALUES(keterangan);

INSERT INTO resep_dokter_racikan_detail
  (no_resep, no_racik, kode_brng, p1, p2, kandungan, jml)
SELECT
  @NO_RESEP, '1', @DUMMY_OBAT1, 1, 1, '500', 2
WHERE @DUMMY_OBAT1 IS NOT NULL
  AND @DUMMY_RACIK <> ''
ON DUPLICATE KEY UPDATE
  p1 = VALUES(p1),
  p2 = VALUES(p2),
  kandungan = VALUES(kandungan),
  jml = VALUES(jml);

/* ============================================================
   8. Diet/gizi source -> Composition/CarePlan tergantung mapper Java
   ============================================================ */

INSERT INTO catatan_adime_gizi
  (no_rawat, tanggal, asesmen, diagnosis, intervensi, monitoring, evaluasi, instruksi, nip)
SELECT
  @NO_RAWAT,
  CONCAT(@TGL, ' ', ADDTIME(@JAM, '00:12:00')),
  'Asupan makan menurun sejak demam',
  'Risiko defisit nutrisi ringan',
  'Diet lunak tinggi kalori tinggi protein',
  'Pantau asupan makan harian',
  'Pasien memahami edukasi diet',
  'Diet lunak TKTP 3 kali sehari',
  @DUMMY_PETUGAS
WHERE @DUMMY_PETUGAS IS NOT NULL
ON DUPLICATE KEY UPDATE
  asesmen = VALUES(asesmen),
  diagnosis = VALUES(diagnosis),
  intervensi = VALUES(intervensi),
  monitoring = VALUES(monitoring),
  evaluasi = VALUES(evaluasi),
  instruksi = VALUES(instruksi),
  nip = VALUES(nip);

/* ============================================================
   9. Lab PK + Lab MB -> ServiceRequest, Specimen, Observation, DiagnosticReport
   ============================================================ */

SET @DUMMY_LAB_TEMPLATE = (
  SELECT id_template
  FROM template_laboratorium
  ORDER BY id_template
  LIMIT 1
);
SET @DUMMY_LAB_PRW = (
  SELECT kd_jenis_prw
  FROM template_laboratorium
  WHERE id_template = @DUMMY_LAB_TEMPLATE
  LIMIT 1
);

INSERT INTO satu_sehat_mapping_lab
  (id_template, code, system, display, sampel_code, sampel_system, sampel_display)
SELECT
  @DUMMY_LAB_TEMPLATE,
  '718-7',
  'http://loinc.org',
  'Hemoglobin [Mass/volume] in Blood',
  '119297000',
  'http://snomed.info/sct',
  'Blood specimen'
WHERE @DUMMY_LAB_TEMPLATE IS NOT NULL
ON DUPLICATE KEY UPDATE
  code = VALUES(code),
  system = VALUES(system),
  display = VALUES(display),
  sampel_code = VALUES(sampel_code),
  sampel_system = VALUES(sampel_system),
  sampel_display = VALUES(sampel_display);

INSERT INTO permintaan_lab
  (noorder, no_rawat, tgl_permintaan, jam_permintaan, tgl_sampel, jam_sampel,
   tgl_hasil, jam_hasil, dokter_perujuk, status, informasi_tambahan, diagnosa_klinis)
SELECT
  @LAB_ORDER, @NO_RAWAT, @TGL, ADDTIME(@JAM, '00:25:00'), @TGL, ADDTIME(@JAM, '00:35:00'),
  @TGL, ADDTIME(@JAM, '00:55:00'), @KD_DOKTER, 'ralan', '-', 'Febris'
WHERE @DUMMY_LAB_TEMPLATE IS NOT NULL
ON DUPLICATE KEY UPDATE
  no_rawat = VALUES(no_rawat),
  tgl_permintaan = VALUES(tgl_permintaan),
  jam_permintaan = VALUES(jam_permintaan),
  tgl_sampel = VALUES(tgl_sampel),
  jam_sampel = VALUES(jam_sampel),
  tgl_hasil = VALUES(tgl_hasil),
  jam_hasil = VALUES(jam_hasil),
  dokter_perujuk = VALUES(dokter_perujuk),
  diagnosa_klinis = VALUES(diagnosa_klinis);

INSERT INTO permintaan_detail_permintaan_lab
  (noorder, kd_jenis_prw, id_template, stts_bayar)
SELECT
  @LAB_ORDER, @DUMMY_LAB_PRW, @DUMMY_LAB_TEMPLATE, 'Belum'
WHERE @DUMMY_LAB_TEMPLATE IS NOT NULL
ON DUPLICATE KEY UPDATE
  stts_bayar = VALUES(stts_bayar);

INSERT INTO permintaan_labmb
  (noorder, no_rawat, tgl_permintaan, jam_permintaan, tgl_sampel, jam_sampel,
   tgl_hasil, jam_hasil, dokter_perujuk, status, informasi_tambahan, diagnosa_klinis)
SELECT
  @LABMB_ORDER, @NO_RAWAT, @TGL, ADDTIME(@JAM, '01:00:00'), @TGL, ADDTIME(@JAM, '01:10:00'),
  @TGL, ADDTIME(@JAM, '01:30:00'), @KD_DOKTER, 'ralan', '-', 'Febris'
WHERE @DUMMY_LAB_TEMPLATE IS NOT NULL
ON DUPLICATE KEY UPDATE
  no_rawat = VALUES(no_rawat),
  tgl_permintaan = VALUES(tgl_permintaan),
  jam_permintaan = VALUES(jam_permintaan),
  tgl_sampel = VALUES(tgl_sampel),
  jam_sampel = VALUES(jam_sampel),
  tgl_hasil = VALUES(tgl_hasil),
  jam_hasil = VALUES(jam_hasil),
  dokter_perujuk = VALUES(dokter_perujuk),
  diagnosa_klinis = VALUES(diagnosa_klinis);

INSERT INTO permintaan_detail_permintaan_labmb
  (noorder, kd_jenis_prw, id_template, stts_bayar)
SELECT
  @LABMB_ORDER, @DUMMY_LAB_PRW, @DUMMY_LAB_TEMPLATE, 'Belum'
WHERE @DUMMY_LAB_TEMPLATE IS NOT NULL
ON DUPLICATE KEY UPDATE
  stts_bayar = VALUES(stts_bayar);

INSERT INTO periksa_lab
  (no_rawat, nip, kd_jenis_prw, tgl_periksa, jam, dokter_perujuk,
   bagian_rs, bhp, tarif_perujuk, tarif_tindakan_dokter,
   tarif_tindakan_petugas, kso, menejemen, biaya, kd_dokter, status, kategori)
SELECT
  @NO_RAWAT, @DUMMY_PETUGAS, @DUMMY_LAB_PRW, @TGL, ADDTIME(@JAM, '00:55:00'), @KD_DOKTER,
  75000, 8000, 7000, 15000, 7000, 0, 8000, 125000, @KD_DOKTER, 'Ralan', 'PK'
WHERE @DUMMY_LAB_TEMPLATE IS NOT NULL
  AND @DUMMY_PETUGAS IS NOT NULL
ON DUPLICATE KEY UPDATE
  nip = VALUES(nip),
  dokter_perujuk = VALUES(dokter_perujuk),
  bagian_rs = VALUES(bagian_rs),
  bhp = VALUES(bhp),
  tarif_perujuk = VALUES(tarif_perujuk),
  tarif_tindakan_dokter = VALUES(tarif_tindakan_dokter),
  tarif_tindakan_petugas = VALUES(tarif_tindakan_petugas),
  kso = VALUES(kso),
  menejemen = VALUES(menejemen),
  biaya = VALUES(biaya),
  kd_dokter = VALUES(kd_dokter),
  kategori = VALUES(kategori);

INSERT INTO periksa_lab
  (no_rawat, nip, kd_jenis_prw, tgl_periksa, jam, dokter_perujuk,
   bagian_rs, bhp, tarif_perujuk, tarif_tindakan_dokter,
   tarif_tindakan_petugas, kso, menejemen, biaya, kd_dokter, status, kategori)
SELECT
  @NO_RAWAT, @DUMMY_PETUGAS, @DUMMY_LAB_PRW, @TGL, ADDTIME(@JAM, '01:30:00'), @KD_DOKTER,
  50000, 5000, 4000, 4000, 4000, 0, 0, 65000, @KD_DOKTER, 'Ralan', 'MB'
WHERE @DUMMY_LAB_TEMPLATE IS NOT NULL
  AND @DUMMY_PETUGAS IS NOT NULL
ON DUPLICATE KEY UPDATE
  nip = VALUES(nip),
  dokter_perujuk = VALUES(dokter_perujuk),
  bagian_rs = VALUES(bagian_rs),
  bhp = VALUES(bhp),
  tarif_perujuk = VALUES(tarif_perujuk),
  tarif_tindakan_dokter = VALUES(tarif_tindakan_dokter),
  tarif_tindakan_petugas = VALUES(tarif_tindakan_petugas),
  kso = VALUES(kso),
  menejemen = VALUES(menejemen),
  biaya = VALUES(biaya),
  kd_dokter = VALUES(kd_dokter),
  kategori = VALUES(kategori);

INSERT INTO detail_periksa_lab
  (no_rawat, kd_jenis_prw, tgl_periksa, jam, id_template, nilai,
   nilai_rujukan, keterangan, bagian_rs, bhp, bagian_perujuk,
   bagian_dokter, bagian_laborat, kso, menejemen, biaya_item)
SELECT
  @NO_RAWAT, @DUMMY_LAB_PRW, @TGL, ADDTIME(@JAM, '00:55:00'), @DUMMY_LAB_TEMPLATE,
  '13.5', '12-16', 'Normal', 75000, 8000, 7000, 15000, 7000, 0, 8000, 125000
WHERE @DUMMY_LAB_TEMPLATE IS NOT NULL
ON DUPLICATE KEY UPDATE
  nilai = VALUES(nilai),
  nilai_rujukan = VALUES(nilai_rujukan),
  keterangan = VALUES(keterangan),
  bagian_rs = VALUES(bagian_rs),
  bhp = VALUES(bhp),
  bagian_perujuk = VALUES(bagian_perujuk),
  bagian_dokter = VALUES(bagian_dokter),
  bagian_laborat = VALUES(bagian_laborat),
  kso = VALUES(kso),
  menejemen = VALUES(menejemen),
  biaya_item = VALUES(biaya_item);

INSERT INTO detail_periksa_lab
  (no_rawat, kd_jenis_prw, tgl_periksa, jam, id_template, nilai,
   nilai_rujukan, keterangan, bagian_rs, bhp, bagian_perujuk,
   bagian_dokter, bagian_laborat, kso, menejemen, biaya_item)
SELECT
  @NO_RAWAT, @DUMMY_LAB_PRW, @TGL, ADDTIME(@JAM, '01:30:00'), @DUMMY_LAB_TEMPLATE,
  'Negatif', 'Negatif', 'Biaya internal lebih tinggi dari billing simulasi', 50000, 5000, 4000, 4000, 4000, 0, 0, 65000
WHERE @DUMMY_LAB_TEMPLATE IS NOT NULL
ON DUPLICATE KEY UPDATE
  nilai = VALUES(nilai),
  nilai_rujukan = VALUES(nilai_rujukan),
  keterangan = VALUES(keterangan),
  bagian_rs = VALUES(bagian_rs),
  bhp = VALUES(bhp),
  bagian_perujuk = VALUES(bagian_perujuk),
  bagian_dokter = VALUES(bagian_dokter),
  bagian_laborat = VALUES(bagian_laborat),
  kso = VALUES(kso),
  menejemen = VALUES(menejemen),
  biaya_item = VALUES(biaya_item);

INSERT INTO saran_kesan_lab
  (no_rawat, tgl_periksa, jam, saran, kesan)
VALUES
  (@NO_RAWAT, @TGL, ADDTIME(@JAM, '00:55:00'),
   'Kontrol sesuai jadwal bila keluhan menetap',
   'Hasil laboratorium dalam batas normal')
ON DUPLICATE KEY UPDATE
  saran = VALUES(saran),
  kesan = VALUES(kesan);

INSERT INTO saran_kesan_lab
  (no_rawat, tgl_periksa, jam, saran, kesan)
VALUES
  (@NO_RAWAT, @TGL, ADDTIME(@JAM, '01:30:00'),
   'Tidak diperlukan tindak lanjut khusus',
   'Tidak ditemukan temuan mikrobiologi bermakna')
ON DUPLICATE KEY UPDATE
  saran = VALUES(saran),
  kesan = VALUES(kesan);

/* ============================================================
   10. Reset cache SATUSEHAT target supaya semua fungsi kirim ulang
   ============================================================ */

DELETE FROM satu_sehat_allergy_intolerance WHERE no_rawat = @NO_RAWAT;
DELETE FROM satu_sehat_careplan WHERE no_rawat = @NO_RAWAT;
DELETE FROM satu_sehat_clinicalimpression WHERE no_rawat = @NO_RAWAT;
DELETE FROM satu_sehat_condition WHERE no_rawat = @NO_RAWAT;
DELETE FROM satu_sehat_diet WHERE no_rawat = @NO_RAWAT;
DELETE FROM satu_sehat_immunization WHERE no_rawat = @NO_RAWAT;
DELETE FROM satu_sehat_procedure WHERE no_rawat = @NO_RAWAT;

DELETE FROM satu_sehat_observationttvsuhu WHERE no_rawat = @NO_RAWAT;
DELETE FROM satu_sehat_observationttvrespirasi WHERE no_rawat = @NO_RAWAT;
DELETE FROM satu_sehat_observationttvnadi WHERE no_rawat = @NO_RAWAT;
DELETE FROM satu_sehat_observationttvspo2 WHERE no_rawat = @NO_RAWAT;
DELETE FROM satu_sehat_observationttvgcs WHERE no_rawat = @NO_RAWAT;
DELETE FROM satu_sehat_observationttvkesadaran WHERE no_rawat = @NO_RAWAT;
DELETE FROM satu_sehat_observationttvtensi WHERE no_rawat = @NO_RAWAT;
DELETE FROM satu_sehat_observationttvtb WHERE no_rawat = @NO_RAWAT;
DELETE FROM satu_sehat_observationttvbb WHERE no_rawat = @NO_RAWAT;
DELETE FROM satu_sehat_observationttvlp WHERE no_rawat = @NO_RAWAT;

DELETE FROM satu_sehat_servicerequest_radiologi WHERE noorder = @RAD_ORDER;
DELETE FROM satu_sehat_specimen_radiologi WHERE noorder = @RAD_ORDER;
DELETE FROM satu_sehat_observation_radiologi WHERE noorder = @RAD_ORDER;
DELETE FROM satu_sehat_diagnosticreport_radiologi WHERE noorder = @RAD_ORDER;

DELETE FROM satu_sehat_servicerequest_lab WHERE noorder = @LAB_ORDER;
DELETE FROM satu_sehat_specimen_lab WHERE noorder = @LAB_ORDER;
DELETE FROM satu_sehat_observation_lab WHERE noorder = @LAB_ORDER;
DELETE FROM satu_sehat_diagnosticreport_lab WHERE noorder = @LAB_ORDER;

DELETE FROM satu_sehat_servicerequest_lab_mb WHERE noorder = @LABMB_ORDER;
DELETE FROM satu_sehat_specimen_lab_mb WHERE noorder = @LABMB_ORDER;
DELETE FROM satu_sehat_observation_lab_mb WHERE noorder = @LABMB_ORDER;
DELETE FROM satu_sehat_diagnosticreport_lab_mb WHERE noorder = @LABMB_ORDER;

DELETE FROM satu_sehat_medicationdispense WHERE no_rawat = @NO_RAWAT;
DELETE FROM satu_sehat_medicationrequest WHERE no_resep = @NO_RESEP;
DELETE FROM satu_sehat_medicationrequest_racikan WHERE no_resep = @NO_RESEP;
DELETE FROM satu_sehat_medicationstatement WHERE no_resep = @NO_RESEP;
DELETE FROM satu_sehat_medicationstatement_racikan WHERE no_resep = @NO_RESEP;
DELETE FROM satu_sehat_questionresponse_telaah_farmasi WHERE no_resep = @NO_RESEP;

DELETE FROM satu_sehat_encounter WHERE no_rawat = @NO_RAWAT;

SET FOREIGN_KEY_CHECKS = 1;

/* ============================================================
   11. Verifikasi cepat
   ============================================================ */

SELECT
  'ACTIVE_RALAN_HARUS_1' AS check_name,
  COUNT(*) AS total
FROM reg_periksa
WHERE tgl_registrasi = @TGL
  AND status_lanjut = 'Ralan'
  AND status_bayar = 'Sudah Bayar';

SELECT
  rp.no_rawat,
  rp.tgl_registrasi,
  rp.jam_reg,
  rp.status_bayar,
  ps.no_ktp AS nik_pasien,
  pg.no_ktp AS nik_practitioner,
  rp.kd_poli,
  ml.id_lokasi_satusehat,
  ml.id_organisasi_satusehat
FROM reg_periksa rp
INNER JOIN pasien ps ON ps.no_rkm_medis = rp.no_rkm_medis
INNER JOIN pegawai pg ON pg.nik = rp.kd_dokter
INNER JOIN satu_sehat_mapping_lokasi_ralan ml ON ml.kd_poli = rp.kd_poli
WHERE rp.no_rawat = @NO_RAWAT;

SELECT 'pemeriksaan_ralan' AS table_name, COUNT(*) AS total FROM pemeriksaan_ralan WHERE no_rawat = @NO_RAWAT
UNION ALL SELECT 'billing', COUNT(*) FROM billing WHERE no_rawat = @NO_RAWAT
UNION ALL SELECT 'nota_jalan', COUNT(*) FROM nota_jalan WHERE no_rawat = @NO_RAWAT
UNION ALL SELECT 'piutang_pasien', COUNT(*) FROM piutang_pasien WHERE no_rawat = @NO_RAWAT
UNION ALL SELECT 'bayar_piutang', COUNT(*) FROM bayar_piutang WHERE no_rawat = @NO_RAWAT
UNION ALL SELECT 'diagnosa_pasien', COUNT(*) FROM diagnosa_pasien WHERE no_rawat = @NO_RAWAT
UNION ALL SELECT 'prosedur_pasien', COUNT(*) FROM prosedur_pasien WHERE no_rawat = @NO_RAWAT
UNION ALL SELECT 'satu_sehat_mapping_radiologi', COUNT(*) FROM satu_sehat_mapping_radiologi WHERE kd_jenis_prw = 'ICU.CTO-01'
UNION ALL SELECT 'permintaan_radiologi', COUNT(*) FROM permintaan_radiologi WHERE no_rawat = @NO_RAWAT
UNION ALL SELECT 'permintaan_pemeriksaan_radiologi', COUNT(*) FROM permintaan_pemeriksaan_radiologi WHERE noorder = @RAD_ORDER
UNION ALL SELECT 'periksa_radiologi', COUNT(*) FROM periksa_radiologi WHERE no_rawat = @NO_RAWAT
UNION ALL SELECT 'hasil_radiologi', COUNT(*) FROM hasil_radiologi WHERE no_rawat = @NO_RAWAT
UNION ALL SELECT 'databarang_dummy_obat', COUNT(*) FROM databarang WHERE kode_brng = @DUMMY_OBAT1
UNION ALL SELECT 'satu_sehat_mapping_obat', COUNT(*) FROM satu_sehat_mapping_obat WHERE kode_brng = @DUMMY_OBAT1
UNION ALL SELECT 'satu_sehat_medication', COUNT(*) FROM satu_sehat_medication WHERE kode_brng = @DUMMY_OBAT1
UNION ALL SELECT 'satu_sehat_mapping_vaksin', COUNT(*) FROM satu_sehat_mapping_vaksin WHERE kode_brng = @DUMMY_OBAT1
UNION ALL SELECT 'databarang_dummy_SS20_total_harus_1', COUNT(*) FROM databarang WHERE kode_brng LIKE 'SS20%'
UNION ALL SELECT 'mapping_obat_SS20_total_harus_1', COUNT(*) FROM satu_sehat_mapping_obat WHERE kode_brng LIKE 'SS20%'
UNION ALL SELECT 'medication_SS20_total_harus_1', COUNT(*) FROM satu_sehat_medication WHERE kode_brng LIKE 'SS20%'
UNION ALL SELECT 'mapping_vaksin_SS20_total_harus_1', COUNT(*) FROM satu_sehat_mapping_vaksin WHERE kode_brng LIKE 'SS20%'
UNION ALL SELECT 'MEDICATION_AKTIF_JAVA_HARUS_1', COUNT(DISTINCT satu_sehat_mapping_obat.kode_brng)
FROM satu_sehat_mapping_obat
INNER JOIN databarang ON databarang.kode_brng = satu_sehat_mapping_obat.kode_brng
INNER JOIN satu_sehat_medication ON satu_sehat_medication.kode_brng = satu_sehat_mapping_obat.kode_brng
WHERE satu_sehat_medication.id_medication <> ''
  AND (
    EXISTS (
      SELECT 1
      FROM resep_obat
      INNER JOIN reg_periksa ON reg_periksa.no_rawat = resep_obat.no_rawat
      INNER JOIN resep_dokter ON resep_dokter.no_resep = resep_obat.no_resep
      WHERE resep_dokter.kode_brng = satu_sehat_mapping_obat.kode_brng
        AND reg_periksa.status_bayar = 'Sudah Bayar'
        AND reg_periksa.tgl_registrasi BETWEEN @TGL AND @TGL
    )
    OR EXISTS (
      SELECT 1
      FROM resep_obat
      INNER JOIN reg_periksa ON reg_periksa.no_rawat = resep_obat.no_rawat
      INNER JOIN resep_dokter_racikan ON resep_dokter_racikan.no_resep = resep_obat.no_resep
      INNER JOIN resep_dokter_racikan_detail ON resep_dokter_racikan_detail.no_resep = resep_dokter_racikan.no_resep
        AND resep_dokter_racikan_detail.no_racik = resep_dokter_racikan.no_racik
      WHERE resep_dokter_racikan_detail.kode_brng = satu_sehat_mapping_obat.kode_brng
        AND reg_periksa.status_bayar = 'Sudah Bayar'
        AND reg_periksa.tgl_registrasi BETWEEN @TGL AND @TGL
    )
    OR EXISTS (
      SELECT 1
      FROM detail_pemberian_obat
      INNER JOIN reg_periksa ON reg_periksa.no_rawat = detail_pemberian_obat.no_rawat
      WHERE detail_pemberian_obat.kode_brng = satu_sehat_mapping_obat.kode_brng
        AND reg_periksa.status_bayar = 'Sudah Bayar'
        AND reg_periksa.tgl_registrasi BETWEEN @TGL AND @TGL
    )
  )
UNION ALL SELECT 'resep_obat', COUNT(*) FROM resep_obat WHERE no_rawat = @NO_RAWAT
UNION ALL SELECT 'telaah_farmasi', COUNT(*) FROM telaah_farmasi WHERE no_resep = @NO_RESEP
UNION ALL SELECT 'detail_pemberian_obat', COUNT(*) FROM detail_pemberian_obat WHERE no_rawat = @NO_RAWAT
UNION ALL SELECT 'aturan_pakai', COUNT(*) FROM aturan_pakai WHERE no_rawat = @NO_RAWAT
UNION ALL SELECT 'resep_dokter', COUNT(*) FROM resep_dokter WHERE no_resep = @NO_RESEP
UNION ALL SELECT 'catatan_adime_gizi', COUNT(*) FROM catatan_adime_gizi WHERE no_rawat = @NO_RAWAT
UNION ALL SELECT 'permintaan_lab', COUNT(*) FROM permintaan_lab WHERE noorder = @LAB_ORDER
UNION ALL SELECT 'permintaan_detail_permintaan_lab', COUNT(*) FROM permintaan_detail_permintaan_lab WHERE noorder = @LAB_ORDER
UNION ALL SELECT 'permintaan_labmb', COUNT(*) FROM permintaan_labmb WHERE noorder = @LABMB_ORDER
UNION ALL SELECT 'permintaan_detail_permintaan_labmb', COUNT(*) FROM permintaan_detail_permintaan_labmb WHERE noorder = @LABMB_ORDER
UNION ALL SELECT 'periksa_lab', COUNT(*) FROM periksa_lab WHERE no_rawat = @NO_RAWAT
UNION ALL SELECT 'detail_periksa_lab', COUNT(*) FROM detail_periksa_lab WHERE no_rawat = @NO_RAWAT
UNION ALL SELECT 'saran_kesan_lab', COUNT(*) FROM saran_kesan_lab WHERE no_rawat = @NO_RAWAT;


/* ============================================================
   VERIFIKASI TAMBAHAN: pastikan hanya target aktif/cache target kosong
   ============================================================ */

SELECT
  'ACTIVE_RALAN_FINAL_HARUS_CUMA_997001' AS check_name,
  no_rawat,
  status_bayar
FROM reg_periksa
WHERE tgl_registrasi = @TGL
  AND status_lanjut = 'Ralan'
  AND status_bayar = 'Sudah Bayar'
ORDER BY no_rawat;

SELECT
  'CACHE_TARGET_997001_HARUS_0' AS check_name,
  (
    SELECT COUNT(*) FROM satu_sehat_encounter
    WHERE no_rawat = @NO_RAWAT
  ) AS total_encounter_cache,
  (
    SELECT COUNT(*) FROM satu_sehat_condition
    WHERE no_rawat = @NO_RAWAT
  ) AS total_condition_cache,
  (
    SELECT COUNT(*) FROM satu_sehat_procedure
    WHERE no_rawat = @NO_RAWAT
  ) AS total_procedure_cache;

SELECT
  'FINANCE_BILLING_SUMMARY' AS check_name,
  status,
  COUNT(*) AS line_count,
  SUM(totalbiaya) AS total_billing
FROM billing
WHERE no_rawat = @NO_RAWAT
GROUP BY status
ORDER BY status;

SELECT
  'FINANCE_PIUTANG_RISK' AS check_name,
  totalpiutang,
  uangmuka,
  sisapiutang,
  tgltempo,
  status
FROM piutang_pasien
WHERE no_rawat = @NO_RAWAT;

SELECT
  'FINANCE_MEDICATION_MARGIN' AS check_name,
  detail_pemberian_obat.kode_brng,
  databarang.nama_brng,
  detail_pemberian_obat.h_beli,
  detail_pemberian_obat.biaya_obat,
  detail_pemberian_obat.jml,
  detail_pemberian_obat.embalase,
  detail_pemberian_obat.tuslah,
  detail_pemberian_obat.total,
  (detail_pemberian_obat.total - (detail_pemberian_obat.h_beli * detail_pemberian_obat.jml)) AS margin_obat
FROM detail_pemberian_obat
LEFT JOIN databarang ON databarang.kode_brng = detail_pemberian_obat.kode_brng
WHERE detail_pemberian_obat.no_rawat = @NO_RAWAT;

SELECT
  'FINANCE_LAB_MARGIN_PROXY' AS check_name,
  kategori,
  biaya,
  (bagian_rs + bhp + tarif_perujuk + tarif_tindakan_dokter + tarif_tindakan_petugas + kso + menejemen) AS komponen_internal,
  (biaya - (bagian_rs + bhp + tarif_perujuk + tarif_tindakan_dokter + tarif_tindakan_petugas + kso + menejemen)) AS margin_proxy
FROM periksa_lab
WHERE no_rawat = @NO_RAWAT;

SELECT
  'FINANCE_RAD_MARGIN_PROXY' AS check_name,
  kd_jenis_prw,
  biaya,
  (bagian_rs + bhp + tarif_perujuk + tarif_tindakan_dokter + tarif_tindakan_petugas + kso + menejemen) AS komponen_internal,
  (biaya - (bagian_rs + bhp + tarif_perujuk + tarif_tindakan_dokter + tarif_tindakan_petugas + kso + menejemen)) AS margin_proxy
FROM periksa_radiologi
WHERE no_rawat = @NO_RAWAT;


/* ============================================================
   VERIFIKASI FINAL TAMBAHAN
   ============================================================ */

SELECT
  'ACTIVE_RALAN_FINAL_HARUS_CUMA_997001' AS check_name,
  no_rawat,
  tgl_registrasi,
  jam_reg,
  no_rkm_medis,
  kd_dokter,
  kd_poli,
  status_lanjut,
  status_bayar
FROM reg_periksa
WHERE tgl_registrasi = @TGL
  AND status_lanjut = 'Ralan'
  AND status_bayar = 'Sudah Bayar'
ORDER BY no_rawat;

SELECT 'CEK_SOURCE_ENCOUNTER_reg_periksa' AS check_name, COUNT(*) AS total FROM reg_periksa WHERE no_rawat=@NO_RAWAT;
SELECT 'CEK_SOURCE_OBSERVATION_TTV_pemeriksaan_ralan' AS check_name, COUNT(*) AS total FROM pemeriksaan_ralan WHERE no_rawat=@NO_RAWAT;
SELECT 'CEK_SOURCE_CONDITION_diagnosa_pasien' AS check_name, COUNT(*) AS total FROM diagnosa_pasien WHERE no_rawat=@NO_RAWAT;
SELECT 'CEK_SOURCE_PROCEDURE_prosedur_pasien' AS check_name, COUNT(*) AS total FROM prosedur_pasien WHERE no_rawat=@NO_RAWAT;
SELECT 'CEK_SOURCE_RAD_ORDER_permintaan_radiologi' AS check_name, COUNT(*) AS total FROM permintaan_radiologi WHERE no_rawat=@NO_RAWAT;
SELECT 'CEK_SOURCE_RAD_RESULT_hasil_radiologi' AS check_name, COUNT(*) AS total FROM hasil_radiologi WHERE no_rawat=@NO_RAWAT;
SELECT 'CEK_SOURCE_RESEP_resep_obat' AS check_name, COUNT(*) AS total FROM resep_obat WHERE no_rawat=@NO_RAWAT;
SELECT 'CEK_SOURCE_DISPENSE_detail_pemberian_obat' AS check_name, COUNT(*) AS total FROM detail_pemberian_obat WHERE no_rawat=@NO_RAWAT;
SELECT 'CEK_SOURCE_CAREPLAN_catatan_adime_gizi' AS check_name, COUNT(*) AS total FROM catatan_adime_gizi WHERE no_rawat=@NO_RAWAT;
SELECT 'CEK_SOURCE_LAB_PK_permintaan_lab' AS check_name, COUNT(*) AS total FROM permintaan_lab WHERE no_rawat=@NO_RAWAT;
SELECT 'CEK_SOURCE_LAB_MB_permintaan_labmb' AS check_name, COUNT(*) AS total FROM permintaan_labmb WHERE no_rawat=@NO_RAWAT;
SELECT 'CEK_SOURCE_LAB_RESULT_periksa_lab' AS check_name, COUNT(*) AS total FROM periksa_lab WHERE no_rawat=@NO_RAWAT;

