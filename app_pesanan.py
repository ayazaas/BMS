import streamlit as st
import pandas as pd
from datetime import datetime
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
NAMA_WORKSHEET_PRODUK = "Produk"
NAMA_WORKSHEET_STATUS = "StatusKirim"

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
   PRODUCT CARD
   ======================================================== */
div[data-testid="stVerticalBlockBorderWrapper"] {
    border-radius: 14px !important;
    padding: 0.75rem !important;
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
    line-height: 1.25 !important;
}

/* ========================================================
   QTY BOX: - | ANGKA | +
   Target langsung via key (bukan posisi/nth-child) supaya
   tidak rapuh terhadap elemen tambahan di DOM.
   ======================================================== */
div[class*="st-key-qtybox-"] {
    margin-top: 0.4rem !important;
}

div[class*="st-key-qtybox-"] div[data-testid="stHorizontalBlock"] {
    display: flex !important;
    align-items: stretch !important;
    gap: 0 !important;
    border: 1px solid rgba(49, 51, 63, 0.20) !important;
    border-radius: 10px !important;
    overflow: hidden !important;
    background: rgba(250, 250, 250, 0.8) !important;
}

div[class*="st-key-qtybox-"] div[data-testid="stHorizontalBlock"] > div {
    min-width: 0 !important;
}

/* Tombol MINUS & PLUS ditembak langsung lewat key-nya sendiri */
div[class*="st-key-qty_minus_"],
div[class*="st-key-qty_plus_"] {
    width: 100% !important;
}

