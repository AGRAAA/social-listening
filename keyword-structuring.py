import pandas as pd
import re
import time
from pytrends.request import TrendReq

class MultiSeedGTrendsPipelineV5:
    def __init__(self, hl='id-ID', tz=360, sleep_delay=10):
        # Inisialisasi koneksi pytrends (tz=360 untuk WIB / GMT+7, sleep_delay ditingkatkan ke 10 detik)
        self.pytrend = TrendReq(hl=hl, tz=tz)
        self.sleep_delay = sleep_delay  
        
    def fetch_keyword_data(self, keyword, timeframe='today 12-m', geo='ID'):
        """
        Mengambil data mentah Top dan Rising Queries dari Google Trends untuk satu seed.
        """
        try:
            geo_label = geo if geo else "GLOBAL (Tanpa Batasan Wilayah)"
            print(f"[*] Menghubungkan ke Google Trends untuk seed: '{keyword}' (Geo: {geo_label})...")
            
            self.pytrend.build_payload([keyword], cat=0, timeframe=timeframe, geo=geo, gprop='')
            related_queries_dict = self.pytrend.related_queries()
            return related_queries_dict.get(keyword, {})
        except Exception as e:
            print(f"[-] Gagal mengambil data untuk seed '{keyword}': {e}")
            return {}

    def _detect_language_refined(self, query):
        """
        Heuristik deteksi bahasa berbasis batas kata (regex \b) dan sistem bobot (V4).
        """
        q = query.lower()
        
        id_domain = [
            'stok', 'persediaan', 'barang', 'gudang', 'selisih', 'pengelolaan', 
            'pencatatan', 'pencocokan', 'penyesuaian', 'sinkronisasi', 'ketidaksesuaian', 
            'kesalahan', 'duplikat', 'hilang', 'rusak', 'aplikasi', 'perusahaan', 
            'penjualan', 'pembelian', 'sistem'
        ]
        id_stop = ['adalah', 'dengan', 'untuk', 'yang']
        
        en_domain = [
            'inventory', 'discrepancy', 'mismatch', 'synchronization', 'reconciliation', 
            'warehouse', 'stocktaking', 'tracking', 'management', 'supply chain', 
            'duplicate', 'inaccurate', 'inconsistent', 'record', 'records', 
            'spreadsheet', 'manual', 'counting', 'adjustment', 'correction', 
            'overselling', 'understock', 'overstock', 'system'
        ]
        en_stop = ['the', 'with', 'for', 'and']
        
        id_score = 0
        en_score = 0
        
        for word in id_domain:
            if re.search(r'\b' + re.escape(word) + r'\b', q):
                id_score += 2
        for word in id_stop:
            if re.search(r'\b' + re.escape(word) + r'\b', q):
                id_score += 1
                
        for word in en_domain:
            if re.search(r'\b' + re.escape(word) + r'\b', q):
                en_score += 2
        for word in en_stop:
            if re.search(r'\b' + re.escape(word) + r'\b', q):
                en_score += 1
                
        if id_score > 0 and en_score == 0:
            return 'ID'
        elif en_score > 0 and id_score == 0:
            return 'EN'
        elif id_score > 0 and en_score > 0:
            if abs(id_score - en_score) <= 1:
                return 'MIXED'
            elif id_score > en_score:
                return 'ID'
            else:
                return 'EN'
        else:
            return 'UNCERTAIN'

    def _classify_contextual_relevance_strict(self, query):
        """
        Aturan ketat berbasis konteks: Wajib memiliki konteks inventaris/data terlebih dahulu.
        """
        q = query.lower()
        
        inventory_context_keywords = [
            'inventory', 'stok', 'stock', 'persediaan', 'gudang', 'warehouse', 
            'supply', 'chain', 'sku', 'barang', 'logistik', 'logistics', 'spreadsheet'
        ]
        
        has_inventory_context = any(re.search(r'\b' + re.escape(k) + r'\b', q) for k in inventory_context_keywords)
        
        if not has_inventory_context:
            return ('rejected', 'Tidak memiliki konteks inventaris, stok, atau supply chain (di luar domain riset)')
        
        approved_keywords = [
            'discrepancy', 'mismatch', 'synchronization', 'sync', 'selisih', 
            'error', 'duplicate', 'duplikat', 'adjust', 'correction', 'cleaning',
            'pencatatan', 'hilang', 'rusak', 'selisih stok', 'inaccurate', 'opname', 'manual'
        ]
        
        rejected_exclusions = [
            'knowledge', 'data science', 'machine learning', 'python', 'sql',
            'tutorial', 'pdf', 'jurnal', 'skripsi', 'course', 'sertifikasi', 'book',
            'laptop', 'work', 'visit', 'maldives', 'bake', 'cake', 'tourist', 'paris'
        ]
        
        if any(re.search(r'\b' + re.escape(exc) + r'\b', q) for exc in rejected_exclusions):
            return ('rejected', 'Mengandung istilah di luar ruang lingkup spesifik riset')
            
        if any(re.search(r'\b' + re.escape(app) + r'\b', q) for app in approved_keywords):
            return ('approved', 'Secara langsung berkaitan dengan masalah selisih stok, error data, atau sinkronisasi')
        else:
            return ('review', 'Berkaitan dengan inventaris/supply chain, tetapi belum cukup spesifik pada masalah data/mismatch')

    def process_single_seed_data(self, related_queries_dict, seed_keyword):
        """
        Memproses satu seed menjadi struktur DataFrame mentah.
        """
        top = related_queries_dict.get('top')
        rising = related_queries_dict.get('rising')
        
        if top is not None and not top.empty:
            top = top.rename(columns={'value': 'top_value'})
            top['query'] = top['query'].str.lower().str.strip()
            top['top_value'] = pd.to_numeric(top['top_value'], errors='coerce')
        else:
            top = pd.DataFrame(columns=['query', 'top_value'])
            
        if rising is not None and not rising.empty:
            rising = rising.rename(columns={'value': 'rising_value'})
            rising['query'] = rising['query'].str.lower().str.strip()
            
            def clean_rising_val(val):
                if str(val).lower() == 'breakout':
                    return 9999.0 
                try:
                    return float(val)
                except:
                    return pd.NA
                    
            rising['rising_value'] = rising['rising_value'].apply(clean_rising_val)
            rising['rising_value'] = pd.to_numeric(rising['rising_value'], errors='coerce')
        else:
            rising = pd.DataFrame(columns=['query', 'rising_value'])
            
        merged_df = pd.merge(top, rising, on='query', how='outer')
        
        # Metadata
        merged_df['seed_keyword'] = seed_keyword
        merged_df['problem_cluster'] = "Messy Data / Inventory Mismatch"
        merged_df['language'] = merged_df['query'].apply(self._detect_language_refined)
        
        relevance_results = merged_df['query'].apply(self._classify_contextual_relevance_strict)
        merged_df['relevance_status'] = [res[0] for res in relevance_results]
        merged_df['relevance_reason'] = [res[1] for res in relevance_results]
        
        merged_df['validation_status'] = 'pending'
        merged_df['x_search_ready'] = False 
        
        return merged_df

    def run_multi_seed_pipeline(self, seed_list, timeframe='today 12-m', geo='ID'):
        """
        Menjalankan pipeline secara iteratif untuk daftar multi-seed, 
        menggabungkan, dan melakukan deduplikasi lintas-seed (Kompatibel dengan semua versi Pandas).
        """
        all_dfs = []
        
        geo_label = geo if geo else "GLOBAL (Tanpa Batasan Wilayah)"
        print(f"=== MEMULAI MULTI-SEED GOOGLE TRENDS PIPELINE (Total Seed: {len(seed_list)} | Geo: {geo_label}) ===")
        
        for seed in seed_list:
            raw_data = self.fetch_keyword_data(seed, timeframe=timeframe, geo=geo)
            
            if raw_data and (raw_data.get('top') is not None or raw_data.get('rising') is not None):
                seed_df = self.process_single_seed_data(raw_data, seed_keyword=seed)
                if not seed_df.empty:
                    all_dfs.append(seed_df)
            else:
                print(f"[!] Peringatan: Tidak ada data valid yang diterima untuk seed '{seed}'.")
            
            # Jeda waktu aman untuk menghindari rate limit Google Trends
            time.sleep(self.sleep_delay)
            
        if not all_dfs:
            print("[-] TIDAK ADA DATA: Seluruh seed mengembalikan hasil kosong. Pertimbangkan untuk menggunakan geo='' (Global) jika seed berbahasa Inggris.")
            return pd.DataFrame()
            
        # Gabungkan seluruh DataFrame dari semua seed
        combined_master_df = pd.concat(all_dfs, ignore_index=True)
        
        print(f"\n[*] Menggabungkan data... Total baris sebelum deduplikasi: {len(combined_master_df)}")
        
        # --- DEDUPLIKASI LINTAS-SEED (Aman untuk berbagai versi pandas) ---
        def aggregate_sources(group):
            seeds = sorted(group['seed_keyword'].unique())
            return ", ".join(seeds)
            
        aggregated_seeds = combined_master_df.groupby('query').apply(aggregate_sources).reset_index()
        aggregated_seeds = aggregated_seeds.rename(columns={0: 'all_origin_seeds'})
        
        # Ambil nilai maksimum untuk kolom numerik jika muncul di multiple seed
        numeric_agg = combined_master_df.groupby('query').agg({
            'top_value': 'max',
            'rising_value': 'max',
            'language': 'first',
            'relevance_status': 'first',
            'relevance_reason': 'first',
            'problem_cluster': 'first',
            'validation_status': 'first',
            'x_search_ready': 'first'
        }).reset_index()
        
        # Gabungkan kembali hasil agregasi metrik dengan daftar seluruh seed asal
        final_master_df = pd.merge(numeric_agg, aggregated_seeds, on='query')
        
        # Atur urutan kolom standar
        final_columns = [
            'query', 'top_value', 'rising_value', 'language',
            'relevance_status', 'relevance_reason', 
            'all_origin_seeds', 'problem_cluster', 
            'validation_status', 'x_search_ready'
        ]
        final_master_df = final_master_df[[col for col in final_columns if col in final_master_df.columns]]
        
        # Urutkan prioritas status (approved di atas) dan nilai top_value tertinggi
        status_order = {'approved': 1, 'review': 2, 'rejected': 3}
        final_master_df['sort_key'] = final_master_df['relevance_status'].map(status_order)
        final_master_df = final_master_df.sort_values(by=['sort_key', 'top_value'], ascending=[True, False]).drop(columns=['sort_key']).reset_index(drop=True)
        
        print(f"[+] Total baris unik setelah deduplikasi lintas-seed: {len(final_master_df)}")
        return final_master_df

    def simulate_human_validation(self, df, approved_queries_to_validate):
        """
        Mensimulasikan validasi manual dan mengaktifkan x_search_ready.
        """
        df_validated = df.copy()
        
        mask = df_validated['query'].isin(approved_queries_to_validate) & (df_validated['relevance_status'] == 'approved')
        
        df_validated.loc[mask, 'validation_status'] = 'manually_validated'
        
        df_validated['x_search_ready'] = df_validated.apply(
            lambda row: True if (
                row['relevance_status'] == 'approved' and 
                row['validation_status'] == 'manually_validated' and 
                row['language'] in ['ID', 'EN']
            ) else False,
            axis=1
        )
        
        print(f"\n[+] Simulasi Validasi Manual Selesai: {mask.sum()} kueri telah disetujui.")
        return df_validated

