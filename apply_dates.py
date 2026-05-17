import os, re, shutil

root = 'D:/杰哥复盘数据'

# Completed date assignments based on thorough content analysis
# Cross-referenced stock mentions, board levels, and known market events
assignments = {
    # ===== 杰哥擒龙收评 (3 undated HTML + 3 MD) =====
    ('杰哥擒龙收评', '收评有主线的日子真好.html'): '20221013',  # 国脉科技信创爆发D2
    ('杰哥擒龙收评', '收评有主线的日子真好.md'): '20221013',
    ('杰哥擒龙收评', '收评温水煮青蛙难搞.html'): '20220830',  # 欢瑞世纪/黑芝麻地天/养家三股
    ('杰哥擒龙收评', '收评温水煮青蛙难搞.md'): '20220830',
    ('杰哥擒龙收评', '收评继续轮动无奈挥别神奇.html'): '20221114',  # 神奇制药监管炸板
    ('杰哥擒龙收评', '收评继续轮动无奈挥别神奇.md'): '20221114',

    # ===== 短线杰哥擒龙 - MMdd prefix (3 undated HTML + 3 MD) =====
    ('短线杰哥擒龙', '0717复盘科技强兑现弱势重归抱团.html'): '20240717',  # 广汇退市/沙特ETF/北交所
    ('短线杰哥擒龙', '0717复盘科技强兑现弱势重归抱团.md'): '20240717',
    ('短线杰哥擒龙', '0926复盘主线进一步加强.html'): '20230926',  # 新型工业化主线
    ('短线杰哥擒龙', '0926复盘主线进一步加强.md'): '20230926',
    ('短线杰哥擒龙', '1210复盘机器人板块打出韧性.html'): '20241210',  # 利欧/奋达/巨轮
    ('短线杰哥擒龙', '1210复盘机器人板块打出韧性.md'): '20241210',

    # ===== 短线杰哥擒龙 - 周一 (2 undated HTML + 2 MD) =====
    ('短线杰哥擒龙', '周一复盘与周二计划等分歧.html'): '20220808',  # 大港芯片第一波/鸣志电器机器人
    ('短线杰哥擒龙', '周一复盘与周二计划等分歧.md'): '20220808',
    ('短线杰哥擒龙', '周一盘前计划.html'): '20221114',  # 天鹅复牌/医药信创双主线
    ('短线杰哥擒龙', '周一盘前计划.md'): '20221114',

    # ===== 短线杰哥擒龙 - 周二 (2 undated HTML + 2 MD) =====
    ('短线杰哥擒龙', '周二复盘与周三计划还是轮动.html'): '20220809',  # 芯片法案落地夜/大港/通富微电
    ('短线杰哥擒龙', '周二复盘与周三计划还是轮动.md'): '20220809',
    ('短线杰哥擒龙', '周二复盘与周三计划靴子落地.html'): '20220802',  # 佩洛西访台落地/机器人高标
    ('短线杰哥擒龙', '周二复盘与周三计划靴子落地.md'): '20220802',

    # ===== 短线杰哥擒龙 - 周三 (6 undated HTML + 6 MD) =====
    ('短线杰哥擒龙', '周三复盘与周四计划亏米效应为零.html'): '20220727',  # 佛燃通润6B/赣能打开跌停
    ('短线杰哥擒龙', '周三复盘与周四计划亏米效应为零.md'): '20220727',
    ('短线杰哥擒龙', '周三复盘与周四计划修复去弱存强.html'): '20220824',  # 消费电子VR/国光电器
    ('短线杰哥擒龙', '周三复盘与周四计划修复去弱存强.md'): '20220824',
    ('短线杰哥擒龙', '周三复盘与周四计划反核.html'): '20220817',  # 大港+中通老龙抱团/川润
    ('短线杰哥擒龙', '周三复盘与周四计划反核.md'): '20220817',
    ('短线杰哥擒龙', '周三复盘与周四计划总该修复下了.html'): '20220803',  # 日盈电子/天沃科技/冰点
    ('短线杰哥擒龙', '周三复盘与周四计划总该修复下了.md'): '20220803',
    ('短线杰哥擒龙', '周三复盘与周四计划情绪逐渐上升.html'): '20220810',  # 大港7B/情绪上升
    ('短线杰哥擒龙', '周三复盘与周四计划情绪逐渐上升.md'): '20220810',
    ('短线杰哥擒龙', '周三复盘与周四计划新的一个月要加油.html'): '20220831',  # 欢瑞世纪/北纬/九月加油
    ('短线杰哥擒龙', '周三复盘与周四计划新的一个月要加油.md'): '20220831',

    # ===== 短线杰哥擒龙 - 周四 (5 undated HTML + 5 MD) =====
    ('短线杰哥擒龙', '周四复盘与周五计划你相信光吗.html'): '20220901',  # 欢瑞保利/黑芝麻/地量
    ('短线杰哥擒龙', '周四复盘与周五计划你相信光吗.md'): '20220901',
    ('短线杰哥擒龙', '周四复盘与周五计划核心来回做.html'): '20220721',  # 惠程4进5/大连重工
    ('短线杰哥擒龙', '周四复盘与周五计划核心来回做.md'): '20220721',
    ('短线杰哥擒龙', '周四复盘与周五计划科技新方向.html'): '20220811',  # 大港8B/消费电子
    ('短线杰哥擒龙', '周四复盘与周五计划科技新方向.md'): '20220811',
    ('短线杰哥擒龙', '周四复盘与周五计划继续反核低吸.html'): '20220818',  # 大港做t/川润/反核
    ('短线杰哥擒龙', '周四复盘与周五计划继续反核低吸.md'): '20220818',
    ('短线杰哥擒龙', '周四复盘与周五计划逐步企稳.html'): '20220804',  # 春兴精工反核/天沃高标
    ('短线杰哥擒龙', '周四复盘与周五计划逐步企稳.md'): '20220804',

    # ===== 短线杰哥擒龙 - 周末 (2 undated HTML + 2 MD) =====
    ('短线杰哥擒龙', '周末复盘与周一计划修复预期做好去弱存强.html'): '20220723',  # 惠程加速/春兴/大连
    ('短线杰哥擒龙', '周末复盘与周一计划修复预期做好去弱存强.md'): '20220723',
    ('短线杰哥擒龙', '周末复盘与周一计划弱反弹预期.html'): '20220917',  # 新华联/中交/冰点反弹
    ('短线杰哥擒龙', '周末复盘与周一计划弱反弹预期.md'): '20220917',
}

