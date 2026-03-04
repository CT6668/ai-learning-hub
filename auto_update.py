#!/usr/bin/env python3
"""
AI学习星球 - 全自动每日更新脚本
无需人工操作，自动从多个公开RSS/API抓取AI新闻，更新 data.json

数据来源（全部公开免费无需Key）：
  1. GitHub Trending (AI 方向)
  2. Reddit r/MachineLearning RSS
  3. Hugging Face 每日论文 API
  4. 36氪 AI 频道 RSS
  5. 少数派 AI 频道 RSS
  6. InfoQ AI RSS
"""

import json
import os
import sys
import time
import hashlib
import re
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime, timezone, timedelta
from xml.etree import ElementTree as ET

# ==================== 配置 ====================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE   = os.path.join(SCRIPT_DIR, 'data.json')
LOG_FILE    = os.path.join(SCRIPT_DIR, 'update.log')
MAX_NEWS    = 20          # 最多保留多少条资讯
MAX_DAYS    = 14          # 超过14天的旧资讯自动归档（不展示）
SHOW_LATEST = 9           # 首页展示最新 N 条

CST = timezone(timedelta(hours=8))

def now_cst():
    return datetime.now(CST)

TODAY = now_cst().strftime('%Y-%m-%d')

# ==================== 日志 ====================
def log(msg):
    ts = now_cst().strftime('%Y-%m-%d %H:%M:%S')
    line = f'[{ts}] {msg}'
    print(line)
    try:
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(line + '\n')
        # 保留最新 500 行
        with open(LOG_FILE, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        if len(lines) > 500:
            with open(LOG_FILE, 'w', encoding='utf-8') as f:
                f.writelines(lines[-500:])
    except:
        pass

# ==================== HTTP 工具 ====================
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                  'AppleWebKit/537.36 (KHTML, like Gecko) '
                  'Chrome/122.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml,application/json;q=0.9,*/*;q=0.8',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    'Cache-Control': 'no-cache',
}

def http_get(url, timeout=12, extra_headers=None):
    headers = dict(HEADERS)
    if extra_headers:
        headers.update(extra_headers)
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            charset = 'utf-8'
            ct = resp.headers.get('Content-Type', '')
            if 'charset=' in ct:
                charset = ct.split('charset=')[-1].strip().split(';')[0].strip()
            return resp.read().decode(charset, errors='replace')
    except Exception as e:
        raise e

def make_id(url):
    return 'news_' + hashlib.md5(url.encode()).hexdigest()[:12]

