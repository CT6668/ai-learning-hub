#!/usr/bin/env python3
"""
AI学习星球 - 每日内容更新脚本
使用方式：
  python3 update_content.py          # 查看当前数据统计
  python3 update_content.py news     # 添加一条新资讯
  python3 update_content.py learn    # 添加一个学习资源
  python3 update_content.py project  # 添加一个项目
  python3 update_content.py auto     # 自动从网络抓取今日AI资讯（需联网）
"""

import json
import sys
import os
from datetime import datetime

# 路径配置
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(SCRIPT_DIR, 'data.json')

TODAY = datetime.now().strftime('%Y-%m-%d')

# ==================== 工具函数 ====================

def load_data():
    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_data(data):
    data['meta']['last_updated'] = TODAY
    data['meta']['version'] = str(float(data['meta'].get('version', '1.0')) + 0.01)[:4]
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f'✅ 数据已保存，更新时间: {TODAY}')

def input_prompt(prompt, default=''):
    val = input(f'{prompt} [{default}]: ').strip()
    return val if val else default

def print_stats():
    data = load_data()
    news = data.get('news', [])
    phases = data.get('learning', {}).get('phases', [])
    projects = data.get('projects', [])

    res_count = sum(len(p.get('resources', [])) for p in phases)
    today_news = [n for n in news if n.get('date') == TODAY]

    print(f'\n{"="*50}')
    print(f'📊 AI学习星球 数据统计 (截至 {data["meta"]["last_updated"]})')
    print(f'{"="*50}')
    print(f'📰 资讯总数:    {len(news)} 条（今日新增: {len(today_news)} 条）')
    print(f'📚 学习资源:    {res_count} 个（分{len(phases)}个阶段）')
    print(f'🚀 实战项目:    {len(projects)} 个')
    print(f'{"="*50}')

    if news:
        print(f'\n最新3条资讯:')
        for n in news[:3]:
            print(f'  [{n["date"]}] {n["title"][:40]}...')

# ==================== 添加资讯 ====================

def add_news_interactive():
    data = load_data()
    print('\n📰 添加新资讯\n' + '-'*40)

    tags = {'1': ('hot', '🔥 热门'), '2': ('new', '✨ 最新'),
            '3': ('trend', '📈 趋势'), '4': ('research', '🔬 深度'), '5': ('tool', '🛠️ 工具')}
    print('标签选项: 1=🔥热门 2=✨最新 3=📈趋势 4=🔬深度 5=🛠️工具')
    tag_choice = input_prompt('选择标签', '1')
    tag, tag_label = tags.get(tag_choice, ('new', '✨ 最新'))

    title = input_prompt('资讯标题 (必填)')
    if not title:
        print('❌ 标题不能为空')
        return

    summary = input_prompt('资讯摘要 (必填)')
    if not summary:
        print('❌ 摘要不能为空')
        return

    source = input_prompt('来源媒体', '科技媒体')
    url = input_prompt('原文链接', 'https://juejin.cn')

    # 生成唯一ID
    existing_ids = {n['id'] for n in data['news']}
    idx = 1
    while True:
        new_id = f'news_{TODAY.replace("-","")}_{idx:03d}'
        if new_id not in existing_ids:
            break
        idx += 1

    new_item = {
        'id': new_id,
        'date': TODAY,
        'tag': tag,
        'tag_label': tag_label,
        'title': title,
        'summary': summary,
        'source': source,
        'url': url
    }

    # 插入到最前面
    data['news'].insert(0, new_item)

    # 同时更新滚动条
    short = title[:30] + ('...' if len(title) > 30 else '')
    if short not in data.get('ticker', []):
        data.setdefault('ticker', []).insert(0, short)
        if len(data['ticker']) > 10:
            data['ticker'] = data['ticker'][:10]

    save_data(data)
    print(f'\n✅ 资讯已添加: {title}')

# ==================== 添加学习资源 ====================