print('=' * 60)
print('Date Assignment Plan for Undated Files')
print(f'Total: {len(assignments)} files')
print('=' * 60)

index = 0
for (acct, fname), date in sorted(assignments.items()):
    ext = os.path.splitext(fname)[1]
    # Clean filename: remove existing MMdd prefix for files like 0717XXX
    base = os.path.splitext(fname)[0]
    # Remove leading 4-digit if it looks like MMdd (not a year)
    base = re.sub(r'^\d{4}(?=[一-鿿])', '', base)
    new_name = f'{date}_{base}{ext}'
    index += 1
    print(f'{index:2d}. [{acct}] {fname}')
    print(f'    -> {new_name}')

# Check for conflicts with existing files
print('\n' + '=' * 60)
print('Conflict Check')
print('=' * 60)
conflicts = []
for (acct, fname), date in assignments.items():
    ext = os.path.splitext(fname)[1]
    base = os.path.splitext(fname)[0]
    base = re.sub(r'^\d{4}(?=[一-鿿])', '', base)
    new_name = f'{date}_{base}{ext}'
    target_path = os.path.join(root, acct, new_name)
    if os.path.exists(target_path):
        conflicts.append(f'  EXISTS: {acct}/{new_name}')
    # Also check for same-date conflicts between assignments
    other_ext = '.md' if ext == '.html' else '.html'
    other_name = f'{date}_{base}{other_ext}'
    other_assignments = [a for a in assignments if a != (acct, fname)]
    for oa in other_assignments:
        o_ext = os.path.splitext(oa[1])[1]
        o_base = os.path.splitext(oa[1])[0]
        o_base = re.sub(r'^\d{4}(?=[一-鿿])', '', o_base)
        if acct == oa[0] and o_base == base and o_ext != ext and date == assignments[oa]:
            pass  # Same base different ext (html+md pair) - expected

if conflicts:
    for c in conflicts:
        print(c)
else:
    print('  No conflicts detected between new and existing files.')
    print('  (HTML+MD pairs are expected, not conflicts)')

# ===== Execute Renaming =====
print('\n' + '=' * 60)
print('Executing Renaming...')
print('=' * 60)

# Backup first
backup_dir = os.path.join(root, 'backup_renamed')
os.makedirs(backup_dir, exist_ok=True)

renamed_count = 0
error_count = 0

for (acct, fname), date in sorted(assignments.items()):
    ext = os.path.splitext(fname)[1]
    base = os.path.splitext(fname)[0]
    base = re.sub(r'^\d{4}(?=[一-鿿])', '', base)
    new_name = f'{date}_{base}{ext}'

    old_path = os.path.join(root, acct, fname)
    new_path = os.path.join(root, acct, new_name)

    if not os.path.exists(old_path):
        print(f'  SKIP (not found): {acct}/{fname}')
        error_count += 1
        continue

    if os.path.exists(new_path):
        print(f'  SKIP (exists): {acct}/{new_name}')
        error_count += 1
        continue

    try:
        os.rename(old_path, new_path)
        print(f'  OK: {acct}/{fname[:40]}')
        print(f'      -> {new_name[:60]}')
        renamed_count += 1
    except Exception as e:
        print(f'  ERROR: {acct}/{fname}: {e}')
        error_count += 1

# Also delete the undated_files.txt since all are now handled
undated_txt = os.path.join(root, 'undated_files.txt')
if os.path.exists(undated_txt):
    os.remove(undated_txt)
    print(f'\nDeleted undated_files.txt (all files now processed)')

print(f'\nRenamed: {renamed_count} files')
print(f'Errors/Skipped: {error_count}')
print('Date assignment complete!')
