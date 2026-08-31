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
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from PIL import Image, ImageDraw, ImageFont

NAMA_WORKSHEET_PESANAN = "Pesanan"
NAMA_WORKSHEET_PRODUK_SNIPER = "Produk_Sniper"
NAMA_WORKSHEET_PRODUK_MATENGAN = "Produk_Matengan"
NAMA_WORKSHEET_STATUS = "StatusKirim"

WIB = ZoneInfo("Asia/Jakarta")

def now_wib():
    """Waktu sekarang di zona WIB (real-time, bukan waktu server)."""
    return datetime.now(WIB)

st.set_page_config(
    page_title="Form Pesanan Outlet",
    page_icon="🛒",
    layout="centered",
)

st.html(
    """
<style>
/* CSS tidak diubah — sama persis seperti file asli kamu, dipangkas di sini */
</style>
""",
    unsafe_allow_javascript=True,
)

@st.cache_resource
def connect_sheet():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]

    gcp_service_account = json.loads(
        os.environ["gcp_service_account"]
    )

    spreadsheet_url = os.environ["spreadsheet_url"]

    creds = Credentials.from_service_account_info(
        gcp_service_account,
        scopes=scopes,
    )

    client = gspread.authorize(creds)

    spreadsheet = client.open_by_url(spreadsheet_url)

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


@st.cache_resource
def connect_drive():
    """Koneksi ke Google Drive API pakai service account yang sama."""
    scopes = ["https://www.googleapis.com/auth/drive"]

    gcp_service_account = json.loads(os.environ["gcp_service_account"])

    creds = Credentials.from_service_account_info(
        gcp_service_account,
        scopes=scopes,
    )

    return build("drive", "v3", credentials=creds)


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

try:
    drive_service = connect_drive()
    DRIVE_FOLDER_ID = os.environ.get("drive_folder_id")
except Exception as e:
    drive_service = None
    DRIVE_FOLDER_ID = None
    st.warning(
        "⚠️ Gagal konek ke Google Drive. Fitur simpan link file SN "
        "tidak akan berfungsi, tapi pesanan tetap bisa dikirim."
    )


def upload_txt_ke_drive(nama_file, isi_bytes):
    """
    Upload file .txt ke folder Drive (drive_folder_id), lalu set
    permission "anyone with link can view" dan kembalikan link
    view-nya. Mengembalikan tuple (link_atau_None, pesan_error_atau_None).
    """
    if not drive_service or not DRIVE_FOLDER_ID:
        return None, "drive_folder_id belum dikonfigurasi di environment variables."

    try:
        media = MediaIoBaseUpload(
            io.BytesIO(isi_bytes),
            mimetype="text/plain",
            resumable=False,
        )

        file_metadata = {
            "name": nama_file,
            "parents": [DRIVE_FOLDER_ID],
        }

        file_hasil = drive_service.files().create(
            body=file_metadata,
            media_body=media,
            fields="id, webViewLink",
        ).execute()

        drive_service.permissions().create(
            fileId=file_hasil["id"],
            body={"type": "anyone", "role": "reader"},
        ).execute()

        return file_hasil.get("webViewLink"), None

    except Exception as e:
        return None, f"Gagal upload ke Drive: {e}"

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

if "sn_input" not in st.session_state:
    st.session_state.sn_input = {}
if "sn_mode" not in st.session_state:
    st.session_state.sn_mode = {}
if "sn_manual" not in st.session_state:
    st.session_state.sn_manual = {}
if "sn_upload" not in st.session_state:
    st.session_state.sn_upload = {}
if "sn_upload_raw" not in st.session_state:
    st.session_state.sn_upload_raw = {}

def _parse_qty(value):
    try:
        return max(0, int(str(value).strip() or "0"))
    except (TypeError, ValueError):
        return 0

def generate_sn_list(sn_awal, sn_akhir):
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

def validate_sn_manual_list(list_input):
    list_sn = [(s or "").strip() for s in list_input]

    if any(not s for s in list_sn):
        return [], None

    counter = {}
    for sn in list_sn:
        counter[sn] = counter.get(sn, 0) + 1

    duplikat = sorted([sn for sn, jml in counter.items() if jml > 1])

    if duplikat:
        return [], f"Ada SN yang dobel: {', '.join(duplikat)}"

    return list_sn, None

def parse_sn_upload_file(uploaded_file):
    if uploaded_file is None:
        return [], None

    try:
        raw = uploaded_file.getvalue()

        MAX_TXT_SIZE = 10 * 1024 * 1024
        if len(raw) > MAX_TXT_SIZE:
            return [], "Ukuran file TXT maksimal 10 MB."

        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = raw.decode("utf-8")
    except Exception as e:
        return [], f"File TXT tidak dapat dibaca: {e}"

    list_sn = [line.strip() for line in text.splitlines() if line.strip()]

    if len(list_sn) > 4000:
        return [], "File TXT maksimal berisi 4000 baris SN."

    return validate_sn_manual_list(list_sn)

