import streamlit as st
import pandas as pd
from datetime import datetime
import io
import gspread
from google.oauth2.service_account import Credentials
from PIL import Image, ImageDraw, ImageFont

# ============ KONFIGURASI ============
NAMA_WORKSHEET_PESANAN = "Pesanan"  # nama tab di Google Sheet untuk simpan pesanan
NAMA_WORKSHEET_PRODUK = "Produk"    # nama tab di Google Sheet untuk data produk

st.set_page_config(page_title="Form Pesanan Outlet", page_icon="🛒", layout="centered")


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

if "last_receipt" not in st.session_state:
    st.session_state.last_receipt = None
if "last_receipt_name" not in st.session_state:
    st.session_state.last_receipt_name = None
if "show_success" not in st.session_state:
    st.session_state.show_success = False


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


def build_receipt_lines(nama_outlet, no_wa, alamat_pengiriman, timestamp, detail_pesanan, total_harga):
    lines = [
        ("title", "STRUK PEMESANAN OUTLET MR FISIK"),
        ("sep", ""),
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


def build_receipt_image(nama_outlet, no_wa, alamat_pengiriman, timestamp, detail_pesanan, total_harga):
    lines = build_receipt_lines(nama_outlet, no_wa, alamat_pengiriman, timestamp, detail_pesanan, total_harga)

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
st.title("🛒 Form Pemesanan Outlet MR\u00A0Fisik")
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
        qty = st.session_state.qty.get(kode, 0)

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
                        "➖", key=f"minus_{kode}", on_click=kurang, args=(kode,),
                        disabled=(harga == 0), use_container_width=True,
                    )
                with c_qty:
                    st.number_input(
                        "Qty", min_value=0, step=1, value=qty,
                        key=f"qtyinput_{kode}", on_change=ubah_qty_manual, args=(kode,),
                        disabled=(harga == 0), label_visibility="collapsed",
                    )
                with c_plus:
                    st.button(
                        "➕", key=f"plus_{kode}", on_click=tambah, args=(kode,),
                        disabled=(harga == 0), use_container_width=True,
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
        rows_to_append = [
            [
                timestamp,
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
                nama_outlet, no_wa, alamat_pengiriman, timestamp, detail_pesanan, total_harga
            )
            nama_file_aman = nama_outlet.strip().replace(" ", "_")
            st.session_state.last_receipt_name = (
                f"struk_{nama_file_aman}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            )
            st.session_state.show_success = True

            for kode in st.session_state.qty:
                st.session_state.qty[kode] = 0
            st.rerun()
        except Exception as e:
            st.error("Gagal menyimpan ke Google Sheets.")
            st.exception(e)

# ============ STATUS SUKSES + DOWNLOAD STRUK ============
if st.session_state.show_success and st.session_state.last_receipt:
    st.success("✅ Terima kasih! Pesanan Anda sudah berhasil tersimpan.")
    st.image(st.session_state.last_receipt, caption="Preview Struk Pesanan", width=340)
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
