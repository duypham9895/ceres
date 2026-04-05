-- Seed data: 70 Indonesian banks that offer loan products
-- Sourced from OJK registry, ASBANDA directory, and bank websites
-- This file runs automatically on first docker-compose up

-- =========================================================================
-- BUMN — State-Owned Banks (4)
-- =========================================================================
INSERT INTO banks (bank_code, bank_name, name_indonesia, website_url, bank_category, bank_type, is_partner_ringkas)
VALUES
  ('BRI', 'Bank Rakyat Indonesia', 'Bank Rakyat Indonesia', 'https://bri.co.id', 'BUMN', 'KONVENSIONAL', true),
  ('BNI', 'Bank Negara Indonesia', 'Bank Negara Indonesia', 'https://www.bni.co.id', 'BUMN', 'KONVENSIONAL', true),
  ('BTN', 'Bank Tabungan Negara', 'Bank Tabungan Negara', 'https://www.btn.co.id', 'BUMN', 'KONVENSIONAL', true),
  ('MANDIRI', 'Bank Mandiri', 'Bank Mandiri', 'https://www.bankmandiri.co.id', 'BUMN', 'KONVENSIONAL', true)
ON CONFLICT (bank_code) DO UPDATE SET
  bank_name = EXCLUDED.bank_name,
  name_indonesia = EXCLUDED.name_indonesia,
  website_url = EXCLUDED.website_url,
  bank_category = EXCLUDED.bank_category,
  bank_type = EXCLUDED.bank_type,
  is_partner_ringkas = EXCLUDED.is_partner_ringkas;

-- =========================================================================
-- SWASTA_NASIONAL — Private National Banks (18)
-- =========================================================================
INSERT INTO banks (bank_code, bank_name, name_indonesia, website_url, bank_category, bank_type, is_partner_ringkas)
VALUES
  ('BCA', 'Bank Central Asia', 'Bank Central Asia', 'https://www.bca.co.id', 'SWASTA_NASIONAL', 'KONVENSIONAL', true),
  ('CIMB', 'CIMB Niaga', 'CIMB Niaga', 'https://www.cimbniaga.co.id', 'SWASTA_NASIONAL', 'KONVENSIONAL', true),
  ('PERMATA', 'Bank Permata', 'Bank Permata', 'https://www.permatabank.com', 'SWASTA_NASIONAL', 'KONVENSIONAL', true),
  ('DANAMON', 'Bank Danamon', 'Bank Danamon', 'https://www.danamon.co.id', 'SWASTA_NASIONAL', 'KONVENSIONAL', true),
  ('PANIN', 'Panin Bank', 'Panin Bank', 'https://www.panin.co.id', 'SWASTA_NASIONAL', 'KONVENSIONAL', false),
  ('BTPN', 'Bank BTPN', 'Bank BTPN', 'https://www.btpn.com', 'SWASTA_NASIONAL', 'KONVENSIONAL', false),
  ('SINARMAS', 'Bank Sinarmas', 'Bank Sinarmas', 'https://www.banksinarmas.com', 'SWASTA_NASIONAL', 'KONVENSIONAL', false),
  ('BUKOPIN', 'KB Bank (formerly Bukopin)', 'KB Bank (eks Bukopin)', 'https://www.kbbank.co.id', 'SWASTA_NASIONAL', 'KONVENSIONAL', false),
  ('MAYAPADA', 'Bank Mayapada', 'Bank Mayapada', 'https://www.bankmayapada.com', 'SWASTA_NASIONAL', 'KONVENSIONAL', false),
  ('MEGA', 'Bank Mega', 'Bank Mega', 'https://www.bankmega.com', 'SWASTA_NASIONAL', 'KONVENSIONAL', false),
  ('OCBC', 'OCBC Indonesia', 'OCBC Indonesia', 'https://www.ocbc.id', 'SWASTA_NASIONAL', 'KONVENSIONAL', true),
  ('MAYBANK', 'Maybank Indonesia', 'Maybank Indonesia', 'https://www.maybank.co.id', 'SWASTA_NASIONAL', 'KONVENSIONAL', false),
  ('MNC', 'MNC Bank', 'Bank MNC Internasional', 'https://www.mncbank.co.id', 'SWASTA_NASIONAL', 'KONVENSIONAL', false),
  ('CCBI', 'CCB Indonesia', 'China Construction Bank Indonesia', 'https://bankccbi.co.id', 'SWASTA_NASIONAL', 'KONVENSIONAL', false),
  ('ALLO', 'Allo Bank', 'Allo Bank Indonesia', 'https://www.allobank.com', 'SWASTA_NASIONAL', 'KONVENSIONAL', false),
  ('VICTORIA', 'Bank Victoria', 'Bank Victoria International', 'https://www.bankvictoria.co.id', 'SWASTA_NASIONAL', 'KONVENSIONAL', false),
  ('JTRUST', 'J Trust Bank', 'J Trust Bank', 'https://www.jtrustbank.co.id', 'SWASTA_NASIONAL', 'KONVENSIONAL', false),
  ('ARTHA', 'Bank Artha Graha', 'Bank Artha Graha Internasional', 'https://www.arthagraha.com', 'SWASTA_NASIONAL', 'KONVENSIONAL', false)
