import streamlit as st
from streamlit import html as st_html
import pandas as pd
from datetime import datetime
from urllib.parse import quote
import io
import random
import gspread
from google.oauth2.service_account import Credentials
from PIL import Image, ImageDraw, ImageFont

# ============ KONFIGURASI ============
NAMA_WORKSHEET_PESANAN = "Pesanan"  # nama tab di Google Sheet untuk simpan pesanan
NAMA_WORKSHEET_PRODUK = "Produk"    # nama tab di Google Sheet untuk data produk

st.set_page_config(page_title="Form Pesanan Outlet", page_icon="🛒", layout="centered")

# ============ CSS KUSTOM + SCROLL CONTROLLER ============
# Scroll controller dibuat satu kali saja.
# st.html(..., unsafe_allow_javascript=True) dipakai agar JavaScript benar-benar
# dieksekusi oleh browser, bukan sekadar dirender sebagai HTML.

st_html(
    """
    <style>
    /* 1. Center angka quantity */
    div[data-testid="stNumberInput"] {
        width: 100% !important;
        display: flex !important;
        justify-content: center !important;
    }

    div[data-testid="stNumberInput"] > div {
        width: auto !important;
    }

    div[data-testid="stNumberInput"] div[data-baseweb="input"] {
        width: 64px !important;
        max-width: 64px !important;
        min-width: 64px !important;
        margin: 0 auto !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        overflow: hidden !important;
    }

    div[data-testid="stNumberInput"] input {
        text-align: center !important;
        width: 100% !important;
        flex: 1 1 auto !important;
        padding-left: 0 !important;
        padding-right: 0 !important;
    }

    div[data-testid="stNumberInputStepDown"],
    div[data-testid="stNumberInputStepUp"] {
        display: none !important;
        width: 0 !important;
        min-width: 0 !important;
        flex: 0 0 0px !important;
        padding: 0 !important;
        margin: 0 !important;
    }

    /* 2. Tombol +/- pada kartu produk */
    div[data-testid="stVerticalBlockBorderWrapper"] .stButton > button {
        height: 18px !important;
        min-height: 18px !important;
        width: 26px !important;
        min-width: 26px !important;
        max-width: 26px !important;
        padding: 0 !important;
        border-radius: 5px !important;
        line-height: 1 !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
    }

    div[data-testid="stVerticalBlockBorderWrapper"] .stButton > button p,
    div[data-testid="stVerticalBlockBorderWrapper"] .stButton > button div {
        font-size: 11px !important;
        font-weight: 700 !important;
        line-height: 1 !important;
        margin: 0 !important;
    }

    /* 3. Floating scroll controller */
    .scroll-rail-container {
        position: fixed;
        right: 8px;
        top: 50%;
        transform: translateY(-50%);
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 6px;
        height: 58vh;
        max-height: 460px;
        min-height: 220px;
        z-index: 2147483647;
        pointer-events: auto;
    }

    .scroll-rail-arrow {
        background: rgba(255,255,255,0.94);
        border: 1px solid rgba(0,0,0,0.12);
        border-radius: 50%;
        width: 30px;
        height: 30px;
        padding: 0;
        margin: 0;
        cursor: pointer;
        display: flex;
        align-items: center;
        justify-content: center;
        touch-action: manipulation;
        -webkit-tap-highlight-color: transparent;
        user-select: none;
        -webkit-user-select: none;
        box-shadow: 0 1px 5px rgba(0,0,0,0.12);
    }

    .scroll-rail-arrow:hover {
        background: #f5f5f5;
    }

    .scroll-rail-arrow:active {
        transform: scale(0.92);
    }

    .scroll-rail-arrow {
        color: #666;
        font-size: 18px;
        font-weight: 700;
        line-height: 1;
    }

    .scroll-rail-track {
        position: relative;
        flex: 1;
        width: 6px;
        background: rgba(0,0,0,0.08);
        border-radius: 4px;
        cursor: pointer;
        touch-action: none;
        user-select: none;
        -webkit-user-select: none;
    }

    .scroll-rail-track::before {
        content: "";
        position: absolute;
        top: 0;
        bottom: 0;
        left: -12px;
        right: -12px;
    }

    .scroll-rail-thumb {
        position: absolute;
        left: 0;
        top: 0;
        width: 6px;
        min-height: 28px;
        border-radius: 4px;
        background: #999;
        pointer-events: none;
    }

    @media (max-width: 600px) {
        .scroll-rail-container {
            right: 5px;
            height: 52vh;
            min-height: 190px;
            max-height: 380px;
        }

        .scroll-rail-arrow {
            width: 32px;
            height: 32px;
        }
    }
    </style>

    <div class="scroll-rail-container" id="wgScrollRail">
        <button class="scroll-rail-arrow" id="wgScrollUp"
                type="button" title="Scroll ke atas" aria-label="Scroll ke atas">↑</button>

        <div class="scroll-rail-track" id="wgScrollTrack"
             title="Klik untuk berpindah posisi">
            <div class="scroll-rail-thumb" id="wgScrollThumb"></div>
        </div>

        <button class="scroll-rail-arrow" id="wgScrollDown"
                type="button" title="Scroll ke bawah" aria-label="Scroll ke bawah">↓</button>
    </div>

    <script>
    (() => {
        const root = document.getElementById("wgScrollRail");
        const up = document.getElementById("wgScrollUp");
        const down = document.getElementById("wgScrollDown");
        const track = document.getElementById("wgScrollTrack");
        const thumb = document.getElementById("wgScrollThumb");

        if (!root || !up || !down || !track || !thumb) return;

        // Ambil document utama Streamlit.
        const doc = window.parent?.document || document;

        function getScrollTarget() {
            const candidates = [
                doc.querySelector('[data-testid="stAppViewContainer"]'),
                doc.querySelector('[data-testid="stMain"]'),
                doc.querySelector('section.main'),
                doc.querySelector('.main'),
                doc.scrollingElement,
                doc.documentElement,
                doc.body
            ];

            // Pilih elemen yang benar-benar memiliki area scroll.
            for (const el of candidates) {
                if (el && el.scrollHeight > el.clientHeight + 5) {
                    return el;
                }
            }

            return doc.scrollingElement || doc.documentElement || doc.body;
        }

        function updateThumb() {
            const target = getScrollTarget();
            const trackHeight = track.clientHeight;

            if (!target || trackHeight <= 0) return;

            const maxScroll = Math.max(
                0,
                target.scrollHeight - target.clientHeight
            );

            const visibleRatio = target.scrollHeight > 0
                ? target.clientHeight / target.scrollHeight
                : 1;

            const thumbHeight = Math.max(
                28,
                Math.min(trackHeight, trackHeight * visibleRatio)
            );

            const maxThumbTop = Math.max(
                0,
                trackHeight - thumbHeight
            );

            const ratio = maxScroll > 0
                ? target.scrollTop / maxScroll
                : 0;

            thumb.style.height = thumbHeight + "px";
            thumb.style.transform =
                "translateY(" + (ratio * maxThumbTop) + "px)";
        }

        function scrollByAmount(amount) {
            const target = getScrollTarget();
            if (!target) return;

            target.scrollBy({
                top: amount,
                left: 0,
                behavior: "smooth"
            });
        }

        up.addEventListener("click", (e) => {
            e.preventDefault();
            e.stopPropagation();
            scrollByAmount(-300);
        });

        down.addEventListener("click", (e) => {
            e.preventDefault();
            e.stopPropagation();
            scrollByAmount(300);
        });

        track.addEventListener("click", (e) => {
            e.preventDefault();
            e.stopPropagation();

            const target = getScrollTarget();
            if (!target) return;

            const rect = track.getBoundingClientRect();
            const y = e.clientY - rect.top;
            const ratio = Math.max(
                0,
                Math.min(1, y / rect.height)
            );

            const maxScroll = Math.max(
                0,
                target.scrollHeight - target.clientHeight
            );

            target.scrollTo({
                top: ratio * maxScroll,
                left: 0,
                behavior: "smooth"
            });
        });

        // Update posisi thumb ketika halaman di-scroll.
        let currentTarget = null;

        function bindScrollListener() {
            const target = getScrollTarget();

            if (!target || target === currentTarget) {
                updateThumb();
                return;
            }

            if (currentTarget) {
                currentTarget.removeEventListener(
                    "scroll",
                    updateThumb
                );
            }

            currentTarget = target;
            currentTarget.addEventListener(
                "scroll",
                updateThumb,
                { passive: true }
            );

            updateThumb();
        }

        bindScrollListener();

        // Streamlit bisa mengganti DOM setelah rerun.
        setInterval(() => {
            bindScrollListener();
        }, 500);

        window.addEventListener("resize", updateThumb);

        if (window.ResizeObserver) {
            const observer = new ResizeObserver(() => {
                bindScrollListener();
            });

            observer.observe(doc.documentElement);
        }
    })();
    </script>
    """,
    unsafe_allow_javascript=True,
)

