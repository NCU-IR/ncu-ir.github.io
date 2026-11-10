# 每天跑一次（GitHub Actions）：讀辦公室雲端檔 → 抓每張圖的發佈更新日、點閱數 → 寫出 meta.js、data.js
#   meta.js：點閱數與日期（網頁每次都用）
#   data.js：雲端檔的備份（讀不到雲端檔時網頁改用它）
# 抓不到的圖沿用上次的數字，不會變成 0
import csv, datetime, io, json, os, re, time, urllib.request
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHEET = 'https://docs.google.com/spreadsheets/d/10i7yVwZtTe_0oWZVRWAtChd77O3TVaED/export?format=csv'
HIDE = {'其他', '高教深耕', '世界大學排名'}
UA = {'User-Agent': 'Mozilla/5.0'}


def get(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30).read()


def load_js(name):
    try:
        s = open(os.path.join(ROOT, name), encoding='utf-8').read()
        return json.loads(s[s.index('=') + 1:].strip().rstrip(';'))
    except (OSError, ValueError):
        return None


def day(ms):
    return datetime.datetime.fromtimestamp(ms / 1000, datetime.timezone(datetime.timedelta(hours=8))).strftime('%Y-%m-%d') if ms else ''


def fetch_meta(repo):
    for _ in range(3):
        try:
            d = json.loads(get(f'https://public.tableau.com/profile/api/single_workbook/{repo}'))
            return repo, {'date': day(d.get('lastPublishDate')), 'views': int(d.get('viewCount') or 0)}
        except Exception:
            time.sleep(2)
    return repo, None


rows = list(csv.DictReader(io.StringIO(get(SHEET).decode('utf-8'))))
items = []
for r in rows:
    cat = (r['分類'] or '').strip()
    m = re.search(r'/views/([^/]+)/([^?]+)', r['網址'] or '')
    if not cat or cat in HIDE or not m:
        continue
    w, h = [int(x) for x in (r['尺寸'] or '1000×827').split('×')]
    items.append(dict(id=m.group(1), sheet=m.group(2), w=w, h=h,
                      group='校際比較' if cat.startswith('校際_') else cat, sub=cat[3:] if cat.startswith('校際_') else '',
                      title=r['網頁表冊名稱'].strip(), short=(r['網頁表冊名稱_簡稱'] or r['網頁表冊名稱']).strip()))

old = load_js('meta.js') or {}
# 並行數壓低，避免被 Tableau 擋（2026-10-20 曾因此抓到一堆 1×1 空白圖）
with ThreadPoolExecutor(4) as ex:
    fresh = dict(ex.map(fetch_meta, sorted({i['id'] for i in items})))
meta = {k: v or old.get(k, {'date': '', 'views': 0}) for k, v in fresh.items()}
for i in items:
    i.update(meta[i['id']])

with open(os.path.join(ROOT, 'meta.js'), 'w', encoding='utf-8') as f:
    f.write('// 程式產生，勿手改（GitHub Actions 每天更新）\nconst META = ' + json.dumps(meta, ensure_ascii=False) + ';\n')
with open(os.path.join(ROOT, 'data.js'), 'w', encoding='utf-8') as f:
    f.write('// 程式產生，勿手改（雲端檔的備份）\nvar CHARTS = ' + json.dumps(items, ensure_ascii=False, indent=0) + ';\n')
print(f'{len(items)} 張圖；點閱數抓到 {sum(v is not None for v in fresh.values())}/{len(fresh)}')
