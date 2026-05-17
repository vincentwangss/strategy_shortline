import os, re, json
from datetime import datetime, timedelta

root = 'D:/杰哥复盘数据'

# Rule: if published before 4AM of next day, use previous trading day's date
# For stock market articles: the date should reflect the market day being discussed

# Check all files - look for signs of wrong dates (Saturday dates, 1-day-off patterns)
# "周末复盘" assigned SAT dates (e.g. 20220723).
# Should these be Friday dates since they review Friday's market?

print('Checking files that might have wrong dates...')
print()

issues = []

for acct in ['杰哥擒龙收评', '短线杰哥擒龙']:
    d = os.path.join(root, acct)
    for f in os.listdir(d):
        if not f.endswith('.html') and not f.endswith('.md'):
            continue
        m = re.match(r'(\d{4})(\d{2})(\d{2})_(.*)', f)
        if not m:
            continue
        y, mo, dd, title = int(m.group(1)), int(m.group(2)), int(m.group(3)), m.group(4)

        # Files on Saturday - weekend review articles should be dated Friday
        try:
            dt = datetime(y, mo, dd)
        except:
            continue
        weekday = dt.weekday()  # 0=Mon, 6=Sun

        if weekday == 5:  # Saturday
            # Check if this is a weekend review or daily article
            if '周末' in title:
                # Weekend review on Saturday - should it be Friday?
                prev_day = dt - timedelta(days=1)
                issues.append((acct, f, f'Saturday weekend review, should be {prev_day.strftime("%Y%m%d")} (Friday)'))
            else:
                issues.append((acct, f, f'Saturday non-weekend article, unusual'))

        if weekday == 6:  # Sunday
            if '周末' in title:
                prev_friday = dt - timedelta(days=2)
                issues.append((acct, f, f'Sunday weekend review, should be {prev_friday.strftime("%Y%m%d")} (Friday)'))
            else:
                prev_friday = dt - timedelta(days=2)
                issues.append((acct, f, f'Sunday article, unusual'))

for acct, f, reason in issues:
    print(f'  [{acct}] {f[:70]}')
    print(f'    -> {reason}')
print(f'\n共 {len(issues)} 个可能日期异常的文件')