# ============ KONEKSI GOOGLE SHEETS ============
@st.cache_resource
def connect_sheet():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"], scopes=scopes
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
        "Gagal konek ke Google Sheets. Cek konfigurasi secrets (gcp_service_account, "
        "spreadsheet_url) dan pastikan sheet sudah di-share ke email service account."
    )
    st.exception(e)
    st.stop()


# ============ LOAD DATA PRODUK (dari Google Sheets, auto-refresh tiap 60 detik) ============
@st.cache_data(ttl=60)
def load_produk(_worksheet_produk):
    data = _worksheet_produk.get_all_records()
    df = pd.DataFrame(data)
    df["harga"] = pd.to_numeric(df["harga"], errors="coerce").fillna(0).astype(int)
    return df


produk_df = load_produk(worksheet_produk)

# ============ SESSION STATE ============
if "qty" not in st.session_state:
    st.session_state.qty = {kode: 0 for kode in produk_df["kode_voucher"]}
else:
    # sinkronkan qty kalau ada kode voucher baru yang baru ditambahkan di sheet
    for kode in produk_df["kode_voucher"]:
        st.session_state.qty.setdefault(kode, 0)

# Kalau ada permintaan reset qty (misal setelah order berhasil dikirim),
# lakukan di SINI, di awal script, SEBELUM widget qty dibuat di bawah.
# Ini wajib: session_state milik sebuah widget tidak boleh diubah lagi
# setelah widget itu sempat di-render di run yang sama (itu penyebab
# StreamlitAPIException "cannot be modified after the widget is instantiated").
if st.session_state.get("_do_reset_qty"):
    for kode in produk_df["kode_voucher"]:
        st.session_state.qty[kode] = 0
        st.session_state[f"qtyinput_{kode}"] = 0
    st.session_state["_do_reset_qty"] = False

