import streamlit as st
import pandas as pd
import os
import json
from datetime import datetime
from zoneinfo import ZoneInfo
from urllib.parse import quote
import io
import random
import gspread
from google.oauth2.service_account import Credentials
from PIL import Image, ImageDraw, ImageFont

# ============================================================
# KONFIGURASI
# ============================================================

NAMA_WORKSHEET_PESANAN = "Pesanan"
NAMA_WORKSHEET_PRODUK_SNIPER = "Produk_Sniper"
NAMA_WORKSHEET_PRODUK_MATENGAN = "Produk_Matengan"
NAMA_WORKSHEET_STATUS = "StatusKirim"

# Zona waktu WIB (Waktu Indonesia Barat, UTC+7).
# Dipakai untuk SEMUA timestamp di aplikasi ini supaya tidak
# tergantung timezone server (mis. Railway biasanya UTC).
WIB = ZoneInfo("Asia/Jakarta")

def now_wib():
    """Waktu sekarang di zona WIB (real-time, bukan waktu server)."""
    return datetime.now(WIB)


st.set_page_config(
    page_title="Form Pesanan Outlet",
    page_icon="🛒",
    layout="centered",
)

# ============================================================
# CSS + FLOATING SCROLL CONTROLLER
# ============================================================

st.html(
    """
<style>
/* ========================================================
   GLOBAL MOBILE / DESKTOP
   ======================================================== */
.block-container {
    padding-top: clamp(1rem, 3vw, 2.5rem) !important;
    padding-bottom: 5rem !important;
}

/* ========================================================
   HEADER / JUDUL — supaya judul & ikon tidak terpotong di HP
   Header Streamlit (hamburger menu, dsb) posisinya fixed/overlay
   di atas konten. Di layar sempit, padding-top bawaan tidak
   cukup untuk membuat judul turun di bawah header tersebut,
   sehingga bagian atas huruf/ikon judul terpotong.
   ======================================================== */
header[data-testid="stHeader"] {
    height: 2.75rem !important;
    background: transparent !important;
}

.block-container h1 {
    overflow: visible !important;
    line-height: 1.35 !important;
    word-break: break-word !important;
    margin-top: 0 !important;
}

.block-container h1 > div,
.block-container h1 span {
    overflow: visible !important;
}

@media (max-width: 600px) {
    .block-container {
        padding-top: 3.6rem !important;
    }

    .block-container h1 {
        line-height: 1.4 !important;
    }
}

/* ========================================================
   HEADER STATIS (2 BARIS) — TIDAK RESPONSIVE
   Ukuran font memakai px tetap (bukan clamp/vw/rem responsif)
   supaya tampilan header sama persis di PC, laptop, maupun HP.
   ======================================================== */
.wg-header {
    margin: 0 0 0.15rem 0 !important;
}

.wg-header-line1 {
    font-size: 36px !important;
    font-weight: 800 !important;
    line-height: 1.25 !important;
    color: #1a1a1a !important;
    white-space: nowrap !important;
}

.wg-header-line2 {
    font-size: 36px !important;
    font-weight: 800 !important;
    line-height: 1.25 !important;
    color: #1a1a1a !important;
    white-space: nowrap !important;
}

/* Ukuran subheader ("Data Outlet", "Pilih Provider") dikunci dengan
   px tetap dan dibuat lebih kecil dari header utama di atas, supaya
   hirarki ukuran (Header > Subheader) sama persis di semua device.
   Margin atas/bawahnya juga dirapatkan supaya tidak banyak ruang
   kosong di sekitar tiap judul section. */
.block-container h3 {
    font-size: 20px !important;
    line-height: 1.35 !important;
    white-space: nowrap !important;
    margin-top: 0.3rem !important;
    margin-bottom: 0.2rem !important;
}

/* Rapatkan garis pembatas (divider) antar section utama, supaya
   tidak ada jarak besar yang terbuang sia-sia. */
.block-container hr {
    margin: 0.5rem 0 !important;
}

/* Rapatkan jarak bawah widget umum (dropdown/input) di luar
   product card, tanpa mengubah spacing di dalam card produk
   (yang sudah diatur khusus lewat aturan stVerticalBlockBorderWrapper
   di bawah dan menang karena urutannya lebih akhir). */
.block-container div[data-testid="element-container"] {
    margin-bottom: 0.3rem !important;
}

/* ========================================================
   PRODUCT CARD
   ======================================================== */
div[data-testid="stVerticalBlockBorderWrapper"] {
    border-radius: 12px !important;
    padding: 0.45rem 0.5rem !important;
}

div[data-testid="stVerticalBlockBorderWrapper"]
div[data-testid="stHorizontalBlock"] {
    flex-wrap: nowrap !important;
    align-items: center !important;
    gap: 0.35rem !important;
}

div[data-testid="stVerticalBlockBorderWrapper"]
div[data-testid="stHorizontalBlock"] > div {
    min-width: 0 !important;
}

div[data-testid="stVerticalBlockBorderWrapper"]
div[data-testid="stVerticalBlock"] {
    gap: 0.05rem !important;
}

div[data-testid="stVerticalBlockBorderWrapper"]
div[data-testid="element-container"] {
    margin-bottom: 0 !important;
    margin-top: 0 !important;
}

div[data-testid="stVerticalBlockBorderWrapper"]
div[data-testid="stMarkdownContainer"] p,
div[data-testid="stVerticalBlockBorderWrapper"]
[data-testid="stCaptionContainer"] p {
    margin: 0 !important;
    padding: 0 !important;
    line-height: 1.1 !important;
}

/* Nama produk & provider dirender lewat HTML custom (bukan
   st.markdown + st.caption terpisah) supaya jaraknya bisa
   dikontrol persis dan tidak renggang seperti bawaan Streamlit. */
.wg-prod-name {
    font-weight: 700 !important;
    font-size: 0.95rem !important;
    line-height: 1.25 !important;
    color: #1a1a1a !important;
    margin: 0 !important;
    padding: 0 !important;
}

.wg-prod-provider {
    font-size: 0.78rem !important;
    line-height: 1.15 !important;
    color: rgba(49, 51, 63, 0.6) !important;
    margin: 0.05rem 0 0 0 !important;
    padding: 0 !important;
}

/* ========================================================
   QTY BOX: - | ANGKA | +
   Target langsung via key (bukan posisi/nth-child) supaya
   tidak rapuh terhadap elemen tambahan di DOM.
   ======================================================== */
div[class*="st-key-qtybox-"] {
    margin-top: 0.05rem !important;
}

div[class*="st-key-qtybox-"] div[data-testid="stHorizontalBlock"] {
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    gap: 0 !important;
    border: 1px solid rgba(49, 51, 63, 0.20) !important;
    border-radius: 8px !important;
    overflow: hidden !important;
    background: rgba(250, 250, 250, 0.8) !important;
}

div[class*="st-key-qtybox-"] div[data-testid="stHorizontalBlock"] > div {
    min-width: 0 !important;
    padding: 0 !important;
    margin: 0 !important;
}

div[class*="st-key-qtybox-"] [data-testid="stColumn"],
div[class*="st-key-qtybox-"] [data-testid="stVerticalBlock"],
div[class*="st-key-qtybox-"] [data-testid="element-container"],
div[class*="st-key-qtybox-"] [data-testid="stElementContainer"] {
    padding: 0 !important;
    margin: 0 !important;
}

/* Tombol MINUS & PLUS ditembak langsung lewat key-nya sendiri */
div[class*="st-key-qty_minus_"],
div[class*="st-key-qty_plus_"] {
    width: 100% !important;
}

div[class*="st-key-qty_minus_"] button,
div[class*="st-key-qty_plus_"] button {
    width: 100% !important;
    height: 24px !important;
    min-height: 24px !important;
    max-height: 24px !important;
    padding: 0 !important;
    margin: 0 !important;
    border: none !important;
    border-radius: 0 !important;
    background: transparent !important;
    color: #30323d !important;
    opacity: 1 !important;
    visibility: visible !important;
    font-size: 13px !important;
    font-weight: 700 !important;
    line-height: 1 !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
}

div[class*="st-key-qty_minus_"] button *,
div[class*="st-key-qty_plus_"] button * {
    color: inherit !important;
    opacity: 1 !important;
    visibility: visible !important;
    font-size: 13px !important;
    font-weight: 700 !important;
    line-height: 1 !important;
}

div[class*="st-key-qty_minus_"] button:hover,
div[class*="st-key-qty_plus_"] button:hover {
    background: rgba(0, 0, 0, 0.04) !important;
    color: #111 !important;
}

div[class*="st-key-qty_minus_"] button:active,
div[class*="st-key-qty_plus_"] button:active {
    background: rgba(0, 0, 0, 0.08) !important;
}

/* Garis pemisah pil: minus di kiri, plus di kanan */
div[class*="st-key-qty_minus_"] {
    border-right: 1px solid rgba(49, 51, 63, 0.15) !important;
}

div[class*="st-key-qty_plus_"] {
    border-left: 1px solid rgba(49, 51, 63, 0.15) !important;
}

/* Input angka di tengah — tetap bisa diketik manual.
   Hanya background/border/padding lapisan bawaan Streamlit yang
   dinolkan (bukan display/height dipaksa flex ke semua div),
   supaya struktur internal komponen input tidak rusak dan angka
   tetap tampil & bisa diklik +/- seperti biasa. */
div[class*="st-key-qtybox-"] div[data-testid="stTextInput"] {
    width: 100% !important;
    background: transparent !important;
}

div[class*="st-key-qtybox-"] div[data-testid="stTextInput"] > div {
    border: none !important;
    box-shadow: none !important;
    background: transparent !important;
    padding: 0 !important;
    margin: 0 !important;
}

div[class*="st-key-qtybox-"] div[data-testid="stTextInput"] div[data-baseweb="input"],
div[class*="st-key-qtybox-"] div[data-testid="stTextInput"] div[data-baseweb="base-input"] {
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
    border-radius: 0 !important;
    padding: 0 !important;
    margin: 0 !important;
}

div[class*="st-key-qtybox-"] div[data-testid="stTextInput"] input {
    width: 100% !important;
    border: none !important;
    background: transparent !important;
    box-shadow: none !important;
    text-align: center !important;
    height: 24px !important;
    line-height: 24px !important;
    padding: 0 4px !important;
    margin: 0 !important;
    font-weight: 700 !important;
    font-size: 12px !important;
    color: #30323d !important;
}

div[class*="st-key-qtybox-"] [data-testid="InputInstructions"] {
    display: none !important;
}

/* ========================================================
   PAGINATION PRODUK
   Dipaksa tetap satu baris (tidak stack) di layar sempit/HP,
   dengan lebar kiri-kanan simetris. Tombol nomor halaman
   memakai ukuran seragam & kompak.
   ======================================================== */
div[class*="st-key-wg-pagination"] div[data-testid="stHorizontalBlock"] {
    flex-wrap: nowrap !important;
    align-items: center !important;
    gap: 0.25rem !important;
}

div[class*="st-key-wg-pagination"] div[data-testid="stHorizontalBlock"] > div {
    min-width: 0 !important;
}

div[class*="st-key-wg-pagination"] .stButton > button {
    width: 100% !important;
    height: 34px !important;
    min-height: 34px !important;
    max-height: 34px !important;
    min-width: 0 !important;
    padding: 0 0.2rem !important;
    font-size: 0.78rem !important;
    white-space: nowrap !important;
}

div[class*="st-key-wg-pagination"] .wg-pagination-ellipsis {
    height: 34px !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    font-size: 0.8rem !important;
    color: rgba(49, 51, 63, 0.45) !important;
    letter-spacing: 1px;
}

@media (max-width: 480px) {
    div[class*="st-key-wg-pagination"] .stButton > button {
        font-size: 0.7rem !important;
        padding: 0 0.1rem !important;
    }

    div[class*="st-key-wg-pagination"] .wg-pagination-ellipsis {
        font-size: 0.75rem !important;
    }
}

/* ========================================================
   PANEL ADMIN
   ======================================================== */
section[data-testid="stSidebar"]
div[data-testid="stVerticalBlockBorderWrapper"] {
    border-radius: 10px !important;
    padding: 0.7rem 0.85rem !important;
}

.wg-admin-card-total {
    font-size: 0.86rem;
    color: rgba(49, 51, 63, 0.72);
}

.wg-admin-empty {
    color: rgba(49, 51, 63, 0.55);
    font-size: 0.85rem;
    padding: 0.35rem 0;
}

section[data-testid="stSidebar"] hr {
    margin: 0.9rem 0 !important;
}

/* ========================================================
   ADMIN ACTION BUTTONS
   Kirim WhatsApp dan Tandai/Batalkan dibuat sama tinggi
   ======================================================== */
.wg-admin-actions {
    width: 100% !important;
}

.wg-admin-actions .stButton,
.wg-admin-actions [data-testid="stLinkButton"] {
    width: 100% !important;
}

.wg-admin-actions .stButton > button,
.wg-admin-actions [data-testid="stLinkButton"] {
    width: 100% !important;
    height: 42px !important;
    min-height: 42px !important;
    max-height: 42px !important;
    padding: 0 0.65rem !important;
    margin: 0 !important;
    box-sizing: border-box !important;
    border-radius: 8px !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    line-height: 1 !important;
}

.wg-admin-actions .stButton > button p,
.wg-admin-actions .stButton > button div,
.wg-admin-actions [data-testid="stLinkButton"] p,
.wg-admin-actions [data-testid="stLinkButton"] div {
    margin: 0 !important;
    line-height: 1.1 !important;
}

/* ========================================================
   ADMIN FULLSCREEN
   ======================================================== */
body.wg-admin-fullscreen section[data-testid="stSidebar"] {
    width: 100vw !important;
    min-width: 100vw !important;
    max-width: 100vw !important;
    z-index: 1000000 !important;
}

body.wg-admin-fullscreen section[data-testid="stSidebar"] > div {
    width: 100vw !important;
}

body.wg-admin-fullscreen section[data-testid="stSidebarContent"] {
    max-width: 1180px !important;
    margin: 0 auto !important;
    padding: 2rem clamp(1rem, 4vw, 3rem) 4rem !important;
}

body.wg-admin-fullscreen .main {
    visibility: hidden !important;
}


/* Catatan: ukuran tombol qty & padding card SENGAJA tidak diberi
   override khusus mobile lagi, supaya tampilannya statis/sama
   persis baik dibuka di PC, laptop, maupun HP. */

/* ========================================================
   BARIS HARGA + QTY (SATU BARIS, QTY DI SEBELAH KANAN HARGA)
   flex-wrap: nowrap dipaksa supaya harga & kontrol qty selalu
   sejajar dalam satu baris di device manapun (tidak pernah
   turun/stack ke bawah seperti perilaku default kolom Streamlit
   di layar sempit).
   ======================================================== */
div[class*="st-key-pricerow-"] div[data-testid="stHorizontalBlock"] {
    flex-wrap: nowrap !important;
    align-items: center !important;
    gap: 0.4rem !important;
}

div[class*="st-key-pricerow-"] div[data-testid="stHorizontalBlock"] > div {
    min-width: 0 !important;
}
</style>

""",
    unsafe_allow_javascript=True,
)

