import requests
from datetime import datetime
from tqdm import tqdm
import os

def update_dataset_if_newer(dataset_slug, last_processed_date_str):
    api_url = f"https://www.data.gouv.fr/api/1/datasets/{dataset_slug}/"
    
    # Parse your provided date (assuming ISO format YYYY-MM-DD)
    last_processed = datetime.fromisoformat(last_processed_date_str.replace('Z', '+00:00'))
    
    print(f"Checking for updates: {dataset_slug}...")
    
    try:
        response = requests.get(api_url)
        response.raise_for_status()
        data = response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching metadata: {e}")
        return False
    
    # 1. Check the last update date of the dataset
    remote_update_str = data.get("last_update")
    remote_update = datetime.fromisoformat(remote_update_str.replace('Z', '+00:00'))
    
    if remote_update <= last_processed:
        print(f"No new updates. Remote version ({remote_update}) is not newer than your date.")
        return False

    print(f"New version detected! Remote update: {remote_update}")
    
    # 2. Find the Parquet resource
    resource = next((r for r in data['resources'] if r['format'] == 'parquet'), None)
    if not resource:
        print("No Parquet resource found in this dataset.")
        return False
        
    download_url = resource['url']
    file_name = resource['title']
    
    # Check if we should use the content-length from the API or the request headers
    total_size = int(resource.get('filesize') or 0)

    # 3. Stream the download with progress bar
    print(f"Starting download: {file_name}")
    
    try:
        with requests.get(download_url, stream=True) as r:
            r.raise_for_status()
            
            # Update total_size from headers if API metadata was missing it
            if total_size == 0:
                total_size = int(r.headers.get('content-length', 0))

            # Progress bar setup
            # unit='iB' uses KiB, MiB, GiB; unit_scale=True auto-scales the units
            with tqdm(total=total_size, unit='iB', unit_scale=True, desc=file_name) as pbar:
                with open(file_name, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=1024 * 1024): # 1MB chunks
                        if chunk:
                            f.write(chunk)
                            pbar.update(len(chunk))
                            
        print(f"\nSuccessfully downloaded: {file_name}")
        return True
        
    except Exception as e:
        print(f"\nAn error occurred during download: {e}")
        # Clean up partial file if download failed
        if os.path.exists(file_name):
            os.remove(file_name)
        return False

# --- Usage ---
if __name__ == "__main__":
    slug = "donnees-financieres-detaillees-des-entreprises-format-parquet"
    
    # Example: If your last run was Feb 1st, 2026, it will download the Feb 10th file.
    # If you set this to '2026-02-15', it will skip the download.
    my_last_update = "2026-02-15T00:00:00+00:00"

    update_dataset_if_newer(slug, my_last_update)