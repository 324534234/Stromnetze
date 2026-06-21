"""
Konvertiert xlsx-Dateien vom strikten OOXML-Format (conformance='strict')
in das transitionale Format, das von openpyxl/pandas korrekt gelesen wird.

Verwendung:
    python convert_pv_xlsx.py            # konvertiert alle .xlsx im PV/-Ordner
    python convert_pv_xlsx.py --dry-run  # zeigt nur, welche Dateien betroffen wären
"""

import zipfile
import io
import os
import sys
import glob

# Namespace-Ersetzungen: Strict OOXML → Transitional OOXML
REPLACEMENTS = {
    b'http://purl.oclc.org/ooxml/spreadsheetml/main':
        b'http://schemas.openxmlformats.org/spreadsheetml/2006/main',
    b'http://purl.oclc.org/ooxml/officeDocument/relationships':
        b'http://schemas.openxmlformats.org/officeDocument/2006/relationships',
    b'http://purl.oclc.org/ooxml/drawingml/2006/main':
        b'http://schemas.openxmlformats.org/drawingml/2006/main',
    b' conformance="strict"': b'',
}


def is_strict_xlsx(path: str) -> bool:
    """Prüft ob eine xlsx-Datei den strikten Namespace verwendet."""
    try:
        with zipfile.ZipFile(path, 'r') as z:
            if 'xl/workbook.xml' in z.namelist():
                data = z.read('xl/workbook.xml')
                return b'purl.oclc.org/ooxml' in data
    except Exception:
        pass
    return False


def convert_strict_to_transitional(path: str) -> None:
    """Konvertiert eine xlsx-Datei in-place von strict nach transitional."""
    buf = io.BytesIO()
    with zipfile.ZipFile(path, 'r') as zin, \
         zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            # Nur XML- und Relationship-Dateien anpassen
            if item.filename.endswith('.xml') or item.filename.endswith('.rels'):
                for old, new in REPLACEMENTS.items():
                    data = data.replace(old, new)
            zout.writestr(item, data)

    with open(path, 'wb') as f:
        f.write(buf.getvalue())


def main():
    dry_run = '--dry-run' in sys.argv

    # Alle xlsx-Dateien im PV/-Ordner suchen
    search_paths = [
        'PV/*.xlsx',
        'PV/**/*.xlsx',
    ]

    files = []
    for pattern in search_paths:
        files.extend(glob.glob(pattern, recursive=True))

    if not files:
        print("Keine .xlsx-Dateien im PV/-Ordner gefunden.")
        print("Skript aus dem Verzeichnis ausführen, das den PV/-Ordner enthält.")
        return

    strict_files = [f for f in files if is_strict_xlsx(f)]

    if not strict_files:
        print(f"Alle {len(files)} Datei(en) bereits im transitonalen Format – nichts zu tun.")
        return

    print(f"Gefunden: {len(strict_files)} Datei(en) im strikten OOXML-Format:\n")
    for f in strict_files:
        print(f"  {f}")

    if dry_run:
        print("\n[Dry-run] Keine Änderungen vorgenommen.")
        return

    print()
    for f in strict_files:
        try:
            convert_strict_to_transitional(f)
            print(f"  ✓  {f}")
        except Exception as e:
            print(f"  ✗  {f}  →  Fehler: {e}")

    print(f"\nFertig. {len(strict_files)} Datei(en) konvertiert.")
    print("pd.read_excel() sollte jetzt ohne Warnung funktionieren.")


if __name__ == '__main__':
    main()