# Inisialisasi key widget qtyinput_{kode} SEBELUM widget number_input dibuat.
# Ini FIX untuk warning "created with a default value but also had its value
# set via the Session State API": widget qty TIDAK boleh dikasih value=...
# sekaligus key-nya juga diisi manual lewat session_state. Jadi session_state
# ini yang jadi satu-satunya sumber nilai, widget cukup pakai key= saja.
for kode in produk_df["kode_voucher"]:
    st.session_state.setdefault(f"qtyinput_{kode}", st.session_state.qty[kode])

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


def tambah(kode):
    st.session_state.qty[kode] += 1
    st.session_state[f"qtyinput_{kode}"] = st.session_state.qty[kode]


def kurang(kode):
    if st.session_state.qty[kode] > 0:
        st.session_state.qty[kode] -= 1
    st.session_state[f"qtyinput_{kode}"] = st.session_state.qty[kode]


def ubah_qty_manual(kode):
    nilai = st.session_state.get(f"qtyinput_{kode}", 0)
    if nilai is None or nilai < 0:
        nilai = 0
    st.session_state.qty[kode] = int(nilai)


def format_rupiah(n):
    return f"Rp {n:,.0f}".replace(",", ".")


def buat_order_id():
    """Buat Order ID unik: ORD-YYMMDD-HHMMSS-XXX (3 digit acak buat jaga-jaga kalau ada 2 transaksi di detik yang sama)"""
    now = datetime.now()
    acak = random.randint(100, 999)
    return f"ORD-{now.strftime('%y%m%d-%H%M%S')}-{acak}"