# ============================================================
# KONEKSI GOOGLE SHEETS
# ============================================================

@st.cache_resource
def connect_sheet():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]

    # ========================================================
    # AMBIL GOOGLE SERVICE ACCOUNT DARI RAILWAY VARIABLES
    # ========================================================
    gcp_service_account = json.loads(
        os.environ["gcp_service_account"]
    )

    spreadsheet_url = os.environ["spreadsheet_url"]

    # ========================================================
    # BUAT CREDENTIALS
    # ========================================================
    creds = Credentials.from_service_account_info(
        gcp_service_account,
        scopes=scopes,
    )

    client = gspread.authorize(creds)

    spreadsheet = client.open_by_url(spreadsheet_url)

    # ========================================================
    # WORKSHEET
    # ========================================================
    ws_pesanan = spreadsheet.worksheet(NAMA_WORKSHEET_PESANAN)
    ws_produk_sniper = spreadsheet.worksheet(NAMA_WORKSHEET_PRODUK_SNIPER)
    ws_produk_matengan = spreadsheet.worksheet(NAMA_WORKSHEET_PRODUK_MATENGAN)

    try:
        ws_status = spreadsheet.worksheet(NAMA_WORKSHEET_STATUS)

    except gspread.exceptions.WorksheetNotFound:
        ws_status = spreadsheet.add_worksheet(
            title=NAMA_WORKSHEET_STATUS,
            rows=1000,
            cols=3,
        )

        ws_status.append_row(
            ["order_id", "status_kirim", "waktu_ditandai"],
            value_input_option="USER_ENTERED",
        )

    return ws_pesanan, ws_produk_sniper, ws_produk_matengan, ws_status