def clean_text(s):
    if not s:
        return ''
    s = re.sub(r'<[^>]+>', '', s)
    s = re.sub(r'&amp;', '&', s)
    s = re.sub(r'&lt;', '<', s)
    s = re.sub(r'&gt;', '>', s)
    s = re.sub(r'&quot;', '"', s)
    s = re.sub(r'&#\d+;', '', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s[:200]

# ==================== 数据加载/保存 ====================
def load_data():
    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_data(data):
    data['meta']['last_updated'] = TODAY
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ==================== 来源1: GitHub Trending ====================
def fetch_github_trending():
    results = []
    try:
        log('  → 抓取 GitHub Trending (AI 方向)...')
        html = http_get('https://github.com/trending?since=daily&spoken_language_code=', timeout=15)

        # 提取 repo 列表
        repos = re.findall(
            r'href="/([^/"]+/[^/"]+)"[^>]*class="[^"]*Link[^"]*"',
            html
        )
        # 提取描述
        descs = re.findall(r'<p[^>]*class="[^"]*col-9[^"]*"[^>]*>(.*?)</p>', html, re.DOTALL)

        ai_kw = ['llm', 'gpt', 'ai', 'ml', 'model', 'diffusion', 'transformer',
                 'agent', 'rag', 'finetune', 'lora', 'deepseek', 'qwen', 'llama',
                 'claude', 'gemini', 'openai', 'stable', 'neural', 'bert', 'mcp']

        seen = set()
        desc_list = [clean_text(d) for d in descs]

        for i, rp in enumerate(repos):
            rp = rp.strip('/')
            if rp in seen:
                continue
            if not any(k in rp.lower() for k in ai_kw):
                continue
            seen.add(rp)

            desc = desc_list[i] if i < len(desc_list) else '开源项目'
            if not desc or len(desc) < 5:
                desc = f'GitHub 热门开源 AI 项目 {rp}'

            results.append({
                'id':        make_id('github_' + rp),
                'date':      TODAY,
                'tag':       'tool',
                'tag_label': '🛠️ 开源',
                'title':     f'GitHub 热榜 · {rp}',
                'summary':   desc[:150],
                'source':    'GitHub Trending',
                'url':       f'https://github.com/{rp}',
            })
            if len(results) >= 3:
                break

        log(f'  ✓ GitHub Trending 获取 {len(results)} 条')
    except Exception as e:
        log(f'  ✗ GitHub Trending 失败: {e}')
    return results

# ==================== 来源2: Hugging Face 每日论文 ====================
def fetch_hf_papers():
    results = []
    try:
        log('  → 抓取 Hugging Face 每日论文...')
        url = f'https://huggingface.co/api/daily_papers?date={TODAY}'
        data = json.loads(http_get(url, timeout=12))

        papers = data if isinstance(data, list) else data.get('papers', [])
        for p in papers[:3]:
            title = p.get('paper', {}).get('title', '') or p.get('title', '')
            abstract = p.get('paper', {}).get('abstract', '') or p.get('abstract', '')
            pid = p.get('paper', {}).get('id', '') or p.get('id', '')
            if not title:
                continue

            summary = clean_text(abstract)[:140] + '...' if abstract else '最新 AI 研究论文'
            results.append({
                'id':        make_id('hf_' + pid),
                'date':      TODAY,
                'tag':       'research',
                'tag_label': '🔬 论文',
                'title':     f'[论文] {title[:60]}',
                'summary':   summary,
                'source':    'Hugging Face',
                'url':       f'https://huggingface.co/papers/{pid}' if pid else 'https://huggingface.co/papers',
            })

        log(f'  ✓ HuggingFace 获取 {len(results)} 条')
    except Exception as e:
        log(f'  ✗ HuggingFace 论文 失败: {e}')
    return results

# ==================== 来源3: RSS 解析通用函数 ====================
def fetch_rss(feed_url, source_name, tag, tag_label, max_items=3, ai_filter=True):
    results = []
    ai_kw = ['ai', '人工智能', '大模型', 'llm', 'gpt', 'chatgpt', 'deepseek', '机器学习',
             '深度学习', 'agent', 'mcp', '模型', 'openai', 'google', '生成式', '多模态',
             'llama', 'qwen', 'claude', 'gemini', 'transformer', 'diffusion', '智能体',
             '神经网络', '自动化', '算法', '训练', '微调', 'rag', 'copilot', '语言模型']
    try:
        log(f'  → 抓取 RSS: {source_name}...')
        xml_text = http_get(feed_url, timeout=12)
        root = ET.fromstring(xml_text)

        # 兼容 RSS 2.0 和 Atom
        ns = {'atom': 'http://www.w3.org/2005/Atom'}
        items = root.findall('.//item') or root.findall('.//atom:entry', ns)

        for item in items:
            def get(tag_name):
                el = item.find(tag_name) or item.find(f'atom:{tag_name}', ns)
                if el is not None:
                    txt = el.text or ''
                    # atom:link has href
                    if not txt and el.get('href'):
                        txt = el.get('href')
                    return clean_text(txt)
                return ''

            title   = get('title')
            link    = get('link') or get('id')
            desc    = get('description') or get('summary') or get('content')
            pub_raw = get('pubDate') or get('published') or get('updated')

            if not title or not link:
                continue

            # AI 关键词过滤
            combined = (title + desc).lower()
            if ai_filter and not any(k.lower() in combined for k in ai_kw):
                continue

            # 解析日期
            pub_date = TODAY
            if pub_raw:
                for fmt in ['%a, %d %b %Y %H:%M:%S %z',
                            '%a, %d %b %Y %H:%M:%S GMT',
                            '%Y-%m-%dT%H:%M:%S%z',
                            '%Y-%m-%dT%H:%M:%SZ']:
                    try:
                        dt = datetime.strptime(pub_raw[:30], fmt)
                        pub_date = dt.strftime('%Y-%m-%d')
                        break
                    except:
                        continue

            summary = desc[:140] + '...' if len(desc) > 140 else desc
            if not summary:
                summary = '点击查看详情'

            results.append({
                'id':        make_id(link),
                'date':      pub_date,
                'tag':       tag,
                'tag_label': tag_label,
                'title':     title[:80],
                'summary':   summary,
                'source':    source_name,
                'url':       link,
            })

            if len(results) >= max_items:
                break

        log(f'  ✓ {source_name} 获取 {len(results)} 条')
    except Exception as e:
        log(f'  ✗ {source_name} RSS 失败: {e}')
    return results

# ==================== 来源4: 多个 RSS 源 ====================
RSS_SOURCES = [
    # (url, 来源名, tag, tag_label, max, ai_filter)
    (
        'https://rsshub.app/36kr/technology-ai',
        '36氪 AI', 'hot', '🔥 热门', 3, False
    ),
    (
        'https://www.infoq.cn/feed?tagName=ai',
        'InfoQ AI', 'new', '✨ 最新', 3, True
    ),
    (
        'https://www.reddit.com/r/MachineLearning/.rss',
        'Reddit ML', 'research', '🔬 深度', 2, False
    ),
    (
        'https://rsshub.app/sspai/category/ai',
        '少数派 AI', 'trend', '📈 趋势', 2, False
    ),
    (
        'https://feeds.feedburner.com/nvidiablog',
        'NVIDIA Blog', 'new', '✨ 最新', 2, True
    ),
    (
        'https://openai.com/blog/rss.xml',
        'OpenAI Blog', 'hot', '🔥 热门', 2, False
    ),
    (
        'https://blogs.microsoft.com/ai/feed/',
        'Microsoft AI', 'new', '✨ 最新', 2, True
    ),
    (
        'https://machinelearningmastery.com/feed/',
        'ML Mastery', 'research', '🔬 深度', 2, True
    ),
    (
        'https://techcrunch.com/category/artificial-intelligence/feed/',
        'TechCrunch AI', 'trend', '📈 趋势', 3, False
    ),
    (
        'https://venturebeat.com/category/ai/feed/',
        'VentureBeat AI', 'hot', '🔥 热门', 3, False
    ),
    (
        'https://www.theregister.com/machine_learning/headlines.atom',
        'The Register ML', 'new', '✨ 最新', 2, True
    ),
]

# ==================== 滚动条更新 ====================
def update_ticker(news_list):
    """从最新资讯自动生成滚动条内容"""
    items = []
    for n in news_list[:10]:
        title = n['title']
        # 截短到30字
        if len(title) > 30:
            title = title[:28] + '...'
        items.append(title)
    return items

# ==================== 主更新逻辑 ====================
def run():
    log('=' * 55)
    log(f'🚀 开始自动更新 AI 学习星球 (日期: {TODAY})')
    log('=' * 55)

    data = load_data()
    existing_ids   = {n['id'] for n in data.get('news', [])}
    existing_urls  = {n['url'] for n in data.get('news', [])}

    all_new = []

    # 1. GitHub Trending
    all_new += fetch_github_trending()

    # 2. HuggingFace 每日论文
    all_new += fetch_hf_papers()

    # 3. RSS 来源（逐个尝试，失败不中断）
    for src in RSS_SOURCES:
        try:
            all_new += fetch_rss(*src)
        except Exception as e:
            log(f'  ✗ RSS 源出错 {src[1]}: {e}')
        time.sleep(0.5)  # 礼貌性延迟

    # 过滤重复（按 id + url 双重去重）
    added = 0
    for item in all_new:
        if item['id'] in existing_ids:
            continue
        if item['url'] in existing_urls:
            continue
        # 只保留7天内的新闻
        try:
            item_date = datetime.strptime(item['date'], '%Y-%m-%d')
            cutoff = now_cst() - timedelta(days=MAX_DAYS)
            if item_date < cutoff.replace(tzinfo=None):
                continue
        except:
            pass

        data['news'].insert(0, item)
        existing_ids.add(item['id'])
        existing_urls.add(item['url'])
        added += 1

    # 只保留最新 MAX_NEWS 条（最多20条）
    data['news'] = data['news'][:MAX_NEWS]

    # 更新滚动条
    data['ticker'] = update_ticker(data['news'])

    # 保存
    save_data(data)

    log(f'✅ 更新完成！新增 {added} 条资讯，当前共 {len(data["news"])} 条')
    log(f'   data.json 已保存，网站将在下次刷新时显示最新内容')
    log('=' * 55)

    return added

if __name__ == '__main__':
    run()