def add_resource_interactive():
    data = load_data()
    phases = data.get('learning', {}).get('phases', [])

    print('\n📚 添加学习资源\n' + '-'*40)
    print('可选阶段:')
    for i, p in enumerate(phases):
        res_count = len(p.get('resources', []))
        print(f'  {i}: {p["icon"]} {p["title"]} (已有{res_count}个资源)')

    phase_idx = int(input_prompt('选择阶段 (0-3)', '0'))
    if not 0 <= phase_idx < len(phases):
        print('❌ 无效的阶段编号')
        return

    types = {'1': ('video', '视频'), '2': ('doc', '文档'), '3': ('course', '课程'),
             '4': ('book', '书籍'), '5': ('tool', '工具/代码')}
    print('类型: 1=视频 2=文档 3=课程 4=书籍 5=工具/代码')
    type_choice = input_prompt('选择类型', '1')
    res_type, type_label = types.get(type_choice, ('doc', '文档'))

    icons = {'video': '📹', 'doc': '📄', 'course': '🎓', 'book': '📖', 'tool': '⚙️'}
    default_icon = icons.get(res_type, '📌')

    icon = input_prompt(f'图标 emoji', default_icon)
    title = input_prompt('资源标题 (必填)')
    if not title:
        print('❌ 标题不能为空')
        return

    desc = input_prompt('一句话描述 (必填)')
    if not desc:
        print('❌ 描述不能为空')
        return

    url = input_prompt('链接 URL', 'https://')

    # 生成ID
    existing = {r['id'] for p in phases for r in p.get('resources', [])}
    idx = 1
    while True:
        new_id = f'r{phase_idx}{TODAY.replace("-","")[4:]}{idx:02d}'
        if new_id not in existing:
            break
        idx += 1

    new_res = {
        'id': new_id,
        'icon': icon,
        'title': title,
        'desc': desc,
        'type': res_type,
        'type_label': type_label,
        'url': url,
        'added_date': TODAY
    }

    data['learning']['phases'][phase_idx]['resources'].append(new_res)
    save_data(data)
    print(f'\n✅ 学习资源已添加到阶段{phase_idx}: {title}')

# ==================== 添加项目 ====================

def add_project_interactive():
    data = load_data()

    print('\n🚀 添加实战项目\n' + '-'*40)

    difficulties = {'1': ('beginner', '入门级'), '2': ('medium', '进阶级'), '3': ('advanced', '挑战级')}
    print('难度: 1=🌱入门 2=⚡进阶 3=🔥挑战')
    diff_choice = input_prompt('选择难度', '1')
    difficulty, diff_label = difficulties.get(diff_choice, ('beginner', '入门级'))

    emoji = input_prompt('项目 emoji 图标', '🤖')
    title = input_prompt('项目名称 (必填)')
    if not title:
        print('❌ 名称不能为空')
        return

    desc = input_prompt('项目描述（2-3句话）(必填)')
    if not desc:
        print('❌ 描述不能为空')
        return

    tags_str = input_prompt('技术标签（逗号分隔）', 'Python,AI')
    tags = [t.strip() for t in tags_str.split(',') if t.strip()]

    duration = input_prompt('预计时长', '3-5天')
    highlight = input_prompt('亮点标注', '⭐ 推荐')
    tutorial_url = input_prompt('教程链接', 'https://github.com')
    github_url = input_prompt('代码/参考链接', tutorial_url)

    # 背景颜色随机选一个
    bg_options = [
        'linear-gradient(135deg,#1e3a5f,#1e4080)',
        'linear-gradient(135deg,#3a1e5f,#5020a0)',
        'linear-gradient(135deg,#1e3a3a,#106060)',
        'linear-gradient(135deg,#2a1e1e,#602020)',
        'linear-gradient(135deg,#1a3a1e,#204020)',
        'linear-gradient(135deg,#2a1e3a,#4a1070)',
    ]
    import random
    bg = random.choice(bg_options)

    # cat 字段
    cat_parts = [difficulty]
    if any(kw in desc.lower() or kw in title.lower() for kw in ['图片', '视觉', '视频', 'cv', '分类', '目标检测']):
        cat_parts.append('vision')
    else:
        cat_parts.append('nlp')
    cat = ' '.join(cat_parts)

    # 生成ID
    existing_ids = {p['id'] for p in data.get('projects', [])}
    idx = 1
    while True:
        new_id = f'p{TODAY.replace("-","")[4:]}{idx:02d}'
        if new_id not in existing_ids:
            break
        idx += 1

    new_proj = {
        'id': new_id,
        'emoji': emoji,
        'title': title,
        'difficulty': difficulty,
        'diff_label': diff_label,
        'cat': cat,
        'desc': desc,
        'tags': tags,
        'duration': duration,
        'highlight': highlight,
        'bg': bg,
        'tutorial_url': tutorial_url,
        'github_url': github_url,
        'added_date': TODAY
    }

    data['projects'].append(new_proj)
    save_data(data)
    print(f'\n✅ 项目已添加: {title}')