try:
    (
        worksheet,
        worksheet_produk_sniper,
        worksheet_produk_matengan,
        worksheet_status,
    ) = connect_sheet()
    sheet_ok = True

except Exception as e:
    sheet_ok = False

    st.error(
        "Gagal konek ke Google Sheets. Cek konfigurasi "
        "gcp_service_account dan spreadsheet_url, serta "
        "pastikan Google Sheet sudah di-share ke email "
        "service account."
    )

    st.exception(e)
    st.stop()

# ============================================================
# LOAD PRODUK
# ============================================================

@st.cache_data(ttl=60)
def load_produk(_worksheet_produk, kategori_key):
    data = _worksheet_produk.get_all_records()
    df = pd.DataFrame(data)

    if df.empty:
        return df

    df["harga"] = (
        pd.to_numeric(df["harga"], errors="coerce")
        .fillna(0)
        .astype(int)
    )

    return df

# Catatan: produk_df (dan qty state yang bergantung padanya) baru
# dimuat setelah pengguna memilih Kategori (Sniper/Matengan) di
# bagian "PILIH KATEGORI" di bawah, supaya sheet yang dibaca sesuai
# kategori yang aktif.

# ============================================================
# SESSION STATE (UMUM — TIDAK BERGANTUNG PADA PRODUK)
# ============================================================
# Hanya satu sumber data untuk qty: st.session_state.qty (diinisialisasi
# nanti setelah produk_df tersedia). Tidak ada state dengan key
# qtyinput_*, sehingga tidak mungkin terjadi konflik antara default
# value widget dan Session State API.

if "last_receipt" not in st.session_state:
    st.session_state.last_receipt = None
if "last_receipt_name" not in st.session_state:
    st.session_state.last_receipt_name = None
if "show_success" not in st.session_state:
    st.session_state.show_success = False
if "last_wa_link" not in st.session_state:
    st.session_state.last_wa_link = None
if "last_cs_wa_link" not in st.session_state:
    st.session_state.last_cs_wa_link = None
if "last_order_id" not in st.session_state:
    st.session_state.last_order_id = None

# Input SN (Serial Number) per kode_voucher: {kode: {"awal": str, "akhir": str}}
if "sn_input" not in st.session_state:
    st.session_state.sn_input = {}


def _parse_qty(value):
    try:
        return max(0, int(str(value).strip() or "0"))
    except (TypeError, ValueError):
        return 0


def generate_sn_list(sn_awal, sn_akhir):
    """
    Generate daftar SN berurutan dari sn_awal ke sn_akhir (inklusif).
    Mengembalikan tuple (list_sn, pesan_error).
    Kalau salah satu input masih kosong, kembalikan ([], None)
    supaya belum dianggap error (user belum selesai isi).
    """
    sn_awal = (sn_awal or "").strip()
    sn_akhir = (sn_akhir or "").strip()

    if not sn_awal or not sn_akhir:
        return [], None

    if not sn_awal.isdigit() or not sn_akhir.isdigit():
        return [], "SN Awal/Akhir harus berupa angka."

    if len(sn_awal) != len(sn_akhir):
        return [], "Jumlah digit SN Awal dan SN Akhir harus sama."

    digit_len = len(sn_awal)
    awal_int = int(sn_awal)
    akhir_int = int(sn_akhir)

    if akhir_int < awal_int:
        return [], "SN Akhir harus lebih besar atau sama dengan SN Awal."

    jumlah = akhir_int - awal_int + 1

    if jumlah > 500:
        return [], "Range SN terlalu besar (maks 500 sekali input)."

    list_sn = [
        str(awal_int + i).zfill(digit_len) for i in range(jumlah)
    ]

    return list_sn, None


def tambah(kode):
    st.session_state.qty[kode] = st.session_state.qty.get(kode, 0) + 1


def kurang(kode):
    st.session_state.qty[kode] = max(
        0, st.session_state.qty.get(kode, 0) - 1
    )


def format_rupiah(n):
    return f"Rp {n:,.0f}".replace(",", ".")


def buat_order_id():
    now = now_wib()
    acak = random.randint(100, 999)
    return f"ORD-{now.strftime('%y%m%d-%H%M%S')}-{acak}"


def format_no_wa(no_wa):
    digits = "".join(ch for ch in no_wa if ch.isdigit())

    if digits.startswith("0"):
        digits = "62" + digits[1:]
    elif digits.startswith("620"):
        digits = "62" + digits[3:]
    elif not digits.startswith("62"):
        digits = "62" + digits

    return digits


