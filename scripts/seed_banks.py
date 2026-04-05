"""Seed Indonesian banks into the banks table.

Comprehensive list of banks that offer loan products (KPR, KPA, KPT,
consumer loans, etc.) to Indonesian consumers. Sourced from OJK data,
ASBANDA directory, and individual bank websites.

Categories:
  BUMN             – State-owned (Badan Usaha Milik Negara)
  SWASTA_NASIONAL  – Private national
  BPD              – Regional development (Bank Pembangunan Daerah)
  ASING            – Foreign-owned
  SYARIAH          – Full Islamic banks (Bank Umum Syariah)
"""
import asyncio
import os
import sys
from pathlib import Path

import asyncpg
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

# (code, name, name_indonesia, website_url, category, type, is_partner_ringkas)
BANKS: tuple[tuple[str, str, str, str, str, str, bool], ...] = (
    # =========================================================================
    # BUMN — State-Owned Banks (4)
    # =========================================================================
    ("BRI", "Bank Rakyat Indonesia", "Bank Rakyat Indonesia", "https://bri.co.id", "BUMN", "KONVENSIONAL", True),
    ("BNI", "Bank Negara Indonesia", "Bank Negara Indonesia", "https://www.bni.co.id", "BUMN", "KONVENSIONAL", True),
    ("BTN", "Bank Tabungan Negara", "Bank Tabungan Negara", "https://www.btn.co.id", "BUMN", "KONVENSIONAL", True),
    ("MANDIRI", "Bank Mandiri", "Bank Mandiri", "https://www.bankmandiri.co.id", "BUMN", "KONVENSIONAL", True),

    # =========================================================================
    # SWASTA_NASIONAL — Private National Banks (18)
    # =========================================================================
    ("BCA", "Bank Central Asia", "Bank Central Asia", "https://www.bca.co.id", "SWASTA_NASIONAL", "KONVENSIONAL", True),
    ("CIMB", "CIMB Niaga", "CIMB Niaga", "https://www.cimbniaga.co.id", "SWASTA_NASIONAL", "KONVENSIONAL", True),
    ("PERMATA", "Bank Permata", "Bank Permata", "https://www.permatabank.com", "SWASTA_NASIONAL", "KONVENSIONAL", True),
    ("DANAMON", "Bank Danamon", "Bank Danamon", "https://www.danamon.co.id", "SWASTA_NASIONAL", "KONVENSIONAL", True),
    ("PANIN", "Panin Bank", "Panin Bank", "https://www.panin.co.id", "SWASTA_NASIONAL", "KONVENSIONAL", False),
    ("BTPN", "Bank BTPN", "Bank BTPN", "https://www.btpn.com", "SWASTA_NASIONAL", "KONVENSIONAL", False),
    ("SINARMAS", "Bank Sinarmas", "Bank Sinarmas", "https://www.banksinarmas.com", "SWASTA_NASIONAL", "KONVENSIONAL", False),
    ("BUKOPIN", "KB Bank (formerly Bukopin)", "KB Bank (eks Bukopin)", "https://www.kbbank.co.id", "SWASTA_NASIONAL", "KONVENSIONAL", False),
    ("MAYAPADA", "Bank Mayapada", "Bank Mayapada", "https://www.bankmayapada.com", "SWASTA_NASIONAL", "KONVENSIONAL", False),
    ("MEGA", "Bank Mega", "Bank Mega", "https://www.bankmega.com", "SWASTA_NASIONAL", "KONVENSIONAL", False),
    ("OCBC", "OCBC Indonesia", "OCBC Indonesia", "https://www.ocbc.id", "SWASTA_NASIONAL", "KONVENSIONAL", True),
    ("MAYBANK", "Maybank Indonesia", "Maybank Indonesia", "https://www.maybank.co.id", "SWASTA_NASIONAL", "KONVENSIONAL", False),
    ("MNC", "MNC Bank", "Bank MNC Internasional", "https://www.mncbank.co.id", "SWASTA_NASIONAL", "KONVENSIONAL", False),
    ("CCBI", "CCB Indonesia", "China Construction Bank Indonesia", "https://bankccbi.co.id", "SWASTA_NASIONAL", "KONVENSIONAL", False),
    ("ALLO", "Allo Bank", "Allo Bank Indonesia", "https://www.allobank.com", "SWASTA_NASIONAL", "KONVENSIONAL", False),
    ("VICTORIA", "Bank Victoria", "Bank Victoria International", "https://www.bankvictoria.co.id", "SWASTA_NASIONAL", "KONVENSIONAL", False),
    ("JTRUST", "J Trust Bank", "J Trust Bank", "https://www.jtrustbank.co.id", "SWASTA_NASIONAL", "KONVENSIONAL", False),
    ("ARTHA", "Bank Artha Graha", "Bank Artha Graha Internasional", "https://www.arthagraha.com", "SWASTA_NASIONAL", "KONVENSIONAL", False),

    # =========================================================================
    # ASING — Foreign Banks (8)
    # =========================================================================
    ("STANCHART", "Standard Chartered Indonesia", "Standard Chartered Indonesia", "https://www.sc.com/id", "ASING", "KONVENSIONAL", False),
    ("CITIBANK", "Citibank Indonesia", "Citibank Indonesia", "https://www.citibank.co.id", "ASING", "KONVENSIONAL", False),
    ("HSBC", "HSBC Indonesia", "HSBC Indonesia", "https://www.hsbc.co.id", "ASING", "KONVENSIONAL", False),
    ("DBS", "DBS Indonesia", "DBS Indonesia", "https://www.dbs.id", "ASING", "KONVENSIONAL", False),
    ("UOB", "UOB Indonesia", "UOB Indonesia", "https://www.uob.co.id", "ASING", "KONVENSIONAL", True),
    ("DEUTSCHE", "Deutsche Bank Indonesia", "Deutsche Bank Indonesia", "https://www.db.com/indonesia", "ASING", "KONVENSIONAL", False),
    ("COMMONWEALTH", "Commonwealth Bank Indonesia", "Commonwealth Bank Indonesia", "https://www.commbank.co.id", "ASING", "KONVENSIONAL", False),
    ("ICBC", "ICBC Indonesia", "ICBC Indonesia", "https://www.icbc.co.id", "ASING", "KONVENSIONAL", False),

    # =========================================================================
    # BPD — Regional Development Banks (26)
    # =========================================================================
    ("BANKACEH", "Bank Aceh Syariah", "Bank Aceh Syariah", "https://bankaceh.co.id", "BPD", "SYARIAH", False),
    ("SUMUT", "Bank Sumut", "Bank Pembangunan Daerah Sumatera Utara", "https://www.banksumut.co.id", "BPD", "KONVENSIONAL", False),
    ("NAGARI", "Bank Nagari", "Bank Pembangunan Daerah Sumatera Barat", "https://www.banknagari.co.id", "BPD", "KONVENSIONAL", False),
    ("RIAUKEPRI", "BRK Syariah", "BRK Syariah (eks Bank Riau Kepri)", "https://www.brksyariah.co.id", "BPD", "SYARIAH", False),
    ("JAMBI", "Bank Jambi", "Bank Pembangunan Daerah Jambi", "https://bankjambi.co.id", "BPD", "KONVENSIONAL", False),
    ("SUMSELBABEL", "Bank Sumsel Babel", "Bank Pembangunan Daerah Sumatera Selatan dan Bangka Belitung", "https://www.banksumselbabel.com", "BPD", "KONVENSIONAL", False),
    ("BENGKULU", "Bank Bengkulu", "Bank Pembangunan Daerah Bengkulu", "https://bankbengkulu.co.id", "BPD", "KONVENSIONAL", False),
    ("LAMPUNG", "Bank Lampung", "Bank Pembangunan Daerah Lampung", "https://www.banklampung.co.id", "BPD", "KONVENSIONAL", False),
    ("BANTEN", "Bank Banten", "Bank Pembangunan Daerah Banten", "https://www.bankbanten.co.id", "BPD", "KONVENSIONAL", False),
    ("BJB", "Bank BJB", "Bank Pembangunan Daerah Jawa Barat dan Banten", "https://www.bankbjb.co.id", "BPD", "KONVENSIONAL", False),
    ("BANKDKI", "Bank DKI", "Bank DKI", "https://www.bankdki.co.id", "BPD", "KONVENSIONAL", False),
    ("BANKJATENG", "Bank Jateng", "Bank Pembangunan Daerah Jawa Tengah", "https://www.bankjateng.co.id", "BPD", "KONVENSIONAL", False),
    ("BPDDIY", "Bank BPD DIY", "Bank Pembangunan Daerah DIY", "https://www.bpddiy.co.id", "BPD", "KONVENSIONAL", False),
    ("BANKJATIM", "Bank Jatim", "Bank Pembangunan Daerah Jawa Timur", "https://www.bankjatim.co.id", "BPD", "KONVENSIONAL", False),
    ("BALI", "Bank BPD Bali", "Bank Pembangunan Daerah Bali", "https://www.bpdbali.co.id", "BPD", "KONVENSIONAL", False),
    ("NTB", "Bank NTB Syariah", "Bank NTB Syariah", "https://www.bankntbsyariah.co.id", "BPD", "SYARIAH", False),
    ("NTT", "Bank NTT", "Bank Pembangunan Daerah Nusa Tenggara Timur", "https://www.bankntt.co.id", "BPD", "KONVENSIONAL", False),
    ("KALBAR", "Bank Kalbar", "Bank Pembangunan Daerah Kalimantan Barat", "https://www.bankkalbar.co.id", "BPD", "KONVENSIONAL", False),
    ("KALTENG", "Bank Kalteng", "Bank Pembangunan Daerah Kalimantan Tengah", "https://www.bankkalteng.co.id", "BPD", "KONVENSIONAL", False),
    ("KALSEL", "Bank Kalsel", "Bank Pembangunan Daerah Kalimantan Selatan", "https://www.bankkalsel.co.id", "BPD", "KONVENSIONAL", False),
    ("KALTIMTARA", "Bankaltimtara", "Bank Pembangunan Daerah Kalimantan Timur dan Kalimantan Utara", "https://www.bankaltimtara.co.id", "BPD", "KONVENSIONAL", False),
    ("SULUTGO", "Bank SulutGo", "Bank Pembangunan Daerah Sulawesi Utara dan Gorontalo", "https://www.banksulutgo.co.id", "BPD", "KONVENSIONAL", False),
    ("SULTENG", "Bank Sulteng", "Bank Pembangunan Daerah Sulawesi Tengah", "https://www.banksulteng.co.id", "BPD", "KONVENSIONAL", False),
    ("SULSELBAR", "Bank Sulselbar", "Bank Pembangunan Daerah Sulawesi Selatan dan Sulawesi Barat", "https://www.banksulselbar.co.id", "BPD", "KONVENSIONAL", False),
    ("SULTRA", "Bank Sultra", "Bank Pembangunan Daerah Sulawesi Tenggara", "https://banksultra.co.id", "BPD", "KONVENSIONAL", False),
    ("MALUKUMALUT", "Bank Maluku Malut", "Bank Pembangunan Daerah Maluku dan Maluku Utara", "https://www.bankmalukumalut.co.id", "BPD", "KONVENSIONAL", False),
    ("PAPUA", "Bank Papua", "Bank Pembangunan Daerah Papua", "https://www.bankpapua.co.id", "BPD", "KONVENSIONAL", False),

    # =========================================================================
    # SYARIAH — Full Islamic Banks / Bank Umum Syariah (13)
    # Note: BSI was formed from the merger of BNI Syariah, BRI Syariah, and
    # Mandiri Syariah. Those legacy entities are kept for historical crawl data.
    # =========================================================================
    ("BSI", "Bank Syariah Indonesia", "Bank Syariah Indonesia", "https://www.bankbsi.co.id", "SYARIAH", "SYARIAH", True),
    ("MUAMALAT", "Bank Muamalat", "Bank Muamalat Indonesia", "https://www.bankmuamalat.co.id", "SYARIAH", "SYARIAH", False),
    ("BCAS", "BCA Syariah", "BCA Syariah", "https://www.bcasyariah.co.id", "SYARIAH", "SYARIAH", False),
    ("MEGASY", "Bank Mega Syariah", "Bank Mega Syariah", "https://www.megasyariah.co.id", "SYARIAH", "SYARIAH", False),
    ("PANINSY", "Panin Dubai Syariah", "Bank Panin Dubai Syariah", "https://www.paninbanksyariah.co.id", "SYARIAH", "SYARIAH", False),
    ("BUKOSY", "KB Syariah (formerly Bukopin Syariah)", "KB Syariah (eks Bank Syariah Bukopin)", "https://www.kbbukopinsyariah.co.id", "SYARIAH", "SYARIAH", False),
    ("BTPNSY", "BTPN Syariah", "BTPN Syariah", "https://www.btpnsyariah.com", "SYARIAH", "SYARIAH", False),
    ("ALADIN", "Bank Aladin Syariah", "Bank Aladin Syariah", "https://aladinbank.id", "SYARIAH", "SYARIAH", False),
    ("VICTORIASY", "Bank Victoria Syariah", "Bank Victoria Syariah", "https://www.bankvictoriasyariah.co.id", "SYARIAH", "SYARIAH", False),
    ("BJBSY", "BJB Syariah", "Bank Jabar Banten Syariah", "https://www.bjbsyariah.co.id", "SYARIAH", "SYARIAH", False),
    # Legacy entities (merged into BSI Feb 2021) — kept for historical data
    ("BNIS", "BNI Syariah", "BNI Syariah", "https://www.bnisyariah.co.id", "SYARIAH", "SYARIAH", False),
    ("BRIS", "BRI Syariah", "BRI Syariah", "https://www.brisyariah.co.id", "SYARIAH", "SYARIAH", False),
    ("MANDIRIS", "Mandiri Syariah", "Mandiri Syariah", "https://www.mandirisyariah.co.id", "SYARIAH", "SYARIAH", False),
)

