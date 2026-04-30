import os
import time
import requests

URL = "https://www.data.gouv.fr/fr/datasets/r/c4ac8f98-2c97-4417-9070-0cbb9de03875"
OUTFILE = "export-detail-bilan.parquet"
PART = OUTFILE + ".part"

TIMEOUT = (10, 1800)          # (connect, read)
CHUNK_SIZE = 1024 * 1024      # 1 MB
MAX_RETRIES = 20
SLEEP_BETWEEN = 3

def parquet_magic_ok(path: str) -> bool:
    if not os.path.exists(path) or os.path.getsize(path) < 8:
        return False
    with open(path, "rb") as f:
        head = f.read(4)
        f.seek(-4, os.SEEK_END)
        tail = f.read(4)
    print("🔎 Header:", head, "| Footer:", tail)
    return head == b"PAR1" and tail == b"PAR1"

def get_expected_size(url: str) -> int | None:
    # HEAD n'est pas toujours supporté -> fallback GET headers
    try:
        r = requests.head(url, allow_redirects=True, timeout=TIMEOUT)
        if r.status_code >= 400:
            raise RuntimeError("HEAD failed")
        cl = r.headers.get("Content-Length")
        return int(cl) if cl else None
    except Exception:
        r = requests.get(url, stream=True, allow_redirects=True, timeout=TIMEOUT, headers={"Accept-Encoding": "identity"})
        r.raise_for_status()
        cl = r.headers.get("Content-Length")
        r.close()
        return int(cl) if cl else None

def download_with_resume(url: str, outfile: str):
    expected = get_expected_size(url)
    if expected:
        print(f"📏 Taille attendue (Content-Length): {expected/1024/1024:.0f} MB")
    else:
        print("⚠️ Pas de Content-Length fourni (on fera au mieux).")

    downloaded = os.path.getsize(PART) if os.path.exists(PART) else 0
    if downloaded:
        print(f"↩️ Reprise à {downloaded/1024/1024:.0f} MB (fichier .part existant)")

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            headers = {"Accept-Encoding": "identity"}
            if downloaded:
                headers["Range"] = f"bytes={downloaded}-"

            with requests.get(url, stream=True, allow_redirects=True, timeout=TIMEOUT, headers=headers) as r:
                # 206 = partial content, 200 = full (si serveur ignore Range)
                r.raise_for_status()

                mode = "ab" if (downloaded and r.status_code == 206) else "wb"
                if mode == "wb":
                    downloaded = 0  # on repart de zéro si pas de reprise réelle

                with open(PART, mode) as f:
                    for chunk in r.iter_content(chunk_size=CHUNK_SIZE):
                        if not chunk:
                            continue
                        f.write(chunk)
                        downloaded += len(chunk)

                        if expected:
                            pct = downloaded * 100 / expected
                            print(f"➡️ {downloaded/1024/1024:.0f} MB / {expected/1024/1024:.0f} MB ({pct:.2f}%)")
                        else:
                            print(f"➡️ {downloaded/1024/1024:.0f} MB")

            # Vérif taille
            if expected and downloaded < expected:
                raise IOError(f"Téléchargement incomplet: {downloaded} < {expected}")

            os.replace(PART, outfile)
            print("✅ Téléchargement terminé:", outfile)
            print("📦 Taille finale (GB):", os.path.getsize(outfile) / 1024**3)
            return

        except Exception as e:
            print(f"❌ Tentative {attempt}/{MAX_RETRIES} échouée:", repr(e))
            print(f"🧩 Taille .part actuelle: {downloaded/1024/1024:.0f} MB")
            time.sleep(SLEEP_BETWEEN)

    raise RuntimeError("Trop d'échecs réseau. Le téléchargement n'a pas pu être complété.")

if __name__ == "__main__":
    download_with_resume(URL, OUTFILE)
    print("\n🧪 Vérification Parquet...")
    if parquet_magic_ok(OUTFILE):
        print("✅ Parquet VALIDE (PAR1 au début et à la fin)")
    else:
        print("❌ Parquet invalide: footer manquant → fichier encore tronqué.")