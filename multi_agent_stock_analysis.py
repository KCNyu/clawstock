#!/usr/bin/env python3
"""
多智能体股票分析系统
Agent 1: 技术分析 (价格、趋势、技术指标)
Agent 2: 基本面分析 (公司信息、财务数据)
Agent 3: 新闻情绪分析
Agent 4: 综合评分与推荐
"""

import requests
import json
from datetime import datetime, timedelta

FINNHUB_API_KEY = 'd6m1kj9r01qu3p05oh6gd6m1kj9r01qu3p05oh70'
ALPHA_VANTAGE_API_KEY = 'KTEYFLXLT8BQFDY7'

class Agent1_TechnicalAnalysis:
    """技术分析智能体"""
    
    def analyze(self, ticker):
        print(f"\n{'='*60}")
        print(f"🤖 Agent 1: 技术分析 - {ticker}")
        print(f"{'='*60}")
        
        # 获取实时报价
        quote_url = f'https://finnhub.io/api/v1/quote?symbol={ticker}&token={FINNHUB_API_KEY}'
        quote_data = requests.get(quote_url).json()
        
        current_price = quote_data.get('c', 0)
        change_pct = quote_data.get('dp', 0)
        high = quote_data.get('h', 0)
        low = quote_data.get('l', 0)
        open_price = quote_data.get('o', 0)
        prev_close = quote_data.get('pc', 0)
        
        # 技术指标分析
        print(f"\n📊 价格数据:")
        print(f"  当前价格: ${current_price:.2f}")
        print(f"  今日涨跌: {change_pct:+.2f}%")
        print(f"  今日区间: ${low:.2f} - ${high:.2f}")
        print(f"  开盘价: ${open_price:.2f}")
        print(f"  昨收: ${prev_close:.2f}")
        
        # 简单趋势判断
        trend = "上涨" if change_pct > 0 else "下跌" if change_pct < 0 else "持平"
        strength = "强" if abs(change_pct) > 2 else "中" if abs(change_pct) > 1 else "弱"
        
        print(f"\n📈 趋势分析:")
        print(f"  短期趋势: {trend} ({strength})")
        print(f"  波动幅度: {((high - low) / low * 100):.2f}%")
        
        # 技术评分 (0-100)
        tech_score = 50  # 基础分
        tech_score += min(change_pct * 5, 20)  # 涨跌贡献
        tech_score = max(0, min(100, tech_score))
        
        print(f"\n⭐ 技术评分: {tech_score:.1f}/100")
        
        return {
            'ticker': ticker,
            'price': current_price,
            'change_pct': change_pct,
            'trend': trend,
            'tech_score': tech_score
        }

class Agent2_FundamentalAnalysis:
    """基本面分析智能体"""
    
    def analyze(self, ticker):
        print(f"\n{'='*60}")
        print(f"🤖 Agent 2: 基本面分析 - {ticker}")
        print(f"{'='*60}")
        
        # 获取公司信息
        profile_url = f'https://finnhub.io/api/v1/stock/profile2?symbol={ticker}&token={FINNHUB_API_KEY}'
        profile_data = requests.get(profile_url).json()
        
        name = profile_data.get('name', 'N/A')
        market_cap = profile_data.get('marketCapitalization', 0)
        industry = profile_data.get('finnhubIndustry', 'N/A')
        
        print(f"\n🏢 公司信息:")
        print(f"  名称: {name}")
        print(f"  行业: {industry}")
        print(f"  市值: ${market_cap:.1f}B")
        
        # 基本面评分
        fundamental_score = 50
        if market_cap > 1000:  # 大市值加分
            fundamental_score += 20
        elif market_cap > 100:
            fundamental_score += 10
        
        print(f"\n⭐ 基本面评分: {fundamental_score:.1f}/100")
        
        return {
            'ticker': ticker,
            'name': name,
            'market_cap': market_cap,
            'industry': industry,
            'fundamental_score': fundamental_score
        }