# ==================== 自动抓取资讯 ====================

def auto_fetch_news():
    """从 GitHub Trending 和 arXiv 抓取今日 AI 资讯（简单版本）"""
    try:
        import urllib.request
        print('\n🌐 自动抓取 GitHub Trending AI 项目...')

        req = urllib.request.Request(
            'https://github.com/trending?since=daily&spoken_language_code=zh',
            headers={'User-Agent': 'Mozilla/5.0'}
        )
        html = urllib.request.urlopen(req, timeout=10).read().decode('utf-8', errors='ignore')

        # 简单提取项目名
        import re
        repos = re.findall(r'href="/([^/]+/[^"]+)"[^>]*>\s*([^<]{5,}?)\s*</a>', html)
        ai_keywords = ['llm', 'gpt', 'ai', 'ml', 'model', 'diffusion', 'transformer', 'agent']
        ai_repos = [(r[0], r[1].strip()) for r in repos if any(k in r[0].lower() for k in ai_keywords)][:5]

        if ai_repos:
            data = load_data()
            added = 0
            for repo_path, _ in ai_repos:
                repo_name = repo_path.strip('/')
                repo_url = f'https://github.com/{repo_name}'
                title = f'GitHub 热门: {repo_name}'

                # 避免重复
                if any(n.get('url') == repo_url for n in data['news']):
                    continue

                existing_ids = {n['id'] for n in data['news']}
                idx = len([n for n in data['news'] if n['date'] == TODAY]) + 1
                new_id = f'news_{TODAY.replace("-","")}_auto_{idx:02d}'

                data['news'].insert(0, {
                    'id': new_id,
                    'date': TODAY,
                    'tag': 'tool',
                    'tag_label': '🛠️ 工具',
                    'title': title,
                    'summary': f'GitHub 今日热门 AI 项目: {repo_name}，正在被开发者广泛关注。',
                    'source': 'GitHub Trending',
                    'url': repo_url
                })
                added += 1

            if added > 0:
                save_data(data)
                print(f'✅ 自动添加了 {added} 条 GitHub Trending AI 资讯')
            else:
                print('ℹ️ 今日资讯已是最新，无需重复添加')
        else:
            print('⚠️ 未抓取到 AI 相关项目，请手动添加')

    except Exception as e:
        print(f'❌ 自动抓取失败: {e}')
        print('💡 建议手动运行: python3 update_content.py news')

# ==================== 主入口 ====================

if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'stats'

    print('🤖 AI学习星球 内容管理工具')

    if cmd == 'stats' or cmd == '':
        print_stats()
        print('\n可用命令:')
        print('  python3 update_content.py news     - 添加资讯')
        print('  python3 update_content.py learn    - 添加学习资源')
        print('  python3 update_content.py project  - 添加项目')
        print('  python3 update_content.py auto     - 自动抓取今日资讯')
    elif cmd == 'news':
        add_news_interactive()
    elif cmd == 'learn':
        add_resource_interactive()
    elif cmd == 'project':
        add_project_interactive()
    elif cmd == 'auto':
        auto_fetch_news()
    else:
        print(f'❌ 未知命令: {cmd}')
        print('使用 python3 update_content.py 查看帮助')
