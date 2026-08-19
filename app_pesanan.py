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

st.set_page_config(
    page_title="Form Pesanan Outlet",
    page_icon="🛒",
    layout="centered",
)

# ============================================================
# CSS + FLOATING SCROLL CONTROLLER + QTY BOX GABUNGAN
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

    div[data-testid="stVerticalBlockBorderWrapper"] .stButton > button {
        width: 100% !important;
        min-width: 0 !important;
        height: 40px !important;
        min-height: 40px !important;
        padding: 0 !important;
        border-radius: 10px !important;
        font-size: 18px !important;
        font-weight: 700 !important;
        line-height: 1 !important;
    }

    div[data-testid="stVerticalBlockBorderWrapper"] .stButton > button p,
    div[data-testid="stVerticalBlockBorderWrapper"] .stButton > button div {
        font-size: 18px !important;
        font-weight: 700 !important;
        line-height: 1 !important;
        margin: 0 !important;
    }

    .wg-qty-label {
        font-size: 0.72rem;
        color: rgba(49, 51, 63, 0.62);
        text-align: center;
        margin-top: 0.35rem;
        margin-bottom: 0.1rem;
    }

    /* ========================================================
       QTY BOX GABUNGAN ( - | angka | + ) JADI SATU PIL
       ======================================================== */
    div[class*="st-key-qtybox-"] div[data-testid="stHorizontalBlock"] {
        display: flex !important;
        align-items: stretch !important;
        gap: 0 !important;
        border: 1px solid rgba(49, 51, 63, 0.20);
        border-radius: 10px;
        overflow: hidden;
        background: rgba(250, 250, 250, 0.8);
    }

    div[class*="st-key-qtybox-"] div[data-testid="stHorizontalBlock"] > div {
        min-width: 0 !important;
    }

    /* tombol - dan + custom: hilangkan border/radius individual */
    div[class*="st-key-qtybox-"] .stButton > button {
        border: none !important;
        border-radius: 0 !important;
        background: transparent !important;
        height: 40px !important;
    }

    div[class*="st-key-qtybox-"] div[data-testid="stHorizontalBlock"] > div:first-child .stButton > button {
        border-right: 1px solid rgba(49, 51, 63, 0.15) !important;
    }

    div[class*="st-key-qtybox-"] div[data-testid="stHorizontalBlock"] > div:last-child .stButton > button {
        border-left: 1px solid rgba(49, 51, 63, 0.15) !important;
    }

    /* input angka di tengah: transparan, nyatu, center text */
    div[class*="st-key-qtybox-"] div[data-testid="stNumberInput"] {
        background: transparent !important;
    }

    div[class*="st-key-qtybox-"] div[data-testid="stNumberInput"] input {
        border: none !important;
        background: transparent !important;
        box-shadow: none !important;
        text-align: center !important;
        height: 40px !important;
        font-weight: 700 !important;
    }

    /* sembunyikan tombol +/- bawaan number_input (pakai tombol custom sendiri) */
    div[class*="st-key-qtybox-"] div[data-testid="stNumberInputStepUp"],
    div[class*="st-key-qtybox-"] div[data-testid="stNumberInputStepDown"] {
        display: none !important;
    }

    /* sembunyikan teks "Press Enter to apply" */
    div[class*="st-key-qtybox-"] [data-testid="InputInstructions"] {
        display: none !important;
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
        touch-action: none;
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

        div[class*="st-key-qtybox-"] div[data-testid="stNumberInput"] input,
        div[data-testid="stVerticalBlockBorderWrapper"] .stButton > button {
            height: 42px !important;
            min-height: 42px !important;
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

        .wg-scroll-track {
            width: 6px;
        }

        .wg-scroll-thumb {
            width: 6px;
        }
    }

    @media (max-width: 600px) {
        .block-container {
            padding-right: max(2.9rem, calc(1rem + env(safe-area-inset-right))) !important;
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
                root.style.display = "none";
                return;
            }

            root.style.display = "flex";

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
        }, { passive: false });

        down.addEventListener("click", (event) => {
            event.preventDefault();
            event.stopPropagation();
            scrollByAmount(1);
        }, { passive: false });

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
        }, { passive: false });

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
        }, { passive: false });

        track.addEventListener("pointermove", (event) => {
            if (!dragging) return;
            dragTo(event.clientY);
            event.preventDefault();
        }, { passive: false });

        track.addEventListener("pointerup", (event) => {
            dragging = false;
            event.preventDefault();
        }, { passive: false });

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
    return ws_pesanan, ws_produk


