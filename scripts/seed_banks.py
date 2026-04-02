"""Seed 62 Indonesian banks into the banks table."""
import asyncio
import os
import sys
from pathlib import Path

import asyncpg
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

# (code, name, name_indonesia, website_url, category, type, is_partner_ringkas)
BANKS: tuple[tuple[str, str, str, str, str, str, bool], ...] = (
    # --- BUMN (4) ---
    ("BRI", "Bank Rakyat Indonesia", "Bank Rakyat Indonesia", "https://bri.co.id", "BUMN", "KONVENSIONAL", True),
    ("BNI", "Bank Negara Indonesia", "Bank Negara Indonesia", "https://www.bni.co.id", "BUMN", "KONVENSIONAL", True),
    ("BTN", "Bank Tabungan Negara", "Bank Tabungan Negara", "https://www.btn.co.id", "BUMN", "KONVENSIONAL", True),
    ("MANDIRI", "Bank Mandiri", "Bank Mandiri", "https://www.bankmandiri.co.id", "BUMN", "KONVENSIONAL", True),
    # --- Swasta Nasional (13) ---
    ("BCA", "Bank Central Asia", "Bank Central Asia", "https://www.bca.co.id", "SWASTA_NASIONAL", "KONVENSIONAL", True),
    ("CIMB", "CIMB Niaga", "CIMB Niaga", "https://www.cimbniaga.co.id", "SWASTA_NASIONAL", "KONVENSIONAL", True),
    ("PERMATA", "Bank Permata", "Bank Permata", "https://www.permatabank.com", "SWASTA_NASIONAL", "KONVENSIONAL", True),
    ("DANAMON", "Bank Danamon", "Bank Danamon", "https://www.danamon.co.id", "SWASTA_NASIONAL", "KONVENSIONAL", True),
    ("PANIN", "Panin Bank", "Panin Bank", "https://www.panin.co.id", "SWASTA_NASIONAL", "KONVENSIONAL", False),
    ("BJB", "Bank BJB", "Bank Pembangunan Daerah Jawa Barat dan Banten", "https://www.bankbjb.co.id", "SWASTA_NASIONAL", "KONVENSIONAL", False),
    ("BTPN", "Bank BTPN", "Bank BTPN", "https://www.btpn.com", "SWASTA_NASIONAL", "KONVENSIONAL", False),  # DNS resolves but may be blocked by Cloudflare
    ("SINARMAS", "Bank Sinarmas", "Bank Sinarmas", "https://www.banksinarmas.com", "SWASTA_NASIONAL", "KONVENSIONAL", False),
    ("BUKOPIN", "KB Bank (formerly Bukopin)", "KB Bank (eks Bukopin)", "https://www.kbbank.co.id", "SWASTA_NASIONAL", "KONVENSIONAL", False),
    ("MAYAPADA", "Bank Mayapada", "Bank Mayapada", "https://www.bankmayapada.com", "SWASTA_NASIONAL", "KONVENSIONAL", False),
    ("MEGA", "Bank Mega", "Bank Mega", "https://www.bankmega.com", "SWASTA_NASIONAL", "KONVENSIONAL", False),
    ("ANDARA", "Bank Andara", "Bank Andara", "https://www.bankandara.co.id", "SWASTA_NASIONAL", "KONVENSIONAL", False),
    ("OCBC", "OCBC NISP", "OCBC NISP", "https://www.ocbc.id", "SWASTA_NASIONAL", "KONVENSIONAL", True),
    # --- Asing (6) ---
    ("STANCHART", "Standard Chartered", "Standard Chartered", "https://www.sc.com/id", "ASING", "KONVENSIONAL", False),
    ("CITIBANK", "Citibank", "Citibank", "https://www.citibank.co.id", "ASING", "KONVENSIONAL", False),
    ("HSBC", "HSBC Indonesia", "HSBC Indonesia", "https://www.hsbc.co.id", "ASING", "KONVENSIONAL", False),
    ("DBS", "DBS Indonesia", "DBS Indonesia", "https://www.dbs.id", "ASING", "KONVENSIONAL", False),
    ("UOB", "UOB Indonesia", "UOB Indonesia", "https://www.uob.co.id", "ASING", "KONVENSIONAL", True),
    ("DEUTSCHE", "Deutsche Bank", "Deutsche Bank", "https://www.db.com/indonesia", "ASING", "KONVENSIONAL", False),
    # --- BPD (27) ---
    ("BPDDIY", "Bank BPD DIY", "Bank Pembangunan Daerah DIY", "https://www.bpddiy.co.id", "BPD", "KONVENSIONAL", False),
    ("BPDJT", "Bank DKI", "Bank DKI", "https://www.bankdki.co.id", "BPD", "KONVENSIONAL", False),
    ("BANKJATENG", "Bank Jateng", "Bank Pembangunan Daerah Jawa Tengah", "https://www.bankjateng.co.id", "BPD", "KONVENSIONAL", False),
    ("BANKJATIM", "Bank Jatim", "Bank Pembangunan Daerah Jawa Timur", "https://www.bankjatim.co.id", "BPD", "KONVENSIONAL", False),
    ("BANKKALTENG", "Bank Kalteng", "Bank Pembangunan Daerah Kalimantan Tengah", "https://www.bankkalteng.co.id", "BPD", "KONVENSIONAL", False),
    ("BANKKALIMANTAN", "Bank Kalbar", "Bank Pembangunan Daerah Kalimantan Barat", "https://www.bankkalbar.co.id", "BPD", "KONVENSIONAL", False),
    ("SUMSELBABEL", "Bank Sumsel Babel", "Bank Pembangunan Daerah Sumatera Selatan dan Bangka Belitung", "https://www.banksumselbabel.com", "BPD", "KONVENSIONAL", False),
    ("BANTEN", "Bank Banten", "Bank Pembangunan Daerah Banten", "https://www.bankbanten.co.id", "BPD", "KONVENSIONAL", False),
    ("NUSA", "Bank NTB Syariah", "Bank NTB Syariah", "https://www.bankntbsyariah.co.id", "BPD", "SYARIAH", False),
    ("SAUDARA", "Bank Woori Saudara", "Bank Woori Saudara", "https://www.banksaudara.com", "BPD", "KONVENSIONAL", False),
    ("NTB", "Bank NTB", "Bank NTB", "https://www.bankntbsyariah.co.id", "BPD", "KONVENSIONAL", False),  # Bank NTB converted to full syariah in 2018; same entity as NUSA
    ("NTT", "Bank NTT", "Bank NTT", "https://www.bankntt.co.id", "BPD", "KONVENSIONAL", False),
    ("MALUKU", "Bank Maluku Malut", "Bank Maluku Malut", "https://www.bankmalukumalut.co.id", "BPD", "KONVENSIONAL", False),
    ("PAPUA", "Bank Papua", "Bank Papua", "https://www.bankpapua.co.id", "BPD", "KONVENSIONAL", False),
    ("SULSELBAR", "Bank Sulselbar", "Bank Sulselbar", "https://www.banksulselbar.co.id", "BPD", "KONVENSIONAL", False),
    ("GORONTALO", "Bank SulutGo (Gorontalo)", "Bank SulutGo (Gorontalo)", "https://www.banksulutgo.co.id", "BPD", "KONVENSIONAL", False),  # Gorontalo merged into Bank SulutGo (BPD Sulut+Gorontalo); same URL as SULUT entry
    ("SULUT", "Bank SulutGo", "Bank SulutGo", "https://www.banksulutgo.co.id", "BPD", "KONVENSIONAL", False),
    ("MALUKUUTARA", "Bank Maluku Utara", "Bank Maluku Utara", "https://www.bankmalukumalut.co.id", "BPD", "KONVENSIONAL", False),  # Merged with Bank Maluku → Bank Maluku Malut; same URL as MALUKU entry
    ("KALSEL", "Bank Kalsel", "Bank Kalsel", "https://www.bankkalsel.co.id", "BPD", "KONVENSIONAL", False),
    ("KALBAR", "Bank Kalbar", "Bank Kalbar", "https://www.bankkalbar.co.id", "BPD", "KONVENSIONAL", False),
    ("KALTARA", "Bankaltimtara (Kaltara)", "Bankaltimtara (Kaltara)", "https://www.bankaltimtara.co.id", "BPD", "KONVENSIONAL", False),  # Kaltara province joined BPD Kaltim → renamed Bankaltimtara in 2017
    ("BENGKULU", "Bank Bengkulu", "Bank Bengkulu", "https://bankbengkulu.co.id", "BPD", "KONVENSIONAL", False),
    ("JAMBI", "Bank Jambi", "Bank Jambi", "https://bankjambi.co.id", "BPD", "KONVENSIONAL", False),  # DNS resolves but server is unresponsive (scout will mark unreachable)
    ("RIAUKEPRI", "BRK Syariah (formerly Bank Riau Kepri)", "BRK Syariah (eks Bank Riau Kepri)", "https://www.brksyariah.co.id", "BPD", "SYARIAH", False),
    ("LAMPUNG", "Bank Lampung", "Bank Lampung", "https://www.banklampung.co.id", "BPD", "KONVENSIONAL", False),
    ("SUMSEL", "Bank Sumsel", "Bank Sumsel", "https://www.banksumselbabel.com", "BPD", "KONVENSIONAL", False),  # Merged with Bank Babel → Bank Sumsel Babel; same URL as SUMSELBABEL entry
    ("SUMUT", "Bank Sumut", "Bank Sumut", "https://www.banksumut.co.id", "BPD", "KONVENSIONAL", False),
    # --- Syariah (8) ---
    ("BSI", "Bank Syariah Indonesia", "Bank Syariah Indonesia", "https://www.bankbsi.co.id", "SYARIAH", "SYARIAH", True),
    ("BCAS", "BCA Syariah", "BCA Syariah", "https://www.bcasyariah.co.id", "SYARIAH", "SYARIAH", False),
    ("BNIS", "BNI Syariah", "BNI Syariah", "https://www.bnisyariah.co.id", "SYARIAH", "SYARIAH", False),
    ("BRIS", "BRI Syariah", "BRI Syariah", "https://www.brisyariah.co.id", "SYARIAH", "SYARIAH", False),
    ("MANDIRIS", "Mandiri Syariah", "Mandiri Syariah", "https://www.mandirisyariah.co.id", "SYARIAH", "SYARIAH", False),
    ("BTNIS", "BTN Syariah", "BTN Syariah", "https://www.btn.co.id/syariah", "SYARIAH", "SYARIAH", False),
    ("JATIMSY", "Bank Jatim Syariah", "Bank Jatim Syariah", "https://www.bankjatim.co.id/syariah", "SYARIAH", "SYARIAH", False),
    ("NAGARI", "Bank Nagari", "Bank Nagari", "https://www.banknagari.co.id", "SYARIAH", "SYARIAH", False),
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