ON CONFLICT (bank_code) DO UPDATE SET
  bank_name = EXCLUDED.bank_name,
  name_indonesia = EXCLUDED.name_indonesia,
  website_url = EXCLUDED.website_url,
  bank_category = EXCLUDED.bank_category,
  bank_type = EXCLUDED.bank_type,
  is_partner_ringkas = EXCLUDED.is_partner_ringkas;

-- =========================================================================
-- ASING — Foreign Banks (8)
-- =========================================================================
INSERT INTO banks (bank_code, bank_name, name_indonesia, website_url, bank_category, bank_type, is_partner_ringkas)
VALUES
  ('STANCHART', 'Standard Chartered Indonesia', 'Standard Chartered Indonesia', 'https://www.sc.com/id', 'ASING', 'KONVENSIONAL', false),
  ('CITIBANK', 'Citibank Indonesia', 'Citibank Indonesia', 'https://www.citibank.co.id', 'ASING', 'KONVENSIONAL', false),
  ('HSBC', 'HSBC Indonesia', 'HSBC Indonesia', 'https://www.hsbc.co.id', 'ASING', 'KONVENSIONAL', false),
  ('DBS', 'DBS Indonesia', 'DBS Indonesia', 'https://www.dbs.id', 'ASING', 'KONVENSIONAL', false),
  ('UOB', 'UOB Indonesia', 'UOB Indonesia', 'https://www.uob.co.id', 'ASING', 'KONVENSIONAL', true),
  ('DEUTSCHE', 'Deutsche Bank Indonesia', 'Deutsche Bank Indonesia', 'https://www.db.com/indonesia', 'ASING', 'KONVENSIONAL', false),
  ('COMMONWEALTH', 'Commonwealth Bank Indonesia', 'Commonwealth Bank Indonesia', 'https://www.commbank.co.id', 'ASING', 'KONVENSIONAL', false),
  ('ICBC', 'ICBC Indonesia', 'ICBC Indonesia', 'https://www.icbc.co.id', 'ASING', 'KONVENSIONAL', false)
ON CONFLICT (bank_code) DO UPDATE SET
  bank_name = EXCLUDED.bank_name,
  name_indonesia = EXCLUDED.name_indonesia,
  website_url = EXCLUDED.website_url,
  bank_category = EXCLUDED.bank_category,
  bank_type = EXCLUDED.bank_type,
  is_partner_ringkas = EXCLUDED.is_partner_ringkas;