def format_no_wa(no_wa):
    """Ubah nomor WA ke format internasional (62xxxxxxxxxx) yang dibutuhkan wa.me"""
    digits = "".join(ch for ch in no_wa if ch.isdigit())
    if digits.startswith("0"):
        digits = "62" + digits[1:]
    elif digits.startswith("620"):
        digits = "62" + digits[3:]
    elif not digits.startswith("62"):
        digits = "62" + digits
    return digits


def build_nota_wa_text(order_id, nama_outlet, no_wa, alamat_pengiriman, timestamp, detail_pesanan, total_harga):
    """Susun teks nota untuk dikirim lewat WhatsApp."""
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
        baris.append(f"   Harga    : {format_rupiah(item['harga_satuan'])}")
        baris.append(f"   Subtotal : {format_rupiah(item['subtotal'])}")
    baris.append(garis)
    baris.append("*TOTAL PESANAN*")
    baris.append(format_rupiah(total_harga))
    baris.append("Mohon diperiksa kembali detail pesanan tersebut.")
    baris.append("Terima kasih atas kepercayaan Anda kepada Toko WG.")
    return "\n".join(baris)


def build_receipt_lines(order_id, nama_outlet, no_wa, alamat_pengiriman, timestamp, detail_pesanan, total_harga):
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
        lines.append(("item", f"[{item['provider']}] {item['produk']} ({item['kode_voucher']})"))
        lines.append(
            (
                "sub",
                f"{item['qty']} x {format_rupiah(item['harga_satuan'])} = {format_rupiah(item['subtotal'])}",
            )
        )
    lines.append(("sep", ""))
    lines.append(("total", f"TOTAL: {format_rupiah(total_harga)}"))
    lines.append(("sep", ""))
    lines.append(("footer", "Terima kasih atas pesanan Anda!"))
    return lines


def _load_font(size, bold=False):
    kandidat = ["consolab.ttf", "courbd.ttf"] if bold else ["consola.ttf", "cour.ttf", "DejaVuSansMono.ttf"]
    for nama in kandidat:
        try:
            return ImageFont.truetype(nama, size)
        except Exception:
            continue
    return ImageFont.load_default()


def build_receipt_image(order_id, nama_outlet, no_wa, alamat_pengiriman, timestamp, detail_pesanan, total_harga):
    lines = build_receipt_lines(order_id, nama_outlet, no_wa, alamat_pengiriman, timestamp, detail_pesanan, total_harga)

    width = 480
    padding = 24
    line_height = 26
    font_normal = _load_font(16)
    font_title = _load_font(20, bold=True)
    font_total = _load_font(18, bold=True)

    height = padding * 2 + sum(
        (34 if tipe == "title" else 14 if tipe == "sep" else 24 if tipe == "total" else line_height)
        for tipe, _ in lines
    )

    img = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(img)
    y = padding

    for tipe, teks in lines:
        if tipe == "sep":
            draw.line([(padding, y + 6), (width - padding, y + 6)], fill=(180, 180, 180), width=1)
            y += 14
        elif tipe == "title":
            bbox = draw.textbbox((0, 0), teks, font=font_title)
            tw = bbox[2] - bbox[0]
            draw.text(((width - tw) / 2, y), teks, fill="black", font=font_title)
            y += 34
        elif tipe == "total":
            bbox = draw.textbbox((0, 0), teks, font=font_total)
            tw = bbox[2] - bbox[0]
            draw.text((width - padding - tw, y), teks, fill="black", font=font_total)
            y += 24
        elif tipe == "footer":
            bbox = draw.textbbox((0, 0), teks, font=font_normal)
            tw = bbox[2] - bbox[0]
            draw.text(((width - tw) / 2, y), teks, fill=(90, 90, 90), font=font_normal)
            y += line_height
        elif tipe == "sub":
            draw.text((padding + 12, y), teks, fill=(90, 90, 90), font=font_normal)
            y += line_height
        else:
            draw.text((padding, y), teks, fill="black", font=font_normal)
            y += line_height

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# ============ HEADER ============
st.title("🛒 Form Pemesanan Outlet Toko\u00A0WG")
st.caption("Isi data outlet, lalu pilih voucher dan jumlahnya.")