div[class*="st-key-qty_minus_"] button,
div[class*="st-key-qty_plus_"] button {
    width: 100% !important;
    height: 40px !important;
    min-height: 40px !important;
    max-height: 40px !important;
    padding: 0 !important;
    margin: 0 !important;
    border: none !important;
    border-radius: 0 !important;
    background: transparent !important;
    color: #30323d !important;
    opacity: 1 !important;
    visibility: visible !important;
    font-size: 21px !important;
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
    font-size: 21px !important;
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

/* Input angka di tengah — tetap bisa diketik manual */
div[class*="st-key-qtybox-"] div[data-testid="stTextInput"] {
    width: 100% !important;
    background: transparent !important;
}

div[class*="st-key-qtybox-"] div[data-testid="stTextInput"] > div {
    border: none !important;
    box-shadow: none !important;
    background: transparent !important;
}

div[class*="st-key-qtybox-"] div[data-testid="stTextInput"] input {
    width: 100% !important;
    border: none !important;
    background: transparent !important;
    box-shadow: none !important;
    text-align: center !important;
    height: 40px !important;
    min-height: 40px !important;
    padding: 0 4px !important;
    font-weight: 700 !important;
    font-size: 16px !important;
    color: #30323d !important;
}

div[class*="st-key-qtybox-"] [data-testid="InputInstructions"] {
    display: none !important;
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

/* ========================================================
   FLOATING SCROLL CONTROLLER
   ======================================================== */
.wg-scroll-rail {
    position: fixed;
    right: max(6px, env(safe-area-inset-right));
    top: 50%;
    transform: translateY(-50%);
    z-index: 999999;
    width: clamp(34px, 8vw, 42px);
    height: min(58vh, 430px);
    max-height: calc(100dvh - 120px);
    min-height: 190px;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 7px;
    pointer-events: auto;
    user-select: none;
    -webkit-user-select: none;
}

.wg-scroll-btn {
    width: clamp(32px, 8vw, 38px);
    height: clamp(32px, 8vw, 38px);
    flex: 0 0 auto;
    border: 1px solid rgba(0,0,0,0.12);
    border-radius: 50%;
    background: rgba(255,255,255,0.96);
    color: #555;
    box-shadow: 0 2px 8px rgba(0,0,0,0.14);
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 0;
    margin: 0;
    font-size: 18px;
    font-weight: 700;
    line-height: 1;
    cursor: pointer;
    touch-action: manipulation;
    -webkit-tap-highlight-color: transparent;
}

.wg-scroll-btn:active {
    transform: scale(0.92);
    background: #f2f2f2;
}

.wg-scroll-track {
    position: relative;
    flex: 1 1 auto;
    width: 7px;
    min-height: 110px;
    border-radius: 999px;
    background: rgba(0,0,0,0.09);
    box-shadow: inset 0 0 0 1px rgba(0,0,0,0.03);
    cursor: pointer;
    touch-action: none;
}

.wg-scroll-track::before {
    content: "";
    position: absolute;
    left: -13px;
    right: -13px;
    top: 0;
    bottom: 0;
}

.wg-scroll-thumb {
    position: absolute;
    left: 0;
    top: 0;
    width: 7px;
    min-height: 30px;
    border-radius: 999px;
    background: rgba(80,80,80,0.55);
    pointer-events: none;
    will-change: transform, height;
}

@media (max-width: 600px) {
    .wg-scroll-rail {
        right: max(4px, env(safe-area-inset-right));
        height: min(48vh, 340px);
        min-height: 170px;
    }

    div[class*="st-key-qtybox-"] div[data-testid="stTextInput"] input,
    div[class*="st-key-qty_minus_"] button,
    div[class*="st-key-qty_plus_"] button {
        height: 42px !important;
        min-height: 42px !important;
        max-height: 42px !important;
    }

    div[data-testid="stVerticalBlockBorderWrapper"] {
        padding: 0.65rem !important;
    }
}

@media (max-width: 380px) {
    .wg-scroll-rail {
        width: 32px;
        height: min(44vh, 300px);
    }

    .wg-scroll-track,
    .wg-scroll-thumb {
        width: 6px;
    }
}

@media (max-width: 600px) {
    .block-container {
        padding-right: max(2.9rem, calc(1rem + env(safe-area-inset-right))) !important;
    }

    .wg-admin-actions .stButton > button,
    .wg-admin-actions [data-testid="stLinkButton"] {
        height: 42px !important;
        min-height: 42px !important;
        max-height: 42px !important;
        font-size: 0.88rem !important;
    }
}
</style>

<div class="wg-scroll-rail" id="wgScrollRail" aria-label="Kontrol scroll">
    <button class="wg-scroll-btn" id="wgScrollUp"
            type="button" aria-label="Scroll ke atas" title="Scroll ke atas">↑</button>

    <div class="wg-scroll-track" id="wgScrollTrack"
         aria-label="Posisi halaman" title="Klik atau geser posisi scroll">
        <div class="wg-scroll-thumb" id="wgScrollThumb"></div>
    </div>

    <button class="wg-scroll-btn" id="wgScrollDown"
            type="button" aria-label="Scroll ke bawah" title="Scroll ke bawah">↓</button>
</div>

<script>
(() => {
    const root = document.getElementById("wgScrollRail");
    const up = document.getElementById("wgScrollUp");
    const down = document.getElementById("wgScrollDown");
    const track = document.getElementById("wgScrollTrack");
    const thumb = document.getElementById("wgScrollThumb");

    if (!root || !up || !down || !track || !thumb) return;

    const doc = document;

    function isScrollable(el) {
        if (!el) return false;
        return el.scrollHeight > el.clientHeight + 8;
    }

    function getScrollTarget() {
        const candidates = [
            doc.querySelector('[data-testid="stAppViewContainer"]'),
            doc.querySelector('[data-testid="stMain"]'),
            doc.querySelector('section.main'),
            doc.scrollingElement,
            doc.documentElement,
            doc.body
        ];

        for (const el of candidates) {
            if (isScrollable(el)) return el;
        }

        return null;
    }

    function getState() {
        const target = getScrollTarget();

        if (!target) {
            return {
                target: null,
                top: window.scrollY || 0,
                max: Math.max(
                    0,
                    doc.documentElement.scrollHeight - window.innerHeight
                ),
                viewport: window.innerHeight,
                total: doc.documentElement.scrollHeight
            };
        }

        const max = Math.max(0, target.scrollHeight - target.clientHeight);

        return {
            target,
            top: target.scrollTop || 0,
            max,
            viewport: target.clientHeight,
            total: target.scrollHeight
        };
    }

    function scrollToPosition(top, smooth = true) {
        const state = getState();
        const safeTop = Math.max(0, Math.min(top, state.max));

        if (state.target) {
            try {
                state.target.scrollTo({
                    top: safeTop,
                    left: 0,
                    behavior: smooth ? "smooth" : "auto"
                });
                return;
            } catch (e) {
                state.target.scrollTop = safeTop;
                return;
            }
        }

        window.scrollTo({
            top: safeTop,
            left: 0,
            behavior: smooth ? "smooth" : "auto"
        });
    }

    function scrollByAmount(direction) {
        const state = getState();
        const amount = Math.max(
            180,
            Math.min(520, Math.round(state.viewport * 0.72))
        );
        scrollToPosition(state.top + direction * amount, true);
    }

    function updateThumb() {
        const state = getState();
        const trackHeight = track.clientHeight;

        if (!trackHeight) return;

        if (state.max <= 0) {
            thumb.style.height = trackHeight + "px";
            thumb.style.transform = "translateY(0)";
            return;
        }

        const visibleRatio = state.total > 0
            ? Math.min(1, state.viewport / state.total)
            : 1;

        const thumbHeight = Math.max(
            30,
            Math.min(trackHeight, trackHeight * visibleRatio)
        );

        const maxThumbTop = Math.max(0, trackHeight - thumbHeight);
        const ratio = state.max > 0 ? state.top / state.max : 0;

        thumb.style.height = thumbHeight + "px";
        thumb.style.transform =
            "translateY(" + (ratio * maxThumbTop) + "px)";
    }

    up.addEventListener("click", (event) => {
        event.preventDefault();
        event.stopPropagation();
        scrollByAmount(-1);
    });

    down.addEventListener("click", (event) => {
        event.preventDefault();
        event.stopPropagation();
        scrollByAmount(1);
    });

    track.addEventListener("click", (event) => {
        if (event.target === thumb) return;

        event.preventDefault();
        event.stopPropagation();

        const state = getState();
        if (state.max <= 0) return;

        const rect = track.getBoundingClientRect();
        const ratio = Math.max(
            0,
            Math.min(1, (event.clientY - rect.top) / rect.height)
        );

        scrollToPosition(ratio * state.max, true);
    });

    let dragging = false;

    function dragTo(clientY) {
        const state = getState();
        const rect = track.getBoundingClientRect();

        const visibleRatio = state.total > 0
            ? Math.min(1, state.viewport / state.total)
            : 1;

        const thumbHeight = Math.max(
            30,
            Math.min(track.clientHeight, track.clientHeight * visibleRatio)
        );

        const maxThumbTop = Math.max(
            0,
            track.clientHeight - thumbHeight
        );

        if (maxThumbTop <= 0 || state.max <= 0) return;

        const y = Math.max(
            0,
            Math.min(maxThumbTop, clientY - rect.top - thumbHeight / 2)
        );

        scrollToPosition((y / maxThumbTop) * state.max, false);
    }

    thumb.addEventListener("pointerdown", (event) => {
        dragging = true;
        thumb.setPointerCapture?.(event.pointerId);
        event.preventDefault();
        event.stopPropagation();
    });

    track.addEventListener("pointermove", (event) => {
        if (!dragging) return;
        dragTo(event.clientY);
        event.preventDefault();
    });

    track.addEventListener("pointerup", (event) => {
        dragging = false;
        event.preventDefault();
    });

    track.addEventListener("pointercancel", () => {
        dragging = false;
    });

    let currentTarget = null;

    function bindScrollListener() {
        const target = getScrollTarget();

        if (target !== currentTarget) {
            if (currentTarget) {
                currentTarget.removeEventListener("scroll", updateThumb);
            }

            currentTarget = target;

            if (currentTarget) {
                currentTarget.addEventListener(
                    "scroll",
                    updateThumb,
                    { passive: true }
                );
            }
        }

        updateThumb();
    }

    bindScrollListener();

    const observer = new MutationObserver(() => {
        bindScrollListener();
    });

    observer.observe(doc.body, {
        childList: true,
        subtree: true
    });

    window.addEventListener("scroll", updateThumb, { passive: true });
    window.addEventListener("resize", updateThumb);

    setTimeout(bindScrollListener, 100);
    setTimeout(bindScrollListener, 500);
    setTimeout(bindScrollListener, 1200);
    setTimeout(bindScrollListener, 2500);
    setTimeout(bindScrollListener, 5000);
})();
</script>
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

    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=scopes,
    )

    client = gspread.authorize(creds)
    spreadsheet = client.open_by_url(st.secrets["spreadsheet_url"])

    ws_pesanan = spreadsheet.worksheet(NAMA_WORKSHEET_PESANAN)
    ws_produk = spreadsheet.worksheet(NAMA_WORKSHEET_PRODUK)

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

    return ws_pesanan, ws_produk, ws_status


try:
    worksheet, worksheet_produk, worksheet_status = connect_sheet()
    sheet_ok = True
except Exception as e:
    sheet_ok = False
    st.error(
        "Gagal konek ke Google Sheets. Cek konfigurasi secrets "
        "(gcp_service_account, spreadsheet_url) dan pastikan sheet "
        "sudah di-share ke email service account."
    )
    st.exception(e)
    st.stop()

# ============================================================
# LOAD PRODUK
# ============================================================

@st.cache_data(ttl=60)
def load_produk(_worksheet_produk):
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


produk_df = load_produk(worksheet_produk)

if produk_df.empty:
    st.warning("Belum ada data produk pada worksheet Produk.")
    st.stop()

# ============================================================
# SESSION STATE / QUANTITY STATE
# ============================================================
# Hanya satu sumber data: st.session_state.qty.
# Tidak ada state dengan key qtyinput_*, sehingga tidak mungkin terjadi
# konflik antara default value widget dan Session State API.
if "qty" not in st.session_state:
    st.session_state.qty = {kode: 0 for kode in produk_df["kode_voucher"]}
else:
    for kode in produk_df["kode_voucher"]:
        st.session_state.qty.setdefault(kode, 0)

if "last_receipt" not in st.session_state:
    st.session_state.last_receipt = None
if "last_receipt_name" not in st.session_state:
    st.session_state.last_receipt_name = None
if "show_success" not in st.session_state:
    st.session_state.show_success = False
if "last_wa_link" not in st.session_state:
    st.session_state.last_wa_link = None
if "last_order_id" not in st.session_state:
    st.session_state.last_order_id = None

if st.session_state.get("_do_reset_qty"):
    for kode in produk_df["kode_voucher"]:
        st.session_state.qty[kode] = 0
    st.session_state["_do_reset_qty"] = False


def _parse_qty(value):
    try:
        return max(0, int(str(value).strip() or "0"))
    except (TypeError, ValueError):
        return 0


def tambah(kode):
    st.session_state.qty[kode] = st.session_state.qty.get(kode, 0) + 1


def kurang(kode):
    st.session_state.qty[kode] = max(
        0, st.session_state.qty.get(kode, 0) - 1
    )


def format_rupiah(n):
    return f"Rp {n:,.0f}".replace(",", ".")


def buat_order_id():
    now = datetime.now()
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
    baris.append("Mohon diperiksa kembali detail pesanan tersebut.")
    baris.append(
        "Terima kasih atas kepercayaan Anda kepada Toko WG."
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
    padding = 24
    line_height = 26

    font_normal = _load_font(16)
    font_title = _load_font(20, bold=True)
    font_total = _load_font(18, bold=True)

    height = padding * 2 + sum(
        (
            34
            if tipe == "title"
            else 14
            if tipe == "sep"
            else 24
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
                    (padding, y + 6),
                    (width - padding, y + 6),
                ],
                fill=(180, 180, 180),
                width=1,
            )
            y += 14

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
            y += 34

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
            y += 24

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
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
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

st.title("🛒 Form Pemesanan Outlet Toko WG")
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

st.caption("Alamat pengiriman bersifat opsional.")
st.divider()

# ============================================================
# FILTER PRODUK
# ============================================================

st.subheader("Pilih Produk")

daftar_provider = [
    "Semua Provider"
] + sorted(
    produk_df["provider"].dropna().unique().tolist()
)

provider_terpilih = st.selectbox(
    "Filter Provider",
    daftar_provider,
)

keyword = st.text_input(
    "Cari produk / kode voucher",
    placeholder="Contoh: 5GB atau KIVFIH0",
)

produk_tampil = produk_df.copy()

if provider_terpilih != "Semua Provider":
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

st.caption(
    f"Menampilkan {len(produk_tampil)} dari {len(produk_df)} produk"
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

produk_list = produk_tampil.to_dict("records")
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
                st.markdown(f"**{nama}**")
                st.caption(f"{provider}")

                if harga > 0:
                    st.markdown(f"**{format_rupiah(harga)}**")
                else:
                    st.caption("⚠️ Harga belum tersedia")

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

st.divider()

# ============================================================
# RINGKASAN
# ============================================================

if detail_pesanan:
    with st.expander(
        f"🧾 Ringkasan pesanan "
        f"({len(detail_pesanan)} item dipilih)",
        expanded=True,
    ):
        st.dataframe(
            pd.DataFrame(detail_pesanan).drop(
                columns=["provider", "kode_voucher"]
            ),
            use_container_width=True,
            hide_index=True,
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
    "🧾 Konfirmasi & Kirim Pesanan",
    type="primary",
    use_container_width=True,
    disabled=not sheet_ok,
):
    if not nama_outlet or not no_wa:
        st.error(
            "Nama outlet dan No. WhatsApp wajib diisi."
        )

    elif total_harga == 0:
        st.error(
            "Pilih minimal 1 produk dengan quantity lebih dari 0."
        )

    else:
        timestamp = datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        order_id = buat_order_id()

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
            ]
            for item in detail_pesanan
        ]

        try:
            worksheet.append_rows(
                rows_to_append,
                value_input_option="USER_ENTERED",
            )

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
                timestamp,
                detail_pesanan,
                total_harga,
            )

            st.session_state.last_wa_link = (
                f"https://wa.me/{nomor_wa_tujuan}"
                f"?text={quote(teks_nota)}"
            )

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

    admin_password_tersedia = "admin_password" in st.secrets

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
            if pw_input == st.secrets["admin_password"]:
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