try:
    worksheet, worksheet_produk = connect_sheet()
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
# SESSION STATE
# ============================================================
if "qty" not in st.session_state:
    st.session_state.qty = {
        kode: 0 for kode in produk_df["kode_voucher"]
    }
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

# Reset qty dilakukan SEBELUM kartu produk dibuat.
if st.session_state.get("_do_reset_qty"):
    for kode in produk_df["kode_voucher"]:
        st.session_state.qty[kode] = 0
        st.session_state[f"qtyinput_{kode}"] = 0
    st.session_state["_do_reset_qty"] = False


def tambah(kode):
    baru = st.session_state.qty.get(kode, 0) + 1
    st.session_state.qty[kode] = baru
    st.session_state[f"qtyinput_{kode}"] = baru


def kurang(kode):
    baru = max(0, st.session_state.qty.get(kode, 0) - 1)
    st.session_state.qty[kode] = baru
    st.session_state[f"qtyinput_{kode}"] = baru


def set_qty_dari_input(kode):
    nilai = st.session_state.get(f"qtyinput_{kode}", 0)
    st.session_state.qty[kode] = max(0, int(nilai or 0))


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
        baris.append(f"   Kode     : {item['kode_voucher']}")
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
                f"[{item['provider']}] "
                f"{item['produk']} ({item['kode_voucher']})",
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
# HITUNG TOTAL DARI SEMUA PRODUK
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
                st.caption(f"{provider} · {kode}")

                if harga > 0:
                    st.markdown(f"**{format_rupiah(harga)}**")
                else:
                    st.caption("⚠️ Harga belum tersedia")

                # ====================================================
                # QUANTITY CONTROL: satu kotak pil [-][angka][+]
                # Angka pakai number_input (tetap bisa diketik manual),
                # tombol +/- bawaan number_input disembunyikan via CSS,
                # digantikan tombol custom di kiri-kanan.
                # ====================================================
                qty_box = st.container(key=f"qtybox-{kode}")
                with qty_box:
                    c_minus, c_qty, c_plus = st.columns(
                        [1, 1.6, 1],
                        gap="small",
                        vertical_alignment="center",
                    )

                    with c_minus:
                        st.button(
                            "−",
                            key=f"minus_{kode}",
                            on_click=kurang,
                            args=(kode,),
                            disabled=(harga == 0),
                            use_container_width=True,
                            help="Kurangi jumlah",
                        )

                    with c_qty:
                        st.number_input(
                            "Jumlah",
                            min_value=0,
                            step=1,
                            value=qty_sekarang,
                            key=f"qtyinput_{kode}",
                            on_change=set_qty_dari_input,
                            args=(kode,),
                            disabled=(harga == 0),
                            label_visibility="collapsed",
                        )

                    with c_plus:
                        st.button(
                            "+",
                            key=f"plus_{kode}",
                            on_click=tambah,
                            args=(kode,),
                            disabled=(harga == 0),
                            use_container_width=True,
                            help="Tambah jumlah",
                        )

                st.markdown(
                    '<div class="wg-qty-label">Jumlah</div>',
                    unsafe_allow_html=True,
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
            pd.DataFrame(detail_pesanan),
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

            st.session_state.last_receipt = (
                build_receipt_image(
                    order_id,
                    nama_outlet,
                    no_wa,
                    alamat_pengiriman,
                    timestamp,
                    detail_pesanan,
                    total_harga,
                )
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

            # Reset pada rerun berikutnya, sebelum widget produk dibuat.
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
        "✅ Pesanan tersimpan! "
        f"Order ID: **{st.session_state.last_order_id}**"
    )

    st.image(
        st.session_state.last_receipt,
        caption="Preview Struk Pesanan",
        width=340,
    )

    if st.session_state.last_wa_link:
        st.link_button(
            "📩 Kirim Nota via WhatsApp",
            st.session_state.last_wa_link,
            use_container_width=True,
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