# ============ INPUT DATA OUTLET ============
st.subheader("Data Outlet")
col1, col2 = st.columns(2)
with col1:
    nama_outlet = st.text_input("Nama Outlet", placeholder="Konter ABC Cell")
with col2:
    no_wa = st.text_input("No. WhatsApp", placeholder="08123456789")

alamat_pengiriman = st.text_input("Alamat Pengiriman *", placeholder="Jl. Ahmad Yani No.2")
st.caption("*Opsional, boleh dikosongkan")

st.divider()

# ============ FILTER PROVIDER ============
st.subheader("Pilih Produk")

daftar_provider = ["Semua Provider"] + sorted(produk_df["provider"].dropna().unique().tolist())
provider_terpilih = st.selectbox("Filter Provider", daftar_provider)

keyword = st.text_input("Cari produk / kode voucher", placeholder="contoh: 5GB, KIVFIH0")

produk_tampil = produk_df.copy()
if provider_terpilih != "Semua Provider":
    produk_tampil = produk_tampil[produk_tampil["provider"] == provider_terpilih]
if keyword:
    kw = keyword.lower()
    produk_tampil = produk_tampil[
        produk_tampil["produk"].str.lower().str.contains(kw)
        | produk_tampil["kode_voucher"].str.lower().str.contains(kw)
    ]

st.caption(f"Menampilkan {len(produk_tampil)} dari {len(produk_df)} produk")

# ============ DAFTAR PRODUK (dengan qty +/-) ============
total_harga = 0
detail_pesanan = []

# hitung total dari SEMUA produk yang punya qty > 0, bukan cuma yang lagi difilter
for _, row in produk_df.iterrows():
    qty = st.session_state.qty.get(row["kode_voucher"], 0)
    if qty > 0:
        subtotal = qty * row["harga"]
        total_harga += subtotal
        detail_pesanan.append(
            {
                "provider": row["provider"],
                "kode_voucher": row["kode_voucher"],
                "produk": row["produk"],
                "harga_satuan": row["harga"],
                "qty": qty,
                "subtotal": subtotal,
            }
        )

produk_list = produk_tampil.to_dict("records")
JUMLAH_KOLOM = 3

for i in range(0, len(produk_list), JUMLAH_KOLOM):
    baris_produk = produk_list[i : i + JUMLAH_KOLOM]
    kolom = st.columns(JUMLAH_KOLOM)

    for kolom_idx, row in enumerate(baris_produk):
        kode = row["kode_voucher"]
        nama = row["produk"]
        harga = row["harga"]

        with kolom[kolom_idx]:
            with st.container(border=True):
                st.markdown(f"**{nama}**")
                if harga > 0:
                    st.caption(f"{row['provider']} · {kode}")
                    st.markdown(f"**{format_rupiah(harga)}**")
                else:
                    st.caption(f"{row['provider']} · {kode}")
                    st.caption("⚠️ harga belum tersedia")

                c_minus, c_qty, c_plus = st.columns([1, 1.4, 1])
                with c_minus:
                    st.button(
                        "−", key=f"minus_{kode}", on_click=kurang, args=(kode,),
                        disabled=(harga == 0), use_container_width=False,
                    )
                with c_qty:
                    # PENTING: TIDAK pakai parameter value=... di sini.
                    # Nilainya sepenuhnya dikendalikan lewat session_state
                    # (key="qtyinput_{kode}") yang diupdate oleh tambah(),
                    # kurang(), dan ubah_qty_manual(). Ini yang menghilangkan
                    # warning "default value but also set via Session State API".
                    st.number_input(
                        "Qty", min_value=0, step=1,
                        key=f"qtyinput_{kode}", on_change=ubah_qty_manual, args=(kode,),
                        disabled=(harga == 0), label_visibility="collapsed",
                    )
                with c_plus:
                    # PENTING: label TIDAK boleh cuma "+" polos. Streamlit render
                    # label tombol pakai Markdown, dan "+" sendirian di awal teks
                    # itu SINTAKS bullet list Markdown -> jadinya "+" nya "dimakan"
                    # jadi bullet kosong, bukan tampil sebagai karakter "+".
                    # Makanya harus di-escape pakai backslash ("\+") supaya
                    # kebaca sebagai tanda plus literal.
                    st.button(
                        "\\+", key=f"plus_{kode}", on_click=tambah, args=(kode,),
                        disabled=(harga == 0), use_container_width=False,
                    )