-- =========================================================================
-- BPD — Regional Development Banks (27)
-- =========================================================================
INSERT INTO banks (bank_code, bank_name, name_indonesia, website_url, bank_category, bank_type, is_partner_ringkas)
VALUES
  ('BANKACEH', 'Bank Aceh Syariah', 'Bank Aceh Syariah', 'https://bankaceh.co.id', 'BPD', 'SYARIAH', false),
  ('SUMUT', 'Bank Sumut', 'Bank Pembangunan Daerah Sumatera Utara', 'https://www.banksumut.co.id', 'BPD', 'KONVENSIONAL', false),
  ('NAGARI', 'Bank Nagari', 'Bank Pembangunan Daerah Sumatera Barat', 'https://www.banknagari.co.id', 'BPD', 'KONVENSIONAL', false),
  ('RIAUKEPRI', 'BRK Syariah', 'BRK Syariah (eks Bank Riau Kepri)', 'https://www.brksyariah.co.id', 'BPD', 'SYARIAH', false),
  ('JAMBI', 'Bank Jambi', 'Bank Pembangunan Daerah Jambi', 'https://bankjambi.co.id', 'BPD', 'KONVENSIONAL', false),
  ('SUMSELBABEL', 'Bank Sumsel Babel', 'Bank Pembangunan Daerah Sumatera Selatan dan Bangka Belitung', 'https://www.banksumselbabel.com', 'BPD', 'KONVENSIONAL', false),
  ('BENGKULU', 'Bank Bengkulu', 'Bank Pembangunan Daerah Bengkulu', 'https://bankbengkulu.co.id', 'BPD', 'KONVENSIONAL', false),
  ('LAMPUNG', 'Bank Lampung', 'Bank Pembangunan Daerah Lampung', 'https://www.banklampung.co.id', 'BPD', 'KONVENSIONAL', false),
  ('BANTEN', 'Bank Banten', 'Bank Pembangunan Daerah Banten', 'https://www.bankbanten.co.id', 'BPD', 'KONVENSIONAL', false),
  ('BJB', 'Bank BJB', 'Bank Pembangunan Daerah Jawa Barat dan Banten', 'https://www.bankbjb.co.id', 'BPD', 'KONVENSIONAL', false),
  ('BANKDKI', 'Bank DKI', 'Bank DKI', 'https://www.bankdki.co.id', 'BPD', 'KONVENSIONAL', false),
  ('BANKJATENG', 'Bank Jateng', 'Bank Pembangunan Daerah Jawa Tengah', 'https://www.bankjateng.co.id', 'BPD', 'KONVENSIONAL', false),
  ('BPDDIY', 'Bank BPD DIY', 'Bank Pembangunan Daerah DIY', 'https://www.bpddiy.co.id', 'BPD', 'KONVENSIONAL', false),
  ('BANKJATIM', 'Bank Jatim', 'Bank Pembangunan Daerah Jawa Timur', 'https://www.bankjatim.co.id', 'BPD', 'KONVENSIONAL', false),
  ('BALI', 'Bank BPD Bali', 'Bank Pembangunan Daerah Bali', 'https://www.bpdbali.co.id', 'BPD', 'KONVENSIONAL', false),
  ('NTB', 'Bank NTB Syariah', 'Bank NTB Syariah', 'https://www.bankntbsyariah.co.id', 'BPD', 'SYARIAH', false),
  ('NTT', 'Bank NTT', 'Bank Pembangunan Daerah Nusa Tenggara Timur', 'https://www.bankntt.co.id', 'BPD', 'KONVENSIONAL', false),
  ('KALBAR', 'Bank Kalbar', 'Bank Pembangunan Daerah Kalimantan Barat', 'https://www.bankkalbar.co.id', 'BPD', 'KONVENSIONAL', false),
  ('KALTENG', 'Bank Kalteng', 'Bank Pembangunan Daerah Kalimantan Tengah', 'https://www.bankkalteng.co.id', 'BPD', 'KONVENSIONAL', false),
  ('KALSEL', 'Bank Kalsel', 'Bank Pembangunan Daerah Kalimantan Selatan', 'https://www.bankkalsel.co.id', 'BPD', 'KONVENSIONAL', false),
  ('KALTIMTARA', 'Bankaltimtara', 'Bank Pembangunan Daerah Kalimantan Timur dan Kalimantan Utara', 'https://www.bankaltimtara.co.id', 'BPD', 'KONVENSIONAL', false),
  ('SULUTGO', 'Bank SulutGo', 'Bank Pembangunan Daerah Sulawesi Utara dan Gorontalo', 'https://www.banksulutgo.co.id', 'BPD', 'KONVENSIONAL', false),
  ('SULTENG', 'Bank Sulteng', 'Bank Pembangunan Daerah Sulawesi Tengah', 'https://www.banksulteng.co.id', 'BPD', 'KONVENSIONAL', false),
  ('SULSELBAR', 'Bank Sulselbar', 'Bank Pembangunan Daerah Sulawesi Selatan dan Sulawesi Barat', 'https://www.banksulselbar.co.id', 'BPD', 'KONVENSIONAL', false),
  ('SULTRA', 'Bank Sultra', 'Bank Pembangunan Daerah Sulawesi Tenggara', 'https://banksultra.co.id', 'BPD', 'KONVENSIONAL', false),
  ('MALUKUMALUT', 'Bank Maluku Malut', 'Bank Pembangunan Daerah Maluku dan Maluku Utara', 'https://www.bankmalukumalut.co.id', 'BPD', 'KONVENSIONAL', false),
  ('PAPUA', 'Bank Papua', 'Bank Pembangunan Daerah Papua', 'https://www.bankpapua.co.id', 'BPD', 'KONVENSIONAL', false)
