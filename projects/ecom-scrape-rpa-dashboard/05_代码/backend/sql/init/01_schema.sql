-- ecom-scrape-rpa-dashboard · 01_schema.sql（T19 / D-48、D-49）
-- 14 张表 DDL，逐字对齐架构 §4.2 v2.0 定稿。
-- 账号（ecom_ro / ecom_rw）不写在本文件：由 `cli initdb` 用 root 会话创建（§5.3 最小权限）。
-- 分区约束：price_snapshot 的每个唯一键都包含分区列 captured_date（MySQL 8 RANGE COLUMNS 限制，
-- 同时也是 C05「同 (platform, sku_id, date) 只落 1 条」的架构级保证，ADR-04）。

CREATE DATABASE IF NOT EXISTS ecom_scrape
  DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
USE ecom_scrape;

-- 1) 任务定义
CREATE TABLE IF NOT EXISTS task (
  id           BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  name         VARCHAR(64)  NOT NULL,
  platform     VARCHAR(16)  NOT NULL,
  cron         VARCHAR(32)  NOT NULL DEFAULT '0 2 * * *',
  enabled      TINYINT(1)   NOT NULL DEFAULT 1,
  config_hash  CHAR(40)     NOT NULL,
  version      INT          NOT NULL DEFAULT 1,
  created_at   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uk_task_name_version (name, version),
  KEY idx_platform_enabled (platform, enabled)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 2) 运行记录（cursor 支持断点续采）
