# Session: 2026-04-07 13:49:40 UTC

- **Session Key**: agent:main:openclaw-weixin:direct:o9cq80-hgtrum-oss8knmdotlvzi@im.wechat
- **Session ID**: a0fc1104-6cb8-43cf-9c01-d8e6623f3525
- **Source**: openclaw-weixin

## Conversation Summary

user: Skills store policy (operator configured):
1. For skills discovery/install/update, try `skillhub` first (cn-optimized).
2. If unavailable, rate-limited, or no match, fallback to `clawhub` (public-registry).
3. Do not claim exclusivity. Public and private registries are both allowed.
4. Before installation, summarize source, version, and notable risk signals.
5. For search requests, execute `exec` with `skillhub search <keywords>` first and report the command output.
6. In the current session, reply directly. Do NOT call `message` tool just to send progress updates.

A new session was started via /new or /reset. Run your Session Startup sequence - read the required files before responding to the user. Then greet the user in your configured persona, if one is provided. Be yourself - use your defined voice, mannerisms, and mood. Keep it to 1-3 sentences and ask what they want to do. If the runtime model differs from default_model in the system prompt, mention the default model. Do not mention internal steps, files, tools, or reasoning.
Current time: Tuesday, April 7th, 2026 - 7:53 PM (Asia/Shanghai) / 2026-04-07 11:53 UTC
assistant: [[reply_to_current]] 晚上好，kcn。我是 Rick 📈，今天也能陪你盯盘、拆持仓、找机会。你想先看哪个，持仓、某只票，还是节后怎么操作？
user: Skills store policy (operator configured):
1. For skills discovery/install/update, try `skillhub` first (cn-optimized).
2. If unavailable, rate-limited, or no match, fallback to `clawhub` (public-registry).
3. Do not claim exclusivity. Public and private registries are both allowed.
4. Before installation, summarize source, version, and notable risk signals.
5. For search requests, execute `exec` with `skillhub search <keywords>` first and report the command output.
6. In the current session, reply directly. Do NOT call `message` tool just to send progress updates.

Conversation info (untrusted metadata):
```json
{
  "message_id": "openclaw-weixin:1775562866030-d06b61b3",
  "timestamp": "Tue 2026-04-07 19:54 GMT+8"
}
```

你帮我看看larkbot的长连接有没有什么方法可以独占，就是go的sdk相关的。我经常发现多个pod会混乱。不能用redis，因为我有多个不同的测试集群。
assistant: [[reply_to_current]] 有，而且关键点其实是个坏消息: **Lark/飞书长连接本身不是广播模式，而是 cluster mode**。同一个 app 起多个长连接客户端时，事件会被平台**随机投递给其中一个连接**，不是每个 pod 都收到，也不是有顺序保证，所以你看到“多个 pod 混乱”很像是这个机制本身导致的。

我查到的官方描述里有两句很关键:

- 每个应用最多 50 个连接
- **同一应用部署多个客户端时，只有随机一个客户端会收到消息**
- 官方还明确说 **does not support broadcasting**

这意味着:

1. **你没法靠 Go SDK 开一个“官方独占锁”**
   SDK 里的 `ws.NewClient(...).Start(...)` 只是建连接收事件，没有内建 leader election / single consumer lease 这种能力。

2. **多个 pod 同时连同一个 Lark app，本质上就是竞争消费**
   不是 Redis 问题，是上游分发模型就这样。即使不用 Redis，只要多 pod 都连，都会乱:
   - 某条消息到 A pod
   - 下一条消息到 B pod
   - 状态/会话如果在本地内存里，就会错乱
   - 如果有 reply / ack / session cache，本地状态更容易撕裂

---

### 你要的“独占”，现实里可行的方案

#### 方案 1，最推荐: **Kubernetes lease 做单活**
不用 Redis，也适合多个测试集群，因为 **锁在各自集群内部**，天然隔离。