def build_nota_wa_text(
    order_id,
    nama_outlet,
    no_wa,
    alamat_pengiriman,
    timestamp,
    detail_pesanan,
    total_harga,
):
    garis = "━" * 20

    baris = [
        "Halo,",
        "Terima kasih telah melakukan pemesanan di Toko WG.",
        "Berikut kami sampaikan nota pesanan Anda:",
        "",
        "*NOTA PESANAN TOKO WG*",
        f"Order ID : {order_id}",
        f"Tanggal  : {timestamp}",
        f"Outlet   : {nama_outlet}",
        f"No. WA   : {no_wa}",
    ]

    if alamat_pengiriman:
        baris.append(f"Alamat   : {alamat_pengiriman}")

    baris.append(garis)
    baris.append("*Detail Pesanan*")

    for idx, item in enumerate(detail_pesanan, start=1):
        baris.append(f"{idx}. {item['produk']}")
        baris.append(f"   Qty      : {item['qty']}")
        baris.append(
            f"   Harga    : {format_rupiah(item['harga_satuan'])}"
        )
        baris.append(
            f"   Subtotal : {format_rupiah(item['subtotal'])}"
        )

    baris.append(garis)
    baris.append("*TOTAL PESANAN*")
    baris.append(format_rupiah(total_harga))
    baris.append("")
    baris.append(
        "Mohon diperiksa kembali detail pesanan tersebut."
    )
    baris.append(
        "Terima kasih atas kepercayaan Anda kepada Toko WG."
    )

    return "\n".join(baris)


def build_konfirmasi_cs_text(
    order_id,
    nama_outlet,
    no_wa,
    alamat_pengiriman,
    timestamp,
    detail_pesanan,
    total_harga,
):
    """
    Template pesan WhatsApp dari OUTLET ke CS/Admin untuk
    konfirmasi pesanan yang baru saja dibuat outlet tersebut.
    """
    garis = "━" * 20

    baris = [
        "Halo Admin Toko WG,",
        "Saya ingin melakukan konfirmasi terkait pesanan yang baru saja saya buat:",
        "",
        "*KONFIRMASI PESANAN OUTLET*",
        f"Order ID : {order_id}",
        f"Tanggal  : {timestamp}",
        f"Outlet   : {nama_outlet}",
        f"No. WA   : {no_wa}",
    ]

    if alamat_pengiriman:
        baris.append(f"Alamat   : {alamat_pengiriman}")

    baris.append(garis)
    baris.append("*Detail Pesanan*")

    for idx, item in enumerate(detail_pesanan, start=1):
        baris.append(f"{idx}. [{item['provider']}] {item['produk']}")
        baris.append(f"   Qty      : {item['qty']}")
        baris.append(
            f"   Harga    : {format_rupiah(item['harga_satuan'])}"
        )
        baris.append(
            f"   Subtotal : {format_rupiah(item['subtotal'])}"
        )

    baris.append(garis)
    baris.append("*TOTAL PESANAN*")
    baris.append(format_rupiah(total_harga))
    baris.append("")
    baris.append(
        "Mohon konfirmasi dan tindak lanjut atas pesanan tersebut. "
        "Terima kasih atas perhatian dan bantuannya."
    )

    return "\n".join(baris)


def build_receipt_lines(
    order_id,
    nama_outlet,
    no_wa,
    alamat_pengiriman,
    timestamp,
    detail_pesanan,
    total_harga,
):
    lines = [
        ("title", "STRUK PEMESANAN OUTLET TOKO WG"),
        ("sep", ""),
        ("normal", f"Order ID: {order_id}"),
        ("normal", f"Tanggal : {timestamp}"),
        ("normal", f"Outlet  : {nama_outlet}"),
        ("normal", f"No. WA  : {no_wa}"),
    ]

    if alamat_pengiriman:
        lines.append(("normal", f"Alamat  : {alamat_pengiriman}"))

    lines.append(("sep", ""))

    for item in detail_pesanan:
        lines.append(
            (
                "item",
                f"[{item['provider']}] {item['produk']}",
            )
        )
        lines.append(
            (
                "sub",
                f"{item['qty']} x "
                f"{format_rupiah(item['harga_satuan'])} = "
                f"{format_rupiah(item['subtotal'])}",
            )
        )

    lines.append(("sep", ""))
    lines.append(
        ("total", f"TOTAL: {format_rupiah(total_harga)}")
    )
    lines.append(("sep", ""))
    lines.append(("footer", "Terima kasih atas pesanan Anda!"))

    return lines


def _load_font(size, bold=False):
    kandidat = (
        ["consolab.ttf", "courbd.ttf"]
        if bold
        else ["consola.ttf", "cour.ttf", "DejaVuSansMono.ttf"]
    )

    for nama in kandidat:
        try:
            return ImageFont.truetype(nama, size)
        except Exception:
            continue

    return ImageFont.load_default()


def build_receipt_image(
    order_id,
    nama_outlet,
    no_wa,
    alamat_pengiriman,
    timestamp,
    detail_pesanan,
    total_harga,
):
    lines = build_receipt_lines(
        order_id,
        nama_outlet,
        no_wa,
        alamat_pengiriman,
        timestamp,
        detail_pesanan,
        total_harga,
    )

    width = 480
    padding = 20
    line_height = 22

    font_normal = _load_font(16)
    font_title = _load_font(20, bold=True)
    font_total = _load_font(18, bold=True)

    height = padding * 2 + sum(
        (
            28
            if tipe == "title"
            else 10
            if tipe == "sep"
            else 20
            if tipe == "total"
            else line_height
        )
        for tipe, _ in lines
    )

    img = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(img)
    y = padding

    for tipe, teks in lines:
        if tipe == "sep":
            draw.line(
                [
                    (padding, y + 5),
                    (width - padding, y + 5),
                ],
                fill=(180, 180, 180),
                width=1,
            )
            y += 10

        elif tipe == "title":
            bbox = draw.textbbox(
                (0, 0),
                teks,
                font=font_title,
            )
            tw = bbox[2] - bbox[0]
            draw.text(
                ((width - tw) / 2, y),
                teks,
                fill="black",
                font=font_title,
            )
            y += 28

        elif tipe == "total":
            bbox = draw.textbbox(
                (0, 0),
                teks,
                font=font_total,
            )
            tw = bbox[2] - bbox[0]
            draw.text(
                (width - padding - tw, y),
                teks,
                fill="black",
                font=font_total,
            )
            y += 20

        elif tipe == "footer":
            bbox = draw.textbbox(
                (0, 0),
                teks,
                font=font_normal,
            )
            tw = bbox[2] - bbox[0]
            draw.text(
                ((width - tw) / 2, y),
                teks,
                fill=(90, 90, 90),
                font=font_normal,
            )
            y += line_height

        elif tipe == "sub":
            draw.text(
                (padding + 12, y),
                teks,
                fill=(90, 90, 90),
                font=font_normal,
            )
            y += line_height

        else:
            draw.text(
                (padding, y),
                teks,
                fill="black",
                font=font_normal,
            )
            y += line_height

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# ============================================================
# HELPER STATUS KIRIM
# ============================================================

def get_status_map(ws_status):
    """Baca worksheet StatusKirim -> dict {order_id: True/False}."""
    try:
        data = ws_status.get_all_records()
    except Exception:
        return {}

    status_map = {}

    for r in data:
        oid = str(r.get("order_id", "")).strip()

        if not oid:
            continue

        nilai = str(r.get("status_kirim", "")).strip().upper()
        status_map[oid] = nilai == "TRUE"

    return status_map


def tandai_terkirim(ws_status, order_id):
    """Catat order_id sebagai sudah terkirim."""
    ws_status.append_row(
        [
            order_id,
            "TRUE",
            now_wib().strftime("%Y-%m-%d %H:%M:%S"),
        ],
        value_input_option="USER_ENTERED",
    )


