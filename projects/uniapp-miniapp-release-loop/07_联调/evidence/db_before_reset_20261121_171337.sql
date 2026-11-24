-- MySQL dump 10.13  Distrib 8.0.46, for Win64 (x86_64)
--
-- Host: 127.0.0.1    Database: uniapp_booking
-- ------------------------------------------------------
-- Server version	8.0.46

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!50503 SET NAMES utf8mb4 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

--
-- Current Database: `uniapp_booking`
--

CREATE DATABASE /*!32312 IF NOT EXISTS*/ `uniapp_booking` /*!40100 DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci */ /*!80016 DEFAULT ENCRYPTION='N' */;

USE `uniapp_booking`;

--
-- Table structure for table `booking`
--

DROP TABLE IF EXISTS `booking`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `booking` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `user_id` bigint NOT NULL,
  `package_id` bigint NOT NULL,
  `book_date` date NOT NULL,
  `slot` varchar(16) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '上午/下午/晚间',
  `contact` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '联系人手机号，幂等键',
  `remark` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `status` tinyint NOT NULL DEFAULT '0' COMMENT '0 待确认 1 已确认 2 已取消',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_contact_date_slot` (`contact`,`book_date`,`slot`),
  KEY `idx_user_created` (`user_id`,`created_at`)
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `booking`
--

LOCK TABLES `booking` WRITE;
/*!40000 ALTER TABLE `booking` DISABLE KEYS */;
INSERT INTO `booking` VALUES (1,1,1,'2026-11-21','下午','13800000001','第9步预走',0,'2026-11-21 17:11:49','2026-11-21 17:11:49');
/*!40000 ALTER TABLE `booking` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `notify_log`
--

DROP TABLE IF EXISTS `notify_log`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `notify_log` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `booking_id` bigint NOT NULL,
  `event` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'booking.created',
  `payload` varchar(1024) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `consumed_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_booking_event` (`booking_id`,`event`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `notify_log`
--

LOCK TABLES `notify_log` WRITE;
/*!40000 ALTER TABLE `notify_log` DISABLE KEYS */;
/*!40000 ALTER TABLE `notify_log` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `package`
--

DROP TABLE IF EXISTS `package`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `package` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `title` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '套餐名，如「城市轻写真」',
  `price` decimal(10,2) NOT NULL,
  `cover_url` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `tags` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '逗号分隔：室内,2套服装,精修8张',
  `summary` varchar(512) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `sort` int NOT NULL DEFAULT '0',
  `status` tinyint NOT NULL DEFAULT '1' COMMENT '1 上架 0 下架',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_status_sort` (`status`,`sort`)
) ENGINE=InnoDB AUTO_INCREMENT=5 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `package`
--

LOCK TABLES `package` WRITE;
/*!40000 ALTER TABLE `package` DISABLE KEYS */;
INSERT INTO `package` VALUES (1,'城市轻写真',399.00,'/static/covers/cover-1.jpg','室内,2套服装,精修8张','室内自然光棚拍，适合日常通勤与社交头像；含妆造基础。',10,1,'2026-11-21 17:11:14'),(2,'复古胶片',499.00,'/static/covers/cover-2.jpg','外景,胶片质感,精修12张','外景街拍 + 胶片色调整，适合换季纪念与情侣合拍。',20,1,'2026-11-21 17:11:14'),(3,'情侣纪实',699.00,'/static/covers/cover-3.jpg','双人,外景,精修15张','以日常互动为主的纪实拍摄，含 90 分钟跟拍与 15 张精修。',30,1,'2026-11-21 17:11:14'),(4,'个人写真·夜场',599.00,'/static/covers/cover-4.jpg','夜景,灯光,精修10张','夜间灯光主题，含冷调/暖调两套布光，出片 10 张。',40,1,'2026-11-21 17:11:14');
/*!40000 ALTER TABLE `package` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `user`
--

DROP TABLE IF EXISTS `user`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `user` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `openid` varchar(64) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '小程序 openid，H5 账号为 NULL',
  `account` varchar(32) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'H5 demo 账号',
  `password_hash` varchar(128) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'PBKDF2 口令哈希；openid 用户为 NULL',
  `phone` varchar(20) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `nickname` varchar(64) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_openid` (`openid`),
  UNIQUE KEY `uk_account` (`account`)
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `user`
--

LOCK TABLES `user` WRITE;
/*!40000 ALTER TABLE `user` DISABLE KEYS */;
INSERT INTO `user` VALUES (1,NULL,'demo','pbkdf2$120000$dW5pYXBwZGVtbzIwMjYhIQ==$QC0Fbhfw0NbrONnFmeLjXwxfmqZKFFAUMW1IBG0Y3s4=',NULL,'演示用户A','2026-11-21 17:11:14'),(2,NULL,'demo2','pbkdf2$120000$dW5pYXBwZGVtbzIwMjYhIQ==$QC0Fbhfw0NbrONnFmeLjXwxfmqZKFFAUMW1IBG0Y3s4=',NULL,'演示用户B','2026-11-21 17:11:14');
/*!40000 ALTER TABLE `user` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Dumping events for database 'uniapp_booking'
--

--
-- Dumping routines for database 'uniapp_booking'
--
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2026-11-21 17:13:38