# --- Eksekusi Utama Program ---
if __name__ == "__main__":
    research_seeds = [
        "inventory discrepancy",
        "stock mismatch",
        "stock discrepancy",
        "inventory synchronization",
        "manual stock update",
        "inventory data accuracy",
        "spreadsheet inventory",
        "selisih stok"
    ]
    
    # Catatan: Gunakan geo='ID' untuk wilayah Indonesia, 
    # atau ubah menjadi geo='' jika ingin menguji pencarian secara global tanpa batasan wilayah.
    TARGET_GEO = '' 
    
    # Inisialisasi pipeline V5 (sleep_delay diset 10 detik untuk keamanan rate limit)
    pipeline = MultiSeedGTrendsPipelineV5(hl='id-ID', tz=360, sleep_delay=10)
    
    # Jalankan proses multi-seed
    master_matrix_df = pipeline.run_multi_seed_pipeline(research_seeds, timeframe='today 12-m', geo=TARGET_GEO)
    
    if not master_matrix_df.empty:
        display_preview = master_matrix_df.copy()
        display_preview['top_value'] = display_preview['top_value'].fillna('—')
        display_preview['rising_value'] = display_preview['rising_value'].fillna('—')
        
        print("\n--- Preview Master Matriks Multi-Seed ---")
        print(display_preview[['query', 'top_value', 'rising_value', 'relevance_status', 'validation_status', 'x_search_ready', 'all_origin_seeds']].head(15).to_string(index=False))
        
        # Simulasi validasi manual
        sample_approved_from_review = [
            'inventory discrepancy', 
            'stock mismatch', 
            'selisih stok', 
            'manual stock update'
        ]
        
        validated_master_df = pipeline.simulate_human_validation(master_matrix_df, sample_approved_from_review)
        
        # Simpan hasil akhir
        output_file = "multi_seed_inventory_master_matrix.csv"
        validated_master_df.to_csv(output_file, index=False)
        print(f"\n[+] Master matriks berhasil disimpan ke '{output_file}'")
        
        # Ekstrak daftar kueri yang siap dicari di X
        x_ready_list = validated_master_df[validated_master_df['x_search_ready'] == True]['query'].tolist()
        print(f"\n[🎯] DAFTAR FINAL SIAP X-SEARCH ({len(x_ready_list)} kueri):")
        for q in x_ready_list:
            print(f"   - {q}")
    else:
        print("\n[!] Saran Pengujian: Jika data tetap kosong, ubah variabel `TARGET_GEO = 'ID'` di bagian bawah skrip menjadi `TARGET_GEO = ''` (Global) karena volume penelusuran domestik untuk istilah bahasa Inggris tertentu di Indonesia mungkin terlalu kecil.")