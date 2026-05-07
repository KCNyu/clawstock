# Scrapling Web Scraping

## 简介

[Scrapling](https://github.com/D4Vinci/Scrapling) 是一个自适应 Web 爬虫框架，能自动适应网站结构变化、支持绕过反爬（Cloudflare Turnstile 等），从单次请求到大规模爬取均可。

**安装：** `pip3 install scrapling --break-system-packages`（依赖：playwright, browserforge, patchright, msgspec）

## 核心 API

### Fetcher 类（静态爬取，快速但无 JS 支持）

```python
from scrapling.fetchers import Fetcher
p = Fetcher.get('https://example.com')
title = p.css('h1::text').get()
links = p.css('a::attr(href)').getall()
```

### StealthyFetcher（绕过反爬，支持 JS 渲染）

```python
from scrapling.fetchers import StealthyFetcher
sp = StealthyFetcher.fetch('https://example.com', headless=True)
title = sp.css('h1::text').get()
text = sp.css('p::text').get()
href = sp.css('a::attr(href)').get()
```

参数：
- `headless=True`：无头浏览器模式
- `network_idle=True`：等待网络空闲
- `adaptive=True`：自适应网站结构变化

### CSS 选择器

```python
# 获取文本
p.css('h1::text').get()          # 单个值
p.css('p::text').getall()        # 全部

# 获取属性
p.css('a::attr(href)').get()     # 获取 href 属性

# 选择特定元素
p.css('.product')[0]             # 第一个
p.css('#id')                     # 按 id
p.css('.product h2')             # 嵌套

# 按内容过滤
p.css('h1:contains("Phone")::text').get()
```

### XPath 选择器

```python
title = p.xpath('//h1//text()').get()
p.xpath('//*[@class="product"]')
p.xpath('//a/@href')
```

### 链式选择

```python
p.css('.product')[0].css('h2::text').get()
p.xpath('//div')[0].css('span::text').get()
```

### 自适应模式（网站结构变化时仍能找到元素）

```python
# 第一次抓取时保存选择器映射
products = page.css('.product', auto_save=True)
# 之后网站改版，加 adaptive=True 自动适应
products = page.css('.product', adaptive=True)
```

### Spider 框架（大规模爬取）

```python
from scrapling.spiders import Spider, Response

class MySpider(Spider):
    name = "demo"
    start_urls = ["https://example.com/"]

    async def parse(self, response: Response):
        for item in response.css('.product'):
            yield {"title": item.css('h2::text').get()}

MySpider().start()
```

## 常用模式

```python
# 简单静态页面
from scrapling.fetchers import Fetcher
p = Fetcher.get('https://example.com')
print(p.css('title::text').get())

# 有反爬的动态页面
from scrapling.fetchers import StealthyFetcher
sp = StealthyFetcher.fetch(url, headless=True, network_idle=True)

# POST 请求
p = Fetcher.post('https://example.com/api', json={'key': 'value'})

# 带 Header
from scrapling.fetchers import Fetcher
p = Fetcher.configure(headers={'User-Agent': '...'}).get('https://example.com')
```

## 适用场景

- 普通 `requests` / `urllib` 拿不到数据的页面（有 JS 渲染或反爬）
- 需要绕过 Cloudflare Turnstile 等反爬机制
- 网站结构可能变化，需要自适应能力
- 需要大规模爬取（Spider 框架支持并发、暂停恢复、代理轮换）

## 注意事项

- `StealthyFetcher` 速度最慢（需要启动浏览器），非必要不用
- `Fetcher`（静态）最快，但只适合纯 HTML 页面
- 港股/美股行情页面优先用东方财富 API 或 `qt.gtimg.cn`，Scrapling 作为备选
- 大规模爬取注意 `robots.txt` 和网站 `robots` 规则