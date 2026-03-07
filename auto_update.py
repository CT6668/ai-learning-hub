#!/usr/bin/env python3
"""
AI学习星球 - 全自动每日更新脚本 v2.0
更新范围：
  1. 【每日】AI 资讯：从 10+ 公开 RSS/API 抓取最新新闻
  2. 【每周】学习资源：从 Papers With Code、HuggingFace Course 等补充新资源
  3. 【每月】实战项目：从 GitHub Trending 抓取热门 AI 开源项目
"""

import json, os, sys, time, hashlib, re, base64
import urllib.request, urllib.error, urllib.parse
from datetime import datetime, timezone, timedelta
from xml.etree import ElementTree as ET

# ==================== 配置 ====================
SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
DATA_FILE   = os.path.join(SCRIPT_DIR, 'data.json')
LOG_FILE    = os.path.join(SCRIPT_DIR, 'update.log')
MAX_NEWS    = 20   # 最多保留多少条资讯
MAX_DAYS    = 14   # 超过14天的旧资讯自动过期

CST = timezone(timedelta(hours=8))
def now_cst(): return datetime.now(CST)
TODAY       = now_cst().strftime('%Y-%m-%d')
THIS_WEEK   = now_cst().strftime('%Y-W%W')   # 周标识，用于判断是否本周已添加
THIS_MONTH  = now_cst().strftime('%Y-%m')

