import urllib.request
import re

url = "https://gong2.nso.edu/HA/haf/202405/20240510/"
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
with urllib.request.urlopen(req, timeout=10) as resp:
    content = resp.read().decode('utf-8', errors='ignore')
    links = re.findall(r'href=[\'"]([^\'"]+)[\'"]', content)
    files = [l for l in links if l.endswith('.fits.fz') or l.endswith('.fits')]
    print(f"Total FITS files on 20240510: {len(files)}")
    print("Sample FITS files:", files[:5])

