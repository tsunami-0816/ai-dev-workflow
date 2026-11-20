-- ============================================================
-- uniapp-miniapp-release-loop · 数据库初始化（T-401 / D-19）
-- 目标库：uniapp_booking（共享 MySQL 8 实例，独立 database）
-- 字符集：utf8mb4；时间：Asia/Shanghai（容器 TZ 已设）
-- 幂等：可重复执行（IF NOT EXISTS + INSERT IGNORE 依赖唯一键）
-- 说明：user.password_hash 为 H5 账号登录所需，架构 §5 原表遗漏，
--       按 T-205 补列（PBKDF2-SHA256 / 120000 / 32B，见 db/gen_hash.py）。
-- ============================================================

CREATE DATABASE IF NOT EXISTS `uniapp_booking`
  DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE `uniapp_booking`;

CREATE TABLE IF NOT EXISTS `user` (
  `id`            BIGINT       NOT NULL AUTO_INCREMENT,
  `openid`        VARCHAR(64)  DEFAULT NULL COMMENT '小程序 openid，H5 账号为 NULL',
  `account`       VARCHAR(32)  DEFAULT NULL COMMENT 'H5 demo 账号',
  `password_hash` VARCHAR(128) DEFAULT NULL COMMENT 'PBKDF2 口令哈希；openid 用户为 NULL',
  `phone`         VARCHAR(20)  DEFAULT NULL,
  `nickname`      VARCHAR(64)  DEFAULT NULL,
  `created_at`    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_openid` (`openid`),
  UNIQUE KEY `uk_account` (`account`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `package` (
  `id`         BIGINT        NOT NULL AUTO_INCREMENT,
  `title`      VARCHAR(64)   NOT NULL COMMENT '套餐名，如「城市轻写真」',
  `price`      DECIMAL(10,2) NOT NULL,
  `cover_url`  VARCHAR(255)  NOT NULL,
  `tags`       VARCHAR(128)  NOT NULL COMMENT '逗号分隔：室内,2套服装,精修8张',
  `summary`    VARCHAR(512)  DEFAULT NULL,
  `sort`       INT           NOT NULL DEFAULT 0,
  `status`     TINYINT       NOT NULL DEFAULT 1 COMMENT '1 上架 0 下架',
  `created_at` DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_status_sort` (`status`,`sort`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `booking` (
  `id`          BIGINT       NOT NULL AUTO_INCREMENT,
  `user_id`     BIGINT       NOT NULL,
  `package_id`  BIGINT       NOT NULL,
  `book_date`   DATE         NOT NULL,
  `slot`        VARCHAR(16)  NOT NULL COMMENT '上午/下午/晚间',
  `contact`     VARCHAR(20)  NOT NULL COMMENT '联系人手机号，幂等键',
  `remark`      VARCHAR(255) DEFAULT NULL,
  `status`      TINYINT      NOT NULL DEFAULT 0 COMMENT '0 待确认 1 已确认 2 已取消',
  `created_at`  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at`  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_contact_date_slot` (`contact`,`book_date`,`slot`),
  KEY `idx_user_created` (`user_id`,`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `notify_log` (
  `id`          BIGINT       NOT NULL AUTO_INCREMENT,
  `booking_id`  BIGINT       NOT NULL,
  `event`       VARCHAR(32)  NOT NULL DEFAULT 'booking.created',
  `payload`     VARCHAR(1024) DEFAULT NULL,
  `consumed_at` DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_booking_event` (`booking_id`,`event`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------- 种子：H5 demo 账号（2 个，口令 welcome1） ----------
-- 哈希由 db/gen_hash.py 生成，同一 salt；仅演示用，上线前必须更换。
INSERT IGNORE INTO `user` (`account`,`password_hash`,`nickname`) VALUES
 ('demo',  'pbkdf2$120000$dW5pYXBwZGVtbzIwMjYhIQ==$QC0Fbhfw0NbrONnFmeLjXwxfmqZKFFAUMW1IBG0Y3s4=', '演示用户A'),
 ('demo2', 'pbkdf2$120000$dW5pYXBwZGVtbzIwMjYhIQ==$QC0Fbhfw0NbrONnFmeLjXwxfmqZKFFAUMW1IBG0Y3s4=', '演示用户B');

-- ---------- 种子：4 个上架套餐 ----------
INSERT IGNORE INTO `package` (`id`,`title`,`price`,`cover_url`,`tags`,`summary`,`sort`,`status`) VALUES
 (1,'城市轻写真',399.00,'/static/covers/cover-1.jpg','室内,2套服装,精修8张','室内自然光棚拍，适合日常通勤与社交头像；含妆造基础。',10,1),
 (2,'复古胶片',499.00,'/static/covers/cover-2.jpg','外景,胶片质感,精修12张','外景街拍 + 胶片色调整，适合换季纪念与情侣合拍。',20,1),
 (3,'情侣纪实',699.00,'/static/covers/cover-3.jpg','双人,外景,精修15张','以日常互动为主的纪实拍摄，含 90 分钟跟拍与 15 张精修。',30,1),
 (4,'个人写真·夜场',599.00,'/static/covers/cover-4.jpg','夜景,灯光,精修10张','夜间灯光主题，含冷调/暖调两套布光，出片 10 张。',40,1);
