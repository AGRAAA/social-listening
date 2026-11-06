import pandas as pd
from pytrends.request import TrendReq
import time

class GTrendsKeywordPipeline:
    def __init__(self, hl='id-ID', tz=420):
        # Inisialisasi koneksi pytrends (tz=420 untuk WITA / disesuaikan, 360 untuk WIB)
        self.pytrend = TrendReq(hl=hl, tz=tz)
        
    def fetch_keyword_data(self, keyword, timeframe='today 3-m'):
        """
        Mengambil data Interest over Time dan Related Queries dari Google Trends.
        """
        print(f"[*] Menghubungkan ke Google Trends untuk keyword: '{keyword}'...")
        self.pytrend.build_payload([keyword], cat=0, timeframe=timeframe, geo='ID', gprop='')
        
        # 1. Ambil data minat waktu
        interest_df = self.pytrend.interest_over_time()
        if not interest_df.empty and 'isPartial' in interest_df.columns:
            interest_df = interest_df.drop(columns=['isPartial'])
            
        # 2. Ambil data related queries
        related_queries_dict = self.pytrend.related_queries()
        
        return interest_df, related_queries_dict.get(keyword, {})

    def structure_keywords(self, related_queries_dict):
        """
        Menyusun dan membersihkan kueri turunan (Rising & Top) untuk social listening.
        """
        structured_data = []
        
        # Proses Rising Queries (Biasanya indikator tren mendadak / pain points baru)
        rising = related_queries_dict.get('rising')
        if rising is not None and not rising.empty:
            rising['category_type'] = 'Rising Trend'
            structured_data.append(rising)
            
        # Proses Top Queries (Kueri populer stabil)
        top = related_queries_dict.get('top')
        if top is not None and not top.empty:
            top['category_type'] = 'Top Stable'
            structured_data.append(top)
            
        if not structured_data:
            return pd.DataFrame(columns=['query', 'value', 'category_type'])
            
        combined_df = pd.concat(structured_data, ignore_index=True)
        
        # Pembersihan Data (Data Cleaning)
        combined_df = combined_df.drop_duplicates(subset=['query'])
        combined_df['query'] = combined_df['query'].str.lower().str.strip()
        
        return combined_df

# --- Contoh Eksekusi ---
if __name__ == "__main__":
    # Inisialisasi pipeline
    pipeline = GTrendsKeywordPipeline(hl='id-ID', tz=360) # tz 360 untuk WIB (GMT+7)
    
    seed_keyword = "keripik pisang" # Contoh seed keyword
    
    try:
        # Ekstraksi data
        interest_time, related = pipeline.fetch_keyword_data(seed_keyword, timeframe='today 1-m')
        
        # Susun kata kunci
        clean_keywords_df = pipeline.structure_keywords(related)
        
        print("\n--- Hasil Struktur Kata Kunci dari Google Trends ---")
        print(clean_keywords_df.head(10))
        
        # Simpan ke CSV untuk tahap Social Listening berikutnya
        clean_keywords_df.to_csv("structured_gtrends_keywords.csv", index=False)
        print("\n[+] Berhasil menyimpan data terstruktur ke 'structured_gtrends_keywords.csv'")
        
    except Exception as e:
        print(f"[-] Terjadi kesalahan (kemungkinan rate limit Google): {e}")