ON CONFLICT (bank_code) DO UPDATE SET
  bank_name = EXCLUDED.bank_name,
  name_indonesia = EXCLUDED.name_indonesia,
  website_url = EXCLUDED.website_url,
  bank_category = EXCLUDED.bank_category,
  bank_type = EXCLUDED.bank_type,
  is_partner_ringkas = EXCLUDED.is_partner_ringkas;

-- =========================================================================
-- SYARIAH — Full Islamic Banks (13)
-- BSI formed from merger of BNI Syariah, BRI Syariah, Mandiri Syariah (Feb 2021)
-- Legacy entities kept for historical crawl data
-- =========================================================================
INSERT INTO banks (bank_code, bank_name, name_indonesia, website_url, bank_category, bank_type, is_partner_ringkas)
VALUES
  ('BSI', 'Bank Syariah Indonesia', 'Bank Syariah Indonesia', 'https://www.bankbsi.co.id', 'SYARIAH', 'SYARIAH', true),
  ('MUAMALAT', 'Bank Muamalat', 'Bank Muamalat Indonesia', 'https://www.bankmuamalat.co.id', 'SYARIAH', 'SYARIAH', false),
  ('BCAS', 'BCA Syariah', 'BCA Syariah', 'https://www.bcasyariah.co.id', 'SYARIAH', 'SYARIAH', false),
  ('MEGASY', 'Bank Mega Syariah', 'Bank Mega Syariah', 'https://www.megasyariah.co.id', 'SYARIAH', 'SYARIAH', false),
  ('PANINSY', 'Panin Dubai Syariah', 'Bank Panin Dubai Syariah', 'https://www.paninbanksyariah.co.id', 'SYARIAH', 'SYARIAH', false),
  ('BUKOSY', 'KB Syariah (formerly Bukopin Syariah)', 'KB Syariah (eks Bank Syariah Bukopin)', 'https://www.kbbukopinsyariah.co.id', 'SYARIAH', 'SYARIAH', false),
  ('BTPNSY', 'BTPN Syariah', 'BTPN Syariah', 'https://www.btpnsyariah.com', 'SYARIAH', 'SYARIAH', false),
  ('ALADIN', 'Bank Aladin Syariah', 'Bank Aladin Syariah', 'https://aladinbank.id', 'SYARIAH', 'SYARIAH', false),
  ('VICTORIASY', 'Bank Victoria Syariah', 'Bank Victoria Syariah', 'https://www.bankvictoriasyariah.co.id', 'SYARIAH', 'SYARIAH', false),
  ('BJBSY', 'BJB Syariah', 'Bank Jabar Banten Syariah', 'https://www.bjbsyariah.co.id', 'SYARIAH', 'SYARIAH', false),
  ('BNIS', 'BNI Syariah', 'BNI Syariah', 'https://www.bnisyariah.co.id', 'SYARIAH', 'SYARIAH', false),
  ('BRIS', 'BRI Syariah', 'BRI Syariah', 'https://www.brisyariah.co.id', 'SYARIAH', 'SYARIAH', false),
  ('MANDIRIS', 'Mandiri Syariah', 'Mandiri Syariah', 'https://www.mandirisyariah.co.id', 'SYARIAH', 'SYARIAH', false)
ON CONFLICT (bank_code) DO UPDATE SET
  bank_name = EXCLUDED.bank_name,
  name_indonesia = EXCLUDED.name_indonesia,
  website_url = EXCLUDED.website_url,
  bank_category = EXCLUDED.bank_category,
  bank_type = EXCLUDED.bank_type,
  is_partner_ringkas = EXCLUDED.is_partner_ringkas;