CREATE TABLE IF NOT EXISTS task_run (
  id           BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  task_id      BIGINT UNSIGNED NOT NULL,
  status       VARCHAR(16)  NOT NULL,          -- running/ok/partial/interrupted/failed
  `cursor`     JSON         NOT NULL,          -- {"page":3,"offset":60,"done":300}
  started_at   DATETIME     NOT NULL,
  finished_at  DATETIME     NULL,
  error        TEXT         NULL,
  snapshot_cnt INT          NOT NULL DEFAULT 0,
  PRIMARY KEY (id),
  KEY idx_task_status (task_id, status),
  KEY idx_started (started_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 3) 逐 SKU 运行明细（C04 集合比对的唯一事实源）
CREATE TABLE IF NOT EXISTS task_run_item (
  id         BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  run_id     BIGINT UNSIGNED NOT NULL,
  platform   VARCHAR(16)  NOT NULL,
  sku_id     VARCHAR(64)  NOT NULL,
  status     VARCHAR(16)  NOT NULL,            -- ok/skip/fail
  reason     VARCHAR(128) NULL,
  snapshot_id BIGINT UNSIGNED NULL,
  at         DATETIME     NOT NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uk_run_sku (run_id, platform, sku_id),
  KEY idx_run_status (run_id, status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 4) 采集暂存（原始解析结果；price_snapshot 的唯一上游，P0-01 / ADR-10）
CREATE TABLE IF NOT EXISTS stg_price_item (
  id             BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  run_id         BIGINT UNSIGNED NOT NULL,
  platform       VARCHAR(16)  NOT NULL,
  sku_id         VARCHAR(64)  NOT NULL,
  title          VARCHAR(255) NULL,
  shop           VARCHAR(128) NULL,
  url            VARCHAR(512) NULL,
  url_hash       CHAR(40)     NULL,
  raw_price_text VARCHAR(64)  NULL,      -- 原始串：'¥1,299.00' / '面议'
  price          DECIMAL(10,2) NULL,     -- 解析值；脏值为 NULL，不违约（价格表才 NOT NULL）
  raw_sales_text VARCHAR(64)  NULL,      -- '1.3万+人付款'
  sales_num      INT          NULL,
  captured_date  DATE         NOT NULL,
  crawled_at     DATETIME     NOT NULL,
  cleaned_flag   TINYINT(1)   NOT NULL DEFAULT 0,  -- 0 待清洗 / 1 已处理（支持重跑）
  PRIMARY KEY (id),
  UNIQUE KEY uk_run_sku (run_id, platform, sku_id),
  KEY idx_date_clean (captured_date, cleaned_flag),
  KEY idx_platform_sku (platform, sku_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 5) 原始快照（表存指针）
CREATE TABLE IF NOT EXISTS raw_page (
  id           BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  platform     VARCHAR(16)  NOT NULL,
  url          VARCHAR(512) NOT NULL,
  url_hash     CHAR(40)     NOT NULL,
  body_path    VARCHAR(255) NOT NULL,
  content_type VARCHAR(32)  NULL,
  http_status  SMALLINT     NULL,
  byte_size    INT          NULL,
  run_id       BIGINT UNSIGNED NULL,
  crawled_at   DATETIME     NOT NULL,
  PRIMARY KEY (id),
  KEY idx_urlhash_time (url_hash, crawled_at),
  KEY idx_platform_time (platform, crawled_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 6) 商品主数据
CREATE TABLE IF NOT EXISTS product (
  id            BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  platform      VARCHAR(16)  NOT NULL,
  sku_id        VARCHAR(64)  NOT NULL,
  title         VARCHAR(255) NOT NULL,
  title_norm    VARCHAR(255) NULL,
  shop          VARCHAR(128) NULL,
  category      VARCHAR(64)  NULL,
  url           VARCHAR(512) NOT NULL,
  url_hash      CHAR(40)     NOT NULL,
  same_group_id VARCHAR(64)  NULL,             -- 跨平台同款分组（difflib>0.8）
  first_seen_at DATETIME     NOT NULL,
  last_seen_at  DATETIME     NOT NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uk_platform_sku (platform, sku_id),
  KEY idx_title_norm (title_norm),
  KEY idx_group (same_group_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 7) 价格快照（按日分区；唯一键含分区列 → C05 架构级保证）
CREATE TABLE IF NOT EXISTS price_snapshot (
  id            BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  product_id    BIGINT UNSIGNED NOT NULL,
  platform      VARCHAR(16)  NOT NULL,
  sku_id        VARCHAR(64)  NOT NULL,
  price         DECIMAL(10,2) NOT NULL,
  list_price    DECIMAL(10,2) NULL,
  sales_tag     VARCHAR(64)  NULL,
  sales_num     INT          NULL,
  imputed       TINYINT(1)   NOT NULL DEFAULT 0,
  anomaly_flag  TINYINT(1)   NOT NULL DEFAULT 0,
  anomaly_reason VARCHAR(64) NULL,
  run_id        BIGINT UNSIGNED NULL,
  captured_date DATE         NOT NULL,
  crawled_at    DATETIME     NOT NULL,
  PRIMARY KEY (id, captured_date),
  UNIQUE KEY uk_platform_sku_date (platform, sku_id, captured_date),
  KEY idx_product_date (product_id, captured_date),
  KEY idx_date_platform (captured_date, platform),
  KEY idx_anomaly (captured_date, anomaly_flag)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
PARTITION BY RANGE COLUMNS(captured_date) (
  PARTITION p202611 VALUES LESS THAN ('2026-12-01'),
  PARTITION p202612 VALUES LESS THAN ('2027-01-01'),
  PARTITION p202701 VALUES LESS THAN ('2027-02-01'),
  PARTITION p202702 VALUES LESS THAN ('2027-03-01'),
  PARTITION pmax    VALUES LESS THAN (MAXVALUE)
);

-- 8) 清洗报告（每日一行）
CREATE TABLE IF NOT EXISTS clean_report (
  id           BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  run_date     DATE         NOT NULL,
  status       VARCHAR(16)  NOT NULL,          -- ok/failed
  total        INT          NOT NULL DEFAULT 0,
  passed       INT          NOT NULL DEFAULT 0,
  blocked      INT          NOT NULL DEFAULT 0,
  imputed      INT          NOT NULL DEFAULT 0,
  anomaly      INT          NOT NULL DEFAULT 0,
  reasons_json JSON         NOT NULL,          -- {"required":3,"range":2,"enum":1,"duplicate":4}
  elapsed_ms   INT          NULL,
  created_at   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uk_run_date (run_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 9) 清洗拦截明细（C06 "各类原因计数"证据）
CREATE TABLE IF NOT EXISTS clean_issue (
  id        BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  run_date  DATE         NOT NULL,
  platform  VARCHAR(16)  NOT NULL,
  sku_id    VARCHAR(64)  NULL,
  rule      VARCHAR(32)  NOT NULL,             -- required/required_price/range/enum/duplicate/unexpected
  field     VARCHAR(32)  NULL,
  raw_value VARCHAR(255) NULL,
  detail    VARCHAR(255) NULL,
  PRIMARY KEY (id),
  KEY idx_date_rule (run_date, rule)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 10) 反爬与健康度观测（只追加）
CREATE TABLE IF NOT EXISTS antibot_metrics (
  id           BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  platform     VARCHAR(16)  NOT NULL,
  url          VARCHAR(512) NOT NULL,
  http_status  SMALLINT     NULL,
  latency_ms   INT          NOT NULL,
  wait_ms      INT          NOT NULL DEFAULT 0,   -- 令牌桶等待（C03 证据）
  via_proxy    TINYINT(1)   NOT NULL DEFAULT 0,
  cookie_state VARCHAR(16)  NOT NULL DEFAULT 'none', -- none/ok/invalid
  blocked_flag TINYINT(1)   NOT NULL DEFAULT 0,
  block_reason VARCHAR(32)  NULL,               -- captcha/login_redirect/rate_limit/keyword
  retry_no     TINYINT      NOT NULL DEFAULT 0,
  run_id       BIGINT UNSIGNED NULL,
  at           DATETIME(3)  NOT NULL,             -- 请求发起时刻（C03 一律以此核算，P1-03）
  finished_at  DATETIME(3)  NULL,                 -- 响应结束时刻（latency 校验用）
  PRIMARY KEY (id),
  KEY idx_platform_at (platform, at),
  KEY idx_blocked (blocked_flag, at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 11) RPA 流程定义（版本化）
CREATE TABLE IF NOT EXISTS rpa_flow (
  id         BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  name       VARCHAR(64)  NOT NULL,
  version    INT          NOT NULL,
  yaml       MEDIUMTEXT   NOT NULL,
  yaml_hash  CHAR(40)     NOT NULL,
  enabled    TINYINT(1)   NOT NULL DEFAULT 1,
  created_at DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uk_name_version (name, version)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 12) RPA 执行记录
CREATE TABLE IF NOT EXISTS rpa_run (
  id             BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  flow_id        BIGINT UNSIGNED NOT NULL,
  status         VARCHAR(16)  NOT NULL,        -- ok/failed
  steps_total    TINYINT      NOT NULL,
  steps_ok       TINYINT      NOT NULL DEFAULT 0,
  screenshot_dir VARCHAR(255) NULL,
  log_path       VARCHAR(255) NULL,
  error          TEXT         NULL,
  started_at     DATETIME     NOT NULL,
  finished_at    DATETIME     NULL,
  PRIMARY KEY (id),
  KEY idx_flow_status (flow_id, status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 13) 报表产物登记
CREATE TABLE IF NOT EXISTS report_file (
  id          BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  run_date    DATE         NOT NULL,
  path        VARCHAR(255) NOT NULL,
  status      VARCHAR(16)  NOT NULL,           -- ok/failed
  sheets_json JSON         NOT NULL,           -- ["原始明细","清洗后明细","透视汇总","异常清单","趋势"]
  rows_json   JSON         NOT NULL,           -- {"原始明细":312,"清洗后明细":300,...}
  elapsed_ms  INT          NULL,
  byte_size   INT          NULL,
  created_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uk_run_date (run_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 14) 平台日聚合（P95 的预聚合来源）
CREATE TABLE IF NOT EXISTS agg_daily_platform (
  stat_date       DATE        NOT NULL,
  platform        VARCHAR(16) NOT NULL,
  sku_count       INT         NOT NULL DEFAULT 0,
  avg_price       DECIMAL(10,2) NULL,
  min_price       DECIMAL(10,2) NULL,
  max_price       DECIMAL(10,2) NULL,
  sum_sales       BIGINT      NOT NULL DEFAULT 0,
  req_cnt         INT         NOT NULL DEFAULT 0,
  success_cnt     INT         NOT NULL DEFAULT 0,
  blocked_cnt     INT         NOT NULL DEFAULT 0,
  p95_latency_ms  INT         NULL,
  computed_at     DATETIME    NOT NULL,
  PRIMARY KEY (stat_date, platform)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