做法:
- 所有 pod 都启动
- 只有拿到 `coordination.k8s.io/v1 Lease` 的 pod 才启动 Lark WS client
- 其他 pod 只做 standby，不连 Lark
- leader 挂了，其他 pod 抢占 lease，接管连接

这基本是最干净的办法。

Go 里直接用 client-go 的 leader election:
- `k8s.io/client-go/tools/leaderelection`
- `k8s.io/client-go/tools/leaderelection/resourcelock`

伪代码大概这样:

```go
lec, _ := leaderelection.NewLeaderElector(leaderelection.LeaderElectionConfig{
    Lock: lock,
    LeaseDuration: 15 * time.Second,
    RenewDeadline: 10 * time.Second,
    RetryPeriod:   2 * time.Second,
    Callbacks: leaderelection.LeaderCallbacks{
        OnStartedLeading: func(ctx context.Context) {
            go startLarkWS(ctx)
        },
        OnStoppedLeading: func() {
            stopLarkWS()
        },
    },
})
lec.Run(ctx)
```

**优点**
- 不需要 Redis
- 每个测试集群独立选主，不互相污染
- 最符合你现在的约束

**注意**
- `startLarkWS` 必须可停止，可重连
- pod 失去 leader 后要立刻断开 WS，不然会双活一小段时间

---

#### 方案 2: **每个环境 / 每个集群用不同 Lark app**
如果你有很多测试集群，而且它们都在消费同一类事件，这其实更稳。

比如:
- prod -> 一个 app
- staging -> 一个 app
- test-a -> 一个 app
- test-b -> 一个 app

这样不是“独占”，而是**从源头隔离事件流**。

**优点**
- 最彻底，不会串流
- 调试简单

**缺点**
- 运维成本高
- 需要多套 app 配置和发布

如果你现在多个测试集群经常互相影响，我其实挺建议至少把 **prod / non-prod** 拆开。

---

#### 方案 3: **单独做一个 lark-gateway / adapter 服务**
让整个集群里只有一个 deployment 专门连 Lark WS，然后把事件转发到内部服务:
- HTTP
- NATS
- Kafka
- gRPC stream
- 或你自己的内部队列

这样业务 pod 不直接连 Lark。

**优点**
- Lark 长连接和业务解耦
- 更容易做幂等、日志、重试、观测

**缺点**
- 架构更重

如果你现在已经有“多个 pod 都直接起 Go SDK client”，我会认为这是容易出问题的拓扑。

---

### 不太建议的路子

#### 1. 用数据库表做分布式锁
能做，但不如 K8s Lease 自然。除非你本来就跨 Kubernetes / 跨机器 / 跨平台混合部署。

#### 2. SDK 层面自己赌“只起一个连接”
比如用 Deployment replicas=1。
这对单环境可行，但一旦 HPA、重启、滚动发布、误扩容，就会重新踩坑。

#### 3. 多 pod 都连，然后靠事件幂等解决
这只能解决“重复处理”，**解决不了随机路由 + 本地会话状态分裂**。如果你的 bot 有上下文、缓存、reply 关联，这条路会一直疼。

---

### 我给你的结论

如果你问的是 **“go 的 lark sdk 有没有内建独占长连接的方法”**，我的判断是:

**没有真正的 SDK 级独占。**
官方长连接模型就是多连接随机分发，不提供单消费者锁。
所以独占要在 **Lark SDK 外面做**。

**最佳实践建议:**
1. **首选 K8s Lease 选主，只有 leader pod 建立长连接**
2. 非生产环境尽量 **按集群拆分 app**
3. 如果规模再大，抽一个 **单独的 Lark ingress service**

---

如果你愿意，我下一条可以直接给你一份 **Go + client-go leader election + larksuite/oapi-sdk-go/v3** 的可落地代码骨架。
user: Skills store policy (operator configured):
1. For skills discovery/install/update, try `skillhub` first (cn-optimized).
2. If unavailable, rate-limited, or no match, fallback to `clawhub` (public-registry).
3. Do not claim exclusivity. Public and private registries are both allowed.
4. Before installation, summarize source, version, and notable risk signals.
5. For search requests, execute `exec` with `skillhub search <keywords>` first and report the command output.
6. In the current session, reply directly. Do NOT call `message` tool just to send progress updates.

