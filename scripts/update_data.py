#!/usr/bin/env python3
"""每月自動更新 data/taipower.json（由 GitHub Actions 執行）。

資料來源：政府資料開放平臺，台灣電力公司
「住宅用戶每月平均用電度數及電費」https://data.gov.tw/dataset/17062

只更新「全台住宅平均用電」（avg、period、series）。
電價（rates）由人工核對後手動修改，這支程式不會動它。

抓不到或格式看不懂時，保留舊檔、不報錯，網站會繼續用原本的數字。
本機測試：python3 scripts/update_data.py --csv 某個下載好的.csv
"""
import csv, io, json, re, sys, datetime, urllib.request

DATASET = '17062'
API = 'https://data.gov.tw/api/v2/rest/dataset/' + DATASET
OUT = 'data/taipower.json'
UA = {'User-Agent': 'degrees-at-home-updater (GitHub Actions)'}


def get(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def find_csv_urls(obj, out):
    """Walk the API reply and collect anything that looks like a CSV download link."""
    if isinstance(obj, dict):
        fmt = str(obj.get('resourceFormat', '')).lower()
        for k, v in obj.items():
            if isinstance(v, str) and v.startswith('http') and (
                    'csv' in v.lower() or 'download' in k.lower() or fmt == 'csv'):
                out.append(v)
            else:
                find_csv_urls(v, out)
    elif isinstance(obj, list):
        for v in obj:
            find_csv_urls(v, out)
    return out


def decode(b):
    for enc in ('utf-8-sig', 'cp950', 'big5'):
        try:
            return b.decode(enc)
        except UnicodeDecodeError:
            pass
    return b.decode('utf-8', 'replace')


def parse_ym(text):
    """'113/06', '11306', '2024/06', '202406', '2024-06' -> '2024-06'"""
    nums = re.findall(r'\d+', str(text))
    if len(nums) >= 2:
        y, m = int(nums[0]), int(nums[1])
    elif len(nums) == 1 and len(nums[0]) in (5, 6):
        y, m = int(nums[0][:-2]), int(nums[0][-2:])
    else:
        return None
    if y < 1911:
        y += 1911
    if not (2000 <= y <= 2100 and 1 <= m <= 12):
        return None
    return '%04d-%02d' % (y, m)


def parse(text):
    rows = list(csv.reader(io.StringIO(text)))
    rows = [r for r in rows if any(c.strip() for c in r)]
    if len(rows) < 2:
        raise ValueError('CSV 是空的')
    head = [h.strip() for h in rows[0]]
    def col(*keys, avoid=('去年',)):
        for i, h in enumerate(head):
            if all(k in h for k in keys) and not any(a in h for a in avoid):
                return i
        return None
    c_date = col('日期') if col('日期') is not None else col('年月')
    c_kwh = col('平均用電')
    c_fee = col('電費')
    if c_date is None or c_kwh is None:
        raise ValueError('找不到欄位，表頭是：%s' % head)
    series = {}
    for r in rows[1:]:
        try:
            ym = parse_ym(r[c_date])
            kwh = float(str(r[c_kwh]).replace(',', ''))
        except (IndexError, ValueError):
            continue
        if not ym or not (100 <= kwh <= 1500):
            continue
        item = {'ym': ym, 'kwh': round(kwh, 1)}
        if c_fee is not None:
            try:
                item['fee'] = round(float(str(r[c_fee]).replace(',', '')))
            except (IndexError, ValueError):
                pass
        series[ym] = item
    out = [series[k] for k in sorted(series)]
    if len(out) < 6:
        raise ValueError('有效資料太少（%d 筆）' % len(out))
    return out


def summarise(series):
    last12 = series[-12:]
    summer = [x['kwh'] for x in last12 if int(x['ym'][5:]) in (6, 7, 8, 9)]
    other = [x['kwh'] for x in last12 if int(x['ym'][5:]) not in (6, 7, 8, 9)]
    if not summer or not other:
        raise ValueError('最近 12 個月缺夏月或非夏月資料')
    return {'s': round(sum(summer) / len(summer)), 'n': round(sum(other) / len(other))}, \
           {'from': last12[0]['ym'], 'to': last12[-1]['ym']}


def main():
    try:
        old = json.load(open(OUT, encoding='utf-8'))
    except Exception:
        old = {}
    try:
        if '--csv' in sys.argv:
            text = decode(open(sys.argv[sys.argv.index('--csv') + 1], 'rb').read())
        else:
            urls = find_csv_urls(json.loads(get(API)), [])
            if not urls:
                raise ValueError('API 回應裡找不到 CSV 連結')
            text, err = None, None
            for u in urls:
                try:
                    text = decode(get(u)); break
                except Exception as e:
                    err = e
            if text is None:
                raise ValueError('下載失敗：%s' % err)
        series = parse(text)
        avg, period = summarise(series)
    except Exception as e:
        print('::warning::這次沒有更新，保留舊資料。原因：%s' % e)
        return 0
    new = dict(old)
    new.update({'source': 'taipower-open-data', 'dataset': 'https://data.gov.tw/dataset/' + DATASET,
                'avg': avg, 'period': period, 'series': series[-36:]})
    if {k: v for k, v in new.items() if k != 'updated'} == {k: v for k, v in old.items() if k != 'updated'}:
        print('資料沒有變化')
        return 0
    new['updated'] = datetime.date.today().isoformat()
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(new, f, ensure_ascii=False, indent=2)
        f.write('\n')
    print('已更新：夏月 %s 度、非夏月 %s 度（%s～%s）' % (avg['s'], avg['n'], period['from'], period['to']))
    return 0


if __name__ == '__main__':
    sys.exit(main())
