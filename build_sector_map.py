import os, re, json
from collections import OrderedDict

root = 'D:/杰哥复盘数据'

# Keyword-based sector classification
SECTOR_KEYWORDS = [
    # 科技/信息技术
    ('科技', ['科技', '信息', '软件', '电子', '通信', '芯片', '半导体', '互联', '数字', '数据', '算力',
             '计算机', '网络', 'AI', '人工智能', '智能', '机器人', '自动化', '5G', '6G', '北斗', '卫星',
             '光刻', '封测', '集成电路', 'IT', '互联网', '数码', '光电', '微电']),
    # 医药医疗
    ('医药', ['医药', '医疗', '生物', '药业', '医', '健康', '康', '药', '制药', '疫苗',
             '基因', '检测', '诊断', '器械', '医院', '中医']),
    # 金融
    ('金融', ['银行', '保险', '证券', '金融', '信托', '期货', '券商', '基金', '理财']),
    # 房地产
    ('房地产', ['房地产', '置业', '地产', '物业', '开发', '城建', '建设']),
    # 汽车
    ('汽车', ['汽车', '汽配', '车', '新能源车', '整车', '零部件']),
    # 电力/能源
    ('电力能源', ['电力', '能源', '新能源', '光伏', '风电', '核电', '水电', '火电', '电网',
                 '电池', '锂电', '氢能', '储能', '充电', '输配']),
    # 煤炭
    ('煤炭', ['煤炭', '煤', '焦炭', '焦煤']),
    # 钢铁
    ('钢铁', ['钢铁', '钢', '冶金', '铁']),
    # 有色金属
    ('有色金属', ['有色', '黄金', '稀土', '锂', '钴', '镍', '铜', '铝', '锌', '铅', '锡',
                 '钨', '钼', '钛', '锆', '新材料', '合金']),
    # 化工
    ('化工', ['化工', '化学', '石化', '化纤', '化肥', '农药', '塑料', '橡胶', '日化',
             '石油', '炼化', '有机硅', '氟']),
    # 消费/食品饮料
    ('消费', ['食品', '饮料', '酒', '乳业', '乳品', '调味', '餐饮', '白酒', '啤酒',
             '葡萄酒', '黄酒', '预制菜', '消费', '家电', '家居', '纺织', '服装',
             '旅游', '酒店', '免税', '零售', '百货', '超市']),
    # 农业
    ('农业', ['农业', '农', '种业', '种子', '渔业', '牧', '养殖', '水产', '猪', '鸡',
             '饲料', '土地', '乡村振兴']),
    # 军工
    ('军工', ['军工', '航天', '航空', '船舶', '装备', '兵装', '国防', '军']),
    # 传媒/游戏
    ('传媒', ['传媒', '影视', '广告', '游戏', '出版', '广电', '媒体', '营销', '体育',
             '教育', '文化']),
    # 交通运输
    ('交通运输', ['交通', '运输', '物流', '港口', '机场', '公路', '铁路', '航运', '航空',
                 '快递', '海运']),
    # 建筑建材
    ('建筑建材', ['建筑', '建材', '工程', '设计', '装饰', '水泥', '玻璃', '陶瓷']),
    # 机械制造
    ('机械制造', ['机械', '设备', '制造', '工业', '通用', '专用', '精密', '机床',
                 '重工', '工程机械', '仪器', '仪表']),
    # 环保
    ('环保', ['环保', '水务', '节能', '环境', '清洁', '生态', '碳中和', '碳']),
    # 商贸
    ('商贸', ['贸易', '商业', '进出口', '外贸', '跨境']),
    # 纺织服装
    ('纺织服装', ['纺织', '服装', '鞋', '帽', '家纺']),
    # 电力设备
    ('电力设备', ['电气', '电缆', '电线', '变压器', '开关', '仪表', '输变电']),
    # 基础化工
    ('基础化工', ['基础化工', '钛白粉', '氯碱', '纯碱', '烧碱', '硫酸', '硝酸']),
]

def classify_stock(name, code):
    """Classify a stock into a sector based on its name and code"""
    for sector, keywords in SECTOR_KEYWORDS:
        for kw in keywords:
            if kw in name:
                return sector
    # Fallback: use board classification
    if code.startswith('300'):
        return '创业板'
    if code.startswith('688'):
        return '科创板'
    if code.startswith('002'):
        return '中小板'
    return '其他'

# Load signals to get all unique stocks
with open(os.path.join(root, 'stock_signals.json'), 'r', encoding='utf-8') as f:
    signals = json.load(f)

# Build code -> (name, sector) mapping
stock_info = {}  # code -> {name, sector}
for s in signals:
    code = s['stock_code']
    if code not in stock_info:
        name = s['stock_name']
        sector = classify_stock(name, code)
        stock_info[code] = {'name': name, 'sector': sector}

# Save sector mapping
with open(os.path.join(root, 'stock_sector.json'), 'w', encoding='utf-8') as f:
    json.dump(stock_info, f, ensure_ascii=False, indent=2)

# Stats
from collections import Counter
sector_counts = Counter(v['sector'] for v in stock_info.values())
print(f'分类股票: {len(stock_info)}')
print(f'板块分布:')
for sector, count in sector_counts.most_common():
    print(f'  {sector}: {count}')

# Show some unclassified
others = [(k,v) for k,v in stock_info.items() if v['sector'] == '其他']
print(f'\n未分类: {len(others)}')
for code, info in others[:20]:
    print(f'  {code} {info["name"]}')