Conversation info (untrusted metadata):
```json
{
  "message_id": "openclaw-weixin:1775563027788-8b496598",
  "timestamp": "Tue 2026-04-07 19:57 GMT+8"
}
```

不行，那就还是说没办法做独占
assistant: [[reply_to_current]] 对，**如果限定在 Lark/飞书长连接 + Go SDK 这一层，本身没办法做“平台保证的独占”**。

更准确地说是:

- **SDK 没有内建独占机制**
- **平台分发是多连接随机投递，不是单消费者锁**
- 所以只要多个 pod 同时连同一个 app，就**不能指望它天然独占**

所以你可以直接把结论说成:

**飞书/Lark 的长连接模式本身不支持独占消费，Go SDK 也没有提供 leader lock 或 single-active-consumer 能力。多个 pod 同时连接同一个 app 时，事件会随机落到某一个连接上，因此无法在 SDK 层实现严格独占。**

如果你要，我可以顺手帮你把这句话润成一段更适合发给同事/写到设计文档里的版本。
user: Skills store policy (operator configured):
1. For skills discovery/install/update, try `skillhub` first (cn-optimized).
2. If unavailable, rate-limited, or no match, fallback to `clawhub` (public-registry).
3. Do not claim exclusivity. Public and private registries are both allowed.
4. Before installation, summarize source, version, and notable risk signals.
5. For search requests, execute `exec` with `skillhub search <keywords>` first and report the command output.
6. In the current session, reply directly. Do NOT call `message` tool just to send progress updates.

Conversation info (untrusted metadata):
```json
{
  "message_id": "openclaw-weixin:1775563078683-a080fee3",
  "timestamp": "Tue 2026-04-07 19:57 GMT+8"
}
```

为什么会这样子，按理说这个应该是一个比较基础的诉求。还是说一般会用webhook的方法
assistant: [[reply_to_current]] 对，我也觉得这诉求很基础，但飞书这套长连接的设计目标，和你想要的“独占消费”其实不是一回事。

本质上它更像是:

- **降低接入门槛**，让你不用公网 webhook
- **方便本地开发/单实例部署**
- **给你一个能收事件的持久连接**

而不是给你做:
- 消费组
- leader election
- 分区顺序
- 单活保证

所以它才会做成这种 **cluster mode + 随机投递一个连接** 的模型。平台只负责“把事件送到某个活着的客户端”，不负责“帮你在多实例之间维持一致性”。

### 为什么会这样
因为一旦平台要支持“独占 + 故障切换 + 顺序 + 租约”，它本质上就不再只是一个 SDK 长连接了，而是接近消息队列语义了，复杂度会高很多:
- 谁是 leader
- leader 挂了多久切
- 未 ack 消息怎么重投
- 顺序怎么保证
- 网络抖动时算不算失联

飞书显然不想在事件订阅这层做这么重。

### 一般是不是会用 webhook
**对，生产里更常见的还是 webhook。**

因为 webhook 的典型架构是:
- 平台推到你的一个固定入口
- 入口后面挂 LB / Ingress
- 你自己做幂等、队列、消费、单活、重试

这样“多 pod 混乱”问题就会变成你自己系统内部的问题，而不是 SDK 长连接层的问题。可控性高很多。

### 但 webhook 也不是天然独占
这点要分清:
- **webhook 更适合多实例**
- 但 **webhook 也不会自动给你独占**

它只是更容易接入你自己的基础设施，比如:
- Ingress + deployment
- 收到 webhook 后先进 Kafka / SQS / NSQ / DB
- 后面再单消费者处理

### 为什么很多人还是用长连接
因为它真的省事:
- 不要公网域名
- 不要签名校验/回调配置那一套
- 本地就能跑
- 单 pod bot 场景很舒服

