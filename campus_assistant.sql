-- MySQL dump 10.13  Distrib 8.0.38, for Win64 (x86_64)
--
-- Host: localhost    Database: campus_assistant
-- ------------------------------------------------------
-- Server version	8.0.39

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!50503 SET NAMES utf8 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

--
-- Table structure for table `class_instances`
--

DROP TABLE IF EXISTS `class_instances`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `class_instances` (
  `id` int NOT NULL AUTO_INCREMENT,
  `orig_class_id` int DEFAULT NULL,
  `template_id` int DEFAULT NULL,
  `school_id` int DEFAULT NULL,
  `school_year` varchar(16) NOT NULL,
  `grade` tinyint DEFAULT NULL,
  `section` varchar(32) DEFAULT NULL,
  `homeroom_teacher_id` int DEFAULT NULL,
  `active` tinyint(1) DEFAULT '1',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `orig_class_id` (`orig_class_id`),
  KEY `school_year` (`school_year`),
  KEY `homeroom_teacher_id` (`homeroom_teacher_id`),
  KEY `fk_ci_school` (`school_id`),
  CONSTRAINT `fk_ci_homeroom_teacher` FOREIGN KEY (`homeroom_teacher_id`) REFERENCES `users` (`id`) ON DELETE SET NULL,
  CONSTRAINT `fk_ci_school` FOREIGN KEY (`school_id`) REFERENCES `schools` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB AUTO_INCREMENT=6 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `class_instances`
--

LOCK TABLES `class_instances` WRITE;
/*!40000 ALTER TABLE `class_instances` DISABLE KEYS */;
INSERT INTO `class_instances` VALUES (1,1,1,1,'2025-2026',4,'1',9,1,'2025-10-17 00:52:08'),(2,2,2,1,'2025-2026',1,'2',10,1,'2025-10-17 00:52:08');
/*!40000 ALTER TABLE `class_instances` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `class_students`
--

DROP TABLE IF EXISTS `class_students`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `class_students` (
  `id` int NOT NULL AUTO_INCREMENT,
  `class_id` int NOT NULL,
  `student_id` int NOT NULL,
  `created_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `class_id` (`class_id`),
  KEY `student_id` (`student_id`),
  CONSTRAINT `class_students_ibfk_1` FOREIGN KEY (`class_id`) REFERENCES `classes` (`id`) ON DELETE CASCADE,
  CONSTRAINT `class_students_ibfk_2` FOREIGN KEY (`student_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=4 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `class_students`
--

LOCK TABLES `class_students` WRITE;
/*!40000 ALTER TABLE `class_students` DISABLE KEYS */;
INSERT INTO `class_students` VALUES (1,1,11,'2025-09-19 20:03:37'),(2,1,12,'2025-09-19 20:03:37'),(3,2,13,'2025-09-19 20:03:37');
/*!40000 ALTER TABLE `class_students` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `classes`
--

DROP TABLE IF EXISTS `classes`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `classes` (
  `id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(128) NOT NULL,
  `homeroom_teacher_id` int DEFAULT NULL,
  `class_code` varchar(32) DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `ux_classes_code` (`class_code`),
  KEY `ix_classes_homeroom_teacher_id` (`homeroom_teacher_id`),
  KEY `idx_classes_homeroom_teacher_id` (`homeroom_teacher_id`),
  CONSTRAINT `fk_class_homeroom_teacher` FOREIGN KEY (`homeroom_teacher_id`) REFERENCES `users` (`id`),
  CONSTRAINT `fk_classes_homeroom_teacher` FOREIGN KEY (`homeroom_teacher_id`) REFERENCES `users` (`id`) ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `classes`
--

LOCK TABLES `classes` WRITE;
/*!40000 ALTER TABLE `classes` DISABLE KEYS */;
INSERT INTO `classes` VALUES (1,'Class 1',9,'202501'),(2,'Class 2',10,'202502');
/*!40000 ALTER TABLE `classes` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `daily_quotes`
--

DROP TABLE IF EXISTS `daily_quotes`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `daily_quotes` (
  `id` int NOT NULL AUTO_INCREMENT,
  `class_id` int DEFAULT NULL,
  `date` date DEFAULT NULL,
  `content` text NOT NULL,
  `voice_url` varchar(255) DEFAULT NULL,
  `broadcast_time` varchar(5) DEFAULT NULL,
  `active` tinyint(1) NOT NULL,
  PRIMARY KEY (`id`),
  KEY `ix_daily_quotes_class_id` (`class_id`),
  KEY `idx_daily_quotes_class_id` (`class_id`),
  KEY `idx_daily_quotes_class_date` (`class_id`,`date`),
  CONSTRAINT `daily_quotes_ibfk_1` FOREIGN KEY (`class_id`) REFERENCES `classes` (`id`),
  CONSTRAINT `fk_daily_quotes_class` FOREIGN KEY (`class_id`) REFERENCES `classes` (`id`) ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `daily_quotes`
--

LOCK TABLES `daily_quotes` WRITE;
/*!40000 ALTER TABLE `daily_quotes` DISABLE KEYS */;
INSERT INTO `daily_quotes` VALUES (1,1,NULL,'别怕慢，只怕站。—— 早安，同学们。',NULL,'07:30',1),(2,2,NULL,'失败是成功之母，坚持才有希望。',NULL,'07:30',1);
/*!40000 ALTER TABLE `daily_quotes` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `enrollments`
--

DROP TABLE IF EXISTS `enrollments`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `enrollments` (
  `id` int NOT NULL AUTO_INCREMENT,
  `user_id` int NOT NULL,
  `class_instance_id` int NOT NULL,
  `start_date` date DEFAULT NULL,
  `end_date` date DEFAULT NULL,
  `status` enum('active','graduated','transferred') DEFAULT 'active',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `user_id` (`user_id`),
  KEY `class_instance_id` (`class_instance_id`),
  CONSTRAINT `fk_enroll_ci` FOREIGN KEY (`class_instance_id`) REFERENCES `class_instances` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_enroll_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=7 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `enrollments`
--

LOCK TABLES `enrollments` WRITE;
/*!40000 ALTER TABLE `enrollments` DISABLE KEYS */;
INSERT INTO `enrollments` VALUES (1,11,1,'2025-10-17',NULL,'active','2025-10-17 00:52:08'),(2,12,1,'2025-10-17',NULL,'active','2025-10-17 00:52:08'),(3,13,2,'2025-10-17',NULL,'active','2025-10-17 00:52:08');
/*!40000 ALTER TABLE `enrollments` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `grades`
--

DROP TABLE IF EXISTS `grades`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `grades` (
  `id` int NOT NULL AUTO_INCREMENT,
  `student_id` int NOT NULL,
  `subject` varchar(50) NOT NULL,
  `score` int NOT NULL,
  `semester` varchar(20) NOT NULL,
  `teacher_id` int NOT NULL,
  `class_instance_id` int DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `ix_grades_student_id` (`student_id`),
  KEY `ix_grades_teacher_id` (`teacher_id`),
  KEY `fk_grades_ci` (`class_instance_id`),
  CONSTRAINT `fk_grades_ci` FOREIGN KEY (`class_instance_id`) REFERENCES `class_instances` (`id`) ON DELETE SET NULL,
  CONSTRAINT `grades_ibfk_1` FOREIGN KEY (`student_id`) REFERENCES `users` (`id`),
  CONSTRAINT `grades_ibfk_2` FOREIGN KEY (`teacher_id`) REFERENCES `users` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=4 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `grades`
--

LOCK TABLES `grades` WRITE;
/*!40000 ALTER TABLE `grades` DISABLE KEYS */;
INSERT INTO `grades` VALUES (1,11,'Math',88,'2025-1',9,1),(2,12,'Math',92,'2025-1',9,1),(3,11,'Chinese',90,'2025-1',9,1);
/*!40000 ALTER TABLE `grades` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `memos`
--

DROP TABLE IF EXISTS `memos`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `memos` (
  `id` int NOT NULL AUTO_INCREMENT,
  `student_id` int NOT NULL,
  `content` text NOT NULL,
  `remind_date` date NOT NULL,
  `status_json` json DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `ix_memos_student_id` (`student_id`),
  CONSTRAINT `memos_ibfk_1` FOREIGN KEY (`student_id`) REFERENCES `users` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=5 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `memos`
--

LOCK TABLES `memos` WRITE;
/*!40000 ALTER TABLE `memos` DISABLE KEYS */;
INSERT INTO `memos` VALUES (1,11,'明天带语文作业','2025-09-20',NULL),(2,12,'周五体检带体检表','2025-09-21',NULL);
/*!40000 ALTER TABLE `memos` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `messages`
--

DROP TABLE IF EXISTS `messages`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `messages` (
  `id` int NOT NULL AUTO_INCREMENT,
  `sender_id` int NOT NULL,
  `receiver_id` int NOT NULL,
  `content` text NOT NULL,
  `audio_url` varchar(200) DEFAULT NULL,
  `priority` enum('normal','urgent') DEFAULT NULL,
  `timestamp` datetime NOT NULL,
  `is_notice` tinyint(1) NOT NULL,
  `target_class` varchar(50) DEFAULT NULL,
  `target_role` varchar(20) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `ix_messages_sender_id` (`sender_id`),
  KEY `ix_messages_receiver_id` (`receiver_id`),
  CONSTRAINT `messages_ibfk_1` FOREIGN KEY (`sender_id`) REFERENCES `users` (`id`),
  CONSTRAINT `messages_ibfk_2` FOREIGN KEY (`receiver_id`) REFERENCES `users` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=10 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `messages`
--

LOCK TABLES `messages` WRITE;
/*!40000 ALTER TABLE `messages` DISABLE KEYS */;
INSERT INTO `messages` VALUES (1,9,11,'明天交作业别忘了',NULL,'normal','2025-09-19 20:03:37',0,NULL,NULL),(2,11,9,'老师收到，知道了',NULL,'normal','2025-09-19 20:03:37',0,NULL,NULL),(3,11,22,'hi',NULL,'normal','2025-10-21 22:12:41',0,NULL,NULL),(4,22,11,'hi',NULL,'normal','2025-10-21 22:53:21',0,NULL,NULL),(5,22,11,'hi',NULL,'normal','2025-10-21 23:03:20',0,NULL,NULL),(6,9,22,'下课记得找我',NULL,'normal','2025-10-23 21:13:28',0,NULL,NULL),(7,22,9,'收到',NULL,'normal','2025-10-23 21:14:06',0,NULL,NULL),(8,9,22,'hello',NULL,'normal','2025-11-03 23:01:22',0,NULL,NULL),(9,22,9,'shoudao',NULL,'normal','2025-11-03 23:02:07',0,NULL,NULL);
/*!40000 ALTER TABLE `messages` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `notices`
--

DROP TABLE IF EXISTS `notices`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `notices` (
  `id` int NOT NULL AUTO_INCREMENT,
  `creator_id` int NOT NULL,
  `content` text NOT NULL,
  `type` enum('normal','urgent') DEFAULT NULL,
  `timestamp` datetime NOT NULL,
  PRIMARY KEY (`id`),
  KEY `ix_notices_creator_id` (`creator_id`),
  CONSTRAINT `notices_ibfk_1` FOREIGN KEY (`creator_id`) REFERENCES `users` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `notices`
--

LOCK TABLES `notices` WRITE;
/*!40000 ALTER TABLE `notices` DISABLE KEYS */;
INSERT INTO `notices` VALUES (1,9,'今天晚自习正常进行，请同学准时到场。','normal','2025-09-19 20:03:37'),(2,10,'明天有考试，请复习','urgent','2025-09-19 20:03:37');
/*!40000 ALTER TABLE `notices` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `open_windows`
--

DROP TABLE IF EXISTS `open_windows`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `open_windows` (
  `id` int NOT NULL AUTO_INCREMENT,
  `class_id` int NOT NULL,
  `start_time` varchar(5) NOT NULL,
  `end_time` varchar(5) NOT NULL,
  `days_json` json DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `ix_open_windows_class_id` (`class_id`),
  CONSTRAINT `open_windows_ibfk_1` FOREIGN KEY (`class_id`) REFERENCES `classes` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=7 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `open_windows`
--

LOCK TABLES `open_windows` WRITE;
/*!40000 ALTER TABLE `open_windows` DISABLE KEYS */;
INSERT INTO `open_windows` VALUES (1,1,'0:00','08:00','[\"Mon\", \"Tue\", \"Wed\", \"Thu\", \"Fri\"]'),(3,2,'07:30','08:00','[\"Mon\", \"Tue\", \"Wed\", \"Thu\", \"Fri\"]'),(4,1,'00:00','17:00','[\"Sat\"]'),(5,1,'00:00','23:59','[\"Sun\"]'),(6,1,'19:00','23:59','[\"Mon\", \"Tue\", \"Wed\", \"Thu\", \"Fri\"]');
/*!40000 ALTER TABLE `open_windows` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `outgoing_queue`
--

DROP TABLE IF EXISTS `outgoing_queue`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `outgoing_queue` (
  `id` int NOT NULL AUTO_INCREMENT,
  `target_user_id` int NOT NULL,
  `payload` json NOT NULL,
  `priority` varchar(16) NOT NULL DEFAULT 'normal',
  `deliver_after` datetime DEFAULT NULL,
  `delivered` tinyint(1) NOT NULL DEFAULT '0',
  `created_at` datetime NOT NULL DEFAULT (now()),
  `delivered_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `ix_outgoing_queue_target_user_id` (`target_user_id`),
  KEY `idx_outgoing_created_at` (`created_at`),
  KEY `idx_outgoing_deliver_after` (`deliver_after`),
  KEY `idx_outgoing_delivered` (`delivered`)
) ENGINE=InnoDB AUTO_INCREMENT=18 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `outgoing_queue`
--

LOCK TABLES `outgoing_queue` WRITE;
/*!40000 ALTER TABLE `outgoing_queue` DISABLE KEYS */;
INSERT INTO `outgoing_queue` VALUES (1,11,'{\"text\": \"今天晚自习正常进行，请同学准时到场。\", \"type\": \"notice\", \"notice_id\": 1}','normal',NULL,1,'2025-09-19 20:03:37','2025-09-19 20:11:00'),(2,12,'{\"date\": \"2025-09-19\", \"text\": \"别怕慢，只怕站。—— 早安，同学们。\", \"type\": \"daily_quote\", \"quote_id\": 1}','normal',NULL,1,'2025-09-19 20:03:37','2025-09-19 20:10:55'),(3,11,'{\"type\": \"daily_quote\", \"content\": \"别怕慢，只怕站。—— 早安，同学们。\", \"quote_id\": 1, \"voice_url\": null, \"broadcast_time\": \"07:30\"}','normal',NULL,1,'2025-09-26 00:27:19','2025-09-26 00:27:33'),(4,12,'{\"type\": \"daily_quote\", \"content\": \"别怕慢，只怕站。—— 早安，同学们。\", \"quote_id\": 1, \"voice_url\": null, \"broadcast_time\": \"07:30\"}','normal',NULL,1,'2025-09-26 00:27:19','2025-10-10 20:24:56'),(5,11,'{\"type\": \"memo_reminder\", \"content\": \"记得洗衣服\", \"memo_id\": 3, \"open_window_id\": 1}','normal','2025-09-26 00:35:40',1,'2025-09-26 00:35:40','2025-09-26 00:36:05'),(6,11,'{\"type\": \"memo_reminder\", \"content\": \"记得洗衣服\", \"memo_id\": 3, \"open_window_id\": 1}','normal','2025-09-26 00:36:10',1,'2025-09-26 00:36:10','2025-09-26 00:36:24'),(7,11,'{\"type\": \"memo_reminder\", \"content\": \"写数学作业\", \"memo_id\": 4, \"open_window_id\": 2}','normal','2025-10-15 21:20:41',1,'2025-10-15 21:20:41','2025-10-15 21:20:49'),(8,11,'{\"type\": \"memo_reminder\", \"content\": \"写数学作业\", \"memo_id\": 4, \"open_window_id\": 2}','normal','2025-10-15 21:21:11',1,'2025-10-15 21:21:11','2025-10-15 21:22:21'),(9,11,'{\"type\": \"memo_reminder\", \"content\": \"写数学作业\", \"memo_id\": 4, \"open_window_id\": 2}','normal','2025-10-15 21:21:41',1,'2025-10-15 21:21:41','2025-10-15 21:22:22'),(10,11,'{\"type\": \"memo_reminder\", \"content\": \"写数学作业\", \"memo_id\": 4, \"open_window_id\": 2}','normal','2025-10-15 21:22:11',1,'2025-10-15 21:22:11','2025-10-15 21:22:20'),(11,22,'{\"type\": \"message\", \"content\": \"hi\", \"audio_url\": null, \"sender_id\": 11, \"timestamp\": \"2025-10-21T22:12:40.791000+08:00\", \"message_id\": 3, \"receiver_id\": 22}','normal',NULL,1,'2025-10-21 22:12:41','2025-10-21 22:13:04'),(12,11,'{\"type\": \"message\", \"content\": \"hi\", \"audio_url\": null, \"sender_id\": 22, \"timestamp\": \"2025-10-21T22:53:20.801000+08:00\", \"message_id\": 4, \"receiver_id\": 11}','normal',NULL,1,'2025-10-21 22:53:21','2025-10-21 22:54:03'),(13,11,'{\"type\": \"message\", \"content\": \"hi\", \"audio_url\": null, \"sender_id\": 22, \"timestamp\": \"2025-10-21T23:03:20.071000+08:00\", \"message_id\": 5, \"receiver_id\": 11, \"sender_name\": \"Jason\"}','normal',NULL,1,'2025-10-21 23:03:20','2025-10-21 23:03:57'),(14,22,'{\"type\": \"message\", \"content\": \"下课记得找我\", \"audio_url\": null, \"sender_id\": 9, \"timestamp\": \"2025-10-23T21:13:28.451000+08:00\", \"message_id\": 6, \"receiver_id\": 22, \"sender_name\": \"teacher_alan\"}','normal',NULL,1,'2025-10-23 21:13:28','2025-10-23 21:14:10'),(15,9,'{\"type\": \"message\", \"content\": \"收到\", \"audio_url\": null, \"sender_id\": 22, \"timestamp\": \"2025-10-23T21:14:05.931000+08:00\", \"message_id\": 7, \"receiver_id\": 9, \"sender_name\": \"Jason\"}','normal',NULL,0,'2025-10-23 21:14:06',NULL),(16,22,'{\"type\": \"message\", \"content\": \"hello\", \"audio_url\": null, \"sender_id\": 9, \"timestamp\": \"2025-11-03T23:01:22.163000+08:00\", \"message_id\": 8, \"receiver_id\": 22, \"sender_name\": \"teacher_alan\"}','normal',NULL,1,'2025-11-03 23:01:27','2025-11-03 23:01:54'),(17,9,'{\"type\": \"message\", \"content\": \"shoudao\", \"audio_url\": null, \"sender_id\": 22, \"timestamp\": \"2025-11-03T23:02:06.532000+08:00\", \"message_id\": 9, \"receiver_id\": 9, \"sender_name\": \"Jason\"}','normal',NULL,0,'2025-11-03 23:02:12',NULL);
/*!40000 ALTER TABLE `outgoing_queue` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `parent_students`
--

DROP TABLE IF EXISTS `parent_students`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `parent_students` (
  `id` int NOT NULL AUTO_INCREMENT,
  `parent_id` int NOT NULL,
  `student_id` int NOT NULL,
  `created_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `parent_id` (`parent_id`),
  KEY `student_id` (`student_id`),
  CONSTRAINT `parent_students_ibfk_1` FOREIGN KEY (`parent_id`) REFERENCES `users` (`id`) ON DELETE CASCADE,
  CONSTRAINT `parent_students_ibfk_2` FOREIGN KEY (`student_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=4 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `parent_students`
--

LOCK TABLES `parent_students` WRITE;
/*!40000 ALTER TABLE `parent_students` DISABLE KEYS */;
INSERT INTO `parent_students` VALUES (1,14,11,'2025-09-19 20:03:37'),(2,14,12,'2025-09-19 20:03:37'),(3,23,22,'2025-10-20 16:38:55');
/*!40000 ALTER TABLE `parent_students` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `schools`
--

DROP TABLE IF EXISTS `schools`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `schools` (
  `id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(200) NOT NULL,
  `code` varchar(50) DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `code` (`code`)
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `schools`
--

LOCK TABLES `schools` WRITE;
/*!40000 ALTER TABLE `schools` DISABLE KEYS */;
INSERT INTO `schools` VALUES (1,'东华小学','SCH001');
/*!40000 ALTER TABLE `schools` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `users`
--

DROP TABLE IF EXISTS `users`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `users` (
  `id` int NOT NULL AUTO_INCREMENT,
  `username` varchar(50) NOT NULL,
  `password_hash` varchar(255) NOT NULL,
  `role` enum('student','teacher','parent','admin') NOT NULL,
  `class_id` int DEFAULT NULL,
  `managed_class_id` int DEFAULT NULL,
  `external_id` varchar(32) DEFAULT NULL,
  `school_id` int DEFAULT NULL,
  `is_active` tinyint(1) NOT NULL DEFAULT '1',
  `graduation_date` date DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `username` (`username`),
  UNIQUE KEY `ux_users_external_id` (`external_id`),
  KEY `ix_users_managed_class_id` (`managed_class_id`),
  KEY `ix_users_class_id` (`class_id`),
  KEY `fk_users_school` (`school_id`),
  CONSTRAINT `fk_user_class` FOREIGN KEY (`class_id`) REFERENCES `classes` (`id`),
  CONSTRAINT `fk_user_managed_class` FOREIGN KEY (`managed_class_id`) REFERENCES `classes` (`id`),
  CONSTRAINT `fk_users_school` FOREIGN KEY (`school_id`) REFERENCES `schools` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB AUTO_INCREMENT=24 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `users`
--

LOCK TABLES `users` WRITE;
/*!40000 ALTER TABLE `users` DISABLE KEYS */;
INSERT INTO `users` VALUES (8,'admin','admin','admin',NULL,NULL,'920250008',NULL,1,NULL),(9,'teacher_alan','scrypt:32768:8:1$HMTujUeQOnOP2Hkg$b8b85048839fb0aee594d8033c8e50110b6b194baf7262935c13de25a443b04bebe06adf76b624b9a3972884b03bee0ce0e8eabffea8a396952323912c5cb27b','teacher',NULL,1,'120250009',1,1,NULL),(10,'teacher_beth','scrypt:32768:8:1$HCa6WZiqFnE1CQre$6994c3e8ef39a76228344045728791130a0f0a6d2a1363769461fdb8d4994a67c56e4eda943ae71d01cf2d4e2a04b4d4af379b3a0432c37683b0cd44f48a3418','teacher',NULL,2,'120250010',1,1,NULL),(11,'student_amy','scrypt:32768:8:1$7gYk9aSssGzdy9R5$b94c97a223d4822aa68108c7c26a13068952894c5270e820062e40a6758dfa7eea0fa32201a33921a65ff85ff11add7bc8c0169433d508c092065541738652ce','student',1,NULL,'202500011',1,1,NULL),(12,'student_bob','scrypt:32768:8:1$llzBTfYykxw7LHTn$42ac8336314824a15b93490458d694fc02a5172f7c31d829426327c458e0ea4d96e0de387b66c769e1f1d128124a0130152c0d051ca87351af4523378606b7c1','student',1,NULL,'202500012',1,1,NULL),(13,'student_cathy','scrypt:32768:8:1$nDEuwHk239kn5pMY$8370f7637cd0a425a07cb84a6f7e942c13425a5f9e76c3ad1f2f6db352ea5d2b9f2852dac4476749065e67592309cf649113381f7e8d59ce33b39a69ae18c240','student',2,NULL,'202500013',1,1,NULL),(14,'parent_mr_x','scrypt:32768:8:1$VdSzOYDUgT9KNcVV$aa7a49eb31da4758b2b8ef51674b072270e28d67d7b834936d6fef01657969cfde1ad025e5d626d8479d2e2c080544d1fbbe82c724521b813c89ab1cde2480cd','parent',NULL,NULL,'320250014',1,1,NULL),(16,'testuser001','scrypt:32768:8:1$OTd4zqm5v5LckPmk$513c8af9cedcf5e02463ae440ded2676590f653bc8690ec870bf50f0365c80d1e9180acd493ebb1e45b80cbe3775d813eb103929f7d716a14e6fd92594cf3dad','student',NULL,NULL,'test_user_001',NULL,1,NULL),(17,'teststudent001','scrypt:32768:8:1$HliKimwZHtEsrSzh$cc960fc46c6248f2dd8032774519c491fed30ec846892228644c271f870c08971eff0a3250990e1c1c4c3022d34abb7c879515bf17381fbd23d41e0eb3ac17e2','student',1,NULL,'test_student_001',1,1,NULL),(18,'testteacher001','scrypt:32768:8:1$8d0NWKFnB1h5ZuzT$0880cea02eb8e0c153cd23f7a1846aa4a5853951b4581219f0b4ed36fd5f1a402d53ee5a7e666d6b7fa3ca13e9941792fde5ee933abccbcdae8554e770abebed','teacher',NULL,1,'test_teacher_001',1,1,NULL),(20,'testparentclass','scrypt:32768:8:1$syKrlYUXcxLBGinC$a131da2950881dcf2e6cf528b1d5c62297350439a432464682cd1c8038c0a92e38852286c174d42ae84bb71f314141c4171879f374ad6af5824fb4d122e78573','parent',1,NULL,'test_parent_with_class',1,1,NULL),(21,'testadminnoclass','scrypt:32768:8:1$f0epKZCarJkFPI4Q$04eca3e79dd60db6644aba590ae802c12cee46ecf662babef764c1c445e48efe15355208b06339ba623e66480c1b18dd74225fd20548332eb727a8c481459019','admin',NULL,NULL,'test_admin_no_class',1,1,NULL),(22,'Jason','scrypt:32768:8:1$xJFl1YlAfFiINN7p$f79a49b3c4b333f8f38fe350d73eab1833966fcafe3d38f3e0bdbe958a9c1506f1f105ba053c1740ca0d6a88324ce97b9c90aa4a5d0487bd925c05af9d42fae4','student',1,NULL,'2351020207',1,1,NULL),(23,'Mandy','scrypt:32768:8:1$kmn9kA35KDv7lYOp$9a76cd3cf837cb2e89c11c2d83d1b2cd9713d44c9eb57ed0a1556294d38e3989fe3f498fce51d73c63d0048ecebf9ce9fdd1d1f0fecaafba9b80e21cb976e4de','parent',1,NULL,'323421134',1,1,NULL);
/*!40000 ALTER TABLE `users` ENABLE KEYS */;
UNLOCK TABLES;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2025-11-24 19:18:25