def batalkan_tandai(ws_status, order_id):
    """Undo: hapus baris status_kirim untuk order_id."""
    try:
        sel = ws_status.findall(order_id)
    except Exception:
        sel = []

    for cell in sorted(sel, key=lambda c: c.row, reverse=True):
        if cell.col == 1:
            ws_status.delete_rows(cell.row)


# ============================================================
# HEADER
# ============================================================

st.markdown(
    """
    <div class="wg-header">
        <div class="wg-header-line1">🛒 Toko WG</div>
        <div class="wg-header-line2">Form Order</div>
    </div>
    """,
    unsafe_allow_html=True,
)
st.caption("Isi data outlet, lalu pilih voucher dan jumlahnya.")

# ============================================================
# DATA OUTLET
# ============================================================

st.subheader("Data Outlet")

col1, col2 = st.columns(2)

with col1:
    nama_outlet = st.text_input(
        "Nama Outlet",
        placeholder="Konter ABC Cell",
    )

with col2:
    no_wa = st.text_input(
        "No. WhatsApp",
        placeholder="08123456789",
    )

alamat_pengiriman = st.text_input(
    "Alamat Pengiriman",
    placeholder="Jl. Ahmad Yani No. 2",
)

st.caption("Alamat pengiriman hanya untuk transaksi Fisik Matengan")
st.divider()

# ============================================================
# PILIH KATEGORI
# ============================================================

st.subheader("Pilih Kategori")

kategori_terpilih = st.selectbox(
    "Filter Kategori",
    ["Sniper", "Matengan"],
    label_visibility="collapsed",
)

if kategori_terpilih == "Sniper":
    worksheet_produk_aktif = worksheet_produk_sniper
else:
    worksheet_produk_aktif = worksheet_produk_matengan

produk_df = load_produk(worksheet_produk_aktif, kategori_terpilih)

if produk_df.empty:
    st.warning(
        f"Belum ada data produk pada worksheet "
        f"Produk_{kategori_terpilih}."
    )
    st.stop()

# Qty state bergantung pada daftar produk kategori yang sedang aktif.
if "qty" not in st.session_state:
    st.session_state.qty = {kode: 0 for kode in produk_df["kode_voucher"]}
else:
    for kode in produk_df["kode_voucher"]:
        st.session_state.qty.setdefault(kode, 0)

if st.session_state.get("_do_reset_qty"):
    for kode in produk_df["kode_voucher"]:
        st.session_state.qty[kode] = 0
    st.session_state["_do_reset_qty"] = False
    st.session_state.sn_input = {}

st.divider()

# ============================================================
# FILTER PRODUK
# ============================================================

st.subheader("Pilih Provider")

daftar_provider = sorted(
    produk_df["provider"].dropna().unique().tolist()
)

provider_terpilih = st.selectbox(
    "Filter Provider",
    daftar_provider,
    label_visibility="collapsed",
)

keyword = st.text_input(
    "Cari produk",
    placeholder="Contoh: 5GB",
)

produk_tampil = produk_df.copy()

if provider_terpilih:
    produk_tampil = produk_tampil[
        produk_tampil["provider"] == provider_terpilih
    ]

if keyword:
    kw = keyword.lower()

    produk_tampil = produk_tampil[
        produk_tampil["produk"]
        .astype(str)
        .str.lower()
        .str.contains(kw, na=False)
        |
        produk_tampil["kode_voucher"]
        .astype(str)
        .str.lower()
        .str.contains(kw, na=False)
    ]

# ============================================================
# PAGINATION PRODUK (15 produk / halaman -> 5 baris x 3 kolom)
# ============================================================

ITEMS_PER_PAGE = 15