所以它特别适合:
- 开发环境
- 小团队内部工具
- 单实例机器人

但一到 **多副本、高可用、状态一致性**，它就开始露馅了。

### 一句话总结
**长连接模式解决的是“怎么方便收到事件”，不是“怎么在分布式系统里稳定独占消费事件”。**
要后者，一般就会回到:
- webhook + 自己的分发层
或者
- 长连接外面再包一层 leader election

如果你愿意，我可以继续帮你拆一下:
**“飞书 bot 场景下，webhook 为什么比长连接更适合 k8s 多 pod”**
我可以直接给你一个架构图式的说明。
user: Skills store policy (operator configured):
1. For skills discovery/install/update, try `skillhub` first (cn-optimized).
2. If unavailable, rate-limited, or no match, fallback to `clawhub` (public-registry).
3. Do not claim exclusivity. Public and private registries are both allowed.
4. Before installation, summarize source, version, and notable risk signals.
5. For search requests, execute `exec` with `skillhub search <keywords>` first and report the command output.
6. In the current session, reply directly. Do NOT call `message` tool just to send progress updates.

Conversation info (untrusted metadata):
```json
{
  "message_id": "openclaw-weixin:1775563105013-0cdfcab0",
  "timestamp": "Tue 2026-04-07 19:58 GMT+8"
}
```

因为pod有时候死亡的时候没办法直接close掉，导致一直还在
assistant: [[reply_to_current]] 对，这就是长连接模式在 K8s 里最烦的点之一，我觉得你这个判断是对的。

问题本质是:

- pod 死了，不一定有机会执行优雅退出
- 所以 SDK 也来不及 `close()`
- 平台那边会在一段时间内还认为这个连接“可能活着”
- 这时候新 pod 又起来连上了，就会出现 **旧连接未清、 新连接已建、事件随机投递/漂移** 的窗口期

这类问题通常来自几个现实情况:

1. **进程不是正常退出**
   比如 OOMKill、node 故障、容器被硬杀，根本来不及走 defer/Shutdown。

2. **TCP / WebSocket 半开连接**
   从客户端视角死了，但服务端未必立刻感知，得等:
   - TCP keepalive
   - websocket ping/pong 超时
   - 平台自己的 session timeout

3. **K8s 的终止和平台连接回收不是同步的**
   pod 生命周期结束了，不代表 Lark 立刻把旧连接摘掉。

所以你看到的现象大概率就是:
- old pod 逻辑上已经没了
- 但旧 ws session 在飞书那边还没过期
- new pod 已经建了新连接
- 一段时间内两个连接并存，平台随机投递

### 所以更准确的结论可以说成
**不仅没有独占，而且在 pod 非优雅退出时，旧长连接还可能短时间残留，进一步放大多 pod 并发接收的混乱。**

### 为什么 webhook 相对好一点
因为 webhook 模式下:
- 平台只认你的回调 URL
- pod 死亡后，流量会被 Service/Ingress 切到活着的 pod
- 不存在“旧 pod 还占着一个 SDK 长连接 session”这种残留态

当然 webhook 也会有重试、超时、重复投递，但至少**不会卡在连接所有权这层**。

### 你这个场景的核心痛点
不是“close 没写好”，而是:

**连接所有权依赖客户端存活状态，而客户端死亡检测天然有延迟。**

这在分布式环境里非常难彻底消掉，除非平台提供:
- lease
- fencing token
- active/passive session ownership

但飞书长连接显然没做到这一步。

### 你可以很直接地总结给同事
> 飞书/Lark 长连接在多 pod 场景下不适合做高可用单活接入。pod 异常死亡时旧连接无法及时主动关闭，而平台对失效连接的回收存在延迟，导致新旧连接并存，在这段窗口期内事件会随机投递，引发消费混乱。

如果你要，我可以帮你把这段再压缩成一句更像事故复盘/架构评审里的表述。
