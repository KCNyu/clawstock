---
layout: default
title: openstock — daily briefs
---

# 📊 openstock

kcn 的 openclaw 投资分析 workspace — harness 化 cron + Tier 3 swarm。
完整 README 在 [README.md](README.html)。

---

## 📅 盘前深度简报 (Daily Deep Brief)

每个工作日 08:00 HKT 自动跑全 swarm 分析 → markdown 落盘 + WeChat 推送。
按日期倒序：

<ul>
{% assign sorted = site.static_files | sort: 'path' | reverse %}
{% for f in sorted %}
  {% if f.path contains '/memory/' and f.extname == '.md' and f.path contains '-pre-open' %}
  <li>
    <a href="{{ f.path | replace: '.md', '.html' }}">{{ f.name | replace: '.md', '' }}</a>
  </li>
  {% endif %}
{% endfor %}
</ul>

## 📝 Daily Notes (kcn 手写笔记)

<ul>
{% for f in sorted %}
  {% if f.path contains '/memory/' and f.extname == '.md' and f.name != '_TEMPLATE.md' %}
    {% unless f.path contains '-pre-open' or f.path contains 'recovery_log' or f.path contains '6_month_review' or f.path contains 'archive_index' %}
  <li>
    <a href="{{ f.path | replace: '.md', '.html' }}">{{ f.name | replace: '.md', '' }}</a>
  </li>
    {% endunless %}
  {% endif %}
{% endfor %}
</ul>

## 📈 历史 plan.json (结构化交易计划)

Self-learning loop 用，给次日 retrospective 算 trigger / P&L / confidence calibration。

<ul>
{% for f in sorted %}
  {% if f.path contains '/memory/' and f.extname == '.json' and f.path contains '-plan' %}
  <li>
    <a href="https://github.com/KCNyu/openstock/blob/master{{ f.path }}">{{ f.name }}</a>
  </li>
  {% endif %}
{% endfor %}
</ul>

## 🛠 Skill bodies

<ul>
{% for f in sorted %}
  {% if f.path contains '/skills/' and f.name == 'SKILL.md' %}
  <li>
    <a href="{{ f.path | replace: '.md', '.html' }}">{{ f.path | replace: '/SKILL.md', '' | replace: '/skills/', '' }}</a>
  </li>
  {% endif %}
{% endfor %}
</ul>

## 📚 Reference docs

- [SOUL](SOUL.html) — Rick 的人格/思考方式
- [USER](USER.html) — kcn profile + 偏好
- [MEMORY](MEMORY.html) — 铁律 + 已知坑
- [TOOLS](TOOLS.html) — 全部脚本 / fallback / skill 路由 / cron map
- [INVESTMENT_SOP](INVESTMENT_SOP.html) — 投资问题启动顺序
- [AGENTS](AGENTS.html) — openclaw 入口
- [CLAUDE](CLAUDE.html) — Claude Code 入口
- [IDENTITY](IDENTITY.html) — Rick 是谁

---

## Disclaimer

This repo contains real trading positions and analysis. **Not investment advice.**
All numbers are point-in-time. Past performance does not guarantee future results.
The model (Rick) is opinionated by design — that doesn't mean it's right.