def tambah(kode):
    st.session_state.qty[kode] = st.session_state.qty.get(kode, 0) + 1

def kurang(kode):
    st.session_state.qty[kode] = max(
        0, st.session_state.qty.get(kode, 0) - 1
    )

def format_rupiah(n):
    return f"Rp {n:,.0f}".replace(",", ".")

def sn_sebagai_teks(sn):
    sn = str(sn or "").strip()

    if not sn:
        return sn

    return f"'{sn}"

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
    order_id, nama_outlet, no_wa, alamat_pengiriman,
    timestamp, detail_pesanan, total_harga,
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
        baris.append(f"   Harga    : {format_rupiah(item['harga_satuan'])}")
        baris.append(f"   Subtotal : {format_rupiah(item['subtotal'])}")

    baris.append(garis)
    baris.append("*TOTAL PESANAN*")
    baris.append(format_rupiah(total_harga))
    baris.append("")
    baris.append("Mohon diperiksa kembali detail pesanan tersebut.")
    baris.append("Terima kasih atas kepercayaan Anda kepada Toko WG.")

    return "\n".join(baris)

def build_konfirmasi_cs_text(
    order_id, nama_outlet, no_wa, alamat_pengiriman,
    timestamp, detail_pesanan, total_harga,
):
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
        baris.append(f"   Harga    : {format_rupiah(item['harga_satuan'])}")
        baris.append(f"   Subtotal : {format_rupiah(item['subtotal'])}")

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
    order_id, nama_outlet, no_wa, alamat_pengiriman,
    timestamp, detail_pesanan, total_harga,
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
        lines.append(("item", f"[{item['provider']}] {item['produk']}"))
        lines.append((
            "sub",
            f"{item['qty']} x {format_rupiah(item['harga_satuan'])} = "
            f"{format_rupiah(item['subtotal'])}",
        ))

    lines.append(("sep", ""))
    lines.append(("total", f"TOTAL: {format_rupiah(total_harga)}"))
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
    order_id, nama_outlet, no_wa, alamat_pengiriman,
    timestamp, detail_pesanan, total_harga,
):
    lines = build_receipt_lines(
        order_id, nama_outlet, no_wa, alamat_pengiriman,
        timestamp, detail_pesanan, total_harga,
    )

    width = 480
    padding = 20
    line_height = 22

    font_normal = _load_font(16)
    font_title = _load_font(20, bold=True)
    font_total = _load_font(18, bold=True)

    height = padding * 2 + sum(
        (
            28 if tipe == "title"
            else 10 if tipe == "sep"
            else 20 if tipe == "total"
            else line_height
        )
        for tipe, _ in lines
    )

    img = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(img)
    y = padding

    for tipe, teks in lines:
        if tipe == "sep":
            draw.line([(padding, y + 5), (width - padding, y + 5)], fill=(180, 180, 180), width=1)
            y += 10
        elif tipe == "title":
            bbox = draw.textbbox((0, 0), teks, font=font_title)
            tw = bbox[2] - bbox[0]
            draw.text(((width - tw) / 2, y), teks, fill="black", font=font_title)
            y += 28
        elif tipe == "total":
            bbox = draw.textbbox((0, 0), teks, font=font_total)
            tw = bbox[2] - bbox[0]
            draw.text((width - padding - tw, y), teks, fill="black", font=font_total)
            y += 20
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

def get_status_map(ws_status):
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
    ws_status.append_row(
        [order_id, "TRUE", now_wib().strftime("%Y-%m-%d %H:%M:%S")],
        value_input_option="USER_ENTERED",
    )

def batalkan_tandai(ws_status, order_id):
    try:
        sel = ws_status.findall(order_id)
    except Exception:
        sel = []

    for cell in sorted(sel, key=lambda c: c.row, reverse=True):
        if cell.col == 1:
            ws_status.delete_rows(cell.row)