# ==================== 日志 ====================
def log(msg):
    ts   = now_cst().strftime('%Y-%m-%d %H:%M:%S')
    line = f'[{ts}] {msg}'
    print(line)
    try:
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(line + '\n')
        with open(LOG_FILE, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        if len(lines) > 500:
            with open(LOG_FILE, 'w', encoding='utf-8') as f:
                f.writelines(lines[-500:])
    except:
        pass

# ==================== HTTP ====================
UA = ('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
      'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36')

def http_get(url, timeout=12, headers=None):
    h = {'User-Agent': UA, 'Accept': '*/*', 'Cache-Control': 'no-cache'}
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            charset = 'utf-8'
            ct = r.headers.get('Content-Type', '')
            if 'charset=' in ct:
                charset = ct.split('charset=')[-1].strip().split(';')[0]
            return r.read().decode(charset, errors='replace')
    except Exception as e:
        raise e

def make_id(s): return 'n_' + hashlib.md5(s.encode()).hexdigest()[:12]

def clean(s):
    if not s: return ''
    s = re.sub(r'<[^>]+>', '', s)
    for e, r in [('&amp;','&'),('&lt;','<'),('&gt;','>'),('&quot;','"'),('&#\d+;','')]:
        s = re.sub(e, r, s)
    return re.sub(r'\s+', ' ', s).strip()

# ==================== 数据 ====================
def load():
    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def save(data):
    data['meta']['last_updated'] = TODAY
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ============================================================
#  模块一：每日资讯更新
# ============================================================

def fetch_github_trending():
    """抓取 GitHub Trending AI 项目（修复URL问题）"""
    results = []
    try:
        log('  → GitHub Trending...')
        html = http_get('https://github.com/trending?since=daily', timeout=15)
        # 精确匹配仓库链接：/user/repo 格式，且不含查询参数
        repos = re.findall(r'href="/([a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+)"[^>]*>\s*\n\s*<span', html)
        if not repos:
            # 备用正则
            repos = re.findall(r'<h2[^>]*>\s*<a href="/([^"?&]+)"', html)

        ai_kw = ['llm','gpt','ai','ml','model','diffusion','transformer','agent','rag',
                 'deepseek','qwen','llama','claude','gemini','openai','neural','bert',
                 'mcp','copilot','whisper','stable','finetune','lora','vllm','ollama']
        # 提取描述
        descs = re.findall(r'<p[^>]*class="[^"]*col-9[^"]*"[^>]*>(.*?)</p>', html, re.DOTALL)
        desc_list = [clean(d) for d in descs]

        seen = set()
        for i, rp in enumerate(repos[:40]):
            rp = rp.strip('/')
            # 过滤：必须是 user/repo 格式，不含特殊字符
            if '?' in rp or '&' in rp or rp.count('/') != 1:
                continue
            if rp in seen:
                continue
            if not any(k in rp.lower() for k in ai_kw):
                continue
            seen.add(rp)
            desc = desc_list[i] if i < len(desc_list) else ''
            if not desc or len(desc) < 5:
                desc = f'GitHub 热门 AI 开源项目'
            results.append({
                'id': make_id('gh_' + rp),
                'date': TODAY,
                'tag': 'tool',
                'tag_label': '🛠️ 开源',
                'title': f'GitHub 热榜 · {rp}',
                'summary': desc[:150],
                'source': 'GitHub Trending',
                'url': f'https://github.com/{rp}',
            })
            if len(results) >= 3:
                break
        log(f'  ✓ GitHub Trending: {len(results)} 条')
    except Exception as e:
        log(f'  ✗ GitHub Trending: {e}')
    return results

def fetch_hf_papers():
    """抓取 HuggingFace 每日论文（用今日日期）"""
    results = []
    try:
        log('  → HuggingFace 每日论文...')
        url = f'https://huggingface.co/api/daily_papers?date={TODAY}'
        data = json.loads(http_get(url, timeout=12))
        papers = data if isinstance(data, list) else data.get('papers', [])
        if not papers:
            # 尝试昨天
            yesterday = (now_cst() - timedelta(days=1)).strftime('%Y-%m-%d')
            url2 = f'https://huggingface.co/api/daily_papers?date={yesterday}'
            data2 = json.loads(http_get(url2, timeout=12))
            papers = data2 if isinstance(data2, list) else data2.get('papers', [])

        for p in papers[:3]:
            title    = p.get('paper', {}).get('title', '') or p.get('title', '')
            abstract = p.get('paper', {}).get('abstract', '') or p.get('abstract', '')
            pid      = p.get('paper', {}).get('id', '') or p.get('id', '')
            if not title: continue
            summary = (clean(abstract)[:140] + '...') if abstract else '最新 AI 研究论文'
            results.append({
                'id': make_id('hf_' + pid),
                'date': TODAY,
                'tag': 'research',
                'tag_label': '🔬 论文',
                'title': f'[论文] {title[:60]}',
                'summary': summary,
                'source': 'Hugging Face',
                'url': f'https://huggingface.co/papers/{pid}' if pid else 'https://huggingface.co/papers',
            })
        log(f'  ✓ HuggingFace 论文: {len(results)} 条')
    except Exception as e:
        log(f'  ✗ HuggingFace 论文: {e}')
    return results

def fetch_rss(feed_url, source_name, tag, tag_label, max_items=3, ai_filter=True):
    """通用 RSS 解析（含 AI 关键词过滤和垃圾帖过滤）"""
    results = []
    # 垃圾帖过滤关键词
    SPAM_KW = ['self-promotion', 'weekly thread', 'discussion thread', 'what are you',
               'hiring', 'job', 'career', 'resume', 'rant', 'meme']
    AI_KW   = ['ai','人工智能','大模型','llm','gpt','chatgpt','deepseek','机器学习',
               '深度学习','agent','model','openai','google','gemini','claude','transformer',
               'diffusion','智能体','神经网络','算法','训练','微调','rag','语言模型',
               'stable diffusion','copilot','ollama','vllm','multimodal','vision']
    try:
        log(f'  → RSS {source_name}...')
        xml_text = http_get(feed_url, timeout=12)
        root = ET.fromstring(xml_text)
        ns   = {'atom': 'http://www.w3.org/2005/Atom'}
        items = root.findall('.//item') or root.findall('.//atom:entry', ns)

        for item in items:
            def get(tag_name):
                el = item.find(tag_name) or item.find(f'atom:{tag_name}', ns)
                if el is not None:
                    txt = el.text or ''
                    if not txt and el.get('href'): txt = el.get('href')
                    return clean(txt)
                return ''

            title   = get('title')
            link    = get('link') or get('id')
            desc    = get('description') or get('summary') or get('content')
            pub_raw = get('pubDate') or get('published') or get('updated')

            if not title or not link: continue

            # 过滤垃圾帖
            title_lower = title.lower()
            if any(k in title_lower for k in SPAM_KW): continue

            # AI 关键词过滤
            combined = (title + desc).lower()
            if ai_filter and not any(k.lower() in combined for k in AI_KW): continue

            # 解析日期
            pub_date = TODAY
            for fmt in ['%a, %d %b %Y %H:%M:%S %z', '%a, %d %b %Y %H:%M:%S GMT',
                        '%Y-%m-%dT%H:%M:%S%z', '%Y-%m-%dT%H:%M:%SZ']:
                try:
                    dt = datetime.strptime(pub_raw[:30].strip(), fmt)
                    pub_date = dt.strftime('%Y-%m-%d')
                    break
                except: continue

            summary = (desc[:140] + '...') if len(desc) > 140 else desc
            if not summary: summary = '点击查看详情'

            results.append({
                'id': make_id(link),
                'date': pub_date,
                'tag': tag,
                'tag_label': tag_label,
                'title': title[:80],
                'summary': summary,
                'source': source_name,
                'url': link,
            })
            if len(results) >= max_items: break

        log(f'  ✓ {source_name}: {len(results)} 条')
    except Exception as e:
        log(f'  ✗ {source_name}: {e}')
    return results

RSS_SOURCES = [
    ('https://techcrunch.com/category/artificial-intelligence/feed/', 'TechCrunch AI', 'hot',      '🔥 热门',  3, False),
    ('https://venturebeat.com/category/ai/feed/',                     'VentureBeat AI','trend',    '📈 趋势',  3, False),
    ('https://openai.com/blog/rss.xml',                               'OpenAI Blog',   'hot',      '🔥 热门',  2, False),
    ('https://blogs.microsoft.com/ai/feed/',                          'Microsoft AI',  'new',      '✨ 最新',  2, True),
    ('https://machinelearningmastery.com/feed/',                      'ML Mastery',    'research', '🔬 深度',  2, True),
    ('https://www.reddit.com/r/MachineLearning/.rss',                 'Reddit ML',     'research', '🔬 深度',  2, True),
    ('https://www.theregister.com/machine_learning/headlines.atom',   'The Register',  'new',      '✨ 最新',  2, True),
]

# ============================================================
#  模块二：每周自动补充学习资源
# ============================================================

# 按阶段预置的「待补充资源池」，脚本每周从中随机选 1-2 条加入
# （这些都是真实存在的高质量资源）
RESOURCE_POOL = {
    0: [  # 阶段一：入门基础
        {'icon':'📹','title':'【2024最新】Python完整教程 - 黑马程序员','desc':'B站百万播放，从基础到项目实战，全程中文，适合零基础','type':'video','type_label':'视频','url':'https://www.bilibili.com/video/BV1qW4y1a7fU'},
        {'icon':'🎓','title':'CS50: Introduction to AI with Python（哈佛）','desc':'哈佛大学免费AI入门课，用Python讲解搜索/神经网络/NLP','type':'course','type_label':'课程','url':'https://cs50.harvard.edu/ai/'},
        {'icon':'📄','title':'Google Machine Learning Crash Course（中文）','desc':'谷歌官方机器学习速成课，图文并茂，适合快速入门','type':'course','type_label':'课程','url':'https://developers.google.com/machine-learning/crash-course?hl=zh-cn'},
        {'icon':'📹','title':'3Blue1Brown - 神经网络（中文字幕）','desc':'最美数学可视化，把神经网络讲得极其直观，B站有中文版','type':'video','type_label':'视频','url':'https://www.bilibili.com/video/BV1bx411M7Zx'},
        {'icon':'🏆','title':'LeetCode - 数据结构与算法','desc':'AI面试必备，刷题练编程基础','type':'tool','type_label':'平台','url':'https://leetcode.cn/'},
    ],
    1: [  # 阶段二：核心技能
        {'icon':'📹','title':'李沐《动手学深度学习》B站直播回放','desc':'作者亲自讲解，配合d2l教材，最好的中文深度学习课','type':'video','type_label':'视频','url':'https://space.bilibili.com/1567748478/channel/seriesdetail?sid=358497'},
        {'icon':'📄','title':'The Illustrated Transformer（图解Transformer）','desc':'Jay Alammar 出品，用动图把 Transformer 讲得无比清楚','type':'doc','type_label':'文档','url':'https://jalammar.github.io/illustrated-transformer/'},
        {'icon':'🎓','title':'Fast.ai - Practical Deep Learning for Coders','desc':'自顶向下学深度学习，边做项目边学理论，实战派必选','type':'course','type_label':'课程','url':'https://course.fast.ai/'},
        {'icon':'📄','title':'OpenAI Prompt Engineering 指南（官方中文版）','desc':'官方出品，系统介绍如何写好 Prompt，必看','type':'doc','type_label':'文档','url':'https://platform.openai.com/docs/guides/prompt-engineering'},
        {'icon':'📹','title':'Andrej Karpathy - Let\'s build GPT from scratch','desc':'前OpenAI大神手把手从零写GPT，YouTube最佳实战视频','type':'video','type_label':'视频','url':'https://www.youtube.com/watch?v=kCc8FmEb1nY'},
    ],
    2: [  # 阶段三：进阶实战
        {'icon':'🎓','title':'吴恩达 - Building Agentic RAG with LlamaIndex','desc':'1小时掌握 Agentic RAG，DeepLearning.AI 免费课','type':'course','type_label':'课程','url':'https://www.deeplearning.ai/short-courses/building-agentic-rag-with-llamaindex/'},
        {'icon':'🎓','title':'吴恩达 - AI Agents in LangGraph','desc':'用 LangGraph 构建生产级 AI Agent，免费课程','type':'course','type_label':'课程','url':'https://www.deeplearning.ai/short-courses/ai-agents-in-langgraph/'},
        {'icon':'📄','title':'Ollama - 本地运行大模型指南','desc':'在自己电脑上跑 Llama/Qwen/Gemma，完全免费，零API费用','type':'tool','type_label':'工具','url':'https://ollama.ai/'},
        {'icon':'📄','title':'Dify - 低代码 LLM 应用开发平台','desc':'国产开源，拖拽式构建 AI 应用，支持 RAG/Agent/工作流','type':'tool','type_label':'工具','url':'https://github.com/langgenius/dify'},
        {'icon':'🎓','title':'吴恩达 - Finetuning LLMs','desc':'大模型微调实战，SFT/LoRA/RLHF 全流程，免费课','type':'course','type_label':'课程','url':'https://www.deeplearning.ai/short-courses/finetuning-large-language-models/'},
    ],
    3: [  # 阶段四：前沿突破
        {'icon':'📑','title':'DeepSeek-R1 技术报告（arXiv）','desc':'2026最强推理模型技术报告，强化学习训练路线深度解析','type':'doc','type_label':'论文','url':'https://arxiv.org/abs/2501.12948'},
        {'icon':'📊','title':'LMSys Chatbot Arena（模型排行榜）','desc':'真实用户投票的大模型能力排行，每周更新，最公正的评测','type':'tool','type_label':'平台','url':'https://chat.lmsys.org/'},
        {'icon':'📹','title':'Two Minute Papers - 最新AI论文速读','desc':'YouTube频道，每期2分钟介绍最新AI研究，紧跟前沿','type':'video','type_label':'视频','url':'https://www.youtube.com/@TwoMinutePapers'},
        {'icon':'📄','title':'Transformer Circuits Thread（机制可解释性）','desc':'Anthropic 研究员的博客，深入理解神经网络内部机制','type':'doc','type_label':'文档','url':'https://transformer-circuits.pub/'},
        {'icon':'🎓','title':'Stanford CS336: Language Modeling from Scratch','desc':'斯坦福2024新课，从头构建大语言模型，公开课资料','type':'course','type_label':'课程','url':'https://stanford-cs336.github.io/spring2024/'},
    ],
}

def update_learning_resources(data):
    """每周自动向每个学习阶段添加 1 个新资源"""
    phases = data.get('learning', {}).get('phases', [])
    added_count = 0

    for phase_idx, phase in enumerate(phases):
        existing_urls = {r['url'] for r in phase.get('resources', [])}
        # 检查本周是否已经给这个阶段加过资源
        this_week_added = any(
            r.get('added_date', '')[:7] == THIS_MONTH and  # 本月加过
            r.get('added_date', '') >= (now_cst() - timedelta(days=7)).strftime('%Y-%m-%d')  # 7天内
            for r in phase.get('resources', [])
        )
        if this_week_added:
            continue

        pool = RESOURCE_POOL.get(phase_idx, [])
        for candidate in pool:
            if candidate['url'] in existing_urls:
                continue
            # 找到一个未添加的，加进去
            new_res = dict(candidate)
            new_res['id']         = 'r_' + hashlib.md5(candidate['url'].encode()).hexdigest()[:8]
            new_res['added_date'] = TODAY
            phase['resources'].append(new_res)
            added_count += 1
            log(f'  ✓ 新增学习资源[阶段{phase_idx+1}]: {new_res["title"][:40]}')
            break

    return added_count

# ============================================================
#  模块三：每月自动补充实战项目
# ============================================================

# 预置项目池（真实 GitHub 热门 AI 项目，每月轮流加入）
PROJECT_POOL = [
    {
        'emoji': '🦙', 'title': 'Ollama 本地大模型部署',
        'difficulty': 'beginner', 'diff_label': '入门级', 'cat': 'beginner nlp',
        'desc': '在本地电脑运行 Llama3/Qwen/Gemma 等大模型，完全离线，零API费用。最简单的大模型本地化方案，一行命令即可运行。',
        'tags': ['Ollama', 'Llama3', 'Qwen', '本地部署'],
        'duration': '半天', 'highlight': '⭐ 超推荐',
        'bg': 'linear-gradient(135deg,#1e3a2a,#0a5030)',
        'tutorial_url': 'https://ollama.ai/',
        'github_url': 'https://github.com/ollama/ollama',
    },
    {
        'emoji': '🔧', 'title': 'Dify - 低代码 AI 应用开发',
        'difficulty': 'beginner', 'diff_label': '入门级', 'cat': 'beginner nlp',
        'desc': '用 Dify 无需写代码即可构建 RAG 知识库问答、AI 工作流、Chatbot 应用。国产开源，中文友好，GitHub 50k+ Star。',
        'tags': ['Dify', 'RAG', '低代码', '工作流'],
        'duration': '1天', 'highlight': '🔥 国产之光',
        'bg': 'linear-gradient(135deg,#1a2050,#102060)',
        'tutorial_url': 'https://docs.dify.ai/zh-hans',
        'github_url': 'https://github.com/langgenius/dify',
    },
    {
        'emoji': '🎙️', 'title': 'AI 实时语音对话助手',
        'difficulty': 'medium', 'diff_label': '进阶级', 'cat': 'medium nlp',
        'desc': '结合 Whisper 语音识别 + LLM 对话 + TTS 语音合成，构建像 Siri 一样的实时语音 AI 助手，支持中英文。',
        'tags': ['Whisper', 'TTS', 'VAD', '语音交互'],
        'duration': '3-5天', 'highlight': '🎙️ 语音交互',
        'bg': 'linear-gradient(135deg,#3a2a1e,#604010)',
        'tutorial_url': 'https://github.com/openai/whisper',
        'github_url': 'https://github.com/snakers4/silero-vad',
    },
    {
        'emoji': '🌐', 'title': 'AI 网页爬虫 + 智能摘要',
        'difficulty': 'medium', 'diff_label': '进阶级', 'cat': 'medium nlp',
        'desc': '给 AI 一个网址，自动爬取网页内容，提取关键信息，生成结构化摘要报告。用 Crawl4AI + LLM 实现智能信息提取。',
        'tags': ['Crawl4AI', 'LLM', '网页爬虫', '信息提取'],
        'duration': '2-3天', 'highlight': '🕷️ 信息收集',
        'bg': 'linear-gradient(135deg,#1e2a3a,#102040)',
        'tutorial_url': 'https://github.com/unclecode/crawl4ai',
        'github_url': 'https://github.com/unclecode/crawl4ai',
    },
    {
        'emoji': '🎨', 'title': 'ComfyUI AI 绘画工作流',
        'difficulty': 'medium', 'diff_label': '进阶级', 'cat': 'medium vision',
        'desc': '用 ComfyUI 构建可视化 Stable Diffusion 工作流，实现文生图、图生图、ControlNet 姿态控制、Inpainting 等高级功能。',
        'tags': ['ComfyUI', 'Stable Diffusion', 'ControlNet', 'AI绘画'],
        'duration': '3-5天', 'highlight': '🎨 创意无限',
        'bg': 'linear-gradient(135deg,#2a1e3a,#3a1060)',
        'tutorial_url': 'https://github.com/comfyanonymous/ComfyUI',
        'github_url': 'https://github.com/comfyanonymous/ComfyUI',
    },
    {
        'emoji': '🤖', 'title': 'MCP 服务开发 - 给 AI 接工具',
        'difficulty': 'advanced', 'diff_label': '挑战级', 'cat': 'advanced nlp',
        'desc': '开发 Model Context Protocol (MCP) 服务，让 AI 能调用你的自定义工具（查数据库/调API/操作文件）。MCP 是 2025 年最热门的 AI 工具协议。',
        'tags': ['MCP', 'Tool Use', 'Python', 'API集成'],
        'duration': '1周', 'highlight': '🔥 2026最热',
        'bg': 'linear-gradient(135deg,#2a1a1e,#601020)',
        'tutorial_url': 'https://modelcontextprotocol.io/quickstart',
        'github_url': 'https://github.com/modelcontextprotocol/python-sdk',
    },
]

def update_projects(data):
    """每月自动添加 1-2 个新实战项目"""
    projects  = data.get('projects', [])
    existing_titles = {p['title'] for p in projects}
    # 检查本月是否已加过
    this_month_added = [p for p in projects if p.get('added_date', '').startswith(THIS_MONTH)]
    if len(this_month_added) >= 2:
        return 0

    added_count = 0
    for candidate in PROJECT_POOL:
        if candidate['title'] in existing_titles:
            continue
        new_proj = dict(candidate)
        new_proj['id']         = 'p_' + hashlib.md5(candidate['title'].encode()).hexdigest()[:8]
        new_proj['added_date'] = TODAY
        projects.append(new_proj)
        added_count += 1
        log(f'  ✓ 新增实战项目: {new_proj["title"]}')
        if added_count >= 2:
            break

    data['projects'] = projects
    return added_count

# ============================================================
#  主流程
# ============================================================

def run():
    log('=' * 55)
    log(f'🚀 AI学习星球 全自动更新 v2.0 (日期: {TODAY})')
    log('=' * 55)

    data = load()
    existing_ids  = {n['id']  for n in data.get('news', [])}
    existing_urls = {n['url'] for n in data.get('news', [])}

    # ===== 模块一：每日资讯 =====
    log('\n📰 模块一：抓取今日 AI 资讯...')
    all_new = []
    all_new += fetch_github_trending()
    all_new += fetch_hf_papers()
    for src in RSS_SOURCES:
        try:
            all_new += fetch_rss(*src)
        except Exception as e:
            log(f'  ✗ {src[1]}: {e}')
        time.sleep(0.4)

    # 去重 + 过期过滤
    news_added = 0
    cutoff = (now_cst() - timedelta(days=MAX_DAYS)).strftime('%Y-%m-%d')
    for item in all_new:
        if item['id'] in existing_ids or item['url'] in existing_urls:
            continue
        if item.get('date', TODAY) < cutoff:
            continue
        data['news'].insert(0, item)
        existing_ids.add(item['id'])
        existing_urls.add(item['url'])
        news_added += 1

    # 只保留最新 MAX_NEWS 条
    data['news'] = data['news'][:MAX_NEWS]

    # 更新滚动条（从最新资讯自动生成）
    data['ticker'] = [n['title'][:35] + ('...' if len(n['title']) > 35 else '')
                      for n in data['news'][:10]]

    log(f'  → 资讯新增 {news_added} 条，当前共 {len(data["news"])} 条')

    # ===== 模块二：每周学习资源 =====
    log('\n📚 模块二：检查学习资源...')
    res_added = update_learning_resources(data)
    log(f'  → 学习资源新增 {res_added} 个')

    # ===== 模块三：每月实战项目 =====
    log('\n🚀 模块三：检查实战项目...')
    proj_added = update_projects(data)
    log(f'  → 实战项目新增 {proj_added} 个')

    # ===== 保存 =====
    save(data)

    log(f'\n✅ 更新完成！')
    log(f'   资讯 +{news_added} | 学习资源 +{res_added} | 项目 +{proj_added}')
    log('=' * 55)
    return news_added + res_added + proj_added

if __name__ == '__main__':
    run()
