import os, re
from datetime import datetime, timedelta

root = 'D:/杰哥复盘数据'

def prev_trading_day(dt):
    """Get previous trading day (skip Sat/Sun)"""
    dt -= timedelta(days=1)
    while dt.weekday() >= 5:  # Sat=5, Sun=6
        dt -= timedelta(days=1)
    return dt

fixes = []

for acct in ['杰哥擒龙收评', '短线杰哥擒龙']:
    d = os.path.join(root, acct)
    for f in os.listdir(d):
        if not f.endswith('.html') and not f.endswith('.md'):
            continue
        m = re.match(r'(\d{4})(\d{2})(\d{2})_(.*)', f)
        if not m:
            continue
        prefix_y, prefix_m, prefix_d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        title = m.group(4)
        ext = os.path.splitext(f)[1]

        try:
            prefix_date = datetime(prefix_y, prefix_m, prefix_d)
        except:
            continue

        new_date = None
        reason = ''

        # Case 1: Title has embedded MMdd like "0809复盘" or "0816收评" or "0228周末"
        mmdd_match = re.match(r'(\d{2})(\d{2})(?:复盘|收评|收盘|盘前|午评|周末)', title)
        if mmdd_match:
            title_m, title_d = int(mmdd_match.group(1)), int(mmdd_match.group(2))
            # If title MMdd differs from filename MMdd
            if title_m != prefix_m or title_d != prefix_d:
                try:
                    candidate = datetime(prefix_y, title_m, title_d)
                    # Skip if MMdd points to weekend AND article is weekend review
                    # (Case 2 below will correctly map to Friday)
                    if candidate.weekday() >= 5 and '周末' in title:
                        pass
                    else:
                        new_date = candidate
                        reason = f'title has {title_m:02d}{title_d:02d} but prefix has {prefix_m:02d}{prefix_d:02d}'
                except:
                    pass

        # Case 2: Weekend article on Sat/Sun, should be Friday
        if not new_date and '周末' in title:
            if prefix_date.weekday() == 5:  # Saturday
                new_date = prev_trading_day(prefix_date)
                reason = 'Saturday weekend review -> previous Friday'
            elif prefix_date.weekday() == 6:  # Sunday
                new_date = prev_trading_day(prefix_date)
                reason = 'Sunday weekend review -> previous Friday'

        # Case 3: Any Sat/Sun non-weekend article (likely published after midnight)
        if not new_date and prefix_date.weekday() >= 5:
            # Check if MMdd in title matches a nearby weekday
            mm_in_title = re.search(r'(\d{2})(\d{2})(?:复盘|收评|盘前|午评)', title)
            if mm_in_title:
                t_m, t_d = int(mm_in_title.group(1)), int(mm_in_title.group(2))
                try:
                    candidate = datetime(prefix_y, t_m, t_d)
                    if candidate.weekday() < 5:  # Weekday
                        new_date = candidate
                        reason = f'Sat/Sun file but title indicates {t_m:02d}{t_d:02d}'
                except:
                    pass

        if new_date:
            new_prefix = new_date.strftime('%Y%m%d')
            # Remove duplicate MMdd from title if it matches
            new_title = title
            title_mmdd_match = re.match(r'(\d{4})(复盘|收评|收盘|盘前|午评|周末)', title)
            if title_mmdd_match:
                # Title starts with MMdd, remove old and use new
                pass  # Keep original title structure

            new_name = f'{new_prefix}_{title}'
            fixes.append((acct, f, new_name, reason))

# Apply fixes
print(f'共 {len(fixes)} 个文件需要修正日期\n')
for acct, old, new, reason in fixes:
    d = os.path.join(root, acct)
    src = os.path.join(d, old)
    dst = os.path.join(d, new)

    # Dedup: if target already exists (from previous rename), add suffix
    if os.path.exists(dst):
        prefix = new[:8]
        base = os.path.splitext(os.path.basename(old))[0]
        ext = os.path.splitext(old)[1]
        suffix = hash(old) % 10000
        new = f'{prefix}_{base}_{suffix:04d}{ext}'
        dst = os.path.join(d, new)
        if os.path.exists(dst):
            import random
            suffix = random.randint(10000, 99999)
            new = f'{prefix}_{base}_{suffix}{ext}'
            dst = os.path.join(d, new)

    os.rename(src, dst)
    print(f'  [{acct}] {old[:55]}')
    print(f'    -> {new[:60]}')
    print(f'    原因: {reason}')

print(f'\n修正完成: {len(fixes)} 个文件')
