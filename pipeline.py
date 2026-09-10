import os
import re
import shutil
import pandas as pd
import pdfplumber

INPUT_DIR = "1_incoming_pdfs"
PROCESSED_DIR = "2_processed_pdfs"
OUTPUT_DIR = "3_normalized_excels"

# Klasörleri garantiye alalım (main.py'den bağımsız çalıştırılırsa diye)
os.makedirs(INPUT_DIR, exist_ok=True)
os.makedirs(PROCESSED_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

def normalize_value(val_str):
    if not isinstance(val_str, str):
        return val_str
    
    return val_str.strip()

def extract_from_pdf(pdf_path):
    extracted_data = []
    
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()
            for table in tables:
                if not table or len(table) < 2:
                    continue
                
                headers = table[0]
                if not headers: continue
                headers = [str(h).replace('\n', ' ').strip() if h else f"Col_{i}" for i, h in enumerate(headers)]
                
                for row in table[1:]:
                    if not row: continue
                    feature = str(row[0]).replace('\n', ' ').strip() if row[0] else ""
                    if not feature:
                        continue
                    
                    for i, val in enumerate(row[1:], start=1):
                        if i < len(headers):
                            model_name = headers[i]
                            if not model_name or model_name.startswith("Col_"):
                                continue
                                
                            raw_val = str(val).replace('\n', ' ').strip() if val else ""
                            if not raw_val: 
                                continue
                                
                            norm_val = normalize_value(raw_val)
                            
                            extracted_data.append({
                                "Model": model_name,
                                "Feature": feature,
                                "Normalized_Value": norm_val,
                                "Raw_Value": raw_val
                            })
    
    return extracted_data

def process_pdfs():
    processed_count = 0
    if not os.path.exists(INPUT_DIR):
        print(f"Error: Directory '{INPUT_DIR}' not found.")
        return processed_count

    files = [f for f in os.listdir(INPUT_DIR) if f.lower().endswith(".pdf")]
    
    for filename in files:
        pdf_path = os.path.join(INPUT_DIR, filename)
        print(f"[Pipeline] Processing {filename}...")
        
        data = extract_from_pdf(pdf_path)
        if not data:
            print(f"  -> Warning: No table data successfully extracted from {filename}")
            # İşlenemese de taşıyalım mı? Şimdilik data yoksa hata sayıp taşımayalım.
            continue
            
        df = pd.DataFrame(data)
        
        try:
            pivot_df = df.pivot_table(
                index='Model', 
                columns='Feature', 
                values='Normalized_Value', 
                aggfunc='first'
            ).reset_index()
            
            base_name = os.path.splitext(filename)[0]
            out_filename = f"{base_name}_excel.xlsx"
            out_path = os.path.join(OUTPUT_DIR, out_filename)
            
            pivot_df.to_excel(out_path, index=False)
            print(f"  -> Saved to: {out_path}")
            
            # İşlem başarıyla bitti, PDF'yi processed klasörüne taşı
            processed_path = os.path.join(PROCESSED_DIR, filename)
            shutil.move(pdf_path, processed_path)
            print(f"  -> Moved to: {processed_path}")
            processed_count += 1
            
        except Exception as e:
            print(f"  -> Error pivoting or saving data for {filename}: {e}")
            
    return processed_count

if __name__ == "__main__":
    process_pdfs()
