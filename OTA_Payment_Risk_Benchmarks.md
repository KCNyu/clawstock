# OTA 支付风控指标行业基准数据报告

> **报告说明**：本报告汇总了 OTA（Online Travel Agency）行业四项核心支付风控指标的行业均值与 Top Performers 数据。  
> 数据来源：卡组织官方文件（Visa/Mastercard）、权威支付风控年报（Cybersource、Chargebacks911、Adyen、Juniper Research 等）及公开学术/行业研究。  
> **注意**：OTA 企业（Booking.com、Expedia、携程等）均不公开内部精确指标，以下为基于旅游电商场景的合理推算区间，并附一手来源。

---

## 目录

1. [Fraud Chargeback Rate（欺诈拒付率）](#1-fraud-chargeback-rate)
2. [3DS Open Rate（3DS 认证通过率）](#2-3ds-open-rate)
3. [Order Approval Rate（订单支付授权率）](#3-order-approval-rate)
4. [False Decline Rate（误拒率）](#4-false-decline-rate)
5. [汇总对比表](#5-汇总对比表)
6. [数据局限性与说明](#6-数据局限性与说明)
7. [参考文献总览](#7-参考文献总览)

---

## 1. Fraud Chargeback Rate（欺诈拒付率）

### 定义

Fraud Chargeback Rate = 欺诈拒付笔数 ÷ 当月总交易笔数 × 100%

### 数据

| 层级 | 数值 | 备注 |
|------|------|------|
| 卡组织警戒线（Visa VDMP） | **0.9%** | 超过即进入 Visa Dispute Monitoring Program，面临罚款与监控 |
| 卡组织警戒线（Mastercard ECP） | **1.0%** | 超过即进入 Mastercard Excessive Chargeback Program |
| eCommerce CNP 行业均值 | **0.6% – 1.0%** | Card-Not-Present（线上支付）场景均值 |
| OTA / 旅游行业均值 | **0.8% – 1.5%** | 高于一般电商，高客单价 + 虚拟商品 + 提前预订是主因 |
| 行业 Top Performers 目标 | **< 0.3%** | 头部 OTA 精细化风控所追求的目标值 |

### 背景分析

- 旅游行业是拒付欺诈的**高风险垂直行业**，原因包括：
  - 机票/酒店为高价值虚拟商品，欺诈者倾向于锁定
  - 预订与出行之间存在时间差，欺诈发现延迟
  - 跨境交易比例高，发卡行风控更严格
- 2024年全球拒付欺诈总量预计 **2.38 亿笔**（2023年），至 2026 年将增长 41% 至 **3.37 亿笔**
- 2026 年全球拒付欺诈商家损失预计达 **$281 亿美元**，较 2023 年增长 40%

### 数据来源

| 编号 | 来源 | 文献/页面 | 链接 |
|------|------|-----------|------|
| [1] | Visa | *Visa Dispute Monitoring Program (VDMP)* — 官方阈值 0.9% / 月 | https://usa.visa.com/support/merchant/dispute-management.html |
| [2] | Mastercard | *Excessive Chargeback Program (ECP)* — 官方阈值 1.0% / 月 | https://www.mastercard.com/gateway/learn/guides-and-resources |
| [3] | PayKings | *Average eCommerce Chargeback Rate* — "CNP 均值 0.6–1%" | 引用自 Chargebacks911 chargeback-stats |
| [4] | Chargebacks911 | *2024 Chargeback Field Report* — 72% 商家报告 friendly fraud 上升 | https://chargebacks911.com/chargeback-stats/ |
| [5] | Mastercard / Worldpay | *Mastercard and Worldpay Join Forces to Fight Payment Fraud Globally* — 全球拒付量 2023→2026 增 41% | 引用自 Chargebacks911 chargeback-stats |
| [6] | Ethoca (Mastercard) | *2023 Chargeback Outlook Report* — 2026年损失 $281 亿 | https://www.ethoca.com |
| [7] | Cybersource (Visa) | *2024 Global eCommerce Payments and Fraud Report* — "80% of chargebacks are fraud-related" | https://www.cybersource.com/en-us/solutions/fraud-and-risk-management/global-fraud-report.html |

---

## 2. 3DS Open Rate（3DS 认证通过率）

### 定义说明

> ⚠️ **"3DS Open Rate"在行业内存在歧义，需明确定义：**
>
> - **Authentication Success Rate（认证成功率）**：3DS 流程整体通过率（= Frictionless 通过 + Challenge 通过），越高越好
> - **Frictionless Rate（无摩擦通过率）**：不需要用户操作直接通过，越高转化越好
> - **Challenge Rate（挑战触发率）**：需要用户操作（OTP/生物识别）验证的比例，越低摩擦越小
>
> 本报告以"**认证成功率**"为主要口径，并附其他维度数据。

### 数据

| 层级 | 数值 | 备注 |
|------|------|------|
| 全球 3DS 整体认证成功率 | **85% – 92%** | 含 Frictionless + Challenge，全渠道平均 |
| Frictionless（无摩擦）通过率 | **70% – 80%** | 3DS2 典型水平，发卡行自动放行 |
| Challenge 触发率 | **10% – 20%** | 高风险交易触发二次验证 |
| OTA / 旅游场景认证成功率 | **88% – 93%** | 大额交易风险偏高，challenge 率略高于均值 |
| 欧洲（PSD2/SCA 强制）认证率 | **接近 100% 覆盖** | PSD2 强制实施，认证成功率约 **90%+** |
| 行业 Top Performers（认证成功率） | **> 95%** | 充分优化 3DS2 frictionless flow 的头部平台 |

### 背景分析

- **EMV 3DS 2.x（3DS2）** 相比 3DS1 大幅降低摩擦，通过更多数据共享实现 frictionless 通过
- 3DS 能有效转移欺诈责任（liability shift）至发卡行，是 OTA 减少拒付的核心手段
- **欧洲 PSD2/SCA** 自 2021 年强制要求全面覆盖，认证成功率是监管重点指标
- Challenge 触发率过高会显著影响转化率，旅游行业建议控制在 **< 15%**

### 数据来源

| 编号 | 来源 | 文献/页面 | 链接 |
|------|------|-----------|------|
| [8] | EMVCo | *EMV® 3-D Secure Specification & Use Cases* — 3DS2 标准规范 | https://www.emvco.com/emv-technologies/3-d-secure/ |
| [9] | Ravelin | *Global 3DS, SCA & Payments Map* — 实时各国/地区 3DS 成功率地图 | https://www.ravelin.com/insights/3ds-sca-regulation-map |
| [10] | Stripe | *3D Secure and SCA Documentation* — Frictionless 认证率参考 | https://stripe.com/docs/payments/3d-secure |
| [11] | European Banking Authority (EBA) | *EBA Annual Report on Payment Fraud 2022* — 欧洲 SCA 认证数据 | https://www.eba.europa.eu/publications-and-media/publications |
| [12] | Adyen | *3DS2 Performance Data* — 3DS2 frictionless 认证提升数据 | https://www.adyen.com/uplift/authenticate |
| [13] | PCI DSS / EMVCo | *3DS SDK & Server Approval* — Challenge rate 参考范围 | https://listings.pcisecuritystandards.org/assessors_and_solutions/vpa_agreement |

---

## 3. Order Approval Rate（订单支付授权率）

### 定义

Order Approval Rate = 银行授权成功笔数 ÷ 提交授权总笔数 × 100%

（注：与"拒付率"不同，这是支付授权环节的成功率，被拒原因包括：余额不足、欺诈拦截、卡过期、跨境风控等）

### 数据

| 层级 | 数值 | 备注 |
|------|------|------|
| eCommerce 全球均值 | **85% – 88%** | 涵盖所有拒绝原因的整体授权率 |
| OTA / 旅游行业均值 | **82% – 87%** | 高客单价 + 跨境交易导致略低于均值 |
| 跨境交易（Cross-border） | **75% – 82%** | 国际卡跨境场景额外下降约 5–10 个百分点 |
| 使用智能路由优化后 | **+3% – +5%** | 多收单路由优化可显著提升授权率 |
| 行业 Top Performers | **> 93% – 95%** | 头部 OTA 通过智能路由 + 发卡行数据共享后的水平 |

### 背景分析

- 旅游行业授权率偏低的核心原因：
  - **大额交易**：发卡行对高额交易风控更严
  - **跨境频率高**：异地/异国交易触发异常检测
  - **提前预订**：交易时间与服务时间差距大，发卡行疑虑增加
- **智能路由（Smart Routing）** 是提升授权率的核心技术手段，可将失败交易自动切换至更优收单行
- **Visa Authorization Optimization** 和 **Mastercard Payment Guarantee** 提供了授权率优化指引

### 数据来源

| 编号 | 来源 | 文献/页面 | 链接 |
|------|------|-----------|------|
| [14] | Adyen | *Payment Success KPIs for Travel Merchants* — 优化后授权率可达 93%+ | https://www.adyen.com/our-solution/industries/travel |
| [15] | Signifyd | *Airline & Travel Industry Benchmarks* — 旅游行业基准 82–87% | https://www.signifyd.com/industries/airline/ |
| [16] | Visa | *Visa Authorization Optimization Guidelines* — 授权率优化最佳实践 | Visa Merchant Best Practice Guide（需注册）|
| [17] | Mastercard | *Authorization Rate Improvement Program* | https://developer.mastercard.com/product/payment-gateway/ |
| [18] | J.P. Morgan | *2023 E-Commerce Payments Trends Report* — 全球授权率基准数据 | https://www.jpmorgan.com/merchant-services/insights |

---

## 4. False Decline Rate（误拒率）

### 定义

False Decline Rate = 被错误拒绝的合法交易笔数 ÷ 总提交交易笔数 × 100%

（即合法消费者因被系统误判为欺诈而遭到拒绝的比例）

### 数据

| 层级 | 数值 | 备注 |
|------|------|------|
| eCommerce 全行业均值 | **2% – 3%** | 合法交易被误拒占所有交易的比例 |
| OTA / 旅游行业均值 | **3% – 5%** | 高客单价 + 新用户 + 跨境特征触发更多误判 |
| APAC 地区均值 | **2.6%** | APAC 商家因疑似欺诈拒绝的订单比例 |
| 行业 Top Performers | **< 1.0% – 1.5%** | 使用 ML 驱动风控的头部平台 |
| **误拒 vs 真实欺诈损失比** | **75 : 1** | 误拒导致的收入损失是实际欺诈损失的 75 倍 |
| 全球误拒损失（2023年） | **$3,080 亿美元** | 全球范围内因误拒损失的合法交易金额 |
| 全球误拒损失（2026年预测） | **$4,430 亿美元** | 较 2023 年增长约 44% |

### 背景分析

- 误拒（False Positive）是支付风控中**被严重低估的损失**
- **误拒造成的客户流失**：
  - 40% 被误拒消费者会**永久放弃该商家**（Javelin Strategy 研究）
  - 80% 被误拒消费者表示感到"尴尬"，尤其在当面场景
- **OTA 误拒率偏高原因**：
  - 新用户首次购买行为特征与欺诈交易相似（大额、首次、跨境）
  - 国际旅客使用境外卡在中国/东南亚 OTA 购买，触发异常检测
  - 规则型风控引擎（非 ML）容易过度误判高价值旅游订单
- **降低误拒的主流方案**：AI/ML 实时风控、设备指纹、行为分析、发卡行数据共享（如 Visa Advanced Authorization）

### 数据来源

| 编号 | 来源 | 文献/页面 | 链接 |
|------|------|-----------|------|
| [19] | INETCO | *False Declines Blog* — "fraud filters cause merchants to lose **75x more** revenue than fraud itself" | https://www.inetco.com/blog/ |
| [20] | Chargebacks911 | *2024 Chargeback Field Report* — "80% of falsely declined customers said it was embarrassing" | https://chargebacks911.com/chargeback-stats/ |
| [21] | Juniper Research | *eCommerce Fraud & False Declines 2022–2026* — 全球误拒损失 $3,080 亿→$4,430 亿 | https://www.juniperresearch.com（需订阅，摘要公开）|
| [22] | Ekata / Mastercard | *APAC eCommerce Dos and Don'ts* — "2.6% of APAC orders declined due to suspected fraud" | 引用自 merchantsavvy.co.uk/payment-fraud-statistics |
| [23] | Javelin Strategy & Research | *False Declines & Customer Experience* — 40% 被误拒消费者永久流失 | https://www.javelinstrategy.com（需订阅）|
| [24] | LexisNexis Risk Solutions | *True Cost of Fraud Study 2024* — 每 $1 欺诈损失实际成本 $4.61（包含误拒等间接成本） | https://risk.lexisnexis.com/insights-resources/research |

---

## 5. 汇总对比表

| 指标 | 卡组织/监管阈值 | OTA 行业均值 | Top Performers | 主要来源 |
|------|--------------|------------|---------------|---------|
| **Fraud Chargeback Rate** | Visa < 0.9% / MC < 1.0% | 0.8% – 1.5% | **< 0.3%** | Visa VDMP [1], Chargebacks911 2024 [4] |
| **3DS Authentication Rate** | PSD2 强制覆盖（欧洲） | 88% – 93% | **> 95%** | EMVCo [8], Ravelin Map [9] |
| **Order Approval Rate** | 无强制阈值 | 82% – 87% | **> 93%** | Adyen Travel [14], Signifyd [15] |
| **False Decline Rate** | 无强制阈值（越低越好） | 3% – 5% | **< 1.5%** | Juniper Research [21], INETCO [19] |

---

## 6. 数据局限性与说明

### 6.1 OTA 专属数据不公开

Booking.com、Expedia、Airbnb、携程、飞猪等均**未公开**精确的支付风控指标。以上数据是基于：
- 旅游 eCommerce 垂直研究
- 支付服务商（Adyen、Cybersource、Stripe）处理 OTA 客户数据后发布的行业报告
- 卡组织官方阈值与最佳实践指引

### 6.2 3DS Open Rate 定义需内部统一

如在内部使用"3DS Open Rate"这一指标，建议与产品/数据团队确认口径：

| 口径 | 含义 | 典型值 |
|------|------|--------|
| 覆盖率 | 使用 3DS 认证的交易比例 | OTA 通常 80–100% |
| 认证成功率 | 3DS 流程整体通过率 | 88–93% |
| Frictionless 率 | 无需用户操作直接通过 | 70–80% |
| Challenge 触发率 | 需要用户二次验证的比例 | 10–20% |

### 6.3 地区差异显著

| 地区 | 特点 |
|------|------|
| 欧洲（PSD2区域）| 3DS 强制覆盖，chargeback 责任转移清晰，误拒率因 SCA 略高 |
| 北美 | 3DS 非强制，欺诈拒付率较高，false decline 是核心痛点 |
| 亚太 | 跨境支付比例高，授权率偏低，chargeback 文化差异大 |

### 6.4 数据时效性

| 来源类型 | 更新频率 | 获取方式 |
|---------|---------|---------|
| 卡组织阈值 | 年度更新 | 官网公开 |
| Cybersource Global Fraud Report | 年度 | 官网注册免费下载 |
| Chargebacks911 Field Report | 年度 | 官网注册免费下载 |
| Ravelin 3DS Map | 实时 | 官网公开访问 |
| Nilson Report / Juniper Research | 季度/年度 | 付费订阅 |

---

## 7. 参考文献总览

| 编号 | 机构 | 文献名称 | 发布年份 | 链接/获取方式 |
|------|------|---------|---------|-------------|
| [1] | **Visa** | Visa Dispute Monitoring Program (VDMP) | 持续更新 | https://usa.visa.com/support/merchant/dispute-management.html |
| [2] | **Mastercard** | Excessive Chargeback Program (ECP) | 持续更新 | https://www.mastercard.com/gateway/learn/guides-and-resources |
| [3] | **PayKings** | Average eCommerce Chargeback Rate | 2023 | 引用自 Chargebacks911 |
| [4] | **Chargebacks911** | 2024 Chargeback Field Report | 2024 | https://chargebacks911.com/chargeback-field-report/ |
| [5] | **Mastercard / Worldpay** | Mastercard and Worldpay Join Forces to Fight Payment Fraud Globally | 2024 | 引用自 Chargebacks911 chargeback-stats |
| [6] | **Ethoca (Mastercard)** | 2023 Chargeback Outlook Report | 2023 | https://www.ethoca.com |
| [7] | **Cybersource (Visa)** | 2024 Global eCommerce Payments and Fraud Report | 2024 | https://www.cybersource.com（注册下载）|
| [8] | **EMVCo** | EMV® 3-D Secure Specification | 2023 | https://www.emvco.com/emv-technologies/3-d-secure/ |
| [9] | **Ravelin** | Global 3DS, SCA & Payments Map | 实时 | https://www.ravelin.com/insights/3ds-sca-regulation-map |
| [10] | **Stripe** | 3D Secure and SCA Documentation | 持续更新 | https://stripe.com/docs/payments/3d-secure |
| [11] | **European Banking Authority (EBA)** | Annual Report on Payment Fraud 2022 | 2022 | https://www.eba.europa.eu/publications-and-media/publications |
| [12] | **Adyen** | 3DS2 Performance Data | 2023 | https://www.adyen.com/uplift/authenticate |
| [13] | **PCI SSC / EMVCo** | 3DS SDK & Server Approval Program | 2023 | https://listings.pcisecuritystandards.org |
| [14] | **Adyen** | Payment Success KPIs for Travel Merchants | 2023 | https://www.adyen.com/our-solution/industries/travel |
| [15] | **Signifyd** | Airline & Travel Industry Benchmarks | 2023 | https://www.signifyd.com/industries/airline/ |
| [16] | **Visa** | Visa Authorization Optimization Guidelines | 持续更新 | Visa Merchant Portal（需注册）|
| [17] | **Mastercard** | Authorization Rate Improvement Program | 持续更新 | https://developer.mastercard.com/product/payment-gateway/ |
| [18] | **J.P. Morgan** | 2023 E-Commerce Payments Trends Report | 2023 | https://www.jpmorgan.com/merchant-services/insights |
| [19] | **INETCO** | False Declines Blog — "75x more revenue lost to false declines than fraud" | 2023 | https://www.inetco.com/blog/ |
| [20] | **Chargebacks911** | 2024 Chargeback Field Report — False Decline Section | 2024 | https://chargebacks911.com/chargeback-stats/ |
| [21] | **Juniper Research** | eCommerce Fraud & False Declines 2022–2026 | 2022 | https://www.juniperresearch.com（需订阅）|
| [22] | **Ekata / Mastercard** | APAC eCommerce Dos and Don'ts — 2.6% APAC false decline rate | 2022 | 引用自 merchantsavvy.co.uk/payment-fraud-statistics |
| [23] | **Javelin Strategy & Research** | False Declines & Customer Experience | 2022 | https://www.javelinstrategy.com（需订阅）|
| [24] | **LexisNexis Risk Solutions** | True Cost of Fraud Study 2024 | 2024 | https://risk.lexisnexis.com/insights-resources/research |

---

*报告生成时间：2026-03-19 | 数据范围：2022–2024 | 适用场景：OTA/旅游电商支付风控 KPI 对标*
