import csv
from io import StringIO

def parse_csv(file_content: str) -> tuple:
    """
    Parses CSV string content.
    Returns (columns: list[str], rows: list[list])
    """
    try:
        # Provide a fallback if content is bytes
        if isinstance(file_content, bytes):
            file_content = file_content.decode('utf-8', errors='replace')
            
        reader = csv.reader(StringIO(file_content))
        
        # Get headers
        columns = next(reader, [])
        if not columns:
            return [], []
            
        # Get rows
        rows = []
        for row in reader:
            if row: # Skip empty rows
                # Try to convert numeric strings to actual numbers for better charting
                processed_row = []
                for val in row:
                    val = val.strip()
                    try:
                        if '.' in val:
                            processed_row.append(float(val))
                        else:
                            processed_row.append(int(val))
                    except ValueError:
                        processed_row.append(val)
                rows.append(processed_row)
                
        return columns, rows
    except Exception as e:
        raise ValueError(f"Failed to parse CSV: {str(e)}")