total_produk_filter = len(produk_tampil)
total_halaman = max(1, -(-total_produk_filter // ITEMS_PER_PAGE))  # ceil division

# Reset ke halaman 1 setiap kali filter provider / keyword berubah
filter_key = f"{provider_terpilih}|{keyword}"
if st.session_state.get("_last_filter_key") != filter_key:
    st.session_state["_last_filter_key"] = filter_key
    st.session_state["halaman_produk"] = 1

if "halaman_produk" not in st.session_state:
    st.session_state["halaman_produk"] = 1

# Jaga-jaga kalau halaman_produk kebesaran (misal filter berubah jadi lebih sedikit)
halaman_sekarang = min(st.session_state["halaman_produk"], total_halaman)
st.session_state["halaman_produk"] = halaman_sekarang

start_idx = (halaman_sekarang - 1) * ITEMS_PER_PAGE
end_idx = start_idx + ITEMS_PER_PAGE
produk_tampil_halaman = produk_tampil.iloc[start_idx:end_idx]

awal_tampil = start_idx + 1 if total_produk_filter > 0 else 0
akhir_tampil = min(end_idx, total_produk_filter)

st.caption(
    f"Menampilkan {awal_tampil}-{akhir_tampil} dari {total_produk_filter} produk "
    f"(Halaman {halaman_sekarang} dari {total_halaman})"
)

# ============================================================
# HITUNG TOTAL
# ============================================================

total_harga = 0
detail_pesanan = []

for _, row in produk_df.iterrows():
    kode = row["kode_voucher"]
    qty = st.session_state.qty.get(kode, 0)

    if qty > 0:
        subtotal = qty * row["harga"]
        total_harga += subtotal

        detail_pesanan.append(
            {
                "provider": row["provider"],
                "kode_voucher": kode,
                "produk": row["produk"],
                "harga_satuan": row["harga"],
                "qty": qty,
                "subtotal": subtotal,
            }
        )

# ============================================================
# DAFTAR PRODUK
# ============================================================

produk_list = produk_tampil_halaman.to_dict("records")
JUMLAH_KOLOM = 3

for i in range(0, len(produk_list), JUMLAH_KOLOM):
    baris_produk = produk_list[i:i + JUMLAH_KOLOM]
    kolom = st.columns(JUMLAH_KOLOM)

    for kolom_idx, row in enumerate(baris_produk):
        kode = row["kode_voucher"]
        nama = row["produk"]
        harga = row["harga"]
        provider = row["provider"]
        qty_sekarang = st.session_state.qty.get(kode, 0)

        with kolom[kolom_idx]:
            with st.container(border=True):
                st.markdown(
                    f"""
                    <div class="wg-prod-name">{nama}</div>
                    <div class="wg-prod-provider">{provider}</div>
                    """,
                    unsafe_allow_html=True,
                )

                price_row = st.container(key=f"pricerow-{kode}")

                with price_row:
                    c_harga, c_qty_group = st.columns(
                        [1, 1.35],
                        gap="small",
                        vertical_alignment="center",
                    )

                    with c_harga:
                        if harga > 0:
                            st.markdown(f"**{format_rupiah(harga)}**")
                        else:
                            st.caption("⚠️ Harga belum tersedia")

                    with c_qty_group:
                        qty_box = st.container(key=f"qtybox-{kode}")

                        with qty_box:
                            c_minus, c_qty, c_plus = st.columns(
                                [1, 1.6, 1],
                                gap="small",
                                vertical_alignment="center",
                            )

                            with c_minus:
                                st.container(key=f"qty_minus_{kode}")
                                st.button(
                                    "−",
                                    key=f"qty_minus_{kode}_btn",
                                    on_click=kurang,
                                    args=(kode,),
                                    disabled=(harga == 0),
                                    use_container_width=True,
                                )

                            with c_qty:
                                # Widget input TIDAK memakai key Session State.
                                # Nilainya selalu berasal dari qty sebagai satu-satunya
                                # sumber data. Ini sengaja untuk menghindari seluruh
                                # konflik "default value + Session State API".
                                teks_qty = st.text_input(
                                    f"Jumlah {kode}",
                                    value=str(qty_sekarang),
                                    disabled=(harga == 0),
                                    label_visibility="collapsed",
                                    placeholder="0",
                                )

                                # Saat user mengetik, langsung sinkronkan ke qty.
                                nilai_ketik = _parse_qty(teks_qty)
                                if nilai_ketik != st.session_state.qty.get(kode, 0):
                                    st.session_state.qty[kode] = nilai_ketik

                            with c_plus:
                                st.container(key=f"qty_plus_{kode}")
                                st.button(
                                    "+",
                                    key=f"qty_plus_{kode}_btn",
                                    on_click=tambah,
                                    args=(kode,),
                                    disabled=(harga == 0),
                                    use_container_width=True,
                                )

# ============================================================
# KONTROL PAGINATION (Sebelumnya / Nomor Halaman / Selanjutnya)
# ============================================================

def _daftar_nomor_halaman(halaman_aktif, total):
    """
    Bangun daftar nomor halaman yang ditampilkan, dengan '...'
    (direpresentasikan None) untuk halaman yang di-skip.
    Contoh (halaman 6 dari 13): 1 ... 5 6 7 ... 13
    """
    if total <= 7:
        return list(range(1, total + 1))

    nomor = {1, total, halaman_aktif}

    if halaman_aktif - 1 >= 1:
        nomor.add(halaman_aktif - 1)
    if halaman_aktif + 1 <= total:
        nomor.add(halaman_aktif + 1)

    nomor_urut = sorted(nomor)

    hasil = []
    sebelumnya = None

    for n in nomor_urut:
        if sebelumnya is not None and n - sebelumnya > 1:
            hasil.append(None)
        hasil.append(n)
        sebelumnya = n

    return hasil


if total_halaman > 1:
    pagination_box = st.container(key="wg-pagination")

    with pagination_box:
        daftar_nomor = _daftar_nomor_halaman(halaman_sekarang, total_halaman)

        # Rasio kolom: panah lebih lebar dikit, nomor sama rata,
        # elipsis lebih sempit.
        rasio_kolom = [1.2]
        for n in daftar_nomor:
            rasio_kolom.append(1 if n is not None else 0.5)
        rasio_kolom.append(1.2)

        kolom_pagination = st.columns(
            rasio_kolom,
            gap="small",
            vertical_alignment="center",
        )

        col_prev = kolom_pagination[0]
        col_next = kolom_pagination[-1]
        kolom_nomor = kolom_pagination[1:-1]

        with col_prev:
            if st.button(
                "◀",
                use_container_width=True,
                disabled=(halaman_sekarang <= 1),
                key="btn_halaman_prev",
            ):
                st.session_state["halaman_produk"] = halaman_sekarang - 1
                st.rerun()

        for kolom, nomor in zip(kolom_nomor, daftar_nomor):
            with kolom:
                if nomor is None:
                    st.markdown(
                        "<div class='wg-pagination-ellipsis'>···</div>",
                        unsafe_allow_html=True,
                    )
                else:
                    if st.button(
                        str(nomor),
                        use_container_width=True,
                        key=f"btn_halaman_{nomor}",
                        type=(
                            "primary"
                            if nomor == halaman_sekarang
                            else "secondary"
                        ),
                    ):
                        st.session_state["halaman_produk"] = nomor
                        st.rerun()

        with col_next:
            if st.button(
                "▶",
                use_container_width=True,
                disabled=(halaman_sekarang >= total_halaman),
                key="btn_halaman_next",
            ):
                st.session_state["halaman_produk"] = halaman_sekarang + 1
                st.rerun()

st.divider()

# ============================================================
# RINGKASAN + INPUT SERIAL NUMBER (SN)
# ============================================================

sn_semua_valid = False

if detail_pesanan:
    with st.expander(
        f"🧾 Ringkasan pesanan "
        f"({len(detail_pesanan)} item dipilih)",
        expanded=True,
    ):
        df_ringkasan = pd.DataFrame(detail_pesanan).drop(
            columns=["provider", "kode_voucher"]
        )
        # Ubah kolom angka jadi teks berformat supaya st.dataframe
        # merender rata kiri (kolom numerik otomatis rata kanan).
        df_ringkasan["harga_satuan"] = df_ringkasan["harga_satuan"].apply(
            format_rupiah
        )
        df_ringkasan["qty"] = df_ringkasan["qty"].astype(str)
        df_ringkasan["subtotal"] = df_ringkasan["subtotal"].apply(
            format_rupiah
        )

        st.dataframe(
            df_ringkasan,
            use_container_width=True,
            hide_index=True,
        )

        st.markdown("---")
        st.markdown("**Input Serial Number (SN)**")
        st.caption(
            "Cek SN pada struk/hasil transaksi H2H setelah voucher "
            "berhasil diproses, lalu masukkan SN pertama dan SN "
            "terakhir untuk tiap produk di bawah ini."
        )

        semua_item_valid = []

        for item in detail_pesanan:
            kode = item["kode_voucher"]
            qty = item["qty"]

            if kode not in st.session_state.sn_input:
                st.session_state.sn_input[kode] = {
                    "awal": "",
                    "akhir": "",
                }

            st.markdown(
                f"*{item['produk']}* — qty {qty}"
            )

            c_sn1, c_sn2 = st.columns(2)

            with c_sn1:
                sn_awal = st.text_input(
                    "SN Awal",
                    value=st.session_state.sn_input[kode]["awal"],
                    key=f"sn_awal_{kode}",
                    placeholder="Contoh: 1234567890123450",
                )

            with c_sn2:
                sn_akhir = st.text_input(
                    "SN Akhir",
                    value=st.session_state.sn_input[kode]["akhir"],
                    key=f"sn_akhir_{kode}",
                    placeholder="Contoh: 1234567890123457",
                )

            st.session_state.sn_input[kode] = {
                "awal": sn_awal,
                "akhir": sn_akhir,
            }

            list_sn, sn_error = generate_sn_list(sn_awal, sn_akhir)

            item_valid = False
            item["sn_list"] = []

            if sn_error:
                st.error(sn_error)

            elif not sn_awal or not sn_akhir:
                st.caption("⏳ Belum diisi.")

            else:
                jumlah_generate = len(list_sn)
                item_valid = jumlah_generate == qty

                if item_valid:
                    label_preview = (
                        f"✅ {jumlah_generate} dari {qty} SN sesuai qty"
                    )
                else:
                    label_preview = (
                        f"❌ {jumlah_generate} dari {qty} SN — "
                        f"{'kurang' if jumlah_generate < qty else 'lebih'} "
                        f"{abs(jumlah_generate - qty)}"
                    )

                with st.expander(label_preview, expanded=False):
                    for idx, sn in enumerate(list_sn, start=1):
                        st.text(f"{idx}. {sn}")

                if item_valid:
                    item["sn_list"] = list_sn

            semua_item_valid.append(item_valid)

            st.markdown("")

        sn_semua_valid = all(semua_item_valid) if semua_item_valid else False

        if not sn_semua_valid:
            st.warning(
                "Lengkapi SN Awal & SN Akhir untuk semua produk "
                "(jumlah SN harus sama dengan qty) sebelum mengirim pesanan."
            )

    col_total1, col_total2 = st.columns([2, 1])

    with col_total2:
        st.metric(
            "Total Pesanan",
            format_rupiah(total_harga),
        )

# ============================================================
# SIMPAN PESANAN
# ============================================================

if st.button(
    "🧾 Kirim Pesanan",
    type="primary",
    use_container_width=True,
    disabled=not sheet_ok or not sn_semua_valid,
):
    if not nama_outlet or not no_wa:
        st.error(
            "Nama outlet dan No. WhatsApp wajib diisi."
        )

    elif total_harga == 0:
        st.error(
            "Pilih minimal 1 produk dengan quantity lebih dari 0."
        )

    elif not sn_semua_valid:
        st.error(
            "Lengkapi Serial Number (SN) untuk semua produk terlebih dahulu."
        )

    else:
        # timestamp: format baku untuk disimpan ke Google Sheets.
        timestamp = now_wib().strftime("%Y-%m-%d %H:%M:%S")

        order_id = buat_order_id()

        # Opsi B: 1 baris per SN. Tiap item di-"pecah" jadi sebanyak
        # SN yang sudah digenerate (list_sn), supaya tiap voucher
        # individual bisa dilacak lewat kolom "sn" masing-masing.
        rows_to_append = [
            [
                timestamp,
                order_id,
                nama_outlet,
                no_wa,
                alamat_pengiriman,
                item["provider"],
                item["kode_voucher"],
                item["produk"],
                item["harga_satuan"],
                item["qty"],
                item["subtotal"],
                total_harga,
                sn,
            ]
            for item in detail_pesanan
            for sn in item["sn_list"]
        ]

        try:
            hasil_append = worksheet.append_rows(
                rows_to_append,
                value_input_option="USER_ENTERED",
            )

            # Google Sheets bisa memformat ulang tampilan tanggal/jam
            # saat parsing USER_ENTERED (mis. jam tunggal tanpa nol di
            # depan seperti "8:21:53"). Supaya template chat WA selalu
            # sama persis dengan yang ada di kolom timestamp sheet,
            # ambil langsung nilai selnya setelah tersimpan.
            timestamp_wa = timestamp
            try:
                updated_range = hasil_append["updates"]["updatedRange"]
                baris_pertama = int(
                    "".join(
                        ch
                        for ch in updated_range.split("!")[1].split(":")[0]
                        if ch.isdigit()
                    )
                )
                nilai_sel = worksheet.acell(f"A{baris_pertama}").value
                if nilai_sel:
                    timestamp_wa = nilai_sel
            except Exception:
                pass

            st.session_state.last_receipt = build_receipt_image(
                order_id,
                nama_outlet,
                no_wa,
                alamat_pengiriman,
                timestamp,
                detail_pesanan,
                total_harga,
            )

            nama_file_aman = (
                nama_outlet.strip().replace(" ", "_")
            )

            st.session_state.last_receipt_name = (
                f"struk_{order_id}_{nama_file_aman}.png"
            )

            nomor_wa_tujuan = format_no_wa(no_wa)

            teks_nota = build_nota_wa_text(
                order_id,
                nama_outlet,
                no_wa,
                alamat_pengiriman,
                timestamp_wa,
                detail_pesanan,
                total_harga,
            )

            st.session_state.last_wa_link = (
                f"https://wa.me/{nomor_wa_tujuan}"
                f"?text={quote(teks_nota)}"
            )

            # ----------------------------------------------------------
            # Link WA konfirmasi ke CS/Admin (nomor tetap dari secrets)
            # ----------------------------------------------------------
            cs_wa_number = os.environ.get("cs_wa_number")

            if cs_wa_number:
                teks_konfirmasi_cs = build_konfirmasi_cs_text(
                    order_id,
                    nama_outlet,
                    no_wa,
                    alamat_pengiriman,
                    timestamp_wa,
                    detail_pesanan,
                    total_harga,
                )

                nomor_cs_tujuan = format_no_wa(cs_wa_number)

                st.session_state.last_cs_wa_link = (
                    f"https://wa.me/{nomor_cs_tujuan}"
                    f"?text={quote(teks_konfirmasi_cs)}"
                )
            else:
                st.session_state.last_cs_wa_link = None

            st.session_state.last_order_id = order_id
            st.session_state.show_success = True

            st.session_state["_do_reset_qty"] = True
            st.rerun()

        except Exception as e:
            st.error(
                "Gagal menyimpan ke Google Sheets."
            )
            st.exception(e)

# ============================================================
# STATUS SUKSES
# ============================================================

if (
    st.session_state.show_success
    and st.session_state.last_receipt
):
    st.success(
        "Pesanan tersimpan! "
        f"Order ID: **{st.session_state.last_order_id}**"
    )

    if st.session_state.last_cs_wa_link:
        st.link_button(
            "💬 Konfirmasi ke Admin via WhatsApp",
            st.session_state.last_cs_wa_link,
            use_container_width=True,
        )
    else:
        st.caption(
            "⚠️ Nomor WA CS belum dikonfigurasi "
            "(`cs_wa_number` di Railway Variables)."
        )

    st.image(
        st.session_state.last_receipt,
        caption="Preview Struk Pesanan",
        width=340,
    )

    dl_col, close_col = st.columns([3, 1])

    with dl_col:
        st.download_button(
            "⬇️ Download Struk (Gambar)",
            data=st.session_state.last_receipt,
            file_name=st.session_state.last_receipt_name,
            mime="image/png",
            use_container_width=True,
        )

    with close_col:
        if st.button(
            "Tutup",
            use_container_width=True,
        ):
            st.session_state.show_success = False
            st.rerun()

# ============================================================

# PANEL ADMIN — SIDEBAR
# ============================================================

if "admin_fullscreen" not in st.session_state:
    st.session_state.admin_fullscreen = False

st.html(
    f"""
<script>
document.body.classList.toggle(
    "wg-admin-fullscreen",
    {str(st.session_state.admin_fullscreen).lower()}
);
</script>
""",
    unsafe_allow_javascript=True,
)

with st.sidebar:
    st.markdown("### Panel Admin")

    if "admin_authed" not in st.session_state:
        st.session_state.admin_authed = False

    admin_password = os.environ.get("admin_password") or os.environ.get("ADMIN_PASSWORD")
    admin_password_tersedia = bool(admin_password)

    if not admin_password_tersedia:
        st.warning(
            "Panel admin belum aktif. Tambahkan `admin_password` "
            "di secrets.toml untuk mengaktifkan fitur ini."
        )

    elif not st.session_state.admin_authed:
        pw_input = st.text_input(
            "Password Admin",
            type="password",
            key="admin_pw_input",
        )

        if st.button("Masuk", key="admin_login_btn"):
            if pw_input == admin_password:
                st.session_state.admin_authed = True
                st.rerun()
            else:
                st.error("Password salah.")

    else:
        col_status, col_logout = st.columns([3, 1])

        with col_status:
            st.success("Masuk sebagai Admin.")

        with col_logout:
            if st.button(
                "Keluar",
                key="admin_logout_btn",
            ):
                st.session_state.admin_authed = False
                st.rerun()

        st.caption(
            "Kirim nota dari HP/laptop yang nomor WhatsApp-nya "
            "adalah nomor admin, agar nota terkirim dari nomor "
            "admin — bukan dari HP outlet."
        )

        st.toggle(
            "Mode layar penuh",
            key="admin_fullscreen",
            help="Perluas panel admin menjadi tampilan penuh.",
        )

        if st.session_state.admin_fullscreen:
            st.caption("Panel admin sedang ditampilkan penuh.")

        search_kw = st.text_input(
            "Cari order ID / nama outlet",
            key="admin_search",
            placeholder="Contoh: ORD-260819 atau ABC Cell",
        )

        try:
            semua_data = worksheet.get_all_records()
        except Exception as e:
            semua_data = []
            st.error(
                "Gagal mengambil data pesanan dari Google Sheets."
            )
            st.exception(e)

        if not semua_data:
            st.markdown(
                '<div class="wg-admin-empty">'
                "Belum ada pesanan masuk."
                "</div>",
                unsafe_allow_html=True,
            )

        else:
            df_semua = pd.DataFrame(semua_data)

            if "order_id" not in df_semua.columns:
                st.warning(
                    "Kolom `order_id` tidak ditemukan di sheet. "
                    "Pastikan header sheet sudah sesuai."
                )

            else:
                status_map = get_status_map(worksheet_status)

                order_ids_unik = (
                    df_semua[["order_id", "timestamp"]]
                    .drop_duplicates(subset="order_id")
                    .sort_values(
                        "timestamp",
                        ascending=False,
                    )["order_id"]
                    .tolist()
                )

                daftar_order = []

                for oid in order_ids_unik:
                    baris_order = df_semua[
                        df_semua["order_id"] == oid
                    ]

                    first_row = baris_order.iloc[0]

                    total_order = pd.to_numeric(
                        baris_order["subtotal"],
                        errors="coerce",
                    ).sum()

                    daftar_order.append(
                        {
                            "order_id": oid,
                            "nama_outlet": first_row.get(
                                "nama_outlet",
                                "",
                            ),
                            "no_wa": first_row.get(
                                "no_wa",
                                "",
                            ),
                            "alamat_pengiriman": first_row.get(
                                "alamat_pengiriman",
                                "",
                            ),
                            "timestamp": first_row.get(
                                "timestamp",
                                "",
                            ),
                            "baris_order": baris_order,
                            "total": total_order,
                            "terkirim": status_map.get(
                                str(oid),
                                False,
                            ),
                        }
                    )

                if search_kw:
                    kw = search_kw.strip().lower()

                    daftar_order = [
                        d
                        for d in daftar_order
                        if (
                            kw in str(
                                d["order_id"]
                            ).lower()
                            or
                            kw in str(
                                d["nama_outlet"]
                            ).lower()
                        )
                    ]

                belum_dikirim = [
                    d
                    for d in daftar_order
                    if not d["terkirim"]
                ]

                sudah_dikirim = [
                    d
                    for d in daftar_order
                    if d["terkirim"]
                ]

                JUMLAH_TAMPIL = 20

                def render_kartu_order(d, sudah):
                    items_order = [
                        {
                            "produk": r["produk"],
                            "kode_voucher": r["kode_voucher"],
                            "qty": r["qty"],
                            "harga_satuan": r["harga_satuan"],
                            "subtotal": r["subtotal"],
                        }
                        for _, r in d["baris_order"].iterrows()
                    ]

                    teks_nota_admin = build_nota_wa_text(
                        d["order_id"],
                        d["nama_outlet"],
                        d["no_wa"],
                        d["alamat_pengiriman"],
                        d["timestamp"],
                        items_order,
                        d["total"],
                    )

                    nomor_tujuan = format_no_wa(
                        str(d["no_wa"])
                    )

                    link_wa_admin = (
                        "https://api.whatsapp.com/send"
                        f"?phone={nomor_tujuan}"
                        f"&text={quote(teks_nota_admin)}"
                    )

                    with st.container(border=True):
                        st.markdown(
                            f"**{d['order_id']}** — "
                            f"{d['nama_outlet']}"
                        )

                        st.markdown(
                            '<div class="wg-admin-card-total">'
                            f"{d['timestamp']} · "
                            f"{format_rupiah(d['total'])} · "
                            f"{len(d['baris_order'])} item"
                            "</div>",
                            unsafe_allow_html=True,
                        )

                        # ====================================================
                        # ACTION BUTTONS
                        # Kedua tombol dibungkus bersama agar tinggi sama.
                        # ====================================================
                        st.markdown(
                            '<div class="wg-admin-actions">',
                            unsafe_allow_html=True,
                        )

                        c1, c2 = st.columns(
                            2,
                            gap="small",
                        )

                        with c1:
                            st.link_button(
                                "Kirim WhatsApp",
                                link_wa_admin,
                                use_container_width=True,
                            )

                        with c2:
                            if not sudah:
                                if st.button(
                                    "Tandai terkirim",
                                    key=(
                                        f"tandai_"
                                        f"{d['order_id']}"
                                    ),
                                    use_container_width=True,
                                ):
                                    tandai_terkirim(
                                        worksheet_status,
                                        d["order_id"],
                                    )
                                    st.rerun()

                            else:
                                if st.button(
                                    "Batalkan tandai",
                                    key=(
                                        f"batal_"
                                        f"{d['order_id']}"
                                    ),
                                    use_container_width=True,
                                ):
                                    batalkan_tandai(
                                        worksheet_status,
                                        d["order_id"],
                                    )
                                    st.rerun()

                        st.markdown(
                            "</div>",
                            unsafe_allow_html=True,
                        )

                with st.expander(
                    f"Belum dikirim ({len(belum_dikirim)})",
                    expanded=True,
                ):
                    if not belum_dikirim:
                        st.markdown(
                            '<div class="wg-admin-empty">'
                            "Tidak ada pesanan yang belum dikirim."
                            "</div>",
                            unsafe_allow_html=True,
                        )
                    else:
                        for d in belum_dikirim[:JUMLAH_TAMPIL]:
                            render_kartu_order(
                                d,
                                sudah=False,
                            )

                st.divider()

                with st.expander(
                    f"Sudah dikirim ({len(sudah_dikirim)})",
                    expanded=False,
                ):
                    if not sudah_dikirim:
                        st.markdown(
                            '<div class="wg-admin-empty">'
                            "Belum ada yang ditandai terkirim."
                            "</div>",
                            unsafe_allow_html=True,
                        )
                    else:
                        for d in sudah_dikirim[:JUMLAH_TAMPIL]:
                            render_kartu_order(
                                d,
                                sudah=True,
                            )

                st.divider()
                st.markdown("#### Rekapitulasi")

                total_pesanan_semua = len(daftar_order)
                total_nilai_semua = sum(
                    d["total"] for d in daftar_order
                )

                rc1, rc2 = st.columns(2)
                rc1.metric("Total Pesanan", total_pesanan_semua)
                rc2.metric("Sudah Terkirim", len(sudah_dikirim))

                rc3, rc4 = st.columns(2)
                rc3.metric("Belum Terkirim", len(belum_dikirim))
                rc4.metric(
                    "Total Nilai",
                    format_rupiah(total_nilai_semua),
                )