UPSERT_SQL = """
INSERT INTO banks (
    bank_code, bank_name, name_indonesia, website_url,
    bank_category, bank_type, is_partner_ringkas
)
VALUES ($1, $2, $3, $4, $5, $6, $7)
ON CONFLICT (bank_code) DO UPDATE SET
    bank_name = EXCLUDED.bank_name,
    name_indonesia = EXCLUDED.name_indonesia,
    website_url = EXCLUDED.website_url,
    bank_category = EXCLUDED.bank_category,
    bank_type = EXCLUDED.bank_type,
    is_partner_ringkas = EXCLUDED.is_partner_ringkas
"""


async def main() -> None:
    url = os.environ.get("DATABASE_URL")
    if not url:
        print("ERROR: DATABASE_URL not set")
        sys.exit(1)

    conn = await asyncpg.connect(url, statement_cache_size=0)
    inserted = 0
    updated = 0

    try:
        for bank in BANKS:
            code = bank[0]
            existing = await conn.fetchrow(
                "SELECT id FROM banks WHERE bank_code = $1", code
            )
            await conn.execute(UPSERT_SQL, *bank)
            if existing is None:
                inserted += 1
            else:
                updated += 1

        total = await conn.fetchval("SELECT COUNT(*) FROM banks")
        print(f"Inserted: {inserted}")
        print(f"Updated:  {updated}")
        print(f"Total banks in DB: {total}")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