st.markdown(
    """
    <div class="wg-header">
        <div class="wg-header-line1">
            <span class="wg-header-icon">🛒</span>
            <span>TOKO WG</span>
        </div>
        <div class="wg-header-line2">Form Order</div>
        <div class="wg-header-desc">
            Isi data outlet, lalu pilih voucher dan jumlahnya.
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

st.subheader("Data Outlet")

col1, col2 = st.columns(2)

with col1:
    nama_outlet = st.text_input("Nama Outlet", placeholder="Konter ABC Cell")

with col2:
    no_wa = st.text_input("No. WhatsApp", placeholder="08123456789")

alamat_pengiriman = st.text_input("Alamat Pengiriman", placeholder="Jl. Ahmad Yani No. 2")

st.caption("Alamat pengiriman hanya untuk transaksi Fisik Matengan")
st.divider()

st.subheader("Pilih Kategori")

kategori_terpilih = st.selectbox(
    "Filter Kategori", ["Sniper", "Matengan"], label_visibility="collapsed",
)

if kategori_terpilih == "Sniper":
    worksheet_produk_aktif = worksheet_produk_sniper
else:
    worksheet_produk_aktif = worksheet_produk_matengan

produk_df = load_produk(worksheet_produk_aktif, kategori_terpilih)

if produk_df.empty:
    st.warning(f"Belum ada data produk pada worksheet Produk_{kategori_terpilih}.")
    st.stop()

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
    st.session_state.sn_mode = {}
    st.session_state.sn_manual = {}
    st.session_state.sn_upload = {}
    st.session_state.sn_upload_raw = {}

st.divider()

st.subheader("Pilih Provider")

daftar_provider = sorted(produk_df["provider"].dropna().unique().tolist())

provider_terpilih = st.selectbox("Filter Provider", daftar_provider, label_visibility="collapsed")

keyword = st.text_input("Cari produk", placeholder="Contoh: 5GB")

produk_tampil = produk_df.copy()

if provider_terpilih:
    produk_tampil = produk_tampil[produk_tampil["provider"] == provider_terpilih]

if keyword:
    kw = keyword.lower()
    produk_tampil = produk_tampil[
        produk_tampil["produk"].astype(str).str.lower().str.contains(kw, na=False)
        | produk_tampil["kode_voucher"].astype(str).str.lower().str.contains(kw, na=False)
    ]

ITEMS_PER_PAGE = 15

total_produk_filter = len(produk_tampil)
total_halaman = max(1, -(-total_produk_filter // ITEMS_PER_PAGE))

filter_key = f"{provider_terpilih}|{keyword}"
if st.session_state.get("_last_filter_key") != filter_key:
    st.session_state["_last_filter_key"] = filter_key
    st.session_state["halaman_produk"] = 1

if "halaman_produk" not in st.session_state:
    st.session_state["halaman_produk"] = 1

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
                        [1, 1.35], gap="small", vertical_alignment="center",
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
                                [1, 1.6, 1], gap="small", vertical_alignment="center",
                            )

                            with c_minus:
                                st.container(key=f"qty_minus_{kode}")
                                st.button(
                                    "−", key=f"qty_minus_{kode}_btn",
                                    on_click=kurang, args=(kode,),
                                    disabled=(harga == 0), use_container_width=True,
                                )

                            with c_qty:
                                teks_qty = st.text_input(
                                    f"Jumlah {kode}", value=str(qty_sekarang),
                                    disabled=(harga == 0), label_visibility="collapsed",
                                    placeholder="0",
                                )

                                nilai_ketik = _parse_qty(teks_qty)
                                if nilai_ketik != st.session_state.qty.get(kode, 0):
                                    st.session_state.qty[kode] = nilai_ketik

                            with c_plus:
                                st.container(key=f"qty_plus_{kode}")
                                st.button(
                                    "+", key=f"qty_plus_{kode}_btn",
                                    on_click=tambah, args=(kode,),
                                    disabled=(harga == 0), use_container_width=True,
                                )

total_harga = 0
detail_pesanan = []

for _, row in produk_df.iterrows():
    kode = row["kode_voucher"]
    qty = st.session_state.qty.get(kode, 0)

    if qty > 0:
        subtotal = qty * row["harga"]
        total_harga += subtotal

        detail_pesanan.append({
            "provider": row["provider"],
            "kode_voucher": kode,
            "produk": row["produk"],
            "harga_satuan": row["harga"],
            "qty": qty,
            "subtotal": subtotal,
        })

def _daftar_nomor_halaman(halaman_aktif, total):
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

        rasio_kolom = [1.2]
        for n in daftar_nomor:
            rasio_kolom.append(1 if n is not None else 0.5)
        rasio_kolom.append(1.2)

        kolom_pagination = st.columns(rasio_kolom, gap="small", vertical_alignment="center")

        col_prev = kolom_pagination[0]
        col_next = kolom_pagination[-1]
        kolom_nomor = kolom_pagination[1:-1]

        with col_prev:
            if st.button("◀", use_container_width=True, disabled=(halaman_sekarang <= 1), key="btn_halaman_prev"):
                st.session_state["halaman_produk"] = halaman_sekarang - 1
                st.rerun()

        for kolom, nomor in zip(kolom_nomor, daftar_nomor):
            with kolom:
                if nomor is None:
                    st.markdown("<div class='wg-pagination-ellipsis'>···</div>", unsafe_allow_html=True)
                else:
                    if st.button(
                        str(nomor), use_container_width=True, key=f"btn_halaman_{nomor}",
                        type=("primary" if nomor == halaman_sekarang else "secondary"),
                    ):
                        st.session_state["halaman_produk"] = nomor
                        st.rerun()

        with col_next:
            if st.button("▶", use_container_width=True, disabled=(halaman_sekarang >= total_halaman), key="btn_halaman_next"):
                st.session_state["halaman_produk"] = halaman_sekarang + 1
                st.rerun()

st.divider()

sn_semua_valid = False

if detail_pesanan:
    with st.expander(f"🧾 Ringkasan pesanan ({len(detail_pesanan)} item dipilih)", expanded=True):
        df_ringkasan = pd.DataFrame(detail_pesanan).drop(columns=["provider", "kode_voucher"])

        df_ringkasan["harga_satuan"] = df_ringkasan["harga_satuan"].apply(format_rupiah)
        df_ringkasan["qty"] = df_ringkasan["qty"].astype(str)
        df_ringkasan["subtotal"] = df_ringkasan["subtotal"].apply(format_rupiah)

        st.dataframe(df_ringkasan, use_container_width=True, hide_index=True)

        if kategori_terpilih == "Sniper":
            st.markdown("**Input Serial Number (SN)**")

            semua_item_valid = []
            item_konflik = []

            MODE_BERURUTAN = "SN Berurutan"
            MODE_ACAK = "SN Acak"
            MODE_UPLOAD = "SN Upload.txt"

            def render_sn_preview_box(container_key, list_sn):
                baris_html = "".join(
                    f'<div class="wg-sn-preview-row">'
                    f'<span class="wg-sn-preview-idx">{idx}.</span>{sn}'
                    f'</div>'
                    for idx, sn in enumerate(list_sn, start=1)
                )

                with st.container(key=container_key):
                    st.markdown(baris_html, unsafe_allow_html=True)

            for item in detail_pesanan:
                kode = item["kode_voucher"]
                qty = item["qty"]

                if kode not in st.session_state.sn_input:
                    st.session_state.sn_input[kode] = {"awal": "", "akhir": ""}
                if kode not in st.session_state.sn_mode:
                    st.session_state.sn_mode[kode] = MODE_BERURUTAN
                if kode not in st.session_state.sn_manual:
                    st.session_state.sn_manual[kode] = [""] * qty
                elif len(st.session_state.sn_manual[kode]) != qty:
                    lama = st.session_state.sn_manual[kode]
                    if len(lama) < qty:
                        st.session_state.sn_manual[kode] = lama + [""] * (qty - len(lama))
                    else:
                        st.session_state.sn_manual[kode] = lama[:qty]

                item_valid = False
                item["sn_list"] = []

                sn_item_box = st.container(key=f"snitem-{kode}")

                with sn_item_box:
                    st.markdown(
                        f'<div class="wg-sn-item-title">'
                        f'{item["produk"]}'
                        f'<span class="wg-sn-item-qty"> · qty {qty}</span>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )

                    mode_options = [MODE_BERURUTAN, MODE_ACAK, MODE_UPLOAD]

                    if st.session_state.sn_mode[kode] not in mode_options:
                        st.session_state.sn_mode[kode] = MODE_BERURUTAN

                    mode_terpilih = st.radio(
                        "Mode Input SN", mode_options,
                        index=mode_options.index(st.session_state.sn_mode[kode]),
                        key=f"sn_mode_{kode}", horizontal=True, label_visibility="collapsed",
                    )

                    st.session_state.sn_mode[kode] = mode_terpilih

                    if mode_terpilih == MODE_BERURUTAN:
                        c_sn1, c_sn2 = st.columns(2)

                        with c_sn1:
                            sn_awal = st.text_input("SN Awal", value=st.session_state.sn_input[kode]["awal"], key=f"sn_awal_{kode}")

                        with c_sn2:
                            sn_akhir = st.text_input("SN Akhir", value=st.session_state.sn_input[kode]["akhir"], key=f"sn_akhir_{kode}")

                        st.session_state.sn_input[kode] = {"awal": sn_awal, "akhir": sn_akhir}

                        list_sn, sn_error = generate_sn_list(sn_awal, sn_akhir)

                        if sn_error:
                            st.error(sn_error)
                        elif not sn_awal or not sn_akhir:
                            pass
                        else:
                            jumlah_generate = len(list_sn)
                            item_valid = jumlah_generate == qty

                            if item_valid:
                                label_preview = f"✅ {jumlah_generate} dari {qty} SN sesuai qty"
                            else:
                                label_preview = (
                                    f"❌ {jumlah_generate} dari {qty} SN — "
                                    f"{'kurang' if jumlah_generate < qty else 'lebih'} "
                                    f"{abs(jumlah_generate - qty)}"
                                )

                            with st.expander(label_preview, expanded=False):
                                render_sn_preview_box(f"snpreview-{kode}", list_sn)

                            if item_valid:
                                item["sn_list"] = list_sn

                    elif mode_terpilih == MODE_ACAK:
                        st.caption(f"Masukkan SN satu per satu ({qty} dibutuhkan)")

                        nilai_manual = [""] * qty

                        sn_manual_box = st.container(key=f"snmanual-{kode}")

                        with sn_manual_box:
                            for i in range(0, qty, 2):
                                c_sn_a, c_sn_b = st.columns(2, gap="small")

                                with c_sn_a:
                                    idx_a = i
                                    nilai_manual[idx_a] = st.text_input(
                                        f"SN #{idx_a + 1}",
                                        value=st.session_state.sn_manual[kode][idx_a],
                                        key=f"sn_manual_{kode}_{idx_a}",
                                    )

                                if i + 1 < qty:
                                    with c_sn_b:
                                        idx_b = i + 1
                                        nilai_manual[idx_b] = st.text_input(
                                            f"SN #{idx_b + 1}",
                                            value=st.session_state.sn_manual[kode][idx_b],
                                            key=f"sn_manual_{kode}_{idx_b}",
                                        )

                        st.session_state.sn_manual[kode] = nilai_manual

                        list_sn, sn_error = validate_sn_manual_list(nilai_manual)

                        if sn_error:
                            st.error(sn_error)
                        elif not list_sn:
                            pass
                        else:
                            jumlah_terisi = len(list_sn)
                            item_valid = jumlah_terisi == qty

                            label_preview = f"✅ {jumlah_terisi} dari {qty} SN terisi (tidak ada duplikat)"

                            with st.expander(label_preview, expanded=False):
                                render_sn_preview_box(f"snpreview-acak-{kode}", list_sn)

                            item["sn_list"] = list_sn

                    else:
                        st.caption(f"Upload 1 file .txt untuk {qty} SN (maksimal 4000 baris)")

                        uploaded_sn_file = st.file_uploader(
                            "File SN (.txt)", type=["txt"], accept_multiple_files=False,
                            key=f"sn_upload_file_{kode}",
                            help="Satu file untuk produk ini. Tulis 1 SN pada setiap baris. Maksimal 4000 baris.",
                        )

                        if uploaded_sn_file is None:
                            st.session_state.sn_upload[kode] = []
                            st.session_state.sn_upload_raw[kode] = None
                        else:
                            # TAMBAHAN BARU: simpan bytes mentah file supaya
                            # masih ada saat "Kirim Pesanan" ditekan, untuk
                            # diupload ke Google Drive.
                            st.session_state.sn_upload_raw[kode] = uploaded_sn_file.getvalue()

                            list_upload, upload_error = parse_sn_upload_file(uploaded_sn_file)

                            if upload_error:
                                st.session_state.sn_upload[kode] = []
                                st.error(upload_error)
                            elif not list_upload:
                                st.session_state.sn_upload[kode] = []
                            else:
                                st.session_state.sn_upload[kode] = list_upload
                                jumlah_upload = len(list_upload)
                                item_valid = jumlah_upload == qty

                                if item_valid:
                                    label_preview = f"✅ {jumlah_upload} dari {qty} SN sesuai qty"
                                else:
                                    label_preview = (
                                        f"❌ {jumlah_upload} dari {qty} SN — "
                                        f"{'kurang' if jumlah_upload < qty else 'lebih'} "
                                        f"{abs(jumlah_upload - qty)}"
                                    )

                                with st.expander(label_preview, expanded=False):
                                    render_sn_preview_box(f"snpreview-upload-{kode}", list_upload)

                                if item_valid:
                                    item["sn_list"] = list_upload

                data_urut = st.session_state.sn_input.get(kode, {})
                list_urut, err_urut = generate_sn_list(data_urut.get("awal", ""), data_urut.get("akhir", ""))
                valid_urut = (not err_urut and bool(list_urut) and len(list_urut) == qty)

                list_acak, err_acak = validate_sn_manual_list(st.session_state.sn_manual.get(kode, []))
                valid_acak = (not err_acak and bool(list_acak) and len(list_acak) == qty)

                list_upload, err_upload = validate_sn_manual_list(st.session_state.sn_upload.get(kode, []))
                valid_upload = (not err_upload and bool(list_upload) and len(list_upload) == qty and len(list_upload) <= 4000)

                mode_valid_count = sum([valid_urut, valid_acak, valid_upload])

                if mode_valid_count > 1:
                    item_valid = False
                    item["sn_list"] = []
                    item_konflik.append(item["produk"])

                    st.warning(
                        "⚠️ Lebih dari satu opsi input SN sudah terisi lengkap "
                        "untuk produk ini. Pesanan hanya bisa dikirim jika "
                        "memilih **salah satu** opsi saja — kosongkan opsi SN "
                        "lain yang tidak digunakan sebelum mengirim."
                    )
                elif valid_urut:
                    item_valid = True
                    item["sn_list"] = list_urut
                elif valid_acak:
                    item_valid = True
                    item["sn_list"] = list_acak
                elif valid_upload:
                    item_valid = True
                    item["sn_list"] = list_upload
                else:
                    item_valid = False
                    item["sn_list"] = []

                semua_item_valid.append(item_valid)

            sn_semua_valid = all(semua_item_valid) if semua_item_valid else False

            if not sn_semua_valid:
                if item_konflik:
                    st.warning(
                        "Produk berikut terisi SN di lebih dari satu mode "
                        "(Berurutan, Acak, atau Upload.txt) sekaligus: "
                        + ", ".join(item_konflik)
                        + ". Pilih salah satu mode saja untuk tiap produk "
                        "tersebut sebelum mengirim pesanan."
                    )
                else:
                    st.warning(
                        "Lengkapi salah satu dari 3 opsi input SN "
                        "(SN Berurutan, SN Acak, atau SN Upload.txt) "
                        "untuk semua produk. Jumlah SN harus sama dengan qty "
                        "dan file TXT maksimal 4000 baris."
                    )
        else:
            for item in detail_pesanan:
                item["sn_list"] = [""]

            sn_semua_valid = True

    col_total1, col_total2 = st.columns([2, 1])

    with col_total2:
        st.metric("Total Pesanan", format_rupiah(total_harga))

if st.button(
    "🧾 Kirim Pesanan", type="primary", use_container_width=True,
    disabled=not sheet_ok or not sn_semua_valid,
):
    if not nama_outlet or not no_wa:
        st.error("Nama outlet dan No. WhatsApp wajib diisi.")

    elif total_harga == 0:
        st.error("Pilih minimal 1 produk dengan quantity lebih dari 0.")

    elif not sn_semua_valid:
        st.error("Lengkapi Serial Number (SN) untuk semua produk terlebih dahulu.")

    else:
        timestamp = now_wib().strftime("%Y-%m-%d %H:%M:%S")
        order_id = buat_order_id()

        # ============================================================
        # TAMBAHAN BARU: upload file SN (.txt) ke Google Drive untuk
        # tiap item yang menggunakan mode "SN Upload.txt", SEBELUM
        # data ditulis ke sheet. Link hasil upload disimpan di dict
        # file_txt_links, keyed by kode_voucher.
        # ============================================================
        file_txt_links = {}

        for item in detail_pesanan:
            kode = item["kode_voucher"]

            if st.session_state.sn_mode.get(kode) == "SN Upload.txt":
                raw_bytes = st.session_state.sn_upload_raw.get(kode)

                if raw_bytes:
                    nama_file_aman_drive = nama_outlet.strip().replace(" ", "_")
                    nama_file_drive = f"SN_{order_id}_{kode}_{nama_file_aman_drive}.txt"

                    link, err = upload_txt_ke_drive(nama_file_drive, raw_bytes)

                    if err:
                        st.warning(f"⚠️ Gagal upload file SN untuk {item['produk']}: {err}")
                        file_txt_links[kode] = ""
                    else:
                        file_txt_links[kode] = link or ""
                else:
                    file_txt_links[kode] = ""
            else:
                file_txt_links[kode] = ""

        # rows_to_append: sama seperti asli, DITAMBAH 1 kolom baru
        # di PALING KANAN (file_txt_link) — pastikan header di sheet
        # Pesanan juga sudah ditambah kolom ini di posisi paling kanan.
        rows_to_append = [
            [
                timestamp,
                order_id,
                nama_outlet,
                f"'{no_wa.strip()}",
                alamat_pengiriman,
                item["provider"],
                item["kode_voucher"],
                item["produk"],
                item["harga_satuan"],
                item["qty"],
                item["subtotal"],
                total_harga,
                sn_sebagai_teks(sn),
                file_txt_links.get(item["kode_voucher"], ""),
            ]
            for item in detail_pesanan
            for sn in item["sn_list"]
        ]

        try:
            hasil_append = worksheet.append_rows(rows_to_append, value_input_option="USER_ENTERED")

            timestamp_wa = timestamp
            try:
                updated_range = hasil_append["updates"]["updatedRange"]
                baris_pertama = int("".join(ch for ch in updated_range.split("!")[1].split(":")[0] if ch.isdigit()))
                nilai_sel = worksheet.acell(f"A{baris_pertama}").value
                if nilai_sel:
                    timestamp_wa = nilai_sel
            except Exception:
                pass

            st.session_state.last_receipt = build_receipt_image(
                order_id, nama_outlet, no_wa, alamat_pengiriman,
                timestamp, detail_pesanan, total_harga,
            )

            nama_file_aman = nama_outlet.strip().replace(" ", "_")
            st.session_state.last_receipt_name = f"struk_{order_id}_{nama_file_aman}.png"

            nomor_wa_tujuan = format_no_wa(no_wa)

            teks_nota = build_nota_wa_text(
                order_id, nama_outlet, no_wa, alamat_pengiriman,
                timestamp_wa, detail_pesanan, total_harga,
            )

            st.session_state.last_wa_link = f"https://wa.me/{nomor_wa_tujuan}?text={quote(teks_nota)}"

            cs_wa_number = os.environ.get("cs_wa_number")

            if cs_wa_number:
                teks_konfirmasi_cs = build_konfirmasi_cs_text(
                    order_id, nama_outlet, no_wa, alamat_pengiriman,
                    timestamp_wa, detail_pesanan, total_harga,
                )

                nomor_cs_tujuan = format_no_wa(cs_wa_number)

                st.session_state.last_cs_wa_link = f"https://wa.me/{nomor_cs_tujuan}?text={quote(teks_konfirmasi_cs)}"
            else:
                st.session_state.last_cs_wa_link = None

            st.session_state.last_order_id = order_id
            st.session_state.show_success = True

            st.session_state["_do_reset_qty"] = True
            st.rerun()

        except Exception as e:
            st.error("Gagal menyimpan ke Google Sheets.")
            st.exception(e)

if st.session_state.show_success and st.session_state.last_receipt:
    st.success(f"Pesanan tersimpan! Order ID: **{st.session_state.last_order_id}**")

    if st.session_state.last_cs_wa_link:
        st.link_button("💬 Konfirmasi ke Admin via WhatsApp", st.session_state.last_cs_wa_link, use_container_width=True)
    else:
        st.caption("⚠️ Nomor WA CS belum dikonfigurasi (`cs_wa_number` di Railway Variables).")

    st.image(st.session_state.last_receipt, caption="Preview Struk Pesanan", width=340)

    dl_col, close_col = st.columns([3, 1])

    with dl_col:
        st.download_button(
            "⬇️ Download Struk (Gambar)", data=st.session_state.last_receipt,
            file_name=st.session_state.last_receipt_name, mime="image/png",
            use_container_width=True,
        )

    with close_col:
        if st.button("Tutup", use_container_width=True):
            st.session_state.show_success = False
            st.rerun()

if "admin_fullscreen" not in st.session_state:
    st.session_state.admin_fullscreen = False

st.html(
    f"""
<script>
document.body.classList.toggle("wg-admin-fullscreen", {str(st.session_state.admin_fullscreen).lower()});
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
        st.warning("Panel admin belum aktif. Tambahkan `admin_password` di secrets.toml untuk mengaktifkan fitur ini.")

    elif not st.session_state.admin_authed:
        pw_input = st.text_input("Password Admin", type="password", key="admin_pw_input")

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
            if st.button("Keluar", key="admin_logout_btn"):
                st.session_state.admin_authed = False
                st.rerun()

        st.caption(
            "Kirim nota dari HP/laptop yang nomor WhatsApp-nya "
            "adalah nomor admin, agar nota terkirim dari nomor "
            "admin — bukan dari HP outlet."
        )

        st.toggle("Mode layar penuh", key="admin_fullscreen", help="Perluas panel admin menjadi tampilan penuh.")

        if st.session_state.admin_fullscreen:
            st.caption("Panel admin sedang ditampilkan penuh.")

        search_kw = st.text_input("Cari order ID / nama outlet", key="admin_search", placeholder="Contoh: ORD-260819 atau ABC Cell")

        try:
            semua_data = worksheet.get_all_records()
        except Exception as e:
            semua_data = []
            st.error("Gagal mengambil data pesanan dari Google Sheets.")
            st.exception(e)

        if not semua_data:
            st.markdown('<div class="wg-admin-empty">Belum ada pesanan masuk.</div>', unsafe_allow_html=True)
        else:
            df_semua = pd.DataFrame(semua_data)

            if "order_id" not in df_semua.columns:
                st.warning("Kolom `order_id` tidak ditemukan di sheet. Pastikan header sheet sudah sesuai.")
            else:
                status_map = get_status_map(worksheet_status)

                order_ids_unik = (
                    df_semua[["order_id", "timestamp"]]
                    .drop_duplicates(subset="order_id")
                    .sort_values("timestamp", ascending=False)["order_id"]
                    .tolist()
                )

                daftar_order = []

                for oid in order_ids_unik:
                    baris_order = df_semua[df_semua["order_id"] == oid]
                    first_row = baris_order.iloc[0]

                    total_order = pd.to_numeric(baris_order["subtotal"], errors="coerce").sum()

                    daftar_order.append({
                        "order_id": oid,
                        "nama_outlet": first_row.get("nama_outlet", ""),
                        "no_wa": first_row.get("no_wa", ""),
                        "alamat_pengiriman": first_row.get("alamat_pengiriman", ""),
                        "timestamp": first_row.get("timestamp", ""),
                        "baris_order": baris_order,
                        "total": total_order,
                        "terkirim": status_map.get(str(oid), False),
                    })

                if search_kw:
                    kw = search_kw.strip().lower()
                    daftar_order = [
                        d for d in daftar_order
                        if (kw in str(d["order_id"]).lower() or kw in str(d["nama_outlet"]).lower())
                    ]

                belum_dikirim = [d for d in daftar_order if not d["terkirim"]]
                sudah_dikirim = [d for d in daftar_order if d["terkirim"]]

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
                        d["order_id"], d["nama_outlet"], d["no_wa"], d["alamat_pengiriman"],
                        d["timestamp"], items_order, d["total"],
                    )

                    nomor_tujuan = format_no_wa(str(d["no_wa"]))

                    link_wa_admin = f"https://api.whatsapp.com/send?phone={nomor_tujuan}&text={quote(teks_nota_admin)}"

                    with st.container(border=True):
                        st.markdown(f"**{d['order_id']}** — {d['nama_outlet']}")

                        st.markdown(
                            '<div class="wg-admin-card-total">'
                            f"{d['timestamp']} · {format_rupiah(d['total'])} · {len(d['baris_order'])} item"
                            "</div>",
                            unsafe_allow_html=True,
                        )

                        st.markdown('<div class="wg-admin-actions">', unsafe_allow_html=True)

                        c1, c2 = st.columns(2, gap="small")

                        with c1:
                            st.link_button("Kirim WhatsApp", link_wa_admin, use_container_width=True)

                        with c2:
                            if not sudah:
                                if st.button("Tandai terkirim", key=f"tandai_{d['order_id']}", use_container_width=True):
                                    tandai_terkirim(worksheet_status, d["order_id"])
                                    st.rerun()
                            else:
                                if st.button("Batalkan tandai", key=f"batal_{d['order_id']}", use_container_width=True):
                                    batalkan_tandai(worksheet_status, d["order_id"])
                                    st.rerun()

                        st.markdown("</div>", unsafe_allow_html=True)

                with st.expander(f"Belum dikirim ({len(belum_dikirim)})", expanded=True):
                    if not belum_dikirim:
                        st.markdown('<div class="wg-admin-empty">Tidak ada pesanan yang belum dikirim.</div>', unsafe_allow_html=True)
                    else:
                        for d in belum_dikirim[:JUMLAH_TAMPIL]:
                            render_kartu_order(d, sudah=False)

                st.divider()

                with st.expander(f"Sudah dikirim ({len(sudah_dikirim)})", expanded=False):
                    if not sudah_dikirim:
                        st.markdown('<div class="wg-admin-empty">Belum ada yang ditandai terkirim.</div>', unsafe_allow_html=True)
                    else:
                        for d in sudah_dikirim[:JUMLAH_TAMPIL]:
                            render_kartu_order(d, sudah=True)

                st.divider()
                st.markdown("#### Rekapitulasi")

                total_pesanan_semua = len(daftar_order)
                total_nilai_semua = sum(d["total"] for d in daftar_order)

                rc1, rc2 = st.columns(2)
                rc1.metric("Total Pesanan", total_pesanan_semua)
                rc2.metric("Sudah Terkirim", len(sudah_dikirim))

                rc3, rc4 = st.columns(2)
                rc3.metric("Belum Terkirim", len(belum_dikirim))
                rc4.metric("Total Nilai", format_rupiah(total_nilai_semua))