class Agent3_SentimentAnalysis:
    """新闻情绪分析智能体"""
    
    def analyze(self, ticker):
        print(f"\n{'='*60}")
        print(f"🤖 Agent 3: 新闻情绪分析 - {ticker}")
        print(f"{'='*60}")
        
        # 获取最新新闻
        end_date = datetime.now()
        start_date = end_date - timedelta(days=7)
        
        news_url = f'https://finnhub.io/api/v1/company-news?symbol={ticker}&from={start_date.strftime("%Y-%m-%d")}&to={end_date.strftime("%Y-%m-%d")}&token={FINNHUB_API_KEY}'
        news_data = requests.get(news_url).json()
        
        print(f"\n📰 最新新闻 (过去7天):")
        
        if news_data and len(news_data) > 0:
            # 显示前3条新闻
            for i, news in enumerate(news_data[:3], 1):
                headline = news.get('headline', 'N/A')
                source = news.get('source', 'N/A')
                print(f"  {i}. {headline[:60]}... ({source})")
            
            news_count = len(news_data)
            print(f"\n  共 {news_count} 条新闻")
            
            # 情绪评分 (基于新闻数量)
            sentiment_score = 50 + min(news_count * 2, 30)
        else:
            print("  暂无新闻")
            sentiment_score = 40
        
        print(f"\n⭐ 情绪评分: {sentiment_score:.1f}/100")
        
        return {
            'ticker': ticker,
            'news_count': len(news_data) if news_data else 0,
            'sentiment_score': sentiment_score
        }

class Agent4_Recommendation:
    """综合推荐智能体"""
    
    def analyze(self, ticker, agent1_result, agent2_result, agent3_result):
        print(f"\n{'='*60}")
        print(f"🤖 Agent 4: 综合评分与推荐 - {ticker}")
        print(f"{'='*60}")
        
        # 综合评分 (加权平均)
        tech_weight = 0.4
        fundamental_weight = 0.4
        sentiment_weight = 0.2
        
        total_score = (
            agent1_result['tech_score'] * tech_weight +
            agent2_result['fundamental_score'] * fundamental_weight +
            agent3_result['sentiment_score'] * sentiment_weight
        )
        
        print(f"\n📊 各维度评分:")
        print(f"  技术面: {agent1_result['tech_score']:.1f}/100 (权重 40%)")
        print(f"  基本面: {agent2_result['fundamental_score']:.1f}/100 (权重 40%)")
        print(f"  情绪面: {agent3_result['sentiment_score']:.1f}/100 (权重 20%)")
        
        print(f"\n⭐ 综合评分: {total_score:.1f}/100")
        
        # 推荐等级
        if total_score >= 70:
            recommendation = "强烈推荐 🔥"
            risk_level = "中"
        elif total_score >= 60:
            recommendation = "推荐 👍"
            risk_level = "中"
        elif total_score >= 50:
            recommendation = "中性 😐"
            risk_level = "中高"
        else:
            recommendation = "观望 ⚠️"
            risk_level = "高"
        
        print(f"\n💡 推荐等级: {recommendation}")
        print(f"🎯 风险等级: {risk_level}")
        
        return {
            'ticker': ticker,
            'total_score': total_score,
            'recommendation': recommendation,
            'risk_level': risk_level,
            'price': agent1_result['price'],
            'change_pct': agent1_result['change_pct'],
            'market_cap': agent2_result['market_cap']
        }

def main():
    tickers = ['MSFT', 'GOOGL', 'META', 'PLTR', 'AI']
    
    print("="*60)
    print("🚀 多智能体股票分析系统启动")
    print("="*60)
    print(f"分析时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"目标股票: {', '.join(tickers)}")
    
    agent1 = Agent1_TechnicalAnalysis()
    agent2 = Agent2_FundamentalAnalysis()
    agent3 = Agent3_SentimentAnalysis()
    agent4 = Agent4_Recommendation()
    
    all_results = []
    
    for ticker in tickers:
        print(f"\n\n{'#'*60}")
        print(f"# 开始分析: {ticker}")
        print(f"{'#'*60}")
        
        # 串行执行各个智能体
        result1 = agent1.analyze(ticker)
        result2 = agent2.analyze(ticker)
        result3 = agent3.analyze(ticker)
        result4 = agent4.analyze(ticker, result1, result2, result3)
        
        all_results.append(result4)
    
    # 最终排名
    print(f"\n\n{'='*60}")
    print("📊 最终排名与推荐")
    print(f"{'='*60}\n")
    
    # 按综合评分排序
    all_results.sort(key=lambda x: x['total_score'], reverse=True)
    
    print(f"{'排名':<4} {'股票':<8} {'当前价格':<12} {'涨跌':<10} {'综合评分':<12} {'推荐':<15}")
    print("-" * 80)
    
    for i, result in enumerate(all_results, 1):
        print(f"{i:<4} {result['ticker']:<8} ${result['price']:<11.2f} {result['change_pct']:>+6.2f}%   {result['total_score']:<11.1f} {result['recommendation']:<15}")
    
    print("\n" + "="*60)
    print("✅ 分析完成")
    print("="*60)

if __name__ == '__main__':
    main()