st.divider()

# ============ RINGKASAN PESANAN ============
if detail_pesanan:
    with st.expander(f"🧾 Ringkasan pesanan ({len(detail_pesanan)} item dipilih)", expanded=True):
        st.dataframe(pd.DataFrame(detail_pesanan), use_container_width=True, hide_index=True)

col_total1, col_total2 = st.columns([2, 1])
with col_total2:
    st.metric("Total Pesanan", format_rupiah(total_harga))

# ============ SIMPAN KE GOOGLE SHEETS ============
if st.button("🧾 Konfirmasi & Kirim Pesanan", type="primary", use_container_width=True, disabled=not sheet_ok):
    if not nama_outlet or not no_wa:
        st.error("Nama outlet dan No. WhatsApp wajib diisi.")
    elif total_harga == 0:
        st.error("Pilih minimal 1 produk dengan quantity lebih dari 0.")
    else:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
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
            worksheet.append_rows(rows_to_append, value_input_option="USER_ENTERED")

            # siapkan struk (gambar PNG) untuk didownload, disimpan di session_state
            # supaya masih ada setelah st.rerun()
            st.session_state.last_receipt = build_receipt_image(
                order_id, nama_outlet, no_wa, alamat_pengiriman, timestamp, detail_pesanan, total_harga
            )
            nama_file_aman = nama_outlet.strip().replace(" ", "_")
            st.session_state.last_receipt_name = f"struk_{order_id}_{nama_file_aman}.png"

            # siapkan link WhatsApp berisi nota, siap kirim ke nomor outlet
            nomor_wa_tujuan = format_no_wa(no_wa)
            teks_nota = build_nota_wa_text(
                order_id, nama_outlet, no_wa, alamat_pengiriman, timestamp, detail_pesanan, total_harga
            )
            st.session_state.last_wa_link = f"https://wa.me/{nomor_wa_tujuan}?text={quote(teks_nota)}"
            st.session_state.last_order_id = order_id

            st.session_state.show_success = True

            # JANGAN reset qty/qtyinput di sini secara langsung — widget-nya
            # sudah sempat dirender di run ini (loop produk di atas), jadi
            # session_state key milik widget tidak boleh diubah lagi sekarang.
            # Cukup pasang flag, reset sebenarnya dieksekusi di awal script
            # pada run berikutnya (sebelum widget qty dibuat).
            st.session_state["_do_reset_qty"] = True
            st.rerun()
        except Exception as e:
            st.error("Gagal menyimpan ke Google Sheets.")
            st.exception(e)

# ============ STATUS SUKSES + DOWNLOAD STRUK ============
if st.session_state.show_success and st.session_state.last_receipt:
    st.success(f"✅ Pesanan tersimpan! Order ID: **{st.session_state.last_order_id}**")
    st.image(st.session_state.last_receipt, caption="Preview Struk Pesanan", width=340)

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
        if st.button("Tutup", use_container_width=True):
            st.session_state.show_success = False
            st.rerun()

# ============ LIHAT DATA TERSIMPAN ============
# Sementara dihapus/disembunyikan dulu — tinggal uncomment kalau mau dipakai lagi.
# with st.expander("📄 Lihat data pesanan tersimpan"):
#     if sheet_ok:
#         try:
#             data = worksheet.get_all_records()
#             if data:
#                 st.dataframe(pd.DataFrame(data), use_container_width=True)
#             else:
#                 st.info("Belum ada data tersimpan.")
#         except Exception as e:
#             st.error("Gagal mengambil data dari Google Sheets.")
#             st.exception(e)
