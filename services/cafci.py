import unicodedata

import requests
import pandas as pd
import json
import io

def normalize_string(text: str) -> str:
    """Removes accents and converts to lowercase."""
    if not text:
        return ""
    # Normalize to decompose combined characters (like 'ó' to 'o' + '´')
    text = unicodedata.normalize('NFD', text)
    # Filter out non-spacing mark characters (the accents)
    text = "".join(c for c in text if unicodedata.category(c) != 'Mn')
    return text.lower()

def get_cafci_data_list(file_buffer):
    """Parses Excel and returns a list of dictionaries (no file saving)."""
    file_buffer.seek(0)
    df = pd.read_excel(file_buffer, header=11, usecols=[0, 1, 5, 18, 20], engine='openpyxl')
    df.columns = ['nombre', 'moneda', 'precio_actual', 'codigo_cnv', 'codigo_cafci']
    
    result_list = []
    for _, row in df.iterrows():
        try:
            if row.isnull().any(): continue
            result_list.append({
                "nombre": str(row['nombre']).strip(),
                "moneda": str(row['moneda']).strip(),
                "precio_actual": float(row['precio_actual']) / 1000,  # Convert from thousands
                "codigo_cnv": int(row['codigo_cnv']),
                "codigo_cafci": int(row['codigo_cafci'])
            })
        except: continue
    return result_list

def download_cafci_to_memory():
    """
    Downloads the CAFCI file and returns it as a BytesIO object (in-memory).
    """
    url = "https://api.pub.cafci.org.ar/pb_get?d=1778263751866"
    
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        
        # 1. Wrap the binary content in a BytesIO object
        file_in_memory = io.BytesIO(response.content)
        
        # 2. Calculate size from the buffer
        file_size_kb = len(response.content) / 1024
        
        return {
            "success": True,
            "message": "File downloaded to memory successfully.",
            "size_kb": round(file_size_kb, 2),
            "file": file_in_memory  # This is your 'virtual' file
        }
        
    except Exception as e:
        return {"success": False, "message": str(e)}
    