# archfind-yang-020 后台参考（按需读取，不常驻加载）

## 一、本质维度表

> 认知背书：Kleppmann《Designing Data-Intensive Applications》——比较系统靠拆实现原理（数据怎么流、一致性怎么保证），不比功能清单。

| 维度 | 看什么 | 关键问题 |
|---|---|---|
| 数据模型与数据路径 | 数据怎么流、怎么存 | 写路径/读路径是否分离？日志追加还是原地更新？ |
| 存储引擎 | LSM-Tree / B+Tree / 内存 / 追加日志 | 写放大/读放大/空间放大各牺牲了什么？ |
| 复制与分区 | 主从/多主/仲裁；范围/哈希分片 | 分区键怎么选？热点怎么办？扩容要不要 rebalance？ |
| 一致性与事务 | 线性化/顺序/最终一致；隔离级别 | 什么场景牺牲了什么一致性换性能？ |
| 扩展模型 | 水平扩展的单元（分区/节点/单元化） | 扩到 N 倍时哪层先崩？ |
| 故障处理 | 故障域划分、恢复机制、脑裂防护 | 挂一台/一机房会怎样？恢复要多久？ |
| 运维复杂度 | 部署/监控/调参/升级门槛 | 团队 hold 得住吗？ |
| 生态成熟度 | 客户端/连接器/社区/招人 | 踩坑有人陪吗？ |

**裁剪规则**：
- 数据系统（存储/消息/数据库）：全维度。
- 基础设施（网关/代理/LB）：砍存储引擎，复制分区简化。
- 应用架构（单体/微服务/Serverless）：只留扩展模型/故障处理/运维复杂度/生态成熟度。

## 二、核心论文索引（经典象限弹药库，链接均验证于 2026-08-23）

| 论文 | 会议/年 | 原点价值一句话 | 链接 |
|---|---|---|---|
| Dynamo: Amazon's Highly Available Key-value Store | SOSP 2007 | AP 牺牲一致性的原点：最终一致+一致性哈希+向量时钟 | https://www.allthingsdistributed.com/files/amazon-dynamo-sosp2007.pdf |
| Bigtable: A Distributed Storage System for Structured Data | OSDI 2006 | LSM + range 分片 + 单行事务的奠基存储 | https://research.google/pubs/bigtable-a-distributed-storage-system-for-structured-data/ |
| Spanner: Google's Globally-Distributed Database | OSDI 2012 | 全球规模外部一致事务（TrueTime），NewSQL 原点 | https://www.usenix.org/system/files/conference/osdi12/osdi12-final-16.pdf |
| In Search of an Understandable Consensus Algorithm（Raft） | USENIX ATC 2014 | 共识工程化事实标准，etcd/CockroachDB/TiDB 底座 | https://www.usenix.org/conference/atc14/technical-sessions/presentation/ongaro |
| Kafka: a Distributed Messaging System for Log Processing | NetDB 2011 | 日志即消息队列的原点：分区追加模型 | 镜像 http://pages.cs.wisc.edu/~akella/CS744/F17/838-CloudPapers/Kafka.pdf；官方设计文档 https://kafka.apache.org/documentation/ |
| MapReduce: Simplified Data Processing on Large Clusters | OSDI 2004 | 大数据计算模型原点 | https://research.google/pubs/mapreduce-simplified-data-processing-on-large-clusters/ |
| ZooKeeper: Wait-free Coordination for Internet-scale Systems | USENIX ATC 2010 | 协调服务（选主/配置/锁）事实标准 | https://www.usenix.org/legacy/event/atc10/tech/full_papers/Hunt.pdf |

**索引纪律**：按需增长；新增条目链接必须先验证再写，不凭记忆。

## 三、信源清单（找对标先扫这里）

**一手（优先）**：
- 系统论文：OSDI / SOSP / NSDI / SIGMOD / VLDB / USENIX ATC。
- 官方架构文档 + 源码（官方仓库的 design doc / ARCHITECTURE.md）。
- 工程团队亲述博客：Discord（discord.com/blog）、Cloudflare（blog.cloudflare.com）、Netflix（netflixtechblog.com）、Meta、Uber、AWS Architecture Blog、ScyllaDB（厂商侧一手）。
- postmortem / 翻车文：官方博客 incident 系列——硬度加分项（真实生产数字+教训）。

**二手（只作线索，不作依据）**：ByteByteGo、InfoQ、HN 讨论（核心开发者现身时，其言论按一手算）。

**搜索动作**：`site:` 限定官方域名；论文标题+会议名；「X architecture」「X migration」「X postmortem」。

## 四、报告模板

```
## bench 报告 · {问题一句话}

约束：{用户给的 + 假设标注「基于假设 X，可纠正重跑」}

### 结论（条件式推荐）
> A 适合…，B 适合…，基于你的约束→…

### 本质对比（深比 2-3）
{裁剪后的维度表}

### 各家要点
- 【系统 A】象限：经典/前沿（一句话理由）
  {一段架构要点 + 生产数字}
  出处：URL

### ADR 推荐
- 背景：{约束}
- 推荐：{条件式}
- 理由：{数字/权衡链}
- 代价：{牺牲了什么、什么情况下会后悔}

### 未收录说明
{没进深比的候选，一句话为什么}

### 出处
{全部 URL 清单}
```
